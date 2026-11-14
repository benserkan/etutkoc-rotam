# -*- coding: utf-8 -*-
"""Bugünün mesajları — gerçek tarayıcı (yerel :3000). 2026-11-14."""
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


def main() -> int:
    os.makedirs(SHOTS, exist_ok=True)
    d = base.seed()
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome")
            page = br.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(f"{BASE}/login")
            page.fill("input[type=email]", f"{base.PFX}_t@test.invalid")
            page.fill("input[type=password]", base.PWD)
            page.click("button[type=submit]")
            page.wait_for_url("**/teacher/**", timeout=30000)
            page.goto(f"{BASE}/teacher/messages")
            for b in ("Daha sonra", "Kapat"):
                loc = page.get_by_role("button", name=b)
                try:
                    if loc.count():
                        loc.first.click(timeout=1000)
                except Exception:
                    pass
            page.locator("[data-testid=msg-suggestion]").first.wait_for(timeout=60000)
            n0 = page.locator("[data-testid=msg-suggestion]").count()
            check("1 öneriler listelendi (≥3)", n0 >= 3, str(n0))
            check("2 sayaç görünür", "Bugün 0 mesaj" in page.locator("[data-testid=msg-sent-today]").inner_text())
            check("3 menüde Bugünün mesajları", page.get_by_role("link", name="Bugünün mesajları").count() >= 1)
            check("4 rapor bağlantısı notu", page.get_by_text("gerçek bağlantısıyla değiştirilir").count() >= 1)
            check("5 taşma yok 1440", overflow(page) <= 1, str(overflow(page)))
            page.screenshot(path=os.path.join(SHOTS, "messages_desktop.png"), full_page=True)
            page.get_by_role("tab", name="Veliye").click()
            nv = page.locator("[data-testid=msg-suggestion]").count()
            check("6 Veliye süzgeci daraltır", 0 < nv < n0, f"{nv}/{n0}")
            page.get_by_role("tab", name="Tümü").click()
            page.locator("[data-testid=msg-suggestion]").first.get_by_role("button", name="Atla").click()
            page.wait_for_timeout(2500)
            n1 = page.locator("[data-testid=msg-suggestion]").count()
            check("7 atlanan kart düştü", n1 == n0 - 1, f"{n0}->{n1}")
            page.goto(f"{BASE}/teacher/messages?student={d['s']}")
            page.locator("[data-testid=msg-suggestion]").first.wait_for(timeout=60000)
            check("8 öğrenci süzgeçli adres çalışır", page.locator("[data-testid=msg-suggestion]").count() == n1)
            page.set_viewport_size({"width": 390, "height": 900})
            page.wait_for_timeout(600)
            check("9 taşma yok 390", overflow(page) <= 1, str(overflow(page)))
            page.screenshot(path=os.path.join(SHOTS, "messages_mobile.png"), full_page=True)
            br.close()
    finally:
        base.cleanup(d)
    print(f"\n{ok} geçti, {len(bad)} kaldı")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
