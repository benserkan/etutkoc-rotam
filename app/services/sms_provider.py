"""SMS sağlayıcı — Netgsm REST API + dev mode log-only.

Tek public fonksiyon: `send_sms(phone, message)`.

- `settings.sms_enabled == False` → log-only (dev). Hiçbir HTTP çağrısı
  yapılmaz, panelde `dev_test_code` UI'da kullanıcıya gösterilir.
- `settings.sms_enabled == True` → Netgsm REST API'ye GET çağrısı.

Netgsm "Sms Gönderme — SMS GET" endpoint'i (en sade):
    GET /sms/send/get?usercode={user}&password={pass}&gsmno={phone}
        &message={msg}&msgheader={header}&dil=TR

Başarılı yanıt: kod "00" ile başlar (ör: "00 12345"); hata: "20"/"30"/...

Bu fonksiyon network/permanent hatalarda exception YÜKSELTMEZ — False döndürür
ki çağıran (phone_service) bunu kullanıcıya "sms_send_failed" olarak yansıtır.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


def is_sms_enabled() -> bool:
    """Prod'da SMS gerçek mi gönderiliyor?"""
    return bool(getattr(settings, "sms_enabled", False))


def send_sms(phone_e164: str, message: str) -> bool:
    """SMS gönder. Başarı → True, hata → False (logla).

    phone_e164: E.164 normalize, "+" olmadan ("905321234567")
    message: SMS gövdesi (max 160 karakter standart, fazla uzarsa Netgsm parça'lar)
    """
    if not is_sms_enabled():
        # Dev mode — log + dönüş True (akışın devam etmesini sağla)
        logger.info(
            "[SMS dev stub] to=%s msg=%s (kullanıcı paneline dev_test_code yansıyacak)",
            phone_e164,
            message[:80],
        )
        return True

    user = getattr(settings, "netgsm_user", "") or ""
    password = getattr(settings, "netgsm_password", "") or ""
    header = getattr(settings, "netgsm_header", "") or ""
    base = (getattr(settings, "netgsm_base_url", "") or "").rstrip("/")

    if not (user and password and header and base):
        logger.error("Netgsm konfigi eksik (user/password/header/base_url).")
        return False

    try:
        # Netgsm "SMS GET" — basit, parametreler URL'de
        params = {
            "usercode": user,
            "password": password,
            "gsmno": phone_e164,
            "message": message,
            "msgheader": header,
            "dil": "TR",
        }
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{base}/sms/send/get", params=params)
        text = (r.text or "").strip()
        # "00" başlangıçlı yanıt başarı (örn: "00 12345678")
        if text.startswith("00"):
            logger.info("Netgsm SMS gönderildi: to=%s resp=%s", phone_e164, text)
            return True
        logger.error("Netgsm SMS hata: to=%s resp=%s", phone_e164, text)
        return False
    except Exception as e:
        logger.exception("Netgsm SMS exception: %s", e)
        return False
