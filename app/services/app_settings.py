"""Genel JSON ayar servisi — kod default + DB override (süper admin düzenler).

Sır değil (şifreleme yok; sırlar için `system_secrets`). Fiyat/üyelik gibi config
JSON'u burada. 60 sn process cache; set/delete invalidate eder.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting

logger = logging.getLogger(__name__)

_CACHE_TTL = 60.0
_cache_lock = threading.Lock()
_cache: dict[str, tuple[Any, float]] = {}


def _invalidate(key: str) -> None:
    with _cache_lock:
        _cache.pop(key, None)


def get_json(key: str, default: Any = None) -> Any:
    """Ayar değeri (JSON parse). Yoksa default. 60 sn cache. Kendi oturumunu açar."""
    now = time.monotonic()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and (now - hit[1]) < _CACHE_TTL:
            return hit[0]
    value: Any = default
    try:
        from app.database import SessionLocal
        with SessionLocal() as db:
            row = db.query(AppSetting).filter(AppSetting.key == key).first()
            if row is not None:
                try:
                    value = json.loads(row.value_json)
                except (ValueError, TypeError):
                    value = default
    except Exception as e:
        logger.warning("app_settings get_json hatası (%s): %s", key, e)
    with _cache_lock:
        _cache[key] = (value, now)
    return value


def set_json(db: Session, key: str, value: Any, *, actor_user_id: int | None = None) -> None:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        row = AppSetting(key=key)
        db.add(row)
    row.value_json = json.dumps(value, ensure_ascii=False)
    row.updated_by_id = actor_user_id
    db.commit()
    _invalidate(key)


def delete(db: Session, key: str) -> bool:
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    _invalidate(key)
    return True
