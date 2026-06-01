"""API v2 iletişim talebi (public POST + süper admin yönetim) smoke.

Senaryolar:
   1. GET /api/v2/pricing → contact bloğu (sales_email dolu)
   2. anonim POST /api/v2/contact geçerli → 200 + ok
   3. POST doğrulama: geçersiz e-posta → 422
   4. POST doğrulama: kısa ad → 422
   5. super admin GET /admin/contact-requests → 200 + kayıt görünür + counts.new>=1
   6. status filtresi (new) çalışır
   7. super admin POST /admin/contact-requests/{id} status=contacted → 200 + değişti
   8. geçersiz status → 400
   9. olmayan id → 404
  10. teacher GET list → 403 role_required
  11. anonim GET list → 401
  12. Turnstile aktif + token yok → 401 captcha_failed (monkeypatch)
  13. Turnstile aktif + geçerli token → 200
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
from app.models import AuditLog, ContactRequest, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2contact_{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassContact!23"
CONTACT_EMAIL = f"{PFX}_lead@example.com"

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
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.commit()
        return {"super_id": super_admin.id, "teacher_id": teacher.id}


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(ContactRequest).where(ContactRequest.email == CONTACT_EMAIL))
        db.execute(sa_delete(AuditLog).where(
            AuditLog.actor_id.in_([seed["super_id"], seed["teacher_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_([seed["super_id"], seed["teacher_id"]])))
        # Auth testlerini kirletmemek için testclient IP bloğunu temizle
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 contact smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        anon = TestClient(app)

        # 1. catalog contact bloğu
        r = anon.get("/api/v2/pricing")
        j = r.json() if r.status_code == 200 else {}
        contact = j.get("contact", {})
        check("1. /pricing contact bloğu (sales_email)",
              r.status_code == 200 and bool(contact.get("sales_email")),
              f"contact={contact}")

        # 2. anonim geçerli POST
        r = anon.post("/api/v2/contact", json={
            "name": "Test Kurum Yetkilisi",
            "email": CONTACT_EMAIL,
            "phone": "+905551112233",
            "institution_name": f"{PFX} Dershane",
            "coach_count": 12,
            "message": "Kurumsal teklif almak istiyorum.",
            "source": "pricing_institution",
        })
        check("2. anonim POST /contact → 200 + ok",
              r.status_code == 200 and r.json().get("ok") is True,
              f"status={r.status_code} body={r.text[:200]}")

        # 3. geçersiz e-posta
        r = anon.post("/api/v2/contact", json={"name": "Ad Soyad", "email": "not-an-email"})
        check("3. geçersiz e-posta → 422", r.status_code == 422, f"status={r.status_code}")

        # 4. kısa ad
        r = anon.post("/api/v2/contact", json={"name": "A", "email": CONTACT_EMAIL})
        check("4. kısa ad → 422", r.status_code == 422, f"status={r.status_code}")

        super_client = _login(SUPER_EMAIL)
        teacher_client = _login(TEACHER_EMAIL)

        # 5. super admin list
        r = super_client.get("/api/v2/admin/contact-requests")
        j = r.json() if r.status_code == 200 else {}
        items = j.get("items", [])
        mine = [it for it in items if it.get("email") == CONTACT_EMAIL]
        check("5. super GET list → 200 + kayıt + counts.new>=1",
              r.status_code == 200 and len(mine) == 1
              and j.get("counts", {}).get("new", 0) >= 1
              and mine[0].get("status_label") == "Yeni"
              and mine[0].get("source_label") == "Fiyatlandırma — Kurumsal",
              f"status={r.status_code} mine={mine}")
        req_id = mine[0]["id"] if mine else 0

        # 6. status filtresi
        r = super_client.get("/api/v2/admin/contact-requests", params={"status": "new"})
        ok6 = r.status_code == 200 and all(
            it.get("status") == "new" for it in r.json().get("items", [])
        )
        check("6. status=new filtresi", ok6, f"status={r.status_code}")

        # 7. status güncelle
        r = super_client.post(f"/api/v2/admin/contact-requests/{req_id}", json={
            "status": "contacted", "admin_note": "Aradım, görüşüldü.",
        })
        ok7 = (r.status_code == 200 and r.json().get("data", {}).get("status") == "contacted"
               and "admin:contact-requests" in r.json().get("invalidate", []))
        check("7. status=contacted güncelle → 200", ok7, f"status={r.status_code} body={r.text[:200]}")

        # 8. geçersiz status
        r = super_client.post(f"/api/v2/admin/contact-requests/{req_id}", json={"status": "weird"})
        check("8. geçersiz status → 400", r.status_code == 400, f"status={r.status_code}")

        # 9. olmayan id
        r = super_client.post("/api/v2/admin/contact-requests/99999999", json={"status": "closed"})
        check("9. olmayan id → 404", r.status_code == 404, f"status={r.status_code}")

        # 10. teacher list → 403
        r = teacher_client.get("/api/v2/admin/contact-requests")
        check("10. teacher GET list → 403", r.status_code == 403, f"status={r.status_code}")

        # 11. anonim list → 401
        r = anon.get("/api/v2/admin/contact-requests")
        check("11. anonim GET list → 401", r.status_code == 401, f"status={r.status_code}")

        # 12-13. Turnstile aktifken zorunluluk (monkeypatch — gerçek CF çağrısı yok)
        import app.services.turnstile as ts
        _orig_enabled, _orig_verify = ts.is_enabled, ts.verify_token
        try:
            ts.is_enabled = lambda: True
            ts.verify_token = lambda token, ip=None: token == "good-token"
            # 12. token boş → 401 captcha_failed (kayıt OLUŞMAZ — turnstile ilk adım)
            r = anon.post("/api/v2/contact", json={
                "name": "Bot Deneme", "email": f"{PFX}_bot@example.com",
                "source": "pricing_institution",
            })
            check("12. captcha aktif + token yok → 401 captcha_failed",
                  r.status_code == 401 and r.json().get("detail", {}).get("code") == "captcha_failed",
                  f"status={r.status_code} body={r.text[:200]}")
            # 13. geçerli token → 200
            r = anon.post("/api/v2/contact", json={
                "name": "Gercek Yetkili", "email": CONTACT_EMAIL,
                "source": "pricing_institution", "turnstile_token": "good-token",
            })
            check("13. captcha aktif + geçerli token → 200", r.status_code == 200,
                  f"status={r.status_code} body={r.text[:200]}")
        finally:
            ts.is_enabled, ts.verify_token = _orig_enabled, _orig_verify

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
