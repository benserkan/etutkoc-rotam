"""Uyarı akışı tazelik + gördüm/ertele durum yönetimi (WarningState).

Uyarılar canlı hesaplanır; bu servis (actor görünümünde) her uyarının first_seen
(yaş) + snooze_until (ertele) durumunu yönetir ve canlı uyarılarla uzlaştırır.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import WarningState

DEFAULT_SNOOZE_DAYS = 3
MAX_SNOOZE_DAYS = 30


def reconcile_states(
    db: Session, *, actor_id: int, present_keys: set[tuple[int, str]],
    now: datetime | None = None,
) -> dict[tuple[int, str], WarningState]:
    """Canlı uyarı anahtarlarıyla durumları uzlaştır.

    - Yeni anahtar → first_seen=now ekle.
    - Canlıda artık olmayan anahtar (koşul düzeldi) → SİL (tekrar ederse taze sayılır).
    Dönen: present_keys için {(student_id, code): WarningState}.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    existing = db.query(WarningState).filter(WarningState.actor_id == actor_id).all()
    by_key = {(w.student_id, w.code): w for w in existing}

    for key, w in by_key.items():
        if key not in present_keys:
            db.delete(w)  # koşul düzeldi → durum sıfırlanır

    result: dict[tuple[int, str], WarningState] = {}
    for key in present_keys:
        st = by_key.get(key)
        if st is None:
            st = WarningState(
                actor_id=actor_id, student_id=key[0], code=key[1], first_seen_at=now,
            )
            db.add(st)
        result[key] = st
    db.flush()
    return result


def set_snooze(
    db: Session, *, actor_id: int, student_id: int, code: str, days: int,
    now: datetime | None = None,
) -> WarningState:
    """Uyarıyı 'gördüm/ertele' — days gün süreyle aktif akıştan gizler."""
    if now is None:
        now = datetime.now(timezone.utc)
    days = max(1, min(int(days), MAX_SNOOZE_DAYS))
    st = (
        db.query(WarningState)
        .filter_by(actor_id=actor_id, student_id=student_id, code=code)
        .first()
    )
    if st is None:
        st = WarningState(actor_id=actor_id, student_id=student_id, code=code, first_seen_at=now)
        db.add(st)
    st.snooze_until = now + timedelta(days=days)
    st.acknowledged_at = now
    db.flush()
    return st


def clear_snooze(
    db: Session, *, actor_id: int, student_id: int, code: str,
) -> WarningState | None:
    """Erteleme/gördüm geri al → uyarı aktif akışa geri döner."""
    st = (
        db.query(WarningState)
        .filter_by(actor_id=actor_id, student_id=student_id, code=code)
        .first()
    )
    if st is not None:
        st.snooze_until = None
        st.acknowledged_at = None
        db.flush()
    return st
