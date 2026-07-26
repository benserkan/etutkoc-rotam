"""Programı kur bölümünün yeni sahneleri (detaylı senaryo, 2026-07-23).

Elif'in (dolu demo) hafta sayfasından: Yeni Program diyaloğu · Programlar
menüsü · görev tipleri (Video / Deneme) · Öneriler satırı · Kaynak Durumu
ÖNCESİ/SONRASI (öneriden "Tümünü ekle" ile gerçek değişim). `hafta` sahnesi
yeni hedef kutularıyla yeniden çekilir.
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
    week_url = f"/teacher/students/{cgs.IDS['elif']}/week"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        page = ctx.new_page()
        cgs.ensure_guide_dismissed()
        cgs.login(page)
        cgs.goto(page, week_url, "Kaynak Durumu")
        time.sleep(2.0)

        # 1) hafta — Yeni Program + Programlar kutularıyla yeniden
        try:
            cgs.snap(page, "hafta", {
                "yeni-program-btn": page.get_by_text("Yeni Program", exact=True).first,
                "programlar-btn": page.get_by_text("Programlar", exact=False).first,
            }, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ hafta: {e}")

        # 2) Yeni Program diyaloğu
        try:
            page.get_by_text("Yeni Program", exact=True).first.click()
            time.sleep(1.5)
            cgs.snap(page, "yeni-program-dialog", settle=1.0)
            page.keyboard.press("Escape")
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ yeni-program-dialog: {e}")

        # 3) Programlar menüsü
        try:
            page.get_by_text("Programlar", exact=False).first.click()
            time.sleep(1.2)
            cgs.snap(page, "programlar-menu", settle=0.8)
            page.keyboard.press("Escape")
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ programlar-menu: {e}")

        # 4) Kaynak Durumu — ÖNCE (henüz yeni görev eklemeden)
        try:
            kd = page.get_by_text("Kaynak Durumu", exact=False).first
            panel = kd.locator(
                "xpath=ancestor::*[contains(@class,'rounded') and contains(@class,'border')][1]"
            )
            cgs.snap(page, "kaynak-once", {"kaynak-panel": panel}, settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ kaynak-once: {e}")

        # 5) Görev formu tipleri: Video + Deneme (açık günde form aç)
        try:
            btn = page.locator("button:has-text('Yeni görev ekle'):visible")
            if btn.count() == 0:
                page.locator("details summary").first.click()
                time.sleep(1.0)
                btn = page.locator("button:has-text('Yeni görev ekle'):visible")
            btn.first.scroll_into_view_if_needed(timeout=8_000)
            btn.first.click()
            time.sleep(1.2)
            form = page.locator("form:visible").last
            try:
                form.get_by_text("Video", exact=True).first.click(timeout=4_000)
                time.sleep(0.8)
            except Exception:
                page.get_by_text("Video", exact=True).first.click(timeout=4_000)
                time.sleep(0.8)
            cgs.snap(page, "gorev-video", {"video-form": form}, settle=0.6)
            try:
                form.get_by_text("Deneme", exact=True).first.click(timeout=4_000)
                time.sleep(0.8)
            except Exception:
                page.get_by_text("Deneme", exact=True).first.click(timeout=4_000)
                time.sleep(0.8)
            cgs.snap(page, "gorev-deneme", {"deneme-form": form}, settle=0.6)
            # formu kapat
            page.locator("button:has-text('Yeni görev ekle'):visible").first.click()
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ gorev tipleri: {e}")

        # 6) Öneriler satırı
        try:
            oner = page.get_by_text("Öneriler", exact=False).first
            oner.scroll_into_view_if_needed(timeout=8_000)
            row = oner.locator(
                "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
            )
            cgs.snap(page, "oneriler", {"oneriler-row": row}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ oneriler: {e}")

        # 7) Tümünü ekle → Kaynak Durumu SONRASI (gerçek rezerv değişimi)
        try:
            add_all = page.locator("button:has-text('Tümünü ekle'):visible")
            if add_all.count() == 0:
                page.get_by_text("Öneriler", exact=False).first.scroll_into_view_if_needed(
                    timeout=8_000
                )
                time.sleep(0.8)
                add_all = page.locator("button:has-text('Tümünü ekle'):visible")
            add_all.first.click(timeout=8_000)
            time.sleep(3.5)
            page.keyboard.press("Home")
            time.sleep(1.2)
            kd = page.get_by_text("Kaynak Durumu", exact=False).first
            panel = kd.locator(
                "xpath=ancestor::*[contains(@class,'rounded') and contains(@class,'border')][1]"
            )
            cgs.snap(page, "kaynak-sonra", {"kaynak-panel": panel}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ kaynak-sonra: {e}")

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
