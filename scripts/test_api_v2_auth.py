"""API v2 /auth smoke — BFF cookie akışı + 3-kanal regresyon.

Senaryolar (sıra ÖNEMLİ — rate limit testi sona, çünkü limiter pencere = 60s):
  1. POST /api/v2/auth/login valid → 200 + Set-Cookie iki cookie + user body
  2. POST /api/v2/auth/login wrong password → 401 + code: invalid_credentials
  3. POST /api/v2/auth/login inactive user → 401 generic (enumeration koruması)
  4. GET /api/v2/me cookie ile (login sonrası) → 200, user.email eşleşir
  5. GET /api/v2/auth/me convenience → 200 + UserPublic
  6. POST /api/v2/auth/refresh refresh cookie ile → 200 + access cookie yenilendi
  7. POST /api/v2/auth/refresh refresh cookie YOK → 401 missing_refresh_token
  8. POST /api/v2/auth/logout → 200 + Set-Cookie clear
  9. Logout sonrası /api/v2/me → 401 missing_credentials
  10. Şifre değişimi → eski cookie token_revoked (JWT doğrudan, login bypass)
  11. Bearer + Cookie aynı istekte → Cookie öncelikli
  12. Bearer YALNIZ (mobile akışı dokunulmaz) → 200
  13. Session cookie YALNIZ (Jinja /login geçiş garantisi) → 200
  14. Rate limit: /api/v2/auth/login 11x → 429 (SON, sonra reset)

Test kullanıcılar: secrets prefix; mevcut hesaplara dokunulmaz.
Rate limit test'inden sonra `get_login_limiter().reset()` ile temizlik —
sonraki regresyon (test_api_v1) kendi rate limit testini temiz koşabilsin.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import DataSubjectRequest, SuspiciousIp, User, UserRole
from app.services.jwt_auth import issue_access_token
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2auth_{secrets.token_hex(3)}"
USER_EMAIL = f"{PFX}@test.invalid"
INACTIVE_EMAIL = f"{PFX}_inactive@test.invalid"
PASSWORD = "TestPass123!@xyz"
NEW_PASSWORD = "NewPass456!@abc"

ACCESS = settings.auth_cookie_access_name
REFRESH = settings.auth_cookie_refresh_name

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


def _seed_users() -> tuple[int, int]:
    with SessionLocal() as db:
        primary = User(
            email=USER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="V2 Auth Test",
            role=UserRole.TEACHER,
            is_active=True,
            plan="solo_free",
        )
        inactive = User(
            email=INACTIVE_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="V2 Auth Inactive",
            role=UserRole.TEACHER,
            is_active=False,
            plan="solo_free",
        )
        db.add_all([primary, inactive])
        db.commit()
        return primary.id, inactive.id


def _cleanup_users(*user_ids: int) -> None:
    with SessionLocal() as db:
        db.query(DataSubjectRequest).filter(
            DataSubjectRequest.target_user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        # record_failed_login_ip TestClient IP'sini ("testclient") bloklayabilir;
        # sonraki test paketleri 429 almasın diye temizle.
        db.query(SuspiciousIp).filter(
            SuspiciousIp.ip == "testclient"
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()


def _cookie_header(name: str, value: str) -> dict[str, str]:
    """Manuel Cookie header üretici — httpx jar bazen domain eşleştirmesinde
    cookie'yi tutmuyor; explicit header en güvenilir yol."""
    return {"Cookie": f"{name}={value}"}


def _make_access_token(user_id: int) -> str:
    """JWT access token'ı doğrudan servisten üret — login flow'unu atla."""
    with SessionLocal() as db:
        u = db.get(User, user_id)
        return issue_access_token(u, now=datetime.now(timezone.utc))


