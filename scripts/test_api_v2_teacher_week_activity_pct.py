"""Hafta görünümü — 'Diğer'/etkinlik görevleri tamamlama %'sine sayılır +
veliye-duyur önizleme ucu smoke.

Senaryolar:
   1. 3 kalemsiz OTHER görev (1 COMPLETED) → gün pct ≈ 0.33 (eskiden 0 idi),
      tasks_count=3, planned=0 (soru hacmi değişmez)
   2. GET /program/parent-preview → daily_breakdown 'Diğer' görevleri is_activity=True
      ile içerir + total_tasks=3 (yayınlanmış) + alıcı veli görünür
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.models.parent import ParentRelation, ParentStudentLink
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2wkpct_{_secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
PASSWORD = "TestWkPct!2345"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    today = date.today()
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd, full_name=f"{PFX} Student",
            role=UserRole.STUDENT, teacher_id=teacher.id, grade_level=8,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd, full_name=f"{PFX} Parent",
            role=UserRole.PARENT, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([student, parent])
        db.flush()
        db.add(ParentStudentLink(
            parent_id=parent.id, student_id=student.id,
            relation=next(iter(ParentRelation)), is_primary=True,
        ))
        # 3 kalemsiz OTHER görev (bugün): 1 COMPLETED + 2 PENDING — hepsi yayınlanmış
        tasks = [
            Task(
                student_id=student.id, date=today, type=TaskType.OTHER,
                title=f"{PFX} Etkinlik {i+1}", status=st, is_draft=False, order=i,
            )
            for i, st in enumerate([TaskStatus.COMPLETED, TaskStatus.PENDING, TaskStatus.PENDING])
        ]
        db.add_all(tasks)
        db.flush()
        # id-reuse kirliliği: yeni task id'lerine yapışmış orphan TaskBookItem'ları
        # temizle (önceki testlerin deneme kalemleri). Bu görevler kalemsiz olmalı.
        db.execute(sa_delete(TaskBookItem).where(
            TaskBookItem.task_id.in_([t.id for t in tasks])
        ))
        db.commit()
        return {"teacher_id": teacher.id, "student_id": student.id, "parent_id": parent.id}


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        task_ids = [t.id for t in db.query(Task.id).filter(Task.student_id == seed["student_id"]).all()]
        if task_ids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
        db.execute(sa_delete(Task).where(Task.student_id == seed["student_id"]))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.student_id == seed["student_id"]
        ))
        ids = [seed["teacher_id"], seed["student_id"], seed["parent_id"]]
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== hafta görev-pct + veli önizleme smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    today_iso = date.today().isoformat()
    sid = seed["student_id"]
    try:
        c = _login(TEACHER_EMAIL)

        # 1. Hafta — bugünün günü: 'Diğer' tamamlama %'ye sayılır
        r = c.get(f"/api/v2/teacher/students/{sid}/week", params={"start": today_iso})
        j = r.json() if r.status_code == 200 else {}
        days = j.get("days", [])
        today_day = next((d for d in days if d.get("date") == today_iso), None)
        pct = today_day.get("pct") if today_day else None
        check(
            "1. gün pct = görev-tamamlama (3 görevden 1 tamam ≈ 0.33, soru=0)",
            r.status_code == 200 and today_day is not None
            and today_day.get("tasks_count") == 3
            and today_day.get("planned") == 0
            and pct is not None and 0.30 <= float(pct) <= 0.37,
            f"status={r.status_code} day={today_day}",
        )

        # 2. Veliye-duyur önizleme — Diğer görevler + alıcı veli
        r2 = c.get(
            f"/api/v2/teacher/students/{sid}/program/parent-preview",
            params={"week_start": today_iso},
        )
        p = r2.json() if r2.status_code == 200 else {}
        bd = p.get("daily_breakdown", [])
        pday = next((d for d in bd if d.get("day_iso") == today_iso), None)
        activities = pday.get("activities", []) if pday else []
        groups = pday.get("subject_groups", []) if pday else []
        recip_names = [rr.get("name") for rr in p.get("recipients", [])]
        check(
            "2. önizleme: 3 Diğer görev activities'te (ders grubu yok) + total_tasks=3 + veli alıcı",
            r2.status_code == 200
            and len(activities) == 3 and len(groups) == 0
            and p.get("total_tasks") == 3
            and p.get("has_recipients") is True
            and f"{PFX} Parent" in recip_names,
            f"status={r2.status_code} activities={len(activities)} groups={len(groups)} "
            f"total={p.get('total_tasks')} recipients={recip_names}",
        )

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
