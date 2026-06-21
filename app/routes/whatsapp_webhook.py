"""WhatsApp Cloud API webhook — verify + status callbacks.

GET /webhooks/whatsapp — Meta verify aşaması (hub.verify_token eşleşmeli)
POST /webhooks/whatsapp — gerçek event'ler (message status: sent/delivered/read/failed)

İmza doğrulaması (X-Hub-Signature-256) zorunludur. App Secret yoksa POST 200 OK
döner ama log "ignored" olur (Meta retry'larını boğmadan, ama state güncellemez).

NotificationLog ile bağlantı: gönderim sonrası external_id = wamid.xxx kaydedilmiş
olur; webhook payload'undaki messages[].id buna eşlenir → status alanı güncellenir.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_db
from app.models import NotificationLog, NotificationStatus
from app.services import comm_log
from app.services.whatsapp import verify_webhook_signature


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/whatsapp")
def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
):
    """Meta'nın webhook abonelik doğrulaması.

    Meta config sayfasında 'verify token' girersin → buradaki settings'tekiyle
    eşleşmeli. Eşleşirse hub.challenge string'ini geri döndürürüz.
    """
    expected = settings.whatsapp_webhook_verify_token
    if hub_mode == "subscribe" and expected and hub_verify_token == expected:
        return PlainTextResponse(content=hub_challenge or "", status_code=200)
    return PlainTextResponse(content="forbidden", status_code=403)


@router.post("/whatsapp")
async def whatsapp_callback(request: Request, db: Session = Depends(get_db)):
    """Meta'dan gelen status/message event'lerini işler.

    Şu an SADECE outbound mesajların status callback'leri ile ilgileniyoruz
    (sent/delivered/read/failed). Inbound mesajlara şimdilik cevap vermiyoruz.
    """
    body_bytes = await request.body()
    sig = request.headers.get("x-hub-signature-256")

    # İmza doğrulanamıyorsa 200 OK ama state güncellemiyoruz — Meta retry'ı
    # bizi DDoS etmesin diye 4xx yerine 200 + log uyarısı.
    if not verify_webhook_signature(body=body_bytes, signature_header=sig):
        logger.warning("WA webhook imzasız/yanlış imzalı çağrı reddedildi.")
        return Response(status_code=200)

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("WA webhook gövdesi parse edilemedi.")
        return Response(status_code=200)

    # Meta payload yapısı: entry[].changes[].value.statuses[]
    updated = 0
    try:
        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                for st in value.get("statuses", []) or []:
                    msg_id = st.get("id")
                    status_str = st.get("status")  # sent | delivered | read | failed
                    if not msg_id or not status_str:
                        continue

                    # K2 — yeni İletişim Sağlığı (communication_logs) teslim güncellemesi.
                    # NotificationLog'tan AYRI; Cloud API ile gönderilen branded teklifler
                    # yalnız comm_log'ta olduğundan burada güncellenir.
                    _wa_err = None
                    if status_str == "failed":
                        _e = (st.get("errors") or [{}])[0]
                        _wa_err = f"{_e.get('code', '?')} {_e.get('title') or _e.get('message') or ''}"[:200]
                    comm_log.apply_whatsapp_event(msg_id, status_str, reason=_wa_err)

                    log = (
                        db.query(NotificationLog)
                        .filter(NotificationLog.external_id == msg_id)
                        .first()
                    )
                    if not log:
                        continue

                    # Final state: failed → FAILED. delivered/read → SENT (zaten SENT olmalı).
                    if status_str == "failed":
                        log.status = NotificationStatus.FAILED
                        err = (st.get("errors") or [{}])[0]
                        log.error = (
                            f"wa_failed:{err.get('code', '?')} "
                            f"{err.get('title') or err.get('message') or ''}"
                        )[:300]
                    elif status_str in ("sent", "delivered", "read"):
                        # SENT ile yetiniyoruz — delivered/read ekstra payload'da
                        # tutulabilir ama şu an gerek yok.
                        if log.status == NotificationStatus.QUEUED:
                            log.status = NotificationStatus.SENT
                            log.sent_at = log.sent_at or datetime.now(timezone.utc)
                    updated += 1
    except Exception as e:
        logger.exception("WA webhook payload işleme hatası: %s", e)

    if updated:
        db.commit()
        logger.info("WA webhook %d log kaydı güncelledi.", updated)

    return Response(status_code=200)
