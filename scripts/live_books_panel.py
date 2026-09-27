"""Öğrenci Kaynaklar sekmesi + Kitap ata penceresi — canlı tarayıcı testi (2026-09-27).

Kendi verisini kurar/temizler: koç + 10. sınıf öğrenci + 5 kitap (katalogdan,
şablondan, elle; iki aynı adlı; biri 11-12. sınıf; biri bölümsüz). Doğrular:
özet kartı · ders listesi · kitap kartında kaynak rozeti · ünite açılır ·
atama penceresi geniş + arama + kaynak filtresi + sınıf filtresi + aynı ad
uyarısı + bölümsüz uyarısı · seç → ata → panelde görünür · kırpma/taşma yok ·
koyu tema kontrastı · dar ekran. Dev sunucular (:3000 + :8081) açık olmalı.
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
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, User, UserRole,
)
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

WEB = "http://localhost:3000"
PFX = f"lbp_{secrets.token_hex(3)}"
PWD = "LiveBooks!234"
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
                     full_name="Canlı Kaynak Koç", role=UserRole.TEACHER, is_active=True,
                     must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Onuncu Sınıf", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=10)
        db.add(st)
        db.flush()
        subj = (db.query(Subject).filter(Subject.name == "TYT Matematik",
                                         Subject.is_builtin.is_(True)).first())

        def book(name, kind, secs, gmin=None, gmax=None):
            b = Book(name=name, subject_id=subj.id, teacher_id=coach.id, type=BookType.SORU_BANKASI,
                     source_kind=kind, target_grade_min=gmin, target_grade_max=gmax, publisher="Deneme Yayın")
            db.add(b)
            db.flush()
            out = []
            for i, n in enumerate(secs):
                s = BookSection(book_id=b.id, label=f"Uzun Adlı Ünite Başlığı Numara {i + 1} — Problemler",
                                test_count=n, order=i)
                db.add(s)
                db.flush()
                out.append(s.id)
            return b, out

        assigned, asecs = book(f"Atanmış Katalog Soru Bankası Çok Uzun Adlı {PFX}", "catalog", [10, 8, 6])
        cat, _ = book(f"Katalog Kitabı {PFX}", "catalog", [5, 5])
        own, _ = book(f"Şablon Kitabı {PFX}", "template", [4])
        dup1, _ = book(f"İkiz Kitap {PFX}", "manual", [3])
        dup2, _ = book(f"İkiz Kitap {PFX}", "manual", [])
        other, _ = book(f"On İkinci Sınıf Kitabı {PFX}", "manual", [2], 11, 12)
        sb = StudentBook(student_id=st.id, book_id=assigned.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=asecs[0],
                               reserved_count=2, completed_count=6))
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": coach.email,
                "books": [assigned.id, cat.id, own.id, dup1.id, dup2.id, other.id],
                "cat_name": cat.name, "own_name": own.name, "other_name": other.name}


def cleanup(d):
    with SessionLocal() as db:
        sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id == d["student"])]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == d["student"]))
        for bid in d["books"]:
            db.execute(sa_delete(BookSection).where(BookSection.book_id == bid))
            db.execute(sa_delete(Book).where(Book.id == bid))
        db.execute(sa_delete(User).where(User.id.in_([d["student"], d["coach"]])))
        db.commit()


OVERFLOW_JS = """(sel) => {
  const root = document.querySelector(sel); if (!root) return {missing: true};
  let clipped = [];
  for (const el of root.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1) clipped.push(el.textContent.slice(0,40));
  }
  const r = root.getBoundingClientRect();
  return {clipped, hscroll: r.right > window.innerWidth + 1 || root.scrollWidth > root.clientWidth + 1,
          width: Math.round(r.width)};
}"""


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    d = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', d["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{d['student']}#books", wait_until="networkidle")
            page.wait_for_timeout(3000)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(800)
            page.wait_for_selector('[data-section="books-panel"] [data-testid="book-card"]', timeout=20000)

            ov_text = page.locator('[data-testid="books-overview"]').inner_text()
            check("1. özet kartı: yüzde + 1 kitap + 24 test", "%25" in ov_text and "24" in ov_text, ov_text[:160])
            card = page.locator('[data-testid="book-card"]').first
            ct = card.inner_text()
            check("2. kitap kartında kaynak rozeti 'Katalogdan'", "Katalogdan" in ct, ct[:160])
            check("3. kartta sıradaki ünite + rezerv", "Sıradaki" in ct and "Programda" in ct, ct[:200])
            card.get_by_role("button", name="Üniteler (3)").click()
            page.wait_for_timeout(300)
            check("4. üniteler açılır (3 satır)", page.locator('[data-testid="book-section"]').count() == 3)
            ov = page.evaluate(OVERFLOW_JS, '[data-section="books-panel"]')
            check("5. panelde kırpma/taşma yok", not ov.get("clipped") and not ov.get("hscroll"), str(ov))
            page.screenshot(path=os.path.join(SHOT_DIR, "books_panel_light.png"), full_page=True)

            page.click('[data-testid="open-assign"]')
            dlg = page.locator('[role="dialog"]')
            dlg.wait_for(timeout=10000)
            page.wait_for_selector('[data-testid="assign-row"]', timeout=15000)
            box = dlg.bounding_box()
            check("6. atama penceresi geniş (≥900px)", box and box["width"] >= 900, str(box))
            rows_txt = " | ".join(dlg.locator('[data-testid="assign-row"]').all_inner_texts())
            check("7. zaten atalı kitap listede yok", "Atanmış Katalog" not in rows_txt)
            check("8. 11-12. sınıf kitabı varsayılan gizli", d["other_name"] not in rows_txt, rows_txt[:200])
            check("9. kaynak rozetleri görünür", "Şablondan" in rows_txt and "Elle oluşturuldu" in rows_txt)
            check("10. aynı ad uyarısı", "Aynı adla 2 kitabın var" in rows_txt)
            check("11. bölümsüz kitap uyarısı", "Bölümü yok" in rows_txt)
            dlg.get_by_label("Yalnız öğrencinin sınıfına uygun").uncheck()
            page.wait_for_timeout(200)
            rows_txt = " | ".join(dlg.locator('[data-testid="assign-row"]').all_inner_texts())
            check("12. filtre kapatınca 'Başka sınıf için' görünür",
                  d["other_name"] in rows_txt and "Başka sınıf için" in rows_txt)
            dlg.get_by_role("button", name="Şablondan", exact=True).click()
            page.wait_for_timeout(200)
            n = dlg.locator('[data-testid="assign-row"]').count()
            check("13. kaynak filtresi: yalnız şablon (1)", n == 1, str(n))
            dlg.get_by_role("button", name="Tümü", exact=True).click()
            page.fill('[data-testid="assign-search"]', "katalog kitabı")
            page.wait_for_timeout(200)
            n = dlg.locator('[data-testid="assign-row"]').count()
            check("14. arama (Türkçe büyük/küçük harf) tek sonuç", n == 1, str(n))
            ov = page.evaluate(OVERFLOW_JS, '[role="dialog"]')
            check("15. pencerede kırpma yok", not ov.get("clipped"), str(ov))
            page.screenshot(path=os.path.join(SHOT_DIR, "books_assign_dialog.png"))
            dlg.locator('[data-testid="assign-row"] input[type="checkbox"]').first.check()
            check("16. seçim çipi görünür", d["cat_name"] in dlg.locator('[data-testid="assign-selected"]').inner_text())

            page.evaluate("() => document.documentElement.classList.add('dark')")
            page.wait_for_timeout(400)
            bad = measure(page, '[role="dialog"]', min_ratio=3.0)["bad"]
            page.screenshot(path=os.path.join(SHOT_DIR, "books_assign_dialog_dark.png"))
            check("17. pencere koyu tema kontrastı", bad == 0, str(bad))

            page.click('[data-testid="assign-submit"]')
            page.wait_for_timeout(2500)
            names = " | ".join(page.locator('[data-testid="book-card"]').all_inner_texts())
            check("18. atanan kitap panelde yenilemesiz görünür", d["cat_name"] in names, names[:200])

            bad = measure(page, '[data-section="books-panel"]', min_ratio=3.0)["bad"]
            page.screenshot(path=os.path.join(SHOT_DIR, "books_panel_dark.png"), full_page=True)
            check("19. panel koyu tema kontrastı", bad == 0, str(bad))

            page.evaluate("() => document.documentElement.classList.remove('dark')")
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(600)
            ov = page.evaluate(OVERFLOW_JS, '[data-section="books-panel"]')
            page.screenshot(path=os.path.join(SHOT_DIR, "books_panel_mobile.png"), full_page=True)
            check("20. dar ekranda panel taşmıyor", not ov.get("hscroll"), str(ov))
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
