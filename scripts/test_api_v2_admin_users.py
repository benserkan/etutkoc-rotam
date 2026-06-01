"""API v2 /admin/users + impersonate smoke (D6 P3).

Senaryolar:
   1. /users list happy
   2. /users ?role=teacher filtre
   3. /users ?q=email arama
   4. /users POST create happy + temp_password issued
   5. /users POST boş name → 400 name_or_email_required
   6. /users POST duplicate email → 409 email_taken
   7. /users POST INSTITUTION_ADMIN inst_id yok → 400 institution_required
   8. /users/{id} detail happy + is_self False
   9. /users/{id} detail 404
  10. /users/{id} POST edit happy + USER_UPDATE audit
  11. /users/{id} POST edit is_active=False → USER_DEACTIVATE audit
  12. /users/{id}/reset-password → temp_password issued + must_change=True
  13. /users/{id}/change-role happy (teacher → parent)
  14. /users/{id}/change-role kendi rolü → 403 cannot_change_own_role
  15. /users/{id}/change-role INSTITUTION_ADMIN inst_id yok → 400
  16. /users/{id}/delete happy
  17. /users/{id}/delete kendi hesabı → 403 cannot_delete_self
  18. /users/{id}/impersonate happy
  19. /users/{id}/impersonate kendi → 403 cannot_impersonate_self
  20. /users/{id}/impersonate super_admin → 403 cannot_impersonate_super_admin
  21. /users/{id}/impersonate reason <10 → 400 invalid_reason
  22. /users/{id}/impersonate pasif user → 403 target_inactive
  23. /independent-teachers happy
  24. Teacher rolü list → 403 role_required
  25. Anonim → 401
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
    ImpersonationSession,
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adusers{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
SUPER2_EMAIL = f"{PFX}_super2@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
INACTIVE_EMAIL = f"{PFX}_inactive@test.invalid"
PASSWORD = "TestPassUsers!23"

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
            contact_email=f"{PFX}@test.invalid",
            plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()

        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Super", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        super2 = User(
            email=SUPER2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Super2", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        inactive = User(
            email=INACTIVE_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Inactive", role=UserRole.TEACHER,
            is_active=False, password_changed_at=now,
            must_change_password=False,
        )
        db.add_all([super_admin, super2, teacher, inactive])
        db.commit()
        return {
            "inst_id": inst.id,
            "super_id": super_admin.id,
            "super2_id": super2.id,
            "teacher_id": teacher.id,
            "inactive_id": inactive.id,
        }


def _cleanup(seed: dict, extra_ids: list[int]) -> None:
    with SessionLocal() as db:
        all_ids = [
            seed["super_id"], seed["super2_id"],
            seed["teacher_id"], seed["inactive_id"],
        ] + extra_ids
        db.execute(sa_delete(ImpersonationSession).where(
            ImpersonationSession.actor_user_id.in_(all_ids),
        ))
        db.execute(sa_delete(AuditLog).where(
            AuditLog.actor_id.in_(all_ids),
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id == seed["inst_id"],
        ))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/users smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded super={seed['super_id']} teacher={seed['teacher_id']}\n")

    extra_ids: list[int] = []
    try:
        sc = _login_v2(SUPER_EMAIL)
        # Teacher login'i + 403 testini en başa alıyoruz — sonraki reset-password
        # bu kullanıcının şifresini değiştirir, oturum invalide olur
        tc = _login_v2(TEACHER_EMAIL)

        # ===== 24 (test başında) Teacher rolü → 403 role_required =====
        r = tc.get("/api/v2/admin/users")
        check(
            "24. Teacher → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 25 (test başında) Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/users")
        check(
            "25. Anonim → 401",
            r.status_code == 401
            and r.json().get("detail", {}).get("code") == "missing_credentials",
            f"status={r.status_code}",
        )

        # ===== 1. list happy =====
        r = sc.get("/api/v2/admin/users")
        ok = r.status_code == 200 and isinstance(r.json().get("items"), list)
        check("1. /users list happy", ok, f"status={r.status_code}")

        # ===== 2. ?role=teacher =====
        r = sc.get("/api/v2/admin/users?role=teacher")
        ok = (
            r.status_code == 200
            and all(u["role"] == "teacher" for u in r.json()["items"])
        )
        check(
            "2. /users ?role=teacher filtre",
            ok,
            f"status={r.status_code}",
        )

        # ===== 3. ?q=email arama =====
        r = sc.get(f"/api/v2/admin/users?q={PFX}_teacher")
        ok = (
            r.status_code == 200
            and any(u["email"] == TEACHER_EMAIL for u in r.json()["items"])
        )
        check("3. /users ?q= arama", ok, f"status={r.status_code}")

        # ===== 4. POST create happy =====
        new_email = f"{PFX}_new1@test.invalid"
        r = sc.post(
            "/api/v2/admin/users",
            json={
                "full_name": f"{PFX} New Teacher",
                "email": new_email,
                "role": "teacher",
                "institution_id": seed["inst_id"],
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("temp_password")
            and r.json()["data"]["user"]["email"] == new_email
            and r.json()["data"]["must_change_password"] is True
        )
        check("4. POST create + temp_password", ok, f"status={r.status_code}")
        if ok:
            extra_ids.append(r.json()["data"]["user"]["id"])

        # ===== 5. POST boş name =====
        r = sc.post(
            "/api/v2/admin/users",
            json={
                "full_name": "  ",
                "email": f"{PFX}_x@test.invalid",
                "role": "teacher",
            },
        )
        check(
            "5. POST boş name → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "name_or_email_required",
            f"status={r.status_code}",
        )

        # ===== 6. POST duplicate email =====
        r = sc.post(
            "/api/v2/admin/users",
            json={
                "full_name": "Dup",
                "email": TEACHER_EMAIL,
                "role": "teacher",
            },
        )
        check(
            "6. POST duplicate email → 409",
            r.status_code == 409
            and r.json().get("detail", {}).get("code") == "email_taken",
            f"status={r.status_code}",
        )

        # ===== 7. INSTITUTION_ADMIN inst_id eksik =====
        r = sc.post(
            "/api/v2/admin/users",
            json={
                "full_name": "Inst Admin",
                "email": f"{PFX}_ia@test.invalid",
                "role": "institution_admin",
            },
        )
        check(
            "7. POST INSTITUTION_ADMIN inst_id yok → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "institution_required",
            f"status={r.status_code}",
        )

        # ===== 8. detail happy =====
        r = sc.get(f"/api/v2/admin/users/{seed['teacher_id']}")
        ok = (
            r.status_code == 200
            and r.json().get("target", {}).get("id") == seed["teacher_id"]
            and r.json().get("is_self") is False
            and isinstance(r.json().get("recent_audits"), list)
        )
        check("8. detail happy + is_self=False", ok, f"status={r.status_code}")

        # ===== 9. detail 404 =====
        r = sc.get("/api/v2/admin/users/999999")
        check(
            "9. detail 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "user_not_found",
            f"status={r.status_code}",
        )

        # ===== 10. POST edit happy =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}",
            json={
                "full_name": f"{PFX} Teacher Renamed",
                "email": TEACHER_EMAIL,
                "institution_id": seed["inst_id"],
                "is_active": True,
            },
        )
        ok = (
            r.status_code == 200
            and r.json()["data"]["user"]["full_name"] == f"{PFX} Teacher Renamed"
        )
        check("10. POST edit happy", ok, f"status={r.status_code}")

        # ===== 11. edit is_active=False =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}",
            json={
                "full_name": f"{PFX} Teacher Renamed",
                "email": TEACHER_EMAIL,
                "institution_id": seed["inst_id"],
                "is_active": False,
            },
        )
        ok = (
            r.status_code == 200
            and r.json()["data"]["user"]["is_active"] is False
        )
        check(
            "11. edit is_active=False (USER_DEACTIVATE audit)",
            ok,
            f"status={r.status_code}",
        )

        # Re-activate for following tests
        sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}",
            json={
                "full_name": f"{PFX} Teacher Renamed",
                "email": TEACHER_EMAIL,
                "institution_id": seed["inst_id"],
                "is_active": True,
            },
        )

        # ===== 12. reset password =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/reset-password"
        )
        ok = (
            r.status_code == 200
            and r.json()["data"].get("temp_password")
            and r.json()["data"]["user"]["must_change_password"] is True
        )
        check("12. reset-password issued temp", ok, f"status={r.status_code}")

        # ===== 13. change-role happy (teacher → parent) =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/change-role",
            json={"new_role": "parent"},
        )
        ok = (
            r.status_code == 200
            and r.json()["data"]["user"]["role"] == "parent"
        )
        check("13. change-role teacher→parent", ok, f"status={r.status_code}")

        # Revert (parent → teacher for cleanup)
        sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/change-role",
            json={"new_role": "teacher"},
        )

        # ===== 14. change-role self → 403 =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['super_id']}/change-role",
            json={"new_role": "teacher"},
        )
        check(
            "14. change-role self → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "cannot_change_own_role",
            f"status={r.status_code}",
        )

        # ===== 15. change-role INSTITUTION_ADMIN inst_id yok =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/change-role",
            json={"new_role": "institution_admin"},
        )
        check(
            "15. change-role INST_ADMIN inst_id yok → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "institution_required",
            f"status={r.status_code}",
        )

        # ===== 16. delete (newly created user) =====
        if extra_ids:
            target = extra_ids[0]
            r = sc.post(f"/api/v2/admin/users/{target}/delete")
            check(
                "16. POST delete happy",
                r.status_code == 200
                and "silindi" in r.json()["data"]["message"],
                f"status={r.status_code}",
            )
            extra_ids.pop(0)

        # ===== 17. delete self → 403 =====
        r = sc.post(f"/api/v2/admin/users/{seed['super_id']}/delete")
        check(
            "17. delete self → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "cannot_delete_self",
            f"status={r.status_code}",
        )

        # ===== 18. impersonate happy =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/impersonate",
            json={"reason": "Test smoke için sahte oturum"},
        )
        ok = (
            r.status_code == 200
            and r.json().get("target_id") == seed["teacher_id"]
            and r.json().get("redirect_url") == "/teacher"
        )
        check(
            "18. impersonate happy + redirect_url",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 18b. BFF: impersonate sc'nin cookie'sini HEDEFE çevirdi (yeni davranış).
        # end → admin cookie geri basılır; sc tekrar süper admin olur (sonraki testler
        # için şart) + end akışı doğrulanır. =====
        r = sc.post("/api/v2/admin/impersonate/end")
        check(
            "18b. impersonate end → 200 + /admin (admin cookie restore)",
            r.status_code == 200 and r.json().get("redirect_url") == "/admin",
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 19. impersonate self → 403 =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['super_id']}/impersonate",
            json={"reason": "Test smoke için kendin"},
        )
        check(
            "19. impersonate self → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code")
            == "cannot_impersonate_self",
            f"status={r.status_code}",
        )

        # ===== 20. impersonate super_admin → 403 =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['super2_id']}/impersonate",
            json={"reason": "Test smoke için diğer super admin"},
        )
        check(
            "20. impersonate super_admin → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code")
            == "cannot_impersonate_super_admin",
            f"status={r.status_code}",
        )

        # ===== 21. impersonate kısa reason → 400 =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['teacher_id']}/impersonate",
            json={"reason": "kısa"},
        )
        check(
            "21. impersonate reason<10 → 400 invalid_reason",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_reason",
            f"status={r.status_code}",
        )

        # ===== 22. impersonate pasif → 403 =====
        r = sc.post(
            f"/api/v2/admin/users/{seed['inactive_id']}/impersonate",
            json={"reason": "Pasif kullanıcı testi - 10+ karakter"},
        )
        check(
            "22. impersonate pasif → 403 target_inactive",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "target_inactive",
            f"status={r.status_code}",
        )

        # ===== 23. /independent-teachers happy =====
        r = sc.get("/api/v2/admin/independent-teachers")
        ok = (
            r.status_code == 200
            and "summary" in r.json()
            and "rows" in r.json()
            and isinstance(r.json()["rows"], list)
        )
        check(
            "23. /independent-teachers happy",
            ok,
            f"status={r.status_code}",
        )

    finally:
        _cleanup(seed, extra_ids)
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
