"""Canlı test — MOBİL Konu Performansı (Expo web :8095 + backend :8081, 2026-10-15).

Kurulum `live_topic_performance.seed` ile aynı (K0 zayıf %42 · K1 sonuçsuz · K2 seansta · K3 yalnız denemede).
Koç girişi → /topic-performance?source=teacher&id=… → özet kartları · sonuç uyarısı · Nerede kaybediyor ·
ders kartı açılınca zayıf konu önde. 390px ekran görüntüsü `.shots/mobile_topic_perf.png`.

  python scripts/live_mobile_topic_performance.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import live_topic_performance as base  # noqa: E402

BASE = "http://localhost:8095"
ROOT = os.path.join(os.path.dirname(__file__), "..")
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


def main() -> int:
    from playwright.sync_api import sync_playwright
    d = base.seed()
    print(f"\n=== Mobil konu performansı ({base.PFX}) ===\n")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            inputs = page.locator("input")
            inputs.nth(0).fill(d["email"])
            inputs.nth(1).fill(base.PWD)
            page.get_by_text("Giriş yap", exact=True).last.click()
            page.wait_for_timeout(8000)
            page.goto(f"{BASE}/topic-performance?source=teacher&id={d['st']}", wait_until="domcontentloaded")
            page.wait_for_timeout(7000)
            body = page.inner_text("body")
            low = body.lower()
            check("1 özet: çözülen 8 · doğruluk %42 · sonucu girilen 3/6",
                  "%42" in body and "3/6" in body and "sonucu girilen" in low, body[:500])
            check("2 uyarı: '6 testin 3 tanesinde sonuç girilmemiş'", "6 testin 3 tanesinde sonuç girilmemiş" in body)
            check("3 Nerede puan kaybediyor + zayıf konu + yalnız denemede",
                  "nerede puan kaybediyor" in low and base_k(d, "k0") in body and "yalnız denemede" in body)
            page.get_by_text(d["kim"], exact=True).last.click(force=True)
            page.wait_for_timeout(1200)
            body2 = page.inner_text("body")
            check("4 ders açılınca seans işareti '2 tanesi seansta' + 'sonuç girilmemiş'",
                  "2 tanesi seansta" in body2 and "sonuç girilmemiş" in body2)
            check("5 390px yatay taşma yok",
                  not page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth + 1"))
            os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
            page.screenshot(path=os.path.join(ROOT, ".shots", "mobile_topic_perf.png"), full_page=True)
            br.close()
    finally:
        base.cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


def base_k(d, k):
    return d[k]


if __name__ == "__main__":
    raise SystemExit(main())
