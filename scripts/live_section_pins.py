"""Raptiyeli bölümler — GERÇEK TARAYICI doğrulaması (2026-09-08).

KOÇ: "en soldaki gün kutuları ve sağdaki bölümleri gizle/göster; alışkanlığa
göre yoğun kullanılan görünsün, diğerleri tıklayınca açılsın; 'Paneli gizle'
çok yukarıda, kaldır; raptiye simgesini bölüm başlarına koy."

Tercih TARAYICIDA (localStorage, useSyncExternalStore) — kullanıcı kararı.

Senaryolar:
   1. Başlıktaki "Paneli gizle" düğmesi YOK
   2. Dört sağ bölüm + sol fihrist raptiyeli (data-section)
   3. İlk açılış varsayılanı: Kaynak Durumu + Müfredat açık, Sıradaki + Bloklar katlı
   4. Katlı bölüm başlığına tıkla → açılır; YENİLE → açık kalır (kullanım sayıldı)
   5. Raptiye → sabit; YENİLE → açık ve raptiye dolu
   6. Sabitlenmiş bölüm başlığa tıklanınca katlanır ama raptiye durur; yenilemede
      raptiye onu yine açar (sabit = her açılışta açık)
   7. 7 gün kullanılmamış (sahte eski damga) bölüm katlı gelir (alışkanlık söner)
   8. Fihrist daralt → 44px şerit; gün tıklaması hâlâ günü değiştirir
   9. Fihrist tercihi yenilemede korunur
  10. Açık gelen bölümün İÇİNE ilk tıklama bölümü KATLAMAZ (canlı testte
      yakalanan bug: 1 kullanım varsayılanı eziyordu)
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


def state(page, sid: str) -> dict:
    """data-open / data-pinned oku."""
    return page.evaluate(
        """(sid) => {
          const el = document.querySelector(`[data-section="${sid}"]`);
          if (!el) return null;
          return { open: el.dataset.open === '1', pinned: el.dataset.pinned === '1' };
        }""",
        sid,
    )


def header_btn(page, sid: str):
    return page.query_selector(f'[data-section="{sid}"] button[aria-expanded]')


def pin_btn(page, sid: str):
    return page.query_selector(f'[data-section="{sid}"] button[aria-pressed]')


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    week = f"{WEB}/teacher/students/{ids['student']}/week"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            ctx = b.new_context(viewport={"width": 1500, "height": 950})
            page = ctx.new_page()
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)

            def open_week():
                page.goto(week, wait_until="networkidle")
                page.wait_for_timeout(2200)
                later = page.query_selector('button:has-text("Daha sonra")')
                if later:
                    later.click()
                    page.wait_for_timeout(800)
                page.wait_for_selector('[data-section="week:resources"]', timeout=8000)
                page.wait_for_timeout(400)

            open_week()

            # ---- 1. Paneli gizle yok
            check("1. başlıktaki 'Paneli gizle' düğmesi KALDIRILDI",
                  page.query_selector('button:has-text("Paneli gizle")') is None)

            # ---- 2. bölümler raptiyeli
            ids_expected = ["week:curriculum", "week:next-units", "week:work-blocks",
                            "week:resources", "week:day-nav"]
            present = [s for s in ids_expected if page.query_selector(f'[data-section="{s}"]')]
            check("2. dört sağ bölüm + fihrist raptiyeli (data-section)",
                  len(present) == 5, f"{present}")

            # ---- 3. varsayılanlar
            st = {s: state(page, s) for s in ids_expected}
            check(
                "3. ilk açılış: Kaynak Durumu + Müfredat AÇIK · Sıradaki + Bloklar KATLI",
                st["week:resources"]["open"] and st["week:curriculum"]["open"]
                and not st["week:next-units"]["open"] and not st["week:work-blocks"]["open"],
                f"{ {k: v['open'] for k, v in st.items()} }",
            )

            # ---- 4. katlı bölümü aç → yenile → açık kalır
            header_btn(page, "week:work-blocks").click()
            page.wait_for_timeout(500)
            opened = state(page, "week:work-blocks")["open"]
            open_week()
            still = state(page, "week:work-blocks")["open"]
            check("4. katlı bölüm açıldı → YENİLE → açık kaldı (kullanım sayıldı)",
                  opened and still, f"acildi={opened} yenileme_sonrasi={still}")

            # ---- 5. raptiye → sabit → yenile → açık + dolu
            pin_btn(page, "week:next-units").click()
            page.wait_for_timeout(400)
            open_week()
            s5 = state(page, "week:next-units")
            check("5. raptiye → YENİLE → açık ve raptiye dolu", s5["open"] and s5["pinned"],
                  f"{s5}")

            # ---- 6. sabit bölüm katlanır ama yenilemede raptiye açar
            header_btn(page, "week:next-units").click()
            page.wait_for_timeout(400)
            collapsed = not state(page, "week:next-units")["open"]
            open_week()
            s6 = state(page, "week:next-units")
            check("6. sabit bölüm elle katlanır; yenilemede raptiye yine AÇAR",
                  collapsed and s6["open"] and s6["pinned"],
                  f"katlandi={collapsed} sonra={s6}")

            # ---- 7. eski kullanım söner: 8 gün önceki damga → katlı
            old_ts = int((time.time() - 8 * 86400) * 1000)
            page.evaluate(
                """([k, v]) => localStorage.setItem(k, v)""",
                ["rotam:section:week:work-blocks",
                 json.dumps({"mode": "auto", "hits": [old_ts, old_ts + 1000],
                             "lastManualOpen": True})],
            )
            open_week()
            check("7. 7 günden eski kullanım SÖNER → bölüm katlı gelir",
                  not state(page, "week:work-blocks")["open"],
                  f"{state(page, 'week:work-blocks')}")

            # ---- 8. fihrist daralt → şerit → gün tıklaması çalışır
            nav_w_before = page.evaluate(
                "() => document.querySelector('nav[aria-label=\"Günler\"]').getBoundingClientRect().width"
            )
            page.click('button[aria-label="Gün listesini daralt"]')
            page.wait_for_timeout(600)
            nav_w_after = page.evaluate(
                "() => document.querySelector('nav[aria-label=\"Günler\"]').getBoundingClientRect().width"
            )
            # şeritte bir güne tıkla → seçili gün (aria-current) değişsin
            def current_day():
                el = page.query_selector('nav[aria-label="Günler"] button[aria-current="true"]')
                return el.get_attribute("title") or el.inner_text() if el else ""
            before_title = current_day()
            target = page.query_selector(
                'nav[aria-label="Günler"] button[title*=" — "]:not([aria-current])'
            )
            if target:
                target.click()
                page.wait_for_timeout(1000)
            after_title = current_day()
            check(
                "8. fihrist daraldı (şerit) ve gün tıklaması günü değiştirdi",
                nav_w_after < nav_w_before * 0.5 and target is not None and before_title != after_title,
                f"{nav_w_before:.0f}px → {nav_w_after:.0f}px · baslik degisti={before_title != after_title}",
            )

            # ---- 9. fihrist tercihi kalıcı
            open_week()
            nav_w_reload = page.evaluate(
                "() => document.querySelector('nav[aria-label=\"Günler\"]').getBoundingClientRect().width"
            )
            check("9. fihrist tercihi yenilemede korunur (şerit kaldı)",
                  nav_w_reload < nav_w_before * 0.5, f"{nav_w_reload:.0f}px")

            # ---- 10. Açık gelen bölümün içine ilk tıklama katlamamalı
            page.evaluate("() => localStorage.removeItem('rotam:section:week:curriculum')")
            open_week()
            was_open = state(page, "week:curriculum")["open"]
            inner = page.query_selector('[data-section="week:curriculum"] li > button')
            if inner:
                inner.click()
                page.wait_for_timeout(600)
            check(
                "10. açık bölümün içine İLK tıklama bölümü katlamaz",
                was_open and inner is not None and state(page, "week:curriculum")["open"],
                f"once={was_open} sonra={state(page, 'week:curriculum')}",
            )

            page.screenshot(path="/tmp/pins_final.png", full_page=False)
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
