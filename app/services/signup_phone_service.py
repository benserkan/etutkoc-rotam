"""Signup-anı telefon doğrulama kapısı (#5) — hesap OLUŞMADAN ÖNCE OTP.

AMAÇ: çoklu-hesap çiftliğini kökünden kesmek — **bir doğrulanmış telefon = bir
trial hesap**. Koç signup'ında telefonunu SMS OTP ile doğrular; aynı telefon
başka aktif hesapta varsa reddedilir.

DORMANT: kapı yalnız `is_sms_enabled()` (SMS OTP paketi satın alınıp
SMS_ENABLED=true) iken devreye girer. O zamana kadar `signup_phone_required()`
False → signup eskisi gibi (telefon opsiyonel, doğrulamasız). Yani bu kod
deploy edilse de SMS açılana kadar hiçbir signup'ı etkilemez.

Akış (SMS açıkken):
  1. POST /auth/signup/phone/start {phone} → OTP SMS gönderilir (telefon-anahtarlı satır)
  2. POST /auth/signup/phone/verify {phone, code} → kısa ömürlü imzalı phone_token
  3. POST /auth/signup/teacher {..., phone_token} → token doğrulanır, hesap
     phone + phone_verified_at ile açılır.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt as _jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SignupPhoneVerification, User
from app.services.phone_service import PhoneError, normalize_e164_tr
from app.services.sms_provider import is_sms_enabled, send_sms

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
IP_HOURLY_CAP = 10               # SMS bombardımanı / maliyet koruması
TOKEN_TTL_SECONDS = 20 * 60      # doğrulanmış phone_token ömrü
_TOKEN_TYPE = "signup_phone"


def signup_phone_required() -> bool:
    """Signup'ta telefon doğrulama zorunlu mu? Yalnız SMS açıkken (paket alınınca)."""
    return is_sms_enabled()


def _is_dev_stub() -> bool:
    """Dev'de (DEBUG + SMS kapalı) OTP kodu yanıtta gösterilir — smoke için."""
    return bool(getattr(settings, "debug", False) and not is_sms_enabled())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def phone_in_use(db: Session, phone_e164: str) -> bool:
    """Bu doğrulanmış telefon zaten bir hesapta var mı (tekillik)."""
    return (
        db.query(User.id)
        .filter(User.phone == phone_e164, User.phone_verified_at.isnot(None))
        .first()
        is not None
    )


def start_signup_phone(db: Session, *, phone: str, ip: str | None) -> tuple[str, str | None]:
    """OTP üret + SMS gönder + telefon-anahtarlı satır yaz.

    Returns (normalized_phone, dev_code|None). Hatalar PhoneError.
    """
    normalized = normalize_e164_tr(phone)
    if not normalized:
        raise PhoneError("invalid_phone",
                         "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir.")

    # Tekillik — bir telefon = bir hesap
    if phone_in_use(db, normalized):
        raise PhoneError("phone_in_use",
                         "Bu telefon numarası zaten bir hesapla ilişkili. Giriş yapmayı deneyin.")

    now = _now()

    # Per-telefon cooldown
    last = (
        db.query(SignupPhoneVerification)
        .filter(SignupPhoneVerification.phone == normalized,
                SignupPhoneVerification.consumed_at.is_(None))
        .order_by(SignupPhoneVerification.id.desc())
        .first()
    )
    if last is not None:
        age = (now - _aware(last.created_at)).total_seconds()
        if age < OTP_RESEND_COOLDOWN_SECONDS:
            raise PhoneError("cooldown_active",
                             f"Az önce kod gönderildi. {int(OTP_RESEND_COOLDOWN_SECONDS - age)} sn sonra tekrar deneyin.")
        last.consumed_at = now

    # Per-IP saatlik cap (SMS bombardımanı/maliyet koruması)
    if ip:
        recent_ip = (
            db.query(func.count(SignupPhoneVerification.id))
            .filter(SignupPhoneVerification.requested_ip == ip,
                    SignupPhoneVerification.created_at >= now - timedelta(hours=1))
            .scalar() or 0
        )
        if recent_ip >= IP_HOURLY_CAP:
            raise PhoneError("ip_rate_limited",
                             "Bu ağdan çok fazla kod isteği yapıldı. Lütfen daha sonra tekrar deneyin.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    row = SignupPhoneVerification(
        phone=normalized, code=code, channel="sms",
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
        requested_ip=(ip or "")[:64] or None,
    )
    db.add(row)
    db.flush()

    message = (f"ETUTKOC Rotam dogrulama kodunuz: {code}\n"
               f"Kod 10 dakika gecerlidir. Paylasmayiniz.")
    ok = send_sms(normalized, message)
    if not ok and is_sms_enabled():
        db.delete(row)
        db.flush()
        raise PhoneError("sms_send_failed",
                         "SMS gönderilemedi. Lütfen birkaç dakika sonra tekrar deneyin.")

    db.commit()
    return normalized, (code if _is_dev_stub() else None)


def _issue_phone_token(phone_e164: str) -> str:
    now = _now()
    payload = {"phone": phone_e164, "type": _TOKEN_TYPE,
               "iat": int(now.timestamp()),
               "exp": int(now.timestamp()) + TOKEN_TTL_SECONDS}
    return _jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_phone_token(token: str) -> str | None:
    """phone_token'ı çöz → doğrulanmış telefon (E.164) ya da None."""
    try:
        data = _jwt.decode(token.strip(), settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if data.get("type") != _TOKEN_TYPE:
            return None
        return str(data.get("phone")) or None
    except Exception:
        return None


def verify_signup_phone(db: Session, *, phone: str, code: str) -> str:
    """OTP doğrula → kısa ömürlü imzalı phone_token döndür. Hatalar PhoneError."""
    normalized = normalize_e164_tr(phone)
    if not normalized:
        raise PhoneError("invalid_phone", "Geçersiz telefon numarası.")
    code_norm = (code or "").strip()
    if not code_norm.isdigit() or len(code_norm) != 6:
        raise PhoneError("invalid_code_format", "Doğrulama kodu 6 haneli olmalı.")

    now = _now()
    pv = (
        db.query(SignupPhoneVerification)
        .filter(SignupPhoneVerification.phone == normalized,
                SignupPhoneVerification.consumed_at.is_(None))
        .order_by(SignupPhoneVerification.id.desc())
        .first()
    )
    if pv is None:
        raise PhoneError("no_pending_verification",
                         "Bekleyen doğrulama yok. Önce kod gönderin.")
    if _aware(pv.expires_at) <= now:
        pv.consumed_at = now
        db.commit()
        raise PhoneError("expired", "Kod süresi doldu. Yeni kod isteyin.")

    pv.attempts = (pv.attempts or 0) + 1
    if not secrets.compare_digest(pv.code, code_norm):
        if pv.attempts >= OTP_MAX_ATTEMPTS:
            pv.consumed_at = now
            db.commit()
            raise PhoneError("too_many_attempts", "Çok fazla hatalı deneme. Yeni kod isteyin.")
        db.commit()
        raise PhoneError("otp_mismatch", "Kod hatalı.")

    pv.consumed_at = now
    db.commit()
    return _issue_phone_token(normalized)
