"""API v2 solo abonelik durumu + yenileme döngüsü smoke (Abonelik Faz 3).

Senaryolar:
   1. admin activate-plan solo_pro monthly → status=active + period_end ~30g + cycle
   2. /teacher/plan → status active + subscription_period_end dolu
   3. period_end geçmişe alınır → process_renewals → koç past_due
   4. past_due → trial-status paywall+past_due True; publish-day → 403 paywall_active
   5. admin yeniden aktive → active, past_due değil, paywall False
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.models.plan_history import PlanChangeHistory, PlanOwnerType
from app.models.suspicious_ip import SuspiciousIp
from app.services import trial_notifications as tn
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"subrenew_{secrets.token_hex(3)}"
PWD = hash_password("SubRenew!23x")
PWDH = "SubRenew!23x"

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


def main() -> int:
    print(f"\n=== solo abonelik yenileme smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    ids: dict[str, int] = {}
    coach_email = f"{PFX}_coach@test.invalid"
    try:
        with SessionLocal() as db:
            coach = User(email=coach_email, password_hash=PWD, full_name=f"{PFX} Koç",
                         role=UserRole.TEACHER, institution_id=None, is_active=True,
                         plan="solo_trial", trial_ends_at=now + timedelta(days=5),
                         post_trial_plan="solo_free",
                         password_changed_at=now, must_change_password=False)
            db.add(coach); db.flush()
            stu = User(email=f"{PFX}_s@test.invalid", password_hash=PWD,
                       full_name=f"{PFX} Öğr", role=UserRole.STUDENT, teacher_id=coach.id,
                       institution_id=None, grade_level=8, is_active=True,
                       password_changed_at=now, must_change_password=False)
            db.add(stu)
            admin = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                         full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
                         password_changed_at=now, must_change_password=False)
            db.add(admin)
            db.commit()
            ids = {"coach": coach.id, "stu": stu.id, "admin": admin.id}

        def login(email):
            c = TestClient(app)
            r = c.post("/api/v2/auth/login", json={"email": email, "password": PWDH})
            if r.status_code != 200:
                raise RuntimeError(f"login {email}: {r.status_code} {r.text[:120]}")
            return c

        admin_cli = login(f"{PFX}_admin@test.invalid")
        coach_cli = login(coach_email)

        # 1. activate solo_pro monthly
        r = admin_cli.post(f"/api/v2/admin/users/{ids['coach']}/activate-plan",
                           json={"plan": "solo_pro", "cycle": "monthly"})
        ok1 = r.status_code == 200
        with SessionLocal() as db:
            c = db.get(User, ids["coach"])
            pe_ok = c.subscription_period_end is not None and 28 <= (c.subscription_period_end.replace(tzinfo=timezone.utc) - now).days <= 31
            ok1 = ok1 and c.plan == "solo_pro" and c.subscription_status == "active" and c.subscription_cycle == "monthly" and pe_ok
            trial_cleared = c.trial_ends_at is None
        check("1. activate solo_pro monthly → active + ~30g period_end + cycle", ok1, f"{r.text[:120]}")
        check("1b. aktivasyon trial_ends_at'i temizledi (trialing'e düşmez)", trial_cleared,
              "trial_ends_at hâlâ dolu")

        # 2. /teacher/plan
        r = coach_cli.get("/api/v2/teacher/plan")
        j = r.json()
        check("2. /teacher/plan → status active + period_end",
              r.status_code == 200 and j.get("status") == "active" and bool(j.get("subscription_period_end")),
              f"{j.get('status')} pe={j.get('subscription_period_end')}")

        # 3. period_end geçmişe → process_renewals → past_due
        with SessionLocal() as db:
            c = db.get(User, ids["coach"])
            c.subscription_period_end = now - timedelta(days=1)
            db.commit()
        with SessionLocal() as db:
            res = tn.process_renewals(db, now=now)
            c = db.get(User, ids["coach"])
            check("3. process_renewals → koç past_due", c.subscription_status == "past_due",
                  f"status={c.subscription_status} res={res}")

        # 4. past_due paywall
        r = coach_cli.get("/api/v2/teacher/trial-status")
        j = r.json()
        check("4a. trial-status → paywall + past_due True",
              j.get("paywall") is True and j.get("past_due") is True, f"{j}")
        r = coach_cli.post(f"/api/v2/teacher/students/{ids['stu']}/publish-day",
                           json={"task_date": date.today().isoformat()})
        code = (r.json().get("detail", {}) or {}).get("code") if r.status_code == 403 else None
        check("4b. past_due publish-day → 403 paywall_active",
              r.status_code == 403 and code == "paywall_active", f"status={r.status_code}")

        # 5. yeniden aktive → past_due kalkar
        r = admin_cli.post(f"/api/v2/admin/users/{ids['coach']}/activate-plan",
                           json={"plan": "solo_pro", "cycle": "monthly"})
        with SessionLocal() as db:
            c = db.get(User, ids["coach"])
            ok5 = c.subscription_status == "active" and c.subscription_period_end.replace(tzinfo=timezone.utc) > now
        r2 = coach_cli.get("/api/v2/teacher/trial-status")
        check("5. yeniden aktive → active + paywall False",
              r.status_code == 200 and ok5 and r2.json().get("paywall") is False,
              f"activate={r.status_code} ts_paywall={r2.json().get('paywall')}")

        # 6. koç iptal → canceled (plan korunur)
        r = coach_cli.post("/api/v2/teacher/subscription/cancel")
        with SessionLocal() as db:
            c = db.get(User, ids["coach"])
            ok6 = c.subscription_status == "canceled" and c.plan == "solo_pro"
        check("6. iptal → canceled + plan solo_pro korunur", r.status_code == 200 and ok6, f"{r.text[:120]}")

        # 7. /teacher/plan → status active + subscription_status canceled
        j = coach_cli.get("/api/v2/teacher/plan").json()
        check("7. /teacher/plan → active + subscription_status canceled",
              j.get("status") == "active" and j.get("subscription_status") == "canceled", f"{j.get('status')}/{j.get('subscription_status')}")

        # 8. geri al → active
        r = coach_cli.post("/api/v2/teacher/subscription/resume")
        with SessionLocal() as db:
            ok8 = db.get(User, ids["coach"]).subscription_status == "active"
        check("8. resume → active", r.status_code == 200 and ok8, f"{r.text[:120]}")

        # 9. iptal + dönem sonu geçmiş → process_renewals → solo_free + temizlenir
        coach_cli.post("/api/v2/teacher/subscription/cancel")
        with SessionLocal() as db:
            c = db.get(User, ids["coach"]); c.subscription_period_end = now - timedelta(days=1); db.commit()
        with SessionLocal() as db:
            res = tn.process_renewals(db, now=now)
            c = db.get(User, ids["coach"])
            ok9 = c.plan == "solo_free" and c.subscription_status is None and c.subscription_period_end is None
        check("9. iptal+dönem sonu → solo_free + sub temizlendi (past_due DEĞİL)", ok9,
              f"plan={c.plan} status={c.subscription_status} res={res}")

        # 10. aktif abonelik yokken iptal → 400
        r = coach_cli.post("/api/v2/teacher/subscription/cancel")
        check("10. aktif abonelik yokken iptal → 400 no_active_subscription",
              r.status_code == 400 and r.json()["detail"]["code"] == "no_active_subscription", f"status={r.status_code}")

    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(User).where(User.id == ids.get("stu", 0)))
            for key in ("coach", "admin"):
                uid = ids.get(key)
                if uid:
                    db.execute(sa_delete(PlanChangeHistory).where(
                        PlanChangeHistory.owner_id == uid,
                        PlanChangeHistory.owner_type == PlanOwnerType.USER))
                    db.execute(sa_delete(User).where(User.id == uid))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
