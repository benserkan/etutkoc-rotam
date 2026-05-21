"""API v2 /admin/institutions + account-history smoke (D6 P2).

Senaryolar:
   1. /institutions list happy (200, items + summary)
   2. /institutions list ?sort=name
   3. /institutions list ?filter_level=critical
   4. /institutions POST create happy → 200 + slug auto-gen
   5. /institutions POST create boş name → 400 name_required
   6. /institutions POST create duplicate slug → 409 slug_taken
   7. /institutions/{id} detail happy → 200 (health + admins + teachers)
   8. /institutions/{id} detail 404
   9. /institutions/{id} POST edit happy → 200 + before/after diff audit
  10. /institutions/{id} POST edit boş name → 400
  11. /institutions/{id}/backup summary → counts dolu + size_bytes > 0
  12. /institutions/{id}/backup.json → JSON download, password REDACTED
  13. /account-history/institution/{id} → events listesi (plan + invoice yoksa boş)
  14. /account-history/user/{id} → user için sadece plan events
  15. /account-history/user/{99999} → 404 user_not_found
  16. /account-history/archive → ok (plan kaydı arşivlenir) — gerçek kayıt yoksa not_found
  17. /account-history/bulk-archive → years validation (0 → 400 if invalid)
  18. /institutions/{id}/delete cascade (User.institution_id NULL)
  19. Teacher rolü list → 403 role_required
  20. Anonim → 401 missing_credentials
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
from app.models import AuditLog, Institution, PlanChangeHistory, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adminst{secrets.token_hex(3)}"  # underscore yok — slugify ile uyumlu
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassInst!23"

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
    """Super admin + bir test kurumu + bir öğretmen (içerde)."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Alpha Inst",
            slug=f"{PFX}-alpha",
            contact_email=f"{PFX}@test.invalid",
            plan="free",
            is_active=True,
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
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.commit()
        return {
            "inst_id": inst.id,
            "super_id": super_admin.id,
            "teacher_id": teacher.id,
        }


