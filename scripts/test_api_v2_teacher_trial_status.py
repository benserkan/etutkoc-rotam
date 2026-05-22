"""API v2 /teacher/trial-status smoke (Faz 1 — trial banner + paywall durumu).

Senaryolar:
   1. solo koç trial başında → is_solo True, trial_active, days_left~14, critical False
   2. öğrenci sayımı + limit (-1 sınırsız), over_limit False, paywall False
   3. trial son 2 gün → trial_critical True
   4. trial dolunca (expire_trials) → plan solo_free, paywall True (5>3), over_limit True
   5. kurum öğretmeni → is_solo False
   6. anonim → 401
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import Institution, User, UserRole
from app.models.plan_history import PlanChangeHistory, PlanOwnerType
from app.models.suspicious_ip import SuspiciousIp
from app.services import plans
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"trialst_{secrets.token_hex(3)}"
PWD = hash_password("TrialStatus!23")
PWDH = "TrialStatus!23"
N = 5

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
    print(f"\n=== /teacher/trial-status smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    coach_id = inst_id = inst_teacher_id = None
    student_ids: list[int] = []
    try:
        with SessionLocal() as db:
            coach = User(
                email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            db.add(coach); db.flush()
            coach_id = coach.id
            plans.start_solo_trial(db, user=coach, autocommit=False)
            db.flush()
            for i in range(N):
                db.add(User(
                    email=f"{PFX}_s{i}@test.invalid", password_hash=PWD,
                    full_name=f"{PFX} Öğr {i}", role=UserRole.STUDENT,
                    teacher_id=coach.id, institution_id=None, grade_level=8,
                    is_active=True, password_changed_at=now, must_change_password=False,
                ))
            inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-kurum", plan="free", is_active=True)
            db.add(inst); db.flush()
            inst_id = inst.id
            inst_teacher = User(
                email=f"{PFX}_instt@test.invalid", password_hash=PWD,
                full_name=f"{PFX} KurumKoç", role=UserRole.TEACHER, institution_id=inst.id,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            db.add(inst_teacher); db.flush()
            inst_teacher_id = inst_teacher.id
            db.commit()
            student_ids = [r.id for r in db.query(User).filter(
                User.teacher_id == coach_id, User.role == UserRole.STUDENT).all()]

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWDH})
        if r.status_code != 200:
            raise RuntimeError(f"login fail {r.status_code} {r.text}")

        # 1-2. trial başında
        r = c.get("/api/v2/teacher/trial-status")
        j = r.json() if r.status_code == 200 else {}
        check("1. trial başı → is_solo + trial_active + ~14 gün",
              r.status_code == 200 and j.get("is_solo") and j.get("trial_active")
              and (j.get("days_left") or 0) >= 13 and j.get("trial_critical") is False,
              f"{j}")
        check("2. öğrenci sayım/limit/paywall",
              j.get("student_count") == N and j.get("student_limit") == -1
              and j.get("over_limit") is False and j.get("paywall") is False,
              f"{j}")

        # 3. son 2 gün → critical
        with SessionLocal() as db:
            u = db.get(User, coach_id)
            u.trial_ends_at = now + timedelta(days=2)
            db.commit()
        r = c.get("/api/v2/teacher/trial-status")
        j = r.json()
        check("3. son 2 gün → trial_critical True", j.get("trial_critical") is True, f"{j}")

        # 4. trial dolunca → solo_free + paywall
        with SessionLocal() as db:
            u = db.get(User, coach_id)
            u.trial_ends_at = now - timedelta(days=1)
            db.commit()
            plans.expire_trials(db, now=now + timedelta(days=1))
        r = c.get("/api/v2/teacher/trial-status")
        j = r.json()
        check("4. trial dolunca → solo_free + paywall (5>3)",
              j.get("plan_code") == "solo_free" and j.get("paywall") is True
              and j.get("over_limit") is True and j.get("trial_active") is False
              and j.get("student_limit") == 3 and j.get("upgrade_target") == "solo_pro",
              f"{j}")

        # 5. kurum öğretmeni → is_solo False
        c2 = TestClient(app)
        r = c2.post("/api/v2/auth/login", json={"email": f"{PFX}_instt@test.invalid", "password": PWDH})
        if r.status_code == 200:
            r = c2.get("/api/v2/teacher/trial-status")
            check("5. kurum öğretmeni → is_solo False",
                  r.status_code == 200 and r.json().get("is_solo") is False, f"{r.json()}")
        else:
            check("5. kurum öğretmeni login", False, f"login {r.status_code}")

        # 6. anonim → 401
        r = TestClient(app).get("/api/v2/teacher/trial-status")
        check("6. anonim → 401", r.status_code == 401, f"status={r.status_code}")

    finally:
        with SessionLocal() as db:
            if student_ids:
                db.execute(sa_delete(User).where(User.id.in_(student_ids)))
            for uid in (coach_id, inst_teacher_id):
                if uid:
                    db.execute(sa_delete(PlanChangeHistory).where(
                        PlanChangeHistory.owner_id == uid,
                        PlanChangeHistory.owner_type == PlanOwnerType.USER))
                    db.execute(sa_delete(User).where(User.id == uid))
            if inst_id:
                db.execute(sa_delete(Institution).where(Institution.id == inst_id))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
