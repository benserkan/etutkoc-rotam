"""Hafta planı "Geçen haftadan eksikler" (Devret) kartları koyu temada okunur mu —
GERÇEK TARAYICI (2026-10-11, koç: "hiç okunmuyor").

Kartlar sabit beyaz zemindeydi (bg-white), yazılar koyu temada açık renge
dönüyordu. Test: geçen haftaya yapılmamış bir etkinlik görevi kurar, koyu temada
Devret bölümünü açar, kart metinlerinin kontrastını ölçer (açık temada da).
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import SuspiciousIp, Task, TaskType, User, UserRole  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from scripts.lib_live_contrast import measure  # noqa: E402

WEB = "http://localhost:3000"
PFX = f"cod_{secrets.token_hex(3)}"
PWD = "DevretKoyu!2345"
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


def seed() -> dict:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Devret Koç", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Devret Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12)
        db.add(st)
        db.flush()
        for i, title in enumerate(["TYT Türkçe · Ses Bilgisi Çalışması 3 Test",
                                   "AYT Matematik · Barış Polinomlar Denemesi 2 Deneme"]):
            db.add(Task(student_id=st.id, date=today - timedelta(days=2 + i), type=TaskType.OTHER,
                        title=title, is_draft=False, status="pending"))
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": f"{PFX}_t@test.invalid"}


def cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uid = [ids["coach"], ids["student"]]
        db.execute(sa_delete(Task).where(Task.student_id.in_(uid)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["127.0.0.1", "::1"])))
        db.execute(sa_delete(User).where(User.id.in_(uid)))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright

    ids = seed()
    print(f"\n=== Devret kartları — koyu/açık tema okunabilirlik (öğrenci #{ids['student']}) ===\n")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            page = b.new_page(viewport={"width": 1440, "height": 900})
            page.add_init_script("try{localStorage.setItem('lgs-theme', sessionStorage.getItem('t')||'dark')}catch(e){}")
            page.goto(f"{WEB}/login", wait_until="networkidle")
            page.fill('input[name="email"]', ids["email"])
            page.fill('input[name="password"]', PWD)
            page.click('button[type="submit"]')
            page.wait_for_timeout(6000)
            for theme in ("dark", "light"):
                page.evaluate(f"sessionStorage.setItem('t','{theme}')")
                page.goto(f"{WEB}/teacher/students/{ids['student']}/week", wait_until="networkidle")
                page.wait_for_timeout(2500)
                later = page.query_selector('button:has-text("Daha sonra")')
                if later:
                    later.click()
                    page.wait_for_timeout(600)
                if theme == "dark":
                    page.evaluate("document.documentElement.classList.add('dark')")
                else:
                    page.evaluate("document.documentElement.classList.remove('dark')")
                rail = page.wait_for_selector('[data-rail="week:carryover"]', timeout=15000)
                if rail.get_attribute("data-pinned") != "1":
                    rail.click()
                    page.wait_for_timeout(800)
                cards = page.query_selector_all('[data-section="week:carryover"] li')
                check(f"{theme}: iki eksik görev kartı görünüyor", len(cards) == 2, f"{len(cards)}")
                m = measure(page, '[data-section="week:carryover"] li', min_ratio=4.5)
                check(f"{theme}: kart metinleri okunur (≥4.5)", m["bad"] == 0, str(m["worst"][:4]))
                os.makedirs(os.path.join(ROOT, ".shots"), exist_ok=True)
                sec = page.query_selector('[data-section="week:carryover"]')
                if sec:
                    sec.screenshot(path=os.path.join(ROOT, f".shots/carryover_{theme}.png"))
            b.close()
    finally:
        cleanup(ids)
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
