"""Programı kur — derin gösterim çekimleri (2026-07-23, kullanıcı 2. tur).

Akış çekimleri (hepsi Elif'in gerçek haftasında, mutasyonlar gerçek):
  kaynak-once (Matematik satırı AÇIK) → form doldurma (Üçgenler 4) →
  görev günde belirdi → kaynak-sonra (Üçgenler rezervi görünür) →
  stadyum modalı → Sıradaki üniteler → öneriden tekil Ekle sonucu →
  periyot çipleri + Sabah'a görev → gün periyot başlıkları →
  Serbest Blok oluşturma (Özel Ders Matematik Ödevi 40) → bloğu güne dağıtma →
  blok kartı (dağıtılan/kalan).
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


def pick(sel, text):
    val = sel.evaluate(
        "el => { const t = arguments[0]; const o = Array.from(el.options).find(o => o.text.includes(t));"
        " return o ? o.value : null; }" if False else
        f"el => {{ const o = Array.from(el.options).find(o => o.text.includes('{text}'));"
        " return o ? o.value : null; }"
    )
    if val is None:
        return False
    sel.select_option(val)
    return True


def open_task_form(page):
    btn = page.locator("button:has-text('Yeni görev ekle'):visible")
    if btn.count() == 0:
        page.locator("details summary").first.click()
        time.sleep(1.0)
        btn = page.locator("button:has-text('Yeni görev ekle'):visible")
    btn.first.scroll_into_view_if_needed(timeout=8_000)
    btn.first.click()
    time.sleep(1.3)
    return page.locator("form:visible").last


def close_task_form(page):
    page.locator("button:has-text('Yeni görev ekle'):visible").first.click()
    time.sleep(0.8)


def fill_test_task(page, form, bolum, count):
    pick(form.locator("select").nth(0), "Matematik")
    time.sleep(1.0)
    pick(form.locator("select").nth(1), "3D LGS")
    time.sleep(1.0)
    ok = pick(form.locator("select").nth(2), bolum)
    time.sleep(0.8)
    nums = form.locator('input[type="number"]:visible')
    for i in range(nums.count()):
        nums.nth(i).click()
        nums.nth(i).press("Control+a")
        nums.nth(i).type(str(count))
        time.sleep(0.4)
    return ok


def submit_form(page, form) -> bool:
    sub = form.locator("button[type=submit]").first
    if sub.evaluate("el => el.disabled"):
        return False
    sub.click()
    time.sleep(3.0)
    return True


def expand_kaynak(page):
    """Kaynak Durumu'nda Matematik satırını (bölüm kırılımı) aç."""
    kd = page.get_by_text("Kaynak Durumu", exact=False).first
    panel = kd.locator(
        "xpath=ancestor::*[contains(@class,'rounded') and contains(@class,'border')][1]"
    )
    try:
        row = panel.get_by_text("Matematik", exact=True).first
        # zaten açıksa bölüm satırları görünür — Üçgenler/Eşitsizlikler ara
        if panel.get_by_text("Kareköklü", exact=False).count() == 0:
            row.click()
            time.sleep(1.2)
    except Exception:
        pass
    return panel


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

        # 1) kaynak-once — Matematik bölüm kırılımı AÇIK
        try:
            panel = expand_kaynak(page)
            cgs.snap(page, "kaynak-once", {"kaynak-panel": panel}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ kaynak-once: {e}")

        # 2) form doldurma → 3) görev belirdi → 4) kaynak-sonra
        try:
            form = open_task_form(page)
            fill_test_task(page, form, "Üçgenler", 4)
            cgs.snap(page, "gorev-form-dolu", {"gorev-form": form}, settle=0.8)
            if submit_form(page, form):
                row = page.get_by_text("Üçgenler: 4 test", exact=False).first
                row.scroll_into_view_if_needed(timeout=8_000)
                task_row = row.locator("xpath=ancestor::*[contains(@class,'rounded')][1]")
                cgs.snap(page, "gorev-eklendi", {"gorev-satiri": task_row}, settle=1.0)
                page.keyboard.press("Home")
                time.sleep(1.2)
                panel = expand_kaynak(page)
                cgs.snap(page, "kaynak-sonra", {"kaynak-panel": panel}, settle=1.0)
            else:
                print("  ✗ gorev submit disabled kaldı")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ gorev akışı: {e}")

        # 5) stadyum modalı
        try:
            page.locator('[aria-label="Sinema-koltuğu görünümü"]').first.click(timeout=8_000)
            time.sleep(2.0)
            cgs.snap(page, "stadyum-modal", settle=1.0)
            page.keyboard.press("Escape")
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ stadyum-modal: {e}")

        # 6) Sıradaki üniteler paneli (aç + kutu)
        try:
            hdr = page.get_by_text("Sıradaki üniteler", exact=False).first
            hdr.scroll_into_view_if_needed(timeout=8_000)
            hdr.click()
            time.sleep(1.2)
            box = hdr.locator(
                "xpath=ancestor::*[contains(@class,'rounded') and contains(@class,'border')][1]"
            )
            cgs.snap(page, "siradaki-uniteler", {"siradaki-panel": box}, settle=0.8)
            hdr.click()  # kapat (diğer karelerde sade dursun)
            time.sleep(0.8)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ siradaki-uniteler: {e}")

        # 7) Öneriden TEKİL Ekle → görev günde
        try:
            oner = page.get_by_text("Öneriler", exact=False).first
            oner.scroll_into_view_if_needed(timeout=8_000)
            time.sleep(0.8)
            row = oner.locator(
                "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
            )
            # önce öneri listesi açık değilse aç (chevron)
            try:
                row.click()
                time.sleep(1.0)
            except Exception:
                pass
            ekle = row.locator("button:has-text('Ekle'):visible").filter(has_not_text="Tümünü")
            if ekle.count() > 0:
                ekle.first.click()
                time.sleep(3.0)
                cgs.snap(page, "oneri-eklendi", settle=1.0)
            else:
                print("  ✗ öneri tekil Ekle bulunamadı")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ oneri-eklendi: {e}")

        # 8) Periyot çipleri + Sabah'a görev + gün periyot başlığı
        try:
            form = open_task_form(page)
            sab = form.get_by_text("Sabah", exact=True).first
            chips = sab.locator("xpath=ancestor::*[1]")
            sab.click()
            time.sleep(0.5)
            fill_test_task(page, form, "Dönüşüm Geometrisi", 2)
            cgs.snap(page, "gorev-periyot", {"periyot-cipleri": chips}, settle=0.8)
            if submit_form(page, form):
                try:
                    hdrp = page.get_by_text("Sabah", exact=True).first
                    hdrp.scroll_into_view_if_needed(timeout=6_000)
                    cgs.snap(page, "hafta-periyot", {"periyot-baslik": hdrp}, settle=1.0)
                except Exception:
                    cgs.snap(page, "hafta-periyot", settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ periyot akışı: {e}")

        # 9) Serbest Blok: oluştur → güne dağıt → kart
        try:
            form = open_task_form(page)
            form.get_by_text("Blok", exact=True).first.click()
            time.sleep(1.0)
            name_in = form.get_by_placeholder("Blok adı — örn. Özel Ders Mat ödevi").first
            name_in.fill("Özel Ders — Matematik Ödevi")
            tot = form.locator('input[type="number"]:visible').first
            tot.click(); tot.press("Control+a"); tot.type("40")
            time.sleep(0.5)
            cgs.snap(page, "blok-yeni", {"blok-form": form}, settle=0.8)
            # blok oluştur (blok formunun kendi submit'i)
            subs = form.locator("button[type=submit]")
            for i in range(subs.count()):
                st = subs.nth(i).evaluate("el => ({d: el.disabled, t: el.textContent.trim()})")
                if not st["d"]:
                    subs.nth(i).click()
                    break
            time.sleep(2.5)
            # blok seç + bu güne 10
            form = page.locator("form:visible").last
            bsel = None
            sels = form.locator("select")
            for i in range(sels.count()):
                if sels.nth(i).evaluate(
                    "el => Array.from(el.options).some(o => o.text.includes('blok seç') || o.text.includes('Özel Ders'))"
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
            # kart
            sb = page.get_by_text("Serbest Bloklar", exact=False).first
            sb.scroll_into_view_if_needed(timeout=8_000)
            time.sleep(1.0)
            kart = page.get_by_text("Özel Ders — Matematik Ödevi", exact=False).first.locator(
                "xpath=ancestor::*[contains(@class,'rounded') or contains(@class,'border')][1]"
            )
            cgs.snap(page, "blok-karti", {"blok-kart": kart}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ blok akışı: {e}")

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
