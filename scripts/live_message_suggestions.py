# -*- coding: utf-8 -*-
"""Bugünün mesajları + Koçlara mesajlar — gerçek tarayıcı (yerel :3000). 2026-11-14."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright  # noqa: E402

import scripts.test_api_v2_institution_message_suggestions as ibase  # noqa: E402
import scripts.test_api_v2_message_suggestions as base  # noqa: E402

BASE = "http://localhost:3000"
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".shots")
ok = 0
bad: list[str] = []


def check(n, c, extra=""):
    global ok
    print(("  [PASS] " if c else "  [FAIL] ") + n + (f" — {extra}" if extra and not c else ""))
    if c:
        ok += 1
    else:
        bad.append(n)


def overflow(page):
    return page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")


def login(page, email, pwd):
    page.goto(f"{BASE}/login")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", pwd)
    page.click("button[type=submit]")
    page.wait_for_timeout(3000)


def dismiss(page):
    for b in ("Daha sonra", "Kapat"):
        loc = page.get_by_role("button", name=b)
        try:
            if loc.count():
                loc.first.click(timeout=1000)
        except Exception:
            pass


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    d = base.seed()
    di = ibase.seed()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome")
            page = br.new_page(viewport={"width": 1440, "height": 1000})
            login(page, f"{base.PFX}_t@test.invalid", base.PWD)
            page.goto(f"{BASE}/teacher/messages")
            dismiss(page)
            page.locator("[data-testid=inbox-groups] li button").first.wait_for(timeout=60000)
            check("1 solda öğrenci listesi", page.locator("[data-testid=inbox-groups] li button").count() >= 1)
            rows = page.locator("[data-testid=msg-suggestion]")
            n0 = rows.count()
            check("2 sağda öneriler (≥3)", n0 >= 3, str(n0))
            check("3 yalnız ilki açık", page.locator("[data-testid=msg-suggestion] textarea").count() == 1)
            check("4 sayaç görünür", "Bugün 0 mesaj" in page.locator("[data-testid=msg-sent-today]").inner_text())
            check("5 taşma yok 1440", overflow(page) <= 1, str(overflow(page)))
            page.screenshot(path=os.path.join(SHOTS, "messages_desktop.png"), full_page=True)
            page.select_option("select[aria-label=Kime]", "parent")
            nv = page.locator("[data-testid=msg-suggestion]").count()
            check("6 Kime=Veliye süzgeci daraltır", 0 < nv < n0, f"{nv}/{n0}")
            page.select_option("select[aria-label=Kime]", "all")
            page.locator("[data-testid=msg-suggestion]").first.get_by_role("button", name="Atla").click()
            page.wait_for_timeout(2500)
            n1 = page.locator("[data-testid=msg-suggestion]").count()
            check("7 atlanan düştü, sıradaki açık", n1 == n0 - 1 and page.locator("[data-testid=msg-suggestion] textarea").count() == 1,
                  f"{n0}->{n1}")
            page.fill("input[aria-label='öğrenci ara']", "zzzz")
            check("8 arama listeyi süzer", page.get_by_text("Aramaya uyan öğrenci yok").count() == 1)
            page.fill("input[aria-label='öğrenci ara']", "")
            page.set_viewport_size({"width": 390, "height": 900})
            page.goto(f"{BASE}/teacher/messages")
            page.locator("[data-testid=inbox-groups] li button").first.wait_for(timeout=60000)
            check("9 telefonda önce liste, ayrıntı gizli", not page.locator("[data-testid=inbox-detail]").is_visible())
            page.locator("[data-testid=inbox-groups] li button").first.click()
            check("10 dokununca ayrıntı + geri düğmesi",
                  page.locator("[data-testid=inbox-detail]").is_visible() and page.get_by_role("button", name="Liste").is_visible())
            check("11 taşma yok 390", overflow(page) <= 1, str(overflow(page)))
            page.screenshot(path=os.path.join(SHOTS, "messages_mobile.png"), full_page=True)

            page2 = br.new_page(viewport={"width": 1440, "height": 1000})
            login(page2, f"{ibase.PFX}_a@test.invalid", ibase.PWD)
            page2.goto(f"{BASE}/institution/messages")
            dismiss(page2)
            page2.locator("[data-testid=inbox-groups] li button").first.wait_for(timeout=60000)
            check("12 kurum: koç listesi", page2.locator("[data-testid=inbox-groups]").inner_text().count("Ayşe c") >= 1)
            check("13 kurum: koça öneri + Hocam", "Hocam" in page2.locator("[data-testid=msg-suggestion] textarea").first.input_value())
            check("14 kurum menüsünde Koçlara mesajlar", page2.get_by_role("link", name="Koçlara mesajlar").count() >= 1)
            page2.screenshot(path=os.path.join(SHOTS, "inst_messages_desktop.png"), full_page=True)
            br.close()
    finally:
        base.cleanup(d)
        ibase.cleanup(di)
    print(f"\n{ok} geçti, {len(bad)} kaldı")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
