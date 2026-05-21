"""Süper admin merkezi sır/ayar servisi — Gemini AI sağlayıcı yapılandırması.

Tek AI sağlayıcı: **Gemini**.
- ÜCRETLİ key (`gemini_paid_api_key`) → öğrenci verili işler (foto/ses/içgörü).
  No-training (faturalı katman) — KVKK. Model: `gemini_paid_model`.
- FREE key(ler) (`gemini_free_api_key` DB tek + env `GEMINI_FREE_API_KEYS` çoklu)
  → yalnız kişisel-veri-içermeyen iş (kitap şablonu). Kota dolunca sıradakine,
  en son ücretliye düşülür. Model: `gemini_free_model`.

Sırlar `system_secrets` tablosunda **Fernet** ile şifreli (anahtar
`settings.session_secret`'tan türetilir). Düz değer ASLA dönmez (maskeli). Model
adları sır değildir — panelde düz gösterilir. resolve* fonksiyonları 60 sn cache.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import threading
import time

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SystemSecret

logger = logging.getLogger(__name__)


# Şifreli (maskeli gösterilen) anahtar adları
SECRET_NAMES = ("gemini_paid_api_key", "gemini_free_api_key")
# Düz (panelde açık gösterilen) ayar adları
CONFIG_NAMES = ("gemini_paid_model", "gemini_free_model")

MODEL_DEFAULTS = {
    "gemini_paid_model": "gemini-2.5-pro",
    "gemini_free_model": "gemini-2.5-flash",
}

_CACHE_TTL = 60.0
_cache_lock = threading.Lock()
_cache: dict[str, tuple[str | None, float]] = {}


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.session_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as e:
        logger.warning("system_secret decrypt başarısız (session_secret değişmiş olabilir): %s", e)
        return None


def mask(value: str | None) -> str:
    """Anahtarı maskele: 'AIzaSy…4f9c'. Boş → ''."""
    if not value:
        return ""
    v = value.strip()
    if len(v) <= 10:
        return "•" * len(v)
    return f"{v[:6]}…{v[-4:]}"


# ---------------------------- DB CRUD ----------------------------


def set_secret(db: Session, name: str, value: str, *, actor_user_id: int | None = None) -> None:
    row = db.query(SystemSecret).filter(SystemSecret.name == name).first()
    if row is None:
        row = SystemSecret(name=name)
        db.add(row)
    row.value_encrypted = _encrypt(value.strip())
    row.updated_by_id = actor_user_id
    db.commit()
    _invalidate(name)


def delete_secret(db: Session, name: str) -> bool:
    row = db.query(SystemSecret).filter(SystemSecret.name == name).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    _invalidate(name)
    return True


def get_db_value(db: Session, name: str) -> str | None:
    row = db.query(SystemSecret).filter(SystemSecret.name == name).first()
    if row is None:
        return None
    return _decrypt(row.value_encrypted)


# ---------------------------- Resolver ----------------------------


def _invalidate(name: str) -> None:
    with _cache_lock:
        _cache.pop(name, None)


def _settings_attr(name: str) -> str | None:
    val = getattr(settings, name, "") or ""
    return val.strip() or None


def _resolve_raw(name: str) -> str | None:
    """DB (süper admin) → settings/.env. 60 sn cache."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(name)
        if hit is not None and (now - hit[1]) < _CACHE_TTL:
            return hit[0]
    value: str | None = None
    try:
        from app.database import SessionLocal
        with SessionLocal() as db:
            value = get_db_value(db, name)
    except Exception as e:
        logger.warning("_resolve_raw DB okuma hatası (%s): %s", name, e)
    if not value:
        value = _settings_attr(name)
    with _cache_lock:
        _cache[name] = (value, now)
    return value


# ---------------------------- Gemini erişimcileri ----------------------------


def _gemini_api_key_list() -> list[str]:
    """Genel GEMINI_API_KEY — virgülle çoklu olabilir (ilk=ücretli, kalan=ücretsiz)."""
    raw = (getattr(settings, "gemini_api_key", "") or "").strip()
    return [k.strip() for k in raw.split(",") if k.strip()]


def get_gemini_paid_key() -> str | None:
    # Açık gemini_paid_api_key (DB/env) → GEMINI_API_KEY listesinin İLK elemanı.
    explicit = _resolve_raw("gemini_paid_api_key")
    if explicit:
        return explicit
    lst = _gemini_api_key_list()
    return lst[0] if lst else None


def get_gemini_free_keys() -> list[str]:
    """Ücretsiz key listesi. Öncelik: DB tek → env GEMINI_FREE_API_KEYS →
    GEMINI_API_KEY listesinin İLK eleman dışındaki kalanı (ilk ücretli sayılır)."""
    db_single = _resolve_raw("gemini_free_api_key")
    if db_single:
        return [db_single]
    raw = (getattr(settings, "gemini_free_api_keys", "") or "").strip()
    explicit = [k.strip() for k in raw.split(",") if k.strip()]
    if explicit:
        return explicit
    lst = _gemini_api_key_list()
    return lst[1:] if len(lst) > 1 else []


def get_gemini_model(*, paid: bool) -> str:
    name = "gemini_paid_model" if paid else "gemini_free_model"
    return _resolve_raw(name) or MODEL_DEFAULTS[name]


# ---------------------------- Süper admin durum ----------------------------


def ai_settings_status(db: Session) -> list[dict]:
    """Süper admin AI Ayarları paneli için durum (anahtarlar maskeli, modeller açık)."""
    out: list[dict] = []

    # Ücretli key (gemini_paid_api_key → GEMINI_API_KEY listesinin ilki)
    paid_db = get_db_value(db, "gemini_paid_api_key")
    paid = get_gemini_paid_key()
    paid_src = "db" if paid_db else ("env" if paid else "none")
    out.append({"name": "gemini_paid_api_key", "kind": "secret", "label": "Gemini ÜCRETLİ anahtar (öğrenci verisi)",
                "is_set": bool(paid), "source": paid_src, "value": mask(paid)})

    # Ücretsiz key(ler)
    free_db = get_db_value(db, "gemini_free_api_key")
    free_keys = get_gemini_free_keys()
    free_src = "db" if free_db else ("env" if free_keys else "none")
    free_val = ""
    if free_keys:
        free_val = mask(free_keys[0]) + (f"  (+{len(free_keys) - 1} env)" if len(free_keys) > 1 else "")
    out.append({"name": "gemini_free_api_key", "kind": "secret", "label": "Gemini ÜCRETSİZ anahtar (kitap şablonu)",
                "is_set": bool(free_keys), "source": free_src, "value": free_val})

    # Modeller (düz)
    for name, lbl in (("gemini_paid_model", "Ücretli model"), ("gemini_free_model", "Ücretsiz model")):
        val = _resolve_raw(name) or MODEL_DEFAULTS[name]
        src = "db" if get_db_value(db, name) else ("env" if _settings_attr(name) else "default")
        out.append({"name": name, "kind": "config", "label": lbl, "is_set": True, "source": src, "value": val})

    return out
