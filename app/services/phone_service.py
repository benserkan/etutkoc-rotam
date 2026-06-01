"""Telefon doğrulama servisi — P1 (2026-05-30).

Yaşam döngüsü (kanal: SMS):
  1. `start_phone_verification(db, user, phone, slot)` →
     - phone'u E.164'e normalize et
     - 60 saniye cooldown kontrolü
     - 6 haneli kod üret + sms_provider.send_sms() çağır
     - PhoneVerification satırı yaz (10dk TTL); önceki tüketilmemiş satırı iptal et
  2. `verify_phone(db, user, code, slot)` →
     - Aktif satırı bul (consumed=NULL, expires_at > now)
     - attempts++; >=5 → SUPPRESSED
     - Kod eşleşirse: User.phone (veya phone_secondary) + verified_at set
     - consumed_at = now
  3. `delete_phone(db, user, slot)` → User.phone alanlarını NULL'a çek

Önemli: User.phone "doğrulanmış" olabilmesi için verified_at dolu olmalı.
Çağıran kodlar (örn. producer kanal=WHATSAPP) verified_at != None kontrolü yapar.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from app.models import PhoneVerification, User
from app.services.sms_provider import is_sms_enabled, send_sms


logger = logging.getLogger(__name__)


# Sabit konfig
OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


class PhoneSlot(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class PhoneError(Exception):
    """phone_service hatası — error_code Pydantic detail'e yansıtılır."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ----------------------------------------------------------------------
# Normalize
# ----------------------------------------------------------------------

_DIGIT_RE = re.compile(r"\D")


def normalize_e164_tr(raw: str) -> Optional[str]:
    """Türkiye formatına göre E.164'e dönüştür ("+" YOK, "905321234567").

    Kabul ettikleri:
      - "0532 123 45 67"
      - "+90 532 123 45 67"
      - "+905321234567"
      - "905321234567"
      - "5321234567" (öncül 0 yok)

    Reddedilenler: rakam <10 veya >13, "5" ile başlamayan mobil olmayan (sabit
    telefon vb. — TR cep telefonu 5XX). P1 yalnız cep telefonu hedefler.

    Dönüş: "905321234567" (12 hane) veya None.
    """
    if not raw:
        return None
    digits = _DIGIT_RE.sub("", raw)
    if not digits:
        return None
    # +90 önekini at: 90 ile başlayan + uzunluk 12 ise muhtemelen +90
    if digits.startswith("90") and len(digits) == 12:
        candidate = digits
    elif digits.startswith("0") and len(digits) == 11:
        candidate = "9" + digits  # 05XXXXXXXXX → 905XXXXXXXXX
    elif len(digits) == 10:
        candidate = "90" + digits
    else:
        return None
    # Cep telefonu kontrolü: 90 sonrası 5 ile başlamalı (5XX)
    if not (candidate.startswith("90") and len(candidate) == 12 and candidate[2] == "5"):
        return None
    return candidate


# ----------------------------------------------------------------------
# OTP üretimi + cooldown
# ----------------------------------------------------------------------


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _phone_field_name(slot: PhoneSlot) -> tuple[str, str]:
    """User modelindeki kolon adlarını döndür (phone_field, verified_at_field)."""
    if slot == PhoneSlot.SECONDARY:
        return "phone_secondary", "phone_secondary_verified_at"
    return "phone", "phone_verified_at"


def _slot_str(slot: PhoneSlot) -> str:
    return slot.value


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def start_phone_verification(
    db: Session,
    *,
    user: User,
    phone: str,
    slot: PhoneSlot = PhoneSlot.PRIMARY,
) -> PhoneVerification:
    """OTP üret + SMS gönder + DB'ye yaz. Cooldown ihlal → PhoneError.

    Aynı user için son aktif satır 60sn'den eski değilse cooldown_active hatası.
    Önceki tüketilmemiş satırlar iptal edilir (consumed_at = now + attempts=99).
    """
    normalized = normalize_e164_tr(phone)
    if not normalized:
        raise PhoneError(
            "invalid_phone",
            "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir.",
        )

    now = datetime.now(timezone.utc)

    # Cooldown — son satıra bak
    last = (
        db.query(PhoneVerification)
        .filter(
            PhoneVerification.user_id == user.id,
            PhoneVerification.slot == _slot_str(slot),
            PhoneVerification.consumed_at.is_(None),
        )
        .order_by(PhoneVerification.id.desc())
        .first()
    )
    if last is not None:
        age = (now - last.created_at.replace(tzinfo=timezone.utc) if last.created_at.tzinfo is None else now - last.created_at).total_seconds()
        if age < OTP_RESEND_COOLDOWN_SECONDS:
            raise PhoneError(
                "cooldown_active",
                f"Çok hızlı yeni kod istediniz. {int(OTP_RESEND_COOLDOWN_SECONDS - age)} saniye sonra tekrar deneyin.",
            )
        # Aktif satırı iptal et — yenisi yazılacak
        last.consumed_at = now

    code = _generate_otp_code()
    expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)
    pv = PhoneVerification(
        user_id=user.id,
        phone=normalized,
        code=code,
        slot=_slot_str(slot),
        channel="sms",
        expires_at=expires_at,
    )
    db.add(pv)
    db.flush()

    # SMS gönder
    message = (
        f"ETUTKOC Rotam dogrulama kodunuz: {code}\n"
        f"Kod 10 dakika gecerlidir. Paylasmayiniz."
    )
    ok = send_sms(normalized, message)
    if not ok and is_sms_enabled():
        # Prod'da gerçek sağlayıcı çalışmadı → satırı sil, hata fırlat
        db.delete(pv)
        db.flush()
        raise PhoneError(
            "sms_send_failed",
            "SMS gönderilemedi. Lütfen birkaç dakika sonra tekrar deneyin.",
        )

    return pv