def main() -> int:
    print(f"\n=== API v2 /auth smoke (BFF cookie) — prefix: {PFX} ===")
    print(f"  cookie names: access={ACCESS!r}  refresh={REFRESH!r}\n")

    # Önceki run'lardan kalmış olabilecek rate limit cache'ini temizle
    get_login_limiter().reset()

    primary_id, inactive_id = _seed_users()
    print(f"  seeded: primary={primary_id}, inactive={inactive_id}\n")

    try:
        # ===== 1. valid login =====
        client = TestClient(app)
        r = client.post("/api/v2/auth/login", json={"email": USER_EMAIL, "password": PASSWORD})
        body = r.json() if r.text else {}
        cookies = {c.name: c for c in client.cookies.jar}
        ok = (
            r.status_code == 200
            and body.get("user", {}).get("email") == USER_EMAIL
            and ACCESS in cookies
            and REFRESH in cookies
            and body.get("must_change_password") is False
        )
        check("1. login valid → 200 + cookies", ok,
              f"status={r.status_code} access={ACCESS in cookies} refresh={REFRESH in cookies}")

        # ===== 2. wrong password =====
        wrong_client = TestClient(app)
        r = wrong_client.post(
            "/api/v2/auth/login", json={"email": USER_EMAIL, "password": "WRONG_PASS_123"}
        )
        body = r.json() if r.text else {}
        ok = r.status_code == 401 and body.get("detail", {}).get("code") == "invalid_credentials"
        check("2. login wrong password → 401", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 3. inactive user =====
        inactive_client = TestClient(app)
        r = inactive_client.post(
            "/api/v2/auth/login", json={"email": INACTIVE_EMAIL, "password": PASSWORD}
        )
        body = r.json() if r.text else {}
        ok = r.status_code == 401 and body.get("detail", {}).get("code") == "invalid_credentials"
        check("3. login inactive user → 401 generic", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 4. /api/v2/me cookie ile =====
        r = client.get("/api/v2/me")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("user", {}).get("email") == USER_EMAIL
        check("4. GET /me cookie ile → 200", ok, f"status={r.status_code}")

        # ===== 5. /api/v2/auth/me convenience =====
        r = client.get("/api/v2/auth/me")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("email") == USER_EMAIL
            and body.get("role") == "teacher"
        )
        check("5. GET /auth/me convenience → 200", ok, f"status={r.status_code}")

        # ===== 6. refresh → 200 + access cookie güncel =====
        # JWT iat/exp saniye granül; aynı saniyede token çakışabilir — bu yüzden
        # rotation tespit etmiyoruz, sadece "yeni Set-Cookie response'ta var mı"yı doğruluyoruz.
        r = client.post("/api/v2/auth/refresh")
        body = r.json() if r.text else {}
        # Response header'larında Set-Cookie içinde ACCESS adı var mı?
        set_cookie_headers = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else []
        if not set_cookie_headers:
            # httpx CaseInsensitiveDict — fallback
            set_cookie_headers = [v for k, v in r.headers.items() if k.lower() == "set-cookie"]
        cookie_set = any(h.startswith(f"{ACCESS}=") for h in set_cookie_headers)
        ok = (
            r.status_code == 200
            and body.get("email") == USER_EMAIL
            and cookie_set
        )
        check("6. /auth/refresh → 200 + access cookie yenilendi", ok,
              f"status={r.status_code} cookie_set={cookie_set}")

        # ===== 7. refresh cookie yok → 401 =====
        no_refresh_client = TestClient(app)
        r = no_refresh_client.post("/api/v2/auth/refresh")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 401
            and body.get("detail", {}).get("code") == "missing_refresh_token"
        )
        check("7. /auth/refresh cookie YOK → 401", ok,
              f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 8. logout → 200 + cookies clear =====
        r = client.post("/api/v2/auth/logout")
        ok = r.status_code == 200 and r.json().get("ok") is True
        check("8. /auth/logout → 200 ok", ok, f"status={r.status_code}")

        # ===== 9. logout sonrası /me → 401 =====
        # httpx Max-Age=0 ile cookie'leri jar'dan siler
        post_logout_cookies = {c.name: c for c in client.cookies.jar}
        cookie_cleared = (
            ACCESS not in post_logout_cookies
            or post_logout_cookies[ACCESS].value in ("", None)
        )
        r = client.get("/api/v2/me")
        body = r.json() if r.text else {}
        ok = (
            cookie_cleared
            and r.status_code == 401
            and body.get("detail", {}).get("code") == "missing_credentials"
        )
        check("9. logout sonrası /me → 401", ok,
              f"cleared={cookie_cleared} status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 10. şifre değişimi → eski cookie token_revoke (login bypass) =====
        # JWT'yi doğrudan üret, Cookie header'ı ile gönder — login flow'u kullanma.
        token_before = _make_access_token(primary_id)
        rev_client = TestClient(app)
        # Önce token'ın geçerli olduğunu doğrula
        r = rev_client.get("/api/v2/me", headers=_cookie_header(ACCESS, token_before))
        precheck_ok = r.status_code == 200

        # DB'de şifre + password_changed_at güncelle (pwd_stamp döner)
        with SessionLocal() as db:
            u = db.get(User, primary_id)
            u.password_hash = hash_password(NEW_PASSWORD)
            u.password_changed_at = datetime.now(timezone.utc)
            db.commit()

        # Aynı eski cookie ile /me → 401 token_revoked
        r = rev_client.get("/api/v2/me", headers=_cookie_header(ACCESS, token_before))
        body = r.json() if r.text else {}
        ok = (
            precheck_ok
            and r.status_code == 401
            and body.get("detail", {}).get("code") == "token_revoked"
        )
        check("10. şifre değişti → eski cookie revoke", ok,
              f"precheck={precheck_ok} status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 11. cookie + bozuk bearer → cookie galip =====
        # Yeni JWT (şifre değişimi sonrası geçerli) → Cookie + Authorization beraber
        token_after = _make_access_token(primary_id)
        cp_client = TestClient(app)
        headers = _cookie_header(ACCESS, token_after)
        headers["Authorization"] = "Bearer this.is.garbage.token"
        r = cp_client.get("/api/v2/me", headers=headers)
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("user", {}).get("email") == USER_EMAIL
        check("11. cookie + bozuk bearer → cookie galip", ok,
              f"status={r.status_code} body={r.text[:120]}")

        # ===== 12. Bearer YALNIZ (mobile akışı) =====
        bare_client = TestClient(app)
        r = bare_client.get(
            "/api/v2/me",
            headers={"Authorization": f"Bearer {token_after}"},
        )
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("user", {}).get("email") == USER_EMAIL
        check("12. Bearer YALNIZ (mobile) → 200", ok, f"status={r.status_code}")

        # ===== 13. Session cookie YALNIZ (Jinja /login) =====
        # Jinja /login web rotası — api/v2/auth/login'in rate limit'ini etkilemez
        session_client = TestClient(app)
        login_resp = session_client.post(
            "/login",
            data={"email": USER_EMAIL, "password": NEW_PASSWORD},
            follow_redirects=False,
        )
        login_ok = login_resp.status_code in (302, 303)
        r = session_client.get("/api/v2/me")
        body = r.json() if r.text else {}
        ok = (
            login_ok
            and r.status_code == 200
            and body.get("user", {}).get("email") == USER_EMAIL
        )
        check("13. Session cookie YALNIZ (Jinja) → 200", ok,
              f"login_status={login_resp.status_code} me_status={r.status_code}")

        # ===== 14. Rate limit 11x → 429 (SON) =====
        rl_client = TestClient(app)
        last_status = None
        for i in range(11):
            r = rl_client.post(
                "/api/v2/auth/login",
                json={"email": f"nobody-{PFX}-{i}@nope.invalid", "password": "x"},
            )
            last_status = r.status_code
        ok = last_status == 429
        check("14. /auth/login rate limit (11x → 429)", ok, f"last_status={last_status}")

    finally:
        _cleanup_users(primary_id, inactive_id)
        # ÖNEMLİ: sonraki test paketleri (test_api_v1, vb.) temiz başlasın
        get_login_limiter().reset()
        print("\n  cleanup OK (limiter reset)\n")

    total = passed + len(failed)
    print(f"\n=== SONUÇ: {passed}/{total} PASS ===")
    if failed:
        print("\nFAILED:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
