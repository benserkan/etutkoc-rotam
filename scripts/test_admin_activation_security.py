"""Elle paket aktivasyonu güvenlik katmanları (2026-10-28) — smoke.

1 süper admin 2FA zorunlu (kurulmamışsa admin API 403 · /me bayrakları)
2 işlem anında kod (yok → step_up_required · hatalı → step_up_invalid + iz)
3 ayrı kanaldan bildirim (e-posta + push, arka plan)
4 tür + not zorunlu · hediye platform=gift → MRR'ye katılmaz · plan geçmişi etiketi
5 400 gün tavanı · hediye sayacı + manual_gift_burst alarm değeri · bütünlük bulgusu
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

import pyotp
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, PlanChangeHistory, SuspiciousIp, TotpBackupCode, User, UserRole
from app.services import admin_activation_notify as notify_mod
from app.services import alarm_engine, data_integrity, email_service, push_notifications
from app.services.rate_limit import get_login_limiter
from app.services.revenue_owner import mrr_owner_aware
from app.services.security import hash_password

PFX = secrets.token_hex(3)
PW = "ActSec!2026xYz"
passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label} ({detail})")


def code_of(r):
    try:
        return r.json()["detail"]["code"]
    except Exception:
        return None


sent_mail: list[tuple[str, str]] = []
pushes: list[int] = []
orig_send, orig_push = email_service.send_email, push_notifications.safe_push
email_service.send_email = lambda to, tpl, ctx, **k: sent_mail.append((to, tpl)) or True
push_notifications.safe_push = (
    lambda db, *, user_id, title, body, data=None: pushes.append(user_id)
)
orig_flag = settings.super_admin_require_2fa
settings.super_admin_require_2fa = True
secret = pyotp.random_base32()


def now_code() -> str:
    return pyotp.TOTP(secret).now()


with SessionLocal() as db:
    a = User(email=f"sa{PFX}@t.invalid", password_hash=hash_password(PW), full_name="Güv SA",
             role=UserRole.SUPER_ADMIN, is_active=True, must_change_password=False)
    c1 = User(email=f"k1{PFX}@t.invalid", password_hash=hash_password(PW), full_name="Koç Bir",
              role=UserRole.TEACHER, is_active=True, plan="solo_free", must_change_password=False)
    c2 = User(email=f"k2{PFX}@t.invalid", password_hash=hash_password(PW), full_name="Koç İki",
              role=UserRole.TEACHER, is_active=True, plan="solo_free", must_change_password=False)
    db.add_all([a, c1, c2])
    db.commit()
    ids = {"a": a.id, "c1": c1.id, "c2": c2.id}

try:
    get_login_limiter().reset()
    cl = TestClient(app)
    cl.post("/api/v2/auth/login", json={"email": f"sa{PFX}@t.invalid", "password": PW})

    print("== 1. 2FA zorunlu")
    r = cl.get("/api/v2/admin/dashboard")
    check("2FA yokken admin API → 403 two_factor_setup_required",
          r.status_code == 403 and code_of(r) == "two_factor_setup_required", r.text[:120])
    me = cl.get("/api/v2/me").json()["user"]
    check("/me two_factor_required=True · enabled=False",
          me.get("two_factor_required") is True and me.get("two_factor_enabled") is False,
          str(me)[:150])
    r = cl.get("/api/v2/me/2fa/status")
    check("kurulum uçları açık (/me/2fa/status 200)", r.status_code == 200, r.text[:80])
    with SessionLocal() as db:
        u = db.get(User, ids["a"])
        u.totp_secret = secret
        u.totp_enabled_at = datetime.now(timezone.utc)
        db.commit()
    r = cl.get("/api/v2/admin/dashboard")
    check("2FA açılınca admin API → 200", r.status_code == 200, r.text[:80])

    url = f"/api/v2/admin/users/{ids['c1']}/activate-plan"
    base = {"plan": "solo_pro", "cycle": "custom", "custom_days": 365}

    print("== 4. tür + not")
    r = cl.post(url, json=base)
    check("tür yok → 422 grant_kind_required",
          r.status_code == 422 and code_of(r) == "grant_kind_required", r.text[:100])
    r = cl.post(url, json={**base, "grant_kind": "gift"})
    check("not yok → 422 note_required",
          r.status_code == 422 and code_of(r) == "note_required", r.text[:100])

    print("== 5. tavan")
    r = cl.post(url, json={**base, "custom_days": 401, "grant_kind": "gift",
                           "note": "test", "totp_code": now_code()})
    check("401 gün → 422", r.status_code == 422, r.text[:100])

    print("== 2. işlem anında kod")
    r = cl.post(url, json={**base, "grant_kind": "gift", "note": "hediye test"})
    check("kod yok → 403 step_up_required",
          r.status_code == 403 and code_of(r) == "step_up_required", r.text[:100])
    r = cl.post(url, json={**base, "grant_kind": "gift", "note": "hediye test",
                           "totp_code": "000000"})
    check("hatalı kod → 403 step_up_invalid",
          r.status_code == 403 and code_of(r) == "step_up_invalid", r.text[:100])
    with SessionLocal() as db:
        n_fail = (db.query(AuditLog)
                  .filter(AuditLog.target_id == ids["c1"],
                          AuditLog.details_json.like("%step_up_failed%"))
                  .count())
        check("hatalı kod denetim kaydına düştü", n_fail == 1, str(n_fail))
        check("hatalı kodla paket AÇILMADI", db.get(User, ids["c1"]).plan == "solo_free")

    sent_mail.clear()
    pushes.clear()
    r = cl.post(url, json={**base, "grant_kind": "gift", "note": "hediye test",
                           "totp_code": now_code()})
    check("doğru kod → 200", r.status_code == 200, r.text[:100])
    with SessionLocal() as db:
        u = db.get(User, ids["c1"])
        check("hediye → platform=gift · aktif",
              u.subscription_platform == "gift" and u.subscription_status == "active",
              f"{u.subscription_platform} {u.subscription_status}")
        h = (db.query(PlanChangeHistory)
             .filter(PlanChangeHistory.owner_id == ids["c1"])
             .order_by(PlanChangeHistory.id.desc()).first())
        check("plan geçmişi [Hediye] etiketli", h is not None and "[Hediye]" in (h.note or ""),
              h.note if h else None)

    print("== 3. ayrı kanal bildirimi")
    check("e-posta gönderildi (admin_manual_activation)",
          any(t == "admin_manual_activation" for _, t in sent_mail), str(sent_mail))
    check("süper admine push", ids["a"] in pushes, str(pushes))

    print("== 4b. gelir ayrımı")
    with SessionLocal() as db:
        before = mrr_owner_aware(db, segment="user")["user_mrr_try"]
    # Aynı TOTP kodu aynı 30 sn penceresinde tekrar kabul edilebilir; sorun değil.
    r = cl.post(f"/api/v2/admin/users/{ids['c2']}/activate-plan",
                json={"plan": "solo_pro", "cycle": "monthly", "grant_kind": "payment",
                      "note": "dekont 123", "totp_code": now_code()})
    with SessionLocal() as db:
        after = mrr_owner_aware(db, segment="user")["user_mrr_try"]
        u2 = db.get(User, ids["c2"])
        plat2 = u2.subscription_platform
    check("ödeme türü → platform=manual · MRR'ye katıldı (2.500 artış); hediye katılmadı",
          r.status_code == 200 and plat2 == "manual" and after - before == 2500,
          f"{r.status_code} {plat2} {before}->{after}")

    print("== 5b. alarm + bütünlük")
    with SessionLocal() as db:
        gifts = notify_mod.gift_activation_count(db)
        check("hediye sayacı ≥1 ve alarm değerlendiricisi aynı sayıyı verir",
              gifts >= 1 and alarm_engine.EVALUATORS["manual_gift_burst"](db) == gifts, str(gifts))
        rep = data_integrity.orphan_scan(db)
        f = [x for x in rep["findings"] if x["kind"] == "manual_paid_plans"]
        uids = {s["user_id"] for s in (f[0]["samples"] if f else [])}
        check("bütünlük paneli: elle açılan paketler listede",
              bool(f) and {ids["c1"], ids["c2"]} <= uids, str(f)[:160])
finally:
    settings.super_admin_require_2fa = orig_flag
    email_service.send_email, push_notifications.safe_push = orig_send, orig_push
    with SessionLocal() as db:
        u = list(ids.values())
        db.query(PlanChangeHistory).filter(PlanChangeHistory.owner_id.in_(u)).delete(
            synchronize_session=False)
        db.query(AuditLog).filter(
            (AuditLog.actor_id.in_(u)) | (AuditLog.target_id.in_(u))).delete(
            synchronize_session=False)
        db.query(TotpBackupCode).filter(TotpBackupCode.user_id.in_(u)).delete(
            synchronize_session=False)
        db.query(User).filter(User.id.in_(u)).delete(synchronize_session=False)
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete()
        db.commit()

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
