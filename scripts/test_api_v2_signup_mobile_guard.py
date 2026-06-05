# -*- coding: utf-8 -*-
"""#1 mobil signup + #5 IP hız kapısı smoke.

- Mobil signup (mobile=true): Turnstile atlanır + token'lar response body'sinde döner.
- IP hız kapısı: aynı IP'den BLOCK_THRESHOLD self-signup sonrası yenisi 429.
- signup_velocity dedektörü: o IP'yi sinyal olarak işaretler.

İZOLASYON: TestClient IP'si "testclient" — testten önce/sonra bu IP'nin
self_signup audit'leri + oluşturulan kullanıcılar temizlenir.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import AuditAction, AuditLog, User
from app.models.active_session import ActiveSession
from app.services.abuse_detection import detect_signup_velocity, KIND_SIGNUP_VELOCITY
from app.services.rate_limit import get_login_limiter
from app.services.signup_guard import SIGNUP_IP_BLOCK_THRESHOLD

PFX = f"sgmob_{secrets.token_hex(3)}"
PWD = "SignupMobile!2345"
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


def _clear_testclient_signup_audits():
    """testclient IP'sinin self_signup audit'lerini sil (IP sayımı izolasyonu)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    with SessionLocal() as db:
        db.execute(sa_delete(AuditLog).where(
            AuditLog.action == AuditAction.USER_CREATE,
            AuditLog.ip_address == "testclient",
            AuditLog.created_at >= cutoff,
            AuditLog.details_json.like('%"self_signup": true%'),
        ))
        db.commit()


def _cleanup_users():
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.like(f"{PFX}-%")).all()
        ids = [u.id for u in users]
        if ids:
            db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(ids)))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def _signup(c, n):
    return c.post("/api/v2/auth/signup/teacher", json={
        "full_name": f"{PFX} Koç {n}",
        "email": f"{PFX}-{n}@test.invalid",
        "password": PWD, "password_confirm": PWD,
        "accept_terms": True, "mobile": True,
    })


def main() -> int:
    print(f"\n=== mobil signup + IP hız kapısı — {PFX} (block eşik={SIGNUP_IP_BLOCK_THRESHOLD}) ===\n")
    get_login_limiter().reset()
    _clear_testclient_signup_audits()
    _cleanup_users()
    try:
        c = TestClient(app)

        # 1. İlk mobil signup → 200 + token body'de (captcha yok)
        r = _signup(c, 0)
        b = r.json() if r.status_code == 200 else {}
        check("1. mobil signup → 200 (Turnstile atlandı)", r.status_code == 200,
              f"status={r.status_code} body={r.text[:160]}")
        check("2. response body'de access+refresh token (mobil Bearer)",
              bool(b.get("access_token")) and bool(b.get("refresh_token")),
              f"keys={list(b.keys())}")
        # access_token ile /me çalışmalı (token geçerli)
        if b.get("access_token"):
            r_me = c.get("/api/v2/me", headers={"authorization": f"Bearer {b['access_token']}"})
            check("3. dönen token ile /me 200", r_me.status_code == 200,
                  f"status={r_me.status_code}")

        # Eşiğe kadar daha signup (toplam BLOCK_THRESHOLD adet başarılı olmalı)
        for n in range(1, SIGNUP_IP_BLOCK_THRESHOLD):
            r = _signup(c, n)
            check(f"4.{n} signup #{n + 1} → 200 (eşik altı)", r.status_code == 200,
                  f"status={r.status_code} {r.text[:100]}")

        # Eşik aşıldı → bir sonraki 429
        r = _signup(c, SIGNUP_IP_BLOCK_THRESHOLD)
        check(f"5. {SIGNUP_IP_BLOCK_THRESHOLD + 1}. signup → 429 IP hız kapısı (BLOCK)",
              r.status_code == 429
              and r.json().get("detail", {}).get("code") == "signup_ip_rate_limited",
              f"status={r.status_code} {r.text[:140]}")

        # signup_velocity dedektörü o IP'yi yakalamalı
        with SessionLocal() as db:
            hits = detect_signup_velocity(db)
            tc_hits = [h for h in hits if h.details.get("ip") == "testclient"]
            check("6. signup_velocity dedektörü testclient IP'sini işaretledi",
                  len(tc_hits) == 1 and tc_hits[0].kind == KIND_SIGNUP_VELOCITY
                  and tc_hits[0].count >= SIGNUP_IP_BLOCK_THRESHOLD,
                  f"hits={len(tc_hits)} count={tc_hits[0].count if tc_hits else '-'}")

    finally:
        _cleanup_users()
        _clear_testclient_signup_audits()
        print("\n  temizlendi")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