def verify_phone(
    db: Session,
    *,
    user: User,
    code: str,
    slot: PhoneSlot = PhoneSlot.PRIMARY,
) -> User:
    """OTP'yi doğrula → User.phone alanlarını set et + consumed_at."""
    now = datetime.now(timezone.utc)
    code_norm = (code or "").strip()
    if not code_norm or not code_norm.isdigit() or len(code_norm) != 6:
        raise PhoneError("invalid_code_format", "Doğrulama kodu 6 haneli olmalı.")

    pv = (
        db.query(PhoneVerification)
        .filter(
            PhoneVerification.user_id == user.id,
            PhoneVerification.slot == _slot_str(slot),
            PhoneVerification.consumed_at.is_(None),
        )
        .order_by(PhoneVerification.id.desc())
        .first()
    )
    if pv is None:
        raise PhoneError(
            "no_pending_verification",
            "Bekleyen doğrulama yok. Önce 'Doğrulama kodu gönder' deyin.",
        )

    expires_at = pv.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        pv.consumed_at = now
        db.flush()
        raise PhoneError(
            "expired",
            "Kod süresi doldu. Yeni kod isteyin.",
        )

    pv.attempts = (pv.attempts or 0) + 1

    if not secrets.compare_digest(pv.code, code_norm):
        if pv.attempts >= OTP_MAX_ATTEMPTS:
            pv.consumed_at = now
            db.flush()
            raise PhoneError(
                "too_many_attempts",
                "Çok fazla hatalı deneme. Yeni kod isteyin.",
            )
        db.flush()
        raise PhoneError("otp_mismatch", "Kod hatalı.")

    # Başarılı — User.phone alanlarını set et
    phone_field, verified_field = _phone_field_name(slot)
    setattr(user, phone_field, pv.phone)
    setattr(user, verified_field, now)
    pv.consumed_at = now
    db.flush()
    return user


def save_phone_unverified(
    db: Session,
    *,
    user: User,
    phone: str,
    slot: PhoneSlot = PhoneSlot.PRIMARY,
) -> str:
    """Soft mod: numarayı DOĞRULAMADAN kaydet (verified_at=None).

    SMS doğrulama henüz operasyonel değilken (is_sms_enabled False) kullanıcı
    numarasını kaydedebilsin diye — böylece Click-to-WhatsApp gönderimi çalışır.
    SMS açıldığında numara verify_phone ile doğrulanır. Numara normalize edilir,
    bekleyen OTP satırları iptal edilir.
    """
    normalized = normalize_e164_tr(phone)
    if not normalized:
        raise PhoneError(
            "invalid_phone",
            "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir.",
        )
    phone_field, verified_field = _phone_field_name(slot)
    setattr(user, phone_field, normalized)
    setattr(user, verified_field, None)  # doğrulanmadı — SMS açılınca doğrulanır
    db.query(PhoneVerification).filter(
        PhoneVerification.user_id == user.id,
        PhoneVerification.slot == _slot_str(slot),
        PhoneVerification.consumed_at.is_(None),
    ).update(
        {PhoneVerification.consumed_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.flush()
    return normalized


def delete_phone(
    db: Session,
    *,
    user: User,
    slot: PhoneSlot = PhoneSlot.PRIMARY,
) -> User:
    """Telefonu kullanıcıdan kaldır. Geri alma yok."""
    phone_field, verified_field = _phone_field_name(slot)
    setattr(user, phone_field, None)
    setattr(user, verified_field, None)
    # Aktif tüm pending OTP'leri iptal et
    db.query(PhoneVerification).filter(
        PhoneVerification.user_id == user.id,
        PhoneVerification.slot == _slot_str(slot),
        PhoneVerification.consumed_at.is_(None),
    ).update(
        {PhoneVerification.consumed_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.flush()
    return user


# ----------------------------------------------------------------------
# UI yardımcısı: dev modda paneline kodu döndür
# ----------------------------------------------------------------------


def pending_verification_for(
    db: Session,
    *,
    user: User,
    slot: PhoneSlot = PhoneSlot.PRIMARY,
) -> PhoneVerification | None:
    """En son aktif (consumed=NULL, expires_at>now) OTP satırını döndür."""
    now = datetime.now(timezone.utc)
    pv = (
        db.query(PhoneVerification)
        .filter(
            PhoneVerification.user_id == user.id,
            PhoneVerification.slot == _slot_str(slot),
            PhoneVerification.consumed_at.is_(None),
            PhoneVerification.expires_at > now,
        )
        .order_by(PhoneVerification.id.desc())
        .first()
    )
    return pv
