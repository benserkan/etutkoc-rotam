"""Programı kur derin çekim — kalanlar: öneri-ekle, periyot, blok akışı.

Düzeltme: görev formu AÇIKSA toggle'a basma (kapatıyordu); formu tip
çiplerinden tanı (chip bar'da 'Deneme' etiketi her zaman var).
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
from scripts.capture_guide_shots_program2 import fill_test_task, pick, submit_form


def task_form(page):
    """Görev formunu getir — kapalıysa aç, açıksa OLDUĞU GİBİ kullan."""
    f = page.locator("form:visible").filter(has_text="Deneme")
    if f.count() > 0:
        return f.last
    btn = page.locator("button:has-text('Yeni görev ekle'):visible")
    if btn.count() == 0:
        page.locator("details summary").first.click()
        time.sleep(1.0)
        btn = page.locator("button:has-text('Yeni görev ekle'):visible")
    btn.first.scroll_into_view_if_needed(timeout=8_000)
    btn.first.click()
    time.sleep(1.3)
    return page.locator("form:visible").filter(has_text="Deneme").last


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
        cgs.goto(page, f"/teacher/students/{cgs.IDS['elif']}/week", "Kaynak Durumu")
        time.sleep(2.5)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # A) Öneriden tekil Ekle
        try:
            oner = page.get_by_text("Öneriler", exact=False).first
            oner.scroll_into_view_if_needed(timeout=8_000)
            time.sleep(0.8)
            allbtn = page.locator("button:has-text('Ekle'):visible")
            cand = None
            for i in range(allbtn.count()):
                t = allbtn.nth(i).evaluate("el => el.textContent.trim()")
                if t == "Ekle":
                    cand = allbtn.nth(i)
                    break
            if cand is None:
                # öneri başlığına tıkla (kapalıysa aç) ve tekrar dene
                oner.click()
                time.sleep(1.2)
                allbtn = page.locator("button:has-text('Ekle'):visible")
                for i in range(allbtn.count()):
                    t = allbtn.nth(i).evaluate("el => el.textContent.trim()")
                    if t == "Ekle":
                        cand = allbtn.nth(i)
                        break
            if cand is not None:
                cand.click()
                time.sleep(3.0)
                cgs.snap(page, "oneri-eklendi", settle=1.0)
            else:
                print("  ✗ öneri Ekle yok (öneriler tükenmiş olabilir)")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ oneri: {e}")

        # B) Periyot: form + Sabah çipi + görev → gün başlığı
        try:
            form = task_form(page)
            sab = form.get_by_text("Sabah", exact=True).first
            sab.scroll_into_view_if_needed(timeout=8_000)
            chips = sab.locator("xpath=ancestor::*[1]")
            sab.click()
            time.sleep(0.6)
            fill_test_task(page, form, "Dönüşüm Geometrisi", 2)
            cgs.snap(page, "gorev-periyot", {"periyot-cipleri": chips}, settle=0.8)
            if submit_form(page, form):
                try:
                    hdrp = page.locator(
                        "xpath=//*[not(self::form)]//*[text()='Sabah']"
                    ).first
                    hdrp.scroll_into_view_if_needed(timeout=6_000)
                    cgs.snap(page, "hafta-periyot", {"periyot-baslik": hdrp}, settle=1.0)
                except Exception:
                    cgs.snap(page, "hafta-periyot", settle=1.0)
            else:
                print("  ✗ periyot submit disabled")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ periyot: {e}")

        # C) Blok: oluştur → seç + 10 → kart
        try:
            form = task_form(page)
            form.get_by_text("Blok", exact=True).first.click()
            time.sleep(1.2)
            form = page.locator("form:visible").filter(has_text="Blok").last
            name_in = page.get_by_placeholder("Blok adı — örn. Özel Ders Mat ödevi").first
            name_in.fill("Özel Ders — Matematik Ödevi")
            # blok formundaki toplam inputu (ad alanının yakınındaki number)
            tot = form.locator('input[type="number"]:visible').last
            tot.click(); tot.press("Control+a"); tot.type("40")
            time.sleep(0.5)
            cgs.snap(page, "blok-yeni", {"blok-form": form}, settle=0.8)
            subs = form.locator("button[type=submit]")
            for i in range(subs.count()):
                if not subs.nth(i).evaluate("el => el.disabled"):
                    subs.nth(i).click()
                    break
            time.sleep(2.5)
            form = page.locator("form:visible").filter(has_text="Blok").last
            sels = form.locator("select")
            bsel = None
            for i in range(sels.count()):
                if sels.nth(i).evaluate(
                    "el => Array.from(el.options).some(o => o.text.includes('Özel Ders') || o.text.includes('blok seç'))"
                ):
                    bsel = sels.nth(i)
                    break
            if bsel is not None:
                pick(bsel, "Özel Ders")
                time.sleep(0.8)
                nums = form.locator('input[type="number"]:visible')
                for i in range(nums.count()):
                    nums.nth(i).click(); nums.nth(i).press("Control+a"); nums.nth(i).type("10")
                    time.sleep(0.3)
                cgs.snap(page, "blok-gorev", {"blok-form": form}, settle=0.8)
                submit_form(page, form)
            else:
                print("  ✗ blok seçici bulunamadı")
            sb = page.get_by_text("Serbest Bloklar", exact=False).first
            sb.scroll_into_view_if_needed(timeout=8_000)
            time.sleep(1.0)
            kart = page.get_by_text("Özel Ders — Matematik Ödevi", exact=False).first.locator(
                "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
            )
            cgs.snap(page, "blok-karti", {"blok-kart": kart}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ blok: {e}")

        browser.close()

    existing = json.loads(cgs.BOXES_PATH.read_text(encoding="utf-8"))
    existing.update(cgs.boxes_out)
    cgs.BOXES_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print("Kutular güncellendi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
