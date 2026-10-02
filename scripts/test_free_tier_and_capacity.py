"""Plan akışı düzeltmeleri — 2026-10-02 regresyon testi.

Kapsam:
  K1  Kayıt geçmişi: "— → 14 gün deneme (seçilen paket: Patika) · kayıt"
  K2  Ücretsiz deneme kişi başına bir kez (aynı cihaz / telefon / e-posta)
  K3  Ücretsiz paket kişi başına bir hesap: ilişkili hesapta öğrenci varsa
      yeni öğrenci eklenemez (403 free_tier_duplicate_account); ücretli serbest
  K4  Ücretli paket kapasitesi aşıldı → uyarı + kısıtlama + yükseltme teklifi
  K5  Ödeme: öğrenci sayısına yetmeyen paket satın alınamaz
  K6  Ödeme sonrası geri açılan öğrenci sayısı paket kapasitesiyle sınırlı
  K7  Ticari 360: görünen adlar, seçilen paket, ilişkili hesaplar, "Yeni üye"

Gerçek iyzico çağrısı YAPILMAZ (SDK mock).
"""
from __future__ import annotations

import sys
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
from app.models import (
    ActiveSession, AuditAction, AuditLog, PaymentTransaction, PlanChangeHistory,
    User, UserRole,
)
from app.models.coach_device import CoachDeviceLink
from app.models.suspicious_ip import SuspiciousIp
from app.services import iyzico_service
from app.services import free_tier_guard as ftg
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"ftg{secrets.token_hex(3)}"
PWD = "FreeTier1!@#xyz"
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


def _mock_create(req: dict) -> dict:
    return {"status": "success", "conversationId": req.get("conversationId", "x"),
            "token": f"mock-{secrets.token_hex(8)}",
            "paymentPageUrl": "https://sandbox-cpp.iyzipay.com?token=mock"}


def _mock_retrieve(token: str) -> dict:
    return {"status": "success", "paymentStatus": "SUCCESS", "token": token,
            "conversationId": "x", "paymentId": "1"}


def _reset_ip_guards():
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(AuditLog).where(
            AuditLog.action == AuditAction.USER_CREATE,
            AuditLog.ip_address == "testclient",
            AuditLog.details_json.like('%"self_signup": true%'),
        ))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _signup(client: TestClient, email: str, **extra):
    _reset_ip_guards()
    body = {"full_name": f"{PFX} Koç", "email": email, "password": PWD,
            "password_confirm": PWD, "accept_terms": True}
    body.update(extra)
    return client.post("/api/v2/auth/signup/teacher", json=body)


def _user(email: str) -> User:
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        db.expunge(u)
        return u


def _set(email: str, **kw):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        for k, v in kw.items():
            setattr(u, k, v)
        db.commit()


def _add_students(email: str, n: int, *, active: bool = True) -> list[int]:
    now = datetime.now(timezone.utc)
    ids = []
    with SessionLocal() as db:
        coach = db.query(User).filter(User.email == email).one()
        for _ in range(n):
            s = User(email=f"{PFX}_s{secrets.token_hex(4)}@test.invalid",
                     password_hash="x", full_name=f"{PFX} Öğr", role=UserRole.STUDENT,
                     is_active=active, grade_level=8, teacher_id=coach.id,
                     password_changed_at=now, must_change_password=False)
            db.add(s)
            db.flush()
            ids.append(s.id)
        db.commit()
    return ids


def _new_student(client: TestClient):
    return client.post("/api/v2/teacher/students", json={
        "full_name": f"{PFX} Yeni", "email": f"{PFX}_n{secrets.token_hex(4)}@test.invalid",
        "grade_level": 8,
    })


def _activate_paid(email: str, plan: str):
    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).one()
        u.plan = plan
        u.trial_ends_at = None
        u.subscription_status = "active"
        u.subscription_cycle = "monthly"
        u.subscription_period_end = datetime.now(timezone.utc) + timedelta(days=20)
        u.subscription_platform = "iyzico"
        db.commit()


