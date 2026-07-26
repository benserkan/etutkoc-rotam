"""Öğrenci rehberi — UYGULAMALI akış kareleri (2026-07-26 kullanıcı 2. tur).

"Bu şudur" değil "bas → ne oldu gör": gerçek tıklamalarla önce/sonra kareleri.
  - Bugün: bekleyen görevi işaretle (üzeri çizilir, manşet artar) + test
    görevinde sayı/Doğru-Yanlış girme sayfası (CompleteSheet)
  - Talep: görev ⋯ menüsü → Sayıyı değiştir doldur → GERÇEK gönder →
    kartta "Bekliyor" rozeti → Taleplerim listesi
  - YSA: Yanlış ekle formunu doldur (gerçek foto + kitap/ünite + hata türü)
    → GERÇEK ekle → listede belirir → yeniden çözmede "Çözdüm" → sıradaki
  - Deneme: örnek karneyi GERÇEKTEN yükle (Gemini çift okuma, koç kredisi 6)
    → "okunuyor" → önizleme; arşive soru seçme diyaloğu (2 soru işaretli)
  - Anket: ilk soruda seçenek işaretle (ilerleme 1/32)
  - Bağımsız çalışma: diyalogda kitap+sayı dolu hali

Önkoşul: :8081 (run_dev_patched — Gemini) + :3000 + tüm student seed'ler.
  python -m scripts.capture_guide_shots_student2
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
    close_dialog,
)

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "scripts" / "ornek_sonuc_karnesi.pdf"
WQ_PHOTO = ROOT / "scripts" / "_soru_foto.png"

HIDE_CSS = """(()=>{const h=()=>{const s=document.createElement('style');
s.textContent='[class*="tsqd"],nextjs-portal{display:none!important}';
document.head&&document.head.appendChild(s);};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',h);else h();})();"""


def make_photo():
    from scripts.seed_guide_demo_student import make_question_png

    png = make_question_png([
        "Bir doğrusal denklemde 3x - 7 = 2x + 5 ise x kaçtır?",
        "A) 8&nbsp;&nbsp; B) 10&nbsp;&nbsp; C) 12&nbsp;&nbsp; D) 14",
    ])
    WQ_PHOTO.write_bytes(png)


def nav(page, path, wait=None, tries=3):
    for i in range(tries):
        try:
            cgs.goto(page, path, wait)
            return
        except Exception as e:  # noqa: BLE001
            print(f"  nav tekrar ({path}, {i + 1}): {type(e).__name__}")
            time.sleep(3.0)
    cgs.goto(page, path, wait)


def card_of(loc):
    return loc.locator("xpath=ancestor::article[1]")


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

        # ================= BUGÜN: işaretle + sayı gir =================
        nav(page, "/student/day", "Günün notu")
        header = page.locator("header").first
        video = page.get_by_text("Doğrusal denklemler konu videosu", exact=False).first
        vcard = card_of(video)
        cgs.snap(page, "ogr-bugun", {"ust-menu": header, "video-gorev": vcard}, settle=1.5)

        # işaretleme düğmesi (kartın solundaki daire)
        toggle = vcard.locator("button").first
        cgs.snap(page, "ogr-gorev-isaretle", {"isaret-dugmesi": toggle}, settle=0.5)
        toggle.click()
        time.sleep(2.0)
        cgs.snap(page, "ogr-gorev-tamam", {"tamam-gorev": vcard}, settle=1.0)

        # test görevinde sayı + D/Y girme sayfası (karekök kaleminin ayar düğmesi)
        done = page.get_by_text("Kareköklü İfadeler", exact=False).first
        dcard = card_of(done)
        done.scroll_into_view_if_needed()
        time.sleep(0.4)
        cgs.snap(page, "ogr-gorev-sonuc", {"sonuc-alani": dcard}, settle=0.6)
        try:
            dcard.locator('button[aria-label="Sonucu düzelt"], button[aria-label="Çözdüğüm sayı ve sonuç"]').first.click()
            time.sleep(1.4)
            cgs.snap(page, "ogr-dy-gir", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  D/Y sheet: {e}")

        # ================= TALEP: menü → doldur → gönder → rozet =================
        try:
            hedef = page.get_by_text("Doğrusal Denklemler: 4 test", exact=False).first
            hcard = card_of(hedef)
            hedef.scroll_into_view_if_needed()
            time.sleep(0.4)
            hcard.locator('button[aria-label="Görev eylemleri"]').first.click()
            time.sleep(0.8)
            menu = page.locator('[role="menu"]').first
            cgs.snap(page, "ogr-gorev-menu", {"gorev-menu": menu}, settle=0.5)
            page.get_by_text("Sayıyı değiştir", exact=False).first.click()
            time.sleep(1.2)
            page.locator("#comm-count").fill("2")
            page.locator("textarea").last.fill(
                "Yarın okulda matematik sınavım var; bu görevi iki teste düşürebilir miyiz?"
            )
            time.sleep(0.4)
            cgs.snap(page, "ogr-talep-doldur", settle=0.5)
            page.get_by_text("Talep gönder", exact=False).first.click()
            time.sleep(2.0)
            hedef2 = page.get_by_text("Doğrusal Denklemler: 4 test", exact=False).first
            cgs.snap(page, "ogr-talep-bekliyor", {"bekliyor-gorev": card_of(hedef2)}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  talep akışı: {e}")

        nav(page, "/student/requests", "Talep")
        cgs.snap(page, "ogr-talepler", settle=1.6)

        # ================= YSA: ekle → listede → çözdüm =================
        nav(page, "/student/wrong-questions", "Yanlış")
        try:
            page.get_by_text("Yanlış ekle", exact=False).first.click()
            time.sleep(1.2)
            page.locator('input[type="file"]').first.set_input_files(str(WQ_PHOTO))
            time.sleep(0.8)
            page.get_by_text("Kitabımdan", exact=True).first.click()
            time.sleep(0.8)
            book_sel = page.locator('select[aria-label="Kitap seç"]').first
            val = book_sel.evaluate(
                "el => { for (const o of el.options) if (o.text.includes('3D LGS')) return o.value; return null; }"
            )
            if val:
                book_sel.select_option(val)
            time.sleep(1.0)
            sec_sel = page.locator("select").nth(1)
            sval = sec_sel.evaluate(
                "el => { for (const o of el.options) if (o.text.includes('Doğrusal Denklemler')) return o.value; return null; }"
            )
            if sval:
                sec_sel.select_option(sval)
            time.sleep(0.5)
            page.get_by_text("İşlem hatası", exact=False).first.click()
            page.locator("textarea").last.fill("Eksili terimi karşıya taşırken işaretini değiştirmeyi unuttum.")
            time.sleep(0.4)
            ekle = page.get_by_text("Arşive ekle", exact=False).first
            cgs.snap(page, "ogr-yanlis-doldur", {"arsive-ekle": ekle}, settle=0.5)
            ekle.click()
            time.sleep(2.5)
            yeni = page.get_by_text("Doğrusal Denklemler", exact=False).first
            cgs.snap(page, "ogr-yanlis-eklendi", {"yeni-kart": yeni.locator(
                "xpath=ancestor::*[self::li or self::article or self::div][contains(@class,'rounded')][1]"
            )}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  yanlış ekle akışı: {e}")

        try:
            for label in ("Çözmeye başla", "Kendini dene"):
                btn = page.get_by_text(label, exact=False)
                if btn.count() > 0:
                    btn.first.click()
                    break
            time.sleep(1.5)
            page.get_by_text("Çözdüm", exact=True).first.click()
            time.sleep(2.0)
            cgs.snap(page, "ogr-coz-sonuc", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  çözdüm akışı: {e}")

        # ================= DENEME: gerçek PDF okutma + arşiv seçimi =================
        nav(page, "/student/exams", "kapanırsa")
        try:
            page.get_by_text("PDF'ten aktar", exact=False).first.click()
            time.sleep(1.2)
            page.locator('input[type="file"]').first.set_input_files(str(PDF))
            time.sleep(2.5)
            cgs.snap(page, "ogr-pdf-okunuyor", settle=0.5)
            # Gemini çift okuma ~35-60 sn
            page.get_by_text("Önizleme", exact=False).first.wait_for(timeout=180_000)
            time.sleep(1.5)
            cgs.snap(page, "ogr-pdf-onizleme", settle=1.0)
            close_dialog(page)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  pdf akışı: {e}")

        try:
            arsiv = page.locator('[aria-label="Yanlışlardan arşive soru seç"]').first
            arsiv.scroll_into_view_if_needed()
            time.sleep(0.5)
            arsiv.click()
            time.sleep(1.5)
            boxes = page.locator('input[type="checkbox"]')
            n = boxes.count()
            for i in range(min(2, n)):
                boxes.nth(i).check()
                time.sleep(0.3)
            cgs.snap(page, "ogr-arsiv-sec", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  arşiv seçimi: {e}")

        # ================= ANKET: işaretle =================
        try:
            nav(page, "/student/surveys", "Anket")
            page.locator('a[href^="/student/surveys/"]').first.click()
            page.wait_for_url("**/student/surveys/**", timeout=60_000)
            page.get_by_text("Kaydet", exact=False).first.wait_for(timeout=60_000)
            time.sleep(1.0)
            # ilk sorunun "4" düğmesi
            page.locator("button", has_text="4").first.click()
            time.sleep(1.0)
            cgs.snap(page, "ogr-anket-isaretle", settle=0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  anket işaretleme: {e}")

        # ================= BAĞIMSIZ: dolu diyalog =================
        try:
            nav(page, "/student/books", "Kitaplarım")
            page.get_by_text("Bağımsız çalışma bildir", exact=False).first.click()
            time.sleep(1.2)
            ksel = page.locator("select").first
            kval = ksel.evaluate(
                "el => { for (const o of el.options) if (o.text.includes('Fen')) return o.value; return null; }"
            )
            if kval:
                ksel.select_option(kval)
            time.sleep(1.2)
            nums = page.locator('input[type="number"]:visible')
            if nums.count() > 0:
                nums.first.fill("6")
                time.sleep(0.3)
            cgs.snap(page, "ogr-bagimsiz-dolu", settle=0.8)
            close_dialog(page)
        except Exception as e:  # noqa: BLE001
            print(f"  bağımsız dolu: {e}")

        browser.close()

    existing = {}
    if cgs.BOXES_PATH.exists():
        existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nshot-boxes.json güncellendi ({len(cgs.boxes_out)} sahne).")
    for name, st in cgs.results:
        print(f"  {st}: {name}")
    WQ_PHOTO.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
