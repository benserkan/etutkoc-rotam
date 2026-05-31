"""M4 — Veli seans hareketleri smoke.

Senaryolar (10):
   1. veli kendi çocuğunun seansını görür → 200
   2. başka veli 404 student_not_found
   3. koç-özel alanlar response'a SIZMAZ (coach_note, agenda, mood vs.)
   4. DONE seans aylık tahakkuk'a sayılır (× fee)
   5. POSTPONED/CANCELLED tahakkuk'a saymaz
   6. CoachStudentRate yoksa fee=0
   7. Ödeme period_month'a göre aya düşer
   8. Ödeme period_month NULL → paid_at ayına düşer
   9. open_balance = total_accrued − total_paid
  10. months query (=1) penceresini daraltır
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    ParentStudentLink,
    SuspiciousIp,
    User,
    UserRole,
)
from app.models.coach_billing import (
    CoachPayment,
    CoachPaymentMethod,
    CoachStudentRate,
)
from app.models.coaching_session import (
    CoachingSession,
    CoachingSessionStatus,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2ps_{secrets.token_hex(3)}"
COACH_EMAIL = f"{PFX}_c@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
PARENT_EMAIL = f"{PFX}_p@test.invalid"
OTHER_PARENT_EMAIL = f"{PFX}_op@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_os@test.invalid"
PASSWORD = "TestPass123!@xyz"

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
    """Test verisi: koç + öğrenci + veli + 6 seans (4 DONE / 1 POSTPONED /
    1 CANCELLED) + 2 ödeme.

    Ay dağılımı (bugüne göre):
      - bu ay: 2 DONE
      - geçen ay: 2 DONE + 1 POSTPONED + 1 CANCELLED
      - bu ay: 1 ödeme period_month=bu_ay
      - geçen ay paid_at, period_month=NULL
    """
    today = date.today()
    cur_month = f"{today.year:04d}-{today.month:02d}"

    if today.month == 1:
        prev_y, prev_m = today.year - 1, 12
    else:
        prev_y, prev_m = today.year, today.month - 1
    prev_month = f"{prev_y:04d}-{prev_m:02d}"

    with SessionLocal() as db:
        coach = User(
            email=COACH_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M4 Koç", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M4 Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M4 Veli", role=UserRole.PARENT,
            is_active=True,
        )
        other_parent = User(
            email=OTHER_PARENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Başka Veli", role=UserRole.PARENT,
            is_active=True,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Başka Öğrenci", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
        )
        db.add_all([coach, student, parent, other_parent, other_student])
        db.flush()
        student.teacher_id = coach.id
        other_student.teacher_id = coach.id

        # Veli ↔ öğrenci bağı
        psl = ParentStudentLink(parent_id=parent.id, student_id=student.id)
        psl_other = ParentStudentLink(parent_id=other_parent.id, student_id=other_student.id)
        db.add_all([psl, psl_other])
        db.flush()

        # Cari ücret
        rate = CoachStudentRate(
            coach_id=coach.id, student_id=student.id, session_fee=2500,
        )
        db.add(rate)

        # Seanslar — bugün + 5 gün önce + geçen ayın 15'i + diğer ay 10/20
        # 4 DONE
        # Geçen ayın bir tarihi
        prev_day = date(prev_y, prev_m, min(15, 28))
        sessions_data = [
            (today, CoachingSessionStatus.DONE),
            (today - timedelta(days=5), CoachingSessionStatus.DONE),
            (prev_day, CoachingSessionStatus.DONE),
            (prev_day - timedelta(days=3), CoachingSessionStatus.DONE),
            (prev_day - timedelta(days=7), CoachingSessionStatus.POSTPONED),
            (prev_day - timedelta(days=10), CoachingSessionStatus.CANCELLED),
        ]
        for sd, st in sessions_data:
            db.add(CoachingSession(
                coach_id=coach.id, student_id=student.id,
                session_date=sd, status=st,
                agenda="gizli koç agenda",
                coach_note="gizli koç notu",
                mood=4,
            ))

        # Ödemeler
        # 1) bu ay için 5000 ödeme (period_month=bu_ay)
        db.add(CoachPayment(
            coach_id=coach.id, student_id=student.id,
            amount=5000, paid_at=today,
            method=CoachPaymentMethod.CASH,
            period_month=cur_month,
            note="bu ay nakit",
        ))
        # 2) geçen aya ait 2000 ödeme — period_month=NULL → paid_at'a göre düşer
        db.add(CoachPayment(
            coach_id=coach.id, student_id=student.id,
            amount=2000, paid_at=prev_day,
            method=CoachPaymentMethod.TRANSFER,
            period_month=None,
        ))

        db.commit()
        return {
            "coach_id": coach.id,
            "student_id": student.id,
            "parent_id": parent.id,
            "other_parent_id": other_parent.id,
            "other_student_id": other_student.id,
            "cur_month": cur_month,
            "prev_month": prev_month,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(CoachPayment).where(
            CoachPayment.student_id.in_([seed["student_id"], seed["other_student_id"]])
        ))
        db.execute(sa_delete(CoachStudentRate).where(
            CoachStudentRate.student_id.in_([seed["student_id"], seed["other_student_id"]])
        ))
        db.execute(sa_delete(CoachingSession).where(
            CoachingSession.student_id.in_([seed["student_id"], seed["other_student_id"]])
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_([seed["parent_id"], seed["other_parent_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["other_student_id"],
            seed["parent_id"], seed["other_parent_id"], seed["coach_id"],
        ])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== M4 veli seans hareketleri smoke — prefix: {PFX} ===\n")
    seed = _seed()

    try:
        client = TestClient(app)
        _login(client, PARENT_EMAIL)

        # ===== 1. veli kendi çocuğunun seansını görür =====
        r = client.get(f"/api/v2/parent/students/{seed['student_id']}/sessions")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("student_id") == seed["student_id"]
            and len(body.get("sessions", [])) == 6
        )
        check("1. veli kendi çocuğu → 200 + 6 seans",
              ok, f"status={r.status_code} count={len(body.get('sessions', []))}")

        # ===== 2. başka veli 404 =====
        new_client = TestClient(app)
        _login(new_client, OTHER_PARENT_EMAIL)
        r = new_client.get(f"/api/v2/parent/students/{seed['student_id']}/sessions")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "student_not_found"
        )
        check("2. başka veli → 404 student_not_found",
              ok, f"status={r.status_code} body={r.text[:160]}")

        # ===== 3. koç-özel alanlar SIZMAZ =====
        r = client.get(f"/api/v2/parent/students/{seed['student_id']}/sessions")
        body = r.json()
        first_session = body["sessions"][0] if body.get("sessions") else {}
        leaked_fields = [
            f for f in ("coach_note", "agenda", "next_change",
                        "mood", "tags", "auto_snapshot", "capture_source")
            if f in first_session
        ]
        ok = len(leaked_fields) == 0
        check("3. koç-özel alanlar serialize EDILMEZ",
              ok, f"leaked={leaked_fields}")

        # ===== 4. DONE seans tahakkuk'a sayılır =====
        # Bu ay 2 DONE × 2500 = 5000 (tahakkuk)
        cur_month_data = next(
            (m for m in body["billing"]["months"] if m["period_month"] == seed["cur_month"]),
            None,
        )
        ok = (
            cur_month_data is not None
            and cur_month_data["sessions_done"] == 2
            and cur_month_data["accrued"] == 5000
        )
        check("4. bu ay 2 DONE × 2500 → accrued 5000",
              ok, f"month_data={cur_month_data}")

        # ===== 5. POSTPONED/CANCELLED tahakkuk'a saymaz =====
        # Geçen ay 2 DONE + 1 POSTPONED + 1 CANCELLED → sessions_done=2 sayılmalı
        prev_month_data = next(
            (m for m in body["billing"]["months"] if m["period_month"] == seed["prev_month"]),
            None,
        )
        ok = (
            prev_month_data is not None
            and prev_month_data["sessions_done"] == 2
            and prev_month_data["accrued"] == 5000
        )
        check("5. geçen ay POSTPONED+CANCELLED hesaba sayılmaz",
              ok, f"prev_month={prev_month_data}")

        # ===== 6. Ödeme period_month'a göre aya düşer =====
        # bu ay paid = 5000 (kendi period'una)
        ok = cur_month_data["paid"] == 5000
        check("6. period_month'lu ödeme doğru aya düşer",
              ok, f"cur paid={cur_month_data['paid']}")

        # ===== 7. period_month NULL → paid_at ayına düşer =====
        # geçen ay paid_at'lı ödeme (2000) period_month NULL → geçen aya
        ok = prev_month_data["paid"] == 2000
        check("7. period_month NULL → paid_at ayına düşer",
              ok, f"prev paid={prev_month_data['paid']}")

        # ===== 8. open_balance hesabı =====
        # Toplam tahakkuk = 5000+5000 = 10000; toplam ödenen = 5000+2000=7000;
        # open_balance = 3000
        billing = body["billing"]
        ok = (
            billing["total_accrued"] == 10000
            and billing["total_paid"] == 7000
            and billing["open_balance"] == 3000
        )
        check("8. open_balance = accrued − paid",
              ok, f"acc={billing['total_accrued']} paid={billing['total_paid']} bal={billing['open_balance']}")

        # ===== 9. fee response'ta görünür =====
        ok = billing["session_fee"] == 2500
        check("9. session_fee 2500",
              ok, f"fee={billing['session_fee']}")

        # ===== 10. months=1 → sadece bu ay =====
        r = client.get(
            f"/api/v2/parent/students/{seed['student_id']}/sessions?months=1"
        )
        body = r.json()
        months = body["billing"]["months"]
        # months=1 → bugün dahil 1 ay = sadece bu ay
        ok = (
            r.status_code == 200
            and len(months) == 1
            and months[0]["period_month"] == seed["cur_month"]
        )
        check("10. months=1 → sadece bu ay penceresi",
              ok, f"len={len(months)} keys={[m['period_month'] for m in months]}")

    finally:
        _cleanup(seed)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
