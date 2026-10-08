"""Sağ şerit + raptiyeli bölümler (v2) — GERÇEK TARAYICI doğrulaması (2026-09-08).

KOÇ (ekran görüntüleriyle, ikinci tur):
  1. Müfredat'ta ders değiştirince açılır liste KAYBOLUYORDU (yanıt yalnız seçili
     dersi taşıyordu → "tek ders → seçici gizli").
  2. "Sabitleme devre dışı görünüyor ama menü açık — mantık ters."
  3. "Bastığımda menü kapanmıyor" (≥2 kullanımı olan bölüm elle kapatılamıyordu).
  4. "Sağ kısım epeyce yer kaplıyor; en sık kullanılanlar öne çıksın; program
     hazırlama kısmına alan açılsın."

v2 modeli: raptiye DOLU = panelde sabit · BOŞ = şeritte simge, tıklayınca
GEÇİCİ (peek) açılır, Esc/dışarı/X kapatır · sıra = son 7 gün kullanım.
Tercih TARAYICIDA (localStorage) — kullanıcı kararı.

Senaryolar (kullanışlılık ölçümleri dahil):
   1. Şerit var: 4 etiketli simge (Devret adayı yokken gizli)
   2. Varsayılan: yalnız Kaynak Durumu sabit (raptiye DOLU + açık) — simge ne
      diyorsa o; diğer bölümler DOM'da yok
   3. Ölçüm: sabit panel ~372px
   4. Kaynak'ın raptiyesini kaldır → peek olarak kalır (sürpriz kapanma yok);
      Esc → sağ taraf 44px şerit; EDİTÖR ≥300px GENİŞLER
   5. Yenile → şerit-only kalıcı, editör geniş
   6. Şeritten Müfredat → peek; şeridin solunda, editörün ÜSTÜNDE (editör
      yer değiştirmez)
   7. BUG 1: Müfredat'ta ders değiştir → seçici KALIR, yeni dersin konuları gelir
   8. Esc kapatır
   9. Dışarı tıklama kapatır
  10. Aynı anda tek peek (Sıradaki açılınca Müfredat kapanır)
  11. Peek'ten "Sabitle" → panele yerleşir; yenilemede sabit + raptiye dolu
  12. BUG 3: sabit bölüm başlığı 3 kez tıklanınca 1→0→1→0 (takılma yok);
      yenilemede yine açık (katlama oturumluk)
  13. Şeritten sabit-katlı bölüme tıklama → açar
  14. Sıralama: son 7 günde çok kullanılan (Bloklar) şeritte BAŞA gelir
  15. Peek içine tıklama kapatmaz
  16. Dar ekran: şerit yatay, peek satır içi (altında)
  17. Sol gün fihristi raptiyesi aynı modelle çalışır
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

from scripts.audit_day_card_perception import PWD, WEB, cleanup, seed  # noqa: E402

SHOT_DIR = os.environ.get("SHOT_DIR") or os.path.join(
    os.environ.get("TEMP", "/tmp"), "rotam_side_rail"
)
os.makedirs(SHOT_DIR, exist_ok=True)

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def sec_state(page, sid: str) -> dict | None:
    return page.evaluate(
        """(sid) => {
          const el = document.querySelector(`[data-section="${sid}"]`);
          if (!el) return null;
          return { mode: el.dataset.mode, open: el.dataset.open === '1',
                   pinned: el.dataset.pinned === '1' };
        }""",
        sid,
    )


def rect(page, selector: str) -> dict | None:
    return page.evaluate(
        """(sel) => {
          const el = document.querySelector(sel);
          if (!el) return null;
          // Belge koordinatı (kaydırma bağımsız) — dar ekranda şerit sayfanın
          // altında; tıklama kaydırınca viewport ölçüsü yanıltır.
          const r = el.getBoundingClientRect();
          const sx = window.scrollX, sy = window.scrollY;
          return { x: r.x + sx, y: r.y + sy, w: r.width, h: r.height,
                   r: r.right + sx, b: r.bottom + sy };
        }""",
        selector,
    )


def rail_ids(page) -> list[str]:
    return page.evaluate(
        "() => [...document.querySelectorAll('[data-rail] button[data-rail]')].map(b => b.dataset.rail)"
    )


def docked_count(page) -> int:
    v = page.get_attribute("[data-side-panel]", "data-docked")
    return int(v or 0)


def peek_id(page) -> str:
    return page.get_attribute("[data-side-panel]", "data-peek-id") or ""


def esc(page):
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


def shot(page, name: str):
    page.screenshot(path=os.path.join(SHOT_DIR, f"{name}.png"))


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    week = f"{WEB}/teacher/students/{ids['student']}/week"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)  # login TAM SAYFA geçiş — sabit bekleme

            def go(clear_prefs: bool = False):
                page.goto(week, wait_until="networkidle")
                if clear_prefs:
                    page.evaluate(
                        "() => Object.keys(localStorage).filter(k => k.startsWith('rotam:section:')).forEach(k => localStorage.removeItem(k))"
                    )
                    page.goto(week, wait_until="networkidle")
                page.wait_for_timeout(2000)
                later = page.query_selector('button:has-text("Daha sonra")')
                if later:
                    later.click()
                    page.wait_for_timeout(800)

            go(clear_prefs=True)

            # ---- 1. şerit
            r_ids = rail_ids(page)
            labels = page.evaluate(
                "() => [...document.querySelectorAll('[data-rail] button[data-rail]')].map(b => b.innerText.trim())"
            )
            check("1. şerit: 4 simge (Devret adayı yokken gizli)",
                  len(r_ids) == 4 and "week:carryover" not in r_ids, str(r_ids))
            check("1b. her simgenin görünür etiketi var",
                  all(l for l in labels) and any("Kaynak" in l for l in labels), str(labels))
            clipped = page.evaluate(
                "() => [...document.querySelectorAll('[data-rail] button[data-rail] span.truncate')].filter(s => s.scrollWidth > s.clientWidth + 1).map(s => s.textContent)"
            )
            check("1c. şerit etiketleri KIRPILMIYOR (Müfredat/Sıradaki sığar)", clipped == [], str(clipped))

            # ---- 2. varsayılan
            st_res = sec_state(page, "week:resources")
            check("2. Kaynak Durumu varsayılan SABİT + açık (raptiye dolu = açık)",
                  st_res == {"mode": "docked", "open": True, "pinned": True}, str(st_res))
            pin_res = page.query_selector('[data-section="week:resources"] button[aria-pressed]')
            check("2b. raptiye düğmesi basılı (aria-pressed=true)",
                  pin_res is not None and pin_res.get_attribute("aria-pressed") == "true")
            others = [sec_state(page, s) for s in ("week:curriculum", "week:next-units", "week:work-blocks")]
            check("2c. sabit olmayan bölümler DOM'da yok (yeri şerit)",
                  all(o is None for o in others), str(others))
            check("2d. data-docked=1", docked_count(page) == 1, str(docked_count(page)))
            shot(page, "01_default_docked")

            # ---- 3. ölçüm (sabit panel)
            aside0 = rect(page, "[data-side-panel]")
            ed0 = rect(page, "#day-editor")
            check("3. sabit panel + şerit ≈ 384px",
                  aside0 is not None and 370 <= aside0["w"] <= 390, str(aside0))

            # ---- 4. raptiyeyi kaldır → peek → Esc → şerit-only, editör genişler
            pin_res.click()
            page.wait_for_timeout(400)
            st_res = sec_state(page, "week:resources")
            check("4. raptiye kaldırılınca bölüm PEEK olarak kalır (sürpriz kapanma yok)",
                  st_res is not None and st_res["mode"] == "peek" and st_res["open"]
                  and peek_id(page) == "week:resources", f"{st_res} peek={peek_id(page)}")
            esc(page)
            aside1 = rect(page, "[data-side-panel]")
            ed1 = rect(page, "#day-editor")
            check("4b. Esc → sağ taraf yalnız şerit (≈56px)",
                  aside1 is not None and 48 <= aside1["w"] <= 60 and docked_count(page) == 0,
                  f"{aside1} docked={docked_count(page)}")
            check("4c. EDİTÖR ≥300px GENİŞLEDİ",
                  ed0 and ed1 and ed1["w"] - ed0["w"] >= 300,
                  f"{ed0 and ed0['w']} → {ed1 and ed1['w']}")
            shot(page, "02_rail_only")

            # ---- 5. yenile → kalıcı
            go()
            aside2 = rect(page, "[data-side-panel]")
            check("5. yenilemede şerit-only kalıcı, editör geniş",
                  docked_count(page) == 0 and aside2 and aside2["w"] <= 60
                  and rect(page, "#day-editor")["w"] >= ed1["w"] - 2,
                  f"docked={docked_count(page)} aside={aside2}")

            # ---- 6. şeritten Müfredat → peek (editörün üstünde, yer değiştirmez)
            page.click('[data-rail="week:curriculum"]')
            page.wait_for_timeout(1500)
            st_cur = sec_state(page, "week:curriculum")
            pk = rect(page, "[data-peek]")
            rail = rect(page, "[data-rail]")
            ed2 = rect(page, "#day-editor")
            check("6. Müfredat peek açıldı",
                  st_cur is not None and st_cur["mode"] == "peek" and peek_id(page) == "week:curriculum",
                  f"{st_cur} peek={peek_id(page)}")
            check("6b. peek şeridin solunda, editörün ÜSTÜNDE (overlay)",
                  pk and rail and ed2 and pk["r"] <= rail["x"] + 2 and pk["x"] < ed2["r"],
                  f"peek={pk} rail={rail} editor={ed2}")
            check("6c. editör YER DEĞİŞTİRMEDİ (genişlik aynı)",
                  ed2 and abs(ed2["w"] - ed1["w"]) <= 2, f"{ed1 and ed1['w']} vs {ed2 and ed2['w']}")
            shot(page, "03_peek_curriculum")

            # ---- 7. BUG 1: ders değiştir → seçici kalır
            sel = page.query_selector('[data-section="week:curriculum"] select[aria-label="Ders seç"]')
            opts = page.evaluate(
                "() => { const s = document.querySelector('[data-section=\"week:curriculum\"] select[aria-label=\"Ders seç\"]'); return s ? [...s.options].map(o => ({v:o.value, t:o.text})) : []; }"
            )
            check("7. ders seçici var, ≥3 ders", sel is not None and len(opts) >= 3, str(opts))
            fizik = next((o for o in opts if "Fizik" in o["t"]), None)
            if sel and fizik:
                sel.select_option(fizik["v"])
                page.wait_for_timeout(2000)
                sel2 = page.query_selector('[data-section="week:curriculum"] select[aria-label="Ders seç"]')
                val = sel2.evaluate("s => s.value") if sel2 else None
                has_topic = page.query_selector('[data-section="week:curriculum"] button:has-text("Fizik Konusu")') is not None
                check("7b. BUG 1: ders değişince seçici KALIR + Fizik konuları listelenir",
                      sel2 is not None and val == fizik["v"] and has_topic,
                      f"sel={sel2 is not None} val={val} topic={has_topic}")
                shot(page, "04_subject_switched")
            else:
                check("7b. BUG 1 senaryosu (seçici yok)", False, "seçici/Fizik bulunamadı")

            # ---- 8. Esc
            esc(page)
            check("8. Esc peek'i kapatır",
                  sec_state(page, "week:curriculum") is None and peek_id(page) == "")

            # ---- 9. dışarı tıklama
            page.click('[data-rail="week:curriculum"]')
            page.wait_for_timeout(600)
            page.evaluate("() => document.body.dispatchEvent(new MouseEvent('mousedown', {bubbles: true}))")
            page.wait_for_timeout(300)
            check("9. dışarı tıklama peek'i kapatır",
                  sec_state(page, "week:curriculum") is None, str(peek_id(page)))

            # ---- 10. tek peek
            page.click('[data-rail="week:curriculum"]')
            page.wait_for_timeout(500)
            page.click('[data-rail="week:next-units"]')
            page.wait_for_timeout(800)
            check("10. aynı anda tek peek (Sıradaki açılınca Müfredat kapanır)",
                  peek_id(page) == "week:next-units" and sec_state(page, "week:curriculum") is None
                  and sec_state(page, "week:next-units") is not None, str(peek_id(page)))

            # ---- 11. Sabitle → panele yerleşir
            page.click('[data-section="week:next-units"] button[aria-pressed]')
            page.wait_for_timeout(500)
            st_nu = sec_state(page, "week:next-units")
            check("11. peek'ten Sabitle → panelde sabit, peek kapandı",
                  st_nu == {"mode": "docked", "open": True, "pinned": True}
                  and docked_count(page) == 1 and peek_id(page) == "", f"{st_nu} docked={docked_count(page)}")
            go()
            st_nu = sec_state(page, "week:next-units")
            pressed = page.get_attribute('[data-section="week:next-units"] button[aria-pressed]', "aria-pressed")
            check("11b. yenilemede sabit + açık + raptiye dolu",
                  st_nu == {"mode": "docked", "open": True, "pinned": True} and pressed == "true",
                  f"{st_nu} pressed={pressed}")
            shot(page, "05_docked_next_units")

            # ---- 12. BUG 3: başlık aç/kapa takılmaz
            seq = []
            for _ in range(3):
                page.click('[data-section="week:next-units"] button[aria-expanded]')
                page.wait_for_timeout(250)
                seq.append(sec_state(page, "week:next-units")["open"])
            check("12. BUG 3: sabit bölüm başlığı 1→0→1→0 (takılma yok)",
                  seq == [False, True, False], str(seq))
            go()
            check("12b. yenilemede yine açık (katlama oturumluk, raptiye kazanır)",
                  sec_state(page, "week:next-units")["open"] is True)

            # ---- 13. şeritten sabit-katlı bölüm → açar
            page.click('[data-section="week:next-units"] button[aria-expanded]')
            page.wait_for_timeout(250)
            page.click('[data-rail="week:next-units"]')
            page.wait_for_timeout(400)
            check("13. şeritten sabit-katlı bölüme tıklama → açar",
                  sec_state(page, "week:next-units")["open"] is True)

            # ---- 14. sıralama: çok kullanılan başa
            now_ms = int(time.time() * 1000)
            page.evaluate(
                "(v) => localStorage.setItem('rotam:section:week:work-blocks', v)",
                json.dumps({"pinned": False, "hits": [now_ms - 1000, now_ms - 60_000, now_ms - 120_000]}),
            )
            go()
            r_ids = rail_ids(page)
            check("14. son 7 günde çok kullanılan (Bloklar) şeritte BAŞA gelir",
                  r_ids and r_ids[0] == "week:work-blocks", str(r_ids))
            check("14b. sabit Sıradaki hâlâ panelde", sec_state(page, "week:next-units") is not None)

            # ---- 15. peek içine tıklama kapatmaz
            page.click('[data-rail="week:curriculum"]')
            page.wait_for_timeout(1500)
            row = page.query_selector('[data-section="week:curriculum"] button:has-text("Konusu")')
            if row:
                row.click()
                page.wait_for_timeout(400)
            check("15. peek içine tıklama kapatmaz",
                  row is not None and peek_id(page) == "week:curriculum", str(peek_id(page)))
            esc(page)

            # ---- 16. dar ekran
            page.set_viewport_size({"width": 1000, "height": 900})
            page.wait_for_timeout(600)
            rail_n = rect(page, "[data-rail]")
            check("16. dar ekranda şerit YATAY", rail_n and rail_n["w"] > rail_n["h"] * 2, str(rail_n))
            page.click('[data-rail="week:curriculum"]')
            page.wait_for_timeout(1200)
            pk_n = rect(page, "[data-peek]")
            check("16b. dar ekranda peek şeridin ALTINDA satır içi",
                  pk_n and rail_n and pk_n["y"] >= rail_n["b"] - 1 and abs(pk_n["x"] - rail_n["x"]) <= 4,
                  f"peek={pk_n} rail={rail_n}")
            shot(page, "06_narrow")
            esc(page)
            page.set_viewport_size({"width": 1440, "height": 900})
            page.wait_for_timeout(500)

            # ---- 17. gün fihristi raptiyesi
            nav = page.query_selector('[data-section="week:day-nav"]')
            nav_open = nav.get_attribute("data-open") if nav else None
            pin_nav = page.query_selector('[data-section="week:day-nav"] button[aria-pressed]')
            check("17. gün fihristi varsayılan sabit + geniş",
                  nav_open == "1" and pin_nav and pin_nav.get_attribute("aria-pressed") == "true")
            pin_nav.click()
            page.wait_for_timeout(300)
            still_open = page.get_attribute('[data-section="week:day-nav"]', "data-open")
            go()
            after = page.get_attribute('[data-section="week:day-nav"]', "data-open")
            check("17b. fihrist raptiyesi kaldırılınca bu oturumda geniş kalır, yenilemede 44px şerit",
                  still_open == "1" and after == "0", f"now={still_open} reload={after}")
            page.click('[data-section="week:day-nav"] button[aria-pressed]')
            page.wait_for_timeout(300)
            go()
            check("17c. yeniden sabitle → yenilemede geniş",
                  page.get_attribute('[data-section="week:day-nav"]', "data-open") == "1")
            shot(page, "07_final")

            b.close()
    finally:
        cleanup(ids)

    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  FAIL:", f)
    print(f"ekran görüntüleri: {SHOT_DIR}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
