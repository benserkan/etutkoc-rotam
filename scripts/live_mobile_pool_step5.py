"""Havuz Adım 5 — MOBİL canlı (Expo web :8095 + backend :8081), 390px.

Veli: çocuk detayında salt-okuma havuz kartı (K52) · Koç: Görüşmeler ekranında günlük
havuz listesi (K48/K50: bugünkü seans üstte, Gördüm → Geri al).
Tohum: live_pool_step5 ile aynı (import). Sistem python (playwright):
    python scripts/live_mobile_pool_step5.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import live_pool_step5 as L  # noqa: E402

BASE = "http://localhost:8095"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def norm(t: str) -> str:
    """innerText CSS uppercase uygular — Türkçe İ/I duyarlı küçültme."""
    return t.replace("İ", "i").replace("I", "ı").lower()


def _login(page, email):
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    inputs = page.locator("input")
    inputs.nth(0).fill(email)
    inputs.nth(1).fill(L.PWD)
    page.get_by_text("Giriş yap", exact=True).last.click()
    page.wait_for_timeout(8000)


def main() -> int:
    from playwright.sync_api import sync_playwright

    d = L.seed()
    L.ids.update(d)
    print(f"\n=== Havuz Adım 5 — mobil canlı ({L.PFX}) ===\n")
    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(viewport={"width": 390, "height": 844})
            page = ctx.new_page()

            # 1) veli
            _login(page, f"{L.PFX}_veli@test.invalid")
            page.get_by_text("Canlı main").first.click(force=True)
            page.wait_for_timeout(5000)
            body = page.inner_text("body")
            check("1a veli çocuk detayı: 'Haftalık görev havuzu' kartı + 2/12 birim", "haftalık görev havuzu" in norm(body) and "/12 birim" in body, body[:500].replace(chr(10), " | "))
            check("1b bugünün kabı + havuz listesi + önceki dönem %60; uyarı yok",
                  "Bugünün kabı" in body and "Önceki dönemler" in body and "%60" in body and "Acil" not in body, body[:600])
            page.screenshot(path=os.path.join(ROOT, ".shots/mobile_parent_pool.png"), full_page=True)

            # 2) koç
            ctx.clear_cookies()
            page.evaluate("localStorage.clear(); sessionStorage.clear();")
            _login(page, f"{L.PFX}_coach@test.invalid")
            page.goto(f"{BASE}/teacher-appointments", wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            body = page.inner_text("body")
            check("2a Görüşmeler: 'Bugünkü görüşme listesi · havuz' + bugün 16:00 seansı",
                  "görüşme l" in norm(body) and "· havuz" in norm(body) and "bugün seans 1" in body and "bugün 16:00" in body, body[:500].replace(chr(10), " | "))
            i_today = body.find("Canlı today")
            i_late = body.find("Canlı late")
            check("2b bugünkü seans öğrencisi üstte", 0 <= i_today < i_late, f"{i_today} {i_late}")
            check("2c geciken seans öğrencisinde ana sinyal + 'Gördüm'", "Seans" in body and "Gördüm (3 gün)" in body)
            page.get_by_text("Gördüm (3 gün)").first.click(force=True)
            page.wait_for_timeout(3000)
            body = page.inner_text("body")
            check("2d Gördüm → 'Geri al' + ertelenen 1", "Geri al" in body and "ertelenen 1" in body, body[:400])
            page.screenshot(path=os.path.join(ROOT, ".shots/mobile_pool_daily.png"), full_page=True)
            br.close()
    finally:
        L.cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
