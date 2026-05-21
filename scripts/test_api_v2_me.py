"""API v2 /me smoke — Dalga 1 kabul testi.

Senaryolar:
  1. /api/v2/ping → 200 (auth gerektirmez)
  2. /api/v2/me Bearer ile → 200, user.email eşleşir
  3. /api/v2/me Bearer YOK → 401 + code: "missing_credentials"
  4. /api/v2/me bozuk Bearer → 401 + code: "invalid_token"
  5. /api/v2/me/data-export Bearer ile → 200, JSON attachment
  6. POST /api/v2/me/data-delete {confirm: true} → 202, MutationResponse
  7. POST /api/v2/me/data-delete tekrar (idempotent) → 202, aynı request_id
  8. POST /api/v2/me/data-delete {confirm: false} → 422, code: "confirmation_required"
  9. POST /me/data-delete/{id}/cancel → 200, invalidate listesi var
  10. /api/v2/me Session cookie ile → 200 (TestClient session middleware)
  11. /api/v2/me must_change_password=True user → 403 + code: "password_change_required"
  12. /me/data-delete/{başkasının_id}/cancel → 403 + code: "not_owner"
  13. /me/data-delete/9999999/cancel → 404 + code: "request_not_found"

Test kullanıcılar: secrets prefix ile yeni oluşturulur; mevcut hesaplara dokunulmaz.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    User,
    UserRole,
)
from app.services.security import hash_password


PFX = f"v2me_{secrets.token_hex(3)}"
USER_EMAIL = f"{PFX}@test.invalid"
OTHER_EMAIL = f"{PFX}_other@test.invalid"
MCP_EMAIL = f"{PFX}_mcp@test.invalid"
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


def _seed_users() -> tuple[int, int, int]:
    """Test user (TEACHER), another user (TEACHER), must_change_password user.

    Mevcut hesaplara dokunulmaz (feedback_never_touch_user_passwords memo'su).
    """
    with SessionLocal() as db:
        primary = User(
            email=USER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="V2 Me Test Öğretmen",
            role=UserRole.TEACHER,
            is_active=True,
            plan="solo_free",
        )
        other = User(
            email=OTHER_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="V2 Me Diğer Öğretmen",
            role=UserRole.TEACHER,
            is_active=True,
            plan="solo_free",
        )
        mcp_user = User(
            email=MCP_EMAIL,
            password_hash=hash_password(PASSWORD),
            full_name="V2 Me MCP Test",
            role=UserRole.TEACHER,
            is_active=True,
            must_change_password=True,   # 403 password_change_required testi için
            plan="solo_free",
        )
        db.add_all([primary, other, mcp_user])
        db.commit()
        return primary.id, other.id, mcp_user.id


def _cleanup_users(*user_ids: int) -> None:
    """Test sonu temizlik — bağlantılı DataSubjectRequest'leri de sil."""
    with SessionLocal() as db:
        db.query(DataSubjectRequest).filter(
            DataSubjectRequest.target_user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()


def _login(client: TestClient, email: str, password: str = PASSWORD) -> str:
    """API v1 login → access token."""
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["tokens"]["access_token"]


def main() -> int:
    print(f"\n=== API v2 /me smoke (Dalga 1) — prefix: {PFX} ===\n")

    primary_id, other_id, mcp_id = _seed_users()
    print(f"  seeded: primary={primary_id}, other={other_id}, mcp={mcp_id}\n")

    client = TestClient(app)
    other_request_id: int | None = None
    my_request_id: int | None = None

    try:
        # 1. /api/v2/ping
        r = client.get("/api/v2/ping")
        check(
            "1. /api/v2/ping",
            r.status_code == 200 and r.json().get("service") == "lgs-api-v2",
            f"got status={r.status_code} body={r.text[:120]}",
        )

        # Login
        access = _login(client, USER_EMAIL)
        auth = {"Authorization": f"Bearer {access}"}

        # 2. GET /me Bearer ile
        r = client.get("/api/v2/me", headers=auth)
        ok = (
            r.status_code == 200
            and r.json()["user"]["email"] == USER_EMAIL
            and r.json()["user"]["role"] == "teacher"
            and r.json()["kvkk_status"]["has_pending_delete"] is False
        )
        check("2. GET /me Bearer", ok, f"status={r.status_code} body={r.text[:200]}")

        # 3. GET /me Bearer yok → 401 missing_credentials
        r = client.get("/api/v2/me")
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        ok = (
            r.status_code == 401
            and body.get("detail", {}).get("code") == "missing_credentials"
        )
        check("3. GET /me unauth", ok, f"status={r.status_code} body={r.text[:200]}")

        # 4. GET /me bozuk Bearer → 401 invalid_token
        r = client.get("/api/v2/me", headers={"Authorization": "Bearer garbage.token.x"})
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 401
            and body.get("detail", {}).get("code") == "invalid_token"
        )
        check("4. GET /me bozuk token", ok, f"status={r.status_code} body={r.text[:200]}")

        # 5. GET /me/data-export → JSON attachment
        r = client.get("/api/v2/me/data-export", headers=auth)
        cd = r.headers.get("content-disposition", "")
        ok = (
            r.status_code == 200
            and "attachment" in cd
            and ".json" in cd
        )
        try:
            payload = json.loads(r.content.decode("utf-8"))
            has_subject = (
                payload.get("data_subject", {}).get("email") == USER_EMAIL
            )
        except Exception:
            has_subject = False
        check(
            "5. GET /me/data-export",
            ok and has_subject,
            f"status={r.status_code} cd={cd} has_subject={has_subject}",
        )

        # 6. POST /me/data-delete confirm=true → 202
        r = client.post(
            "/api/v2/me/data-delete",
            headers=auth,
            json={"confirm": True, "reason": "test smoke"},
        )
        body = r.json() if r.text else {}
        my_request_id = body.get("data", {}).get("request_id")
        ok = (
            r.status_code == 202
            and isinstance(my_request_id, int)
            and "me:kvkk" in body.get("invalidate", [])
        )
        check(
            "6. POST /me/data-delete confirm=true",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # 7. POST /me/data-delete tekrar → idempotent (aynı id)
        r = client.post(
            "/api/v2/me/data-delete",
            headers=auth,
            json={"confirm": True, "reason": "yine"},
        )
        body = r.json() if r.text else {}
        again_id = body.get("data", {}).get("request_id")
        ok = r.status_code == 202 and again_id == my_request_id
        check(
            "7. POST /me/data-delete idempotent",
            ok,
            f"status={r.status_code} again_id={again_id} (orig={my_request_id})",
        )

        # 8. POST /me/data-delete confirm=false → 422 confirmation_required
        r = client.post(
            "/api/v2/me/data-delete",
            headers=auth,
            json={"confirm": False},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "confirmation_required"
        )
        check(
            "8. POST /me/data-delete confirm=false",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # 9. POST /me/data-delete/{id}/cancel → 200 + invalidate
        r = client.post(
            f"/api/v2/me/data-delete/{my_request_id}/cancel",
            headers=auth,
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("ok") is True
            and "me:kvkk" in body.get("invalidate", [])
        )
        check(
            "9. POST /me/data-delete/{id}/cancel",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # 10. GET /me Session cookie ile (TestClient — Jinja akışı simülasyonu)
        # SessionMiddleware ile manuel session — gerçek login akışı /login POST'una
        # bağlı, ama smoke için ayrı bir client'ta /login üzerinden cookie alıyoruz.
        cookie_client = TestClient(app)
        cookie_login = cookie_client.post(
            "/login",
            data={"email": USER_EMAIL, "password": PASSWORD},
            follow_redirects=False,
        )
        # /login başarılı: 303 (redirect) veya 302
        login_ok = cookie_login.status_code in (302, 303)
        r = cookie_client.get("/api/v2/me")
        body = r.json() if r.text else {}
        ok = (
            login_ok
            and r.status_code == 200
            and body.get("user", {}).get("email") == USER_EMAIL
        )
        check(
            "10. GET /me Session cookie",
            ok,
            f"login_status={cookie_login.status_code} me_status={r.status_code}",
        )

        # 11. /me must_change_password=True → 403 password_change_required
        # MCP user için login akışı zorlu (web /login mcp'yi /password/change'e
        # yönlendiriyor), bu yüzden doğrudan API v1 JWT ile test edelim.
        mcp_access = _login(client, MCP_EMAIL)
        r = client.get(
            "/api/v2/me",
            headers={"Authorization": f"Bearer {mcp_access}"},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 403
            and body.get("detail", {}).get("code") == "password_change_required"
        )
        check(
            "11. GET /me mcp user",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # 12. Başkasının request_id'siyle cancel → 403 not_owner
        # Önce other user için bir delete talebi oluştur (DB direkt)
        with SessionLocal() as db:
            other = db.get(User, other_id)
            other_req = DataSubjectRequest(
                kind=DataRequestKind.DELETE,
                status=DataRequestStatus.PROCESSING,
                requester_user_id=other.id,
                target_user_id=other.id,
                reason="other's request",
            )
            db.add(other_req)
            db.commit()
            other_request_id = other_req.id

        r = client.post(
            f"/api/v2/me/data-delete/{other_request_id}/cancel",
            headers=auth,   # primary user, other'ın talebine girer
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 403
            and body.get("detail", {}).get("code") == "not_owner"
        )
        check(
            "12. cancel başkasının talebi",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # 13. Olmayan request_id → 404 request_not_found
        r = client.post(
            "/api/v2/me/data-delete/9999999/cancel",
            headers=auth,
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 404
            and body.get("detail", {}).get("code") == "request_not_found"
        )
        check(
            "13. cancel olmayan id",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

    finally:
        _cleanup_users(primary_id, other_id, mcp_id)
        print("\n  cleanup OK\n")

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
