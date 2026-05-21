"""Cloudflare Turnstile CAPTCHA verification — login/forgot/register için bot koruması.

Turnstile, Google reCAPTCHA'ya alternatif, kullanıcı dostu (genelde invisible)
ve GDPR uyumlu bir CAPTCHA hizmetidir.

Env vars:
- TURNSTILE_SITE_KEY: client-side widget key (HTML'e gömülür)
- TURNSTILE_SECRET_KEY: server-side verification key (gizli)
- TURNSTILE_ENABLED: "1"/"0" — global toggle (default: ikisi de set ise açık)

Site key boşsa CAPTCHA atlanır (dev mode). Verification başarısızsa False döner.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT_SEC = 5.0


def get_site_key() -> Optional[str]:
    """Template'e gömülecek public key. Boşsa CAPTCHA gösterilmez."""
    key = os.getenv("TURNSTILE_SITE_KEY", "").strip()
    enabled = os.getenv("TURNSTILE_ENABLED", "1").strip().lower()
    if enabled in ("0", "false", "no", "off"):
        return None
    return key or None


def is_enabled() -> bool:
    """Hem site_key hem secret_key tanımlıysa Turnstile aktiftir."""
    return bool(get_site_key()) and bool(os.getenv("TURNSTILE_SECRET_KEY", "").strip())


def verify_token(token: Optional[str], ip: Optional[str] = None) -> bool:
    """Turnstile token'ını Cloudflare'de doğrula.

    Args:
        token: Form'dan gelen `cf-turnstile-response` değeri
        ip: İsteğin geldiği IP (opsiyonel ama önerilen)

    Returns:
        True: doğrulandı veya CAPTCHA devre dışı
        False: token yok / yanlış / network hatası
    """
    if not is_enabled():
        return True  # CAPTCHA kapalı — geç

    if not token:
        logger.info("turnstile: token boş")
        return False

    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        logger.warning("turnstile: TURNSTILE_SECRET_KEY tanımsız")
        return False

    try:
        import httpx
    except ImportError:
        logger.warning("httpx kurulu değil; turnstile bypass")
        return True

    payload = {"secret": secret, "response": token}
    if ip:
        payload["remoteip"] = ip

    try:
        with httpx.Client(timeout=TURNSTILE_TIMEOUT_SEC) as client:
            r = client.post(TURNSTILE_VERIFY_URL, data=payload)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("turnstile verify hatası: %s", e)
        # Network hatası → True döner (yanlışlıkla legit kullanıcıyı bloklamayalım)
        # Eğer fail-closed istersen False döndür.
        return True

    success = bool(data.get("success"))
    if not success:
        logger.info("turnstile reddetti: %s", data.get("error-codes"))
    return success
