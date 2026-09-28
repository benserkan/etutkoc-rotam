"""Kütüphane (yeni tasarım) — canlı tarayıcı testi (2026-09-28).

Kendi verisini kurar/temizler: koç + 4 kitap (TYT Matematik: eksik eşleşmeli
soru bankası [öğrencide] · deneme · ünitesiz kitap; LGS Matematik: tam
eşleşmeli). Dev sunucular (:3000 + :8081) açık olmalı.
Ekran görüntüleri .shots/library_*.png
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Book, BookSection, BookType, Subject, Topic, User, UserRole
from app.models.progress import StudentBook
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"llb_{secrets.token_hex(3)}"
PWD = "LiveLibrary!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
LONG_NAME = "Orijinal Yayınları TYT Matematik Soru Bankası Tamamı Video Çözümlü Yeni Nesil"
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        tyt = db.query(Subject).filter(Subject.name == "TYT Matematik",
                                       Subject.teacher_id.is_(None)).first()
        lgs = db.query(Subject).filter(Subject.name == "Matematik",
                                       Subject.curriculum_model == "lgs",
                                       Subject.teacher_id.is_(None)).first()
        assert tyt and lgs, "yerleşik dersler yok"
        tyt_topics = db.query(Topic).filter(Topic.subject_id == tyt.id).order_by(Topic.order).limit(3).all()
        lgs_topics = db.query(Topic).filter(Topic.subject_id == lgs.id).order_by(Topic.order).limit(2).all()
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Kütüphane Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                   full_name="Kitap Öğrenci", role=UserRole.STUDENT, teacher_id=coach.id,
                   grade_level=12, is_active=True, created_at=now - timedelta(days=30))
        db.add(stu)
        db.flush()

        def book(name, subj, btype, secs, mapped_topics, grade=None):
            b = Book(teacher_id=coach.id, subject_id=subj.id, name=name, type=btype,
                     publisher="Test Yayın", target_grade_min=grade, target_grade_max=grade)
            db.add(b)
            db.flush()
            for i in range(secs):
                db.add(BookSection(book_id=b.id, label=f"Ünite {i+1}", test_count=5, order=i,
                                   topic_id=mapped_topics[i].id if i < len(mapped_topics) else None))
            return b

        b1 = book(LONG_NAME, tyt, BookType.SORU_BANKASI, 3, tyt_topics[:2], 12)
        book("TYT Mat Deneme Seti", tyt, BookType.BRANS_DENEMESI, 2, [])
        book("Boş Fasikül", tyt, BookType.FASIKUL, 0, [])
        book("LGS Matematik Kazanım", lgs, BookType.SORU_BANKASI, 2, lgs_topics, 8)
        db.flush()
        db.add(StudentBook(student_id=stu.id, book_id=b1.id))
        db.commit()
        return {"coach": coach.id, "stu": stu.id, "email": coach.email}


def cleanup(d):
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(Book.id).filter(Book.teacher_id == d["coach"]).all()]
        if ids:
            db.execute(sa_delete(StudentBook).where(StudentBook.book_id.in_(ids)))
            db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids)))
            db.execute(sa_delete(Book).where(Book.id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_([d["stu"], d["coach"]])))
        db.commit()


def no_overflow(pg) -> bool:
    return not pg.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")


def truncated(pg, sel) -> list[str]:
    return pg.evaluate(f"""() => [...document.querySelectorAll('{sel} *')].filter(e =>
        e.children.length === 0 && e.textContent.trim() &&
        (getComputedStyle(e).textOverflow === 'ellipsis' || e.scrollWidth > e.clientWidth + 1) &&
        getComputedStyle(e).overflow !== 'visible').map(e => e.textContent.trim()).slice(0, 5)""")


def cards(pg) -> int:
    return pg.locator('[data-testid="book-card"]').count()


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_context(viewport={"width": 1400, "height": 1000}).new_page()
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)

            api = pg.request.get(f"{BASE}/api/v2/teacher/library/books").json()
            by = {i["name"]: i for i in api["items"]}
            chk("1 API: eşleşme sayısı 2/3", by[LONG_NAME].get("mapped_section_count") == 2,
                str(by[LONG_NAME]))
            chk("2 API: aktif öğrenci 1", by[LONG_NAME].get("active_student_count") == 1)

            pg.goto(f"{BASE}/teacher/library", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(400)
            chk("3 varsayılan müfredat LGS → 1 kart", cards(pg) == 1, str(cards(pg)))
            pg.click('[data-testid="curriculum-exam"]')
            pg.wait_for_timeout(1500)
            chk("4 Sınav müfredatı → 3 kart", cards(pg) == 3, str(cards(pg)))
            stats = pg.locator('[data-testid="library-stats"]').inner_text()
            chk("5 durum kartları: 3 kitap · 1 kullanılıyor · 2 atanmamış · 2 eksik",
                all(x in stats for x in ["3", "1", "2"]) and "eksiği var" in stats, stats)
            chk("5b deneme teste katılmaz: 15 test · 10 deneme", "15 test · 10 deneme" in stats, stats)
            pg.screenshot(path=os.path.join(SHOT_DIR, "library_grid.png"), full_page=True)
            chk("6 uzun kitap adı kırpılmadan tam görünür",
                pg.get_by_text(LONG_NAME, exact=True).count() == 1
                and not truncated(pg, '[data-testid="book-card"]'),
                str(truncated(pg, '[data-testid="book-card"]')))
            txt = pg.locator('[data-testid="book-card"]').all_inner_texts()
            joined = " ".join(txt)
            chk("7 eksik uyarıları: ünitesiz + 1 ünite bağlı değil",
                "Ünite eklenmemiş" in joined and "1 ünite müfredata bağlı değil" in joined)
            chk("8 deneme kartında 'Deneme' etiketi, eşleşme barı yok",
                any("Deneme" in t and "Müfredata bağlı" not in t for t in txt if "Deneme Seti" in t))

            pg.click('[data-testid="stat-attention"]')
            pg.wait_for_timeout(1500)
            chk("9 'eksiği olanlar' süzgeci → 2 kart", cards(pg) == 2, str(cards(pg)))
            chk("10 aktif filtre çipi görünür", pg.get_by_text("Eksiği olanlar").count() >= 1)
            pg.get_by_role("button", name="Tümünü temizle").click()
            pg.wait_for_timeout(1500)
            chk("11 temizle → 3 kart", cards(pg) == 3, str(cards(pg)))

            pg.select_option('[data-testid="filter-type"]', "soru_bankasi")
            pg.wait_for_timeout(1800)
            chk("12 tür süzgeci (soru bankası) → 1 kart", cards(pg) == 1, str(cards(pg)))
            pg.select_option('[data-testid="filter-type"]', "")
            pg.wait_for_timeout(1500)
            pg.fill('[data-testid="library-search"]', "Deneme Seti")
            pg.wait_for_timeout(2000)
            chk("13 arama → 1 kart", cards(pg) == 1, str(cards(pg)))
            pg.fill('[data-testid="library-search"]', "")
            pg.wait_for_timeout(2000)

            pg.click('[data-testid="view-list"]')
            pg.wait_for_timeout(1500)
            chk("14 liste görünümü → 3 satır",
                pg.locator('[data-testid="book-row"]').count() == 3)
            pg.screenshot(path=os.path.join(SHOT_DIR, "library_list.png"), full_page=True)
            pg.select_option('[data-testid="filter-sort"]', "students")
            pg.wait_for_timeout(1500)
            first = pg.locator('[data-testid="book-row"]').first.inner_text()
            chk("16 sıralama → öğrencide kullanılan ilk satırda", LONG_NAME in first, first[:80])
            chk("17 masaüstü yatay taşma yok", no_overflow(pg))

            pg.goto(f"{BASE}/teacher/library?curriculum=exam", wait_until="networkidle")
            pg.wait_for_timeout(1500)
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(400)
            m1 = measure(pg, '[data-testid="library-stats"]', min_ratio=3.0)
            m2 = measure(pg, '[data-testid="book-card"]', min_ratio=3.0)
            chk("18 koyu tema kontrast", m1["bad"] + m2["bad"] == 0,
                str(m1["worst"][:3] + m2["worst"][:3]))
            pg.screenshot(path=os.path.join(SHOT_DIR, "library_dark.png"), full_page=True)
            pg.evaluate("() => document.documentElement.classList.remove('dark')")

            pg.set_viewport_size({"width": 390, "height": 844})
            pg.wait_for_timeout(700)
            chk("19 390px yatay taşma yok", no_overflow(pg))
            chk("20 390px kart metni kırpılmıyor",
                not truncated(pg, '[data-testid="book-card"]'),
                str(truncated(pg, '[data-testid="book-card"]')))
            chk("21 390px sekmeler kırpılmıyor", not truncated(pg, 'nav[aria-label="Kütüphane bölümleri"]')
                and no_overflow(pg))
            pg.screenshot(path=os.path.join(SHOT_DIR, "library_390.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
