"""Eksik uygulamalı kareler (2. tur tamamlayıcı): YSA ekle/eklendi/çözdüm +
PDF önizleme + arşiv seçimi. Diyalog-KAPSAMLI seçiciler (arka plandaki eş
metinlere tıklama tuzağına düşmez).

  python -m scripts.capture_guide_shots_student3
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
from scripts.capture_guide_shots_student import (
    ensure_student_guide_dismissed,
    login_student,
)
from scripts.capture_guide_shots_student2 import HIDE_CSS, make_photo, nav, WQ_PHOTO

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "scripts" / "ornek_sonuc_karnesi.pdf"


def main() -> int:
    make_photo()
    ensure_student_guide_dismissed()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        ctx.add_init_script(HIDE_CSS)
        page = ctx.new_page()
        page.route("**/me/panel-visits", lambda r: r.abort())
        login_student(page)

        # ---------- YSA: ekle formu doldur → gerçek ekle → çözdüm ----------
        nav(page, "/student/wrong-questions", "Yanlış")
        page.get_by_text("Yanlış ekle", exact=False).first.click()
        time.sleep(1.2)
        dlg = page.locator('[role="dialog"]').last
        dlg.locator('input[type="file"]').first.set_input_files(str(WQ_PHOTO))
        time.sleep(0.8)
        dlg.get_by_text("Kitabımdan", exact=True).first.click()
        time.sleep(1.0)
        book_sel = dlg.locator("select").first
        for _ in range(20):
            val = book_sel.evaluate(
                "el => { for (const o of el.options) if (o.text.includes('3D LGS')) return o.value; return null; }"
            )
            if val:
                book_sel.select_option(val)
                break
            time.sleep(0.5)
        time.sleep(1.0)
        sec_sel = dlg.locator("select").nth(1)
        for _ in range(20):
            sval = sec_sel.evaluate(
                "el => { for (const o of el.options) if (o.text.includes('Doğrusal Denklemler')) return o.value; return null; }"
            )
            if sval:
                sec_sel.select_option(sval)
                break
            time.sleep(0.5)
        time.sleep(0.5)
        dlg.get_by_text("İşlem hatası", exact=False).first.click()
        dlg.locator("textarea").last.fill(
            "Eksili terimi karşıya taşırken işaretini değiştirmeyi unuttum."
        )
        time.sleep(0.4)
        ekle = dlg.get_by_text("Arşive ekle", exact=False).first
        cgs.snap(page, "ogr-yanlis-doldur", {"arsive-ekle": ekle}, settle=0.5)
        ekle.click()
        time.sleep(3.0)
        yeni = page.get_by_text("Doğrusal Denklemler", exact=False).first
        try:
            kart = yeni.locator("xpath=ancestor::button[1]")
            box = {"yeni-kart": kart} if kart.count() else {}
        except Exception:  # noqa: BLE001
            box = {}
        cgs.snap(page, "ogr-yanlis-eklendi", box, settle=1.0)

        # yeniden çözme → Çözdüm → sıradaki soru
        for label in ("Çözmeye başla", "Kendini dene"):
            btn = page.get_by_text(label, exact=False)
            if btn.count() > 0:
                btn.first.click()
                break
        time.sleep(1.6)
        rdlg = page.locator('[role="dialog"]').last
        rdlg.get_by_text("Çözdüm", exact=True).first.click()
        time.sleep(2.0)
        cgs.snap(page, "ogr-coz-sonuc", settle=0.8)
        page.keyboard.press("Escape")
        time.sleep(0.8)

        # ---------- DENEME: gerçek analiz → önizleme ----------
        nav(page, "/student/exams", "kapanırsa")
        page.get_by_text("PDF'ten aktar", exact=False).first.click()
        time.sleep(1.2)
        idlg = page.locator('[role="dialog"]').last
        idlg.locator('input[type="file"]').first.set_input_files(str(PDF))
        time.sleep(2.5)
        cgs.snap(page, "ogr-pdf-okunuyor", settle=0.5)
        idlg.locator('input[aria-label="Deneme adı"]').wait_for(timeout=180_000)
        time.sleep(1.5)
        cgs.snap(page, "ogr-pdf-onizleme", settle=1.0)
        idlg.get_by_text("Vazgeç", exact=False).first.click()
        time.sleep(1.5)

        # ---------- arşive soru seçimi ----------
        arsiv = page.locator('[aria-label="Yanlışlardan arşive soru seç"]').first
        arsiv.scroll_into_view_if_needed()
        time.sleep(0.5)
        arsiv.click()
        time.sleep(1.8)
        adlg = page.locator('[role="dialog"]').last
        boxes = adlg.locator('input[type="checkbox"]')
        for i in range(min(2, boxes.count())):
            boxes.nth(i).check()
            time.sleep(0.3)
        gonder = adlg.get_by_text("Seçilenleri arşive ekle", exact=False).first
        cgs.snap(page, "ogr-arsiv-sec", {"arsiv-gonder": gonder}, settle=0.8)
        page.keyboard.press("Escape")
        browser.close()

    existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nshot-boxes.json güncellendi ({len(cgs.boxes_out)} sahne).")
    WQ_PHOTO.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
