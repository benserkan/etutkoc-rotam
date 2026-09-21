"""Koltuk ızgarasından 'çözüldü'yü geri alma — CANLI E2E (dev sunucu + Playwright).

Saha (2026-09-21, Emir · Direnç): öğrenci çözmediği 2 testi 'çözdüm' işaretlemiş,
konu geçmiş haftada kalmış; koç seansta kaynağa bakınca fark ediyor. Koç koltuk
ızgarasında yeşil koltuğa tıklayıp geri alabilmeli — ızgara SIKIŞMADAN.

Neyi korur:
  - yeşil koltuk tıklanınca şerit o bölümün ALTINDA açılır (koltuk sayısı/düzeni
    değişmez, yatay taşma yok, metin kırpılmaz)
  - '1 test geri al' → yeşil koltuk 2 → 1, görev silinmez
  - 'Bu görevin N testini geri al' birden çok koltukta görünür
  - geçmiş hafta görevi: dönen rezerv anında serbest (sarı koltuk KALMAZ)

Ön koşul: backend :8081 + Next :3000. Kullanım:
  PYTHONPATH=. python scripts/live_grid_revert.py
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

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
    User,
    UserRole,
)
from app.services.security import hash_password

BASE = "http://localhost:3000"
PFX = f"grv_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def chk(name: str, cond: bool, extra: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed.append(name)
        print(f"  [FAIL] {name}  {extra}")


def seed() -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Grv Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Grv Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=11)
        db.add(st)
        db.flush()
        subj = Subject(name=f"Grv Fizik {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(name=f"Grv Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
                    type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Direnç ve Ohm Yasası Uzun Başlık",
                          test_count=6, order=1)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        t = Task(student_id=st.id, date=today - timedelta(days=20), type=TaskType.TEST,
                 title="Direnç: 2 test", status=TaskStatus.COMPLETED, is_draft=False)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=2, completed_count=2))
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=2))
        db.commit()
        return {"coach_id": coach.id, "student_id": st.id, "book_id": book.id,
                "subject_id": subj.id, "sb_id": sb.id, "sec": sec.id, "task": t.id,
                "email": coach.email}


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        ids = [s["coach_id"], s["student_id"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(ids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id == s["sb_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == s["sb_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


GREEN = '[role="dialog"] button.bg-emerald-500'
AMBER = '[role="dialog"] a.bg-amber-400'
STRIP = '[data-section="book-grid:revert-strip"]'


def main() -> int:
    from playwright.sync_api import sync_playwright

    s = seed()
    sid = s["student_id"]
    print(f"\n=== Koltuk ızgarası geri al — canlı (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)

            pg.get_by_text("Grv Fizik", exact=False).first.click()  # ders satırını aç
            pg.wait_for_timeout(800)
            pg.click('button[aria-label="Sinema-koltuğu görünümü"]', timeout=8000)
            pg.wait_for_selector(GREEN, timeout=15000)
            chk("1. modal açıldı: 2 yeşil koltuk", pg.locator(GREEN).count() == 2,
                f"{pg.locator(GREEN).count()}")
            seats_before = pg.locator(
                '[role="dialog"] section .grid > *').count()

            pg.locator(GREEN).first.click()
            pg.wait_for_selector(STRIP, timeout=5000)
            chk("2. yeşile tıkla → şerit açıldı (sayfa DEĞİŞMEDİ)",
                "/week" in pg.url and pg.locator(STRIP).count() == 1)
            geo = pg.evaluate(
                """() => {
                  const strip = document.querySelector('[data-section="book-grid:revert-strip"]');
                  const grid = strip.parentElement.querySelector('.grid');
                  const dlg = document.querySelector('[role="dialog"]');
                  const clipped = [...strip.querySelectorAll('p,button,a')].filter(
                    e => e.scrollWidth > e.clientWidth + 1).length;
                  return {
                    below: strip.getBoundingClientRect().top >= grid.getBoundingClientRect().bottom - 1,
                    overflow: dlg.scrollWidth > dlg.clientWidth + 1,
                    clipped,
                  };
                }""")
            chk("3. şerit koltukların ALTINDA, yatay taşma yok, metin kırpılmıyor",
                geo["below"] and not geo["overflow"] and geo["clipped"] == 0, f"{geo}")
            chk("4. koltuk düzeni aynı (sıkışma yok)",
                pg.locator('[role="dialog"] section .grid > *').count() == seats_before)
            chk("5. 'Bu görevin tümünü geri al (2 test)' seçeneği de var",
                pg.locator(STRIP).get_by_text("Bu görevin tümünü").count() == 1)
            pg.screenshot(path=".shots/grid_revert_strip.png")

            pg.locator(STRIP).get_by_text("1 test geri al").click()
            pg.wait_for_timeout(2500)
            chk("6. 1 test geri alındı: yeşil 2 → 1, şerit kapandı",
                pg.locator(GREEN).count() == 1 and pg.locator(STRIP).count() == 0,
                f"yeşil={pg.locator(GREEN).count()}")
            chk("7. geçmiş hafta: sarı (rezerv) koltuk KALMADI — test atanabilir",
                pg.locator(AMBER).count() == 0, f"sarı={pg.locator(AMBER).count()}")
            with SessionLocal() as db:
                t = db.get(Task, s["task"])
                chk("8. görev SİLİNMEDİ: kısmi (1/2)",
                    t is not None and t.status == TaskStatus.PARTIAL
                    and t.book_items[0].completed_count == 1)
            b.close()
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
