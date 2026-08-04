# -*- coding: utf-8 -*-
"""Faz 3 — kredi ek paketi (iyzico, devreden) + iptal-anı neden anketi.

Kritik güvence: one_time kredi ödemesi PLAN/ABONELİK alanlarına ASLA dokunmaz;
başarılı ödeme yalnız purchased_credits kovasına yazar; kova ay devrinde
kullanılmayan kısmıyla taşınır (bonus/tahsisat devretmez).
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
    ContactRequest,
    CreditAccount,
    PaymentTransaction,
    SuspiciousIp,
    UsageEvent,
    User,
    UserRole,
)
from app.models.usage import UsageOwnerType
from app.services import iyzico_service
from app.services.credits import CreditOwner, get_or_create_account
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"cpk{secrets.token_hex(3)}"
PASSWORD = "CreditPack!26"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def _mock_iyzico(monkey_target=iyzico_service):
    """SDK'yı mock'la: init success + retrieve success (gerçek çağrı YOK)."""
    def fake_create(request):
        return {
            "status": "success",
            "paymentPageUrl": "https://sandbox.test/pay",
            "token": f"tok-{secrets.token_hex(8)}",
        }

    def fake_retrieve(token):
        return {"status": "success", "paymentStatus": "SUCCESS"}

    monkey_target._iyzico_call_create = fake_create
    monkey_target._iyzico_call_retrieve = fake_retrieve


def main() -> int:
    print(f"\n=== Kredi ek paketi + iptal anketi smoke — {PFX} ===\n")
    now = datetime.now(timezone.utc)

    # SDK mock + provider available say
    orig_create = iyzico_service._iyzico_call_create
    orig_retrieve = iyzico_service._iyzico_call_retrieve
    orig_available = iyzico_service.is_provider_available
    iyzico_service.is_provider_available = lambda: True
    _mock_iyzico()

    ids: dict = {}
    with SessionLocal() as db:
        active = User(email=f"{PFX}-a@t.invalid", password_hash=hash_password(PASSWORD),
                      full_name="Aktif Koç", role=UserRole.TEACHER, is_active=True,
                      plan="solo_pro", subscription_status="active",
                      subscription_period_end=now + timedelta(days=20),
                      must_change_password=False)
        trial = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Deneme Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_trial", trial_ends_at=now + timedelta(days=7),
                     must_change_password=False)
        apple = User(email=f"{PFX}-ap@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Apple Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", subscription_status="active",
                     subscription_platform="app_store", must_change_password=False)
        db.add_all([active, trial, apple])
        db.commit()
        ids = {"active": active.id, "trial": trial.id, "apple": apple.id}
        # id-reuse kalıntıları
        db.execute(sa_delete(CreditAccount).where(
            CreditAccount.owner_type == UsageOwnerType.USER,
            CreditAccount.owner_id.in_(list(ids.values()))))
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.owner_type == UsageOwnerType.USER,
            UsageEvent.owner_id.in_(list(ids.values()))))
        db.execute(sa_delete(ContactRequest).where(
            ContactRequest.email.like(f"{PFX}-%")))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        ca = TestClient(app)
        ca.post("/api/v2/auth/login", json={"email": f"{PFX}-a@t.invalid", "password": PASSWORD})
        ct = TestClient(app)
        ct.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        cap = TestClient(app)
        cap.post("/api/v2/auth/login", json={"email": f"{PFX}-ap@t.invalid", "password": PASSWORD})

        print("1) Katalog + kapılar")
        r = ca.get("/api/v2/pricing")
        packs = r.json().get("credit_packs", [])
        check("katalogda 3 paket (500/1500/4000 — 900/2400/5500)",
              [(p["credits"], p["price"]) for p in packs]
              == [(500, 900), (1500, 2400), (4000, 5500)], str(packs))
        r = TestClient(app).post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_500"})
        check("anonim 401", r.status_code == 401, str(r.status_code))
        r = ct.post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_500"})
        check("deneme koçu 403 credit_pack_requires_subscription",
              r.status_code == 403
              and r.json()["detail"]["code"] == "credit_pack_requires_subscription",
              r.text[:120])
        r = cap.post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_500"})
        check("App Store abonesi 409", r.status_code == 409, r.text[:120])
        r = ca.post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_9999"})
        check("bilinmeyen paket 404 credit_pack_not_found",
              r.status_code == 404
              and r.json()["detail"]["code"] == "credit_pack_not_found", r.text[:120])

        print("\n2) Satın alma: init → callback → kredi yazılır, PLAN DEĞİŞMEZ")
        r = ca.post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_500"})
        j = r.json()
        check("init 200 + one_time + 900 TL",
              r.status_code == 200 and j.get("cycle") == "one_time"
              and j.get("amount") == 900.0 and j.get("plan_code") == "pack_500",
              r.text[:200])
        token = j["iyzico_token"]

        with SessionLocal() as db:
            u = db.get(User, ids["active"])
            pre = {"plan": u.plan, "status": u.subscription_status,
                   "end": u.subscription_period_end, "platform": u.subscription_platform}
            tx = iyzico_service.verify_callback(db, iyzico_token=token)
            check("callback succeeded", tx.status == "succeeded", tx.status)
            db.refresh(u)
            check("PLAN/ABONELİK ALANLARI DEĞİŞMEDİ (kritik)",
                  u.plan == pre["plan"] and u.subscription_status == pre["status"]
                  and u.subscription_period_end == pre["end"]
                  and u.subscription_platform == pre["platform"],
                  f"{u.plan}/{u.subscription_status}")
            owner = CreditOwner(type=UsageOwnerType.USER, id=ids["active"], plan_code="solo_pro")
            acc = get_or_create_account(db, owner=owner)
            check("purchased_credits = 500 + toplam tavana yansıdı",
                  acc.purchased_credits == 500
                  and acc.total_allocated == acc.allocated_credits + 500,
                  f"purch={acc.purchased_credits} total={acc.total_allocated}")
            # idempotent: aynı token ikinci kez → çifte kredi YOK
            iyzico_service.verify_callback(db, iyzico_token=token)
            db.refresh(acc)
            check("callback idempotent (çifte kredi yok)",
                  acc.purchased_credits == 500, str(acc.purchased_credits))

        print("\n3) Başarısız ödeme kredi yazmaz")
        r = ca.post("/api/v2/payment/credit-pack/init", json={"pack_code": "pack_1500"})
        token2 = r.json()["iyzico_token"]
        iyzico_service._iyzico_call_retrieve = lambda t: {
            "status": "success", "paymentStatus": "FAILURE", "errorMessage": "kart red"}
        with SessionLocal() as db:
            tx = iyzico_service.verify_callback(db, iyzico_token=token2)
            check("failed tx", tx.status == "failed", tx.status)
            owner = CreditOwner(type=UsageOwnerType.USER, id=ids["active"], plan_code="solo_pro")
            acc = get_or_create_account(db, owner=owner)
            check("kredi hâlâ 500 (başarısız ödeme yazmadı)",
                  acc.purchased_credits == 500, str(acc.purchased_credits))
        _mock_iyzico()  # geri success

        print("\n4) Ay devri: kullanılmayan satın alınan kredi taşınır")
        with SessionLocal() as db:
            owner = CreditOwner(type=UsageOwnerType.USER, id=ids["active"], plan_code="solo_pro")
            acc = get_or_create_account(db, owner=owner)
            # senaryo: tahsisat 1500 + bonus 0 + satın alınan 500; kullanım 1700
            # → taşan 200 satın alınandan yendi → devir 300
            acc.used_credits = acc.allocated_credits + 200
            db.commit()
            next_period = (now + timedelta(days=35)).strftime("%Y-%m")
            acc2 = get_or_create_account(db, owner=owner, period=next_period)
            check("devir = 500 - 200 = 300 (bonus/tahsisat devretmez)",
                  acc2.purchased_credits == 300
                  and acc2.used_credits == 0 and acc2.bonus_credits == 0,
                  f"purch={acc2.purchased_credits}")
            # zincir devri: EN YENİ dönemden okunur — acc2'de kullanım tabanın
            # altındaysa 300'ün tamamı bir sonraki aya taşınır
            acc2.used_credits = 50
            db.commit()
            next2 = (now + timedelta(days=70)).strftime("%Y-%m")
            acc3 = get_or_create_account(db, owner=owner, period=next2)
            check("zincir devri: kullanım tabanın altında → tam devir (300)",
                  acc3.purchased_credits == 300, str(acc3.purchased_credits))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.id.in_([acc2.id, acc3.id])))
            db.commit()

        print("\n5) İptal-anı neden anketi")
        r = ca.post("/api/v2/teacher/subscription/cancel",
                    json={"reason_code": "season_break", "note": "Yaz tatili"})
        check("iptal 200", r.status_code == 200, r.text[:120])
        with SessionLocal() as db:
            u = db.get(User, ids["active"])
            check("abonelik canceled", u.subscription_status == "canceled",
                  str(u.subscription_status))
            cr = (db.query(ContactRequest)
                  .filter(ContactRequest.email == f"{PFX}-a@t.invalid",
                          ContactRequest.source == "cancel_feedback")
                  .first())
            check("ContactRequest cancel_feedback + neden + koç_id",
                  cr is not None and "Dönem/sezon bitti" in (cr.message or "")
                  and f"koç_id={ids['active']}" in (cr.message or "")
                  and "Yaz tatili" in (cr.message or ""),
                  (cr.message if cr else "YOK")[:150])
            # geriye uyum: gövdesiz iptal de çalışır (resume + tekrar)
            u.subscription_status = "active"
            db.commit()
        r = ca.post("/api/v2/teacher/subscription/cancel")
        check("gövdesiz iptal (eski istemci) 200", r.status_code == 200, r.text[:120])
        with SessionLocal() as db:
            n = (db.query(ContactRequest)
                 .filter(ContactRequest.email == f"{PFX}-a@t.invalid",
                         ContactRequest.source == "cancel_feedback")
                 .count())
            check("gövdesiz iptal anket kaydı ÜRETMEZ", n == 1, str(n))
    finally:
        iyzico_service._iyzico_call_create = orig_create
        iyzico_service._iyzico_call_retrieve = orig_retrieve
        iyzico_service.is_provider_available = orig_available
        with SessionLocal() as db:
            db.execute(sa_delete(PaymentTransaction).where(
                PaymentTransaction.user_id.in_(list(ids.values()))))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_type == UsageOwnerType.USER,
                CreditAccount.owner_id.in_(list(ids.values()))))
            db.execute(sa_delete(ContactRequest).where(
                ContactRequest.email.like(f"{PFX}-%")))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f_ in failed:
        print("  FAIL:", f_)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
