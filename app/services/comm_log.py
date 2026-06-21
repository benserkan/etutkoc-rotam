"""Merkezi iletişim loglama — tüm kanallar buradan `communication_logs`'a yazar.

İlke: **best-effort + tam izolasyon**. Loglama ASLA gönderim akışını bozmaz
(hata yutulur) ve çağıranın DB transaction'ından bağımsızdır (kendi kısa
SessionLocal'ını açar, commit eder, kapatır). Bu sayede `send_email` / `send_sms`
gibi DB session'ı olmayan yerlerden de güvenle çağrılır.

Süper admin "İletişim Sağlığı" merkezi bu tablodan okur. Bounce webhook'u
(`mark_delivery`) durum günceller.
"""

from __future__ import annotations

import logging

from app.database import SessionLocal
from app.models import CommunicationLog
from app.models.communication_log import (
    CHANNEL_EMAIL,
    CHANNEL_PUSH,
    CHANNEL_SMS,
    CHANNEL_WHATSAPP,
    STATUS_BOUNCED,
    STATUS_COMPLAINED,
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PRECEDENCE,
    STATUS_SENT,
)

logger = logging.getLogger(__name__)

_MAX_SUBJECT = 480
_MAX_ERR = 1000


def _clip(s: str | None, n: int) -> str | None:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n]


def mask_token(token: str | None) -> str | None:
    """Push token'ı maskele (tam token saklanmaz; PII/secret değil ama gerek yok)."""
    if not token:
        return None
    t = token.strip()
    if len(t) <= 14:
        return t[:4] + "…"
    return f"{t[:12]}…{t[-4:]}"


def record(
    channel: str,
    *,
    db=None,
    status: str = STATUS_SENT,
    to_address: str | None = None,
    to_user_id: int | None = None,
    category: str | None = None,
    subject: str | None = None,
    provider: str | None = None,
    provider_message_id: str | None = None,
    error: str | None = None,
    meta_json: str | None = None,
    sent_at=None,
) -> int | None:
    """Bir gönderim kaydı yaz. Hata olursa sessizce None döner (akışı bozmaz).

    `db` verilirse çağıranın transaction'ına SAVEPOINT içinde eklenir (atomik +
    SQLite tek-yazar kilidi sorunu yaşanmaz; satır çağıran commit edince kalıcı
    olur). Verilmezse kendi kısa SessionLocal'ını açıp commit eder (DB session'ı
    olmayan send_email/send_sms için).
    """
    def _build() -> CommunicationLog:
        return CommunicationLog(
            channel=channel,
            status=status,
            to_address=_clip(to_address, 320),
            to_user_id=to_user_id,
            category=_clip(category, 64),
            subject=_clip(subject, _MAX_SUBJECT),
            provider=_clip(provider, 32),
            provider_message_id=_clip(provider_message_id, 255),
            error=_clip(error, _MAX_ERR),
            meta_json=meta_json,
            sent_at=sent_at,
        )

    try:
        if db is not None:
            # Çağıranın session'ı — SAVEPOINT ile izole (hata outer txn'i bozmaz)
            try:
                with db.begin_nested():
                    row = _build()
                    db.add(row)
                    db.flush()
                return row.id
            except Exception as e:  # noqa: BLE001
                logger.warning("comm_log.record (shared) failed (non-fatal): %s", e)
                return None
        with SessionLocal() as s:
            row = _build()
            s.add(row)
            s.commit()
            return row.id
    except Exception as e:  # noqa: BLE001 — loglama gönderimi asla bozmaz
        logger.warning("comm_log.record failed (non-fatal): %s", e)
        return None


# ---- Kanal kısayolları (çağrı yerlerini sade tutmak için) ----

def log_email(**kw) -> int | None:
    return record(CHANNEL_EMAIL, provider=kw.pop("provider", "smtp"), **kw)


def log_push(**kw) -> int | None:
    return record(CHANNEL_PUSH, provider=kw.pop("provider", "expo"), **kw)


def log_whatsapp(**kw) -> int | None:
    return record(CHANNEL_WHATSAPP, provider=kw.pop("provider", "whatsapp_link"), **kw)


def log_sms(**kw) -> int | None:
    return record(CHANNEL_SMS, provider=kw.pop("provider", "sms"), **kw)


