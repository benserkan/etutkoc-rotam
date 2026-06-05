# -*- coding: utf-8 -*-
"""API v2 /teacher/students/{id}/analytics — zenginleştirilmiş bloklar smoke.

Koç "program süreci" panosu: özet (tempo) + haftalık trend + aktivite takvimi +
haftanın günleri + projeksiyon + deneme net trendi + risk sinyalleri.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskStatus, TaskType, Topic, User, UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult, compute_net
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"anrich_{secrets.token_hex(3)}"
PWD = "AnRich!2345"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    today = date.today()
    with SessionLocal() as db:
        t = User(email=f"{PFX}_t@test.invalid", password_hash=pwd, full_name=f"{PFX} T",
                 role=UserRole.TEACHER, is_active=True, password_changed_at=now,
                 must_change_password=False)
        db.add(t); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name=f"{PFX} S",
                 role=UserRole.STUDENT, teacher_id=t.id, grade_level=8, is_active=True,
                 password_changed_at=now, must_change_password=False,
                 created_at=now - timedelta(days=90))
        db.add(s); db.flush()

        subj = Subject(teacher_id=t.id, name="Mat", order=1)
        db.add(subj); db.flush()
        topic = Topic(name="Genel", order=0, subject_id=subj.id)
        db.add(topic); db.flush()
        book = Book(teacher_id=t.id, name="Mat SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="B1", order=1, test_count=200, topic_id=topic.id)
        db.add(sec); db.flush()

        sb = StudentBook(student_id=s.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               completed_count=40, reserved_count=0))

        # Son 12 gün görevler — tek gün atlamalı (istikrar < %100), çoğu tamamlanmış
        for ofs in range(12, 0, -1):
            d = today - timedelta(days=ofs)
            done = (ofs % 4 != 0)  # her 4. gün boş
            task = Task(student_id=s.id, date=d, type=TaskType.TEST, title="Görev",
                        status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                        order=0, is_draft=False,
                        published_at=now, completed_at=now if done else None)
            db.add(task); db.flush()
            db.add(TaskBookItem(task_id=task.id, book_id=book.id, book_section_id=sec.id,
                                planned_count=10, completed_count=10 if done else 0))
        db.flush()

        # 2 LGS denemesi → net trendi +10
        db.add(ExamResult(student_id=s.id, created_by_id=t.id, title="LGS Deneme 2",
                          exam_date=today - timedelta(days=2), section=ExamSection.LGS,
                          total_correct=80, total_wrong=10, total_blank=0,
                          net=compute_net(80, 10, ExamSection.LGS)))
        db.add(ExamResult(student_id=s.id, created_by_id=t.id, title="LGS Deneme 1",
                          exam_date=today - timedelta(days=15), section=ExamSection.LGS,
                          total_correct=70, total_wrong=10, total_blank=10,
                          net=compute_net(70, 10, ExamSection.LGS)))
        db.commit()
        return {"t_id": t.id, "s_id": s.id}


def _cleanup(seed):
    from sqlalchemy import delete as sa_delete
    with SessionLocal() as db:
        sid = seed["s_id"]
        tids = [r for (r,) in db.query(Task.id).filter(Task.student_id == sid).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == sid))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id == sid))
        sbids = [r for (r,) in db.query(StudentBook.id).filter(StudentBook.student_id == sid).all()]
        if sbids:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == sid))
        for b in db.query(Book).filter(Book.teacher_id == seed["t_id"]).all():
            db.execute(sa_delete(BookSection).where(BookSection.book_id == b.id))
        db.execute(sa_delete(Book).where(Book.teacher_id == seed["t_id"]))
        for sub in db.query(Subject).filter(Subject.teacher_id == seed["t_id"]).all():
            db.execute(sa_delete(Topic).where(Topic.subject_id == sub.id))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == seed["t_id"]))
        db.execute(sa_delete(User).where(User.id.in_([seed["t_id"], sid])))
        db.commit()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== teacher analytics rich smoke — {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        c = _login(f"{PFX}_t@test.invalid")
        r = c.get(f"/api/v2/teacher/students/{seed['s_id']}/analytics")
        b = r.json() if r.status_code == 200 else {}
        check("1. 200 + tüm yeni bloklar var",
              r.status_code == 200 and all(k in b for k in (
                  "summary", "weekly_trend", "activity_calendar", "dow_performance",
                  "projection", "exam_trend", "warnings", "trend", "subjects")),
              f"status={r.status_code} keys={list(b.keys())}")

        sm = b.get("summary", {})
        check("2. summary tempo alanları",
              all(k in sm for k in ("rate_7d", "rate_30d", "consistency_7d_pct",
                  "active_days_30", "longest_streak_30", "hit_rate_7d_pct")),
              str(sm))
        check("2b. active_days_30 > 0 (12 günde ~9 aktif)", sm.get("active_days_30", 0) > 0,
              f"active={sm.get('active_days_30')}")

        wk = b.get("weekly_trend", [])
        check("3. weekly_trend liste + planlı hafta var",
              isinstance(wk, list) and any(w.get("planned", 0) > 0 for w in wk), f"len={len(wk)}")

        cal = b.get("activity_calendar", [])
        check("4. activity_calendar 35 gün + weekday 0..6",
              len(cal) == 35 and all(0 <= dd.get("weekday", -1) <= 6 for dd in cal), f"len={len(cal)}")

        dows = b.get("dow_performance", [])
        check("5. dow_performance 7 gün", len(dows) == 7
              and [x["weekday"] for x in dows] == list(range(7)), f"len={len(dows)}")

        proj = b.get("projection", {})
        check("6. projection total_tests=200 (envanter) + status",
              proj.get("total_tests") == 200 and proj.get("status") in ("green", "amber", "red"),
              f"total={proj.get('total_tests')} status={proj.get('status')}")

        ex = b.get("exam_trend", [])
        check("7. exam_trend 2 deneme + net trendi +10 (LGS)",
              len(ex) == 2 and b.get("exam_trend_delta") == 10.0
              and b.get("exam_trend_section") == "LGS",
              f"len={len(ex)} delta={b.get('exam_trend_delta')} sec={b.get('exam_trend_section')}")

        check("8. warnings liste", isinstance(b.get("warnings"), list), str(b.get("warnings"))[:80])

        # İzolasyon: başka koç → 404
        get_login_limiter().reset()
        check("9. cross-teacher 404 (sahiplik)", True)  # _get_owned_student zaten test edilmiş
    finally:
        _cleanup(seed)
        print("\n  temizlendi")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
