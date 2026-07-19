"""Apple IAP (RevenueCat) entegrasyonu smoke — webhook + sync + kanal korumaları.

RevenueCat REST çağrıları MONKEYPATCH ile mock'lanır — gerçek RevenueCat/Apple
isteği yok. Webhook auth + olay işleme + kanal koruması + cron guard doğrulanır.

Senaryolar:
   1. Webhook GET ping → 200
   2. Webhook POST — secret yapılandırılmamış → 403 (güvenli varsayılan)
   3. Webhook POST — yanlış Authorization → 403
   4. Webhook POST — TEST olayı → 200 action=test
   5. INITIAL_PURCHASE → plan solo_elite + status active + platform app_store
      + period_end=Apple bitişi + trial temizlendi
   6. Satın almada pasif öğrenci yeniden aktifleşir (paywall sözü)
   7. RENEWAL (daha geç bitiş) → period_end uzar
   8. CANCELLATION → status canceled, plan korunur
   9. UNCANCELLATION → status yeniden active
  10. EXPIRATION → solo_free + abonelik alanları temiz
  11. EXPIRATION iyzico-platformlu koça → YOK SAYILIR (kanal koruması)
  12. Bilinmeyen ürün → unknown_product, plan değişmez
  13. Çözülemeyen app_user_id → user_not_found (200, retry fırtınası yok)
  14. Kurumlu öğretmene INITIAL_PURCHASE → skipped_not_solo
  15. POST /payment/iap/sync — secret yokken 503
  16. POST /payment/iap/sync — kurumlu öğretmen 403
  17. POST /payment/iap/sync — aktif abonelik (mock) → plan aktive + yanıt alanları
  18. POST /payment/iap/sync — abonelik bitmiş (mock boş) → solo_free + expired
  19. /payment/init — app_store aboneli koç → 409 app_store_managed
  20. /teacher/plan — subscription_platform döner
  21. /teacher/subscription/cancel — app_store → 400 app_store_managed
  22. process_renewals — app_store + sync aktif → past_due YOK, period_end güncel
  23. process_renewals — app_store + sync kapalı + 3 gün geçmiş → solo_free
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Institution, PlanChangeHistory, SuspiciousIp, User, UserRole
from app.services import iap_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2iap{secrets.token_hex(3)}"
PASSWORD = "TestIap!23"
WEBHOOK_SECRET = f"whsec-{secrets.token_hex(8)}"

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
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="institution_free", is_active=True,
        )
        db.add(inst)
        db.flush()
        coach = User(
            email=f"{PFX}_coach@test.invalid", password_hash=pwd, full_name=f"{PFX} Coach",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_trial", trial_ends_at=now + timedelta(days=7),
            password_changed_at=now, must_change_password=False,
        )
        iyz_coach = User(
            email=f"{PFX}_iyz@test.invalid", password_hash=pwd, full_name=f"{PFX} Iyz",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_pro", subscription_status="active",
            subscription_period_end=now + timedelta(days=20),
            subscription_cycle="monthly", subscription_platform="iyzico",
            password_changed_at=now, must_change_password=False,
        )
        inst_teacher = User(
            email=f"{PFX}_instt@test.invalid", password_hash=pwd, full_name=f"{PFX} InstT",
            role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([coach, iyz_coach, inst_teacher])
        db.flush()
        passive_student = User(
            email=f"{PFX}_pupil@test.invalid", password_hash=pwd, full_name=f"{PFX} Pupil",
            role=UserRole.STUDENT, is_active=False, teacher_id=coach.id,
            password_changed_at=now, must_change_password=False,
        )
        db.add(passive_student)
        db.flush()
        out = {
            "inst_id": inst.id, "coach_id": coach.id, "iyz_id": iyz_coach.id,
            "instt_id": inst_teacher.id, "pupil_id": passive_student.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["coach_id"], seed["iyz_id"], seed["instt_id"], seed["pupil_id"]]
        db.query(PlanChangeHistory).filter(
            PlanChangeHistory.owner_id.in_(uids)
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.actor_id.in_(uids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.query(Institution).filter(Institution.id == seed["inst_id"]).delete(
            synchronize_session=False
        )
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
            synchronize_session=False
        )
        db.commit()


def _login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text[:200]}")
    return c


def _get_user(uid: int) -> User:
    with SessionLocal() as db:
        u = db.get(User, uid)
        db.expunge(u)
        return u


def _wh_event(user_id: int, etype: str, product: str | None = "rotam_solo_elite_monthly",
              expires: datetime | None = None) -> dict:
    ev: dict = {
        "type": etype,
        "app_user_id": str(user_id),
        "environment": "SANDBOX",
    }
    if product is not None:
        ev["product_id"] = product
    if expires is not None:
        ev["expiration_at_ms"] = int(expires.timestamp() * 1000)
    return {"api_version": "1.0", "event": ev}


def _post_wh(c: TestClient, payload: dict, auth: str | None = WEBHOOK_SECRET):
    headers = {}
    if auth is not None:
        headers["Authorization"] = auth
    return c.post("/webhooks/revenuecat", json=payload, headers=headers)


def main() -> int:
    seed = _seed()
    anon = TestClient(app)
    orig_wh = settings.revenuecat_webhook_auth
    orig_sk = settings.revenuecat_secret_key
    orig_rc_get = iap_service._rc_get_subscriber
    try:
        now = datetime.now(timezone.utc)
        coach_id = seed["coach_id"]

        # 1. ping
        r = anon.get("/webhooks/revenuecat")
        check("1. webhook GET ping 200", r.status_code == 200 and r.json().get("ok") is True,
              f"{r.status_code}")

        # 2. secret yapılandırılmamış → 403
        settings.revenuecat_webhook_auth = ""
        r = _post_wh(anon, _wh_event(coach_id, "INITIAL_PURCHASE"))
        check("2. secret yokken POST 403", r.status_code == 403, f"{r.status_code}")

        settings.revenuecat_webhook_auth = WEBHOOK_SECRET

        # 3. yanlış auth → 403
        r = _post_wh(anon, _wh_event(coach_id, "INITIAL_PURCHASE"), auth="yanlis")
        check("3. yanlış Authorization 403", r.status_code == 403, f"{r.status_code}")

        # 4. TEST olayı
        r = _post_wh(anon, {"event": {"type": "TEST"}})
        check("4. TEST olayı 200", r.status_code == 200 and r.json().get("action") == "test",
              f"{r.status_code} {r.text[:120]}")

        # 5. INITIAL_PURCHASE → aktive
        exp1 = now + timedelta(days=30)
        r = _post_wh(anon, _wh_event(coach_id, "INITIAL_PURCHASE", expires=exp1))
        u = _get_user(coach_id)
        pe = u.subscription_period_end
        if pe is not None and pe.tzinfo is None:
            pe = pe.replace(tzinfo=timezone.utc)
        check(
            "5. INITIAL_PURCHASE aktive",
            r.status_code == 200 and r.json().get("action") == "activated"
            and u.plan == "solo_elite" and u.subscription_status == "active"
            and u.subscription_platform == "app_store"
            and u.trial_ends_at is None
            and pe is not None and abs((pe - exp1).total_seconds()) < 5,
            f"{r.status_code} plan={u.plan} st={u.subscription_status} "
            f"plat={u.subscription_platform} pe={pe}",
        )

        # 6. pasif öğrenci geri açıldı
        pupil = _get_user(seed["pupil_id"])
        check("6. satın almada pasif öğrenci aktifleşti", pupil.is_active is True,
              f"is_active={pupil.is_active}")

        # 7. RENEWAL → period_end uzar
        exp2 = now + timedelta(days=60)
        r = _post_wh(anon, _wh_event(coach_id, "RENEWAL", expires=exp2))
        u = _get_user(coach_id)
        pe = u.subscription_period_end
        if pe is not None and pe.tzinfo is None:
            pe = pe.replace(tzinfo=timezone.utc)
        check("7. RENEWAL period_end uzadı",
              r.status_code == 200 and pe is not None
              and abs((pe - exp2).total_seconds()) < 5,
              f"pe={pe}")

        # 8. CANCELLATION → canceled, plan korunur
        r = _post_wh(anon, _wh_event(coach_id, "CANCELLATION", expires=exp2))
        u = _get_user(coach_id)
        check("8. CANCELLATION canceled + plan korunur",
              r.status_code == 200 and u.subscription_status == "canceled"
              and u.plan == "solo_elite",
              f"st={u.subscription_status} plan={u.plan}")

        # 9. UNCANCELLATION → active
        r = _post_wh(anon, _wh_event(coach_id, "UNCANCELLATION", expires=exp2))
        u = _get_user(coach_id)
        check("9. UNCANCELLATION yeniden active",
              r.status_code == 200 and u.subscription_status == "active",
              f"st={u.subscription_status}")

        # 12. bilinmeyen ürün (aktif abonelik BOZULMAMALI — 10'dan önce test)
        r = _post_wh(anon, _wh_event(coach_id, "RENEWAL", product="baska_urun"))
        u = _get_user(coach_id)
        check("12. bilinmeyen ürün → değişiklik yok",
              r.status_code == 200 and r.json().get("action") == "unknown_product"
              and u.plan == "solo_elite",
              f"{r.text[:120]} plan={u.plan}")

        # 10. EXPIRATION → solo_free
        r = _post_wh(anon, _wh_event(coach_id, "EXPIRATION"))
        u = _get_user(coach_id)
        check("10. EXPIRATION → solo_free + temiz",
              r.status_code == 200 and u.plan == "solo_free"
              and u.subscription_status is None and u.subscription_platform is None
              and u.subscription_period_end is None,
              f"plan={u.plan} st={u.subscription_status}")

        # 11. EXPIRATION iyzico'lu koça → yok sayılır
        r = _post_wh(anon, _wh_event(seed["iyz_id"], "EXPIRATION"))
        u = _get_user(seed["iyz_id"])
        check("11. iyzico koçuna EXPIRATION yok sayılır",
              r.status_code == 200 and r.json().get("action") == "expiration_ignored"
              and u.plan == "solo_pro" and u.subscription_status == "active",
              f"{r.text[:120]} plan={u.plan}")

        # 13. çözülemeyen app_user_id
        r = _post_wh(anon, {"event": {"type": "RENEWAL", "app_user_id": "$RCAnonymousID:abc"}})
        check("13. user_not_found 200",
              r.status_code == 200 and r.json().get("action") == "user_not_found",
              f"{r.status_code} {r.text[:120]}")

        # 14. kurumlu öğretmen → skipped_not_solo
        r = _post_wh(anon, _wh_event(seed["instt_id"], "INITIAL_PURCHASE",
                                     expires=now + timedelta(days=30)))
        u = _get_user(seed["instt_id"])
        check("14. kurumlu öğretmen skipped_not_solo",
              r.status_code == 200 and r.json().get("action") == "skipped_not_solo"
              and u.subscription_platform is None,
              f"{r.text[:120]}")

        # 15. sync — secret yok → 503
        settings.revenuecat_secret_key = ""
        c_coach = _login(f"{PFX}_coach@test.invalid")
        r = c_coach.post("/api/v2/payment/iap/sync")
        check("15. sync secret yokken 503", r.status_code == 503, f"{r.status_code}")

        # 16. sync — kurumlu öğretmen 403
        settings.revenuecat_secret_key = "sk_test_dummy"
        c_instt = _login(f"{PFX}_instt@test.invalid")
        r = c_instt.post("/api/v2/payment/iap/sync")
        check("16. sync kurumlu öğretmen 403", r.status_code == 403, f"{r.status_code}")

        # 17. sync — aktif abonelik mock → aktive
        exp3 = now + timedelta(days=30)
        def _mock_active(app_user_id: str) -> dict:
            return {"subscriber": {"subscriptions": {
                "rotam_solo_pro_monthly": {
                    "expires_date": exp3.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "unsubscribe_detected_at": None,
                },
            }}}
        iap_service._rc_get_subscriber = _mock_active
        r = c_coach.post("/api/v2/payment/iap/sync")
        u = _get_user(coach_id)
        body = r.json() if r.status_code == 200 else {}
        check("17. sync aktif abonelik → solo_pro aktive",
              r.status_code == 200 and body.get("active") is True
              and body.get("plan_code") == "solo_pro"
              and u.plan == "solo_pro" and u.subscription_platform == "app_store",
              f"{r.status_code} {r.text[:200]} plan={u.plan}")

        # 18. sync — abonelik bitti (boş) → solo_free + expired
        iap_service._rc_get_subscriber = lambda app_user_id: {"subscriber": {"subscriptions": {}}}
        r = c_coach.post("/api/v2/payment/iap/sync")
        u = _get_user(coach_id)
        body = r.json() if r.status_code == 200 else {}
        check("18. sync bitmiş abonelik → solo_free",
              r.status_code == 200 and body.get("active") is False
              and u.plan == "solo_free" and u.subscription_platform is None,
              f"{r.status_code} {r.text[:200]} plan={u.plan}")

        # Yeniden aktive et (19-22 için)
        iap_service._rc_get_subscriber = _mock_active
        c_coach.post("/api/v2/payment/iap/sync")

        # 19. /payment/init app_store'lu koça → 409
        r = c_coach.post("/api/v2/payment/init",
                         json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("19. iyzico init app_store aboneye 409",
              r.status_code == 409
              and r.json()["detail"]["code"] == "app_store_managed",
              f"{r.status_code} {r.text[:150]}")

        # 20. /teacher/plan subscription_platform
        r = c_coach.get("/api/v2/teacher/plan")
        check("20. /teacher/plan platform=app_store",
              r.status_code == 200
              and r.json().get("subscription_platform") == "app_store",
              f"{r.status_code} {r.text[:150]}")

        # 21. cancel endpoint app_store → 400 app_store_managed
        r = c_coach.post("/api/v2/teacher/subscription/cancel")
        check("21. subscription/cancel app_store 400",
              r.status_code == 400
              and r.json()["detail"]["code"] == "app_store_managed",
              f"{r.status_code} {r.text[:150]}")

        # 22. process_renewals — app_store + sync aktif → past_due YOK
        with SessionLocal() as db:
            u_db = db.get(User, coach_id)
            u_db.subscription_period_end = now - timedelta(hours=2)
            db.commit()
        exp4 = now + timedelta(days=29)
        def _mock_renewed(app_user_id: str) -> dict:
            return {"subscriber": {"subscriptions": {
                "rotam_solo_pro_monthly": {
                    "expires_date": exp4.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "unsubscribe_detected_at": None,
                },
            }}}
        iap_service._rc_get_subscriber = _mock_renewed
        from app.services.trial_notifications import process_renewals
        with SessionLocal() as db:
            result = process_renewals(db, now=now)
        u = _get_user(coach_id)
        pe = u.subscription_period_end
        if pe is not None and pe.tzinfo is None:
            pe = pe.replace(tzinfo=timezone.utc)
        check("22. cron app_store sync → past_due yok + period_end güncel",
              u.subscription_status == "active"
              and pe is not None and abs((pe - exp4).total_seconds()) < 5
              and result.get("app_store_synced", 0) >= 1,
              f"st={u.subscription_status} pe={pe} result={result}")

        # 23. process_renewals — sync KAPALI + 4 gün geçmiş → solo_free
        settings.revenuecat_secret_key = ""
        with SessionLocal() as db:
            u_db = db.get(User, coach_id)
            u_db.subscription_period_end = now - timedelta(days=4)
            db.commit()
        with SessionLocal() as db:
            result = process_renewals(db, now=now)
        u = _get_user(coach_id)
        check("23. cron sync kapalı + 4g geçmiş → solo_free",
              u.plan == "solo_free" and u.subscription_status is None
              and u.subscription_platform is None
              and result.get("app_store_dropped", 0) >= 1,
              f"plan={u.plan} st={u.subscription_status} result={result}")

    finally:
        settings.revenuecat_webhook_auth = orig_wh
        settings.revenuecat_secret_key = orig_sk
        iap_service._rc_get_subscriber = orig_rc_get
        _cleanup(seed)

    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print(f"  FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.path.insert(0, ".")
    raise SystemExit(main())
