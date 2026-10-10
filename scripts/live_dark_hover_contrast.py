"""Koyu tema: üzerine gelince (hover) metin okunur mu — GERÇEK TARAYICI (2026-10-10).

Koç bulgusu: öğrenci detayı Durum Özeti'nde sarı uyarı kartının üzerine gelince
zemin açık sarıya dönüyor, koyu temadaki açık yazı kayboluyordu
(`hover:bg-amber-100`, dark karşılığı yok). Bu test Durum Özeti kart tonlarını
(student-tabs.tsx SUMMARY_TONE — kaynaktan okunur) gerçek Tailwind CSS'iyle
sayfaya koyar, koyu temada fareyi üzerine getirir ve kontrastı ölçer.
"""
from __future__ import annotations

import os
import re
import secrets
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import SuspiciousIp, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PWD = "HoverKontrast!234"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def tones() -> dict[str, dict[str, str]]:
    src = open(os.path.join(ROOT, "web/components/teacher/student-tabs.tsx"), encoding="utf-8").read()
    out = {}
    for name in ("red", "amber", "green"):
        m = re.search(rf'{name}: \{{ card: "([^"]+)", title: "([^"]+)", text: "([^"]+)"', src)
        out[name] = {"card": m.group(1), "title": m.group(2), "text": m.group(3)}
    return out


def main() -> int:
    from playwright.sync_api import sync_playwright

    email = f"hov_{secrets.token_hex(3)}@test.invalid"
    with SessionLocal() as db:
        u = User(email=email, password_hash=hash_password(PWD), full_name="Hover Koç",
                 role=UserRole.TEACHER, is_active=True)
        db.add(u)
        db.commit()
        uid = u.id
    print("\n=== Koyu tema hover kontrastı (Durum Özeti kartları) ===\n")
    try:
        T = tones()
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1280, "height": 900})
            page.add_init_script("try{localStorage.setItem('lgs-theme','dark')}catch(e){}")
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', email)
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            page.goto(f"{WEB}/teacher/dashboard", wait_until="networkidle")
            page.wait_for_timeout(1500)
            page.evaluate("document.documentElement.classList.add('dark')")
            for name, t in T.items():
                page.evaluate(
                    """([id, t]) => {
                      const a = document.createElement('a');
                      a.id = id; a.href = '#';
                      a.className = 'block rounded-lg border p-4 ' + t.card;
                      a.style.cssText = 'position:fixed;left:40px;top:40px;width:384px;z-index:99999';
                      a.innerHTML = '<div class="font-semibold ' + t.title + '">AYT Fizik sınav takvimine yetişmiyor</div>'
                        + '<div class="text-sm ' + t.text + '">Bu hızla aktif kaynaklar 22 May 2027 tarihinde biter</div>';
                      document.body.appendChild(a);
                    }""",
                    [f"hov-{name}", t],
                )
                sel = f"#hov-{name}"
                page.mouse.move(5, 890)
                page.wait_for_timeout(200)
                before = measure(page, sel, min_ratio=4.5)
                bb = page.locator(sel).bounding_box()
                page.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
                page.wait_for_timeout(400)
                after = measure(page, sel, min_ratio=4.5)
                check(f"{name}: üzerine gelmeden okunur", before["bad"] == 0, str(before["worst"]))
                check(f"{name}: üzerine gelince okunur (≥4.5)", after["bad"] == 0, str(after["worst"]))
                if name == "amber":
                    os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
                    page.screenshot(path=os.path.join(ROOT, ".shots/dark_hover_amber.png"),
                                    clip={"x": 20, "y": 20, "width": 440, "height": 140})
                page.evaluate(f"document.querySelector('{sel}').remove()")
            b.close()
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
            db.execute(sa_delete(User).where(User.id == uid))
            db.commit()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
