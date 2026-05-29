"""API v2 /auth P3 — Signup + email doğrulama smoke (Dalga 7 P3).

Senaryolar:
   1. signup/teacher happy → 200 + cookie + email_verification_sent + user oluştu (TEACHER, solo)
   2. signup/teacher email_taken → 409
   3. signup/teacher password_mismatch → 422
   4. signup/teacher accept_terms yok → 422
   5. signup sonrası user email_verified_at NULL (soft, doğrulanmamış)
   6. verify-email happy → 200 + email_verified_at dolar
   7. verify-email aynı token tekrar → 400 (tek kullanım)
   8. signup/invite info — geçerli davet → valid=True + role/email
   9. signup/invite info — bilinmeyen token → valid=False status=not_found
  10. signup/invite happy → 200 + davet consumed + user kurum rolünde
  11. signup/invite kullanılmış davet tekrar → 410
  12. resend-verification (login'li, doğrulanmamış) → 200
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

from app.config import settings
from app.database import SessionLocal
from app.models import (
    EmailVerificationToken,
    Institution,
    Invitation,
    SuspiciousIp,
    User,
    UserRole,
    invitation_default_expiry,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2authp3_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
INVITE_EMAIL = f"{PFX}_invited@test.invalid"
PASSWORD = "TeacherPass1!@xyz"
ACCESS = settings.auth_cookie_access_name

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
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()
        inv = Invitation(
            token=f"{PFX}_invtok_{secrets.token_hex(6)}",
            email=INVITE_EMAIL, full_name="Davetli Öğretmen",
            role=UserRole.TEACHER, institution_id=inst.id,
            expires_at=invitation_default_expiry(),
        )
        db.add(inv)
        db.flush()
        out = {"inst_id": inst.id, "inv_token": inv.token, "inv_id": inv.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        emails = [TEACHER_EMAIL, INVITE_EMAIL]
        users = db.query(User).filter(User.email.in_(emails)).all()
        uids = [u.id for u in users]
        if uids:
            db.execute(sa_delete(EmailVerificationToken).where(EmailVerificationToken.user_id.in_(uids)))
        db.execute(sa_delete(Invitation).where(Invitation.id == seed["inv_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        if uids:
            db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _user(email: str) -> User | None:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).first()


def _latest_verify_token(user_id: int) -> str | None:
    with SessionLocal() as db:
        row = (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.user_id == user_id)
            .order_by(EmailVerificationToken.id.desc())
            .first()
        )
        return row.token if row else None


def main() -> int:
    print(f"\n=== API v2 /auth P3 (signup + email doğrulama) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']} inv={seed['inv_token'][:16]}…\n")

    try:
        # 1. signup/teacher happy + intended_plan='solo_pro' (yeni: post_trial_plan kaydı)
        get_login_limiter().reset()
        c = TestClient(app)
        r = c.post("/api/v2/auth/signup/teacher", json={
            "full_name": "Yeni Öğretmen", "email": TEACHER_EMAIL,
            "password": PASSWORD, "password_confirm": PASSWORD, "accept_terms": True,
            "intended_plan": "solo_pro"})
        j = r.json() if r.text else {}
        cookies = {ck.name for ck in c.cookies.jar}
        u = _user(TEACHER_EMAIL)
        ok = (
            r.status_code == 200 and ACCESS in cookies
            and j.get("user", {}).get("email") == TEACHER_EMAIL
            and u is not None and u.role == UserRole.TEACHER and u.institution_id is None
            and u.plan == "solo_trial"
            and u.post_trial_plan == "solo_pro"  # ← intended_plan yansıdı
        )
        check("1. signup/teacher happy + cookie + user + intended_plan", ok,
              f"status={r.status_code} plan={u.plan if u else None} post_trial={u.post_trial_plan if u else None}")
        teacher_id = u.id if u else None

        # 5. (önce) email_verified_at NULL
        check("5. signup sonrası email doğrulanmamış (soft)",
              u is not None and u.email_verified_at is None, "")

        # 2. email_taken
        get_login_limiter().reset()
        r = TestClient(app).post("/api/v2/auth/signup/teacher", json={
            "full_name": "Tekrar", "email": TEACHER_EMAIL,
            "password": PASSWORD, "password_confirm": PASSWORD, "accept_terms": True})
        check("2. signup/teacher email_taken → 409", r.status_code == 409, f"status={r.status_code}")

        # 3. password_mismatch
        get_login_limiter().reset()
        r = TestClient(app).post("/api/v2/auth/signup/teacher", json={
            "full_name": "X", "email": f"x-{TEACHER_EMAIL}",
            "password": PASSWORD, "password_confirm": "BASKA1!@xyz", "accept_terms": True})
        check("3. password_mismatch → 422", r.status_code == 422, f"status={r.status_code}")

        # 4. accept_terms yok
        get_login_limiter().reset()
        r = TestClient(app).post("/api/v2/auth/signup/teacher", json={
            "full_name": "Y", "email": f"y-{TEACHER_EMAIL}",
            "password": PASSWORD, "password_confirm": PASSWORD, "accept_terms": False})
        check("4. accept_terms yok → 422", r.status_code == 422, f"status={r.status_code}")

        # 6. verify-email happy
        vtok = _latest_verify_token(teacher_id) if teacher_id else None
        r = TestClient(app).post(f"/api/v2/auth/verify-email/{vtok}")
        ok = r.status_code == 200
        u2 = _user(TEACHER_EMAIL)
        check("6. verify-email happy + verified", ok and u2 is not None and u2.email_verified_at is not None,
              f"status={r.status_code} verified={u2.email_verified_at if u2 else None}")

        # 7. verify-email aynı token tekrar → 400
        r = TestClient(app).post(f"/api/v2/auth/verify-email/{vtok}")
        check("7. verify-email tekrar → 400", r.status_code == 400, f"status={r.status_code}")

        # 8. invite info geçerli
        r = TestClient(app).get(f"/api/v2/auth/signup/invite/{seed['inv_token']}")
        j = r.json() if r.text else {}
        ok = r.status_code == 200 and j.get("valid") is True and j.get("role") == "teacher" and j.get("email") == INVITE_EMAIL
        check("8. invite info geçerli → valid", ok, f"status={r.status_code} {j}")

        # 9. invite info bilinmeyen
        r = TestClient(app).get("/api/v2/auth/signup/invite/bilinmeyen_token_xyz")
        j = r.json() if r.text else {}
        check("9. invite info bilinmeyen → not_found", r.status_code == 200 and j.get("valid") is False and j.get("status") == "not_found",
              f"status={r.status_code} {j}")

        # 10. invite signup happy
        get_login_limiter().reset()
        ic = TestClient(app)
        r = ic.post(f"/api/v2/auth/signup/invite/{seed['inv_token']}", json={
            "full_name": "Davetli Öğretmen", "email": INVITE_EMAIL,
            "password": PASSWORD, "password_confirm": PASSWORD, "accept_terms": True})
        iu = _user(INVITE_EMAIL)
        ok = (
            r.status_code == 200 and ACCESS in {ck.name for ck in ic.cookies.jar}
            and iu is not None and iu.institution_id == seed["inst_id"] and iu.role == UserRole.TEACHER
        )
        check("10. invite signup happy + kurum rolü", ok, f"status={r.status_code} {r.text[:120]}")
        with SessionLocal() as db:
            inv = db.get(Invitation, seed["inv_id"])
            check("10b. davet consumed", inv is not None and inv.consumed_at is not None, "")

        # 11. kullanılmış davet tekrar → 410
        get_login_limiter().reset()
        r = TestClient(app).post(f"/api/v2/auth/signup/invite/{seed['inv_token']}", json={
            "full_name": "Z", "email": f"z-{INVITE_EMAIL}",
            "password": PASSWORD, "password_confirm": PASSWORD, "accept_terms": True})
        check("11. kullanılmış davet → 410", r.status_code == 410, f"status={r.status_code}")

        # 12. resend-verification (invite user login'li, doğrulanmamış)
        r = ic.post("/api/v2/auth/resend-verification")
        check("12. resend-verification → 200", r.status_code == 200, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


from app.main import app  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
