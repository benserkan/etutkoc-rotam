"""#5 — Signup-anı telefon doğrulama kapısı (DORMANT) smoke.

Kapı yalnız SMS açıkken (is_sms_enabled) devreye girer. Bu test `is_sms_enabled`
+ `send_sms`'i monkeypatch ederek hem KAPALI (dormant, eski davranış korunur)
hem AÇIK (kapı zorunlu) durumları doğrular.

Senaryolar:
   1. signup_phone_required() == is_sms_enabled()  (kapalı → False)
   2. DORMANT: SMS kapalıyken signup/teacher (phone_token YOK) → 200, eski davranış
      (telefon opsiyonel, phone_verified_at NULL) — deploy edilse de signup'ı bozmaz
   3. [kapı AÇILIR] signup_phone_required() → True
   4. AÇIK: signup/teacher (phone_token YOK) → 422 phone_verification_required
   5. signup/phone/start (geçersiz telefon) → 400 invalid_phone
   6. signup/phone/start (geçerli) → 200, DB'de 6 haneli kod satırı
   7. signup/phone/verify (yanlış kod) → 400 otp_mismatch
   8. signup/phone/verify (doğru kod) → 200, phone_token dolu
   9. decode_phone_token: geçerli → telefon, çöp → None
  10. AÇIK: signup/teacher (geçerli phone_token) → 200, User.phone + verified_at SET
  11. phone_in_use: aynı (artık kullanımda) telefonla start → 409 phone_in_use
  12. AÇIK: kullanımdaki telefonun token'ıyla yeniden signup → 409 phone_in_use
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

import app.services.signup_guard as sguard
import app.services.signup_phone_service as sps
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, SignupPhoneVerification, SuspiciousIp, User
from app.models.audit_log import AuditAction
from app.services.rate_limit import get_login_limiter

PFX = f"sphg_{_secrets.token_hex(3)}"
EMAIL_DORMANT = f"{PFX}_dormant@test.invalid"
EMAIL_GATED = f"{PFX}_gated@test.invalid"
EMAIL_FAIL = f"{PFX}_fail@test.invalid"
PASSWORD = "Rotam!PhoneGate2026x"
PHONE_RAW = "+90 555 111 22 33"
PHONE_E164 = "905551112233"

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


def _user(email: str) -> User | None:
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).first()


def _otp_for(phone_e164: str) -> str | None:
    with SessionLocal() as db:
        row = (
            db.query(SignupPhoneVerification)
            .filter(SignupPhoneVerification.phone == phone_e164,
                    SignupPhoneVerification.consumed_at.is_(None))
            .order_by(SignupPhoneVerification.id.desc())
            .first()
        )
        return row.code if row else None


def _signup(c: TestClient, email: str, phone_token: str = "") -> "tuple[int, dict]":
    r = c.post("/api/v2/auth/signup/teacher", json={
        "full_name": f"{PFX} Koc",
        "email": email,
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        "accept_terms": True,
        "phone_token": phone_token,
    })
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {}


def _cleanup() -> None:
    with SessionLocal() as db:
        emails = [EMAIL_DORMANT, EMAIL_GATED, EMAIL_FAIL]
        users = db.query(User).filter(User.email.in_(emails)).all()
        uids = [u.id for u in users]
        db.execute(sa_delete(SignupPhoneVerification).where(
            SignupPhoneVerification.phone == PHONE_E164))
        if uids:
            db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        # signup-velocity kapısı USER_CREATE self_signup audit'lerini IP'ye göre
        # sayar → bıraktığımız testclient kayıtlarını temizle (başka signup
        # testlerini 429'a düşürmesin)
        db.execute(sa_delete(AuditLog).where(
            AuditLog.ip_address == "testclient",
            AuditLog.action == AuditAction.USER_CREATE,
        ))
        db.commit()


def main() -> int:
    print(f"\n=== #5 signup telefon kapısı smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    _cleanup()

    # IP hız kapısını izole et (ayrı test) — yalnız telefon kapısını ölçüyoruz
    orig_ip_block = sguard.signup_ip_blocked
    orig_sms = sps.is_sms_enabled
    orig_send = sps.send_sms
    sguard.signup_ip_blocked = lambda db, ip: False  # type: ignore

    c = TestClient(app)
    try:
        # ===== 1. kapalıyken required False =====
        sps.is_sms_enabled = lambda: False  # type: ignore
        check("1. signup_phone_required() SMS kapalıyken False",
              sps.signup_phone_required() is False)

        # ===== 2. DORMANT — kapı kapalıyken signup eskisi gibi çalışır =====
        st, body = _signup(c, EMAIL_DORMANT)
        u = _user(EMAIL_DORMANT)
        check("2. DORMANT: phone_token'sız signup → 200 + hesap açılır (eski davranış)",
              st == 200 and u is not None and u.phone_verified_at is None,
              f"status={st} user={'var' if u else 'yok'}")

        # ===== KAPI AÇILIR (SMS satın alındı simülasyonu) =====
        sps.is_sms_enabled = lambda: True   # type: ignore
        sps.send_sms = lambda phone, msg: True  # type: ignore

        # ===== 3. required True =====
        check("3. kapı açılınca signup_phone_required() → True",
              sps.signup_phone_required() is True)

        # ===== 4. AÇIK: token yok → 422 =====
        st, body = _signup(c, EMAIL_FAIL)
        code = (body.get("detail") or {}).get("code") if isinstance(body.get("detail"), dict) else None
        check("4. AÇIK: phone_token'sız signup → 422 phone_verification_required",
              st == 422 and code == "phone_verification_required" and _user(EMAIL_FAIL) is None,
              f"status={st} code={code}")

        # ===== 5. start invalid =====
        r = c.post("/api/v2/auth/signup/phone/start", json={"phone": "abc123"})
        code = (r.json().get("detail") or {}).get("code")
        check("5. signup/phone/start geçersiz telefon → 400 invalid_phone",
              r.status_code == 400 and code == "invalid_phone",
              f"status={r.status_code} body={r.text[:160]}")

        # ===== 6. start valid =====
        r = c.post("/api/v2/auth/signup/phone/start", json={"phone": PHONE_RAW})
        otp = _otp_for(PHONE_E164)
        check("6. signup/phone/start geçerli → 200 + DB'de 6 haneli kod",
              r.status_code == 200 and r.json().get("sent") is True
              and otp is not None and len(otp) == 6,
              f"status={r.status_code} otp={'var' if otp else 'yok'}")

        # ===== 7. verify wrong =====
        wrong = f"{(int(otp) + 1) % 1_000_000:06d}" if otp else "000000"
        r = c.post("/api/v2/auth/signup/phone/verify", json={"phone": PHONE_RAW, "code": wrong})
        code = (r.json().get("detail") or {}).get("code")
        check("7. signup/phone/verify yanlış kod → 400 otp_mismatch",
              r.status_code == 400 and code == "otp_mismatch",
              f"status={r.status_code} code={code}")

        # ===== 8. verify correct =====
        r = c.post("/api/v2/auth/signup/phone/verify", json={"phone": PHONE_RAW, "code": otp})
        phone_token = r.json().get("phone_token", "")
        check("8. signup/phone/verify doğru kod → 200 + phone_token",
              r.status_code == 200 and bool(phone_token),
              f"status={r.status_code} token={'var' if phone_token else 'yok'}")

        # ===== 9. decode_phone_token =====
        check("9. decode_phone_token geçerli→telefon, çöp→None",
              sps.decode_phone_token(phone_token) == PHONE_E164
              and sps.decode_phone_token("garbage.token") is None)

        # ===== 10. signup with valid token =====
        st, body = _signup(c, EMAIL_GATED, phone_token=phone_token)
        u = _user(EMAIL_GATED)
        check("10. AÇIK: geçerli phone_token ile signup → 200 + phone + verified_at SET",
              st == 200 and u is not None and u.phone == PHONE_E164
              and u.phone_verified_at is not None,
              f"status={st} phone={getattr(u, 'phone', None)} "
              f"verified={getattr(u, 'phone_verified_at', None)}")

        # ===== 11. phone_in_use at start =====
        r = c.post("/api/v2/auth/signup/phone/start", json={"phone": PHONE_RAW})
        code = (r.json().get("detail") or {}).get("code")
        check("11. kullanımdaki telefonla start → 409 phone_in_use",
              r.status_code == 409 and code == "phone_in_use",
              f"status={r.status_code} code={code}")

        # ===== 12. signup reusing token of now-used phone =====
        st, body = _signup(c, EMAIL_FAIL, phone_token=phone_token)
        code = (body.get("detail") or {}).get("code") if isinstance(body.get("detail"), dict) else None
        check("12. AÇIK: kullanımdaki telefonun token'ıyla signup → 409 phone_in_use",
              st == 409 and code == "phone_in_use" and _user(EMAIL_FAIL) is None,
              f"status={st} code={code}")

    finally:
        sguard.signup_ip_blocked = orig_ip_block  # type: ignore
        sps.is_sms_enabled = orig_sms  # type: ignore
        sps.send_sms = orig_send  # type: ignore
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
