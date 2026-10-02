"""Canlı tarayıcı testi — paket kapasitesi uyarı/kısıtlama/teklif + Ticari 360.

Senaryo: Patika (≤10) paketindeki koçun 12 aktif öğrencisi var.
  1. Panelde kırmızı banner "12 aktif öğrencin var, Rota gerekir" + tek buton
  2. Butona tıkla → /teacher/plan?plan=solo_elite&checkout=1 → ödeme penceresi
     AÇIK gelir ("Rota paketine geç")
  3. Patika kartı pasif: "Öğrenci sayına yetmiyor"
  4. Süper admin Ticari 360: paket görünen adı, geçmiş "— → ... · kayıt",
     "Yeni üye" sağlık bandı
Dev sunucuları (:8081 + :3000) açık olmalı. Kendi verisini kurar/temizler.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright
from sqlalchemy import delete as sa_delete

sys.path.insert(0, ".")
from app.database import SessionLocal  # noqa: E402
from app.models import ActiveSession, AuditLog, PlanChangeHistory, User, UserRole  # noqa: E402
from app.models.coach_device import CoachDeviceLink  # noqa: E402
from app.models.plan_history import PlanChangeReason, PlanOwnerType  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lcap{secrets.token_hex(3)}"
PWD = "LiveCap1!@#xyz"
COACH = f"{PFX}_koc@test.invalid"
ADMIN = f"{PFX}_adm@test.invalid"
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


def seed() -> int:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        coach = User(email=COACH, password_hash=hash_password(PWD), full_name=f"{PFX} Koç",
                     role=UserRole.TEACHER, is_active=True, plan="solo_pro",
                     subscription_status="active", subscription_cycle="monthly",
                     subscription_period_end=now + timedelta(days=20),
                     subscription_platform="iyzico",
                     password_changed_at=now, must_change_password=False,
                     email_verified_at=now)
        adm = User(email=ADMIN, password_hash=hash_password(PWD), full_name="Adm",
                   role=UserRole.SUPER_ADMIN, is_active=True, password_changed_at=now,
                   must_change_password=False, email_verified_at=now)
        db.add_all([coach, adm])
        db.flush()
        for i in range(12):
            db.add(User(email=f"{PFX}_s{i}@test.invalid", password_hash="x",
                        full_name=f"Öğrenci {i}", role=UserRole.STUDENT, is_active=True,
                        grade_level=8, teacher_id=coach.id, password_changed_at=now,
                        must_change_password=False))
        db.add(PlanChangeHistory(owner_type=PlanOwnerType.USER, owner_id=coach.id,
                                 from_plan=None, to_plan="solo_trial",
                                 reason=PlanChangeReason.SIGNUP,
                                 note="14 gün ücretsiz deneme başladı · seçilen paket: Patika"))
        db.commit()
        return coach.id


def cleanup():
    with SessionLocal() as db:
        ids = [i for (i,) in db.query(User.id).filter(User.email.like(f"%{PFX}%")).all()]
        if ids:
            db.execute(sa_delete(CoachDeviceLink).where(CoachDeviceLink.user_id.in_(ids)))
            db.execute(sa_delete(PlanChangeHistory).where(PlanChangeHistory.owner_id.in_(ids)))
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(ids)))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def login(page, email):
    get_login_limiter().reset()
    page.goto(f"{BASE}/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', email)
    page.fill('input[type="password"]', PWD)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)


def main() -> int:
    print(f"\n=== CANLI: paket kapasitesi + Ticari 360 — {PFX} ===\n")
    cid = seed()
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(channel="chrome")
            page = br.new_page(viewport={"width": 1366, "height": 900})
            login(page, COACH)
            page.goto(f"{BASE}/teacher/students")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(2500)
            body = page.inner_text("body")
            check("1a. banner '12 aktif öğrencin var, Rota gerekir'",
                  "12 aktif öğrencin var, Rota gerekir" in body, body[:300])
            btn = page.get_by_role("link", name="Rota paketine geç")
            check("1b. tek tık buton görünür", btn.count() >= 1, str(btn.count()))
            page.screenshot(path=".shots/capacity_banner.png")
            btn.first.click()
            page.wait_for_url("**/teacher/plan?plan=solo_elite&checkout=1", timeout=15000)
            page.wait_for_timeout(3000)
            dlg = page.locator('[role="dialog"]')
            check("2a. ödeme penceresi açık geldi", dlg.count() >= 1 and dlg.first.is_visible(), "")
            check("2b. pencere 'Rota paketine geç'",
                  dlg.count() >= 1 and "Rota paketine geç" in dlg.first.inner_text(),
                  dlg.first.inner_text()[:150] if dlg.count() else "")
            page.screenshot(path=".shots/capacity_checkout.png")
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)
            pb = page.get_by_role("button", name="Öğrenci sayına yetmiyor")
            check("3a. Patika kartı pasif ('Öğrenci sayına yetmiyor')",
                  pb.count() == 1 and pb.first.is_disabled(), f"count={pb.count()}")
            body = page.inner_text("body")
            check("3b. kart notu '12 aktif öğrencin var — bu paket 10 öğrenci'",
                  "12 aktif öğrencin var — bu paket 10 öğrenci" in body, "")
            page.screenshot(path=".shots/capacity_plan.png", full_page=True)

            ctx2 = br.new_context(viewport={"width": 1366, "height": 900})
            p2 = ctx2.new_page()
            login(p2, ADMIN)
            p2.goto(f"{BASE}/admin/revenue/users/{cid}")
            p2.wait_for_load_state("networkidle")
            p2.wait_for_timeout(2500)
            body = p2.inner_text("body")
            check("4a. 360 başlık 'Patika' (ham kod yok)",
                  "Patika" in body and "solo_pro" not in body, body[:200])
            check("4b. sağlık 'Yeni üye'", "Yeni üye" in body, "")
            p2.get_by_role("button", name="Plan & Ödeme").click()
            p2.wait_for_timeout(1200)
            body = p2.inner_text("body")
            check("4c. geçmiş '— → 14 Gün Ücretsiz Deneme' + 'kayıt'",
                  "— → 14 Gün Ücretsiz Deneme" in body and "kayıt" in body, "")
            check("4d. öğrenci kapasitesi '12 / 10 aktif'", "12 / 10 aktif" in body, "")
            check("4e. ham 'free' / 'solo_trial' yok",
                  "free →" not in body and "solo_trial" not in body, "")
            p2.screenshot(path=".shots/revenue360_plan.png", full_page=True)
            br.close()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
