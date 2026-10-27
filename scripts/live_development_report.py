"""Gelişim Raporu (360°) — gerçek tarayıcı (dev :3000 + :8081). Geçici koç/öğrenci kurar, siler.

  1. Öğrenci detayında kendi sekmesi "Gelişim Raporu" (#report; 2026-10-27 Denemeler'den taşındı)
  2. Başlık + bu hafta gün şeridi + hafta tablosu + 4 kutu + aksiyon planı görünür
  3. Bir risk + bir aksiyon seç → alt çubuk "2 madde seçili" → Seansa ekle → "Seans gündeminde"
  4. Yatay taşma yok (1440 + 390) · koyu tema ekran görüntüsü
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.test_api_v2_development_report as base  # noqa: E402

BASE = "http://localhost:3000"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
ok = 0
bad: list[str] = []


def check(label, cond, detail=""):
    global ok
    if cond:
        ok += 1
        print(f"  [PASS] {label}")
    else:
        bad.append(label)
        print(f"  [FAIL] {label} ({detail})")


def overflow(page) -> int:
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    d = base.seed()
    sid = d["st"]
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome")
            for scheme in ("light", "dark"):
                ctx = br.new_context(viewport={"width": 1440, "height": 1000}, color_scheme=scheme)
                page = ctx.new_page()
                page.goto(f"{BASE}/login")
                page.fill("input[type=email]", f"{base.PFX}_t@test.invalid")
                page.fill("input[type=password]", base.PWD)
                page.click("button[type=submit]")
                page.wait_for_url("**/teacher/**", timeout=30000)
                page.goto(f"{BASE}/teacher/students/{sid}#report")
                page.wait_for_timeout(1500)
                for btn in ("Daha sonra", "Kapat"):
                    loc = page.get_by_role("button", name=btn)
                    if loc.count():
                        try:
                            loc.first.click(timeout=1000)
                        except Exception:
                            pass
                rep = page.locator("[data-section=dev-report]")
                rep.wait_for(timeout=30000)
                if scheme == "light":
                    tab = page.get_by_role("tab", name="Gelişim Raporu", exact=True)
                    check("1 üst menüde Gelişim Raporu sekmesi seçili", tab.get_attribute("aria-selected") == "true")
                    check("1b Koçluk sekmesi artık Alışkanlıklar",
                          page.get_by_role("tab", name="Alışkanlıklar").count() == 1)
                    check("2a başlık", page.locator("[data-testid=dev-report-headline]").count() == 1)
                    check("2b hafta tablosu ≥8 satır",
                          page.locator("[data-testid=dev-report-weeks] tbody tr").count() >= 8)
                    for t in ("Mevcut durum", "Güçlü yanlar", "Fırsatlar", "Riskler", "Aksiyon planı"):
                        check(f"2c bölüm: {t}", rep.get_by_text(t, exact=False).first.is_visible())
                    rep.get_by_label("Görev uyumu geçmişin en kötüsü seans gündemine eklenecek").first.check()
                    page.locator("[data-testid=dev-report-actions] input[type=checkbox]").first.check()
                    bar = page.locator("[data-testid=dev-report-bar]")
                    check("3a alt çubuk 2 seçili", "2 madde seçili" in bar.inner_text(), bar.inner_text()[:80])
                    bar.get_by_role("button", name="Seansa ekle (2)").click()
                    page.wait_for_timeout(2500)
                    check("3b seans gündeminde işareti", rep.get_by_text("Seans gündeminde").count() >= 2)
                    check("4a taşma yok 1440", overflow(page) <= 1, str(overflow(page)))
                    page.screenshot(path=os.path.join(SHOTS, "dev_report_light.png"), full_page=True)
                    page.set_viewport_size({"width": 390, "height": 900})
                    page.wait_for_timeout(600)
                    check("4b taşma yok 390", overflow(page) <= 1, str(overflow(page)))
                    page.screenshot(path=os.path.join(SHOTS, "dev_report_mobile.png"), full_page=True)
                else:
                    page.screenshot(path=os.path.join(SHOTS, "dev_report_dark.png"), full_page=True)
                    check("4c koyu tema render", rep.is_visible())
                ctx.close()
            br.close()
    finally:
        base.cleanup()
    print(f"\n{ok} geçti, {len(bad)} kaldı")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
