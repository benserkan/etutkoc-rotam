"""Smoke — kaynaksız KONULU kalemde D/Y/B girişi (2026-10-14 düzeltmesi).

Havuzdan kaba alınan kaynaksız konulu kalem (kitapsız ama topic_id dolu) TEST birimidir:
completed = test, D/Y/B = soru (toplam tavanı yok). Önceden kitapsız deneme sanılıp
"D+Y+B ≤ çözülen test" kuralına takılıyordu → öğrenci gerçek sayıları giremiyordu.
Kitapsız + konusuz deneme kalemi (soru birimi) eski kuralı korur.

  python scripts/test_sourceless_topic_dyb.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    PoolItem, StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, TaskType, Track, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import curriculum_progress as cp, pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.topic_performance import compute_topic_performance  # noqa: E402

PFX = f"stdyb_{secrets.token_hex(3)}"
PWD = "Ogrenci!234567xy"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="DYB Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="DYB Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, entry_year_grade9=2023, program_mode="havuz")
        db.add(st)
        db.flush()
        kim = db.query(Subject).filter(Subject.name == "TYT Kimya", Subject.is_builtin.is_(True)).first()
        topic = cp.leaf_topics_for_student(db, st, coach.id, [kim.id]).by_subject[kim.id][0]
        p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=1),
                           expected_next_on=today + timedelta(days=5))
        it = pm.add_item(db, period=p, student=st, subject=kim, quantity=6, unit="test", topic=topic)
        task = pm.put_in_cup(db, item=it, day=today, count=3)
        # kitapsız + konusuz deneme görevi (soru birimi) — eski kural korunmalı
        dt = Task(student_id=st.id, date=today, type=TaskType.OTHER, title="Genel Deneme", is_draft=False,
                  status=TaskStatus.PENDING,
                  book_items=[TaskBookItem(book_id=None, book_section_id=None, label="Genel Deneme",
                                           planned_count=40, completed_count=0)])
        db.add(dt)
        db.commit()
        return {"coach": coach.id, "st": st.id, "task": task.id, "item": task.book_items[0].id,
                "topic": topic.id, "subject": kim.id, "dtask": dt.id, "ditem": dt.book_items[0].id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== kaynaksız konulu kalem D/Y/B — {PFX} ===\n")
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        day = c.get("/api/v2/student/day").json()
        it = next(i for t in day["tasks"] if t["id"] == d["task"] for i in t["items"])
        check("1 öğrenci yanıtı: kaynaksız konulu kalem is_test_unit=True + konu adı + ders",
              it.get("is_test_unit") is True and it.get("topic_id") == d["topic"]
              and it.get("topic_name") and it.get("subject_id") == d["subject"], str(it))
        dit = next(i for t in day["tasks"] if t["id"] == d["dtask"] for i in t["items"])
        check("2 kitapsız deneme kalemi is_test_unit=False", dit.get("is_test_unit") is False, str(dit))

        r = c.post(f"/api/v2/student/tasks/{d['task']}/items/{d['item']}/set-completed",
                   json={"completed": 3, "correct": 30, "wrong": 5, "blank": 1})
        check("3 3 test · 30D 5Y 1B kabul (soru sayısı, test tavanı yok)", r.status_code == 200, r.text[:200])

        r = c.post(f"/api/v2/student/tasks/{d['dtask']}/items/{d['ditem']}/set-completed",
                   json={"completed": 40, "correct": 35, "wrong": 6, "blank": 0})
        check("4 kitapsız deneme: D+Y > çözülen soru → 422 (eski kural korunur)", r.status_code == 422, r.text[:200])

        with SessionLocal() as db:
            perf = compute_topic_performance(db, d["st"])
            sp = next((s for s in perf if s.subject_id == d["subject"]), None)
            tp = next((t for t in sp.topics if t.topic_id == d["topic"]), None) if sp else None
            check("5 konu performansı: 3 test · 30D 5Y · %86",
                  tp is not None and tp.tests_solved == 3 and tp.correct == 30 and tp.wrong == 5
                  and tp.accuracy_pct == 86, str(tp))
            pi = db.get(PoolItem, db.get(Task, d["task"]).pool_item_id)
            pm.sync_item_progress(db, pi)
            check("6 havuz kalemi ilerlemesi 3/6", int(pi.completed or 0) == 3, str(pi.completed))
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
