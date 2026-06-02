"""Kapsamlı uyarı/risk doğruluk simülasyonu — yanlış-pozitif + zamanlama testi.

Kullanıcı 2026-05-23: yeni oluşturulan öğrenci hemen "giriş yok / hareket yok /
programsız" uyarısı alıyordu. Onboarding grace eklendi. Bu script holistik
doğrular: doğru zamanda + doğru durumda üretiliyor mu, yanlış-pozitif var mı.

Senaryolar (risk_analysis.compute_risk_score + analytics.generate_warnings):
  1. YENİ (bugün, giriş yok, programsız)        → SESSİZ (hiç uyarı)
  2. ESKİ programsız, hiç giriş (10g)            → no_login_5d + no_program
  3. ESKİ programsız, dün giriş (10g)            → no_program (no_login YOK)
  4. ZAMANLAMA: 2g programsız → no_program YOK; 4g → no_program VAR
  5. ESKİ programlı, 3 gün boş (10g)             → inactive_3d + consecutive_empty
  6. AKTİF (10g, bugün giriş + tamamlama)        → temiz
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
    Book, BookSection, BookType, Subject, Task, TaskBookItem, TaskType, User, UserRole,
)
from app.services import analytics, risk_analysis
from app.services.security import hash_password

PFX = f"alert_{secrets.token_hex(3)}"
PWD = hash_password("AlertSim!23")
now = datetime.now(timezone.utc)
today = date.today()
uids: list[int] = []
coach_id = None
subj_id = book_id = section_id = None

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


def _mk_student(suffix, *, age_days, last_login_days=None):
    with SessionLocal() as db:
        s = User(email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                 full_name=f"{PFX}-{suffix}", role=UserRole.STUDENT,
                 teacher_id=coach_id, institution_id=None, grade_level=8, is_active=True,
                 password_changed_at=now, must_change_password=False)
        s.created_at = now - timedelta(days=age_days)
        if last_login_days is not None:
            s.last_login_at = now - timedelta(days=last_login_days)
        db.add(s); db.commit(); db.refresh(s)
    uids.append(s.id)
    return s.id


def _add_task(student_id, day, planned, completed):
    with SessionLocal() as db:
        t = Task(student_id=student_id, date=day, type=TaskType.TEST, title="P",
                 is_draft=False, published_at=now)
        db.add(t); db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=book_id, book_section_id=section_id,
                            planned_count=planned, completed_count=completed,
                            correct_count=completed, wrong_count=0))
        db.commit()


def _risk_codes(sid):
    with SessionLocal() as db:
        s = db.get(User, sid)
        a = risk_analysis.compute_risk_score(db, student=s, today=today, now=now)
        return {i.code for i in a.indicators}, a.score, a.level


def _warning_codes(sid):
    with SessionLocal() as db:
        s = db.get(User, sid)
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        ws = analytics.generate_warnings(db, s, today, proj)
        return {w.code for w in ws}


def main():
    global coach_id, subj_id, book_id, section_id
    print(f"\n=== UYARI/RİSK DOĞRULUK SİMÜLASYONU — {PFX} ===\n")
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD, full_name=f"{PFX}-coach",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
        db.add(coach); db.flush(); coach_id = coach.id
        subj = Subject(name=f"{PFX} Mat", teacher_id=coach.id); db.add(subj); db.flush(); subj_id = subj.id
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} Kitap", type=BookType.SORU_BANKASI); db.add(book); db.flush(); book_id = book.id
        sec = BookSection(book_id=book.id, label="Ü1"); db.add(sec); db.flush(); section_id = sec.id
        db.commit()
    uids.append(coach_id)

    try:
        # 1) YENİ öğrenci — hiçbir uyarı olmamalı
        s1 = _mk_student("yeni", age_days=0)
        rc, score, lvl = _risk_codes(s1)
        wc = _warning_codes(s1)
        check("1. YENİ öğrenci → risk SESSİZ (no_login/no_program yok)",
              "no_login_5d" not in rc and "no_program" not in rc, f"codes={rc} score={score}")
        check("1b. YENİ öğrenci → 'inactive_3d' uyarısı YOK", "inactive_3d" not in wc, f"warnings={wc}")

        # 2) ESKİ programsız, hiç giriş yapmamış
        s2 = _mk_student("eski_giris_yok", age_days=10)
        rc, _, _ = _risk_codes(s2)
        check("2. ESKİ + hiç giriş + programsız → no_login_5d + no_program",
              "no_login_5d" in rc and "no_program" in rc, f"codes={rc}")

        # 3) ESKİ programsız, dün giriş yaptı
        s3 = _mk_student("eski_dun_giris", age_days=10, last_login_days=1)
        rc, _, _ = _risk_codes(s3)
        wc = _warning_codes(s3)
        check("3. ESKİ + dün giriş + programsız → no_program VAR, no_login YOK",
              "no_program" in rc and "no_login_5d" not in rc, f"codes={rc}")
        check("3b. programsız → inactive_3d YOK", "inactive_3d" not in wc, f"warnings={wc}")

        # 4) ZAMANLAMA — no_program eşiği (3 gün)
        s4a = _mk_student("yas2", age_days=2)
        s4b = _mk_student("yas4", age_days=4)
        rc_a, _, _ = _risk_codes(s4a)
        rc_b, _, _ = _risk_codes(s4b)
        check("4. ZAMANLAMA: 2g → no_program YOK; 4g → no_program VAR",
              "no_program" not in rc_a and "no_program" in rc_b, f"2g={rc_a} 4g={rc_b}")

        # 5) ESKİ programlı, son 3 gün planlı ama tamamlama yok
        s5 = _mk_student("eski_programli_bos", age_days=10, last_login_days=1)
        for dd in (0, 1, 2):
            _add_task(s5, today - timedelta(days=dd), planned=20, completed=0)
        rc, _, _ = _risk_codes(s5)
        wc = _warning_codes(s5)
        check("5. ESKİ + programlı + 3 gün boş → inactive_3d uyarısı VAR",
              "inactive_3d" in wc, f"warnings={wc}")
        check("5b. risk: consecutive_empty veya low_completion VAR",
              "consecutive_empty" in rc or "low_completion" in rc, f"codes={rc}")

        # 6) AKTİF öğrenci — bugün giriş + tamamlama
        s6 = _mk_student("aktif", age_days=10, last_login_days=0)
        _add_task(s6, today, planned=10, completed=10)
        rc, score, lvl = _risk_codes(s6)
        wc = _warning_codes(s6)
        check("6. AKTİF öğrenci → inactive_3d YOK + bugün_tik_yok YOK",
              "inactive_3d" not in wc and "today_no_tick" not in wc, f"warnings={wc} risk={rc}")

    finally:
        with SessionLocal() as db:
            sids = [u for u in uids if u != coach_id]
            if sids:
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            if section_id:
                db.execute(sa_delete(BookSection).where(BookSection.id == section_id))
            if book_id:
                db.execute(sa_delete(Book).where(Book.id == book_id))
            if subj_id:
                db.execute(sa_delete(Subject).where(Subject.id == subj_id))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
