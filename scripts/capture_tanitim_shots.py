# -*- coding: utf-8 -*-
"""Doküman kareleri — sağlam sürüm: girişi DOĞRULA, sayfa hazır olmadan çekme.

Kullanım: python capture_doc_shots2.py [koc|kurum]
"""
from __future__ import annotations

import sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / ".doc-build" / "docshots"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:3000"

WHO = sys.argv[1] if len(sys.argv) > 1 else "koc"
CRED = {
    "koc": ("rehber-koc@etutkoc.demo", "RehberDemo2026!", "**/teacher/**"),
    "kurum": ("admin@atlas-etut-video-demo.demo", "VideoDemo2026!", "**/institution**"),
}[WHO]

ELIF = 228
KOC_PAGES = [
    ("koc-analitik", f"/teacher/students/{ELIF}#analytics", 0),
    ("koc-analitik-alt", f"/teacher/students/{ELIF}#analytics", 980),
    ("koc-mufredat", f"/teacher/students/{ELIF}#curriculum", 320),
    ("koc-konu-perf", f"/teacher/students/{ELIF}#topics", 240),
    ("koc-yanlislar", f"/teacher/students/{ELIF}#wrongs", 200),
    ("koc-seanslar", f"/teacher/students/{ELIF}#sessions", 180),
    ("koc-anketler", f"/teacher/students/{ELIF}#surveys", 160),
    ("koc-tahsilat", "/teacher/billing", 0),
    ("koc-talepler", "/teacher/requests", 0),
    ("koc-toplu-wa", "/teacher/bulk-wa", 0),
    ("koc-paket", "/teacher/plan", 0),
    ("koc-randevu", "/teacher/appointments", 0),
    ("koc-dna", f"/teacher/students/{ELIF}/dna", 220),
    ("koc-hedefler", f"/teacher/students/{ELIF}/goals", 0),
    ("koc-tekrar", f"/teacher/students/{ELIF}/review", 0),
    ("koc-odak", f"/teacher/students/{ELIF}/focus", 0),
]
KURUM_PAGES = [
    ("kurum-panel", "/institution", 0),
    ("kurum-panel-koclar", "/institution", 720),
    ("kurum-risk", "/institution/at-risk", 0),
    ("kurum-tukenmislik", "/institution/burnout", 0),
    ("kurum-kohort", "/institution/cohorts", 0),
    ("kurum-aktivite", "/institution/activity-heatmap", 0),
    ("kurum-veli-guveni", "/institution/parent-trust", 0),
    ("kurum-hedefler", "/institution/goals", 0),
    ("kurum-ozet", "/institution/admin-digest", 0),
    ("kurum-ogretmenler", "/institution/teachers", 0),
    ("kurum-bagimsiz", "/institution/self-study", 0),
    ("kurum-kullanim", "/institution/usage", 0),
    ("kurum-uyum2", "/institution/compliance", 640),
    ("kurum-mudahale2", "/institution/action-center", 0),
    ("kurum-karne2", "/institution/teacher-scorecard", 0),
    ("kurum-akademik2", "/institution/academic", 0),
]
PAGES = KOC_PAGES if WHO == "koc" else KURUM_PAGES

with sync_playwright() as pw:
    br = pw.chromium.launch(channel="chrome")
    ctx = br.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(
        "const s=document.createElement('style');"
        "s.textContent='[class*=tsqd]{display:none!important}nextjs-portal{display:none!important}';"
        "document.addEventListener('DOMContentLoaded',()=>document.head.appendChild(s));"
    )
    p = ctx.new_page()
    email, pwd, url_glob = CRED
    # ısınma: ilk derleme yavaş; hydration bitmeden submit native POST olur
    p.goto(BASE + "/login", timeout=180_000, wait_until="domcontentloaded")
    p.wait_for_load_state("networkidle", timeout=120_000)
    time.sleep(3.0)
    p.locator('input[type="email"]').fill(email)
    p.locator('input[type="password"]').fill(pwd)
    p.locator('button[type="submit"]').first.click()
    try:
        p.wait_for_url(url_glob, timeout=60_000)
    except Exception:
        print(f"!! GİRİŞ BAŞARISIZ ({email}) — url: {p.url}")
        p.screenshot(path=str(OUT / f"_login-fail-{WHO}.png"))
        br.close()
        raise SystemExit(1)
    time.sleep(2.5)
    print(f"giriş OK: {email}")

    ok = 0
    for name, path, scroll in PAGES:
        try:
            p.goto(BASE + path, timeout=120_000, wait_until="domcontentloaded")
            # ana içerik gelene kadar bekle (yükleniyor/boş kare önlemi)
            p.wait_for_load_state("networkidle", timeout=45_000)
            time.sleep(2.0)
            # sayfada anlamlı metin var mı?
            txt = p.locator("body").inner_text()
            if len(txt.strip()) < 120 or "Giriş yap" in txt[:200]:
                time.sleep(3.0)
                txt = p.locator("body").inner_text()
            if scroll:
                p.mouse.wheel(0, scroll)
                time.sleep(1.2)
            p.screenshot(path=str(OUT / f"{name}.png"))
            size = (OUT / f"{name}.png").stat().st_size // 1024
            flag = "" if size > 25 else "  <<< ŞÜPHELİ (boş olabilir)"
            print(f"  ✓ {name}  ({size} KB){flag}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  !! {name}: {str(e)[:90]}")
    br.close()
print(f"BITTI — {ok}/{len(PAGES)}")
