"""Görüşmeler sayfası yeni tasarım — canlı tarayıcı testi (2026-09-29).

Kendi verisini kurar/temizler. Dev sunucular (:3000 + :8081) açık olmalı.
Ekran görüntüleri: .shots/appointments_light.png, .shots/appointments_dark_mobile.png
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.appointment import CoachingAppointment
from app.services.appointment_service import now_tr
from app.services.security import hash_password

sys.path.insert(0, os.path.dirname(__file__))
from lib_live_contrast import measure  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lap_{secrets.token_hex(3)}"
PWD = "LiveAppt!2345"
SHOT_DIR = os.path.join(os.path.dirname(__file__), "..", ".shots")
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []
d: dict = {}


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed():
    today = now_tr().date()
    with SessionLocal() as db:
        c = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                 full_name="Görüşme Koç", role=UserRole.TEACHER, is_active=True,
                 plan="solo_unlimited", subscription_status="active")
        db.add(c)
        db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                 full_name="Selin Uzunadlı Görüşmeöğrencisi", role=UserRole.STUDENT,
                 teacher_id=c.id, grade_level=12, is_active=True,
                 created_at=now - timedelta(days=30))
        db.add(s)
        db.flush()
        up = CoachingAppointment(coach_id=c.id, student_id=s.id, date=today + timedelta(days=1),
                                 start_time="17:00", duration_min=40, status="scheduled",
                                 source="coach", meeting_link="https://meet.google.com/abc-defg-hij",
                                 link_source="manual", note="Deneme analizini konuşacağız")
        past = CoachingAppointment(coach_id=c.id, student_id=s.id,
                                   date=today - timedelta(days=1) if today.weekday() > 0 else today,
                                   start_time="00:05", duration_min=40, status="scheduled", source="coach")
        pend = CoachingAppointment(coach_id=c.id, student_id=s.id, date=today + timedelta(days=2),
                                   start_time="18:00", duration_min=40, status="pending",
                                   source="student", requested_by_id=s.id,
                                   request_note="Sınav öncesi kısa bir görüşme rica ediyorum")
        db.add_all([up, past, pend])
        db.commit()
        d.update(coach=c.id, student=s.id, email=c.email, up=up.id, past=past.id, pend=pend.id)


def status(aid):
    with SessionLocal() as db:
        return db.get(CoachingAppointment, aid).status


def cleanup():
    with SessionLocal() as db:
        db.execute(sa_delete(CoachingAppointment).where(CoachingAppointment.coach_id == d.get("coach", 0)))
        db.execute(sa_delete(User).where(User.id.in_([d.get("student", 0), d.get("coach", 0)])))
        db.commit()


def main() -> int:
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOT_DIR, exist_ok=True)
    seed()
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome", headless=True)
            ctx = br.new_context(viewport={"width": 1400, "height": 1100})
            pg = ctx.new_page()
            pg.goto(f"{BASE}/login", wait_until="networkidle")
            pg.fill('input[type="email"]', d["email"])
            pg.fill('input[type="password"]', PWD)
            pg.click('button[type="submit"]')
            pg.wait_for_timeout(4000)
            pg.goto(f"{BASE}/teacher/appointments", wait_until="networkidle")
            pg.wait_for_timeout(2500)
            later = pg.get_by_role("button", name="Daha sonra")
            if later.count():
                later.first.click()
                pg.wait_for_timeout(500)

            nxt = pg.locator('[data-testid="appt-next"]')
            chk("1 sıradaki görüşme kartı + Katıl", nxt.count() == 1
                and "Görüşmeöğrencisi" in nxt.inner_text() and "Görüşmeye katıl" in nxt.inner_text(),
                nxt.inner_text() if nxt.count() else "")
            body = pg.locator("main").inner_text()
            chk("2 özet: 1 onay bekleyen istek", "Onay bekleyen istek" in body)
            chk("3 haftalık görünüm 7 gün", pg.locator('[data-testid="appt-day"]').count() == 7)
            cards = pg.locator('[data-testid="appt-card"]')
            chk("4 geçmiş planlı görüşmede 'Seansı kaydet'",
                any("Seansı kaydet" in cards.nth(i).inner_text() for i in range(cards.count())))
            chk("5 istekte öğrenci notu tam", "Sınav öncesi kısa bir görüşme rica ediyorum" in body)
            chk("6 yatay taşma yok", not pg.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            ell = pg.evaluate("""() => [...document.querySelectorAll('main *')]
                .filter(e => e.children.length === 0 && e.scrollWidth > e.clientWidth + 1
                        && getComputedStyle(e).textOverflow === 'ellipsis').length""")
            chk("7 kırpılmış metin yok", ell == 0, str(ell))
            widths = pg.evaluate("""() => [...document.querySelectorAll('[data-testid="appt-card"]')]
                .map(e => Math.round(e.getBoundingClientRect().width))""")
            chk("7b kart genişliği okunur (>=220px, ad hece ortasından bölünmez)",
                widths and min(widths) >= 220, str(widths))
            pg.screenshot(path=os.path.join(SHOT_DIR, "appointments_light.png"), full_page=True)

            # İstek reddi — tarayıcı istemi değil diyalog
            pend = pg.locator('[data-testid="appt-pending"] li').first
            pend.get_by_role("button", name="Reddet").click()
            pg.fill('[data-testid="ask-reason"]', "Bu saat dolu, başka gün bakalım.")
            pg.click('[data-testid="ask-confirm"]')
            pg.wait_for_timeout(2500)
            chk("8 istek diyalogla reddedildi", status(d["pend"]) == "rejected", status(d["pend"]))

            # Yarınki görüşmeyi iptal et
            up_card = [cards.nth(i) for i in range(cards.count()) if "Katıl" in cards.nth(i).inner_text()]
            if up_card:
                up_card[0].get_by_role("button", name="İptal").click()
                pg.click('[data-testid="ask-confirm"]')
                pg.wait_for_timeout(2500)
            chk("9 görüşme diyalogla iptal edildi", status(d["up"]) == "cancelled", status(d["up"]))

            pg.get_by_role("button", name="Sonraki hafta").click()
            pg.wait_for_timeout(2000)
            chk("10 sonraki hafta gezinmesi", pg.locator('[data-testid="appt-day"]').count() == 7
                and pg.get_by_role("button", name="Bu hafta").is_enabled())

            dctx = br.new_context(viewport={"width": 390, "height": 900}, color_scheme="dark",
                                  storage_state=ctx.storage_state())
            dp = dctx.new_page()
            dp.goto(f"{BASE}/teacher/appointments", wait_until="networkidle")
            dp.wait_for_timeout(2500)
            dp.evaluate("() => document.documentElement.classList.add('dark')")
            dp.wait_for_timeout(300)
            chk("11 390px yatay taşma yok", not dp.evaluate(
                "() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1"))
            bad = measure(dp, '[data-section="appointments:calendar"]', min_ratio=3.0)["bad"]
            chk("12 koyu tema takvim kontrastı", bad == 0, str(bad))
            dp.screenshot(path=os.path.join(SHOT_DIR, "appointments_dark_mobile.png"), full_page=True)
            br.close()
    finally:
        cleanup()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
