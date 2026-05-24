"""API v2 /institution/* smoke (Dalga 4 Paket 1).

Senaryolar (15):
   1. /institution/dashboard happy → 200, aggregate + risk + inactive blokları
   2. /institution/dashboard teacher_summaries listesi 2 öğretmenle dolu
   3. /institution/teachers list → 2 öğretmen, agrega
   4. /institution/teachers POST happy → 201, temp_password issued, must_change_password=true
   5. /institution/teachers POST email duplicate → 409
   6. /institution/teachers POST email validation → 422 (Pydantic)
   7. /institution/teachers/{id}/deactivate → is_active=False + invalidate keys
   8. /institution/teachers/{id}/activate → is_active=True
   9. /institution/teachers/{id}/pause-alerts → is_paused=True, pause_reason=manual
  10. /institution/teachers/{id}/resume-alerts → is_paused=False
  11. /institution/teachers/{id} kart → öğrenciler + overall_rate
  12. /institution/teachers/{id} cross-tenant → 404
  13. /institution/roster (filtresiz) → 3 öğrenci + filter options (2 öğretmen seç + sınıflar)
  14. /institution/roster?teacher_id=X → sadece o öğretmenin öğrencileri
  15. /institution/roster?grade=8 → sadece 8. sınıf
  16. /institution/goals → agrega yapı
  17. Öğretmen rolü /institution/dashboard'a → 403 role_required
  18. Tenant izolasyon: ALPHA admin BETA öğretmenini görmez (404)

Test verisi: secrets prefix; gerçek hesaplara dokunulmaz.
Çalışırken yeni öğretmen create edilirse cleanup'ta o da silinir.
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
from sqlalchemy import delete as sa_delete, or_ as sa_or

from app.database import SessionLocal
from app.main import app
from app.models import (
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2inst_{secrets.token_hex(3)}"
ALPHA_NAME = f"{PFX}_ALPHA"
BETA_NAME = f"{PFX}_BETA"
ALPHA_ADMIN_EMAIL = f"{PFX}_alpha_admin@test.invalid"
ALPHA_T1_EMAIL = f"{PFX}_alpha_t1@test.invalid"
ALPHA_T2_EMAIL = f"{PFX}_alpha_t2@test.invalid"
BETA_ADMIN_EMAIL = f"{PFX}_beta_admin@test.invalid"
BETA_T1_EMAIL = f"{PFX}_beta_t1@test.invalid"
PASSWORD = "TestPass!2345Inst"

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
    """2 kurum + her birinde admin + 2 öğretmen (BETA: 1) + birkaç öğrenci."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        alpha = Institution(
            name=ALPHA_NAME, slug=f"{PFX}-alpha",
            contact_email="alpha@test.invalid", plan="etut_standart", is_active=True,
        )
        beta = Institution(
            name=BETA_NAME, slug=f"{PFX}-beta",
            contact_email="beta@test.invalid", plan="free", is_active=True,
        )
        db.add_all([alpha, beta])
        db.flush()

        alpha_admin = User(
            email=ALPHA_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Alpha Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        alpha_t1 = User(
            email=ALPHA_T1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Alpha T1", role=UserRole.TEACHER,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        alpha_t2 = User(
            email=ALPHA_T2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Alpha T2", role=UserRole.TEACHER,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        beta_admin = User(
            email=BETA_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Beta Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        beta_t1 = User(
            email=BETA_T1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Beta T1", role=UserRole.TEACHER,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([alpha_admin, alpha_t1, alpha_t2, beta_admin, beta_t1])
        db.flush()

        # Alpha T1: 2 öğrenci (8 + 9. sınıf)
        s_a1 = User(
            email=f"{PFX}_s_a1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Alpha S1", role=UserRole.STUDENT,
            institution_id=alpha.id, teacher_id=alpha_t1.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        s_a2 = User(
            email=f"{PFX}_s_a2@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Alpha S2", role=UserRole.STUDENT,
            institution_id=alpha.id, teacher_id=alpha_t1.id,
            grade_level=9, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Alpha T2: 1 öğrenci (8. sınıf)
        s_a3 = User(
            email=f"{PFX}_s_a3@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Alpha S3", role=UserRole.STUDENT,
            institution_id=alpha.id, teacher_id=alpha_t2.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Beta T1: 1 öğrenci — Alpha admin'in görmemesi gereken
        s_b1 = User(
            email=f"{PFX}_s_b1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Beta S1", role=UserRole.STUDENT,
            institution_id=beta.id, teacher_id=beta_t1.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([s_a1, s_a2, s_a3, s_b1])
        db.flush()
        db.commit()

        return {
            "alpha_id": alpha.id,
            "beta_id": beta.id,
            "alpha_admin_id": alpha_admin.id,
            "alpha_t1_id": alpha_t1.id,
            "alpha_t2_id": alpha_t2.id,
            "beta_admin_id": beta_admin.id,
            "beta_t1_id": beta_t1.id,
            "s_a1_id": s_a1.id,
            "s_a2_id": s_a2.id,
            "s_a3_id": s_a3.id,
            "s_b1_id": s_b1.id,
        }


def _cleanup(seed: dict, extra_user_ids: list[int]) -> None:
    """Test verisini sil — gerçek hesaplara dokunma."""
    with SessionLocal() as db:
        all_ids = [
            seed["alpha_admin_id"], seed["alpha_t1_id"], seed["alpha_t2_id"],
            seed["beta_admin_id"], seed["beta_t1_id"],
            seed["s_a1_id"], seed["s_a2_id"], seed["s_a3_id"], seed["s_b1_id"],
        ] + extra_user_ids
        db.execute(sa_delete(User).where(User.id.in_(all_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id.in_([seed["alpha_id"], seed["beta_id"]])
        ))
        # Audit log artıklarını da temizle (cleanup safety)
        from app.models import AuditLog
        db.execute(sa_delete(AuditLog).where(sa_or(
            AuditLog.actor_id.in_(all_ids),
            AuditLog.target_id.in_(all_ids),
        )))
        db.commit()


def _login_v2(email: str) -> TestClient:
    """Yeni TestClient + login JWT cookie set'ler."""
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /institution smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded alpha_inst={seed['alpha_id']} beta_inst={seed['beta_id']} "
        f"alpha_t1={seed['alpha_t1_id']} alpha_t2={seed['alpha_t2_id']} "
        f"beta_t1={seed['beta_t1_id']}\n"
    )

    extra_user_ids: list[int] = []
    try:
        alpha_admin = _login_v2(ALPHA_ADMIN_EMAIL)

        # ===== 1. /dashboard happy =====
        r = alpha_admin.get("/api/v2/institution/dashboard")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("institution", {}).get("name") == ALPHA_NAME
            and "aggregate" in body and "risk" in body and "inactive" in body
            and "teacher_summaries" in body
        )
        check(
            "1. /dashboard happy",
            ok,
            f"status={r.status_code} keys={list(body.keys())}",
        )

        # ===== 2. /dashboard teacher_summaries — 2 öğretmen =====
        summaries = body.get("teacher_summaries", [])
        teacher_ids_in_resp = {s.get("id") for s in summaries}
        ok = (
            len(summaries) == 2
            and seed["alpha_t1_id"] in teacher_ids_in_resp
            and seed["alpha_t2_id"] in teacher_ids_in_resp
            and seed["beta_t1_id"] not in teacher_ids_in_resp
        )
        check(
            "2. /dashboard teacher_summaries — sadece alpha",
            ok,
            f"summaries={teacher_ids_in_resp} beta_t1={seed['beta_t1_id']}",
        )

        # ===== 3. /teachers list =====
        r = alpha_admin.get("/api/v2/institution/teachers")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and body.get("total") == 2
            and len(items) == 2
        )
        check(
            "3. /teachers list",
            ok,
            f"status={r.status_code} total={body.get('total')} items={len(items)}",
        )

        # ===== 4. POST /teachers happy =====
        new_email = f"{PFX}_new_teacher@test.invalid"
        r = alpha_admin.post("/api/v2/institution/teachers", json={
            "full_name": "Smoke Yeni Öğretmen",
            "email": new_email,
        })
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 201
            and data.get("email") == new_email
            and len(data.get("temp_password", "")) >= 8
            and data.get("must_change_password") is True
            and isinstance(body.get("invalidate"), list)
        )
        check(
            "4. POST /teachers happy",
            ok,
            f"status={r.status_code} data={data}",
        )
        new_teacher_id = data.get("id")
        if new_teacher_id:
            extra_user_ids.append(int(new_teacher_id))

        # ===== 5. POST /teachers duplicate email → 409 =====
        r = alpha_admin.post("/api/v2/institution/teachers", json={
            "full_name": "Tekrar Adam",
            "email": new_email,
        })
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = (
            r.status_code == 409
            and detail.get("code") == "email_exists"
        )
        check(
            "5. POST /teachers duplicate email",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 6. POST /teachers invalid email → 422 =====
        r = alpha_admin.post("/api/v2/institution/teachers", json={
            "full_name": "Bozuk Email",
            "email": "not-an-email",
        })
        ok = r.status_code == 422
        check(
            "6. POST /teachers invalid email",
            ok,
            f"status={r.status_code}",
        )

        # ===== 7. /teachers/{id}/deactivate =====
        target_tid = seed["alpha_t1_id"]
        r = alpha_admin.post(
            f"/api/v2/institution/teachers/{target_tid}/deactivate"
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("id") == target_tid
            and data.get("is_active") is False
            and isinstance(body.get("invalidate"), list)
            and any("dashboard" in k for k in body.get("invalidate", []))
        )
        check(
            "7. /teachers/{id}/deactivate",
            ok,
            f"status={r.status_code} is_active={data.get('is_active')}",
        )

        # ===== 8. /teachers/{id}/activate =====
        r = alpha_admin.post(
            f"/api/v2/institution/teachers/{target_tid}/activate"
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = r.status_code == 200 and data.get("is_active") is True
        check(
            "8. /teachers/{id}/activate",
            ok,
            f"status={r.status_code} is_active={data.get('is_active')}",
        )

        # ===== 9. /teachers/{id}/pause-alerts =====
        r = alpha_admin.post(
            f"/api/v2/institution/teachers/{target_tid}/pause-alerts"
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("is_paused") is True
            and data.get("pause_reason") == "manual"
        )
        check(
            "9. /teachers/{id}/pause-alerts",
            ok,
            f"status={r.status_code} is_paused={data.get('is_paused')} reason={data.get('pause_reason')}",
        )

        # ===== 10. /teachers/{id}/resume-alerts =====
        r = alpha_admin.post(
            f"/api/v2/institution/teachers/{target_tid}/resume-alerts"
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("is_paused") is False
        )
        check(
            "10. /teachers/{id}/resume-alerts",
            ok,
            f"status={r.status_code} is_paused={data.get('is_paused')}",
        )

        # ===== 11. /teachers/{id} kart =====
        r = alpha_admin.get(f"/api/v2/institution/teachers/{target_tid}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("teacher", {}).get("id") == target_tid
            and isinstance(body.get("students"), list)
            and len(body["students"]) == 2  # alpha_t1 → s_a1 + s_a2
        )
        check(
            "11. /teachers/{id} kart — öğrenci listesi",
            ok,
            f"status={r.status_code} student_count={len(body.get('students', []))}",
        )

        # ===== 12. /teachers/{id} cross-tenant → 404 =====
        r = alpha_admin.get(
            f"/api/v2/institution/teachers/{seed['beta_t1_id']}"
        )
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 404 and detail.get("code") == "teacher_not_found"
        check(
            "12. /teachers/{id} cross-tenant → 404",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 13. /roster (filtresiz) =====
        r = alpha_admin.get("/api/v2/institution/roster")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        filters = body.get("filters", {})
        ok = (
            r.status_code == 200
            and body.get("total") == 3
            # alpha_t1 + alpha_t2 + test #4'te oluşturulan yeni öğretmen
            and len(filters.get("teachers", [])) >= 2
            and 8 in filters.get("grades", [])
            and 9 in filters.get("grades", [])
            # BETA öğrencisinin orada olmaması
            and seed["s_b1_id"] not in {i.get("student_id") for i in items}
        )
        check(
            "13. /roster (filtresiz)",
            ok,
            f"status={r.status_code} total={body.get('total')} "
            f"teachers={len(filters.get('teachers', []))} "
            f"grades={filters.get('grades', [])} "
            f"items={len(items)} ids={[i.get('student_id') for i in items]}",
        )

        # ===== 14. /roster?teacher_id=alpha_t1 =====
        r = alpha_admin.get(
            f"/api/v2/institution/roster?teacher_id={seed['alpha_t1_id']}"
        )
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ids_in_resp = {i.get("student_id") for i in items}
        ok = (
            r.status_code == 200
            and body.get("total") == 2
            and {seed["s_a1_id"], seed["s_a2_id"]} == ids_in_resp
        )
        check(
            "14. /roster?teacher_id=alpha_t1",
            ok,
            f"status={r.status_code} ids={ids_in_resp}",
        )

        # ===== 15. /roster?grade=8 =====
        r = alpha_admin.get("/api/v2/institution/roster?grade=8")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ids_in_resp = {i.get("student_id") for i in items}
        ok = (
            r.status_code == 200
            and body.get("total") == 2
            and {seed["s_a1_id"], seed["s_a3_id"]} == ids_in_resp
        )
        check(
            "15. /roster?grade=8",
            ok,
            f"status={r.status_code} ids={ids_in_resp}",
        )

        # ===== 16. /goals agrega =====
        r = alpha_admin.get("/api/v2/institution/goals")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and "students_with_goals" in body
            and "students_without_goals" in body
            and "total_goals" in body
        )
        check(
            "16. /goals agrega",
            ok,
            f"status={r.status_code} keys={list(body.keys())}",
        )

        # ===== 17. Öğretmen rolü /dashboard → 403 =====
        teacher_client = _login_v2(ALPHA_T1_EMAIL)
        r = teacher_client.get("/api/v2/institution/dashboard")
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 403 and detail.get("code") == "role_required"
        check(
            "17. /dashboard öğretmen → 403 role_required",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 18. Tenant isolation: ALPHA admin BETA öğretmenini deaktive edemez =====
        r = alpha_admin.post(
            f"/api/v2/institution/teachers/{seed['beta_t1_id']}/deactivate"
        )
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 404 and detail.get("code") == "teacher_not_found"
        check(
            "18. tenant isolation — cross-tenant deactivate → 404",
            ok,
            f"status={r.status_code} detail={detail}",
        )

    finally:
        _cleanup(seed, extra_user_ids)

    print(f"\n=== SONUÇ ===\n  PASSED: {passed}\n  FAILED: {len(failed)}")
    for f in failed:
        print(f"    - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
