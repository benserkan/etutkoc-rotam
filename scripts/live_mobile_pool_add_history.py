"""Canlı MOBİL (Expo web 390px + gerçek backend) — öğrenci eşleşmeli kalem ekleme + Program geçmişim (2026-10-22).

Önkoşul: backend :8081 (CORS'ta http://localhost:8095) + Expo web :8095 (EXPO_PUBLIC_API_BASE=http://localhost:8081).
    PYTHONPATH=. python scripts/live_mobile_pool_add_history.py
"""
from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import scripts.live_student_pool_add_linked as base  # noqa: E402

BASE = "http://localhost:8095"


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = base.ids
    ids.update(base.seed())
    check = base.check
    print(f"\n=== Mobil — eşleşmeli kalem + program geçmişi ({base.PFX}) ===\n")
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            page = br.new_context(viewport={"width": 390, "height": 844}).new_page()
            page.goto(f"{BASE}/login", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            inputs = page.locator("input")
            inputs.nth(0).fill(ids["email"])
            inputs.nth(1).fill(base.PWD)
            page.get_by_text("Giriş yap", exact=True).last.click()
            page.wait_for_timeout(8000)

            def open_sheet():
                page.goto(f"{BASE}/student-pool", wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                page.get_by_text("Kalem ekle").first.click(force=True)
                page.wait_for_timeout(1500)
                page.get_by_text(ids["subj"]).last.click(force=True)
                page.wait_for_timeout(1500)

            # A) müfredat konusundan
            open_sheet()
            body = page.inner_text("body")
            check("A1 sayfa: Kitabımdan (1) + Müfredat konusu", "Kitabımdan (1)" in body and "Müfredat konusu" in body, body[:400])
            page.get_by_text("Müfredat konusu", exact=True).click(force=True)
            page.wait_for_timeout(2000)
            page.get_by_text("Üslü Sayılar", exact=True).last.click(force=True)
            page.wait_for_timeout(600)
            page.get_by_text("3", exact=True).last.click(force=True)
            page.wait_for_timeout(400)
            body = page.inner_text("body")
            check("A2 önizleme 'müfredata bağlı' + 3 test", "müfredata bağlı" in body and "3 test" in body, body[-500:])
            page.screenshot(path=os.path.join(ROOT, ".shots", "mobile_pool_add_topic.png"))
            page.get_by_text("Havuza ekle", exact=True).last.click(force=True)
            page.wait_for_timeout(4000)
            it = base.items()
            check("A3 kalem konuya bağlı, onay bekliyor", len(it) == 1 and it[0][0] == ids["t1"] and it[0][5] == "bekliyor", it)

            # B) kitabımdan
            open_sheet()
            page.get_by_text("Köklü Sayılar Testleri", exact=True).last.click(force=True)
            page.wait_for_timeout(600)
            page.get_by_text("2", exact=True).last.click(force=True)
            page.wait_for_timeout(400)
            check("B1 önizleme 'kitaba bağlı'", "kitaba bağlı" in page.inner_text("body"))
            page.get_by_text("Havuza ekle", exact=True).last.click(force=True)
            page.wait_for_timeout(4000)
            it = base.items()
            check("B2 kalem kitap + bölüm bağlı", len(it) == 2 and it[1][2] == ids["s1"] and it[1][4] == 2, it)

            # C) Program geçmişim
            page.goto(f"{BASE}/program-history", wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            body = page.inner_text("body")
            check("C1 Program geçmişim: şu an havuz + açık dönem", "Program geçmişim" in body and "Açık dönem" in body
                  and "Haftalık" in body, body[:500])
            page.screenshot(path=os.path.join(ROOT, ".shots", "mobile_program_history.png"))
            br.close()
    finally:
        base.cleanup()
    print(f"\n{base.passed} passed · {len(base.failed)} failed")
    return 1 if base.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
