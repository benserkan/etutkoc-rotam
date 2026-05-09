"""Stage 7 — Aktif duyuruları çekme + audience filtre.

Her template render'ında bir kez çağrılır (Jinja context processor
benzeri). Performans: 60 sn'lik in-process cache; admin yeni duyuru
yayınlayınca cache invalidate edilir.

Audience eşleme:
- ALL → herkese
- SUPER_ADMIN/INSTITUTION_ADMIN/TEACHER/STUDENT/PARENT → o role
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    AnnouncementAudience,
    SystemAnnouncement,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


CACHE_TTL_SECONDS = 60.0


@dataclass
class _Cache:
    items: list[SystemAnnouncement]
    ts: float


_cache_lock = threading.Lock()
_cache: _Cache | None = None


def _load(db: Session) -> _Cache:
    """Aktif olabilecek tüm duyuruları çek (ends_at NULL veya gelecekte)."""
    now = datetime.now(timezone.utc)
    items = (
        db.query(SystemAnnouncement)
        .filter(SystemAnnouncement.starts_at <= now)
        .filter(
            (SystemAnnouncement.ends_at.is_(None))
            | (SystemAnnouncement.ends_at > now)
        )
        .order_by(SystemAnnouncement.severity.desc(), SystemAnnouncement.starts_at.desc())
        .all()
    )
    # SQLAlchemy session'dan çekildi; expunge'ı çağıran tarafa bırak (Jinja
    # render'ı normalde aynı request session'ı kullanır, sorun olmaz).
    return _Cache(items=items, ts=time.monotonic())


def _get(db: Session) -> _Cache:
    global _cache
    with _cache_lock:
        if _cache is None or (time.monotonic() - _cache.ts) >= CACHE_TTL_SECONDS:
            _cache = _load(db)
        return _cache


def invalidate_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


# Role → AnnouncementAudience eşleme
_ROLE_TO_AUDIENCE = {
    UserRole.SUPER_ADMIN: AnnouncementAudience.SUPER_ADMIN,
    UserRole.INSTITUTION_ADMIN: AnnouncementAudience.INSTITUTION_ADMIN,
    UserRole.TEACHER: AnnouncementAudience.TEACHER,
    UserRole.STUDENT: AnnouncementAudience.STUDENT,
    UserRole.PARENT: AnnouncementAudience.PARENT,
}


def active_for_user(
    db: Session, user: User | None, *, now: datetime | None = None,
) -> list[SystemAnnouncement]:
    """Kullanıcının görmesi gereken aktif duyurular.

    User None ise (anonim sayfa) sadece ALL audience gösterilir.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cache = _get(db)
    items = []
    user_audience = (
        _ROLE_TO_AUDIENCE.get(user.role) if user is not None else None
    )
    for ann in cache.items:
        if not ann.is_active(now):
            continue
        if ann.audience == AnnouncementAudience.ALL:
            items.append(ann)
        elif user_audience is not None and ann.audience == user_audience:
            items.append(ann)
    return items
