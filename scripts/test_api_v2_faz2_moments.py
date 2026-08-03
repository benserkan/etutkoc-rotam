# -*- coding: utf-8 -*-
"""Faz 2C+2D — bağlamsal yükseltme anı + deneme değer sayacı.

2C: solo koç kapasitesi doluyken öğrenci ekleme → 422 plan_quota_exceeded
    detayı SİHİRBAZ-TARZI öneri yükü taşır (önerilen paket + fiyat + kredi).
2D: aktif denemedeki koçun /trial-status yanıtı trial_value sayaçlarını
    (karne/veli/etiket + toplam kredi) taşır; kullanım yoksa alan null.
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
from app.models import SuspiciousIp, UsageEvent, User, UserRole
from app.models.usage import UsageKind, UsageOwnerType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"faz2m{secrets.token_hex(3)}"
PASSWORD = "Faz2Moment!26"
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


def main() -> int:
    print(f"\n=== Faz 2C+2D smoke — {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: dict = {}
    with SessionLocal() as db:
        # 2C: solo_pro (10 kapasite) koç + 10 aktif öğrenci
        full = User(email=f"{PFX}-full@t.invalid", password_hash=hash_password(PASSWORD),
                    full_name="Dolu Koç", role=UserRole.TEACHER, is_active=True,
                    plan="solo_pro", subscription_status="active",
                    must_change_password=False)
        # 2D: aktif denemede koç
        trial = User(email=f"{PFX}-tr@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Deneme Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_trial", trial_ends_at=now + timedelta(days=7),
                     must_change_password=False)
        db.add_all([full, trial])
        db.flush()
        for i in range(10):
            s = User(email=f"{PFX}-s{i}@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name=f"Öğr {i}", role=UserRole.STUDENT, is_active=True,
                     grade_level=8, teacher_id=full.id, must_change_password=False)
            db.add(s)
        db.commit()
        ids = {"full": full.id, "trial": trial.id}
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.actor_user_id.in_(list(ids.values()))))
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.owner_id.in_(list(ids.values())),
            UsageEvent.owner_type == UsageOwnerType.USER))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        cf = TestClient(app)
        cf.post("/api/v2/auth/login", json={"email": f"{PFX}-full@t.invalid", "password": PASSWORD})
        ct = TestClient(app)
        ct.post("/api/v2/auth/login", json={"email": f"{PFX}-tr@t.invalid", "password": PASSWORD})

        print("1) 2C — kapasite dolu: 422 + sihirbaz-tarzı öneri yükü")
        r = cf.post("/api/v2/teacher/students", json={
            "full_name": "On Birinci Öğrenci", "email": f"{PFX}-s11@t.invalid",
            "grade_level": 8})
        d = r.json().get("detail", {})
        det = d.get("details", {})
        check("11. öğrenci → 422 plan_quota_exceeded",
              r.status_code == 422 and d.get("code") == "plan_quota_exceeded",
              r.text[:150])
        check("öneri: Rota (solo_elite)",
              det.get("recommended_plan") == "solo_elite"
              and det.get("recommended_label") == "Rota", str(det))
        check("öneri: fiyat + kapasite + kredi",
              det.get("recommended_monthly") == 5000
              and det.get("recommended_students") == 25
              and det.get("recommended_credits") == 4000, str(det))
        check("mevcut durum: 10/10 + plan etiketi",
              det.get("current") == 10 and det.get("limit") == 10
              and det.get("current_plan_label"), str(det))

        print("\n2) 2D — deneme değer sayacı")
        r = ct.get("/api/v2/teacher/trial-status")
        j = r.json()
        check("kullanım yokken trial_value null",
              r.status_code == 200 and j.get("trial_active") is True
              and j.get("trial_value") is None, r.text[:150])

        with SessionLocal() as db:
            period = now.strftime("%Y-%m")
            db.add_all([
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["trial"],
                           kind=UsageKind.AI_EXAM_IMPORT, credits=6,
                           period_year_month=period, actor_user_id=ids["trial"]),
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["trial"],
                           kind=UsageKind.AI_PARENT_COMMENTARY, credits=6,
                           period_year_month=period, actor_user_id=ids["trial"]),
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["trial"],
                           kind=UsageKind.AI_PARENT_CHAT, credits=3,
                           period_year_month=period, actor_user_id=ids["trial"]),
                UsageEvent(owner_type=UsageOwnerType.USER, owner_id=ids["trial"],
                           kind=UsageKind.AI_WRONG_TAG, credits=2,
                           period_year_month=period, actor_user_id=ids["trial"]),
            ])
            db.commit()
        r = ct.get("/api/v2/teacher/trial-status")
        tv = r.json().get("trial_value") or {}
        check("sayaçlar dolu: 1 karne · 2 veli · 1 etiket · 17 kredi",
              tv.get("karne") == 1 and tv.get("veli") == 2
              and tv.get("etiket") == 1 and tv.get("toplam_kredi") == 17, str(tv))

        print("\n3) 2C — dolu-olmayan koçta öneri yükü tetiklenmez (normal akış)")
        r = ct.post("/api/v2/teacher/students", json={
            "full_name": "Deneme Öğrencisi", "email": f"{PFX}-ts1@t.invalid",
            "grade_level": 8})
        check("deneme koçu öğrenci ekleyebilir (deneme sınırsız)",
              r.status_code == 200, r.text[:150])
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(UsageEvent).where(
                UsageEvent.owner_id.in_(list(ids.values())),
                UsageEvent.owner_type == UsageOwnerType.USER))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f_ in failed:
        print("  FAIL:", f_)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
