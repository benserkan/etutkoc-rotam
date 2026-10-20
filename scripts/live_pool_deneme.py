"""Canlı — havuz editöründe Deneme sekmesi (D1b, 2026-10-20).

  1 Düzenle modunda "Deneme" sekmesi açılır, deneme formu havuz modunda ("Havuza ekle")
  2 Kaynaklı ×2 → DB: unit deneme, quantity 2, 6 soru · listede "deneme başına 6 soru"
  3 Genel TYT → dersiz kalem "Genel deneme" grubu listede
  4 Taşma yok · koyu tema ekran görüntüsü
Ön koşul: backend :8081 + Next :3000.
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

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.services import pool_mode  # noqa: E402
from app.services.security import hash_password  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"lpd_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
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


def seed():
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Havuz Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Havuz Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, program_mode="havuz")
        db.add(st); db.flush()
        bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(bio); db.flush()
        b = Book(teacher_id=coach.id, subject_id=bio.id, name=f"{PFX} Bio Branş", type=BookType.BRANS_DENEMESI)
        db.add(b); db.flush()
        db.add_all([BookSection(book_id=b.id, label=f"DENEME {i}", test_count=1, order=i) for i in range(1, 6)])
        db.add(StudentBook(student_id=st.id, book_id=b.id))
        pool_mode.open_period(db, student=st, coach=coach, opened_on=date.today(),
                              expected_next_on=date.today() + timedelta(days=6))
        db.commit()
        return {"coach": coach.id, "st": st.id, "bio": bio.id, "book": b.id}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["coach"], d["st"]]
        from app.models import ExamResult as _ER  # D3 köprü kayıtları
        db.execute(sa_delete(_ER).where(_ER.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == d["coach"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    os.makedirs(SHOTS, exist_ok=True)
    d = seed()
    print(f"\n=== canlı: havuz Deneme sekmesi — {PFX} ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 950}, color_scheme="dark")
            errs: list[str] = []
            page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', f"{PFX}_t@test.invalid")
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{d['st']}/pool?mod=duzenle", wait_until="networkidle")
            page.wait_for_timeout(3000)
            lt = page.query_selector('button:has-text("Daha sonra")')
            if lt:
                lt.click(); page.wait_for_timeout(600)
            page.locator('[role="tab"]:has-text("Deneme")').first.click()
            page.wait_for_timeout(1500)
            form = page.locator('form[aria-label="Deneme ekleme"]')
            check("1a Deneme sekmesi formu açtı", form.count() == 1)
            check("1b havuz modu düğmesi", form.locator('button[type="submit"]:has-text("Havuza ekle")').count() == 1)
            form.locator('button[aria-pressed]:has-text("2")').first.click()
            page.wait_for_timeout(300)
            ov = page.evaluate("""() => { const f = document.querySelector('form[aria-label="Deneme ekleme"]');
              return f.scrollWidth - f.clientWidth; }""")
            check("4a form taşma yok", ov <= 1, str(ov))
            form.screenshot(path=os.path.join(SHOTS, "pool_deneme_form_dark.png"))
            form.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                it = db.query(PoolItem).filter(PoolItem.student_id == d["st"]).order_by(PoolItem.id.desc()).first()
            check("2a DB: deneme 2 adet, 6 soru", it is not None and it.unit == "deneme" and it.quantity == 2
                  and it.question_count == 6, str(it and (it.unit, it.quantity, it.question_count)))
            body = page.inner_text("body")
            check("2b listede 'deneme başına 6 soru'", "deneme başına 6 soru" in body)

            form = page.locator('form[aria-label="Deneme ekleme"]')
            form.locator('[role="radio"]:has-text("Genel deneme")').click()
            page.wait_for_timeout(300)
            form.locator('select[aria-label="Genel deneme türü"]').select_option("tyt")
            form.locator('button[type="submit"]').click()
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            check("3 'Genel deneme' grubu listede", "genel deneme" in body.lower() and "120 soru" in body)
            page.screenshot(path=os.path.join(SHOTS, "pool_deneme_list_dark.png"), full_page=True)
            check("4b konsol hatası yok", not errs, " | ".join(errs)[:300])
            b.close()
    finally:
        cleanup(d)
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
