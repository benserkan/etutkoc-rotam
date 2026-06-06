"""'{Ders} henüz başlanmadı' (subject_untouched) uyarısı — DENEME≠TEST + koruma testi.

Kullanıcı 2026-06-06 (Berra/student 11): Türk Dili ve Edebiyatı'na tek atama bir
BRANŞ DENEMESİ kitabıydı; subject_breakdown deneme'yi derse katıp "henüz başlanmadı
· hiçbir test tamamlanmamış" uyarısını yaktırıyordu (DENEME≠TEST ihlali).

Senaryolar (analytics.generate_warnings, subject_untouched_*):
  A. DENEME-only ders (rezerv + yayınlanmış geçmiş görev)  → UYARI YOK (Berra fix)
  B. TEST dersi (rezerv + yayınlanmış geçmiş görev, compl=0) → UYARI VAR (doğru)
  C. TEST dersi ama geçmiş görev TASLAK                      → UYARI YOK (Defect A)
  D. TEST dersi, completed>0 (baseline, Task.completed_at yok) → UYARI YOK (Defect B)
  E. TEST dersi, görev TAMAMLANMIŞ                           → UYARI YOK (sanity)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services import analytics
from app.services.security import hash_password

PFX = f"untouched_{secrets.token_hex(3)}"
PWD = hash_password("Untouched!23")
now = datetime.now(timezone.utc)
today = date.today()

coach_id = None
uids: list[int] = []
subj_ids: list[int] = []
book_ids: list[int] = []

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


def _mk_student(suffix):
    with SessionLocal() as db:
        s = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                 full_name=f"{PFX}-{suffix}", role=UserRole.STUDENT,
                 teacher_id=coach_id, institution_id=None, grade_level=12,
                 is_active=True, password_changed_at=now, must_change_password=False)
        s.created_at = now - timedelta(days=30)  # eski hesap → onboarding grace yok
        s.last_login_at = now - timedelta(days=1)
        db.add(s); db.commit(); db.refresh(s)
    uids.append(s.id)
    return s.id


def _mk_book(subject_name, book_type, test_count=20):
    """Subject + Book + tek bölüm oluşturur; (subject_id, book_id, section_id)."""
    with SessionLocal() as db:
        subj = Subject(name=f"{PFX} {subject_name}", teacher_id=coach_id)
        db.add(subj); db.flush()
        book = Book(teacher_id=coach_id, subject_id=subj.id,
                    name=f"{PFX} {subject_name} Kitap", type=book_type)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Ü1", test_count=test_count)
        db.add(sec); db.flush()
        db.commit()
        subj_ids.append(subj.id); book_ids.append(book.id)
        return subj.id, book.id, sec.id


def _assign(student_id, book_id, section_id, reserved=0, completed=0):
    with SessionLocal() as db:
        sb = StudentBook(student_id=student_id, book_id=book_id)
        db.add(sb); db.flush()
        if reserved or completed:
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=section_id,
                                   reserved_count=reserved, completed_count=completed))
        db.commit()


def _add_task(student_id, day, book_id, section_id, planned, completed,
              *, draft=False, done=False):
    with SessionLocal() as db:
        t = Task(student_id=student_id, date=day, type=TaskType.TEST, title="P",
                 is_draft=draft, published_at=(None if draft else now),
                 completed_at=(now if done else None))
        db.add(t); db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=book_id, book_section_id=section_id,
                            planned_count=planned, completed_count=completed,
                            correct_count=completed, wrong_count=0))
        db.commit()


def _warning_codes(sid):
    with SessionLocal() as db:
        s = db.get(User, sid)
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        ws = analytics.generate_warnings(db, s, today, proj)
        return {w.code for w in ws}


def main():
    global coach_id
    print(f"\n=== subject_untouched DENEME≠TEST + koruma testi — {PFX} ===\n")
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                     full_name=f"{PFX}-coach", role=UserRole.TEACHER,
                     institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
        db.add(coach); db.flush(); coach_id = coach.id
        db.commit()
    uids.append(coach_id)
    past = today - timedelta(days=4)

    try:
        # A) Berra reproduction — DENEME-only ders, rezerv + yayınlanmış geçmiş görev
        sA = _mk_student("denemeOnly")
        subjA, bookA, secA = _mk_book("TurkDili", BookType.BRANS_DENEMESI, test_count=10)
        _assign(sA, bookA, secA, reserved=1, completed=0)
        _add_task(sA, past, bookA, secA, planned=1, completed=0)
        wc = _warning_codes(sA)
        check("A. DENEME-only ders → subject_untouched UYARI YOK (Berra fix)",
              f"subject_untouched_{subjA}" not in wc, f"warnings={wc}")

        # B) Gerçek TEST dersi — rezerv + yayınlanmış geçmiş görev, completed=0
        sB = _mk_student("testUntouched")
        subjB, bookB, secB = _mk_book("Matematik", BookType.SORU_BANKASI)
        _assign(sB, bookB, secB, reserved=5, completed=0)
        _add_task(sB, past, bookB, secB, planned=5, completed=0)
        wc = _warning_codes(sB)
        check("B. TEST dersi rezervli + dokunulmamış → subject_untouched VAR (doğru)",
              f"subject_untouched_{subjB}" in wc, f"warnings={wc}")

        # C) TEST dersi ama geçmiş görev TASLAK → uyarı yok (Defect A)
        sC = _mk_student("testDraft")
        subjC, bookC, secC = _mk_book("Fizik", BookType.SORU_BANKASI)
        _assign(sC, bookC, secC, reserved=5, completed=0)
        _add_task(sC, past, bookC, secC, planned=5, completed=0, draft=True)
        wc = _warning_codes(sC)
        check("C. TEST dersi geçmiş görev TASLAK → subject_untouched YOK (Defect A)",
              f"subject_untouched_{subjC}" not in wc, f"warnings={wc}")

        # D) TEST dersi, completed>0 (baseline: SectionProgress.completed_count,
        #    Task.completed_at YOK) → uyarı yok (Defect B)
        sD = _mk_student("testBaseline")
        subjD, bookD, secD = _mk_book("Kimya", BookType.SORU_BANKASI)
        _assign(sD, bookD, secD, reserved=5, completed=3)   # 3 baseline işaretli
        _add_task(sD, past, bookD, secD, planned=5, completed=0)  # tamamlanmamış rezerv
        wc = _warning_codes(sD)
        check("D. TEST dersi completed>0 (baseline) → subject_untouched YOK (Defect B)",
              f"subject_untouched_{subjD}" not in wc, f"warnings={wc}")

        # E) TEST dersi, görev TAMAMLANMIŞ → untouched yok (sanity)
        sE = _mk_student("testDone")
        subjE, bookE, secE = _mk_book("Biyoloji", BookType.SORU_BANKASI)
        _assign(sE, bookE, secE, reserved=0, completed=5)
        _add_task(sE, past, bookE, secE, planned=5, completed=5, done=True)
        wc = _warning_codes(sE)
        check("E. TEST dersi görev tamamlanmış → subject_untouched YOK (sanity)",
              f"subject_untouched_{subjE}" not in wc, f"warnings={wc}")

    finally:
        with SessionLocal() as db:
            sids = [u for u in uids if u != coach_id]
            if sids:
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sbids)))
            if book_ids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(book_ids)))
                db.execute(sa_delete(Book).where(Book.id.in_(book_ids)))
            if subj_ids:
                db.execute(sa_delete(Subject).where(Subject.id.in_(subj_ids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
