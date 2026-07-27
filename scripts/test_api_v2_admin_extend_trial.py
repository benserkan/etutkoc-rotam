# -*- coding: utf-8 -*-
"""API v2 süper admin deneme uzatma smoke (POST /admin/users/{id}/extend-trial).

Senaryolar:
   1. anonim 401 · koç 403 (yalnız süper admin)
   2. denemesi bitmiş koç (solo_free) → +14 gün: plan=solo_trial, bitiş ~+14g
   3. post_trial_plan KORUNUR (solo_pro signup ön-seçimi kaybolmaz)
   4. uzatma sonrası deneme aktif + AI kapısı açılır (ai_premium_allowed)
   5. aktif denemede uzatma → mevcut bitişin ÜZERİNE eklenir
   6. intended_plan=solo_elite → post_trial_plan güncellenir
   7. geçersiz intended_plan → 400 invalid_plan
   8. ücretli aktif abone → 409 paid_subscription_active (ödeyen müşteri korunur)
   9. kurumlu öğretmen → 400 not_solo_teacher · öğrenci hedef → 400
  10. PlanChangeHistory ADMIN_OVERRIDE kaydı yazılır
  11. expire_trials yeni bitişte koçu yine solo_free'ye düşürür (cron uyumu)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import Institution, User, UserRole
from app.models.plan_history import PlanChangeHistory, PlanChangeReason, PlanOwnerType
from app.models.suspicious_ip import SuspiciousIp
from app.services import plans
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"exttrial_{secrets.token_hex(3)}"
PWDH = "ExtendTrial!2345"
PWD = hash_password(PWDH)

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


def login(c: TestClient, email: str):
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWDH})
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text[:200]}"


def aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> int:
    print(f"\n=== admin extend-trial smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    ids: list[int] = []
    inst_id = None
    try:
        with SessionLocal() as db:
            admin = User(
                email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            # denemesi bitmiş koç (Hatice senaryosu): solo_free + intended solo_pro
            coach = User(
                email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                plan="solo_free", trial_ends_at=None, post_trial_plan="solo_pro",
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            paid = User(
                email=f"{PFX}_paid@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Paid", role=UserRole.TEACHER, institution_id=None,
                plan="solo_pro", subscription_status="active",
                subscription_period_end=now + timedelta(days=20),
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            student = User(
                email=f"{PFX}_stu@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Öğr", role=UserRole.STUDENT, grade_level=8,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            inst = Institution(name=f"{PFX} K", slug=f"{PFX}-k", plan="free", is_active=True)
            db.add_all([admin, coach, paid, student, inst])
            db.flush()
            inst_id = inst.id
            inst_teacher = User(
                email=f"{PFX}_instt@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Kurumlu", role=UserRole.TEACHER,
                institution_id=inst.id,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            db.add(inst_teacher)
            db.flush()
            ids = [admin.id, coach.id, paid.id, student.id, inst_teacher.id]
            admin_id, coach_id, paid_id, stu_id, instt_id = ids
            db.commit()

        anon = TestClient(app)
        r = anon.post(f"/api/v2/admin/users/{coach_id}/extend-trial", json={"days": 14})
        ok1 = r.status_code == 401
        cclient = TestClient(app)
        login(cclient, f"{PFX}_coach@test.invalid")
        r2 = cclient.post(f"/api/v2/admin/users/{coach_id}/extend-trial", json={"days": 14})
        check("1. anonim 401 + koç 403", ok1 and r2.status_code == 403,
              f"{r.status_code}/{r2.status_code}")

        adm = TestClient(app)
        login(adm, f"{PFX}_admin@test.invalid")

        r = adm.post(f"/api/v2/admin/users/{coach_id}/extend-trial", json={"days": 14})
        with SessionLocal() as db:
            c = db.get(User, coach_id)
            ends = aware(c.trial_ends_at)
            delta_days = (ends - now).days if ends else -1
            check("2. bitmiş koç +14g → solo_trial + bitiş ~14 gün sonra",
                  r.status_code == 200 and c.plan == "solo_trial" and 13 <= delta_days <= 14,
                  f"{r.status_code} plan={c.plan} delta={delta_days}")
            check("3. post_trial_plan korunur (solo_pro)",
                  c.post_trial_plan == "solo_pro", c.post_trial_plan)
            active = plans.is_trial_active(c)
            check("4. deneme aktif + AI kapısı açık",
                  active and plans.ai_premium_allowed(db, c),
                  f"trial_active={active}")
            first_end = ends

        r = adm.post(f"/api/v2/admin/users/{coach_id}/extend-trial", json={"days": 7})
        with SessionLocal() as db:
            c = db.get(User, coach_id)
            ends2 = aware(c.trial_ends_at)
            check("5. aktif denemede +7g → bitişin üzerine eklenir",
                  r.status_code == 200 and abs((ends2 - first_end).days - 7) <= 0,
                  f"{first_end} → {ends2}")

        r = adm.post(f"/api/v2/admin/users/{coach_id}/extend-trial",
                     json={"days": 3, "intended_plan": "solo_elite"})
        with SessionLocal() as db:
            c = db.get(User, coach_id)
            check("6. intended_plan=solo_elite → ön-seçim güncellenir",
                  r.status_code == 200 and c.post_trial_plan == "solo_elite",
                  f"{r.status_code} {c.post_trial_plan}")

        r = adm.post(f"/api/v2/admin/users/{coach_id}/extend-trial",
                     json={"days": 3, "intended_plan": "solo_free"})
        check("7. geçersiz intended_plan → 400 invalid_plan",
              r.status_code == 400 and r.json()["detail"]["code"] == "invalid_plan",
              f"{r.status_code} {r.text[:120]}")

        r = adm.post(f"/api/v2/admin/users/{paid_id}/extend-trial", json={"days": 14})
        check("8. ücretli aktif abone → 409 paid_subscription_active",
              r.status_code == 409 and r.json()["detail"]["code"] == "paid_subscription_active",
              f"{r.status_code} {r.text[:120]}")

        r = adm.post(f"/api/v2/admin/users/{instt_id}/extend-trial", json={"days": 14})
        r2 = adm.post(f"/api/v2/admin/users/{stu_id}/extend-trial", json={"days": 14})
        check("9. kurumlu öğretmen + öğrenci → 400 not_solo_teacher",
              r.status_code == 400 and r2.status_code == 400
              and r.json()["detail"]["code"] == "not_solo_teacher",
              f"{r.status_code}/{r2.status_code}")

        with SessionLocal() as db:
            rows = (
                db.query(PlanChangeHistory)
                .filter(
                    PlanChangeHistory.owner_type == PlanOwnerType.USER,
                    PlanChangeHistory.owner_id == coach_id,
                    PlanChangeHistory.reason == PlanChangeReason.ADMIN_OVERRIDE,
                )
                .all()
            )
            check("10. PlanChangeHistory ADMIN_OVERRIDE kaydı",
                  len(rows) >= 3 and "uzatıldı" in (rows[-1].note or ""),
                  f"n={len(rows)}")

        with SessionLocal() as db:
            c = db.get(User, coach_id)
            future = aware(c.trial_ends_at) + timedelta(hours=1)
            plans.expire_trials(db, now=future)
            db.commit()
        with SessionLocal() as db:
            c = db.get(User, coach_id)
            check("11. expire_trials yeni bitişte yine solo_free'ye düşürür",
                  c.plan == "solo_free", c.plan)

    finally:
        with SessionLocal() as db:
            if ids:
                db.execute(sa_delete(PlanChangeHistory).where(
                    PlanChangeHistory.owner_type == PlanOwnerType.USER,
                    PlanChangeHistory.owner_id.in_(ids)))
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            if inst_id:
                db.execute(sa_delete(Institution).where(Institution.id == inst_id))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n  Sonuç: {passed} PASS / {len(failed)} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
