"""API v2 /payment/* (Iyzico + PaymentLink) smoke (Ödeme Paket Ö3).

Iyzico SDK çağrıları MONKEYPATCH ile mock'lanır — gerçek Iyzico'ya istek yok,
gerçek ödeme deneme yok. Yalnız backend mantığı + state machine doğrulanır.

Senaryolar:
   1. Anon → 401
   2. Öğrenci → 403 (rol guard)
   3. Provider status — sandbox + available
   4. init_checkout solo_pro/monthly (mock) → payment_page_url + tx pending
   5. init_checkout geçersiz plan → 400 plan_invalid
   6. init_checkout geçersiz cycle → 400 cycle_invalid
   7. callback başarı (mock SUCCESS) → tx succeeded + plan aktive + subscription_status
   8. callback başarısız (mock FAILURE) → tx failed + plan değişmedi
   9. callback idempotent — aynı token 2 kere → ikinci no-op
  10. /transactions/{id} sahip → 200 + alanlar
  11. /transactions/{id} başka koç → 404
  12. /history — son ödemeler listesi (sahibin)
  13. PaymentLink admin create (kurum)
  14. PaymentLink admin create (koç)
  15. PaymentLink yetkisiz user → 403
  16. PaymentLink admin list + status filter
  17. PaymentLink GET /link/{token} (kurum yöneticisi) → can_pay True
  18. PaymentLink GET /link/{token} (yabancı koç) → can_pay False
  19. PaymentLink POST /link/{token}/checkout (yetkisiz) → 403
  20. PaymentLink POST /link/{token}/checkout (yetkili) + callback → kurum planı aktive + link consumed
  21. PaymentLink tek-kullanım — ikinci checkout → 400 link_unusable
  22. PaymentLink admin cancel — aktif link iptal
  23. PaymentLink cancel ikinci kez → 400 not_active
  24. Iyzico SDK exception → 503 provider_unavailable
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
from decimal import Decimal

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    LINK_STATUS_ACTIVE,
    LINK_STATUS_CANCELLED,
    LINK_STATUS_CONSUMED,
    PaymentLink,
    PaymentTransaction,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    User,
    UserRole,
)
from app.services import iyzico_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2pay{secrets.token_hex(3)}"
PASSWORD = "TestPay!23"

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
    """Seed:
      - 1 süper admin
      - 1 ödeyen kurum yöneticisi (institution_admin)
      - 1 bağımsız koç (teacher, ödeme yapacak)
      - 1 başka koç (yetki kontrolü için)
      - 1 öğrenci (403 testi)
    """
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="institution_free", is_active=True,
        )
        db.add(inst)
        db.flush()

        super_admin = User(
            email=f"{PFX}_super@test.invalid", password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        inst_admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash=pwd, full_name=f"{PFX} Admin",
            role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        coach = User(
            email=f"{PFX}_coach@test.invalid", password_hash=pwd, full_name=f"{PFX} Coach",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        other_coach = User(
            email=f"{PFX}_other@test.invalid", password_hash=pwd, full_name=f"{PFX} Other",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        student = User(
            email=f"{PFX}_student@test.invalid", password_hash=pwd, full_name=f"{PFX} Student",
            role=UserRole.STUDENT, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, inst_admin, coach, other_coach, student])
        db.flush()
        out = {
            "inst_id": inst.id,
            "super_id": super_admin.id,
            "inst_admin_id": inst_admin.id,
            "coach_id": coach.id,
            "other_coach_id": other_coach.id,
            "student_id": student.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        user_ids = [seed["super_id"], seed["inst_admin_id"], seed["coach_id"],
                    seed["other_coach_id"], seed["student_id"]]
        # PaymentLink + PaymentTransaction cascade'leri test seed'ine bağlı
        db.query(PaymentTransaction).filter(
            PaymentTransaction.user_id.in_(user_ids)
        ).delete(synchronize_session=False)
        db.query(PaymentLink).filter(
            PaymentLink.created_by_admin_id.in_(user_ids)
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.query(Institution).filter(Institution.id == seed["inst_id"]).delete(synchronize_session=False)
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")
    return c


# --------------------------- Mock fixtures ---------------------------

_LAST_REQUEST: dict = {}


def _mock_create_success(req: dict) -> dict:
    """Iyzico create() mock — başarılı response."""
    _LAST_REQUEST.update(req)
    return {
        "status": "success",
        "conversationId": req["conversationId"],
        "token": f"mock-token-{secrets.token_hex(8)}",
        "paymentPageUrl": f"https://sandbox-cpp.iyzipay.com?token=mock-fake",
    }


def _mock_create_failure(req: dict) -> dict:
    return {
        "status": "failure",
        "errorCode": "10051",
        "errorMessage": "Kart bilgileri hatalı",
    }


def _mock_retrieve_success_for_token(token: str) -> dict:
    return {
        "status": "success",
        "paymentStatus": "SUCCESS",
        "token": token,
        "conversationId": "irrelevant",  # backend artık token ile arar
        "paymentId": "12345",
    }


def _mock_retrieve_failure_for_token(token: str) -> dict:
    return {
        "status": "success",
        "paymentStatus": "FAILURE",
        "token": token,
        "errorMessage": "3D Secure doğrulaması başarısız",
        "mdStatus": "0",
    }


def _mock_sdk_exception(*args, **kwargs):
    raise RuntimeError("Iyzico unreachable (mock network error)")


# ============================ Main ==================================


def main() -> int:
    print(f"\n=== API v2 /payment/* (Iyzico + PaymentLink) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()

    # SDK fonksiyonlarını mock'larla değiştir; finally'de geri al
    orig_create = iyzico_service._iyzico_call_create
    orig_retrieve = iyzico_service._iyzico_call_retrieve

    seed = _seed()
    print(f"  seeded inst={seed['inst_id']} coach={seed['coach_id']}\n")

    try:
        # 1. Anon → 401
        r = TestClient(app).post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("1. Anon → 401", r.status_code == 401, f"status={r.status_code}")

        # 2. Öğrenci → 403
        sc = _login(f"{PFX}_student@test.invalid")
        r = sc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("2. Öğrenci → 403", r.status_code == 403, f"status={r.status_code}")

        # 3. provider-status (anon OK çünkü public)
        r = TestClient(app).get("/api/v2/payment/provider-status")
        j = r.json()
        check("3. provider-status sandbox + available",
              r.status_code == 200 and j.get("available") is True and j.get("sandbox") is True,
              f"j={j}")

        cc = _login(f"{PFX}_coach@test.invalid")
        ot = _login(f"{PFX}_other@test.invalid")
        sa = _login(f"{PFX}_super@test.invalid")
        ia = _login(f"{PFX}_admin@test.invalid")

        # 4. init_checkout başarılı mock
        iyzico_service._iyzico_call_create = _mock_create_success
        r = cc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        j = r.json()
        tx_id = j.get("transaction_id")
        check("4. init_checkout solo_pro/monthly OK",
              r.status_code == 200 and "payment_page_url" in j and tx_id and j.get("amount") == 2500.0,
              f"status={r.status_code} j={j}")

        # 5. Geçersiz plan
        r = cc.post("/api/v2/payment/init", json={"plan_code": "bilinmeyen_plan", "cycle": "monthly"})
        check("5. geçersiz plan → 400", r.status_code == 400,
              f"status={r.status_code}")

        # 6. Geçersiz cycle (Pydantic pattern validation)
        r = cc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "haftalik"})
        check("6. geçersiz cycle → 422 (Pydantic)", r.status_code == 422,
              f"status={r.status_code}")

        # 7. callback başarı — gerçek token'ı DB'den çek (mock_create_success raw_response'a yazdı)
        with SessionLocal() as db:
            tx = db.get(PaymentTransaction, tx_id)
            real_token = tx.provider_reference  # init_checkout token'ı buraya koydu
            assert real_token, "token DB'de yok"
        iyzico_service._iyzico_call_retrieve = _mock_retrieve_success_for_token
        # callback Iyzico tarafından form-POST → form data ile çağır
        r = TestClient(app).post(
            "/api/v2/payment/iyzico/callback",
            data={"token": real_token},
            follow_redirects=False,
        )
        check("7a. callback 303 redirect", r.status_code == 303 and "/payment/result" in r.headers.get("location", ""),
              f"status={r.status_code} loc={r.headers.get('location')}")

        with SessionLocal() as db:
            tx2 = db.get(PaymentTransaction, tx_id)
            coach2 = db.get(User, seed["coach_id"])
            ok_tx = tx2.status == STATUS_SUCCEEDED and tx2.completed_at is not None
            ok_plan = coach2.plan == "solo_pro"
            ok_sub = coach2.subscription_status == "active" and coach2.subscription_cycle == "monthly"
            check("7b. tx=succeeded + plan aktive + subscription_status",
                  ok_tx and ok_plan and ok_sub,
                  f"tx={tx2.status} plan={coach2.plan} sub_status={coach2.subscription_status}")

        # 7c. Yıllık abonelik akışı — cycle="annual" → subscription_cycle="academic_year"
        with SessionLocal() as db:
            db.get(User, seed["coach_id"]).plan = "solo_free"  # reset
            db.get(User, seed["coach_id"]).subscription_status = None
            db.get(User, seed["coach_id"]).subscription_cycle = None
            db.commit()
        iyzico_service._iyzico_call_create = _mock_create_success
        r = cc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "annual"})
        annual_tx_id = r.json()["transaction_id"]
        with SessionLocal() as db:
            annual_token = db.get(PaymentTransaction, annual_tx_id).provider_reference
        iyzico_service._iyzico_call_retrieve = _mock_retrieve_success_for_token
        TestClient(app).post(
            "/api/v2/payment/iyzico/callback",
            data={"token": annual_token}, follow_redirects=False,
        )
        with SessionLocal() as db:
            coach3 = db.get(User, seed["coach_id"])
            check(
                "7c. yıllık akış → subscription_cycle=academic_year (normalize)",
                coach3.subscription_cycle == "academic_year"
                and coach3.subscription_status == "active",
                f"cycle={coach3.subscription_cycle} status={coach3.subscription_status}",
            )

        # 8. Yeni init + callback FAILURE → tx failed + plan değişmedi
        with SessionLocal() as db:
            db.get(User, seed["coach_id"]).plan = "solo_free"  # reset
            db.commit()
        r = cc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        fail_tx_id = r.json()["transaction_id"]
        with SessionLocal() as db:
            tx = db.get(PaymentTransaction, fail_tx_id)
            fail_token = tx.provider_reference
        iyzico_service._iyzico_call_retrieve = _mock_retrieve_failure_for_token
        r = TestClient(app).post(
            "/api/v2/payment/iyzico/callback",
            data={"token": fail_token}, follow_redirects=False,
        )
        with SessionLocal() as db:
            tx2 = db.get(PaymentTransaction, fail_tx_id)
            coach2 = db.get(User, seed["coach_id"])
            check("8. callback FAILURE → tx=failed + plan değişmedi",
                  tx2.status == STATUS_FAILED and coach2.plan == "solo_free",
                  f"tx_status={tx2.status} plan={coach2.plan}")

        # 9. callback idempotent — aynı token tekrar
        iyzico_service._iyzico_call_retrieve = _mock_retrieve_success_for_token
        with SessionLocal() as db:
            tx2 = db.get(PaymentTransaction, tx_id)
            already_succeeded_token = tx2.provider_reference
        r = TestClient(app).post(
            "/api/v2/payment/iyzico/callback",
            data={"token": already_succeeded_token}, follow_redirects=False,
        )
        check("9. callback idempotent (zaten succeeded)", r.status_code == 303,
              f"status={r.status_code}")

        # 10. /transactions/{id} sahip
        r = cc.get(f"/api/v2/payment/transactions/{tx_id}")
        j = r.json()
        check("10. /transactions/{id} sahip → 200",
              r.status_code == 200 and j["status"] == "succeeded" and j["plan_code"] == "solo_pro",
              f"status={r.status_code}")

        # 11. Başka koç → 404
        r = ot.get(f"/api/v2/payment/transactions/{tx_id}")
        check("11. /transactions/{id} başka koç → 404", r.status_code == 404, f"status={r.status_code}")

        # 12. /history
        r = cc.get("/api/v2/payment/history")
        j = r.json()
        check("12. /history koç ödemelerini listele",
              r.status_code == 200 and j["total"] >= 2 and all("status_label" in it for it in j["items"]),
              f"total={j.get('total')}")

        # 13. PaymentLink admin create (kurum)
        r = sa.post("/api/v2/payment/admin/links", json={
            "target_owner_type": "institution",
            "target_owner_id": seed["inst_id"],
            "plan_code": "etut_standart",
            "cycle": "annual",
            "amount": 100000,
            "description": "Smoke test link",
            "expires_in_days": 14,
        })
        j = r.json()
        link_inst_id = j.get("id")
        check("13. PaymentLink admin create (kurum)",
              r.status_code == 200 and j.get("status") == "active" and "token" in j and j["amount"] == 100000.0,
              f"status={r.status_code} j={j}")

        # 14. PaymentLink admin create (koç)
        r = sa.post("/api/v2/payment/admin/links", json={
            "target_owner_type": "user",
            "target_owner_id": seed["coach_id"],
            "plan_code": "solo_unlimited",
            "cycle": "monthly",
            "amount": 6000,
            "expires_in_days": 7,
        })
        j = r.json()
        link_user_id = j.get("id")
        check("14. PaymentLink admin create (koç)",
              r.status_code == 200 and j["target_owner_type"] == "user" and j["amount"] == 6000.0,
              f"status={r.status_code}")

        # 15. Yetkisiz user (koç) link create → 403
        r = cc.post("/api/v2/payment/admin/links", json={
            "target_owner_type": "user", "target_owner_id": seed["coach_id"],
            "plan_code": "solo_pro", "cycle": "monthly", "amount": 2500,
        })
        check("15. koç link create → 403", r.status_code == 403, f"status={r.status_code}")

        # 16. admin list + status filter
        r = sa.get("/api/v2/payment/admin/links?status_filter=active")
        j = r.json()
        check("16. admin list status=active",
              r.status_code == 200 and j["total"] >= 2 and all(it["status"] == "active" for it in j["items"]),
              f"total={j.get('total')}")

        # 17. /link/{token} kurum yöneticisi → can_pay True
        with SessionLocal() as db:
            link = db.get(PaymentLink, link_inst_id)
            token_inst = link.token
        r = ia.get(f"/api/v2/payment/link/{token_inst}")
        j = r.json()
        check("17. /link/{token} kurum yön. → can_pay=True",
              r.status_code == 200 and j["can_pay"] is True and j["target_owner_type"] == "institution",
              f"status={r.status_code} can_pay={j.get('can_pay')}")

        # 18. /link/{token} yabancı koç → can_pay False
        r = ot.get(f"/api/v2/payment/link/{token_inst}")
        j = r.json()
        check("18. /link/{token} yabancı koç → can_pay=False",
              r.status_code == 200 and j["can_pay"] is False,
              f"can_pay={j.get('can_pay')}")

        # 19. /link/{token}/checkout yabancı koç → 403
        r = ot.post(f"/api/v2/payment/link/{token_inst}/checkout")
        check("19. /link/{token}/checkout yabancı koç → 403", r.status_code == 403,
              f"status={r.status_code}")

        # 20. /link/{token}/checkout kurum yöneticisi + callback başarı → kurum planı aktive + link consumed
        iyzico_service._iyzico_call_create = _mock_create_success
        r = ia.post(f"/api/v2/payment/link/{token_inst}/checkout")
        j = r.json()
        link_tx_id = j.get("transaction_id")
        check("20a. link checkout başlat",
              r.status_code == 200 and "payment_page_url" in j,
              f"status={r.status_code}")

        with SessionLocal() as db:
            link_tx = db.get(PaymentTransaction, link_tx_id)
            link_token = link_tx.provider_reference
        iyzico_service._iyzico_call_retrieve = _mock_retrieve_success_for_token
        r = TestClient(app).post(
            "/api/v2/payment/iyzico/callback",
            data={"token": link_token}, follow_redirects=False,
        )
        with SessionLocal() as db:
            link2 = db.get(PaymentLink, link_inst_id)
            inst2 = db.get(Institution, seed["inst_id"])
            tx2 = db.get(PaymentTransaction, link_tx_id)
            check("20b. callback → link consumed + kurum planı aktive + tx succeeded",
                  link2.status == LINK_STATUS_CONSUMED
                  and link2.consumed_transaction_id == link_tx_id
                  and link2.consumed_by_user_id == seed["inst_admin_id"]
                  and inst2.plan == "etut_standart"
                  and tx2.status == STATUS_SUCCEEDED,
                  f"link_status={link2.status} inst_plan={inst2.plan} tx_status={tx2.status}")

        # 21. Aynı link ikinci kez checkout → 400 link_unusable
        r = ia.post(f"/api/v2/payment/link/{token_inst}/checkout")
        check("21. tek-kullanım: consumed link ikinci checkout → 400",
              r.status_code == 400, f"status={r.status_code}")

        # 22. admin cancel — aktif link (link_user_id)
        r = sa.post(f"/api/v2/payment/admin/links/{link_user_id}/cancel")
        j = r.json()
        check("22. admin cancel aktif link",
              r.status_code == 200 and j["status"] == "cancelled",
              f"status={r.status_code}")

        # 23. cancel ikinci kez → 400
        r = sa.post(f"/api/v2/payment/admin/links/{link_user_id}/cancel")
        check("23. cancel iki kez → 400 not_active",
              r.status_code == 400, f"status={r.status_code}")

        # 24. SDK exception → 503
        iyzico_service._iyzico_call_create = _mock_sdk_exception
        with SessionLocal() as db:
            db.get(User, seed["coach_id"]).plan = "solo_free"
            db.commit()
        r = cc.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("24. SDK exception → 503 provider_unavailable",
              r.status_code == 503, f"status={r.status_code}")

    finally:
        # SDK mock'ları geri al
        iyzico_service._iyzico_call_create = orig_create
        iyzico_service._iyzico_call_retrieve = orig_retrieve
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
