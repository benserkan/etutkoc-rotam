"""Katman 11.B — Süper admin kimliğe-bürünme servisi.

Mevcut akışı sarmalar: gerekçe doğrulama, ImpersonationSession satırı,
30 dk auto-expire kontrol, panoda görünür aktif liste.

Politika:
  - reason zorunlu, 10-200 karakter (kısa, anlaşılır)
  - 30 dk sonra otomatik kapanır (uzatmak için yeni başlatmak gerek)
  - Aynı admin'in aynı target için aktif tek oturumu olur (idempotent)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import (
    AuditAction,
    AuditLog,
    IMPERSONATION_MAX_DURATION_MINUTES,
    IMPERSONATION_REASON_MAX_LENGTH,
    IMPERSONATION_REASON_MIN_LENGTH,
    ImpersonationSession,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class ReasonValidation:
    ok: bool
    error: str | None
    cleaned: str


def validate_reason(reason: str | None) -> ReasonValidation:
    cleaned = (reason or "").strip()
    if len(cleaned) < IMPERSONATION_REASON_MIN_LENGTH:
        return ReasonValidation(
            ok=False,
            error=(
                f"Gerekçe en az {IMPERSONATION_REASON_MIN_LENGTH} karakter olmalı. "
                "Sebebi açıkça yazın (örn. 'kullanıcı ödev görünmüyor şikayetini "
                "yerinde inceleme')."
            ),
            cleaned="",
        )
    if len(cleaned) > IMPERSONATION_REASON_MAX_LENGTH:
        cleaned = cleaned[:IMPERSONATION_REASON_MAX_LENGTH]
    return ReasonValidation(ok=True, error=None, cleaned=cleaned)


def start_session(
    db: Session,
    *,
    actor: User,
    target: User,
    reason: str,
    ip: str | None,
    autocommit: bool = True,
) -> ImpersonationSession:
    """Yeni impersonation oturumu açar. reason valide edilmiş varsayılır."""
    now = _now()
    expires = now + timedelta(minutes=IMPERSONATION_MAX_DURATION_MINUTES)
    row = ImpersonationSession(
        actor_user_id=actor.id,
        target_user_id=target.id,
        reason=reason,
        started_at=now,
        expires_at=expires,
        ip=(ip or "")[:64] or None,
    )
    db.add(row)
    if autocommit:
        db.commit()
        db.refresh(row)
    return row


def end_session(
    db: Session,
    *,
    session_id: int,
    end_reason: str,
    ended_by_user_id: int | None = None,
    autocommit: bool = True,
) -> ImpersonationSession | None:
    row = db.get(ImpersonationSession, session_id)
    if row is None or row.ended_at is not None:
        return row
    row.ended_at = _now()
    row.end_reason = end_reason[:40]
    row.ended_by_user_id = ended_by_user_id
    if autocommit:
        db.commit()
    return row


def get_session(db: Session, session_id: int) -> ImpersonationSession | None:
    return db.get(ImpersonationSession, session_id)


def is_expired(row: ImpersonationSession, *, now: datetime | None = None) -> bool:
    if row.ended_at is not None:
        return False  # zaten kapanmış
    now = now or _now()
    expires = _aware(row.expires_at)
    return expires is not None and expires <= now


def list_active(db: Session) -> list[dict]:
    """Şu an aktif (ended_at NULL ve süresi dolmamış) oturumlar."""
    now = _now()
    rows = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.ended_at.is_(None))
        .order_by(desc(ImpersonationSession.started_at))
        .limit(50)
        .all()
    )
    out: list[dict] = []
    # Tek toplu user lookup
    ids: set[int] = set()
    for r in rows:
        ids.add(r.actor_user_id)
        ids.add(r.target_user_id)
    users_map: dict[int, User] = {}
    if ids:
        for u in db.query(User).filter(User.id.in_(ids)).all():
            users_map[u.id] = u
    for r in rows:
        started = _aware(r.started_at) or now
        expires = _aware(r.expires_at) or now
        is_exp = expires <= now
        seconds_left = max(0, int((expires - now).total_seconds()))
        age_seconds = int((now - started).total_seconds())
        actor = users_map.get(r.actor_user_id)
        target = users_map.get(r.target_user_id)
        out.append({
            "id": r.id,
            "actor_user_id": r.actor_user_id,
            "actor_email": actor.email if actor else None,
            "actor_full_name": actor.full_name if actor else f"#{r.actor_user_id}",
            "target_user_id": r.target_user_id,
            "target_email": target.email if target else None,
            "target_full_name": target.full_name if target else f"#{r.target_user_id}",
            "reason": r.reason,
            "started_at": started,
            "expires_at": expires,
            "ip": r.ip,
            "is_expired_now": is_exp,
            "seconds_left": seconds_left,
            "age_seconds": age_seconds,
        })
    return out


def expire_if_needed(
    db: Session, *, session_id: int, autocommit: bool = True
) -> bool:
    """deps.py her request'te çağırır. Süresi dolmuşsa otomatik end yapar.
    Returns True = expire edildi (caller session.clear() yapmalı)."""
    row = db.get(ImpersonationSession, session_id)
    if row is None:
        return False
    if row.ended_at is not None:
        return False
    if not is_expired(row):
        return False
    row.ended_at = _now()
    row.end_reason = "expired"
    if autocommit:
        db.commit()
    return True


def find_active_for_actor_target(
    db: Session, *, actor_id: int, target_id: int
) -> ImpersonationSession | None:
    """Aynı (actor, target) çifti için aktif kayıt var mı?"""
    return (
        db.query(ImpersonationSession)
        .filter(
            ImpersonationSession.actor_user_id == actor_id,
            ImpersonationSession.target_user_id == target_id,
            ImpersonationSession.ended_at.is_(None),
        )
        .order_by(desc(ImpersonationSession.started_at))
        .first()
    )


__all__ = [
    "ReasonValidation",
    "end_session",
    "expire_if_needed",
    "find_active_for_actor_target",
    "get_session",
    "is_expired",
    "list_active",
    "start_session",
    "validate_reason",
]
