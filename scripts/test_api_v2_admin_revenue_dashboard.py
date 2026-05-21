"""API v2 /admin/security-monitor/revenue (Ticari ana dashboard) smoke (D6 G1).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. dashboard happy (mrr/plan_distribution/payment_calendar/segment_counts)
   4. dashboard segment=institution
   5. dashboard segment=user
   6. dashboard geçersiz segment → 'all'a düşer
   7. drill happy (paying)
   8. drill plan:<code>
   9. drill bilinmeyen key → error
  10. invoices happy (rows + status_counts + statuses)
  11. invoices status_filter=pending
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
from app.models import (
    AuditLog,
    Institution,
    Invoice,
    InvoiceStatus,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg1{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassG1!23"

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
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        inv = Invoice(
            owner_type="institution", institution_id=inst.id, user_id=None,
            plan="free", amount_try=2999, status=InvoiceStatus.PENDING,
            period_start=now - timedelta(days=30), period_end=now,
            due_at=now + timedelta(days=5),
        )
        db.add(inv)
        db.flush()
        out = {"inst_id": inst.id, "super_id": super_admin.id, "teacher_id": teacher.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(Invoice).where(Invoice.institution_id == seed["inst_id"]))
        uids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/security-monitor/revenue (G1) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/revenue")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/security-monitor/revenue")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. dashboard happy
        r = sc.get("/api/v2/admin/security-monitor/revenue")
        j = r.json()
        ok = (
            r.status_code == 200
            and "mrr" in j and "plan_distribution" in j and "payment_calendar" in j
            and "segment_counts" in j and j["segment"] == "all"
            and set(j["segment_counts"].keys()) == {"all", "institution", "user"}
        )
        check("3. dashboard happy", ok, f"status={r.status_code}")

        # 4. segment=institution
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=institution")
        check("4. segment=institution", r.status_code == 200 and r.json()["segment"] == "institution",
              f"status={r.status_code}")

        # 5. segment=user
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=user")
        check("5. segment=user", r.status_code == 200 and r.json()["segment"] == "user",
              f"status={r.status_code}")

        # 6. geçersiz segment → all
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=xyz")
        check("6. geçersiz segment → all", r.status_code == 200 and r.json()["segment"] == "all",
              f"status={r.status_code}")

        # 7. drill paying
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=paying")
        j = r.json()
        check("7. drill paying", r.status_code == 200 and "rows" in j and "count" in j and j["key"] == "paying",
              f"status={r.status_code}")

        # 8. drill plan:free
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan:free")
        check("8. drill plan:free", r.status_code == 200 and r.json()["plan"] == "free",
              f"status={r.status_code}")

        # 9. drill bilinmeyen key → error
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=not_real_key")
        j = r.json()
        check("9. drill bilinmeyen key → error", r.status_code == 200 and j.get("error") == "unknown_key",
              f"status={r.status_code} {r.text[:120]}")

        # 10. invoices happy
        r = sc.get("/api/v2/admin/security-monitor/revenue/invoices")
        j = r.json()
        ok = (
            r.status_code == 200
            and "rows" in j and "status_counts" in j and len(j["statuses"]) == 6
            and any(row["id"] for row in j["rows"])
        )
        check("10. invoices happy", ok, f"status={r.status_code}")

        # 11. invoices status_filter=pending
        r = sc.get("/api/v2/admin/security-monitor/revenue/invoices?status_filter=pending")
        j = r.json()
        ok = r.status_code == 200 and j["status_filter"] == "pending" and all(row["status"] == "pending" for row in j["rows"])
        check("11. invoices status_filter=pending", ok, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
