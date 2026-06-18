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
        # Geçen hafta DÜZ TEST görevi — 3 test rezerv (reconcile serbest bırakır,
        # LİSTEDE GÖRÜNMEZ — kitapta çözülmedi olarak görünür)
        t_past = Task(student_id=student.id, date=today - timedelta(days=6), type=TaskType.TEST,
                      title="Geçen hafta test", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_past); db.flush()
        db.add(TaskBookItem(task_id=t_past.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=3, completed_count=0))
        # Geçen hafta ETKİNLİK görevi (video) — LİSTEDE GÖRÜNÜR, taşınabilir
        t_video = Task(student_id=student.id, date=today - timedelta(days=6), type=TaskType.VIDEO,
                       title="Geçen hafta video", status=TaskStatus.PENDING, order=1, is_draft=False)
        db.add(t_video); db.flush()
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "book": book.id, "sec": sec.id,
               "sp": sp.id, "t_past": t_past.id, "t_video": t_video.id, "subj": subj.id}

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
        ctids = {c["task_id"] for c in body.get("candidates", [])}
        check("3. düz TEST görevi listede YOK (rezerv iade edildi, kitapta görünür)",
              ids["t_past"] not in ctids, f"got {ctids}")
        check("3b. ETKİNLİK (video) görevi listede VAR", ids["t_video"] in ctids, f"got {ctids}")
        with SessionLocal() as db:
            check("4. reconcile sonrası sec reserved=0 (kapasite açıldı, kitapta çözülmedi)",
                  db.get(SectionProgress, ids["sp"]).reserved_count == 0)

        # Hata 1: GEÇMİŞ güne taşıma reddedilir (422)
        r = client.post(
            f"/api/v2/teacher/students/{ids['student']}/carryover",
            json={"target_date": (today - timedelta(days=2)).isoformat(), "task_ids": [ids["t_video"]]},
        )
        check("5. Hata1: geçmiş güne taşıma → 422 past_target_date",
              r.status_code == 422 and "past_target_date" in r.text, f"{r.status_code} {r.text[:120]}")

        # POST carry → video görevini bugüne taşı
        r = client.post(
            f"/api/v2/teacher/students/{ids['student']}/carryover",
            json={"target_date": today.isoformat(), "task_ids": [ids["t_video"]]},
        )
        check("6. carry 200 + created=1", r.status_code == 200
              and r.json().get("data", {}).get("created_tasks") == 1, r.text[:160])
        with SessionLocal() as db:
            src = db.get(Task, ids["t_video"])
            check("7. kaynak video carried_at işaretlendi (kayıt durur)", src.carried_at is not None)
            new_tasks = db.query(Task).filter(
                Task.student_id == ids["student"], Task.date == today).all()
            check("8. bugün yeni görev oluştu + kaynağa bağlı (carried_from)",
                  len(new_tasks) == 1 and new_tasks[0].carried_from_task_id == ids["t_video"],
                  f"got {[(t.id, t.carried_from_task_id) for t in new_tasks]}")
            ids["new_task"] = new_tasks[0].id

        # GET candidates → taşınan video listeden DÜŞTÜ (dinamik)
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/carryover-candidates")
        check("9. taşınan video artık adaylarda YOK (dinamik düşme)",
              ids["t_video"] not in {c["task_id"] for c in r.json().get("candidates", [])})

        # Hata 2: yeni görevi sil → kaynak video LİSTEYE GERİ döner
        r = client.delete(f"/api/v2/teacher/tasks/{ids['new_task']}")
        check("10. yeni görev silindi (200)", r.status_code == 200, r.text[:120])
        with SessionLocal() as db:
            check("10b. kaynak video carried_at TEMİZLENDİ (geri-al)",
                  db.get(Task, ids["t_video"]).carried_at is None)
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/carryover-candidates")
        check("10c. Hata2: silinince kaynak video LİSTEYE GERİ döndü",
              ids["t_video"] in {c["task_id"] for c in r.json().get("candidates", [])})

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
        check("12. browse: o haftanın etkinlik görevi (video) listede (bilgi amaçlı)", ids["t2"] in bids, f"got {bids}")
        check("13. browse: düz TEST görevi DE listede (bilgi amaçlı, tüm tipler)",
              ids["t_past"] in bids, f"got {bids}")
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
