"""Blok tamamen tamamlanınca (completed==total) listeden otomatik kalkar.

Kullanıcı kararı 2026-06-18: tamamen tamamlanmış blok 'işe yaramaz' → Serbest
Bloklar listesinden otomatik düşer (status=archived). Kısmi tamamlanan kalır.
Görevler programda BLOK olarak kalır (dokunulmaz).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CoachWorkBlock, SuspiciousIp, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"baa{secrets.token_hex(3)}"
PASSWORD = "AutoArc!2026X"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def _block_task(db, student_id, blk_id, planned, completed, order):
    t = Task(student_id=student_id, date=date.today(), type=TaskType.OTHER,
             title="Matematik · Blok işi", status=TaskStatus.PENDING, order=order,
             is_draft=False, work_block_id=blk_id)
    db.add(t); db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=None, book_section_id=None,
                        label="Blok işi", planned_count=planned, completed_count=completed))
    return t


def main() -> int:
    print(f"\n=== block auto-archive smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True, plan="solo_free",
                       must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True, grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        # Blok A: total=5, dağıtılan 5, çözülen 5 → TAM TAMAMLANDI → otomatik arşiv
        blk_full = CoachWorkBlock(coach_id=teacher.id, student_id=student.id,
                                  title="Tam Blok", total_count=5, unit="test", status="active")
        # Blok B: total=5, dağıtılan 5, çözülen 3 → kısmi → KALIR
        blk_part = CoachWorkBlock(coach_id=teacher.id, student_id=student.id,
                                  title="Kısmi Blok", total_count=5, unit="test", status="active")
        db.add_all([blk_full, blk_part]); db.flush()
        _block_task(db, student.id, blk_full.id, 5, 5, 0)
        _block_task(db, student.id, blk_part.id, 5, 3, 1)
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id,
               "blk_full": blk_full.id, "blk_part": blk_part.id}

    get_login_limiter().reset()
    client = TestClient(app)
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
        r = client.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("1. koç login 200", r.status_code == 200, r.text[:100])

        r = client.get(f"/api/v2/teacher/students/{ids['student']}/work-blocks")
        check("2. work-blocks 200", r.status_code == 200, r.text[:100])
        listed = {b["id"] for b in r.json().get("items", [])}
        check("3. TAM tamamlanan blok listede YOK (otomatik arşiv)",
              ids["blk_full"] not in listed, f"got {listed}")
        check("4. KISMİ blok listede VAR (çözülen<toplam)",
              ids["blk_part"] in listed, f"got {listed}")

        with SessionLocal() as db:
            bf = db.get(CoachWorkBlock, ids["blk_full"])
            bp = db.get(CoachWorkBlock, ids["blk_part"])
            check("5. tam blok status=archived", bf.status == "archived", bf.status)
            check("6. kısmi blok status=active (dokunulmadı)", bp.status == "active", bp.status)
            # blok görevleri programda KALDI (dokunulmaz)
            ftasks = db.query(Task).filter(Task.work_block_id == ids["blk_full"]).all()
            check("7. tam bloğun görevi programda KALDI (BLOK bağı korundu)",
                  len(ftasks) == 1 and ftasks[0].work_block_id == ids["blk_full"], f"got {len(ftasks)}")

        # include_archived=True → tam blok görünür
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/work-blocks?include_archived=true")
        all_ids = {b["id"] for b in r.json().get("items", [])}
        check("8. include_archived=true → tam blok yine görünür", ids["blk_full"] in all_ids, f"got {all_ids}")
    finally:
        with SessionLocal() as db:
            tids = [t.id for t in db.query(Task).filter(Task.student_id == ids["student"]).all()]
            if tids:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            db.execute(sa_delete(CoachWorkBlock).where(CoachWorkBlock.student_id == ids["student"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
