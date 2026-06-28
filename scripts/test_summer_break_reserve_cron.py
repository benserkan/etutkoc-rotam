"""Faz 1a (günlük ölü-rezerv cron) + Faz 1b (mola modu / yaz molası) smoke.

Senaryo (Elif'in durumu genelleştirilmiş):
- Geçen haftadan yapılmamış rezerv (sec_a) = ÖLÜ → cron otomatik düşürmeli.
- BU haftanın (bugün) yapılmamış rezervi (sec_b) = CANLI → cron DOKUNMAZ,
  ama 'yaz molası' anında serbest bırakmalı (cutoff=today+1).
- Mola modunda koç-yüzü uyarılar (student_snapshot.warnings) SUSAR; takibe
  devam edince geri gelir.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
    WeeklyProgram,
)
from app.services import task_service as ts
from app.services.analytics import student_snapshot
from app.services.pause import (
    REASON_SUMMER_BREAK,
    pause_user,
    resume_user,
)
from app.services.security import hash_password

PFX = f"smbreak{secrets.token_hex(3)}"
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


def _reserved(db, sp_id) -> int:
    return db.get(SectionProgress, sp_id).reserved_count


def main() -> int:
    print(f"\n=== summer break + dead-reserve cron smoke — {PFX} ===\n")
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    past_date = this_monday - timedelta(days=1)  # geçen hafta (cutoff'tan kesin önce)
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="T", role=UserRole.TEACHER, is_active=True, plan="solo_free")
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password("X!23pass"),
                       full_name="S", role=UserRole.STUDENT, is_active=True, grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        student.created_at = datetime.now(timezone.utc) - timedelta(days=20)  # eski hesap
        subj = Subject(name=f"{PFX} Ders", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Konu", order=0, subject_id=subj.id); db.add(topic); db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        sec_a = BookSection(book_id=book.id, label="Bölüm A", test_count=10, order=0, topic_id=topic.id)
        sec_b = BookSection(book_id=book.id, label="Bölüm B", test_count=10, order=1, topic_id=topic.id)
        db.add_all([sec_a, sec_b]); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        sp_a = SectionProgress(student_book_id=sb.id, book_section_id=sec_a.id, reserved_count=3, completed_count=0)
        sp_b = SectionProgress(student_book_id=sb.id, book_section_id=sec_b.id, reserved_count=2, completed_count=0)
        db.add_all([sp_a, sp_b]); db.flush()

        # GEÇMİŞ görev (geçen hafta, PENDING, yayında) — sec_a 3 test, yapılmadı → ÖLÜ
        t_past = Task(student_id=student.id, date=past_date, type=TaskType.TEST,
                      title="Geçen hafta", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_past); db.flush()
        db.add(TaskBookItem(task_id=t_past.id, book_id=book.id, book_section_id=sec_a.id,
                            planned_count=3, completed_count=0))
        # BUGÜNKÜ görev (yayında, yapılmadı) — sec_b 2 test → CANLI + today_no_tick uyarısı
        t_today = Task(student_id=student.id, date=today, type=TaskType.TEST,
                       title="Bugün", status=TaskStatus.PENDING, order=0, is_draft=False)
        db.add(t_today); db.flush()
        db.add(TaskBookItem(task_id=t_today.id, book_id=book.id, book_section_id=sec_b.id,
                            planned_count=2, completed_count=0))
        db.commit()
        ids = {"student": student.id, "teacher": teacher.id, "book": book.id,
               "sec_a": sec_a.id, "sec_b": sec_b.id, "sp_a": sp_a.id, "sp_b": sp_b.id,
               "t_past": t_past.id, "t_today": t_today.id}

    try:
        # ---------------- Faz 1a — günlük cron (ölü rezerv) ----------------
        with SessionLocal() as db:
            check("0. başlangıç sec_a=3 (ölü), sec_b=2 (canlı)",
                  _reserved(db, ids["sp_a"]) == 3 and _reserved(db, ids["sp_b"]) == 2)

            res = ts.reconcile_all_active_reservations(db, today=today)
            db.commit()
            check("1a-1. cron sec_a → 0 (geçen hafta ölü rezerv serbest)",
                  _reserved(db, ids["sp_a"]) == 0, f"got {_reserved(db, ids['sp_a'])}")
            check("1a-2. cron sec_b → 2 DEĞİŞMEDİ (bu hafta canlı, korunur)",
                  _reserved(db, ids["sp_b"]) == 2, f"got {_reserved(db, ids['sp_b'])}")
            check("1a-3. cron benim öğrencimi taradı + serbest bıraktı",
                  res["students_scanned"] >= 1 and res["released_items"] >= 1, f"got {res}")

            # idempotent
            ts.reconcile_all_active_reservations(db, today=today)
            db.commit()
            check("1a-4. ikinci cron sec_a hâlâ 0, sec_b hâlâ 2 (idempotent)",
                  _reserved(db, ids["sp_a"]) == 0 and _reserved(db, ids["sp_b"]) == 2)

        # ---------------- Faz 1b — mola modu (yaz molası) ----------------
        with SessionLocal() as db:
            student = db.get(User, ids["student"])
            snap = student_snapshot(db, student, today=today)
            check("1b-1. mola ÖNCESİ uyarı VAR (today_no_tick)",
                  any(w.code == "today_no_tick" for w in snap.warnings), f"got {[w.code for w in snap.warnings]}")

            # Yaz molası aç
            pause_user(db, student, actor=db.get(User, ids["teacher"]), reason=REASON_SUMMER_BREAK)
            db.refresh(student)
            check("1b-2. is_paused=True + reason=summer_break",
                  student.is_paused and student.pause_reason == REASON_SUMMER_BREAK)

            rel = ts.release_due_reservations_for_pause(db, student_id=student.id, today=today)
            db.commit()
            check("1b-3. mola CANLI haftanın rezervini de serbest bıraktı (sec_b → 0)",
                  _reserved(db, ids["sp_b"]) == 0, f"got {_reserved(db, ids['sp_b'])} rel={rel}")

            snap2 = student_snapshot(db, student, today=today)
            check("1b-4. mola modunda uyarı SUSTU (warnings boş)",
                  len(snap2.warnings) == 0, f"got {[w.code for w in snap2.warnings]}")
            check("1b-5. mola modunda worst_warning_level=green",
                  snap2.worst_warning_level == "green", f"got {snap2.worst_warning_level}")

            # Takibe devam
            resume_user(db, student, actor=db.get(User, ids["teacher"]), is_auto_resume=False)
            db.refresh(student)
            check("1b-6. takibe devam → is_paused=False",
                  not student.is_paused and student.pause_reason is None)
            snap3 = student_snapshot(db, student, today=today)
            check("1b-7. takibe devam → uyarı GERİ geldi (today_no_tick)",
                  any(w.code == "today_no_tick" for w in snap3.warnings),
                  f"got {[w.code for w in snap3.warnings]}")
            # serbest bırakılan rezerv geri YÜKLENMEZ
            check("1b-8. resume rezervi geri yüklemez (sec_b hâlâ 0)",
                  _reserved(db, ids["sp_b"]) == 0)
    finally:
        with SessionLocal() as db:
            tids = [ids["t_past"], ids["t_today"]]
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id == ids["student"]))
            db.execute(sa_delete(SectionProgress).where(
                SectionProgress.book_section_id.in_([ids["sec_a"], ids["sec_b"]])))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id.in_([ids["sec_a"], ids["sec_b"]])))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id.in_(
                db.query(Subject.id).filter(Subject.teacher_id == ids["teacher"]).scalar_subquery())))
            db.execute(sa_delete(Subject).where(Subject.teacher_id == ids["teacher"]))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
