"""API v2 abonelik talebi + süper admin aktivasyon smoke (Abonelik Faz 2).

Senaryolar:
   1. solo koç POST /teacher/subscription-request → 200 ok + ContactRequest (subscription_request)
   2. tekrar → 200 already_pending True (idempotent, tek kayıt)
   3. kurum öğretmeni → 403 managed_by_institution
   4. süper admin /admin/users/{coach}/activate-plan solo_pro → 200 + plan=solo_pro
   5. kurum öğretmenine activate-plan → 400 not_solo_teacher
   6. geçersiz plan → 400 invalid_plan
   7. olmayan kullanıcı → 404
   8. öğretmen (admin değil) activate-plan → 403
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
from app.models import ContactRequest, Institution, User, UserRole
from app.models.plan_history import PlanChangeHistory, PlanOwnerType
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"subreq_{secrets.token_hex(3)}"
PWD = hash_password("SubReq!23xyz")
PWDH = "SubReq!23xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    print(f"\n=== abonelik talebi + aktivasyon smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    ids: dict[str, int] = {}
    coach_email = f"{PFX}_coach@test.invalid"
    try:
        with SessionLocal() as db:
            coach = User(
                email=coach_email, password_hash=PWD, full_name=f"{PFX} Koç",
                role=UserRole.TEACHER, institution_id=None, is_active=True,
                plan="solo_free", password_changed_at=now, must_change_password=False)
            db.add(coach); db.flush()
            for i in range(3):
                db.add(User(email=f"{PFX}_s{i}@test.invalid", password_hash=PWD,
                            full_name=f"{PFX} Öğr {i}", role=UserRole.STUDENT,
                            teacher_id=coach.id, institution_id=None, grade_level=8,
                            is_active=True, password_changed_at=now, must_change_password=False))
            admin = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                         full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
                         password_changed_at=now, must_change_password=False)
            db.add(admin)
            inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", plan="free", is_active=True)
            db.add(inst); db.flush()
            kteacher = User(email=f"{PFX}_kt@test.invalid", password_hash=PWD,
                            full_name=f"{PFX} KurumKoç", role=UserRole.TEACHER,
                            institution_id=inst.id, is_active=True,
                            password_changed_at=now, must_change_password=False)
            db.add(kteacher)
            db.commit()
            ids = {"coach": coach.id, "admin": admin.id, "inst": inst.id, "kt": kteacher.id}

        def login(email):
            c = TestClient(app)
            r = c.post("/api/v2/auth/login", json={"email": email, "password": PWDH})
            if r.status_code != 200:
                raise RuntimeError(f"login {email}: {r.status_code} {r.text[:120]}")
            return c

        coach_cli = login(coach_email)
        admin_cli = login(f"{PFX}_admin@test.invalid")
        kt_cli = login(f"{PFX}_kt@test.invalid")

        # 1. koç talep
        r = coach_cli.post("/api/v2/teacher/subscription-request", json={"plan": "solo_pro", "cycle": "monthly"})
        j = r.json()
        check("1. koç subscription-request → 200 ok",
              r.status_code == 200 and j["data"]["ok"] and not j["data"]["already_pending"], f"{r.text[:160]}")
        with SessionLocal() as db:
            cnt = db.query(ContactRequest).filter(
                ContactRequest.email == coach_email,
                ContactRequest.source == "subscription_request").count()
        check("1b. ContactRequest oluştu (subscription_request)", cnt == 1, f"cnt={cnt}")

        # 2. idempotent
        r = coach_cli.post("/api/v2/teacher/subscription-request", json={"plan": "solo_pro", "cycle": "academic_year"})
        check("2. tekrar → already_pending True",
              r.status_code == 200 and r.json()["data"]["already_pending"] is True, f"{r.text[:160]}")
        with SessionLocal() as db:
            cnt = db.query(ContactRequest).filter(
                ContactRequest.email == coach_email,
                ContactRequest.source == "subscription_request").count()
        check("2b. hâlâ tek kayıt", cnt == 1, f"cnt={cnt}")

        # 3. kurum öğretmeni → 403
        r = kt_cli.post("/api/v2/teacher/subscription-request", json={"plan": "solo_pro"})
        check("3. kurum öğretmeni → 403 managed_by_institution",
              r.status_code == 403 and r.json()["detail"]["code"] == "managed_by_institution", f"status={r.status_code}")

        # 4. admin aktive et
        r = admin_cli.post(f"/api/v2/admin/users/{ids['coach']}/activate-plan", json={"plan": "solo_pro"})
        check("4. admin activate-plan solo_pro → 200", r.status_code == 200, f"{r.text[:160]}")
        with SessionLocal() as db:
            coach = db.get(User, ids["coach"])
            check("4b. koç planı solo_pro oldu", coach.plan == "solo_pro", f"plan={coach.plan}")

        # 5. kurum öğretmenine activate → 400 not_solo_teacher
        r = admin_cli.post(f"/api/v2/admin/users/{ids['kt']}/activate-plan", json={"plan": "solo_pro"})
        check("5. kurum öğretmenine → 400 not_solo_teacher",
              r.status_code == 400 and r.json()["detail"]["code"] == "not_solo_teacher", f"status={r.status_code}")

        # 6. geçersiz plan
        r = admin_cli.post(f"/api/v2/admin/users/{ids['coach']}/activate-plan", json={"plan": "etut_standart"})
        check("6. geçersiz plan → 400 invalid_plan",
              r.status_code == 400 and r.json()["detail"]["code"] == "invalid_plan", f"status={r.status_code}")

        # 7. olmayan kullanıcı
        r = admin_cli.post("/api/v2/admin/users/99999999/activate-plan", json={"plan": "solo_pro"})
        check("7. olmayan kullanıcı → 404", r.status_code == 404, f"status={r.status_code}")

        # 8. öğretmen (admin değil) → 403
        r = coach_cli.post(f"/api/v2/admin/users/{ids['coach']}/activate-plan", json={"plan": "solo_pro"})
        check("8. admin olmayan → 403", r.status_code == 403, f"status={r.status_code}")

    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ContactRequest).where(ContactRequest.email == coach_email))
            uids = [ids.get("coach"), ids.get("admin"), ids.get("kt")]
            sids = [r.id for r in db.query(User).filter(User.email.like(f"{PFX}_s%")).all()]
            db.execute(sa_delete(User).where(User.id.in_([u for u in sids])))
            for uid in uids:
                if uid:
                    db.execute(sa_delete(PlanChangeHistory).where(
                        PlanChangeHistory.owner_id == uid,
                        PlanChangeHistory.owner_type == PlanOwnerType.USER))
                    db.execute(sa_delete(User).where(User.id == uid))
            if ids.get("inst"):
                db.execute(sa_delete(Institution).where(Institution.id == ids["inst"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
