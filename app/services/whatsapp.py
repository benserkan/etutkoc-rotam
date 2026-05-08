"""WhatsApp Cloud API client — gerçek httpx tabanlı implementasyon.

Driver pattern: `send_template()` çağrılır; `whatsapp_enabled=True` ise Meta Cloud
API'ye HTTP POST atılır, aksi halde log-only modda sadece logger'a yazar ve "sent"
ile döner. Dispatcher bu fonksiyondan dönen WhatsAppResult'ı kullanır.

Konfigürasyon (settings):
    WHATSAPP_ENABLED — true → gerçek gönderim
    WHATSAPP_API_VERSION — "v21.0" gibi
    WHATSAPP_PHONE_NUMBER_ID — Meta'nın atadığı sayısal ID
    WHATSAPP_ACCESS_TOKEN — Bearer token (kalıcı veya 60 gün)
    WHATSAPP_APP_SECRET — webhook imza doğrulama
    WHATSAPP_WEBHOOK_VERIFY_TOKEN — GET verify aşaması
    WHATSAPP_DEFAULT_LANGUAGE — "tr" gibi
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


@dataclass
class WhatsAppResult:
    success: bool
    external_id: str | None = None
    error: str | None = None


def _whatsapp_enabled() -> bool:
    return bool(
        getattr(settings, "whatsapp_enabled", False)
        and settings.whatsapp_phone_number_id
        and settings.whatsapp_access_token
    )


def normalize_phone(phone: str) -> str | None:
    """E.164 benzeri düzenleme — '+', rakam dışı her şey atılır.

    Türkiye numarası heuristic:
      - "0532..." → "90532..."
      - "+90532..." → "90532..."
      - "532..." (10 hane) → "90532..."
    Geçersizse None döner.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return None
    # 0 ile başlayan TR formatını düzelt
    if digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10 and digits.startswith("5"):
        digits = "90" + digits
    if len(digits) < 10 or len(digits) > 15:
        return None
    return digits


def send_template(
    *,
    to_phone: str,
    template_name: str,
    components: list[dict[str, Any]] | None = None,
    language_code: str | None = None,
) -> WhatsAppResult:
    """Onaylı şablon mesajı gönder.

    components: Meta Cloud API formatında değişken doldurma listesi.
        Örnek: [{"type":"body","parameters":[{"type":"text","text":"Ali"}]}]

    Devre dışıysa log atar ve "stub:..." external_id ile başarılı döner.
    Aktifse Meta Graph API'ye POST atar.
    """
    normalized = normalize_phone(to_phone)
    if not normalized:
        return WhatsAppResult(success=False, error="invalid_phone")

    lang = language_code or settings.whatsapp_default_language or "tr"

    if not _whatsapp_enabled():
        logger.info(
            "[WHATSAPP] (devre dışı) → %s | şablon: %s | lang=%s | components: %s",
            normalized, template_name, lang, components,
        )
        return WhatsAppResult(success=True, external_id=f"stub:{template_name}")

    url = (
        f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "to": normalized,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang},
        },
    }
    if components:
        payload["template"]["components"] = components

    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=15.0)
    except httpx.RequestError as e:
        logger.exception("WA HTTP error: %s", e)
        return WhatsAppResult(success=False, error=f"http_error:{type(e).__name__}")

    if r.status_code >= 400:
        # Meta hata gövdesinden mesajı çek
        try:
            body = r.json()
            err = (body.get("error") or {}).get("message") or r.text[:200]
        except Exception:
            err = r.text[:200]
        logger.warning("WA API %s — %s | payload=%s", r.status_code, err, payload)
        return WhatsAppResult(success=False, error=f"http_{r.status_code}:{err[:120]}")

    try:
        data = r.json()
        msg_id = (data.get("messages") or [{}])[0].get("id")
    except Exception:
        msg_id = None
    return WhatsAppResult(success=True, external_id=msg_id or "wa:unknown")


def send_otp(*, to_phone: str, code: str) -> WhatsAppResult:
    """Telefon doğrulama OTP'sini AUTHENTICATION şablonuyla gönder.

    Meta Cloud API AUTHENTICATION kategorisinde "veli_otp_kodu" şablonu kullanılır
    (Sprint 6 öncesinde Meta Business Manager'da onaylatılmalı). Body parametre
    olarak {{1}} = code, button URL/copy_code olarak code geçilir.
    """
    components = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": code}],
        },
        {
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": code}],
        },
    ]
    return send_template(
        to_phone=to_phone,
        template_name="veli_otp_kodu",
        components=components,
        language_code=settings.whatsapp_default_language or "tr",
    )


def verify_webhook_signature(*, body: bytes, signature_header: str | None) -> bool:
    """Meta webhook'unun X-Hub-Signature-256 header'ını doğrula.

    Header formatı: "sha256=<hex>". App Secret yoksa veya devre dışıysa
    False döner (production'da imzasız çağrı reddedilmeli).
    """
    if not settings.whatsapp_app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = signature_header.split("=", 1)[1].strip()
    digest = hmac.new(
        settings.whatsapp_app_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(digest, expected)