def main() -> int:
    print(f"\n=== ÜCRETSİZ PAKET TEKİLLİĞİ + KAPASİTE — {PFX} ===\n")
    orig_c, orig_r = iyzico_service._iyzico_call_create, iyzico_service._iyzico_call_retrieve
    orig_avail = iyzico_service.is_provider_available
    iyzico_service._iyzico_call_create = _mock_create
    iyzico_service._iyzico_call_retrieve = _mock_retrieve
    iyzico_service.is_provider_available = lambda: True

    A = f"{PFX}.ana@gmail.com"
    try:
        # ── K1: kayıt geçmişi ──
        ca = TestClient(app)
        r = _signup(ca, A, intended_plan="solo_pro")
        check("K1a. kayıt → 200", r.status_code == 200, r.text[:150])
        ua = _user(A)
        check("K1b. plan=solo_trial, deneme reddi yok",
              ua.plan == "solo_trial" and ua.trial_denied_reason is None,
              f"{ua.plan} {ua.trial_denied_reason}")
        with SessionLocal() as db:
            h = db.query(PlanChangeHistory).filter(
                PlanChangeHistory.owner_id == ua.id,
                PlanChangeHistory.occurred_at >= datetime.now(timezone.utc) - timedelta(minutes=10),
            ).order_by(PlanChangeHistory.id).first()
        check("K1c. ilk geçmiş kaydı: from_plan YOK (free değil)",
              h is not None and h.from_plan is None, f"from={h.from_plan if h else None}")
        check("K1d. not 'seçilen paket: Patika'",
              h is not None and "seçilen paket: Patika" in (h.note or ""), f"{h.note if h else None}")
        check("K1e. cihaz çerezi basıldı + bağ yazıldı",
              ca.cookies.get(ftg.DEVICE_COOKIE) is not None, str(dict(ca.cookies)))
        with SessionLocal() as db:
            n_links = db.query(CoachDeviceLink).filter(
                CoachDeviceLink.user_id == ua.id,
                CoachDeviceLink.last_seen_at >= datetime.now(timezone.utc) - timedelta(minutes=10),
            ).count()
        check("K1f. coach_device_links satırı", n_links == 1, f"n={n_links}")

        # ── K2: aynı cihazdan ikinci hesap → deneme yok ──
        ca.post("/api/v2/auth/logout")
        B = f"{PFX}.ikinci@test.invalid"
        r = _signup(ca, B, intended_plan="solo_pro")
        ub = _user(B)
        check("K2a. aynı cihaz → plan=solo_free + reason=device",
              r.status_code == 200 and ub.plan == "solo_free" and ub.trial_denied_reason == "device",
              f"{r.status_code} {ub.plan} {ub.trial_denied_reason}")
        check("K2b. seçilen paket ödeme ekranı için korunur", ub.post_trial_plan == "solo_pro",
              ub.post_trial_plan)
        st = ca.get("/api/v2/teacher/trial-status").json()
        check("K2c. trial-status trial_denied_reason=device", st.get("trial_denied_reason") == "device",
              str(st)[:200])

        # Gmail nokta/+etiket varyantı → e-posta kanıtı (yeni cihaz)
        C = f"{PFX}ana+deneme@gmail.com"
        cc = TestClient(app)
        r = _signup(cc, C)
        uc = _user(C)
        check("K2d. Gmail varyantı → reason=email", uc.trial_denied_reason == "email",
              f"{r.status_code} {uc.plan} {uc.trial_denied_reason}")
        # Telefon kanıtı
        _set(A, phone="905321112233")
        D = f"{PFX}.tel@test.invalid"
        cd = TestClient(app)
        r = _signup(cd, D, phone="0532 111 22 33")
        ud = _user(D)
        check("K2e. aynı telefon → reason=phone", ud.trial_denied_reason == "phone",
              f"{r.status_code} {ud.plan} {ud.trial_denied_reason}")
        # Bağımsız yeni kişi → deneme alır
        E = f"{PFX}.bagimsiz@test.invalid"
        ce = TestClient(app)
        _signup(ce, E)
        check("K2f. ilişkisiz kişi → deneme verilir", _user(E).plan == "solo_trial", _user(E).plan)

        # ── K3: ücretsiz paket kişi başına bir hesap ──
        _add_students(A, 2)                       # ana hesap (deneme) 2 aktif öğrenci
        r = _new_student(ca)                       # ca şu an B ile girişli (solo_free)
        check("K3a. ilişkili hesapta öğrenci var → 403 free_tier_duplicate_account",
              r.status_code == 403 and r.json().get("detail", {}).get("code") == "free_tier_duplicate_account",
              f"{r.status_code} {r.text[:200]}")
        check("K3b. mesaj maskeli e-postayı + çözümü söyler",
              "***@" in r.text and "paket" in r.text, r.text[:200])
        _activate_paid(B, "solo_pro")              # B paket alırsa serbest
        r = _new_student(ca)
        check("K3c. ücretli pakette kural yok → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
        r = _new_student(ce)                       # ilişkisiz deneme koçu serbest
        check("K3d. ilişkisiz koç → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")

        # ── K4: ücretli paket kapasitesi aşımı ──
        _add_students(B, 11)                       # B: 1 (K3c) + 11 = 12 aktif, Patika=10
        st = ca.get("/api/v2/teacher/trial-status").json()
        check("K4a. capacity_exceeded + paywall", st.get("capacity_exceeded") and st.get("paywall"),
              str(st)[:250])
        check("K4b. öneri Rota (12 öğrenci)", st.get("recommended_plan") == "solo_elite"
              and st.get("recommended_label") == "Rota", f"{st.get('recommended_plan')}")
        r = _new_student(ca)
        d = r.json().get("detail", {})
        check("K4c. kısıtlama: yeni öğrenci 403 paywall_active",
              r.status_code == 403 and d.get("code") == "paywall_active", f"{r.status_code} {r.text[:200]}")
        check("K4d. mesaj '12 aktif öğrencin var' + 'Rota'",
              "12 aktif öğrencin var" in d.get("message", "") and "Rota" in d.get("message", ""),
              d.get("message"))
        check("K4e. tek tık teklif linki ?plan=solo_elite&checkout=1",
              (d.get("details") or {}).get("upgrade_url") == "/teacher/plan?plan=solo_elite&checkout=1",
              str(d.get("details")))

        # ── K5: yetmeyen paket ödenemez, yeten paket ödenir ──
        r = ca.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("K5a. 12 öğrenciyle Patika → 400 plan_capacity_insufficient",
              r.status_code == 400 and "plan_capacity_insufficient" in r.text and "Rota" in r.text,
              f"{r.status_code} {r.text[:200]}")
        r = ca.post("/api/v2/payment/init", json={"plan_code": "solo_elite", "cycle": "monthly"})
        check("K5b. Rota → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
        tx_id = r.json().get("transaction_id")
        with SessionLocal() as db:
            token = db.get(PaymentTransaction, tx_id).provider_reference
        TestClient(app).post("/api/v2/payment/iyzico/callback", data={"token": token},
                             follow_redirects=False)
        ub = _user(B)
        check("K5c. ödeme → plan=solo_elite", ub.plan == "solo_elite", ub.plan)
        st = ca.get("/api/v2/teacher/trial-status").json()
        check("K5d. kısıtlama kalktı", not st.get("paywall") and not st.get("capacity_exceeded"),
              str(st)[:200])

        # ── K6: geri açılan öğrenci kapasiteyle sınırlı ──
        F = f"{PFX}.kapasite@test.invalid"
        cf = TestClient(app)
        _signup(cf, F)
        _set(F, plan="solo_free", trial_ends_at=None)
        _add_students(F, 3)
        _add_students(F, 12, active=False)         # 3 aktif + 12 pasif
        r = cf.post("/api/v2/payment/init", json={"plan_code": "solo_pro", "cycle": "monthly"})
        check("K6a. 3 aktif öğrenciyle Patika ödemesi başlar", r.status_code == 200, r.text[:150])
        with SessionLocal() as db:
            token = db.get(PaymentTransaction, r.json()["transaction_id"]).provider_reference
        TestClient(app).post("/api/v2/payment/iyzico/callback", data={"token": token},
                             follow_redirects=False)
        with SessionLocal() as db:
            uf = db.query(User).filter(User.email == F).one()
            act = db.query(User).filter(User.teacher_id == uf.id, User.is_active.is_(True)).count()
            pas = db.query(User).filter(User.teacher_id == uf.id, User.is_active.is_(False)).count()
        check("K6b. yalnız 7 öğrenci geri açıldı (10 aktif, 5 pasif)", act == 10 and pas == 5,
              f"aktif={act} pasif={pas}")
        st = cf.get("/api/v2/teacher/trial-status").json()
        check("K6c. kapasite aşılmadı → kısıtlama yok", not st.get("paywall"), str(st)[:150])

        # ── K7: ticari 360 ──
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            adm = User(email=f"{PFX}_adm@test.invalid", password_hash=hash_password(PWD),
                       full_name="Adm", role=UserRole.SUPER_ADMIN, is_active=True,
                       password_changed_at=now, must_change_password=False)
            db.add(adm)
            db.commit()
        cadm = TestClient(app)
        _reset_ip_guards()
        cadm.post("/api/v2/auth/login", json={"email": f"{PFX}_adm@test.invalid", "password": PWD})
        uid = _user(A).id
        r = cadm.get(f"/api/v2/admin/revenue/users/{uid}")
        j = r.json() if r.status_code == 200 else {}
        o = j.get("owner", {})
        check("K7a. 360 → 200", r.status_code == 200, r.text[:150])
        check("K7b. plan_label=14 Gün Ücretsiz Deneme + seçilen paket Patika",
              o.get("plan_label") == "14 Gün Ücretsiz Deneme" and o.get("intended_plan_label") == "Patika",
              str(o))
        pc = (j.get("plan_changes") or [{}])[0]  # en yeni önce
        check("K7c. geçmiş: from yok, to '14 Gün Ücretsiz Deneme', neden 'kayıt'",
              pc.get("from_plan") is None and pc.get("to_plan_label") == "14 Gün Ücretsiz Deneme"
              and pc.get("reason_label") == "kayıt", str(pc))
        rel = j.get("related_accounts") or []
        check("K7d. ilişkili hesaplar listelenir (cihaz/telefon/e-posta)",
              {x["reason"] for x in rel} >= {"device", "email", "phone"}, str(rel)[:250])
        check("K7e. yeni hesap sağlık bandı 'Yeni üye'",
              (j.get("health_v2") or {}).get("band") == "new_member"
              and (j.get("health_v2") or {}).get("band_label") == "Yeni üye",
              str(j.get("health_v2"))[:150])
    finally:
        iyzico_service._iyzico_call_create = orig_c
        iyzico_service._iyzico_call_retrieve = orig_r
        iyzico_service.is_provider_available = orig_avail
        with SessionLocal() as db:
            ids = [i for (i,) in db.query(User.id).filter(User.email.like(f"%{PFX}%")).all()]
            if ids:
                db.execute(sa_delete(CoachDeviceLink).where(CoachDeviceLink.user_id.in_(ids)))
                db.execute(sa_delete(PlanChangeHistory).where(PlanChangeHistory.owner_id.in_(ids)))
                db.execute(sa_delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(ids)))
                db.execute(sa_delete(ActiveSession).where(ActiveSession.user_id.in_(ids)))
                db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
                db.execute(sa_delete(User).where(User.teacher_id.in_(ids)))
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.commit()
        _reset_ip_guards()

    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
