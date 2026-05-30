"""P1 — Telefon altyapısı + /me/phone/* + SMS provider (dev mode) smoke.

Senaryolar:
   1. normalize_e164_tr: 0532..., +90 532..., 905..., 5... → "905XXXXXXXXX"
   2. normalize_e164_tr geçersiz formatlar → None
   3. POST /me/phone/start (geçersiz format) → 400 invalid_phone
   4. POST /me/phone/start (geçerli) → 200, dev modda info.phone_dev_test_code dolu
   5. POST /me/phone/start tekrar (cooldown) → 400 cooldown_active
   6. POST /me/phone/verify (yanlış kod) → 400 otp_mismatch
   7. POST /me/phone/verify (doğru kod) → 200, User.phone + phone_verified_at set
   8. /me yanıtında phone alanı + phone_verified_at dolu
   9. POST /me/phone/delete → 200, User.phone NULL
  10. PARENT olmayan kullanıcı /me/phone-secondary/start → 403 secondary_slot_parent_only
  11. PARENT için /me/phone-secondary/start + verify → User.phone_secondary set
  12. Auth gerektiren endpoint'lere unauth çağrı → 401
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    PhoneVerification,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.phone_service import normalize_e164_tr
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2phn_{_secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PASSWORD = "TestPhone!23456"

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


def _login(c: TestClient, email: str) -> bool:
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code == 200


def _seed() -> dict:
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
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Student", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([parent, student])
        db.commit()
        return {
            "teacher_id": teacher.id,
            "parent_id": parent.id,
            "student_id": student.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_ids = [seed["teacher_id"], seed["parent_id"], seed["student_id"]]
        db.execute(sa_delete(PhoneVerification).where(
            PhoneVerification.user_id.in_(all_ids)
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P1 phone + /me/phone/* smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        # ===== 1. normalize_e164_tr — kabul ettikleri =====
        cases = [
            ("0532 123 45 67", "905321234567"),
            ("+90 532 123 45 67", "905321234567"),
            ("+905321234567", "905321234567"),
            ("905321234567", "905321234567"),
            ("5321234567", "905321234567"),
        ]
        all_ok = all(normalize_e164_tr(raw) == expected for raw, expected in cases)
        check(
            "1. normalize_e164_tr farklı kabul edilebilir formatları E.164'e çevirir",
            all_ok,
        )

        # ===== 2. normalize_e164_tr — reddedilenler =====
        bad_cases = [
            "",                  # boş
            "123",               # çok kısa
            "0212 123 45 67",    # sabit (0212 — cep değil)
            "abcdefghijk",       # rakam yok
            "+905321234",        # eksik (10 hane)
            "+90 5321234567 89", # 14 hane (fazla)
            "1234567890",        # 10 hane ama 5 ile başlamıyor
        ]
        all_bad = all(normalize_e164_tr(raw) is None for raw in bad_cases)
        check(
            "2. normalize_e164_tr geçersiz formatları None döndürür",
            all_bad,
            f"sonuçlar: {[normalize_e164_tr(r) for r in bad_cases]}",
        )

        # Login bir test öğretmen ile
        c = TestClient(app)
        assert _login(c, TEACHER_EMAIL), "teacher login failed"

        # ===== 3. /me/phone/start invalid phone =====
        r = c.post("/api/v2/me/phone/start", json={"phone": "abc123"})
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_phone"
        )
        check(
            "3. POST /me/phone/start invalid → 400 invalid_phone",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 4. /me/phone/start geçerli =====
        r = c.post("/api/v2/me/phone/start", json={"phone": "+90 532 123 45 67"})
        body = r.json()
        info = body.get("data", {}).get("info", {})
        dev_code = info.get("phone_dev_test_code")
        ok = (
            r.status_code == 200
            and info.get("phone_pending_verify") is True
            and info.get("phone_pending_phone") == "905321234567"
            and dev_code is not None
            and len(dev_code) == 6
        )
        check(
            "4. POST /me/phone/start geçerli → 200 + dev_test_code dolu",
            ok,
            f"status={r.status_code} info={info}",
        )

        # ===== 5. Cooldown — hemen yeni kod istemek 400 =====
        r2 = c.post("/api/v2/me/phone/start", json={"phone": "+90 532 123 45 67"})
        ok = (
            r2.status_code == 400
            and r2.json().get("detail", {}).get("code") == "cooldown_active"
        )
        check(
            "5. POST /me/phone/start tekrar → 400 cooldown_active",
            ok,
            f"status={r2.status_code}",
        )

        # ===== 6. Yanlış kod =====
        # dev_code ile karışmasın diye, dev_code'a 1 ekleyip yanlış kod üret
        wrong_code = f"{(int(dev_code) + 1) % 1_000_000:06d}" if dev_code else "000000"
        r3 = c.post("/api/v2/me/phone/verify", json={"code": wrong_code})
        ok = (
            r3.status_code == 400
            and r3.json().get("detail", {}).get("code") == "otp_mismatch"
        )
        check(
            "6. POST /me/phone/verify yanlış kod → 400 otp_mismatch",
            ok,
            f"status={r3.status_code}",
        )

        # ===== 7. Doğru kod =====
        r4 = c.post("/api/v2/me/phone/verify", json={"code": dev_code})
        body4 = r4.json()
        info4 = body4.get("data", {}).get("info", {})
        ok = (
            r4.status_code == 200
            and info4.get("phone") == "905321234567"
            and info4.get("phone_verified_at") is not None
        )
        check(
            "7. POST /me/phone/verify doğru kod → 200 + phone+verified_at",
            ok,
            f"status={r4.status_code} info={info4}",
        )

        # ===== 8. /me yanıtında telefon =====
        r5 = c.get("/api/v2/me")
        ph = r5.json().get("phone", {}) if r5.status_code == 200 else {}
        ok = (
            r5.status_code == 200
            and ph.get("phone") == "905321234567"
            and ph.get("phone_verified_at") is not None
            and ph.get("secondary_slot_available") is False  # teacher değil parent
        )
        check(
            "8. GET /me yanıtında phone + secondary_slot_available=False (teacher)",
            ok,
            f"status={r5.status_code} ph={ph}",
        )

        # ===== 9. /me/phone/delete =====
        r6 = c.post("/api/v2/me/phone/delete")
        info6 = r6.json().get("data", {}).get("info", {})
        ok = (
            r6.status_code == 200
            and info6.get("phone") is None
            and info6.get("phone_verified_at") is None
        )
        check(
            "9. POST /me/phone/delete → User.phone NULL",
            ok,
            f"status={r6.status_code} info={info6}",
        )

        # ===== 10. /me/phone-secondary/start — teacher → 403 =====
        r7 = c.post(
            "/api/v2/me/phone-secondary/start",
            json={"phone": "+905321234567"},
        )
        ok = (
            r7.status_code == 403
            and r7.json().get("detail", {}).get("code") == "secondary_slot_parent_only"
        )
        check(
            "10. /me/phone-secondary/start teacher → 403 secondary_slot_parent_only",
            ok,
            f"status={r7.status_code}",
        )

        # ===== 11. PARENT için secondary akışı =====
        c2 = TestClient(app)
        assert _login(c2, PARENT_EMAIL), "parent login failed"
        r8 = c2.post(
            "/api/v2/me/phone-secondary/start",
            json={"phone": "0533 456 78 90"},
        )
        info8 = r8.json().get("data", {}).get("info", {})
        sec_code = info8.get("phone_secondary_dev_test_code")
        ok_start = r8.status_code == 200 and sec_code is not None
        if not ok_start:
            check(
                "11. PARENT /me/phone-secondary/start + verify → set",
                False,
                f"start status={r8.status_code} info={info8}",
            )
        else:
            r9 = c2.post(
                "/api/v2/me/phone-secondary/verify",
                json={"code": sec_code},
            )
            info9 = r9.json().get("data", {}).get("info", {})
            ok = (
                r9.status_code == 200
                and info9.get("phone_secondary") == "905334567890"
                and info9.get("phone_secondary_verified_at") is not None
                and info9.get("secondary_slot_available") is True
            )
            check(
                "11. PARENT /me/phone-secondary/start + verify → set",
                ok,
                f"verify status={r9.status_code} info={info9}",
            )

        # ===== 12. Auth gerekli — unauth 401 =====
        c3 = TestClient(app)
        r10 = c3.post("/api/v2/me/phone/start", json={"phone": "+90 532 000 0000"})
        ok = r10.status_code == 401
        check(
            "12. /me/phone/start unauth → 401",
            ok,
            f"status={r10.status_code}",
        )

        # ===== 13. Signup teacher invalid_phone → 400 =====
        # Yeni signup endpoint'i geçersiz format ile reddedilmeli
        c4 = TestClient(app)
        signup_email_bad = f"{PFX}_signup_bad@test.invalid"
        r11 = c4.post(
            "/api/v2/auth/signup/teacher",
            json={
                "full_name": "Signup Bad Phone Test",
                "email": signup_email_bad,
                "password": "VeryStrongPass!2345",
                "password_confirm": "VeryStrongPass!2345",
                "accept_terms": True,
                "phone": "abc123",  # GEÇERSIZ
            },
        )
        ok = (
            r11.status_code == 400
            and r11.json().get("detail", {}).get("code") == "invalid_phone"
        )
        check(
            "13. signup/teacher invalid phone → 400 invalid_phone",
            ok,
            f"status={r11.status_code} body={r11.text[:200]}",
        )
        # Cleanup — signup başarısız olsa bile veri kalmamalı, ama defensive
        with SessionLocal() as db:
            db.execute(sa_delete(User).where(User.email == signup_email_bad))
            db.commit()

        # ===== 14. Signup teacher valid phone → User.phone yazıldı, verified_at NULL =====
        c5 = TestClient(app)
        signup_email_ok = f"{PFX}_signup_ok@test.invalid"
        r12 = c5.post(
            "/api/v2/auth/signup/teacher",
            json={
                "full_name": "Signup OK Phone Test",
                "email": signup_email_ok,
                "password": "VeryStrongPass!2345",
                "password_confirm": "VeryStrongPass!2345",
                "accept_terms": True,
                "phone": "0532 999 88 77",
            },
        )
        new_user_id: int | None = None
        if r12.status_code == 200:
            with SessionLocal() as db:
                u = db.query(User).filter(User.email == signup_email_ok).first()
                if u:
                    new_user_id = u.id
                    ok = (
                        u.phone == "905329998877"
                        and u.phone_verified_at is None
                    )
                else:
                    ok = False
        else:
            ok = False
        check(
            "14. signup/teacher valid phone → User.phone normalize edildi, verified_at NULL",
            ok,
            f"status={r12.status_code}",
        )
        # Cleanup
        if new_user_id is not None:
            with SessionLocal() as db:
                db.execute(sa_delete(PhoneVerification).where(
                    PhoneVerification.user_id == new_user_id
                ))
                db.execute(sa_delete(User).where(User.id == new_user_id))
                db.commit()

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
