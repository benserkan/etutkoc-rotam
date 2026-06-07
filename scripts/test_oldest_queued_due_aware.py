"""oldest_queued_minutes — vadesi-gelmiş (due-aware) testi.

Sessiz saat ertelemesi (scheduled_at ileri) + retry-backoff (next_attempt_at
ileri) bildirimleri 'takılı' SAYILMAMALI; yalnız gerçekten gönderilebilir ama
gönderilmemiş satırlar oldest_queued_minutes'e girmeli. Aksi halde her gece
yanlış 'Kuyrukta uzun süre bekleyen bildirim' (oldest_queued_long) alarmı çıkar.

  python -m scripts.test_oldest_queued_due_aware
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    NotificationChannel, NotificationKind, NotificationLog, NotificationStatus,
    User, UserRole,
)
from app.services.notification_health import oldest_queued_minutes
from app.services.security import hash_password

PFX = f"oqm_{secrets.token_hex(3)}"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
ids: list[int] = []
parent_id = None


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def _mk(db, *, queued_min_ago, scheduled_at, next_attempt_at):
    log = NotificationLog(
        parent_id=parent_id, student_id=None,
        kind=NotificationKind.WEEKLY_REPORT, channel=NotificationChannel.EMAIL,
        status=NotificationStatus.QUEUED,
        scheduled_at=scheduled_at, next_attempt_at=next_attempt_at,
    )
    db.add(log); db.flush()
    log.queued_at = now - timedelta(minutes=queued_min_ago)
    db.flush()
    ids.append(log.id)
    return log.id


def main():
    global parent_id
    print(f"\n=== oldest_queued_minutes due-aware testi — {PFX} ===\n")
    with SessionLocal() as db:
        p = User(email=f"{PFX}@test.invalid", password_hash=hash_password("x12345678"),
                 full_name=f"{PFX}-parent", role=UserRole.PARENT, is_active=True)
        db.add(p); db.flush(); parent_id = p.id
        db.commit()

    try:
        # Senaryo 1: SADECE ertelenmiş (sessiz saat) — scheduled_at 1 saat İLERİDE,
        # queued_at 400 dk önce. ESKİ kod 400 derdi; YENİ kod None demeli.
        with SessionLocal() as db:
            _mk(db, queued_min_ago=400, scheduled_at=now + timedelta(hours=1), next_attempt_at=None)
            db.commit()
            val = oldest_queued_minutes(db)
            check("1. Ertelenmiş (scheduled ileri) → takılı SAYILMAZ (None)",
                  val is None, f"val={val}")

        # Senaryo 2: + retry-backoff (next_attempt ileri), queued 300 dk önce.
        with SessionLocal() as db:
            _mk(db, queued_min_ago=300, scheduled_at=now - timedelta(hours=5),
                next_attempt_at=now + timedelta(minutes=20))
            db.commit()
            val = oldest_queued_minutes(db)
            check("2. + retry-backoff (next_attempt ileri) → hâlâ None",
                  val is None, f"val={val}")

        # Senaryo 3: + gerçekten vadesi gelmiş (scheduled geçmiş, next null),
        # queued 90 dk önce → bu sayılmalı, ~90 dk dönmeli.
        with SessionLocal() as db:
            _mk(db, queued_min_ago=90, scheduled_at=now - timedelta(minutes=95), next_attempt_at=None)
            db.commit()
            val = oldest_queued_minutes(db)
            check("3. Vadesi gelmiş (due) satır → ~90 dk sayılır",
                  val is not None and 88 <= val <= 92, f"val={val}")

        # Senaryo 4: daha eski ama vadesi gelmiş bir satır daha → en eskisi (130) dönmeli
        with SessionLocal() as db:
            _mk(db, queued_min_ago=130, scheduled_at=None, next_attempt_at=None)
            db.commit()
            val = oldest_queued_minutes(db)
            check("4. scheduled_at NULL + eski (130dk) due → en eski=~130 dönmeli",
                  val is not None and 128 <= val <= 132, f"val={val}")

    finally:
        with SessionLocal() as db:
            if ids:
                db.execute(sa_delete(NotificationLog).where(NotificationLog.id.in_(ids)))
            if parent_id:
                db.execute(sa_delete(User).where(User.id == parent_id))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
