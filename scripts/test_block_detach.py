"""Blok silme → görev 'Diğer' (DENEME değil) smoke.

Serbest Blok görevleri kitapsız kalem olarak saklanır. Blok silinince work_block_id
NULL'a düşüp kitapsız kalem yanlışlıkla tam_deneme (DENEME) sınıflanıyordu. Düzeltme:
block_detached işareti → görev 'etkinlik/Diğer', DENEME değil. Program değişmez.
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
from app.services import gorev_stats
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"bd{secrets.token_hex(3)}"
PASSWORD = "Detach!2026X"
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


def main() -> int:
    print(f"\n=== block detach smoke — {PFX} ===\n")
    today = date.today()
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True, plan="solo_free",
                       must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True, grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        blk = CoachWorkBlock(coach_id=teacher.id, student_id=student.id,
                             title="Mat Blok", total_count=10, unit="test", status="active")
        db.add(blk); db.flush()
        # Blok görevi: kitapsız kalem (book_id=None + label) — gerçek blok deseni
        t_blk = Task(student_id=student.id, date=today, type=TaskType.OTHER,
                     title="Matematik · Orjinal Doğrunun Analitiği", status=TaskStatus.PENDING,
                     order=0, is_draft=False, work_block_id=blk.id)
        db.add(t_blk); db.flush()
        db.add(TaskBookItem(task_id=t_blk.id, book_id=None, book_section_id=None,
                            label="Orjinal Doğrunun Analitiği", planned_count=3, completed_count=0))
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "blk": blk.id, "t_blk": t_blk.id}

        # blok bağlıyken → etkinlik (BLOK)
        tb = db.get(Task, ids["t_blk"])
        check("1. blok görevi (work_block_id set) → classify=etkinlik (BLOK)",
              gorev_stats.classify_gorev(tb) == "etkinlik", gorev_stats.classify_gorev(tb))

    # HTTP: bloğu sil → görev kalır + block_detached + Diğer (DENEME değil)
    get_login_limiter().reset()
    client = TestClient(app)
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
        r = client.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("2. koç login 200", r.status_code == 200, r.text[:100])

        r = client.delete(f"/api/v2/teacher/work-blocks/{ids['blk']}")
        check("3. blok sil 200", r.status_code == 200, r.text[:120])

        with SessionLocal() as db:
            tb = db.get(Task, ids["t_blk"])
            check("4. görev programda KALDI (silinmedi)", tb is not None)
            check("5. work_block_id NULL'a düştü (blok bağı gitti)", tb.work_block_id is None)
            check("6. block_detached=True işaretlendi", tb.block_detached is True)
            check("7. classify=etkinlik (Diğer) — DENEME DEĞİL",
                  gorev_stats.classify_gorev(tb) == "etkinlik", gorev_stats.classify_gorev(tb))
            # block_detached olmasaydı tam_deneme olurdu — flag'in etkisini kanıtla
            tb.block_detached = False
            check("8. (kontrol) block_detached=False olsa → tam_deneme (DENEME) olurdu",
                  gorev_stats.classify_gorev(tb) == "tam_deneme", gorev_stats.classify_gorev(tb))
            db.rollback()

        # Serializer block_detached'i taşıyor mu (week yanıtı)
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/day?date={today.isoformat()}")
        if r.status_code == 200:
            tasks = r.json().get("tasks", [])
            mine = [t for t in tasks if t["id"] == ids["t_blk"]]
            check("9. serializer block_detached=True döndürür",
                  len(mine) == 1 and mine[0].get("block_detached") is True, f"got {mine[:1]}")
        else:
            check("9. day endpoint 200", False, f"{r.status_code}")
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
