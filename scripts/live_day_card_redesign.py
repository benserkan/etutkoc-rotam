"""Gün kartı yeniden tasarımı — GERÇEK TARAYICI doğrulaması (2026-09-07).

Seed: audit_day_card_perception ile aynı (1 gün · 3 periyot · 3 ders · 9 görev).

Senaryolar:
   1. Üç periyot bölgesi ayrı <section> olarak çizilir (Sabah/Öğle/Akşam)
   2. Ders başlığı YOK (eski hâlde 9 taneydi) — ders satırın kendisinde
   3. TEST rozeti YOK (görevlerin %78'i test; her satırda yazmak gürültü)
   4. 9 görevlik gün TEK EKRANA sığar (≤ 900px)
   5. Satır ortalaması ≤ 44px
   6. SÜRÜKLE-BIRAK: sabahtaki görev öğledeki görevin üstüne → period
      DB'de "noon" olur (2026-08-12 saha bug'ı: görsel taşınır ama kaydedilmez)
   7. Satır aksiyonları (düzenle/sil/yay) her satırda duruyor
   8. "+ Öğleye ekle" → form o periyot ÖN-SEÇİLİ açılır; eklenen görev
      öğle periyodunda oluşur (koç periyot çipi seçmez)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.audit_day_card_perception import PWD, WEB, cleanup, seed  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Task  # noqa: E402

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


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/students/{ids['student']}/week",
                      wait_until="networkidle")
            page.wait_for_timeout(2500)
            later = page.query_selector('button:has-text("Daha sonra")')
            if later:
                later.click()
                page.wait_for_timeout(1000)
            page.wait_for_selector(".task-row", timeout=8000)
            page.wait_for_timeout(600)

            # ---- 1. üç bölge
            zones = page.query_selector_all("#day-editor section[aria-label]")
            labels = [z.get_attribute("aria-label") for z in zones]
            check("1. üç periyot bölgesi ayrı section (Sabah/Öğle/Akşam)",
                  labels == ["Sabah", "Öğle", "Akşam"], f"{labels}")

            # ---- 2. ders başlığı yok
            n_subj_heads = page.evaluate(
                "() => [...document.querySelectorAll('#day-editor div.bg-muted\\\\/20')]"
                ".filter(d => d.className.includes('border-l-[3px]')).length"
            )
            check("2. ders başlığı YOK (eskiden 9 tane)", n_subj_heads == 0,
                  f"{n_subj_heads}")

            # ---- 3. TEST rozeti yok
            n_test_badges = page.evaluate(
                "() => [...document.querySelectorAll('#day-editor .task-row span')]"
                ".filter(s => s.textContent.trim() === 'Test').length"
            )
            check("3. TEST rozeti YOK (her satırda yazmak gürültüydü)",
                  n_test_badges == 0, f"{n_test_badges}")

            # ---- 4-5. yoğunluk
            card_h = page.evaluate(
                "() => document.querySelector('#day-editor').getBoundingClientRect().height"
            )
            row_hs = page.evaluate(
                "() => [...document.querySelectorAll('#day-editor .task-row')]"
                ".map(r => r.getBoundingClientRect().height)"
            )
            avg_row = sum(row_hs) / max(1, len(row_hs))
            check("4. 9 görevlik gün tek ekrana sığar (≤ 900px)", card_h <= 900,
                  f"{card_h:.0f}px")
            check("5. satır ortalaması ≤ 44px", avg_row <= 44, f"{avg_row:.0f}px")

            # ---- 6. Sürükle-bırak periyot değiştirir ve KAYDEDİLİR
            rows = page.query_selector_all("#day-editor .task-row")
            first_id = int(rows[0].get_attribute("id").split("-")[1])
            with SessionLocal() as db:
                before = db.get(Task, first_id).period
            src_sel = f'#{rows[0].get_attribute("id")} button[aria-label="Sırala"]'
            dst_sel = f'#{rows[4].get_attribute("id")}'   # öğle bölgesi, 2. görev
            # dnd-kit PointerSensor: page.mouse yeterli pointer olayı üretmiyor
            # (aktivasyon hiç tetiklenmiyordu). Sentetik PointerEvent zinciriyle
            # sür: pointerdown → eşik hareketi → adım adım pointermove → pointerup.
            # Hedef bölgenin ORTA noktasına bırak (satırlar sıralama animasyonuyla
            # kayabilir; bölge merkezi kararlı).
            drag_js = """
            async ([srcSel, dstSel]) => {
              const src = document.querySelector(srcSel);
              const dstRow = document.querySelector(dstSel);
              const zone = dstRow.closest('section[aria-label]');
              // ÖNCE görünür kıl, SONRA ölç: bölgeler başta viewport dışında
              // (y≈1028); sürükleme sayfayı kaydırınca eski koordinat başka
              // bölgeye düşüyordu (ilk koşuda Öğle'ye bırakıp Akşam'a gitti).
              src.scrollIntoView({block: 'center'});
              await new Promise(r => setTimeout(r, 300));
              const r1 = src.getBoundingClientRect(), r2 = zone.getBoundingClientRect();
              const sx = r1.x + r1.width/2, sy = r1.y + r1.height/2;
              const tx = r2.x + 80, ty = r2.y + r2.height/2 + 10;
              const ev = (type, x, y, t) => t.dispatchEvent(new PointerEvent(type, {
                bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1,
                pointerType: 'mouse', isPrimary: true, button: 0,
                buttons: type === 'pointerup' ? 0 : 1,
              }));
              const sleep = (ms) => new Promise(r => setTimeout(r, ms));
              ev('pointerdown', sx, sy, src); await sleep(60);
              ev('pointermove', sx + 10, sy + 10, document); await sleep(60);
              for (let i = 1; i <= 20; i++) {
                ev('pointermove', sx + (tx-sx)*i/20, sy + (ty-sy)*i/20, document);
                await sleep(25);
              }
              await sleep(250);
              ev('pointerup', tx, ty, document);
              return zone.getAttribute('aria-label');
            }
            """
            dropped_zone = page.evaluate(drag_js, [src_sel, dst_sel])
            page.wait_for_timeout(2500)
            with SessionLocal() as db:
                after = db.get(Task, first_id).period
            check("6. sürükle-bırak: sabah → öğle DB'de KAYDEDİLDİ",
                  before == "morning" and after == "noon" and dropped_zone == "Öğle",
                  f"{before} → {after} (bırakılan bölge: {dropped_zone})")

            # ---- 7. Satır aksiyonları duruyor (düzenle/sil/yay)
            acts = page.query_selector_all('#day-editor .task-row button[aria-label="Düzenle"]')
            check("7. satır aksiyonları (düzenle) her satırda duruyor", len(acts) == 9,
                  f"{len(acts)}")

            # ---- 8. Periyoda doğrudan ekleme
            add_noon = page.query_selector('button:has-text("Öğleye ekle")')
            check("8a. bölge altında '+ Öğleye ekle' var", add_noon is not None)
            if add_noon:
                add_noon.scroll_into_view_if_needed()
                add_noon.click()
                page.wait_for_timeout(1500)
                box = page.query_selector('input[aria-label="Görev ara"]')
                check("8b. form o bölgenin altında açıldı (hızlı kutu)", box is not None)
                if box:
                    with SessionLocal() as db:
                        n_noon_before = (db.query(Task)
                                         .filter(Task.student_id == ids["student"],
                                                 Task.period == "noon").count())
                    box.click()
                    page.wait_for_timeout(1800)
                    # DİKKAT: has-text sayfadaki İLK eşleşeni verir — Hafta
                    # Izgarası'nın gün kolonu da "Fizik Bölümü" içeriyor ve o
                    # bir buton. Aday listesinin içine kapsa.
                    row = page.query_selector(
                        'div.bg-popover button:has-text("Fizik Soru Bankası")'
                    )
                    if row:
                        row.click()
                        page.wait_for_timeout(700)
                        page.locator(
                            'form:has(input[aria-label="Görev ara"]) button[type="submit"]'
                        ).first.click()
                        page.wait_for_timeout(2500)
                    with SessionLocal() as db:
                        n_noon_after = (db.query(Task)
                                        .filter(Task.student_id == ids["student"],
                                                Task.period == "noon").count())
                    check("8c. eklenen görev ÖĞLE periyodunda oluştu (çip seçilmedi)",
                          n_noon_after == n_noon_before + 1,
                          f"{n_noon_before} → {n_noon_after}")

            page.screenshot(path="/tmp/daycard_after.png", full_page=True)
            b.close()
    finally:
        cleanup(ids)

    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
