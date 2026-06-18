"""Devret (carryover) HTTP smoke — GET candidates + POST carry uçtan uca.

Koç login → geçen haftadan eksikler listelenir (reconcile kapasiteyi açar) →
seçili kalem bu haftaya taşınır (yeni görev + yeni rezerv). Eski görev durur.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    SuspiciousIp, Task, TaskBookItem, TaskStatus, TaskType, Topic, User, UserRole,
    WeeklyProgram,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"coh{secrets.token_hex(3)}"
PASSWORD = "Carry!2026X"
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
    print(f"\n=== carryover HTTP smoke — {PFX} ===\n")
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
        subj = Subject(name=f"{PFX} Ders", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Konu", order=0, subject_id=subj.id); db.add(topic); db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI, teacher_id=teacher.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Bölüm A", test_count=3, order=0, topic_id=topic.id)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        sp = SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=3, completed_count=0)
        db.add(sp); db.flush()
        # Geçen hafta görevi — 3 test rezerv, yapılmadı (tam kapasite kilitli)
        t_past = Task(student_id=student.id, date=today - timedelta(days=6), type=TaskType.TEST,
                      title="Geçen hafta", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_past); db.flush()
        db.add(TaskBookItem(task_id=t_past.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=3, completed_count=0))
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "book": book.id, "sec": sec.id,
               "sp": sp.id, "t_past": t_past.id, "subj": subj.id}

    get_login_limiter().reset()
    client = TestClient(app)
    try:
        # cleanup any testclient IP block from prior runs
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        r = client.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("1. koç login 200", r.status_code == 200, r.text[:120])

        # GET candidates — reconcile kapasiteyi açar + adayı listeler (GÖREV düzeyi)
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/carryover-candidates")
        check("2. candidates 200", r.status_code == 200, r.text[:120])
        body = r.json()
        check("2b. mode=plan (aktif/yeni hafta)", body.get("mode") == "plan", body.get("mode"))
        cands = body.get("candidates", [])
        mine = [c for c in cands if c["task_id"] == ids["t_past"]]
        check("3. geçen haftanın eksik görevi adaylarda (kalan=3)",
              len(mine) == 1 and mine[0]["total_remaining"] == 3, f"got {mine}")
        with SessionLocal() as db:
            check("4. reconcile sonrası sec reserved=0 (kapasite açıldı)",
                  db.get(SectionProgress, ids["sp"]).reserved_count == 0)

        # POST carry → görevi bu haftaya (bugün) taşı
        r = client.post(
            f"/api/v2/teacher/students/{ids['student']}/carryover",
            json={"target_date": today.isoformat(), "task_ids": [ids["t_past"]]},
        )
        check("5. carry 200", r.status_code == 200, r.text[:160])
        check("6. created_tasks=1", r.json().get("data", {}).get("created_tasks") == 1, r.text[:120])
        with SessionLocal() as db:
            check("7. taşıma sonrası sec reserved=3 (yeni görevde yeniden rezerv)",
                  db.get(SectionProgress, ids["sp"]).reserved_count == 3)
            new_tasks = db.query(Task).filter(
                Task.student_id == ids["student"], Task.date == today).all()
            check("8. bugün yeni görev oluştu", len(new_tasks) == 1, f"got {len(new_tasks)}")
            src = db.get(Task, ids["t_past"])
            check("9. eski görev hâlâ duruyor + carried_at işaretlendi",
                  src is not None and src.carried_at is not None)

        # GET candidates tekrar → taşınan görev listeden DÜŞTÜ (dinamik)
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/carryover-candidates")
        cands2 = r.json().get("candidates", [])
        check("10. taşınan görev artık adaylarda YOK (dinamik düşme)",
              ids["t_past"] not in {c["task_id"] for c in cands2}, f"got {[c['task_id'] for c in cands2]}")

        # BROWSE mode: geçmiş program + ikinci (taşınmamış) görev
        with SessionLocal() as db:
            prog = WeeklyProgram(student_id=ids["student"], coach_id=ids["teacher"],
                                 start_date=today - timedelta(days=7), end_date=today - timedelta(days=1),
                                 name="Geçen hafta")
            db.add(prog); db.flush()
            t2 = Task(student_id=ids["student"], date=today - timedelta(days=5), type=TaskType.VIDEO,
                      title="Geçen hafta video", status=TaskStatus.PENDING, order=2, is_draft=False)
            db.add(t2); db.flush()
            db.commit()
            ids["prog"] = prog.id; ids["t2"] = t2.id
        r = client.get(
            f"/api/v2/teacher/students/{ids['student']}/carryover-candidates?program_id={ids['prog']}")
        bj = r.json()
        check("11. geçmiş program görüntüleme → mode=browse", bj.get("mode") == "browse", bj.get("mode"))
        bids = {c["task_id"] for c in bj.get("candidates", [])}
        check("12. browse: o haftanın taşınmamış görevi (video) listede", ids["t2"] in bids, f"got {bids}")
        check("13. browse: taşınmış (carried) görev listede YOK", ids["t_past"] not in bids, f"got {bids}")
    finally:
        with SessionLocal() as db:
            # tüm öğrenci görevlerini sil
            tids = [t.id for t in db.query(Task).filter(Task.student_id == ids["student"]).all()]
            if tids:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id == ids["student"]))
            db.execute(sa_delete(SectionProgress).where(SectionProgress.book_section_id == ids["sec"]))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id == ids["sec"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
