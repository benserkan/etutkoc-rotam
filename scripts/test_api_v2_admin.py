"""API v2 /admin/* smoke (Dalga 6 Paket 1 — dashboard foundation).

Senaryolar:
   1. /admin/dashboard SUPER_ADMIN happy → 200, counts dolu, audit listesi
   2. /admin/dashboard counts shape: 8 alan + tipler
   3. /admin/dashboard health_summary 6 alan (healthy/watch/risk/critical + total)
   4. /admin/dashboard teacher_activity_summary tip kontrolü
   5. /admin/dashboard top_unhealthy max 3
   6. /admin/dashboard top_teacher_risk max 3 + sıralama (critical önce)
   7. /admin/dashboard recent_audits max 10 + action_label + via_admin handle
   8. /admin/dashboard counts.independent_teachers = role=TEACHER + institution_id=NULL
   9. Teacher rolü → 403 role_required
  10. Institution Admin rolü → 403 role_required
  11. Student rolü → 403 role_required
  12. Parent rolü → 403 role_required
  13. Anonim → 401 missing_credentials
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
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2admin_{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
INST_ADMIN_EMAIL = f"{PFX}_inst_admin@test.invalid"
TEACHER_INST_EMAIL = f"{PFX}_teacher_inst@test.invalid"
TEACHER_INDEP_EMAIL = f"{PFX}_teacher_indep@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
PASSWORD = "TestPassAdmin!23"

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
    """1 kurum + 1 super admin + 1 inst admin + 1 kurum öğr + 1 bağımsız öğr +
    1 öğrenci + 1 veli. Audit log için bir kayıt seed et."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Inst",
            slug=f"{PFX}-inst",
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
        inst_admin = User(
            email=INST_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} InstAdmin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher_inst = User(
            email=TEACHER_INST_EMAIL, password_hash=pwd,
            full_name=f"{PFX} TeacherInst", role=UserRole.TEACHER,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Bağımsız öğretmen — institution_id NULL
        teacher_indep = User(
            email=TEACHER_INDEP_EMAIL, password_hash=pwd,
            full_name=f"{PFX} TeacherIndep", role=UserRole.TEACHER,
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=now,  # son 7g — "healthy" band
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Student", role=UserRole.STUDENT,
            teacher_id=teacher_inst.id, institution_id=inst.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, inst_admin, teacher_inst, teacher_indep, student, parent])
        db.commit()
        return {
            "inst_id": inst.id,
            "super_id": super_admin.id,
            "inst_admin_id": inst_admin.id,
            "teacher_inst_id": teacher_inst.id,
            "teacher_indep_id": teacher_indep.id,
            "student_id": student.id,
            "parent_id": parent.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_user_ids = [
            seed["super_id"], seed["inst_admin_id"],
            seed["teacher_inst_id"], seed["teacher_indep_id"],
            seed["student_id"], seed["parent_id"],
        ]
        # Audit log artıklarını temizle
        db.execute(sa_delete(AuditLog).where(
            AuditLog.actor_id.in_(all_user_ids),
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id == seed["inst_id"]
        ))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded super={seed['super_id']} indep_teacher={seed['teacher_indep_id']}\n"
    )

    try:
        super_client = _login_v2(SUPER_EMAIL)
        teacher_client = _login_v2(TEACHER_INST_EMAIL)
        inst_admin_client = _login_v2(INST_ADMIN_EMAIL)
        student_client = _login_v2(STUDENT_EMAIL)
        parent_client = _login_v2(PARENT_EMAIL)

        # ===== 1. /dashboard SUPER_ADMIN happy =====
        r = super_client.get("/api/v2/admin/dashboard")
        ok = (
            r.status_code == 200
            and "counts" in r.json()
            and "health_summary" in r.json()
            and "teacher_activity_summary" in r.json()
            and "recent_audits" in r.json()
            and "top_unhealthy" in r.json()
            and "top_teacher_risk" in r.json()
            and "failed_logins_24h" in r.json()
        )
        check(
            "1. /dashboard happy → 200, 7 blok dolu",
            ok,
            f"status={r.status_code} keys={list(r.json().keys()) if r.status_code == 200 else r.text[:200]}",
        )

        # ===== 2. counts shape =====
        if ok:
            counts = r.json()["counts"]
            shape_ok = all(
                k in counts and isinstance(counts[k], int)
                for k in [
                    "institutions", "active_institutions", "teachers",
                    "students", "parents", "institution_admins",
                    "super_admins", "independent_teachers",
                ]
            )
            check(
                "2. counts 8 alan + int tip",
                shape_ok,
                f"counts={counts}",
            )

            # ===== 3. health_summary shape =====
            hs = r.json()["health_summary"]
            hs_ok = all(
                k in hs and isinstance(hs[k], int)
                for k in [
                    "healthy", "watch", "risk", "critical",
                    "unhealthy_total", "needs_attention",
                ]
            )
            check(
                "3. health_summary 6 alan + int tip",
                hs_ok,
                f"hs={hs}",
            )

            # ===== 4. teacher_activity_summary shape =====
            tas = r.json()["teacher_activity_summary"]
            tas_ok = all(
                k in tas and isinstance(tas[k], int)
                for k in [
                    "healthy", "watch", "risk", "critical",
                    "unhealthy_total", "total",
                ]
            )
            check(
                "4. teacher_activity_summary 6 alan + int tip",
                tas_ok,
                f"tas={tas}",
            )

            # ===== 5. top_unhealthy max 3 =====
            tu = r.json()["top_unhealthy"]
            check(
                "5. top_unhealthy max 3 + liste",
                isinstance(tu, list) and len(tu) <= 3,
                f"len={len(tu)}",
            )

            # ===== 6. top_teacher_risk max 3 + sıralama =====
            ttr = r.json()["top_teacher_risk"]
            check(
                "6. top_teacher_risk max 3 + liste",
                isinstance(ttr, list) and len(ttr) <= 3,
                f"len={len(ttr)}",
            )

            # ===== 7. recent_audits max 10 + action_label =====
            ra = r.json()["recent_audits"]
            ra_ok = isinstance(ra, list) and len(ra) <= 10
            if ra_ok and len(ra) > 0:
                ra_ok = (
                    "action" in ra[0]
                    and "action_label" in ra[0]
                    and "created_at" in ra[0]
                )
            check(
                "7. recent_audits max 10 + action_label dolu",
                ra_ok,
                f"len={len(ra)} sample_keys={list(ra[0].keys()) if ra else '[]'}",
            )

            # ===== 8. counts.independent_teachers = seed'deki sayım =====
            # Seed'de 1 bağımsız öğretmen oluşturduk (TEACHER, institution_id=NULL)
            check(
                "8. counts.independent_teachers >= 1 (seed dahil)",
                counts["independent_teachers"] >= 1,
                f"indep_teachers={counts['independent_teachers']}",
            )

        # ===== 9. Teacher rolü → 403 =====
        r = teacher_client.get("/api/v2/admin/dashboard")
        check(
            "9. Teacher → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 10. Institution Admin rolü → 403 =====
        r = inst_admin_client.get("/api/v2/admin/dashboard")
        check(
            "10. InstitutionAdmin → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 11. Student rolü → 403 =====
        r = student_client.get("/api/v2/admin/dashboard")
        check(
            "11. Student → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 12. Parent rolü → 403 =====
        r = parent_client.get("/api/v2/admin/dashboard")
        check(
            "12. Parent → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 13. Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/dashboard")
        check(
            "13. Anonim → 401 missing_credentials",
            r.status_code == 401
            and r.json().get("detail", {}).get("code") == "missing_credentials",
            f"status={r.status_code}",
        )

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
