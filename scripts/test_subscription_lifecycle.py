"""Üyelik yaşam döngüsü — Google tarzı kartsız 14 gün deneme, UÇTAN UCA smoke.

2026-07-24 üyelik revizyonunun regresyon koruması. Zincir:

  signup(intended=solo_pro) → 14g deneme → D-3 hatırlatma → deneme bitişi
  → HER ZAMAN solo_free (ödemesiz ücretliye geçiş YOK) + ön-seçim korunur
  → payment_pending banner sinyali → AI kapalı (403) → arka kapı kapalı (404)
  → mock iyzico ödemesi → aktif abonelik (period_end) → D-3 yenileme
  → dönem bitti → past_due → paywall → tekrar ödeme → aktif + paywall kalkar
  → defensive: ödeme kayıtsız ücretli plan → status payment_required

Gerçek iyzico/AI çağrısı YAPILMAZ (SDK mock).
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    PaymentTransaction,
    PlanChangeHistory,
    PlanOwnerType,
    User,
    UserRole,
)
from app.models.offer import Offer
from app.models.suspicious_ip import SuspiciousIp
from app.models.usage import CreditAccount, UsageOwnerType
from app.services import iyzico_service
from app.services import trial_notifications as tn
from app.services.plans import expire_trials
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"lifec{secrets.token_hex(3)}"
PWD = "LifeCyc1!@#xyz"
EMAIL = f"{PFX}_koc@test.invalid"

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


# ---------------- Iyzico SDK mock ----------------

def _mock_create(req: dict) -> dict:
    return {
        "status": "success",
        "conversationId": req.get("conversationId", "x"),
        "token": f"mock-token-{secrets.token_hex(8)}",
        "paymentPageUrl": "https://sandbox-cpp.iyzipay.com?token=mock-fake",
    }


def _mock_retrieve_ok(token: str) -> dict:
    return {"status": "success", "paymentStatus": "SUCCESS", "token": token,
            "conversationId": "x", "paymentId": "12345"}


def _pay(client: TestClient, plan_code: str) -> int:
    """Mock ödeme: init → callback(success). Returns init status."""
    r = client.post("/api/v2/payment/init", json={"plan_code": plan_code, "cycle": "monthly"})
    if r.status_code != 200:
        return r.status_code
    tx_id = r.json()["transaction_id"]
    with SessionLocal() as db:
        token = db.get(PaymentTransaction, tx_id).provider_reference
    TestClient(app).post(
        "/api/v2/payment/iyzico/callback", data={"token": token}, follow_redirects=False,
    )
    return r.status_code


def _coach_id() -> int:
    with SessionLocal() as db:
        return db.query(User.id).filter(User.email == EMAIL).scalar()


def _coach_field(name):
    with SessionLocal() as db:
        return getattr(db.query(User).filter(User.email == EMAIL).one(), name)


def _set_coach(**kw):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == EMAIL).one()
        for k, v in kw.items():
            setattr(u, k, v)
        db.commit()


def main() -> int:
    print(f"\n=== ÜYELİK YAŞAM DÖNGÜSÜ (kartsız 14g deneme → ödeme) — {PFX} ===\n")
    get_login_limiter().reset()

    now = datetime.now(timezone.utc)
    orig_create = iyzico_service._iyzico_call_create
    orig_retrieve = iyzico_service._iyzico_call_retrieve
    orig_send_email = tn.send_email
    iyzico_service._iyzico_call_create = _mock_create
    iyzico_service._iyzico_call_retrieve = _mock_retrieve_ok
    captured_emails: list[dict] = []
    tn.send_email = lambda **kw: captured_emails.append(kw)

    # Hatırlatma cron'u için süper admin (otomatik DRAFT teklif üretir)
    with SessionLocal() as db:
        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash=hash_password(PWD),
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False)
        db.add(admin)
        db.commit()

    try:
        c = TestClient(app)

        # ── 1. Kayıt: intended_plan=solo_pro → 14g deneme başlar ──
        r = c.post("/api/v2/auth/signup/teacher", json={
            "full_name": f"{PFX} Koç", "email": EMAIL,
            "password": PWD, "password_confirm": PWD,
            "accept_terms": True, "intended_plan": "solo_pro",
        })
        check("1a. signup → 200 + auto-login", r.status_code == 200, f"status={r.status_code} {r.text[:160]}")
        check("1b. plan=solo_trial + post_trial_plan=solo_pro",
              _coach_field("plan") == "solo_trial" and _coach_field("post_trial_plan") == "solo_pro",
              f"plan={_coach_field('plan')} post={_coach_field('post_trial_plan')}")
        r = c.get("/api/v2/teacher/plan")
        check("1c. /plan status=trialing", r.status_code == 200 and r.json()["status"] == "trialing",
              f"{r.text[:120]}")

        # Öğrenci (paywall/publish testleri için 1 adet — limit altında)
        cid = _coach_id()
        with SessionLocal() as db:
            s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                     full_name=f"{PFX} Öğr", role=UserRole.STUDENT, is_active=True,
                     grade_level=8, teacher_id=cid,
                     password_changed_at=now, must_change_password=False)
            db.add(s)
            db.commit()
            sid = s.id

        # ── 2. D-3 hatırlatma: e-posta + otomatik DRAFT teklif ──
        _set_coach(trial_ends_at=now + timedelta(days=2))
        processed = tn.send_trial_reminders(SessionLocal())
        with SessionLocal() as db:
            offer_cnt = db.query(Offer).filter(Offer.user_id == cid).count()
        check("2. D-3 hatırlatma → koç işlendi + DRAFT teklif oluştu",
              processed >= 1 and offer_cnt >= 1, f"processed={processed} offers={offer_cnt}")

        # ── 3. Deneme bitişi: DAİMA solo_free (ödemesiz ücretliye geçiş YOK) ──
        _set_coach(trial_ends_at=now - timedelta(hours=1))
        with SessionLocal() as db:
            result = expire_trials(db)
        check("3a. expire → plan=solo_free (solo_pro DEĞİL!)",
              _coach_field("plan") == "solo_free", f"plan={_coach_field('plan')}")
        check("3b. post_trial_plan=solo_pro KORUNDU (ön-seçim)",
              _coach_field("post_trial_plan") == "solo_pro",
              f"post={_coach_field('post_trial_plan')}")
        with SessionLocal() as db:
            h = (db.query(PlanChangeHistory)
                 .filter(PlanChangeHistory.owner_id == cid,
                         PlanChangeHistory.to_plan == "solo_free")
                 .order_by(PlanChangeHistory.id.desc()).first())
        check("3c. geçmiş notu doğru + 'ödeme bekleyen paket' izi",
              h is not None and "ödeme bekleyen paket: solo_pro" in (h.note or ""),
              f"note={h.note if h else None}")
        # bitiş e-postası seçilen paketi adıyla anıyor
        captured_emails.clear()
        tn.notify_trial_expired(SessionLocal(), user_ids=result.get("expired_user_ids", []))
        exp_mail = next((m for m in captured_emails if m.get("template") == "trial_expired"), None)
        check("3d. bitiş e-postası → intended_plan_label dolu",
              exp_mail is not None and (exp_mail["ctx"].get("intended_plan_label") or "") == "Patika",
              f"mail={exp_mail}")

        # ── 4. Ödeme bekleniyor durumu ──
        r = c.get("/api/v2/teacher/trial-status")
        j = r.json()
        check("4a. trial-status → payment_pending=True + intended=solo_pro + paywall=False",
              r.status_code == 200 and j["payment_pending"] is True
              and j["intended_plan"] == "solo_pro" and j["paywall"] is False,
              f"{r.text[:200]}")
        r = c.get("/api/v2/teacher/plan")
        check("4b. /plan status=free + post_trial ön-seçimi",
              r.status_code == 200 and r.json()["status"] == "free"
              and r.json()["post_trial_plan"] == "solo_pro", f"{r.text[:160]}")
        # AI kapalı (ödeme yapılmadı)
        r = c.post(f"/api/v2/teacher/students/{sid}/sessions/parse-photo",
                   json={"image_base64": "Zm9v", "media_type": "image/jpeg"})
        check("4c. AI → 403 plan_upgrade_required (bedava ücretli özellik YOK)",
              r.status_code == 403 and r.json()["detail"]["code"] == "plan_upgrade_required",
              f"status={r.status_code} {r.text[:140]}")
        # Ödemesiz yükseltme arka kapısı kapalı
        r = c.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_pro"})
        check("4d. /plan/upgrade ucu yok → 404/405", r.status_code in (404, 405), f"status={r.status_code}")

        # ── 5. Kartla ödeme (mock iyzico) → aktif abonelik ──
        st = _pay(c, "solo_pro")
        check("5a. ödeme → plan=solo_pro + subscription active + period_end dolu",
              st == 200 and _coach_field("plan") == "solo_pro"
              and _coach_field("subscription_status") == "active"
              and _coach_field("subscription_period_end") is not None,
              f"init={st} plan={_coach_field('plan')} sub={_coach_field('subscription_status')}")
        r = c.get("/api/v2/teacher/plan")
        check("5b. /plan status=active + ai_premium=True",
              r.status_code == 200 and r.json()["status"] == "active"
              and r.json()["ai_premium"] is True, f"{r.text[:160]}")
        r = c.get("/api/v2/teacher/trial-status")
        check("5c. payment_pending kapandı", r.json()["payment_pending"] is False, f"{r.text[:160]}")

        # ── 6. Yenileme: D-3 hatırlatma → dönem bitti → past_due → paywall ──
        _set_coach(subscription_period_end=now + timedelta(days=2, hours=12))
        captured_emails.clear()
        ren = tn.process_renewals(SessionLocal())
        check("6a. D-3 yenileme hatırlatması gönderildi",
              ren.get("reminded", 0) >= 1
              and any(m.get("template") == "renewal_reminder" for m in captured_emails),
              f"ren={ren}")
        _set_coach(subscription_period_end=now - timedelta(hours=1))
        ren = tn.process_renewals(SessionLocal())
        check("6b. dönem bitti → past_due",
              _coach_field("subscription_status") == "past_due", f"ren={ren}")
        r = c.get("/api/v2/teacher/trial-status")
        check("6c. past_due → paywall=True", r.json()["paywall"] is True, f"{r.text[:160]}")
        r = c.post(f"/api/v2/teacher/students/{sid}/publish-day",
                   json={"task_date": date.today().isoformat()})
        check("6d. aktif koçluk kilitli → 403 paywall_active",
              r.status_code == 403 and r.json()["detail"]["code"] == "paywall_active",
              f"status={r.status_code} {r.text[:140]}")

        # ── 7. Tekrar ödeme → aktif + kilit açılır ──
        st = _pay(c, "solo_pro")
        check("7a. yeniden ödeme → subscription active",
              st == 200 and _coach_field("subscription_status") == "active",
              f"init={st} sub={_coach_field('subscription_status')}")
        r = c.post(f"/api/v2/teacher/students/{sid}/publish-day",
                   json={"task_date": date.today().isoformat()})
        check("7b. koçluk yeniden açık → publish-day 200", r.status_code == 200,
              f"status={r.status_code} {r.text[:120]}")

        # ── 8. Defensive: ödeme kayıtsız ücretli plan → payment_required ──
        _set_coach(subscription_status=None, subscription_period_end=None,
                   subscription_cycle=None, subscription_platform=None)
        r = c.get("/api/v2/teacher/plan")
        check("8. abonelik kayıtsız ücretli plan → status=payment_required",
              r.status_code == 200 and r.json()["status"] == "payment_required",
              f"{r.text[:160]}")

    finally:
        iyzico_service._iyzico_call_create = orig_create
        iyzico_service._iyzico_call_retrieve = orig_retrieve
        tn.send_email = orig_send_email
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(ids)))
                db.execute(sa_delete(Offer).where(Offer.user_id.in_(ids)))
                db.execute(sa_delete(PlanChangeHistory).where(
                    PlanChangeHistory.owner_type == PlanOwnerType.USER,
                    PlanChangeHistory.owner_id.in_(ids)))
                db.execute(sa_delete(CreditAccount).where(
                    CreditAccount.owner_type == UsageOwnerType.USER,
                    CreditAccount.owner_id.in_(ids)))
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
