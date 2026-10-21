"""Canlı tarayıcı — öğrenci Gelişim sayfası + Bugün özeti + yazdır menüsü + paylaş/PDF + deneme vurgusu (2026-10-21).

Demo öğrenci (#459, seed_weekly_progress_demo). Dev :3000 + :8081 açık olmalı.
Çalıştır: python scripts/live_student_progress.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402

WEB = "http://localhost:3000"
EMAIL, PWD = "ornek-haftalik@lgs.local", "OrnekHafta2026!"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
os.makedirs(SHOTS, exist_ok=True)
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({str(detail)[:300]})")


def dismiss(page):
    for txt in ("Daha sonra",):
        try:
            b = page.get_by_role("button", name=txt)
            if b.count() and b.first.is_visible():
                b.first.click()
                page.wait_for_timeout(400)
        except Exception:
            pass


def overflow(page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def main() -> int:
    get_login_limiter().reset()
    with SessionLocal() as db:
        row = (db.query(Task.date).join(TaskBookItem, TaskBookItem.task_id == Task.id)
               .filter(Task.student_id == 459, TaskBookItem.exam_kind.isnot(None))
               .order_by(Task.date.desc()).first())
        deneme_day = row[0].isoformat() if row else None
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context(viewport={"width": 1440, "height": 950}, accept_downloads=True)
        page = ctx.new_page()
        errs: list[str] = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.goto(f"{WEB}/login", wait_until="networkidle")
        page.fill('input[type="email"]', EMAIL)
        page.fill('input[type="password"]', PWD)
        page.click('button[type="submit"]')
        page.wait_for_timeout(3500)

        # 1 Bugün özeti
        page.goto(f"{WEB}/student/day", wait_until="networkidle")
        page.wait_for_timeout(1500)
        dismiss(page)
        card = page.locator('[data-section="student:progress-summary"]')
        check("1a Bugün'de sınava hazırlık özeti", card.count() == 1, card.count())
        txt = card.inner_text() if card.count() else ""
        check("1b özet: kalan gün + görev + tempo + bu gidişle", all(k in txt for k in ("gün", "görev", "tempo", "Bu gidişle")), txt[:200])
        page.screenshot(path=os.path.join(SHOTS, "student_day_summary.png"))
        nav = page.locator("header").first.inner_text()
        check("1c menüde Gelişim sekmesi", "Gelişim" in nav, nav[:200])

        # 2 Gelişim sayfası
        page.locator('[data-testid="progress-summary-link"]').click()
        page.wait_for_url("**/student/progress", timeout=10000)
        page.wait_for_selector('[data-section="progress:hero"]', timeout=15000)
        page.wait_for_timeout(1500)
        secs = [s for s in ("hero", "week", "rhythm", "subjects", "exams", "weak", "deep")
                if page.locator(f'[data-section="progress:{s}"]').count() == 1]
        check("2a Gelişim bölümleri (hero/hafta/ritim/dersler/denemeler/konular/derine)", len(secs) >= 6, secs)
        check("2b yatay taşma yok (1440)", overflow(page) <= 0, overflow(page))
        page.screenshot(path=os.path.join(SHOTS, "student_progress_light.png"), full_page=True)
        page.emulate_media(color_scheme="dark")
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(SHOTS, "student_progress_dark.png"), full_page=True)
        page.emulate_media(color_scheme="light")
        page.set_viewport_size({"width": 390, "height": 900})
        page.wait_for_timeout(600)
        check("2c 390px taşma yok", overflow(page) <= 0, overflow(page))
        page.screenshot(path=os.path.join(SHOTS, "student_progress_mobile.png"), full_page=True)
        page.set_viewport_size({"width": 1440, "height": 950})

        # 3 Yazdır menüsü
        page.goto(f"{WEB}/student/week", wait_until="networkidle")
        page.wait_for_timeout(1000)
        dismiss(page)
        page.get_by_role("button", name="Yazdır").click()
        menu = page.locator('[role="menu"]').inner_text()
        check("3a menü: Günü / Haftayı / Deneme sonuçlarını yazdır",
              all(k in menu for k in ("Günü yazdır", "Haftayı yazdır", "Deneme sonuçlarını yazdır")), menu)
        check("3b 'Veli raporu' yok", "Veli" not in menu, menu)
        page.keyboard.press("Escape")
        for path, needle in (("/student/day/print", "Günün Programı"), ("/student/exams/print", "Deneme Sonuçlarım")):
            pg = ctx.new_page()
            r = pg.goto(f"{WEB}{path}", wait_until="networkidle")
            check(f"3c {path} açılır", r is not None and r.status == 200 and needle in pg.inner_text("main"),
                  r.status if r else None)
            pg.screenshot(path=os.path.join(SHOTS, f"print_{path.split('/')[2]}.png"), full_page=True)
            pg.close()

        # 4 Paylaş → PDF
        page.locator('[data-testid="share-program"]').click()
        page.wait_for_selector('[data-testid="share-download"]', timeout=40000)
        check("4a PDF hazırlandı (WhatsApp + indir düğmeleri)", page.locator('[data-testid="share-whatsapp"]').count() == 1)
        with page.expect_download(timeout=15000) as dl:
            page.locator('[data-testid="share-download"]').click()
        fpath = dl.value.path()
        head = open(fpath, "rb").read(5) if fpath else b""
        size = os.path.getsize(fpath) if fpath else 0
        check("4b indirilen dosya gerçek PDF", head == b"%PDF-" and size > 20_000, (head, size))
        page.screenshot(path=os.path.join(SHOTS, "student_share_dialog.png"))
        page.keyboard.press("Escape")

        # 5 Deneme vurgusu
        if deneme_day:
            page.goto(f"{WEB}/student/day?date={deneme_day}", wait_until="networkidle")
            page.wait_for_timeout(1200)
            dismiss(page)
            d = page.locator("article[data-deneme]")
            check("5a deneme görevi vurgulu kart", d.count() >= 1, d.count())
            t = d.first.inner_text() if d.count() else ""
            check("5b 'Branş denemesi' şeridi + TEST rozeti yok", "denemesi" in t.lower() and "\nTEST\n" not in t, t[:200])
            if d.count():
                d.first.screenshot(path=os.path.join(SHOTS, "student_deneme_card.png"))
        else:
            check("5 demo öğrencide deneme görevi bulunamadı", False)

        bad = [e for e in errs if "favicon" not in e and "Hydration" not in e]
        check("6 konsol hatası yok", not bad, bad[:3])
        b.close()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
