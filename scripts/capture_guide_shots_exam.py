"""Deneme PDF içe aktarma — GERÇEK uçtan uca çekim (2026-07-24).

Sentetik Karekök karnesi (scripts/ornek_sonuc_karnesi.pdf) demo koçla Elif'e
GERÇEKTEN yüklenir (Gemini çift okuma, 6 kredi): diyalog → yükleniyor →
önizleme (üst + soru tablosu) → kaydet/sonuç → yenilenen liste + Net Gelişimi
→ konu analizi (net fırsatı · ısı haritası · unutulan/gelişen).
Önkoşul: backend scripts.run_dev_patched ile açık (Gemini DNS yaması).
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
from pathlib import Path

from playwright.sync_api import sync_playwright

import scripts.capture_guide_shots as cgs

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "scripts" / "ornek_sonuc_karnesi.pdf"


def pick_opt(sel, text):
    val = sel.evaluate(
        f"el => {{ const o = Array.from(el.options).find(o => o.text.includes('{text}'));"
        " return o ? o.value : null; }"
    )
    if val is not None:
        sel.select_option(val)
    return val is not None


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        page = ctx.new_page()
        # Dev SQLite tek-yazar kilidi: uzun analiz isteğiyle ziyaret-izleyicisi
        # yazması çakışıp 500 üretiyor (prod PG'de yok) → izleyiciyi engelle.
        page.route("**/me/panel-visits", lambda r: r.abort())
        cgs.ensure_guide_dismissed()
        cgs.login(page)
        cgs.goto(page, f"/teacher/students/{cgs.IDS['elif']}", "Elif Kaya")
        page.get_by_role("tab", name="Denemeler").first.click(timeout=15_000)
        time.sleep(2.5)

        # 1) Diyalog: PDF'ten aktar → beyan seçicileri + dosya kutusu
        page.get_by_text("PDF'ten aktar", exact=False).first.click(timeout=10_000)
        time.sleep(1.5)
        dlg = page.locator('[role="dialog"]').last
        sels = dlg.locator("select")
        if sels.count() >= 2:
            pick_opt(sels.nth(0), "8. sınıf")
            time.sleep(0.6)
            pick_opt(sels.nth(1), "LGS")
            time.sleep(0.6)
        try:
            drop = dlg.get_by_text("Deneme sonuç PDF", exact=False).first
            cgs.snap(page, "deneme-pdf", {"dosya-kutusu": drop}, settle=0.8)
        except Exception:
            cgs.snap(page, "deneme-pdf", settle=0.8)

        # 2) Dosyayı ver → analiz otomatik başlar → yükleniyor karesi
        dlg.locator('input[type="file"]').set_input_files(str(PDF))
        time.sleep(2.5)
        cgs.snap(page, "aktar-yukleniyor", settle=0.5)

        # 3) Önizleme (çift okuma 1-3 dk sürebilir)
        dlg.get_by_text("Kontrol ettim, kaydet", exact=False).first.wait_for(timeout=300_000)
        time.sleep(1.5)
        cgs.snap(page, "aktar-onizleme", settle=1.0)
        try:
            row = dlg.get_by_text("Üslü", exact=False).first
            row.scroll_into_view_if_needed(timeout=8_000)
            time.sleep(0.8)
            cgs.snap(page, "aktar-tablo", settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  tablo scroll: {e}")
            cgs.snap(page, "aktar-tablo", settle=0.8)

        # 4) Kaydet → sonuç ekranı (arşiv köprüsü)
        dlg.get_by_text("Kontrol ettim, kaydet", exact=False).first.click()
        try:
            dlg.get_by_text("Kapat", exact=True).first.wait_for(timeout=120_000)
        except Exception:
            pass
        time.sleep(1.5)
        cgs.snap(page, "aktar-kayit", settle=1.0)
        dlg.get_by_text("Kapat", exact=True).first.click()
        time.sleep(3.0)

        # 5) Net Gelişimi grafiği
        try:
            trend = page.get_by_text("Net Gelişimi", exact=False).first
            trend.scroll_into_view_if_needed(timeout=10_000)
            time.sleep(1.2)
            box = trend.locator(
                "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
            )
            cgs.snap(page, "denemeler-sonuc", {"net-trend": box}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  net trend: {e}")

        # 6) Konu analizi: fırsat + ısı haritası + unutulan/gelişen
        def area(txt, name, key):
            try:
                el = page.get_by_text(txt, exact=False).first
                el.scroll_into_view_if_needed(timeout=10_000)
                time.sleep(1.0)
                box = el.locator(
                    "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
                )
                cgs.snap(page, name, {key: box}, settle=0.8)
            except Exception as e:  # noqa: BLE001
                print(f"  {name}: {e}")

        area("Net fırsatı", "analiz-firsat", "firsat-listesi")
        area("ısı haritası", "analiz-isi", "isi-tablosu")
        area("Unutulan konular", "analiz-unutulan", "unutulan-karti")

        b.close()

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
