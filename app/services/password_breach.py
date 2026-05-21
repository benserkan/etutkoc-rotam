"""HaveIBeenPwned k-anonymity şifre sızıntı kontrolü.

API: https://api.pwnedpasswords.com/range/{first5_of_sha1}
- SHA1(password) hash'i hesapla
- İlk 5 karakteri (prefix) HIBP API'sine gönder
- Yanıt: "SUFFIX:COUNT" satırları
- Bizim suffix'imiz listede varsa şifre sızdırılmış, COUNT kaç kez sızdığını söyler

Bu yöntem k-anonymity sağlar — HIBP tam şifreyi veya tam hash'i asla görmez.

Env var ile devre dışı bırakılabilir:
- PASSWORD_BREACH_CHECK=0 → kontrol atla (offline dev için)
- PASSWORD_BREACH_CHECK=1 → kontrol et (default production)

Network hatası veya timeout → False döner (kullanıcıyı blokeleme).
"""
from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


HIBP_API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
HIBP_TIMEOUT_SEC = 3.0


def is_breach_check_enabled() -> bool:
    """Env var ile aç/kapat. Default açık (production)."""
    val = os.getenv("PASSWORD_BREACH_CHECK", "1").strip().lower()
    return val not in ("0", "false", "no", "off", "")


@lru_cache(maxsize=512)
def _hibp_lookup_prefix(prefix: str) -> dict[str, int]:
    """HIBP'ye prefix sorgusu yap, suffix→count map'i döndür.

    Cache'li: aynı prefix tekrar sorulmaz (process ömrü).
    Hata durumunda boş dict döner (kullanıcı bloklanmaz).
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx kurulu değil; breach check atlanıyor")
        return {}

    try:
        with httpx.Client(timeout=HIBP_TIMEOUT_SEC) as client:
            r = client.get(
                HIBP_API_URL.format(prefix=prefix),
                headers={"Add-Padding": "true"},  # response padding privacy
            )
            r.raise_for_status()
            text = r.text
    except Exception as e:
        logger.info("HIBP lookup failed for prefix=%s: %s", prefix, e)
        return {}

    out: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        suffix, _, count_str = line.partition(":")
        try:
            cnt = int(count_str)
        except ValueError:
            continue
        if cnt > 0:
            out[suffix.upper()] = cnt
    return out


def check_password_breach(password: str) -> Optional[int]:
    """Şifre HIBP'de sızdırılmış mı? Sızdırıldıysa kaç kez döner, yoksa None.

    None: temiz, ya da kontrol devre dışı, ya da network hatası
    int: sızdırılma sayısı (≥1)
    """
    if not password or not is_breach_check_enabled():
        return None
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    lookup = _hibp_lookup_prefix(prefix)
    return lookup.get(suffix)


def breach_check_message(count: int) -> str:
    """Sızdırılma sayısına göre kullanıcı dostu mesaj."""
    if count >= 1_000_000:
        return (
            f"Bu şifre milyonlarca kez sızdırılmış (≈{count:,} kez). "
            "Saldırganlar denemekten ilk önce bunu dener — başka bir şifre seç."
        )
    if count >= 10_000:
        return (
            f"Bu şifre dünya çapında {count:,} kez sızdırılmış. "
            "Genel kelime/desen — daha özgün bir şifre seç."
        )
    if count >= 100:
        return (
            f"Bu şifre {count} kez veri sızıntılarında görüldü. "
            "Hâlâ tehlikeli — bilinmedik bir kombinasyon dene."
        )
    return (
        f"Bu şifre {count} kez sızdırılmış. "
        "Az olsa da risk taşıyor — daha güvenli bir tane seç."
    )
