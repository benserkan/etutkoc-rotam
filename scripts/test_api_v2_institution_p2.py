"""API v2 /institution/* smoke — Dalga 4 Paket 2.

Senaryolar (18):
   1. /invitations list — başlangıçta 0
   2. POST /invitations açık (email yok) → 201, signup_url tam URL
   3. POST /invitations hedefli (email var) → 201
   4. POST /invitations zaten kayıtlı user email → 409 email_exists
   5. /invitations list → 2 davetiye
   6. POST /invitations/{id}/revoke → revoked durumu
   7. POST /invitations/{id}/revoke (tekrar) → 409 invitation_not_usable
   8. /invitations list → revoked davetiye expired/revoked statüsünde
   9. /activity-heatmap?weeks=4 → 28 cell/teacher
  10. /activity-heatmap?weeks=12 → 84 cell/teacher
  11. /activity-heatmap?weeks=99 → 4'e düşer
  12. /at-risk happy → counts + at_risk + healthy
  13. /at-risk BETA öğrencisi yok (tenant isolation)
  14. /burnout → items sorted by risk_score desc (risk=0 olanlar dahil değil)
  15. /cohorts?tab=grade → 200, active_tab=grade, 4 tab info
  16. /cohorts?tab=track → 200
  17. /cohorts?tab=invalid → grade'e düşer
  18. Cross-tenant invitation revoke → 404
  19. Cross-tenant invitation revoke yan etki yok (BETA davetiyesi hâlâ pending)
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
    Invitation,
    User,
    UserRole,
    invitation_default_expiry,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2inst2_{secrets.token_hex(3)}"
ALPHA_NAME = f"{PFX}_ALPHA"
BETA_NAME = f"{PFX}_BETA"
ALPHA_ADMIN_EMAIL = f"{PFX}_alpha_admin@test.invalid"
ALPHA_T1_EMAIL = f"{PFX}_alpha_t1@test.invalid"
BETA_ADMIN_EMAIL = f"{PFX}_beta_admin@test.invalid"
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
    """2 kurum + alpha admin + alpha öğretmen + öğrenci + beta admin + beta davetiye."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        alpha = Institution(
            name=ALPHA_NAME, slug=f"{PFX}-alpha",
            contact_email="alpha@test.invalid", plan="free", is_active=True,
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
        beta_admin = User(
            email=BETA_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Beta Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([alpha_admin, alpha_t1, beta_admin])
        db.flush()

        # Alpha öğrencisi (risk + burnout için)
        s_a1 = User(
            email=f"{PFX}_s_a1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Alpha S1", role=UserRole.STUDENT,
            institution_id=alpha.id, teacher_id=alpha_t1.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Beta öğrencisi (isolation check için — alpha admin görmemeli)
        s_b1 = User(
            email=f"{PFX}_s_b1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Beta S1", role=UserRole.STUDENT,
            institution_id=beta.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([s_a1, s_b1])
        db.flush()

        # Beta davetiyesi — alpha admin'in iptal edemeyeceği
        beta_inv = Invitation(
            token=secrets.token_urlsafe(32),
            email=None,
            full_name=f"{PFX} Beta davetli",
            role=UserRole.TEACHER,
            institution_id=beta.id,
            created_by_user_id=beta_admin.id,
            expires_at=invitation_default_expiry(),
        )
        db.add(beta_inv)
        db.flush()

        db.commit()
        return {
            "alpha_id": alpha.id,
            "beta_id": beta.id,
            "alpha_admin_id": alpha_admin.id,
            "alpha_t1_id": alpha_t1.id,
            "beta_admin_id": beta_admin.id,
            "s_a1_id": s_a1.id,
            "s_b1_id": s_b1.id,
            "beta_inv_id": beta_inv.id,
            "beta_inv_token": beta_inv.token,
        }


def _cleanup(seed: dict, extra_inv_ids: list[int]) -> None:
    """Test verisini sil."""
    with SessionLocal() as db:
        user_ids = [
            seed["alpha_admin_id"], seed["alpha_t1_id"], seed["beta_admin_id"],
            seed["s_a1_id"], seed["s_b1_id"],
        ]
        inv_ids = [seed["beta_inv_id"]] + extra_inv_ids
        db.execute(sa_delete(Invitation).where(
            sa_or(
                Invitation.id.in_(inv_ids),
                Invitation.institution_id.in_([seed["alpha_id"], seed["beta_id"]]),
            )
        ))
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id.in_([seed["alpha_id"], seed["beta_id"]])
        ))
        from app.models import AuditLog
        db.execute(sa_delete(AuditLog).where(sa_or(
            AuditLog.actor_id.in_(user_ids),
            AuditLog.target_id.in_(user_ids),
        )))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /institution P2 smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded alpha_inst={seed['alpha_id']} beta_inst={seed['beta_id']} "
        f"alpha_t1={seed['alpha_t1_id']} s_a1={seed['s_a1_id']} "
        f"beta_inv={seed['beta_inv_id']}\n"
    )

    extra_inv_ids: list[int] = []
    try:
        alpha_admin = _login_v2(ALPHA_ADMIN_EMAIL)

        # ===== 1. /invitations list — başlangıçta 0 =====
        r = alpha_admin.get("/api/v2/institution/invitations")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("total") == 0
            and isinstance(body.get("items"), list)
            and "origin" in body
        )
        check(
            "1. /invitations list başlangıçta boş",
            ok,
            f"status={r.status_code} total={body.get('total')}",
        )

        # ===== 2. POST /invitations açık (email YOK) =====
        r = alpha_admin.post("/api/v2/institution/invitations", json={
            "full_name": "Açık Davetli",
        })
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 201
            and data.get("email") is None
            and data.get("status") == "pending"
            and "/signup/invite/" in data.get("signup_url", "")
            and data.get("is_usable") is True
        )
        check(
            "2. POST /invitations açık (email yok)",
            ok,
            f"status={r.status_code} data={data}",
        )
        open_inv_id = data.get("id")
        if open_inv_id:
            extra_inv_ids.append(int(open_inv_id))

        # ===== 3. POST /invitations hedefli (email var) =====
        target_email = f"{PFX}_invitee@test.invalid"
        r = alpha_admin.post("/api/v2/institution/invitations", json={
            "full_name": "Hedefli Davetli",
            "email": target_email,
        })
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 201
            and data.get("email") == target_email
            and data.get("status") == "pending"
        )
        check(
            "3. POST /invitations hedefli",
            ok,
            f"status={r.status_code} email={data.get('email')}",
        )
        targeted_inv_id = data.get("id")
        if targeted_inv_id:
            extra_inv_ids.append(int(targeted_inv_id))

        # ===== 4. POST /invitations zaten kayıtlı user email → 409 =====
        r = alpha_admin.post("/api/v2/institution/invitations", json={
            "email": ALPHA_T1_EMAIL,  # mevcut öğretmen
        })
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 409 and detail.get("code") == "email_exists"
        check(
            "4. POST /invitations mevcut user email → 409",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 5. /invitations list → 2 davetiye =====
        r = alpha_admin.get("/api/v2/institution/invitations")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and body.get("total") == 2
            and any(i.get("email") == target_email for i in items)
            and any(i.get("email") is None for i in items)
        )
        check(
            "5. /invitations list 2 davetiye",
            ok,
            f"total={body.get('total')} emails={[i.get('email') for i in items]}",
        )

        # ===== 6. POST /invitations/{id}/revoke =====
        r = alpha_admin.post(
            f"/api/v2/institution/invitations/{open_inv_id}/revoke"
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("status") == "revoked"
            and data.get("is_usable") is False
            and data.get("revoked_at") is not None
        )
        check(
            "6. POST /invitations/{id}/revoke",
            ok,
            f"status={r.status_code} resp_status={data.get('status')}",
        )

        # ===== 7. POST /invitations/{id}/revoke (tekrar) → 409 =====
        r = alpha_admin.post(
            f"/api/v2/institution/invitations/{open_inv_id}/revoke"
        )
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = (
            r.status_code == 409
            and detail.get("code") == "invitation_not_usable"
        )
        check(
            "7. POST /invitations/{id}/revoke idempotent guard",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 8. list — revoked görünür =====
        r = alpha_admin.get("/api/v2/institution/invitations")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        revoked_one = next((i for i in items if i.get("id") == open_inv_id), None)
        ok = (
            revoked_one is not None
            and revoked_one.get("status") == "revoked"
        )
        check(
            "8. /invitations list revoked görünür",
            ok,
            f"revoked={revoked_one}",
        )

        # ===== 9. /activity-heatmap?weeks=4 =====
        r = alpha_admin.get("/api/v2/institution/activity-heatmap?weeks=4")
        body = r.json() if r.text else {}
        teachers_resp = body.get("teachers", [])
        ok = (
            r.status_code == 200
            and body.get("weeks") == 4
            and body.get("days_count") == 28
            and len(teachers_resp) >= 1
            and all(len(t.get("cells", [])) == 28 for t in teachers_resp)
        )
        check(
            "9. /activity-heatmap?weeks=4 → 28 cell/teacher",
            ok,
            f"status={r.status_code} weeks={body.get('weeks')} days={body.get('days_count')} teachers={len(teachers_resp)}",
        )

        # ===== 10. /activity-heatmap?weeks=12 =====
        r = alpha_admin.get("/api/v2/institution/activity-heatmap?weeks=12")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("weeks") == 12
            and body.get("days_count") == 84
            and all(len(t.get("cells", [])) == 84 for t in body.get("teachers", []))
        )
        check(
            "10. /activity-heatmap?weeks=12 → 84 cell",
            ok,
            f"weeks={body.get('weeks')} days={body.get('days_count')}",
        )

        # ===== 11. /activity-heatmap?weeks=99 → 4'e düşer =====
        r = alpha_admin.get("/api/v2/institution/activity-heatmap?weeks=99")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("weeks") == 4
        check(
            "11. /activity-heatmap?weeks=99 → 4'e clamp",
            ok,
            f"weeks={body.get('weeks')}",
        )

        # ===== 12. /at-risk happy =====
        r = alpha_admin.get("/api/v2/institution/at-risk")
        body = r.json() if r.text else {}
        counts = body.get("counts", {})
        ok = (
            r.status_code == 200
            and "critical" in counts and "high" in counts and "medium" in counts
            and "total_students" in body
            and "healthy_count" in body
            and isinstance(body.get("at_risk"), list)
        )
        check(
            "12. /at-risk happy",
            ok,
            f"status={r.status_code} keys={list(body.keys())}",
        )

        # ===== 13. /at-risk Beta öğrencisi yok (tenant isolation) =====
        at_risk_ids = {a.get("student_id") for a in body.get("at_risk", [])}
        ok = seed["s_b1_id"] not in at_risk_ids and body.get("total_students") == 1
        check(
            "13. /at-risk tenant izolasyon",
            ok,
            f"total={body.get('total_students')} at_risk_ids={at_risk_ids} beta_s={seed['s_b1_id']}",
        )

        # ===== 14. /burnout =====
        r = alpha_admin.get("/api/v2/institution/burnout")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and isinstance(items, list)
            # Sıralama: risk_score desc (test verisinde 0/1 öğrenci, hep doğru)
            and all(
                items[i]["risk_score"] >= items[i + 1]["risk_score"]
                for i in range(len(items) - 1)
            )
            # risk=0 olanlar listede DEĞİL
            and all(it.get("risk_score", 0) > 0 for it in items)
        )
        check(
            "14. /burnout sıralama + risk=0 atılır",
            ok,
            f"status={r.status_code} item_count={len(items)} scores={[i.get('risk_score') for i in items]}",
        )

        # ===== 15. /cohorts?tab=grade =====
        r = alpha_admin.get("/api/v2/institution/cohorts?tab=grade")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("active_tab") == "grade"
            and len(body.get("tabs", [])) == 4
            and isinstance(body.get("cohorts"), list)
            and "wow" in body
        )
        check(
            "15. /cohorts?tab=grade",
            ok,
            f"status={r.status_code} active={body.get('active_tab')} tabs={len(body.get('tabs', []))}",
        )

        # ===== 16. /cohorts?tab=track =====
        r = alpha_admin.get("/api/v2/institution/cohorts?tab=track")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("active_tab") == "track"
        check(
            "16. /cohorts?tab=track",
            ok,
            f"active={body.get('active_tab')}",
        )

        # ===== 17. /cohorts?tab=invalid → grade =====
        r = alpha_admin.get("/api/v2/institution/cohorts?tab=foobar")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("active_tab") == "grade"
        check(
            "17. /cohorts?tab=invalid → grade",
            ok,
            f"active={body.get('active_tab')}",
        )

        # ===== 18. Cross-tenant invitation revoke → 404 =====
        r = alpha_admin.post(
            f"/api/v2/institution/invitations/{seed['beta_inv_id']}/revoke"
        )
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 404 and detail.get("code") == "invitation_not_found"
        check(
            "18. cross-tenant invitation revoke → 404",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 19. BETA davetiyesi hâlâ pending (yan etki yok) =====
        with SessionLocal() as db:
            beta_inv = db.get(Invitation, seed["beta_inv_id"])
            ok = (
                beta_inv is not None
                and beta_inv.revoked_at is None
                and beta_inv.is_usable is True
            )
            check(
                "19. cross-tenant revoke yan etki yok",
                ok,
                f"revoked_at={beta_inv.revoked_at if beta_inv else 'NULL'}",
            )

    finally:
        _cleanup(seed, extra_inv_ids)

    print(f"\n=== SONUÇ ===\n  PASSED: {passed}\n  FAILED: {len(failed)}")
    for f in failed:
        print(f"    - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
