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
