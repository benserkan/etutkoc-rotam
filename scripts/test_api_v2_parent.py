"""API v2 /parent/* smoke (Dalga 5 Paket 1).

Senaryolar (~17):
   1. /parent/dashboard happy → 2 çocuk listesi (P1 bağlı)
   2. /parent/dashboard farklı veli (P2) → 0 çocuk (bağlı değil)
   3. /parent/students/{s1} → overview (student/today/week/projection/...)
   4. /parent/students/{s2} → overview
   5. /parent/students/{s1} farklı veli (P2) → 404 student_not_found
   6. /parent/students/{99999} → 404
   7. /parent/students/{s1}/week → 7 gün, default bugün
   8. /parent/students/{s1}/week?start=2024-01-08 → start doğru
   9. /parent/notifications → liste (boş veya dolu)
  10. /parent/settings → preferences + whatsapp.enabled=False + children=2
  11. /parent/settings/preferences update → değişti
  12. /parent/settings/preferences invalid quiet_start → 400 invalid_quiet_hours
  13. /parent/settings/students/{s1}/mute true → muted=True
  14. /parent/settings/students/{99999}/mute → 404 child_not_found
  15. /parent/settings/whatsapp/start → OTP üret (stub mode → dev_test_code)
  16. /parent/settings/whatsapp/verify yanlış kod → 400 otp_mismatch
  17. /parent/settings/whatsapp/verify doğru kod → enabled=True
  18. /parent/settings/whatsapp/disable → enabled=False
  19. Teacher rolü /parent/dashboard → 403 role_required

Test verisi: secrets prefix; gerçek hesaplara dokunulmaz.
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
    NotificationLog,
    ParentNotificationPref,
    ParentPhoneVerification,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2par_{secrets.token_hex(3)}"
P1_EMAIL = f"{PFX}_p1@test.invalid"
P2_EMAIL = f"{PFX}_p2@test.invalid"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
S1_EMAIL = f"{PFX}_s1@test.invalid"
S2_EMAIL = f"{PFX}_s2@test.invalid"
S3_EMAIL = f"{PFX}_s3@test.invalid"
PASSWORD = "TestPassParent!23"

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
    """1 öğretmen + 3 öğrenci + 2 veli (P1→s1,s2; P2→s3)."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()

        s1 = User(
            email=S1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} S1", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        s2 = User(
            email=S2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} S2", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=11, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        s3 = User(
            email=S3_EMAIL, password_hash=pwd,
            full_name=f"{PFX} S3", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=10, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        p1 = User(
            email=P1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Veli-1", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        p2 = User(
            email=P2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Veli-2", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([s1, s2, s3, p1, p2])
        db.flush()

        # P1 → S1 (primary, anne), S2 (secondary, baba)
        l1 = ParentStudentLink(
            parent_id=p1.id, student_id=s1.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        l2 = ParentStudentLink(
            parent_id=p1.id, student_id=s2.id,
            relation=ParentRelation.BABA, is_primary=False,
        )
        # P2 → S3 (anne)
        l3 = ParentStudentLink(
            parent_id=p2.id, student_id=s3.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        db.add_all([l1, l2, l3])

        # P1 için pref (varsayılan açık tümü)
        pref1 = ParentNotificationPref(
            parent_id=p1.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref1)
        db.commit()

        return {
            "teacher_id": teacher.id,
            "s1_id": s1.id, "s2_id": s2.id, "s3_id": s3.id,
            "p1_id": p1.id, "p2_id": p2.id,
        }


def _cleanup(seed: dict) -> None:
    """Test verisini temizle."""
    with SessionLocal() as db:
        parent_ids = [seed["p1_id"], seed["p2_id"]]
        student_ids = [seed["s1_id"], seed["s2_id"], seed["s3_id"]]
        all_user_ids = parent_ids + student_ids + [seed["teacher_id"]]

        # Önce bağımlı tablolar
        db.execute(sa_delete(ParentSessionLog).where(
            ParentSessionLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentPhoneVerification).where(
            ParentPhoneVerification.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /parent smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded p1={seed['p1_id']} p2={seed['p2_id']} "
        f"s1={seed['s1_id']} s2={seed['s2_id']} s3={seed['s3_id']}\n"
    )

    try:
        p1 = _login_v2(P1_EMAIL)
        p2 = _login_v2(P2_EMAIL)
        teacher = _login_v2(TEACHER_EMAIL)

        # ===== 1. /dashboard P1 happy → 2 çocuk =====
        r = p1.get("/api/v2/parent/dashboard")
        ok = (
            r.status_code == 200
            and isinstance(r.json().get("children"), list)
            and len(r.json()["children"]) == 2
        )
        check(
            "1. /dashboard P1 → 2 çocuk",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )
        if ok:
            kids = sorted(r.json()["children"], key=lambda c: c["student_id"])
            ok2 = (
                kids[0]["student_id"] == seed["s1_id"]
                and kids[0]["relation"] == "anne"
                and kids[0]["is_primary"] is True
                and kids[1]["student_id"] == seed["s2_id"]
                and kids[1]["relation"] == "baba"
            )
            check("1b. /dashboard P1 → relation+primary doğru", ok2, str(kids))

        # ===== 2. /dashboard P2 → 1 çocuk =====
        r = p2.get("/api/v2/parent/dashboard")
        ok = r.status_code == 200 and len(r.json().get("children", [])) == 1
        check(
            "2. /dashboard P2 → 1 çocuk (S3)",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 3. /students/{s1} P1 → 200 overview =====
        r = p1.get(f"/api/v2/parent/students/{seed['s1_id']}")
        ok = (
            r.status_code == 200
            and r.json().get("student", {}).get("id") == seed["s1_id"]
            and "today" in r.json()
            and "week" in r.json()
            and "projection" in r.json()
            and "subjects" in r.json()
            and "trend" in r.json()
            and "teacher_notes" in r.json()
        )
        check(
            "3. /students/s1 → overview tam yapı",
            ok,
            f"status={r.status_code} keys={list(r.json().keys()) if r.status_code == 200 else r.text[:200]}",
        )

        # ===== 4. /students/{s2} P1 → 200 overview =====
        r = p1.get(f"/api/v2/parent/students/{seed['s2_id']}")
        check(
            "4. /students/s2 → 200",
            r.status_code == 200 and r.json()["student"]["id"] == seed["s2_id"],
            f"status={r.status_code}",
        )

        # ===== 5. /students/{s1} P2 (bağlı değil) → 404 =====
        r = p2.get(f"/api/v2/parent/students/{seed['s1_id']}")
        check(
            "5. /students/s1 P2 (bağlı değil) → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "student_not_found",
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 6. /students/99999 → 404 =====
        r = p1.get("/api/v2/parent/students/999999")
        check(
            "6. /students/999999 → 404",
            r.status_code == 404,
            f"status={r.status_code}",
        )

        # ===== 7. /week default → 7 gün =====
        r = p1.get(f"/api/v2/parent/students/{seed['s1_id']}/week")
        ok = (
            r.status_code == 200
            and isinstance(r.json().get("days"), list)
            and len(r.json()["days"]) == 7
            and "prev_start" in r.json()
            and "next_start" in r.json()
        )
        check(
            "7. /week default → 7 gün",
            ok,
            f"status={r.status_code}",
        )

        # ===== 8. /week?start=YYYY-MM-DD =====
        r = p1.get(
            f"/api/v2/parent/students/{seed['s1_id']}/week",
            params={"start": "2024-01-08"},
        )
        ok = (
            r.status_code == 200
            and r.json().get("start") == "2024-01-08"
            and r.json().get("end") == "2024-01-14"
        )
        check(
            "8. /week?start=2024-01-08 → doğru pencere",
            ok,
            f"status={r.status_code} start={r.json().get('start') if r.status_code == 200 else r.text[:120]}",
        )

        # ===== 9. /notifications =====
        r = p1.get("/api/v2/parent/notifications")
        ok = r.status_code == 200 and isinstance(r.json().get("items"), list)
        check(
            "9. /notifications → liste",
            ok,
            f"status={r.status_code}",
        )

        # ===== 10. /settings → preferences + whatsapp + children =====
        r = p1.get("/api/v2/parent/settings")
        ok = (
            r.status_code == 200
            and "preferences" in r.json()
            and "whatsapp" in r.json()
            and isinstance(r.json().get("children"), list)
            and len(r.json()["children"]) == 2
            and r.json()["whatsapp"]["enabled"] is False
        )
        check(
            "10. /settings → 3 blok dolu",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 11. /settings/preferences update happy =====
        r = p1.post(
            "/api/v2/parent/settings/preferences",
            json={
                "daily_summary": False,
                "weekly_report": True,
                "empty_day": False,
                "new_program": True,
                "drop_alert": True,
                "teacher_note": True,
                "exam_approaching": False,
                "quiet_start": "23:00",
                "quiet_end": "06:30",
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("daily_summary_enabled") is False
            and r.json().get("data", {}).get("quiet_hours_start") == "23:00"
            and r.json().get("data", {}).get("quiet_hours_end") == "06:30"
            and "parent:me" in r.json().get("invalidate", [])
        )
        check(
            "11. /settings/preferences update → değişti + invalidate",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 12. /settings/preferences invalid quiet_start =====
        r = p1.post(
            "/api/v2/parent/settings/preferences",
            json={
                "daily_summary": True, "weekly_report": True,
                "empty_day": True, "new_program": True,
                "drop_alert": True, "teacher_note": True,
                "exam_approaching": True,
                "quiet_start": "25:99", "quiet_end": "07:00",
            },
        )
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_quiet_hours"
        )
        check(
            "12. /settings/preferences invalid quiet_start → 400",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 13. /settings/students/{s1}/mute true =====
        r = p1.post(
            f"/api/v2/parent/settings/students/{seed['s1_id']}/mute",
            json={"muted": True},
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("muted") is True
        )
        check(
            "13. /settings/students/s1/mute true → muted=True",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 14. /settings/students/99999/mute → 404 =====
        r = p1.post(
            "/api/v2/parent/settings/students/999999/mute",
            json={"muted": True},
        )
        check(
            "14. /settings/students/999999/mute → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "child_not_found",
            f"status={r.status_code}",
        )

        # ===== 15. /settings/whatsapp/start → 200 + dev_test_code =====
        r = p1.post(
            "/api/v2/parent/settings/whatsapp/start",
            json={"phone": "+90 532 555 4433"},
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("pending_verify") is True
        )
        check(
            "15. /settings/whatsapp/start → OTP gönderildi",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )
        test_code = r.json().get("data", {}).get("dev_test_code") if ok else None

        # ===== 16. /settings/whatsapp/verify yanlış kod → 400 otp_mismatch =====
        r = p1.post(
            "/api/v2/parent/settings/whatsapp/verify",
            json={"code": "000000" if test_code != "000000" else "000001"},
        )
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "otp_mismatch"
        )
        check(
            "16. /settings/whatsapp/verify yanlış kod → 400 otp_mismatch",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 17. /settings/whatsapp/verify doğru kod → enabled=True =====
        if test_code:
            r = p1.post(
                "/api/v2/parent/settings/whatsapp/verify",
                json={"code": test_code},
            )
            ok = (
                r.status_code == 200
                and r.json().get("data", {}).get("enabled") is True
                and r.json().get("data", {}).get("phone") == "905325554433"
            )
            check(
                "17. /settings/whatsapp/verify doğru kod → enabled=True",
                ok,
                f"status={r.status_code} body={r.text[:200]}",
            )
        else:
            check(
                "17. /settings/whatsapp/verify doğru kod → enabled=True",
                False,
                "test_code yok (15. başarısız?)",
            )

        # ===== 18. /settings/whatsapp/disable → enabled=False =====
        r = p1.post("/api/v2/parent/settings/whatsapp/disable")
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("enabled") is False
        )
        check(
            "18. /settings/whatsapp/disable → enabled=False",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 19. Teacher rolü /dashboard → 403 role_required =====
        r = teacher.get("/api/v2/parent/dashboard")
        check(
            "19. Teacher /parent/dashboard → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
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
