"""Canlı MOBİL (Expo web 390px) — Gelişim sekmesi + Bugün özeti + PDF/Paylaş + deneme vurgusu (2026-10-21).

Demo öğrenci #459 (seed_weekly_progress_demo). Önkoşul: backend :8081 (CORS'ta :8095) + Expo web :8095
(EXPO_PUBLIC_API_BASE=http://localhost:8081).
Çalıştır: python scripts/live_mobile_progress.py
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

from app.services.rate_limit import get_login_limiter  # noqa: E402

BASE = "http://localhost:8095"
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


def norm(s: str) -> str:
    return s.replace("İ", "i").replace("I", "ı").lower()


def main() -> int:
    get_login_limiter().reset()
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        ctx = b.new_context(viewport={"width": 390, "height": 860})
        page = ctx.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"{BASE}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        inputs = page.locator("input")
        inputs.nth(0).fill(EMAIL)
        inputs.nth(1).fill(PWD)
        page.get_by_text("Giriş yap", exact=True).last.click(force=True)
        page.wait_for_timeout(6000)

        # 1 Bugün
        body = norm(page.inner_text("body"))
        check("1a Bugün: sınava hazırlık özeti", "sınava hazırlık" in body and "bu gidişle" in body, body[:300])
        check("1b Bugün: PDF / Paylaş düğmesi", "pdf / paylaş" in body)
        page.screenshot(path=os.path.join(SHOTS, "mobile_today_summary.png"), full_page=True)

        # 2 PDF menüsü → yeni sekmede PDF
        page.get_by_text("PDF / Paylaş", exact=True).first.click(force=True)
        page.wait_for_timeout(800)
        body = page.inner_text("body")
        check("2a PDF menüsü: gün / hafta / denemeler",
              all(k in body for k in ("Günün programı", "Haftalık program", "Deneme sonuçlarım")), body[-400:])
        page.screenshot(path=os.path.join(SHOTS, "mobile_pdf_menu.png"))
        with ctx.expect_page(timeout=15000) as np:
            page.get_by_text("Haftalık program", exact=True).first.click(force=True)
        pdf_page = np.value
        pdf_page.wait_for_load_state()
        url = pdf_page.url
        resp = ctx.request.get(url)
        check("2b haftalık program PDF olarak açılır", resp.status == 200 and resp.body()[:5] == b"%PDF-"
              and "/api/v2/pdf/" in url, (resp.status, url[:80]))
        pdf_page.close()

        # 3 Gelişim sekmesi
        page.goto(f"{BASE}/student/gelisim", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        body = norm(page.inner_text("body"))
        want = ["sınava hazırlık", "bu hafta nasıl gidiyor", "çalışma ritmim", "derslerim", "denemelerim", "net kaybettiğim konular"]
        missing = [w for w in want if w not in body]
        check("3a Gelişim: tüm bölümler", not missing, missing)
        check("3b Gelişim: eski DNA/Odak kartları da duruyor", "odak" in body and "tekrar" in body, "")
        ov = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("3c yatay taşma yok", ov <= 0, ov)
        page.screenshot(path=os.path.join(SHOTS, "mobile_gelisim.png"), full_page=True)

        # 4 Hafta: deneme etiketi + PDF
        page.goto(f"{BASE}/student/week", wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        body = norm(page.inner_text("body"))
        check("4a Hafta: PDF / Paylaş + 'N deneme' etiketi", "pdf / paylaş" in body and " deneme" in body, body[:300])
        page.screenshot(path=os.path.join(SHOTS, "mobile_week.png"), full_page=True)

        check("5 sayfa hatası yok", not errs, errs[:3])
        b.close()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
