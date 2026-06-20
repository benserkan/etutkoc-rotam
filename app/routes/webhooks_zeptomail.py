"""ZeptoMail bounce/teslimat webhook'u.

POST /webhooks/zeptomail — ZeptoMail "Web Kancaları" olayları (hardbounce/
softbounce/delivery/open/click). İlgili communication_logs satırı DELIVERED veya
BOUNCED olarak güncellenir → süper admin İletişim Sağlığı panosunda "ulaştı /
geri döndü" görünür.

Güvenlik: `settings.zeptomail_webhook_secret` doluysa URL'deki `?token=` eşleşmeli
(eşleşmezse 403). Boşsa tüm POST'lar kabul edilir (yine de loglanır).

ZeptoMail payload biçimi sürümle değişebildiğinden parser SAVUNMACI: olay
listesini + alıcı/sebep/message-id alanlarını esnek arar. İlk gerçek olaylar
log'a yazılır (gerekirse eşleme rafine edilir).
"""

from __future__ import annotations

import json
import logging
from typing import Iterator

from fastapi import APIRouter, Query, Request

from app.config import settings
from app.models.communication_log import (
    STATUS_BOUNCED,
    STATUS_COMPLAINED,
    STATUS_DELIVERED,
)
from app.services import comm_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_BOUNCE_EVENTS = {"hardbounce", "softbounce", "bounce", "bounced"}
# Geribildirim döngüsü = alıcı SPAM işaretledi → şikayet (itibar zedeler)
_COMPLAINT_EVENTS = {
    "feedback_loop", "feedbackloop", "feedback-loop", "fbl",
    "complaint", "complained", "spam", "spam_complaint", "abuse",
}
# open/click teslimatı ima eder → delivered (yalnız 'sent' iken yükseltilir)
_DELIVERED_EVENTS = {
    "email_delivery", "delivery", "delivered",
    "email_open", "open", "opened",
    "email_link_click", "click", "clicked",
}

_RECIPIENT_KEYS = (
    "bounced_recipient", "recipient", "email", "email_address",
    "emailaddress", "to_email", "to", "destination",
)
_REASON_KEYS = ("bounce_reason", "reason", "diagnostic_message", "description", "detail")
_MSGID_KEYS = ("message_id", "messageId", "message_key", "msg_id", "references")


def _events(payload: object) -> Iterator[tuple[str, dict]]:
    """(event_name_lower, detail_dict) çiftleri üret — biçim varyasyonlarına dayanıklı."""
    if not isinstance(payload, dict):
        return
    top_event = str(payload.get("event_name") or payload.get("event") or "").lower()
    msgs = payload.get("event_message") or payload.get("events") or [payload]
    if isinstance(msgs, dict):
        msgs = [msgs]
    if not isinstance(msgs, list):
        return
    for m in msgs:
        if not isinstance(m, dict):
            continue
        ename = str(m.get("event_name") or m.get("event") or top_event).lower()
        details = m.get("details")
        if isinstance(details, list) and details:
            for d in details:
                yield ename, (d if isinstance(d, dict) else {})
        elif isinstance(details, dict):
            yield ename, details
        else:
            yield ename, m


def _search(d: dict, keys: tuple[str, ...], *, want_email: bool = False) -> str | None:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            if want_email and "@" not in v:
                continue
            return v.strip()
    # iç içe alt sözlük/listelerde ara
    for v in d.values():
        if isinstance(v, dict):
            r = _search(v, keys, want_email=want_email)
            if r:
                return r
        elif isinstance(v, list):
            for it in v:
                if isinstance(it, dict):
                    r = _search(it, keys, want_email=want_email)
                    if r:
                        return r
    return None


@router.get("/zeptomail")
def zeptomail_ping():
    """Bağlantı testi (ZeptoMail kurulum kontrolü)."""
    return {"ok": True, "service": "zeptomail-webhook"}


@router.post("/zeptomail")
async def zeptomail_webhook(request: Request, token: str | None = Query(None)):
    secret = settings.zeptomail_webhook_secret
    if secret and token != secret:
        logger.warning("zeptomail webhook: token mismatch")
        from fastapi.responses import Response
        return Response(status_code=403)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}

    try:
        logger.info("zeptomail webhook payload: %s", json.dumps(payload)[:1500])
    except Exception:  # noqa: BLE001
        pass

    updated = 0
    for ename, d in _events(payload):
        recipient = _search(d, _RECIPIENT_KEYS, want_email=True)
        msgid = _search(d, _MSGID_KEYS)
        if ename in _BOUNCE_EVENTS:
            updated += comm_log.apply_email_event(
                recipient, STATUS_BOUNCED,
                reason=_search(d, _REASON_KEYS), message_id=msgid,
            )
        elif ename in _COMPLAINT_EVENTS:
            updated += comm_log.apply_email_event(
                recipient, STATUS_COMPLAINED,
                reason=_search(d, _REASON_KEYS) or "Alıcı spam işaretledi",
                message_id=msgid,
            )
        elif ename in _DELIVERED_EVENTS:
            updated += comm_log.apply_email_event(
                recipient, STATUS_DELIVERED, message_id=msgid,
            )

    return {"ok": True, "updated": updated}
