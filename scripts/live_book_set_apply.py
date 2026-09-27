"""Kitap setini çok öğrenciye uygula — canlı tarayıcı testi (2026-09-27).

Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
"""
from __future__ import annotations

import os
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookSet, BookSetItem, BookType, SectionProgress, StudentBook, Subject,
    User, UserRole,
)
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

WEB = "http://localhost:3000"
PFX = f"lbsa_{secrets.token_hex(3)}"
PWD = "LiveSetApply!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Canlı Set Koç", role=UserRole.TEACHER, is_active=True,
                     must_change_password=False)
        db.add(coach)
        db.flush()
        sids = []
        for name, g, grp in [("Ada Onuncu Sınıf Uzun Soyadlı", 10, "10-A"), ("Bora Onuncu", 10, "10-A"),
                             ("Cem On Birinci", 11, "11-B")]:
            u = User(email=f"{PFX}_{len(sids)}@test.invalid", password_hash=hash_password(PWD),
                     full_name=name, role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                     grade_level=g, class_group=grp)
            db.add(u)
            db.flush()
            sids.append(u.id)
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        bids = []
        for i in range(2):
            b = Book(name=f"Set Kitabı {i} {PFX}", subject_id=subj.id, teacher_id=coach.id,
                     type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            db.add(BookSection(book_id=b.id, label="Ü1", test_count=5, order=0))
            bids.append(b.id)
        bs = BookSet(teacher_id=coach.id, name=f"10. sınıf seti {PFX}", target_grade_min=10,
                     target_grade_max=10)
        db.add(bs)
        db.flush()
        for i, b in enumerate(bids):
            db.add(BookSetItem(set_id=bs.id, book_id=b, order=i))
        db.commit()
        return {"coach": coach.id, "email": coach.email, "students": sids, "books": bids, "set": bs.id}


def cleanup(d):
    with SessionLocal() as db:
        sbs = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(d["students"]))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(d["students"])))
        db.execute(sa_delete(BookSetItem).where(BookSetItem.set_id == d["set"]))
        db.execute(sa_delete(BookSet).where(BookSet.id == d["set"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(d["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(d["books"])))
        db.execute(sa_delete(User).where(User.id.in_(d["students"] + [d["coach"]])))
        db.commit()


ELLIPSIS_JS = """(sel) => { const r = document.querySelector(sel); if (!r) return ['missing'];
  const out=[]; for (const el of r.querySelectorAll('*')) { const cs=getComputedStyle(el);
  if (cs.textOverflow==='ellipsis' && el.scrollWidth>el.clientWidth+1) out.push(el.textContent.slice(0,40)); }
  return out; }"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1400, "height": 950})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', d["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/library/book-sets/{d['set']}", wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(600)
            page.click('[data-testid="open-set-apply"]')
            page.wait_for_selector('[data-testid="set-apply-row"]', timeout=15000)
            rows = page.locator('[data-testid="set-apply-row"]')
            check("1. 3 öğrenci listelendi", rows.count() == 3, str(rows.count()))
            txt = page.locator('[role="dialog"]').inner_text()
            check("2. şube başlıkları (10-A, 11-B)", "10-A" in txt and "11-B" in txt)
            check("3. 11. sınıf öğrencisine uyumsuzluk uyarısı", "sınıfı setin hedefine uymuyor" in txt)
            checked = page.locator('[data-testid="set-apply-row"] input:checked').count()
            check("4. uygun 2 öğrenci ön-seçili", checked == 2, str(checked))
            check("5. pencerede kırpma yok", page.evaluate(ELLIPSIS_JS, '[role="dialog"]') == [])
            page.screenshot(path=os.path.join(SHOT_DIR, "book_set_apply.png"))
            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(300)
            bad = measure(page, '[role="dialog"]', min_ratio=3.0)["bad"]
            check("6. koyu tema kontrastı", bad == 0, str(bad))
            page.evaluate("() => document.documentElement.classList.remove('dark')")
            page.click('[data-testid="set-apply-submit"]')
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                n = db.query(StudentBook).filter(StudentBook.student_id.in_(d["students"])).count()
            check("7. 2 öğrenci × 2 kitap = 4 atama", n == 4, str(n))
            body = page.locator("body").inner_text()
            check("8. atanmış öğrenciler bölümü yenilemesiz güncellendi",
                  "Ada Onuncu" in body and "Bora Onuncu" in body)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
