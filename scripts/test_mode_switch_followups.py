"""Mod geçişi saha düzeltmeleri — Taha #84 vakası (2026-10-22).

1) Havuza geçen öğrencinin gün gün program haftaları takvim haftasına dağılmaz; geçişte yarıda
   kalan program haftası kendi haftası olarak kalır (`cut`) ve eğilim dizisine girmez (sahte
   "3 hafta üst üste kötüleşme" yok).
2) Bayat (7+ gün geçmiş) yayınlanmamış taslak görevin rezervi ölü sayılır; yakın taslak korunur.
4) Geçişte öğrenciye bildirim: cihaz varsa push, yoksa e-posta.
5) Boş havuzun başlığı "yolunda" demez.

Çalıştır: PYTHONPATH=. python scripts/test_mode_switch_followups.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, TaskStatus, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.device_push_token import DevicePushToken  # noqa: E402
from app.models.pool import ProgramModeChange  # noqa: E402
from app.models.weekly_program import WeeklyProgram  # noqa: E402
from app.services import analytics, program_mode_switch as pms, push_notifications  # noqa: E402
from app.services import student_email_fallback as sef  # noqa: E402
from app.services import weekly_progress as wp  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_flags import evaluate_flags  # noqa: E402

PFX = f"msf_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@example.com", password_hash=hash_password("Xx!234567890ab"),
             full_name=f"MSF {tag}", role=role, is_active=True, created_at=now - timedelta(days=90), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _task(db, student, day, planned, done, sec, book, draft=False):
    t = Task(student_id=student.id, date=day, title=f"Görev {day}", type="test", is_draft=draft,
             status=TaskStatus.COMPLETED if done >= planned else TaskStatus.PENDING,
             completed_at=datetime.combine(day, time(18, 0), tzinfo=timezone.utc) if done >= planned else None)
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id, planned_count=planned,
                        completed_count=done))
    db.flush()
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        sub = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(sub)
        db.flush()
        ids["subjects"].append(sub.id)
        b = Book(teacher_id=coach.id, subject_id=sub.id, name=f"{PFX} Kitap", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Bölüm", test_count=500, order=1)
        db.add(sec)
        db.flush()

        s = _user(db, "st", UserRole.STUDENT, teacher_id=coach.id, grade_level=12)
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        # Program haftaları (7'şer gün); son hafta bugünü kapsar → geçişte yarıda kalır.
        weeks = [(today - timedelta(days=33), 30), (today - timedelta(days=26), 35),
                 (today - timedelta(days=19), 30), (today - timedelta(days=12), 24),
                 (today - timedelta(days=5), 14)]
        for start, done in weeks:
            db.add(WeeklyProgram(student_id=s.id, coach_id=coach.id, start_date=start,
                                 end_date=start + timedelta(days=6)))
            _task(db, s, start, done, done, sec, b)
        # Bayat taslak (20 gün önce) + yakın taslak (3 gün önce) + geçmiş yayında yapılmamış
        _task(db, s, today - timedelta(days=20), 3, 0, sec, b, draft=True)
        _task(db, s, today - timedelta(days=3), 2, 0, sec, b, draft=True)
        _task(db, s, today - timedelta(days=2), 4, 0, sec, b)
        _task(db, s, today + timedelta(days=1), 5, 0, sec, b)  # geçişte silinir
        done_total = sum(d for _, d in weeks)
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=3 + 2 + 4 + 5, completed_count=done_total))
        db.commit()
        return {"coach": coach.id, "s": s.id, "sb": sb.id, "sec": sec.id, "p4": weeks[-1][0]}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(ProgramModeChange).where(ProgramModeChange.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        db.execute(sa_delete(DevicePushToken).where(DevicePushToken.user_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    d = seed()
    try:
        # --- 2) önizleme: bayat taslak ölü sayılır, yakın taslak korunur
        with SessionLocal() as db:
            s = db.get(User, d["s"])
            pv = pms.preview(db, s, "havuz", today)
            check("2a önizleme ölü rezerv = yayında 4 + bayat taslak 3 (yakın taslak hariç)",
                  pv.dead_reserve_tests == 7, f"{pv.dead_reserve_tests}")

            pms.switch_to_havuz(db, student=s, actor=db.get(User, d["coach"]), effective_on=today,
                                open_first_period=True, expected_next_on=today + timedelta(days=7), note=None)
            db.commit()
            sp = db.query(SectionProgress).filter_by(student_book_id=d["sb"], book_section_id=d["sec"]).one()
            check("2b geçiş sonrası kalan rezerv yalnız yakın taslak (2)", sp.reserved_count == 2,
                  f"{sp.reserved_count}")

        # --- 1) haftalar: program haftası kaybolmaz, kırpılır, eğilime girmez
        with SessionLocal() as db:
            s = db.get(User, d["s"])
            weeks = wp._weeks(db, s, today)
            p4 = next((w for w in weeks if w.start == d["p4"]), None)
            check("1a geçiş haftası kendi başlangıcıyla kalır (takvime dağılmaz)",
                  p4 is not None and p4.kind == "program", f"{[(w.start, w.end, w.kind) for w in weeks]}")
            check("1b geçiş haftası geçiş gününden önce biter + cut işaretli",
                  p4 is not None and p4.end == today - timedelta(days=1) and p4.cut, f"{p4}")
            check("1c dönem bugün başlar", any(w.kind == "donem" and w.start == today for w in weeks))
            check("1d tüm program haftaları korunur (4 tam + 1 kırpık)",
                  sum(1 for w in weeks if w.kind == "program") == 5, f"{[(w.start, w.kind) for w in weeks]}")
            res = wp.build_weekly_progress(db, s, today=today)
            card = next(c for c in res["cards"] if c["key"] == "test_done")
            check("1e kırpık hafta sahte 'kötüleşme' üretmez", not card["trend"],
                  f"run={card['trend_run']} {card['verdict']}")
            check("1f grafikte kırpık hafta işaretli",
                  any("mod geçişiyle kısaldı" in r["range"] for r in res["chart"]), f"{res['chart']}")

        # --- 5) boş havuz başlığı
        with SessionLocal() as db:
            s = db.get(User, d["s"])
            rep = evaluate_flags(db, s, today)
            check("5a boş havuz 'yolunda' demez", "yolunda" not in (rep.headline or "")
                  and "boş" in (rep.headline or ""), rep.headline)

        # --- 4) öğrenci bildirimi
        sent: list = []
        orig = push_notifications.safe_push
        push_notifications.safe_push = lambda db, **kw: sent.append(kw)
        try:
            with SessionLocal() as db:
                s = db.get(User, d["s"])
                r1 = sef.notify_student_program_mode(db, student=s, to_mode="havuz", effective_on=today,
                                                     expected_next_on=today + timedelta(days=7))
                check("4a cihazsız öğrenci: push yok, e-posta denenir", not r1["push"] and r1["email"] in
                      ("sent", "failed"), f"{r1}")
                db.add(DevicePushToken(user_id=s.id, token=f"ExponentPushToken[{PFX}]", platform="ios"))
                db.commit()
                r2 = sef.notify_student_program_mode(db, student=s, to_mode="havuz", effective_on=today)
                check("4b cihazlı öğrenci: push gider, e-posta atılmaz",
                      r2["push"] and r2["email"] == "has_device", f"{r2}")
                check("4c push havuz ekranına yönlendirir",
                      sent and sent[-1]["data"].get("screen") == "pool", f"{sent}")
        finally:
            push_notifications.safe_push = orig
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