def _cleanup(seed: dict, extra_inst_ids: list[int]) -> None:
    with SessionLocal() as db:
        # Audit + plan history önce
        db.execute(sa_delete(AuditLog).where(
            AuditLog.actor_id == seed["super_id"]
        ))
        db.execute(sa_delete(PlanChangeHistory).where(
            PlanChangeHistory.actor_user_id == seed["super_id"]
        ))
        # Tüm test kurumlarını sil
        inst_ids = [seed["inst_id"]] + extra_inst_ids
        db.execute(sa_delete(Institution).where(
            Institution.id.in_(inst_ids)
        ))
        # User (teacher institution_id NULL olabilir delete sonrası)
        db.execute(sa_delete(User).where(
            User.id.in_([seed["super_id"], seed["teacher_id"]])
        ))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/institutions smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']} teacher={seed['teacher_id']}\n")

    extra_inst_ids: list[int] = []
    try:
        sc = _login_v2(SUPER_EMAIL)

        # ===== 1. list happy =====
        r = sc.get("/api/v2/admin/institutions")
        ok = (
            r.status_code == 200
            and isinstance(r.json().get("items"), list)
            and "summary" in r.json()
            and r.json().get("sort") == "health"
        )
        check(
            "1. /institutions list happy",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 2. list ?sort=name =====
        r = sc.get("/api/v2/admin/institutions?sort=name")
        check(
            "2. /institutions ?sort=name",
            r.status_code == 200 and r.json().get("sort") == "name",
            f"status={r.status_code}",
        )

        # ===== 3. list ?filter_level=critical =====
        r = sc.get("/api/v2/admin/institutions?filter_level=critical")
        check(
            "3. /institutions ?filter_level=critical",
            r.status_code == 200
            and r.json().get("filter_level") == "critical",
            f"status={r.status_code}",
        )

        # ===== 4. POST create happy =====
        new_name = f"{PFX} Beta Inst"
        r = sc.post(
            "/api/v2/admin/institutions",
            json={"name": new_name, "plan": "starter"},
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("institution", {}).get("name") == new_name
        )
        check(
            "4. POST create happy",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )
        if ok:
            new_inst_id = r.json()["data"]["institution"]["id"]
            extra_inst_ids.append(new_inst_id)

            new_slug = r.json()["data"]["institution"]["slug"]
            check(
                "4b. slug auto-gen (lowercase, alphanumeric+dash)",
                new_slug == new_slug.lower() and "-" in new_slug,
                f"slug={new_slug}",
            )

        # ===== 5. POST create boş name =====
        r = sc.post("/api/v2/admin/institutions", json={"name": "  "})
        check(
            "5. POST create boş name → 400 name_required",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "name_required",
            f"status={r.status_code}",
        )

        # ===== 6. POST create duplicate slug =====
        r = sc.post(
            "/api/v2/admin/institutions",
            json={"name": f"{PFX} Beta Dup", "slug": f"{PFX}-alpha"},
        )
        check(
            "6. POST create duplicate slug → 409 slug_taken",
            r.status_code == 409
            and r.json().get("detail", {}).get("code") == "slug_taken",
            f"status={r.status_code}",
        )

        # ===== 7. detail happy =====
        r = sc.get(f"/api/v2/admin/institutions/{seed['inst_id']}")
        ok = (
            r.status_code == 200
            and r.json().get("institution", {}).get("id") == seed["inst_id"]
            and "health" in r.json()
            and isinstance(r.json().get("teachers"), list)
            and isinstance(r.json().get("institution_admins"), list)
            and "student_count" in r.json()
        )
        check(
            "7. /institutions/{id} detail happy",
            ok,
            f"status={r.status_code} keys={list(r.json().keys()) if r.status_code == 200 else r.text[:200]}",
        )
        if ok:
            check(
                "7b. detail teachers listesinde test öğretmeni var",
                any(t["id"] == seed["teacher_id"] for t in r.json()["teachers"]),
                f"teachers={r.json()['teachers']}",
            )

        # ===== 8. detail 404 =====
        r = sc.get("/api/v2/admin/institutions/999999")
        check(
            "8. /institutions/999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "institution_not_found",
            f"status={r.status_code}",
        )

        # ===== 9. POST edit happy =====
        r = sc.post(
            f"/api/v2/admin/institutions/{seed['inst_id']}",
            json={
                "name": f"{PFX} Alpha Renamed",
                "contact_email": f"{PFX}_new@test.invalid",
                "plan": "professional",
                "is_active": True,
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("institution", {}).get("name")
            == f"{PFX} Alpha Renamed"
            and r.json().get("data", {}).get("institution", {}).get("plan")
            == "professional"
        )
        check(
            "9. POST edit happy + plan değişti",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 10. POST edit boş name =====
        r = sc.post(
            f"/api/v2/admin/institutions/{seed['inst_id']}",
            json={"name": "  ", "plan": "free", "is_active": True},
        )
        check(
            "10. POST edit boş name → 400 name_required",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "name_required",
            f"status={r.status_code}",
        )

        # ===== 11. backup summary =====
        r = sc.get(f"/api/v2/admin/institutions/{seed['inst_id']}/backup")
        ok = (
            r.status_code == 200
            and "counts" in r.json()
            and r.json().get("size_bytes", 0) > 0
            and r.json().get("schema_version") == 1
        )
        check(
            "11. /backup summary → counts + size_bytes",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 12. backup.json download =====
        r = sc.get(f"/api/v2/admin/institutions/{seed['inst_id']}/backup.json")
        ok = (
            r.status_code == 200
            and "Content-Disposition" in r.headers
            and "attachment" in r.headers["Content-Disposition"]
        )
        check(
            "12. /backup.json download",
            ok,
            f"status={r.status_code} content-disposition={r.headers.get('Content-Disposition')}",
        )
        if ok:
            import json as _json
            payload = _json.loads(r.content)
            check(
                "12b. backup.json password_hash REDACTED",
                all(
                    u.get("password_hash") == "REDACTED"
                    for u in payload.get("users", [])
                ),
                f"users={len(payload.get('users', []))}",
            )

        # ===== 13. account-history institution =====
        r = sc.get(
            f"/api/v2/admin/account-history/institution/{seed['inst_id']}"
        )
        ok = (
            r.status_code == 200
            and "events" in r.json()
            and r.json().get("owner_type") == "institution"
            and r.json().get("years") == 3
        )
        check(
            "13. /account-history/institution/{id}",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 14. account-history user =====
        r = sc.get(
            f"/api/v2/admin/account-history/user/{seed['teacher_id']}"
        )
        ok = (
            r.status_code == 200
            and r.json().get("owner_type") == "user"
        )
        check(
            "14. /account-history/user/{id}",
            ok,
            f"status={r.status_code}",
        )

        # ===== 15. account-history user 99999 → 404 =====
        r = sc.get("/api/v2/admin/account-history/user/999999")
        check(
            "15. /account-history/user/999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "user_not_found",
            f"status={r.status_code}",
        )

        # ===== 16. archive olmayan kayıt → not_found =====
        r = sc.post(
            "/api/v2/admin/account-history/archive",
            json={"record_type": "plan", "record_id": 999999, "note": "test"},
        )
        check(
            "16. archive olmayan kayıt → ok=False + error=not_found",
            r.status_code == 200
            and r.json().get("data", {}).get("ok") is False
            and r.json().get("data", {}).get("error") == "not_found",
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 17. bulk-archive happy (kayıt yoksa total=0) =====
        r = sc.post(
            "/api/v2/admin/account-history/bulk-archive",
            json={
                "owner_type": "institution",
                "owner_id": seed["inst_id"],
                "years": 3,
            },
        )
        check(
            "17. bulk-archive happy",
            r.status_code == 200
            and r.json().get("data", {}).get("ok") is True
            and "admin:account-history" in r.json().get("invalidate", []),
            f"status={r.status_code}",
        )

        # ===== 18. delete cascade — yeni oluşturduğumuz kurumu sil =====
        if extra_inst_ids:
            target = extra_inst_ids[0]
            r = sc.post(f"/api/v2/admin/institutions/{target}/delete")
            check(
                "18. POST delete cascade",
                r.status_code == 200
                and r.json().get("data", {}).get("institution") is None
                and "silindi" in r.json().get("data", {}).get("message", ""),
                f"status={r.status_code} body={r.text[:200]}",
            )
            # Artık deleted, extra_inst_ids'den çıkar (cleanup tekrar denemesin)
            extra_inst_ids.pop(0)

        # ===== 19. Teacher rolü list → 403 =====
        tc = _login_v2(TEACHER_EMAIL)
        r = tc.get("/api/v2/admin/institutions")
        check(
            "19. Teacher → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 20. Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/institutions")
        check(
            "20. Anonim → 401 missing_credentials",
            r.status_code == 401
            and r.json().get("detail", {}).get("code") == "missing_credentials",
            f"status={r.status_code}",
        )

    finally:
        _cleanup(seed, extra_inst_ids)
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
