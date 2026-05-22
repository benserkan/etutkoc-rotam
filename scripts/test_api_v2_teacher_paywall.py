"""API v2 koç ödeme-duvarı (paywall) enforcement smoke (Faz 3).

Senaryolar:
   1. paywall koç (solo_free, 5>3 öğr) publish-day → 403 paywall_active
   2. paywall koç bulk-tasks {tasks:[]} → 403 paywall_active
   3. limit-altı koç (solo_free, 2 öğr) publish-day → 200 (gate geçti)
   4. trial koç (solo_trial, 5 öğr) publish-day → 200 (sınırsız, paywall yok)
   5. paywall koç öğrenci pasifleştir → 200 (öğrenci yönetimi engellenmez)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, date, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"paywall_{secrets.token_hex(3)}"
PWD = hash_password("PaywallTest!23")
PWDH = "PaywallTest!23"

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
    print(f"\n=== koç paywall smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    ids: dict[str, int] = {}
    student_ids: list[int] = []
    try:
        with SessionLocal() as db:
            def coach(suffix, plan, trial_ends):
                u = User(
                    email=f"{PFX}_{suffix}@test.invalid", password_hash=PWD,
                    full_name=f"{PFX} {suffix}", role=UserRole.TEACHER, institution_id=None,
                    is_active=True, plan=plan, trial_ends_at=trial_ends,
                    post_trial_plan="solo_free",
                    password_changed_at=now, must_change_password=False)
                db.add(u); db.flush()
                return u

            cpw = coach("pw", "solo_free", None)        # paywall: 5>3
            cok = coach("ok", "solo_free", None)         # limit altı: 2
            ctr = coach("tr", "solo_trial", now + timedelta(days=10))  # trial sınırsız: 5
            ids = {"pw": cpw.id, "ok": cok.id, "tr": ctr.id}

            def students(coach_obj, n):
                made = []
                for i in range(n):
                    s = User(
                        email=f"{PFX}_{coach_obj.id}_s{i}@test.invalid", password_hash=PWD,
                        full_name=f"{PFX} Öğr {coach_obj.id}-{i}", role=UserRole.STUDENT,
                        teacher_id=coach_obj.id, institution_id=None, grade_level=8,
                        is_active=True, password_changed_at=now, must_change_password=False)
                    db.add(s); made.append(s)
                return made

            db.flush()
            s_pw = students(cpw, 5)
            students(cok, 2)
            students(ctr, 5)
            db.commit()
            student_ids = [r.id for r in db.query(User).filter(
                User.role == UserRole.STUDENT,
                User.email.like(f"{PFX}_%")).all()]
            first_pw_student = db.query(User).filter(
                User.teacher_id == ids["pw"], User.role == UserRole.STUDENT).first().id
            ok_student = db.query(User).filter(
                User.teacher_id == ids["ok"], User.role == UserRole.STUDENT).first().id
            tr_student = db.query(User).filter(
                User.teacher_id == ids["tr"], User.role == UserRole.STUDENT).first().id

        today = date.today().isoformat()

        def login(suffix):
            c = TestClient(app)
            r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
            if r.status_code != 200:
                raise RuntimeError(f"login {suffix}: {r.status_code} {r.text}")
            return c

        cpw_cli = login("pw")
        cok_cli = login("ok")
        ctr_cli = login("tr")

        # 1. paywall publish-day → 403 paywall_active
        r = cpw_cli.post(f"/api/v2/teacher/students/{first_pw_student}/publish-day", json={"task_date": today})
        code = (r.json().get("detail", {}) or {}).get("code") if r.status_code == 403 else None
        check("1. paywall koç publish-day → 403 paywall_active",
              r.status_code == 403 and code == "paywall_active", f"status={r.status_code} body={r.text[:160]}")

        # 2. paywall bulk-tasks → 403 paywall_active
        r = cpw_cli.post(f"/api/v2/teacher/students/{first_pw_student}/bulk-tasks", json={"tasks": []})
        code = (r.json().get("detail", {}) or {}).get("code") if r.status_code == 403 else None
        check("2. paywall koç bulk-tasks → 403 paywall_active",
              r.status_code == 403 and code == "paywall_active", f"status={r.status_code} body={r.text[:160]}")

        # 3. limit-altı koç publish-day → 200 (gate geçti)
        r = cok_cli.post(f"/api/v2/teacher/students/{ok_student}/publish-day", json={"task_date": today})
        check("3. limit-altı koç publish-day → 200 (gate geçti)", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

        # 4. trial koç publish-day → 200 (paywall yok)
        r = ctr_cli.post(f"/api/v2/teacher/students/{tr_student}/publish-day", json={"task_date": today})
        check("4. trial koç publish-day → 200 (sınırsız)", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

        # 5. paywall koç öğrenci pasifleştir → 200 (engellenmez)
        r = cpw_cli.post(f"/api/v2/teacher/students/{first_pw_student}/deactivate")
        check("5. paywall koç öğrenci pasifleştir → 200 (öğrenci yönetimi serbest)",
              r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

    finally:
        with SessionLocal() as db:
            if student_ids:
                db.execute(sa_delete(User).where(User.id.in_(student_ids)))
            cids = list(ids.values())
            if cids:
                from app.models.task import Task
                sids2 = student_ids
                if sids2:
                    db.execute(sa_delete(Task).where(Task.student_id.in_(sids2)))
                db.execute(sa_delete(User).where(User.id.in_(cids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
