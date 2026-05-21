"""API v2 /admin/revenue analitik çekirdek smoke (D6 P7a).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. /revenue/action-center happy (items + severity_counts + total_count)
   4. /revenue/forecast happy (risk + proj_30/60/90 + scenario)
   5. /revenue/forecast?save_rate=0.75 → save_rate_pct=75
   6. /revenue/cohort happy (matrix + churn + ltv)
   7. /revenue/cohort?months_back=6&horizon=6&churn_days=30 (clamp + echo)
   8. /revenue/action-center/quick-action happy (CrmAction oluşturur)
   9. quick-action geçersiz kind → 400
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    CrmAction,
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp7a{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP7a!23"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Super", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        out = {"inst_id": inst.id, "super_id": super_admin.id, "teacher_id": teacher.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(CrmAction).where(CrmAction.institution_id == seed["inst_id"]))
        ids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/revenue analitik smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']} super={seed['super_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # ===== 1. Teacher → 403 =====
        r = tc.get("/api/v2/admin/revenue/action-center")
        check(
            "1. Teacher → 403",
            r.status_code == 403 and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 2. Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/revenue/action-center")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # ===== 3. action-center happy =====
        r = sc.get("/api/v2/admin/revenue/action-center")
        j = r.json()
        ok = (
            r.status_code == 200
            and "items" in j and "severity_counts" in j and "total_count" in j
            and {"critical", "high", "medium", "low", "positive"} <= set(j["severity_counts"].keys())
        )
        check("3. action-center happy", ok, f"status={r.status_code}")

        # ===== 4. forecast happy =====
        r = sc.get("/api/v2/admin/revenue/forecast")
        j = r.json()
        ok = (
            r.status_code == 200
            and "risk" in j and "proj_30" in j and "proj_60" in j and "proj_90" in j
            and "scenario" in j
            and "institutions" in j["risk"]
            and len(j["scenario"]["horizons"]) == 3
            and j["proj_90"]["horizon_days"] == 90
        )
        check("4. forecast happy", ok, f"status={r.status_code}")

        # ===== 5. forecast save_rate param =====
        r = sc.get("/api/v2/admin/revenue/forecast?save_rate=0.75")
        j = r.json()
        ok = r.status_code == 200 and j["save_rate_pct"] == 75 and j["scenario"]["save_rate"] == 0.75
        check("5. forecast save_rate=0.75", ok, f"status={r.status_code} pct={j.get('save_rate_pct')}")

        # ===== 6. cohort happy =====
        r = sc.get("/api/v2/admin/revenue/cohort")
        j = r.json()
        ok = (
            r.status_code == 200
            and "matrix" in j and "churn" in j and "ltv" in j
            and "cohorts" in j["matrix"]
            and "plans" in j["ltv"]
            and j["matrix"]["horizon_months"] == 12
        )
        check("6. cohort happy", ok, f"status={r.status_code}")

        # ===== 7. cohort params =====
        r = sc.get("/api/v2/admin/revenue/cohort?months_back=6&horizon=6&churn_days=30")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["months_back"] == 6 and j["horizon"] == 6 and j["churn_days"] == 30
            and j["churn"]["window_days"] == 30
        )
        check("7. cohort params echo", ok, f"status={r.status_code}")

        # ===== 8. quick-action happy =====
        r = sc.post("/api/v2/admin/revenue/action-center/quick-action", json={
            "institution_id": seed["inst_id"],
            "kind": "call",
            "summary": "Test temas görüşmesi",
            "result": "pending",
            "follow_up_days": 3,
        })
        j = r.json()
        ok = (
            r.status_code == 200
            and "Aksiyon eklendi" in j.get("data", {}).get("message", "")
            and any("revenue" in k for k in j.get("invalidate", []))
        )
        check("8. quick-action happy", ok, f"status={r.status_code} {r.text[:200]}")

        # ===== 9. quick-action invalid kind → 400 =====
        r = sc.post("/api/v2/admin/revenue/action-center/quick-action", json={
            "institution_id": seed["inst_id"],
            "kind": "not_a_real_kind",
            "summary": "x",
        })
        check(
            "9. quick-action invalid kind → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_action_kind",
            f"status={r.status_code}",
        )

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
