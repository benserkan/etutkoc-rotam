"""API v2 /teacher tahsilat smoke (KS2).

Senaryolar:
   1. Anonim → 401
   2. POST rate (upsert) → 200
   3. POST rate negatif → 422 invalid_fee
   4. billing: 2 done + 1 postponed seans → done_sessions=2, accrued=2×fee, status pending
   5. POST payment (kısmi) → balance düşer, status partial
   6. POST payment (kalan) → balance 0, status paid
   7. POST payment amount 0 → 422
   8. POST payment geçersiz tarih → 422
   9. GET payments listesi → 2 kayıt + total
  10. DELETE payment → 200
  11. başka öğretmenin öğrencisi rate → 404
  12. başka öğretmen payment DELETE → 404
  13. invalid month → 422
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CoachPayment, CoachStudentRate, CoachingSession, CoachingSessionStatus,
    User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2tbil{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "BilPass1!@xyz"
MONTH = "2026-05"

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


def _seed():
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Öğr",
                 role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t.id)
        s2 = User(email=f"{PFX}_s2@test.invalid", password_hash=pwd, full_name="Öğr2",
                  role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t2.id)
        db.add_all([s, s2]); db.flush()
        # 2 DONE + 1 POSTPONED seans (2026-05)
        for d, st in [(date(2026, 5, 5), CoachingSessionStatus.DONE),
                      (date(2026, 5, 12), CoachingSessionStatus.DONE),
                      (date(2026, 5, 19), CoachingSessionStatus.POSTPONED)]:
            db.add(CoachingSession(coach_id=t.id, student_id=s.id, session_date=d,
                                   status=st, agenda="x"))
        db.flush()
        out = {"t_id": t.id, "t2_id": t2.id, "s_id": s.id, "s2_id": s2.id}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sids = [seed["s_id"], seed["s2_id"]]
        db.execute(sa_delete(CoachPayment).where(CoachPayment.student_id.in_(sids)))
        db.execute(sa_delete(CoachStudentRate).where(CoachStudentRate.student_id.in_(sids)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(sids)))
        db.execute(sa_delete(User).where(User.id.in_(
            [seed["t_id"], seed["t2_id"], *sids])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def _row(j, sid):
    return next((x for x in j["rows"] if x["student_id"] == sid), None)


def main():
    print(f"\n=== API v2 /teacher billing smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    sid = seed["s_id"]
    try:
        tc = _login(T_EMAIL)
        t2c = _login(T2_EMAIL)

        r = TestClient(app).get(f"/api/v2/teacher/billing?month={MONTH}")
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 2. rate
        r = tc.post(f"/api/v2/teacher/students/{sid}/rate", json={"session_fee": 2500})
        check("2. rate set → 200", r.status_code == 200 and r.json()["data"]["session_fee"] == 2500, f"status={r.status_code}")

        # 3. negatif
        r = tc.post(f"/api/v2/teacher/students/{sid}/rate", json={"session_fee": -5})
        check("3. negatif ücret → 422", r.status_code == 422 and r.json()["detail"]["code"] == "invalid_fee", f"status={r.status_code}")

        # 4. billing: done=2, accrued=5000
        r = tc.get(f"/api/v2/teacher/billing?month={MONTH}")
        j = r.json()
        row = _row(j, sid)
        check("4. done=2 accrued=5000 status pending",
              r.status_code == 200 and row and row["done_sessions"] == 2
              and row["accrued"] == 5000 and row["paid"] == 0 and row["balance"] == 5000
              and row["status"] == "pending", f"{row}")

        # 5. kısmi ödeme 3000
        r = tc.post(f"/api/v2/teacher/students/{sid}/payments",
                    json={"amount": 3000, "paid_at": "2026-05-20", "method": "cash", "period_month": MONTH})
        check("5. kısmi ödeme → 200", r.status_code == 200 and r.json()["data"]["amount"] == 3000, f"status={r.status_code}")
        r = tc.get(f"/api/v2/teacher/billing?month={MONTH}")
        row = _row(r.json(), sid)
        check("5b. balance=2000 status partial",
              row and row["paid"] == 3000 and row["balance"] == 2000 and row["status"] == "partial", f"{row}")

        # 6. kalan ödeme 2000
        r = tc.post(f"/api/v2/teacher/students/{sid}/payments",
                    json={"amount": 2000, "paid_at": "2026-05-25", "period_month": MONTH})
        r = tc.get(f"/api/v2/teacher/billing?month={MONTH}")
        row = _row(r.json(), sid)
        check("6. balance=0 status paid", row and row["balance"] == 0 and row["status"] == "paid", f"{row}")
        check("6b. totals", r.json()["totals"]["accrued"] == 5000 and r.json()["totals"]["paid"] == 5000, f"{r.json()['totals']}")

        # 7. amount 0
        r = tc.post(f"/api/v2/teacher/students/{sid}/payments", json={"amount": 0, "paid_at": "2026-05-20"})
        check("7. amount 0 → 422", r.status_code == 422 and r.json()["detail"]["code"] == "invalid_amount", f"status={r.status_code}")

        # 8. geçersiz tarih
        r = tc.post(f"/api/v2/teacher/students/{sid}/payments", json={"amount": 100, "paid_at": "bozuk"})
        check("8. geçersiz tarih → 422", r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date", f"status={r.status_code}")

        # 9. payments listesi
        r = tc.get(f"/api/v2/teacher/students/{sid}/payments")
        j = r.json()
        check("9. payments listesi 2 + total 5000", len(j["rows"]) == 2 and j["total_paid"] == 5000, f"{j.get('total_paid')}")
        pay_id = j["rows"][0]["id"]

        # 10. delete
        r = tc.delete(f"/api/v2/teacher/payments/{pay_id}")
        check("10. DELETE payment → 200", r.status_code == 200 and r.json()["data"]["deleted"], f"status={r.status_code}")

        # 11. başka öğr. öğrencisi rate → 404
        r = tc.post(f"/api/v2/teacher/students/{seed['s2_id']}/rate", json={"session_fee": 1000})
        check("11. başka öğr. rate → 404", r.status_code == 404, f"status={r.status_code}")

        # 12. başka öğretmen payment delete → 404 (kalan ödeme)
        r = tc.get(f"/api/v2/teacher/students/{sid}/payments")
        remaining = r.json()["rows"][0]["id"]
        r = t2c.delete(f"/api/v2/teacher/payments/{remaining}")
        check("12. başka öğr. payment DELETE → 404", r.status_code == 404, f"status={r.status_code}")

        # 13. invalid month
        r = tc.get("/api/v2/teacher/billing?month=2026-13")
        check("13. invalid month → 422", r.status_code == 422 and r.json()["detail"]["code"] == "invalid_month", f"status={r.status_code}")

        # 14. pasif öğrenci, bu ay aktivitesi (2 DONE seans) varsa listede KALIR
        with SessionLocal() as db:
            su = db.get(User, sid)
            su.is_active = False
            db.commit()
        r = tc.get(f"/api/v2/teacher/billing?month={MONTH}")
        row = _row(r.json(), sid)
        check("14. pasif + aktiviteli öğrenci listede + is_active=false",
              row is not None and row["is_active"] is False and row["done_sessions"] == 2,
              f"{row}")
        # 14b. aktivitesiz BAŞKA bir ayda pasif öğrenci görünmez
        r = tc.get(f"/api/v2/teacher/billing?month=2026-03")
        check("14b. pasif + aktivitesiz ay → gizli", _row(r.json(), sid) is None,
              f"{[x['student_id'] for x in r.json()['rows']]}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
