"""Eksik iki rehber sahnesi: sihirbaz-eslestirme + sihirbaz-ozet + gorev-ekle.

Ana yakalayıcının (capture_guide_shots) tamamlayıcısı — yalnız eksikleri çeker.
Sihirbazda 'Elle gir' yolu izlenir (eşleştirme adımı katalogda atlandığından
adım 3 ancak bu yolla görünür).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time

from playwright.sync_api import sync_playwright

import scripts.capture_guide_shots as cgs


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        page = ctx.new_page()
        cgs.ensure_guide_dismissed()
        cgs.login(page)

        # --- sihirbaz elle-gir yolu → adım 3 (eşleştirme) + adım 4 (özet) ------
        try:
            cgs.goto(page, "/teacher/library/new", "Bilgiler")
            page.get_by_role("textbox").first.fill("Karekök LGS Türkçe Soru Bankası")
            subj = page.locator("select").first
            val = subj.evaluate(
                "el => { const o = Array.from(el.options).find(o => o.text.includes('Türkçe'));"
                " return o ? o.value : null; }"
            )
            if val:
                subj.select_option(val)
            page.get_by_role("button", name="Oluştur").first.click()
            page.get_by_text("Elle gir", exact=False).first.wait_for(timeout=60_000)
            page.get_by_text("Elle gir", exact=False).first.click()
            time.sleep(0.8)
            for label, cnt in [
                ("Sözcükte Anlam", 18), ("Cümlede Anlam", 20), ("Paragraf", 32),
                ("Yazım Kuralları", 14),
            ]:
                page.locator("#ms-label").fill(label)
                page.locator("#ms-count").fill(str(cnt))
                page.locator("#ms-label").press("Enter")
                time.sleep(0.4)
            page.get_by_role("button", name="Devam").first.click()
            time.sleep(2.0)
            cgs.snap(page, "sihirbaz-eslestirme", settle=1.5)
            page.get_by_role("button", name="Devam").first.click()
            time.sleep(2.0)
            cgs.snap(page, "sihirbaz-ozet", settle=1.5)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ sihirbaz: {e}")

        # --- gorev-ekle: kapalı gün kartını aç → formu göster -------------------
        try:
            cgs.goto(page, f"/teacher/students/{cgs.IDS['elif']}/week", "Kaynak Durumu")
            time.sleep(2.0)
            btn = page.locator("button:has-text('Yeni görev ekle'):visible")
            if btn.count() == 0:
                page.locator("details summary").first.click()
                time.sleep(1.0)
                btn = page.locator("button:has-text('Yeni görev ekle'):visible")
            first = btn.first
            first.scroll_into_view_if_needed(timeout=8_000)
            first.click()
            time.sleep(1.5)
            form = page.locator("form:visible").last
            cgs.snap(page, "gorev-ekle", {"gorev-ekle-form": form}, settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ gorev-ekle: {e}")

        browser.close()

    existing = {}
    if cgs.BOXES_PATH.exists():
        existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Kutular güncellendi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
