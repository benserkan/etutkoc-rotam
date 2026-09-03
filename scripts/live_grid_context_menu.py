"""Hafta Izgarası sağ tık menüsü — CANLI E2E (dev sunucu + Playwright).

Koç isteği (2026-09-03): ızgarada bir göreve sağ tıklayıp taşı / kopyala /
sil yapabilmek. Sürükle-bırakın fare dostu alternatifi.

Neyi korur (gerçek bug'lar):
  - Menü öğeleri onClick ile yazılırsa ÇALIŞMAZ: dışarı-tıklama dinleyicisi
    'mousedown'da menüyü kapatıyor, buton unmount olduğu için click hiç
    tetiklenmiyor. Bu yüzden menü öğeleri onMouseDown kullanır.
  - Taşıma kopya üretmemeli (toplam görev sabit), kopyalama +1 üretmeli,
    silme -1 üretmeli.

Ön koşul: backend :8081 + Next :3000 ayakta olmalı.
Kullanım: PYTHONPATH=. python scripts/live_grid_context_menu.py
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
PFX = f"ctxm_{secrets.token_hex(3)}"
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
    monday = today - timedelta(days=today.weekday())
    with SessionLocal() as db:
        coach = User(
            email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
            full_name="Ctx Menu Koç", role=UserRole.TEACHER, is_active=True,
        )
        db.add(coach)
        db.flush()
        student = User(
            email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
            full_name="Ctx Menu Öğrenci", role=UserRole.STUDENT, is_active=True,
            teacher_id=coach.id, grade_level=11,
        )
        db.add(student)
        db.flush()
        subj = Subject(name=f"Ctx Ders {PFX}", teacher_id=coach.id)
        db.add(subj)
        db.flush()
        book = Book(
            name=f"Ctx Kitap {PFX}", subject_id=subj.id, teacher_id=coach.id,
            type=BookType.SORU_BANKASI,
        )
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Bölüm 1", test_count=20, order=1)
        db.add(sec)
        db.flush()
        db.add(StudentBook(student_id=student.id, book_id=book.id))
        # Hafta başına 3 görev (ızgarada satır olsun)
        for i in range(3):
            t = Task(
                student_id=student.id, date=monday + timedelta(days=i),
                type=TaskType.TEST, title="Ctx görev", status=TaskStatus.PENDING,
                is_draft=False,
            )
            db.add(t)
            db.flush()
            db.add(TaskBookItem(
                task_id=t.id, book_id=book.id, book_section_id=sec.id,
                planned_count=2, completed_count=0,
            ))
        db.commit()
        return {"coach_id": coach.id, "student_id": student.id,
                "email": coach.email, "book_id": book.id, "subject_id": subj.id}


def cleanup(s: dict) -> None:
    with SessionLocal() as db:
        tids = [t.id for t in db.query(Task).filter(Task.student_id == s["student_id"]).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == s["student_id"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == s["student_id"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == s["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == s["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == s["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_([s["coach_id"], s["student_id"]])))
        db.commit()


def task_total(student_id: int) -> int:
    with SessionLocal() as db:
        return db.query(Task).filter(Task.student_id == student_id).count()


def task_dates(student_id: int) -> dict[int, str]:
    """{task_id: tarih} — taşımanın GERÇEKTEN tarih değiştirdiğini kanıtlar."""
    with SessionLocal() as db:
        return {
            t.id: t.date.isoformat()
            for t in db.query(Task).filter(Task.student_id == student_id).all()
        }


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright yok — atlanıyor (pip install playwright).")
        return 0

    s = seed()
    sid = s["student_id"]
    print(f"\n=== Izgara sağ tık menüsü E2E (öğrenci #{sid}) ===\n")
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', s["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(3500)   # login TAM SAYFA geçiş yapar
            pg.goto(f"{BASE}/teacher/students/{sid}/week", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            try:
                pg.get_by_role("button", name="Daha sonra").click(timeout=2500)
                pg.wait_for_timeout(400)
            except Exception:
                pass

            grid = pg.locator("section").filter(has_text="Hafta Izgarası").first
            row = grid.locator("li[draggable='true']").first
            row.scroll_into_view_if_needed()

            # 1. sağ tık → menü
            row.click(button="right")
            pg.wait_for_timeout(600)
            chk("1. sağ tık → menü açıldı",
                pg.get_by_role("button", name="Başka güne taşı").count() > 0)

            # 2-3. kopyala
            before = task_total(sid)
            pg.get_by_role("button", name="Başka güne kopyala").first.click()
            pg.wait_for_timeout(500)
            chk("2. 'Kopyala' → hedef seçme bandı",
                pg.get_by_role("button", name="Vazgeç (ESC)").count() > 0)
            # NOT: has_text="Pazar" Pazartesi'yi de yakalar (substring) →
            # geçmiş güne düşüp işlem reddediliyordu. title ile kesin seçim.
            tgt = grid.locator('button[title*="Cumartesi"]').first
            tgt.click()
            pg.wait_for_timeout(2500)
            after = task_total(sid)
            chk("3. hedef güne kopyalandı (+1 görev)", after == before + 1,
                f"önce={before} sonra={after}")

            # 4-5. taşı
            before2 = task_total(sid)
            dates_before = task_dates(sid)
            row = grid.locator("li[draggable='true']").first
            row.click(button="right")
            pg.wait_for_timeout(500)
            pg.get_by_role("button", name="Başka güne taşı").first.click()
            pg.wait_for_timeout(400)
            chk("4. 'Taşı' → hedef seçme bandı",
                pg.get_by_role("button", name="Vazgeç (ESC)").count() > 0)
            grid.locator('button[title*="Pazar —"]').first.click()
            pg.wait_for_timeout(2500)
            after2 = task_total(sid)
            dates_after = task_dates(sid)
            moved = [
                tid for tid, d in dates_after.items()
                if tid in dates_before and dates_before[tid] != d
            ]
            sunday = (date.today() - timedelta(days=date.today().weekday())
                      + timedelta(days=6)).isoformat()
            chk("5. taşıma: toplam sabit AMA görevin tarihi hedefe değişti",
                after2 == before2 and len(moved) == 1
                and dates_after[moved[0]] == sunday,
                f"toplam {before2}->{after2} taşınan={moved} hedef={sunday}")

            # 6-7. sil
            before3 = task_total(sid)
            row = grid.locator("li[draggable='true']").first
            row.click(button="right")
            pg.wait_for_timeout(500)
            pg.get_by_role("button", name="Görevi sil").first.click()
            pg.wait_for_timeout(500)
            chk("6. 'Sil' → onay dialogu (kapasite iadesi uyarısı)",
                pg.get_by_text("Kitaptan ayrılan test kapasitesi", exact=False).count() > 0)
            pg.locator("div.fixed.inset-0").get_by_role(
                "button", name="Sil", exact=True).click()
            pg.wait_for_timeout(2500)
            after3 = task_total(sid)
            chk("7. silindi (-1 görev)", after3 == before3 - 1,
                f"önce={before3} sonra={after3}")

            b.close()
    finally:
        cleanup(s)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===\n")
    if failed:
        for f in failed:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
