"""API v2 /admin/usage + /quota + /feature-flags smoke (D6 P5).

Senaryolar:
   1. /usage happy (period + inst_rows + indep_rows + totals + kind_costs)
   2. /usage/institution/{id}/hard-block toggle
   3. /usage/institution/{id}/hard-block account_not_found (period yoksa)
   4. /usage/institution/{id}/bonus happy
   5. /usage/user/{id}/bonus happy
   6. /usage bonus invalid amount → 400
   7. /usage bonus invalid owner_type → 400
   8. /quota happy (rows + quota_keys + plans)
   9. /quota/{id}/override happy
  10. /quota/{id}/override invalid quota_key → 400
  11. /quota/{id}/override invalid value → 400
  12. /quota/overrides/{id}/delete happy
  13. /quota/{99999}/override → 404 institution_not_found
  14. /feature-flags list happy
  15. /feature-flags/{id} detail happy
  16. /feature-flags/{id} 404
  17. /feature-flags/{id}/toggle happy
  18. /feature-flags/{id}/overrides add happy
  19. /feature-flags/overrides/{id}/delete happy
  20. Teacher → 403
  21. Anonim → 401
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
    CreditAccount,
    FeatureFlag,
    FeatureFlagOverride,
    Institution,
    InstitutionQuotaOverride,
    UsageOwnerType,
    User,
    UserRole,
)
from app.services.credits import (
    CreditOwner,
    current_period,
    get_or_create_account,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp5{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP5!23"

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
            institution_id=None, is_active=True,  # bağımsız öğretmen
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()

        # Feature flag seed
        flag = FeatureFlag(
            key=f"{PFX}_test_flag",
            description="Test flag for smoke",
            enabled_globally=True,
        )
        db.add(flag)
        db.flush()

        teacher_id = teacher.id
        inst_id = inst.id
        flag_id = flag.id

        # Credit account'lar — usage testi için period satırı lazım
        period = current_period()
        inst_owner = CreditOwner.for_institution(inst)
        get_or_create_account(db, owner=inst_owner, period=period)
        teacher_owner = CreditOwner.for_user(teacher)
        get_or_create_account(db, owner=teacher_owner, period=period)

        db.commit()
        return {
            "inst_id": inst_id,
            "super_id": super_admin.id,
            "teacher_id": teacher_id,
            "flag_id": flag_id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        ids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(sa_delete(FeatureFlagOverride).where(
            FeatureFlagOverride.feature_flag_id == seed["flag_id"]
        ))
        db.execute(sa_delete(FeatureFlag).where(
            FeatureFlag.id == seed["flag_id"]
        ))
        db.execute(sa_delete(InstitutionQuotaOverride).where(
            InstitutionQuotaOverride.institution_id == seed["inst_id"]
        ))
        db.execute(sa_delete(CreditAccount).where(
            (CreditAccount.owner_id == seed["inst_id"])
            | (CreditAccount.owner_id == seed["teacher_id"])
        ))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id == seed["inst_id"]
        ))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin P5 smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded inst={seed['inst_id']} teacher={seed['teacher_id']} "
        f"flag={seed['flag_id']}\n"
    )

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # ===== Teacher → 403 (başta) =====
        r = tc.get("/api/v2/admin/usage")
        check(
            "20. Teacher /usage → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/usage")
        check(
            "21. Anonim /usage → 401",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ===== 1. /usage happy =====
        r = sc.get("/api/v2/admin/usage")
        ok = (
            r.status_code == 200
            and "period" in r.json()
            and "inst_rows" in r.json()
            and "indep_rows" in r.json()
            and "totals" in r.json()
            and "kind_costs" in r.json()
        )
        check("1. /usage happy", ok, f"status={r.status_code}")

        # ===== 2. hard-block toggle =====
        r = sc.post(f"/api/v2/admin/usage/institution/{seed['inst_id']}/hard-block")
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("account", {}).get("hard_block_enabled") is True
        )
        check("2. hard-block toggle → True", ok, f"status={r.status_code}")
        # toggle back
        sc.post(f"/api/v2/admin/usage/institution/{seed['inst_id']}/hard-block")

        # ===== 3. hard-block account_not_found =====
        r = sc.post("/api/v2/admin/usage/institution/999999/hard-block")
        check(
            "3. hard-block 999999 → 404 account_not_found",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "account_not_found",
            f"status={r.status_code}",
        )

        # ===== 4. bonus institution =====
        r = sc.post(
            f"/api/v2/admin/usage/institution/{seed['inst_id']}/bonus",
            json={"bonus_amount": 100},
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("account", {}).get("bonus_credits") == 100
        )
        check("4. bonus institution +100", ok, f"status={r.status_code}")

        # ===== 5. bonus user =====
        r = sc.post(
            f"/api/v2/admin/usage/user/{seed['teacher_id']}/bonus",
            json={"bonus_amount": 50},
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("account", {}).get("bonus_credits") == 50
        )
        check("5. bonus user +50", ok, f"status={r.status_code}")

        # ===== 6. bonus invalid amount =====
        r = sc.post(
            f"/api/v2/admin/usage/institution/{seed['inst_id']}/bonus",
            json={"bonus_amount": 0},
        )
        check(
            "6. bonus 0 → 400 invalid_bonus_amount",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_bonus_amount",
            f"status={r.status_code}",
        )

        # ===== 7. bonus invalid owner_type =====
        r = sc.post(
            f"/api/v2/admin/usage/student/{seed['teacher_id']}/bonus",
            json={"bonus_amount": 10},
        )
        check(
            "7. bonus invalid owner_type → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_owner_type",
            f"status={r.status_code}",
        )

        # ===== 8. /quota happy =====
        r = sc.get("/api/v2/admin/quota")
        ok = (
            r.status_code == 200
            and "rows" in r.json()
            and "quota_keys" in r.json()
            and "plans" in r.json()
        )
        check("8. /quota happy", ok, f"status={r.status_code}")

        # ===== 9. quota override =====
        r = sc.post(
            f"/api/v2/admin/quota/{seed['inst_id']}/override",
            json={"quota_key": "teachers", "override_value": 50, "note": "pilot"},
        )
        ok = r.status_code == 200 and "teachers" in r.json().get("data", {}).get("message", "")
        check("9. quota override teachers=50", ok, f"status={r.status_code} body={r.text[:200]}")

        # ===== 10. quota invalid quota_key =====
        r = sc.post(
            f"/api/v2/admin/quota/{seed['inst_id']}/override",
            json={"quota_key": "BOGUS", "override_value": 50},
        )
        check(
            "10. quota invalid key → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_quota_key",
            f"status={r.status_code}",
        )

        # ===== 11. quota invalid value =====
        r = sc.post(
            f"/api/v2/admin/quota/{seed['inst_id']}/override",
            json={"quota_key": "teachers", "override_value": -5},
        )
        check(
            "11. quota invalid value → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_override_value",
            f"status={r.status_code}",
        )

        # ===== 12. quota override delete =====
        # önce override id'sini bul
        with SessionLocal() as db:
            ov = db.query(InstitutionQuotaOverride).filter(
                InstitutionQuotaOverride.institution_id == seed["inst_id"],
                InstitutionQuotaOverride.quota_key == "teachers",
            ).first()
            ov_id = ov.id if ov else None
        if ov_id:
            r = sc.post(f"/api/v2/admin/quota/overrides/{ov_id}/delete")
            check(
                "12. quota override delete",
                r.status_code == 200 and "silindi" in r.json().get("data", {}).get("message", ""),
                f"status={r.status_code}",
            )
        else:
            check("12. quota override delete", False, "override bulunamadı")

        # ===== 13. quota override on 99999 → 404 =====
        r = sc.post(
            "/api/v2/admin/quota/999999/override",
            json={"quota_key": "teachers", "override_value": 10},
        )
        check(
            "13. quota override 999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "institution_not_found",
            f"status={r.status_code}",
        )

        # ===== 14. /feature-flags list =====
        r = sc.get("/api/v2/admin/feature-flags")
        ok = (
            r.status_code == 200
            and "flags" in r.json()
            and any(f["id"] == seed["flag_id"] for f in r.json()["flags"])
        )
        check("14. /feature-flags list", ok, f"status={r.status_code}")

        # ===== 15. /feature-flags/{id} detail =====
        r = sc.get(f"/api/v2/admin/feature-flags/{seed['flag_id']}")
        ok = (
            r.status_code == 200
            and r.json().get("id") == seed["flag_id"]
            and "overrides" in r.json()
            and "available_institutions" in r.json()
        )
        check("15. /feature-flags/{id} detail", ok, f"status={r.status_code}")

        # ===== 16. /feature-flags/99999 → 404 =====
        r = sc.get("/api/v2/admin/feature-flags/999999")
        check(
            "16. /feature-flags/999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "flag_not_found",
            f"status={r.status_code}",
        )

        # ===== 17. toggle =====
        r = sc.post(f"/api/v2/admin/feature-flags/{seed['flag_id']}/toggle")
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("enabled_globally") is False
        )
        check("17. flag toggle → False", ok, f"status={r.status_code}")

        # ===== 18. add override =====
        r = sc.post(
            f"/api/v2/admin/feature-flags/{seed['flag_id']}/overrides",
            json={"institution_id": seed["inst_id"], "enabled": True, "note": "pilot"},
        )
        ok = r.status_code == 200 and "override" in r.json().get("data", {}).get("message", "").lower()
        check("18. flag override add", ok, f"status={r.status_code} body={r.text[:200]}")

        # ===== 19. remove override =====
        with SessionLocal() as db:
            o = db.query(FeatureFlagOverride).filter(
                FeatureFlagOverride.feature_flag_id == seed["flag_id"],
                FeatureFlagOverride.institution_id == seed["inst_id"],
            ).first()
            o_id = o.id if o else None
        if o_id:
            r = sc.post(f"/api/v2/admin/feature-flags/overrides/{o_id}/delete")
            check(
                "19. flag override remove",
                r.status_code == 200 and "silindi" in r.json().get("data", {}).get("message", ""),
                f"status={r.status_code}",
            )
        else:
            check("19. flag override remove", False, "override bulunamadı")

    finally:
        _cleanup(seed)
        print("\n  test verileri temizlendi")

    print("\n=== SONUÇ ===")
    print(f"  PASSED: {passed}")
    print(f"  FAILED: {len(failed)}")
    if failed:
        for f in failed:
            print(f"    - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