# ---- E-posta teslimat/bounce olayı (ZeptoMail webhook → durum güncelle) ----

def apply_email_event(
    recipient: str | None,
    status: str,
    *,
    reason: str | None = None,
    message_id: str | None = None,
    window_days: int = 14,
) -> int:
    """Bir e-posta gönderim satırını DELIVERED/BOUNCED/COMPLAINED olarak güncelle.

    Eşleşme: önce Message-ID (varsa), yoksa alıcı adresi + en yeni açık satır.
    Güncelleme ÖNCELİK sırasına göre: yalnız daha kesin duruma yükseltir (delivered'ı
    sent'e, bounced/complained'ı delivered'a düşürmez). Döner: güncellenen satır (0/1).
    """
    if status not in (STATUS_DELIVERED, STATUS_BOUNCED, STATUS_COMPLAINED):
        return 0
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func as _func

    try:
        with SessionLocal() as db:
            since = datetime.now(timezone.utc) - timedelta(days=window_days)
            base = db.query(CommunicationLog).filter(
                CommunicationLog.channel == CHANNEL_EMAIL,
                CommunicationLog.created_at >= since,
            )
            row = None
            if message_id:
                row = (
                    base.filter(CommunicationLog.provider_message_id == message_id)
                    .order_by(CommunicationLog.id.desc())
                    .first()
                )
            if row is None and recipient:
                row = (
                    base.filter(
                        _func.lower(CommunicationLog.to_address)
                        == recipient.strip().lower(),
                        CommunicationLog.status.in_([STATUS_SENT, STATUS_DELIVERED]),
                    )
                    .order_by(CommunicationLog.id.desc())
                    .first()
                )
            if row is None:
                return 0
            cur = STATUS_PRECEDENCE.get(row.status, 0)
            new = STATUS_PRECEDENCE.get(status, 0)
            if new <= cur:
                return 0  # daha kesin değil → dokunma (örn. delivered'ı sent yapma)
            row.status = status
            if reason:
                row.error = _clip(reason, _MAX_ERR)
            db.commit()
            return 1
    except Exception as e:  # noqa: BLE001
        logger.warning("apply_email_event failed (non-fatal): %s", e)
        return 0


# ---- WhatsApp teslimat olayı (Cloud API webhook → durum güncelle) ----

# Meta status → comm_log status (read'i delivered sayarız; model'de read yok)
_WA_EVENT_MAP = {
    "sent": STATUS_SENT,
    "delivered": STATUS_DELIVERED,
    "read": STATUS_DELIVERED,
    "failed": STATUS_FAILED,
}


def apply_whatsapp_event(
    provider_message_id: str | None,
    event: str,
    *,
    reason: str | None = None,
    window_days: int = 14,
) -> int:
    """WhatsApp gönderim satırını Meta status callback'iyle güncelle (Cloud API webhook).

    Eşleşme: Meta message id (gönderimde sakladığımız provider_message_id).
    ÖNCELİK sırasına göre yalnız daha kesin duruma yükseltir (delivered'ı sent'e düşürmez).
    """
    if not provider_message_id:
        return 0
    new_status = _WA_EVENT_MAP.get((event or "").lower())
    if new_status is None:
        return 0
    from datetime import datetime, timedelta, timezone

    try:
        with SessionLocal() as db:
            since = datetime.now(timezone.utc) - timedelta(days=window_days)
            row = (
                db.query(CommunicationLog)
                .filter(
                    CommunicationLog.channel == CHANNEL_WHATSAPP,
                    CommunicationLog.provider_message_id == provider_message_id,
                    CommunicationLog.created_at >= since,
                )
                .order_by(CommunicationLog.id.desc())
                .first()
            )
            if row is None:
                return 0
            cur = STATUS_PRECEDENCE.get(row.status, 0)
            new = STATUS_PRECEDENCE.get(new_status, 0)
            if new <= cur:
                return 0
            row.status = new_status
            if reason:
                row.error = _clip(reason, _MAX_ERR)
            db.commit()
            return 1
    except Exception as e:  # noqa: BLE001
        logger.warning("apply_whatsapp_event failed (non-fatal): %s", e)
        return 0
