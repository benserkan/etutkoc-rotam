"""SMS sağlayıcı — pluggable (VatanSMS veya Netgsm) + dev mode log-only.

Tek public fonksiyon: `send_sms(phone, message)`.

Seçim: `settings.sms_provider` = "vatansms" (default) veya "netgsm".

Modlar:
  - `settings.sms_enabled == False` → log-only (dev). HTTP çağrısı yok,
    panelde `dev_test_code` UI'da kullanıcıya gösterilir.
  - `settings.sms_enabled == True` → gerçek HTTP çağrısı.

Network/permanent hatalarda exception YÜKSELTMEZ — False döndürür ki çağıran
(phone_service) bunu kullanıcıya "sms_send_failed" olarak yansıtır.

### VatanSMS REST (default)
- Endpoint: POST https://api.vatansms.net/api/v1/1toN
- Auth: JSON body içinde `api_id` + `api_key`
- Bireysel hesap (TC kimlik + e-devlet yerleşim belgesi) ile aynı gün açılır

### Netgsm REST
- Endpoint: GET {base}/sms/send/get?usercode=&password=&gsmno=&message=&msgheader=
- Auth: query string'de user + password
- Genelde kurumsal hesap gerekir
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


def is_sms_enabled() -> bool:
    """Prod'da SMS gerçek mi gönderiliyor?"""
    return bool(getattr(settings, "sms_enabled", False))


def get_provider_name() -> str:
    """Hangi sağlayıcı aktif (vatansms | netgsm)."""
    name = (getattr(settings, "sms_provider", "vatansms") or "vatansms").strip().lower()
    return name if name in ("vatansms", "netgsm") else "vatansms"


def send_sms(phone_e164: str, message: str) -> bool:
    """SMS gönder. Başarı → True, hata → False (logla).

    phone_e164: E.164 normalize, "+" olmadan ("905321234567")
    message: SMS gövdesi (160 karakter standart, fazlasında sağlayıcı parça'lar)
    """
    if not is_sms_enabled():
        # Dev mode — log + dönüş True (akışın devam etmesini sağla)
        logger.info(
            "[SMS dev stub] to=%s msg=%s (kullanıcı paneline dev_test_code yansıyacak)",
            phone_e164,
            message[:80],
        )
        return True

    provider = get_provider_name()
    if provider == "netgsm":
        return _send_via_netgsm(phone_e164, message)
    # Default: vatansms
    return _send_via_vatansms(phone_e164, message)


# =============================================================================
# VatanSMS REST implementation
# =============================================================================


def _vatansms_phone(phone_e164: str) -> str:
    """E.164 (905XXXXXXXXX) → VatanSMS formatı (5XXXXXXXXX, 10 hane).

    VatanSMS TR yerel format kullanır; ülke kodu (90) yok, başında 0 yok.
    """
    s = (phone_e164 or "").strip().replace("+", "")
    # 90 ile başlıyorsa kaldır
    if s.startswith("90") and len(s) >= 12:
        s = s[2:]
    # Başında 0 varsa kaldır
    if s.startswith("0"):
        s = s[1:]
    return s


def _send_via_vatansms(phone_e164: str, message: str) -> bool:
    api_id = getattr(settings, "vatansms_api_id", "") or ""
    api_key = getattr(settings, "vatansms_api_key", "") or ""
    sender = getattr(settings, "vatansms_sender", "") or ""
    base = (getattr(settings, "vatansms_base_url", "") or "https://api.vatansms.net").rstrip("/")

    if not (api_id and api_key and sender):
        logger.error("VatanSMS konfigi eksik (api_id/api_key/sender).")
        return False

    phone_local = _vatansms_phone(phone_e164)
    if not phone_local:
        logger.error("VatanSMS: geçersiz telefon formatı: %s", phone_e164)
        return False

    # Türkçe karakter varsa "turkce" işaretle (UTF-8 SMS, biraz daha pahalı
    # ama Türkçe doğru gider). Mesajımız OTP olduğu için genelde ASCII.
    has_tr = any(c in message for c in "çğıöşüÇĞİÖŞÜ")
    message_type = "turkce" if has_tr else "normal"

    body = {
        "api_id": api_id,
        "api_key": api_key,
        "sender": sender,
        "message_type": message_type,
        "message": message,
        "phones": [phone_local],
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(f"{base}/api/v1/1toN", json=body)
        try:
            payload = r.json()
        except Exception:
            payload = {"status": False, "raw": r.text[:200]}
        if r.status_code == 200 and payload.get("status") is True:
            logger.info(
                "VatanSMS gönderildi: to=%s report_id=%s",
                phone_local,
                payload.get("report_id"),
            )
            return True
        logger.error(
            "VatanSMS hata: to=%s http=%s payload=%s",
            phone_local,
            r.status_code,
            payload,
        )
        return False
    except Exception as e:
        logger.exception("VatanSMS exception: %s", e)
        return False


# =============================================================================
# Netgsm REST implementation (legacy)
# =============================================================================


def _send_via_netgsm(phone_e164: str, message: str) -> bool:
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
