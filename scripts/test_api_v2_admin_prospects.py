"""API v2 /admin/prospects (Hedef Havuzu) smoke — K1a.

1 anon 401 · 2 teacher 403 · 3 create happy + normalize · 4 invalid phone 422 ·
5 duplicate 409 · 6 list + counts + meta · 7 filtre status/kind/q · 8 update ·
9 set status member · 10 delete · 11 teacher create 403.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SalesProspect, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"prsp{secrets.token_hex(3)}"
SUPER = f"{PFX}_super@test.invalid"
TEACHER = f"{PFX}_t@test.invalid"
PW = "ProspectTest!23"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1; print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}"); print(f"  [FAIL] {label} ({detail})")


def _seed():
    with SessionLocal() as db:
        pw = hash_password(PW)
        sa = User(email=SUPER, password_hash=pw, full_name=f"{PFX} Super",
                  role=UserRole.SUPER_ADMIN, is_active=True, must_change_password=False)
        tc = User(email=TEACHER, password_hash=pw, full_name=f"{PFX} T",
                  role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add_all([sa, tc]); db.commit()
        return {"super": sa.id, "teacher": tc.id}


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(SalesProspect).where(SalesProspect.phone.like("9055%")))
        db.execute(sa_delete(SalesProspect).where(SalesProspect.created_by_admin_id == seed["super"]))
        db.execute(sa_delete(User).where(User.id.in_([seed["super"], seed["teacher"]])))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    if r.status_code != 200:
        raise RuntimeError(f"login {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== /admin/prospects smoke — {PFX} ===\n")
    seed = _seed()
    created_id = None
    try:
        sc = _login(SUPER); tc = _login(TEACHER)

        r = TestClient(app).get("/api/v2/admin/prospects")
        check("1. anon → 401", r.status_code == 401, str(r.status_code))

        r = tc.get("/api/v2/admin/prospects")
        check("2. teacher → 403", r.status_code == 403, str(r.status_code))

        # 3. create + normalize (0532... → 90532...)
        r = sc.post("/api/v2/admin/prospects", json={
            "name": "Demo Kurum Yön", "phone": "0532 111 22 33", "kind": "institution",
            "org_name": "X Dershanesi", "city": "Trabzon"})
        j = r.json()
        created_id = j.get("data", {}).get("id")
        check("3. create + telefon normalize",
              r.status_code == 200 and j["data"]["phone"] == "905321112233"
              and j["data"]["kind_label"] == "Kurum", f"{r.status_code} {j.get('data',{}).get('phone')}")

        # 4. invalid phone
        r = sc.post("/api/v2/admin/prospects", json={"name": "Bad", "phone": "123"})
        check("4. geçersiz telefon → 422", r.status_code == 422, str(r.status_code))

        # 5. duplicate phone
        r = sc.post("/api/v2/admin/prospects", json={"name": "Yine", "phone": "05321112233"})
        check("5. mükerrer telefon → 409", r.status_code == 409, str(r.status_code))

        # 6. list + counts + meta
        r = sc.get("/api/v2/admin/prospects")
        j = r.json()
        check("6. list + counts + meta",
              any(p["id"] == created_id for p in j["items"]) and "counts" in j
              and "statuses" in j["meta"], f"items={len(j.get('items',[]))}")

        # 7. filtre kind=institution
        r = sc.get("/api/v2/admin/prospects?kind=institution")
        check("7. kind filtresi", all(p["kind"] == "institution" for p in r.json()["items"]),
              "kind mismatch")
        r = sc.get("/api/v2/admin/prospects?q=Dershane")
        check("7b. q araması", any(p["id"] == created_id for p in r.json()["items"]), "q miss")

        # 8. update
        r = sc.post(f"/api/v2/admin/prospects/{created_id}", json={"city": "İstanbul", "opt_in": True})
        check("8. update", r.status_code == 200 and r.json()["data"]["city"] == "İstanbul"
              and r.json()["data"]["opt_in"] is True, str(r.status_code))

        # 9. set status member
        r = sc.post(f"/api/v2/admin/prospects/{created_id}/status", json={"status": "member"})
        check("9. status=member", r.status_code == 200 and r.json()["data"]["status"] == "member",
              str(r.status_code))

        # 10. teacher create → 403
        r = tc.post("/api/v2/admin/prospects", json={"name": "X", "phone": "05330001122"})
        check("10. teacher create → 403", r.status_code == 403, str(r.status_code))

        # 11. delete
        r = sc.post(f"/api/v2/admin/prospects/{created_id}/delete")
        check("11. delete → 200", r.status_code == 200 and r.json()["data"]["deleted"],
              str(r.status_code))
    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
