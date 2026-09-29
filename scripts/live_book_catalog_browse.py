"""Kitap sihirbazı — katalog tarayıcısı + "Kapak + içindekiler" canlı testi (2026-09-29).

Dev sunucular (:3000 + :8081, Gemini erişimli run_dev_patched) açık olmalı.
Kullanım: python -m scripts.live_book_catalog_browse [örnek.pdf] [katalog_dışı.pdf]
PDF verilmezse tarama adımları atlanır.
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
from app.models import Book, BookSection, User, UserRole
from app.services.security import hash_password
from scripts.lib_live_contrast import measure

BASE = "http://localhost:3000"
PFX = f"lbcb_{secrets.token_hex(3)}"
PWD = "LiveCatalog!234"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
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
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Katalog Tarayıcı Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_unlimited", subscription_status="active")
        db.add(coach)
        db.commit()
        return {"coach": coach.id, "email": coach.email}


def cleanup(d):
    with SessionLocal() as db:
        ids = [b.id for b in db.query(Book).filter(Book.teacher_id == d["coach"])]
        if ids:
            db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids)))
            db.execute(sa_delete(Book).where(Book.id.in_(ids)))
        db.execute(sa_delete(User).where(User.id == d["coach"]))
        db.commit()


def truncated(pg, sel: str) -> int:
    return pg.evaluate(
        """(sel) => [...document.querySelectorAll(sel + ' *')].filter(el => {
            const cs = getComputedStyle(el);
            return cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1;
        }).length""",
        sel,
    )


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    pdf_match = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    d = seed()
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(channel="chrome", headless=True)
            pg = b.new_page(viewport={"width": 1300, "height": 950})
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/library/new", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(500)

            start = pg.locator('[data-testid="start-choice"]')
            chk("0. açılışta 'Ne yapmak istiyorsun?' + 3 yol (form YOK)",
                start.count() == 1 and "Ne yapmak istiyorsun" in start.inner_text()
                and pg.locator('[data-testid^="choose-"]').count() >= 3
                and pg.locator("#cb-name").count() == 0,
                start.inner_text()[:200] if start.count() else "")
            chk("0b. seçim kartlarında kırpma yok + taşma yok",
                truncated(pg, '[data-testid="start-choice"]') == 0
                and not pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            pg.screenshot(path=os.path.join(SHOT_DIR, "book_start_choice.png"), full_page=True)
            catalog_card = pg.locator('[data-testid="choose-catalog"]')
            chk("1. 'Hazır bir kitap ekle' kartında katalog sayısı", "Katalogda" in catalog_card.inner_text(),
                catalog_card.inner_text()[:160])
            catalog_card.click()
            pg.wait_for_timeout(1500)
            rows = pg.locator('[data-testid="catalog-row"]')
            n_all = rows.count()
            chk("2. yazmadan tüm katalog listeleniyor (>20)", n_all > 20, str(n_all))
            chk("3. ders başlıkları", pg.locator('[data-testid="catalog-browse-list"] h4').count() >= 3)
            chk("4. kitap adı kırpılmıyor", truncated(pg, '[data-testid="catalog-browse-list"]') == 0)

            pg.get_by_role("group", name="Sınav grubu").get_by_role("button", name="LGS").click()
            pg.wait_for_timeout(400)
            n_lgs = rows.count()
            chk("5. LGS süzgeci listeyi daraltır", 0 < n_lgs < n_all, f"{n_lgs}/{n_all}")
            pg.get_by_label("Katalogda ara").fill("ay serisi fen")
            pg.wait_for_timeout(400)
            n_q = rows.count()
            chk("6. arama (kelime bazlı) sonuç verir", 0 < n_q < n_lgs, str(n_q))

            rows.first.locator("button[aria-expanded]").click()
            pg.wait_for_timeout(1500)
            secs = pg.locator('[data-testid="catalog-sections"] li')
            chk("7. kitaba tıklayınca bölümler + test sayıları", secs.count() >= 2
                and "test" in secs.first.inner_text(), str(secs.count()))
            pg.screenshot(path=os.path.join(SHOT_DIR, "catalog_browse.png"), full_page=False)

            ov = pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
            chk("8. yatay taşma yok", not ov)

            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(300)
            bad = measure(pg, '[data-testid="catalog-browse-list"]', min_ratio=3.0)["bad"]
            chk("9. koyu tema kontrastı (liste)", bad == 0, str(bad))
            pg.evaluate("() => document.documentElement.classList.remove('dark')")

            pg.set_viewport_size({"width": 390, "height": 850})
            pg.wait_for_timeout(500)
            ov = pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")
            chk("10. 390px taşma yok", not ov)
            pg.set_viewport_size({"width": 1300, "height": 950})

            # Süzgeçleri temizle → "Yapısını kullan" ile kitap oluştur
            pg.get_by_role("button", name="Süzgeçleri temizle").click()
            pg.wait_for_timeout(300)
            chk("11. süzgeç temizlenince tüm liste geri", rows.count() == n_all)
            pg.get_by_label("Katalogda ara").fill("ay serisi fen bilimleri soru")
            pg.wait_for_timeout(400)
            rows.first.get_by_role("button", name="Kütüphaneme ekle").click()
            pg.wait_for_timeout(3500)
            with SessionLocal() as db:
                bk = db.query(Book).filter(Book.teacher_id == d["coach"]).first()
                n_sec = db.query(BookSection).filter(BookSection.book_id == bk.id).count() if bk else 0
            chk("12. 'Kütüphaneme ekle' kitabı bölümleriyle oluşturdu", bk is not None and n_sec >= 2,
                f"sec={n_sec}")

            # elle yol: form açılır, şablon seçici YOK
            pg.goto(f"{BASE}/teacher/library/new", wait_until="networkidle")
            pg.wait_for_timeout(2000)
            pg.locator('[data-testid="choose-manual"]').click()
            pg.wait_for_timeout(800)
            chk("12c. elle yol: form açık, şablon seçici yok, 'Başka yol seç' var",
                pg.locator("#cb-name").count() == 1 and pg.locator("#cb-template").count() == 0
                and pg.get_by_role("button", name="Başka yol seç").count() == 1)
            pg.get_by_role("button", name="Başka yol seç").click()
            pg.wait_for_timeout(500)
            chk("12d. geri dönünce seçim ekranı", pg.locator('[data-testid="start-choice"]').count() == 1)
            pg.evaluate("() => document.documentElement.classList.add('dark')")
            pg.wait_for_timeout(300)
            bad = measure(pg, '[data-testid="start-choice"]', min_ratio=3.0)["bad"]
            chk("12e. koyu tema kontrastı (seçim kartları)", bad == 0, str(bad))
            pg.screenshot(path=os.path.join(SHOT_DIR, "book_start_choice_dark.png"), full_page=True)
            pg.evaluate("() => document.documentElement.classList.remove('dark')")
            pg.set_viewport_size({"width": 390, "height": 850})
            pg.wait_for_timeout(400)
            chk("12f. 390px seçim ekranı taşmıyor",
                not pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            pg.screenshot(path=os.path.join(SHOT_DIR, "book_start_choice_mobile.png"), full_page=True)
            pg.set_viewport_size({"width": 1300, "height": 950})

            if pdf_match and os.path.exists(pdf_match):
                pg.goto(f"{BASE}/teacher/library/new", wait_until="networkidle")
                pg.wait_for_timeout(2500)
                pg.locator('[data-testid="choose-scan"]').click()
                pg.wait_for_timeout(800)
                chk("12b. tarat yolu: yükleme alanı + form henüz YOK",
                    pg.locator('[data-testid="scan-button"]').count() == 1 and pg.locator("#cb-name").count() == 0)
                pg.locator('[data-testid="scan-input"]').set_input_files(pdf_match)
                pg.wait_for_selector('[data-testid="scan-outcome"]', timeout=180_000)
                pg.wait_for_timeout(800)
                out = pg.locator('[data-testid="scan-outcome"]').inner_text()
                print("     tarama sonucu:", out.replace("\n", " | ")[:300])
                matched = pg.locator('[data-testid="scan-outcome"] [data-testid="catalog-row"]').count()
                chk("13. PDF taraması: kitap tanındı + katalog kaydı ya da okuma", matched > 0
                    or pg.locator('[data-testid="scan-read-ok"]').count() == 1, out[:200])
                pg.screenshot(path=os.path.join(SHOT_DIR, "catalog_scan.png"), full_page=True)
                force = pg.get_by_role("button", name="Bu kitap değil — içindekileri oku")
                if (matched and force.count()) or pg.locator('[data-testid="scan-read-ok"]').count():
                    if matched and force.count():
                        force.click()
                    pg.wait_for_selector('[data-testid="scan-read-ok"]', timeout=240_000)
                    name_val = pg.locator("#cb-name").input_value() \
                        if pg.locator("#cb-name").count() else ""
                    chk("14. zorla okuma → bölümler okundu + form adı dolu",
                        pg.locator('[data-testid="scan-read-ok"]').count() == 1 and bool(name_val),
                        f"name={name_val!r}")
                    pg.screenshot(path=os.path.join(SHOT_DIR, "catalog_scan_read.png"), full_page=True)
                    # ders seç → oluştur → 2. adımda taslak hazır (tekrar yükleme yok)
                    sel = pg.locator("#cb-subject") if pg.locator("#cb-subject").count() else \
                        pg.locator("select").filter(has_text="— Seç —").first
                    opts = sel.locator("option").all_inner_texts()
                    fen = next((o for o in opts if "Fen" in o), None) or opts[1]
                    sel.select_option(label=fen)
                    pg.get_by_role("button", name="Oluştur ve bölümlere geç").click()
                    pg.wait_for_timeout(4000)
                    body = pg.locator("main").inner_text()
                    chk("15. 2. adımda okunan bölümler taslak olarak hazır",
                        "bölüm okundu" in body and "kitaba ekle" in body, body[:300])
                    if "--expect-estimate" in sys.argv:
                        chk("16. tahmini rozeti + açıklama notu",
                            pg.locator('[data-testid="estimated-badge"]').count() > 0
                            and pg.locator('[data-testid="estimated-note"]').count() == 1)
                        chk("17. taslak listesinde kırpma/taşma yok",
                            not pg.evaluate("() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
                    pg.screenshot(path=os.path.join(SHOT_DIR, "catalog_scan_step2.png"), full_page=True)
            b.close()
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
