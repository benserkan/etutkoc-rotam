"""RevenueCat webhook — Apple IAP abonelik olayları.

POST /webhooks/revenuecat — RevenueCat proje ayarlarındaki webhook URL'i.
Olaylar (INITIAL_PURCHASE / RENEWAL / CANCELLATION / EXPIRATION ...)
`iap_service.handle_webhook_event` ile User.plan + abonelik alanlarına işlenir.

GÜVENLİK: Bu webhook PLAN AKTİVE EDER → Authorization header ZORUNLU.
`settings.revenuecat_webhook_auth` boşsa veya header eşleşmezse 403
(zeptomail'in "secret boşsa kabul et" deseni burada bilinçli uygulanmaz —
sahte POST ücretsiz abonelik açabilirdi). RevenueCat Dashboard'da webhook
Authorization değeri .env'deki REVENUECAT_WEBHOOK_AUTH ile birebir aynı
girilir ("Bearer xxx" biçimi de kabul edilir).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services import iap_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/revenuecat")
def revenuecat_ping():
    """Bağlantı testi (kurulum kontrolü) — yapılandırma durumu döner."""
    return {
        "ok": True,
        "service": "revenuecat-webhook",
        "auth_configured": bool(settings.revenuecat_webhook_auth),
    }


@router.post("/revenuecat")
async def revenuecat_webhook(request: Request, db: Session = Depends(get_db)):
    secret = settings.revenuecat_webhook_auth
    header = request.headers.get("authorization") or ""
    if not secret or header not in (secret, f"Bearer {secret}"):
        logger.warning("revenuecat webhook: auth reddedildi (configured=%s)", bool(secret))
        return Response(status_code=403)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    try:
        result = iap_service.handle_webhook_event(db, payload)
    except Exception:  # noqa: BLE001
        # 500 dönersek RevenueCat retry eder — istenen davranış (geçici DB hatası vb.)
        logger.exception("revenuecat webhook işleme hatası")
        return Response(status_code=500)

    return {"ok": True, **result}
