"""Kitap ekle bölümü — derin gösterim (2026-07-24, kullanıcı 3. tur).

GERÇEK yolculuk: "Sınav Yayınları LGS Fen Bilimleri Soru Bankası" sıfırdan
oluşturulur — ad → hedef sınıf (ön ayarlar + İNCE AYAR) → ders listesi AÇIK
(müfredat grupları görünür) → tip listesi AÇIK → oluştur → yöntem kartları →
katalog paneli (göster, geri dön) → YAPAY ZEKÂ önerisi (gerçek Gemini) →
test sayısı düzeltme → eşleştirme (kısmi + elle tamamlama) → Elif'e ata →
özet → öğrencinin Kitaplar sekmesinde görünüşü → kütüphane araçları
(kitap setleri · kitap şablonları · görev şablonları).

Not: <select> açılır listesi OS penceresi olduğundan ekran görüntüsüne girmez —
çekim için geçici `size` büyütme hilesi kullanılır (yalnız o karede).
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

BOOK_NAME = "Sınav Yayınları LGS Fen Bilimleri Soru Bankası"


def pick_by_text(sel, text, group_hint=None):
    """Option'ı metinden seç; group_hint verilirse o optgroup içinde ara."""
    script = """(el, arg) => {
      const [text, hint] = arg;
      for (const o of Array.from(el.options)) {
        if (!o.text.includes(text)) continue;
        const g = o.parentElement && o.parentElement.tagName === 'OPTGROUP'
          ? o.parentElement.label : '';
        if (hint && !g.includes(hint)) continue;
        return o.value;
      }
      return null;
    }"""
    val = sel.evaluate(script, [text, group_hint])
    if val is not None:
        sel.select_option(val)
    return val is not None


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(
            viewport={"width": cgs.VW, "height": cgs.VH},
            device_scale_factor=1, locale="tr-TR", color_scheme="light",
        )
        page = ctx.new_page()
        page.route("**/me/panel-visits", lambda r: r.abort())
        cgs.ensure_guide_dismissed()
        cgs.login(page)

        # ---------------- ADIM 1: Bilgiler ----------------
        cgs.goto(page, "/teacher/library/new", "Bilgiler")
        time.sleep(1.5)
        name_in = page.get_by_role("textbox").first
        name_in.fill(BOOK_NAME)
        time.sleep(0.5)
        # hedef sınıf ön ayar kartları
        lgs_preset = page.get_by_text("LGS (5-8)", exact=False).first
        grid = lgs_preset.locator("xpath=ancestor::div[2]")
        cgs.snap(page, "sihirbaz-ad", {"sinif-kartlari": grid}, settle=0.8)
        lgs_preset.click()
        time.sleep(0.6)
        # ince ayar
        try:
            page.get_by_text("İnce ayar", exact=False).first.click()
            time.sleep(0.8)
            gmin = page.locator("#cb-gmin")
            gmax = page.locator("#cb-gmax")
            ince = gmin.locator("xpath=ancestor::div[2]")
            pick_by = gmin.evaluate("el => el.tagName")
            if pick_by == "SELECT":
                gmin.select_option("8"); gmax.select_option("8")
            else:
                gmin.fill("8"); gmax.fill("8")
            time.sleep(0.5)
            cgs.snap(page, "sihirbaz-ince", {"ince-alanlari": ince}, settle=0.6)
        except Exception as e:  # noqa: BLE001
            print(f"  ince ayar: {e}")
        # ders listesi — optgroup'ları görünür yap (size hilesi)
        ders = page.locator("#cb-subject")
        ders.evaluate("el => { el.size = 12; }")
        time.sleep(0.6)
        cgs.snap(page, "sihirbaz-ders-acik", {"ders-listesi": ders}, settle=0.6)
        ders.evaluate("el => { el.size = 0; }")
        ok = pick_by_text(ders, "Fen Bilimleri", "LGS")
        print("ders seçildi:", ok)
        time.sleep(0.8)
        # tip listesi
        tip = page.locator("#cb-type")
        tip.evaluate("el => { el.size = 6; }")
        time.sleep(0.5)
        cgs.snap(page, "sihirbaz-tip", {"tip-listesi": tip}, settle=0.6)
        tip.evaluate("el => { el.size = 0; }")
        pick_by_text(tip, "Soru bankası")
        # yayınevi
        try:
            page.locator("#cb-publisher").fill("Sınav Yayınları")
        except Exception:
            pass
        time.sleep(0.4)
        page.get_by_role("button", name="Oluştur").first.click()
        page.get_by_text("Üniteler", exact=False).first.wait_for(timeout=60_000)
        time.sleep(1.5)

        # ---------------- ADIM 2: Üniteler ----------------
        katalog_karti = page.get_by_text("Resmi konulardan ekle", exact=False).first
        yk = katalog_karti.locator("xpath=ancestor::*[contains(@class,'rounded')][1]")
        cgs.snap(page, "sihirbaz-yontem", {"katalog-karti": yk}, settle=0.8)
        # katalog panelini göster → geri dön
        try:
            katalog_karti.click()
            time.sleep(1.5)
            cgs.snap(page, "sihirbaz-katalog", settle=0.8)
            page.get_by_text("Yöntem seç", exact=False).first.click()
            time.sleep(1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  katalog: {e}")
        # yapay zekâ önerisi (GERÇEK Gemini)
        page.get_by_text("Yapay zekâ önersin", exact=False).first.click()
        time.sleep(0.8)
        page.get_by_role("button", name="Yapay zekâ ile öner").first.click()
        # sonuç listesi (ünite satırları) gelene dek bekle
        deadline = time.time() + 120
        while time.time() < deadline:
            if page.locator("input").count() > 6:  # ünite satır inputları geldi
                break
            time.sleep(2)
        time.sleep(2.0)
        cgs.snap(page, "sihirbaz-ai-sonuc", settle=1.0)
        # bir test sayısını düzelt (ilk sayı inputu)
        try:
            nums = page.locator('input[type="number"]:visible')
            if nums.count() > 0:
                n0 = nums.first
                n0.click(); n0.press("Control+a"); n0.type("12")
                time.sleep(0.5)
                row = n0.locator("xpath=ancestor::*[contains(@class,'flex') or contains(@class,'grid')][1]")
                cgs.snap(page, "sihirbaz-test-duzelt", {"test-alani": row}, settle=0.6)
        except Exception as e:  # noqa: BLE001
            print(f"  test düzelt: {e}")
        page.get_by_role("button", name="Devam").first.click()
        time.sleep(2.0)

        # ---------------- ADIM 3: Eşleştirme ----------------
        page.get_by_text("Eşleştirme", exact=False).first.wait_for(timeout=30_000)
        time.sleep(1.5)
        cgs.snap(page, "sihirbaz-esles", settle=1.0)
        # eşleşmemiş satırları bul (değeri boş select'ler) → İKİSİNİ elle bağla
        sels = page.locator("select:visible")
        fixed = 0
        first_fixed_row = None
        for i in range(sels.count()):
            s = sels.nth(i)
            try:
                if s.evaluate("el => el.value === '' && el.options.length > 1"):
                    # ilk gerçek konuyu seç
                    val = s.evaluate(
                        "el => { const o = Array.from(el.options).find(o => o.value !== ''); return o ? o.value : null; }"
                    )
                    if val:
                        s.select_option(val)
                        fixed += 1
                        if first_fixed_row is None:
                            first_fixed_row = s.locator(
                                "xpath=ancestor::*[self::tr or contains(@class,'grid') or contains(@class,'flex')][1]"
                            )
                        time.sleep(0.5)
                if fixed >= 2:
                    break
            except Exception:
                continue
        print("elle bağlanan satır:", fixed)
        if first_fixed_row is not None:
            cgs.snap(page, "sihirbaz-esles-duzelt", {"duzeltilen-satir": first_fixed_row}, settle=0.8)
        else:
            cgs.snap(page, "sihirbaz-esles-duzelt", settle=0.8)
        # uygula/devam
        for label in ("Uygula", "Devam"):
            try:
                page.get_by_role("button", name=label).first.click(timeout=4_000)
                time.sleep(1.5)
            except Exception:
                continue
        time.sleep(1.0)

        # ---------------- ADIM 4: Öğrenci + bitir ----------------
        try:
            page.get_by_text("Öğrenci ata", exact=False).first.wait_for(timeout=20_000)
        except Exception:
            pass
        time.sleep(1.0)
        try:
            elif_cb = page.get_by_text("Elif", exact=False).first
            elif_cb.click()
            time.sleep(0.6)
        except Exception as e:  # noqa: BLE001
            print(f"  elif seçimi: {e}")
        cgs.snap(page, "sihirbaz-ogrenci", settle=0.8)
        try:
            page.get_by_text("ata ve bitir", exact=False).first.click(timeout=8_000)
            time.sleep(2.5)
        except Exception as e:  # noqa: BLE001
            print(f"  ata-bitir: {e}")
        cgs.snap(page, "sihirbaz-tamam", settle=1.0)

        # ---------------- Öğrencinin Kitaplar sekmesinde görünüş ----------------
        cgs.goto(page, f"/teacher/students/{cgs.IDS['elif']}", "Elif")
        try:
            page.get_by_role("tab", name="Kitaplar").first.click(timeout=10_000)
            time.sleep(2.5)
            row = page.get_by_text("Fen Bilimleri Soru Bankası", exact=False).first
            row.scroll_into_view_if_needed(timeout=8_000)
            box = row.locator("xpath=ancestor::*[contains(@class,'rounded')][1]")
            cgs.snap(page, "ogrenci-kitap-yeni", {"yeni-kitap-satiri": box}, settle=1.0)
        except Exception as e:  # noqa: BLE001
            print(f"  öğrenci kitap: {e}")

        # ---------------- Kütüphane araçları ----------------
        for path, name in (
            ("/teacher/library/book-sets", "kutup-setler"),
            ("/teacher/library/templates", "kutup-sablonlar"),
            ("/teacher/library/task-templates", "kutup-gorev-sablon"),
        ):
            try:
                cgs.goto(page, path)
                time.sleep(2.5)
                cgs.snap(page, name, settle=1.0)
            except Exception as e:  # noqa: BLE001
                print(f"  {name}: {e}")

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
