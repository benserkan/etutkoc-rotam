"""Cloudflare Turnstile CAPTCHA verification — login/forgot/register için bot koruması.

Turnstile, Google reCAPTCHA'ya alternatif, kullanıcı dostu (genelde invisible)
ve GDPR uyumlu bir CAPTCHA hizmetidir.

Env vars:
- TURNSTILE_SITE_KEY: client-side widget key (HTML'e gömülür)
- TURNSTILE_SECRET_KEY: server-side verification key (gizli)
- TURNSTILE_ENABLED: "1"/"0" — global toggle (default: ikisi de set ise açık)
- TURNSTILE_ALLOWED_HOSTNAMES: virgülle alan adları (ops.; token başka sitede üretildiyse reddet)
- TURNSTILE_FAIL_CLOSED: "1" → Cloudflare'e ulaşılamazsa reddet (vars. geç)

Site key boşsa CAPTCHA atlanır (dev mode). Verification başarısızsa False döner.
"""
from __future__ import annotations

import logging
import os
import uuid
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


def _allowed_hostnames() -> set[str]:
    """TURNSTILE_ALLOWED_HOSTNAMES (virgülle). Boşsa hostname kontrolü yapılmaz.

    Cloudflare'in önerisi: token'ın gerçekten bizim alan adımızda üretildiğini
    doğrula — başka bir sitede çözülüp bize taşınan token reddedilir.
    """
    raw = os.getenv("TURNSTILE_ALLOWED_HOSTNAMES", "").strip()
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _siteverify(payload: dict) -> Optional[dict]:
    """siteverify çağrısı; geçici ağ hatasında bir kez yeniden dener."""
    try:
        import httpx
    except ImportError:  # pragma: no cover
        logger.warning("httpx kurulu değil; turnstile bypass")
        return None
    last_err: Exception | None = None
    for _ in range(2):
        try:
            with httpx.Client(timeout=TURNSTILE_TIMEOUT_SEC) as client:
                r = client.post(TURNSTILE_VERIFY_URL, data=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:  # ağ / 5xx
            last_err = e
    logger.warning("turnstile verify hatası: %s", last_err)
    return None


def verify_token(
    token: Optional[str],
    ip: Optional[str] = None,
    action: Optional[str] = None,
) -> bool:
    """Turnstile token'ını Cloudflare'de doğrula.

    Args:
        token: Form'dan gelen token
        ip: İsteğin geldiği gerçek istemci IP'si (Cloudflare arkasında
            CF-Connecting-IP; Caddy trusted_proxies ile X-Forwarded-For'a yazılır)
        action: Beklenen eylem (login/signup/forgot/contact). Widget aynı action
            ile çizilir; başka bir formun token'ı bu uçta kullanılamaz. Eski
            (action'sız) istemci için yanıtta action boşsa kabul edilir.

    Returns:
        True: doğrulandı veya CAPTCHA devre dışı
        False: token yok / yanlış / süresi geçmiş / başka eylem / başka alan adı
    """
    if not is_enabled():
        return True  # CAPTCHA kapalı — geç

    if not token:
        logger.info("turnstile: token boş")
        return False
    if len(token) > 2048:  # Cloudflare: token en çok 2048 karakter
        logger.info("turnstile: token çok uzun")
        return False

    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        logger.warning("turnstile: TURNSTILE_SECRET_KEY tanımsız")
        return False

    payload = {
        "secret": secret,
        "response": token,
        # Yeniden deneme aynı doğrulamayı iki kez saymasın (Cloudflare idempotency)
        "idempotency_key": str(uuid.uuid4()),
    }
    if ip:
        payload["remoteip"] = ip

    data = _siteverify(payload)
    if data is None:
        # Cloudflare'e ulaşılamadı → meşru kullanıcıyı kilitlememek için geç.
        # (IP blok + hesap kilidi + hız sınırı yine çalışır.) Kapalı-başarısız
        # istenirse TURNSTILE_FAIL_CLOSED=1.
        return os.getenv("TURNSTILE_FAIL_CLOSED", "0").strip() not in ("1", "true", "yes")

    if not data.get("success"):
        logger.info("turnstile reddetti: %s", data.get("error-codes"))
        return False

    got_action = (data.get("action") or "").strip()
    if action and got_action and got_action != action:
        logger.info("turnstile: eylem uyuşmuyor (beklenen=%s gelen=%s)", action, got_action)
        return False

    allowed = _allowed_hostnames()
    hostname = (data.get("hostname") or "").strip().lower()
    if allowed and hostname and hostname not in allowed:
        logger.info("turnstile: alan adı uyuşmuyor (%s)", hostname)
        return False

    return True
