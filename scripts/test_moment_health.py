# -*- coding: utf-8 -*-
"""Faz C+D — moment sağlık sistemi smoke.

Her bağlamsal uyarı için: koşulu kur → sinyal API yanıtında + MomentEvent izi
yazıldı mı; koşul yokken iz YAZILMADI mı; sessizlik taraması "koşul var +
panelde gezdi + sinyal yok" kullanıcıyı yakalıyor mu; sinyal kaydedilince
temizleniyor mu; alarm kuralı moment_silent seed'leniyor + tetikleniyor mu.
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
    AlarmRule,
    CreditAccount,
    MomentEvent,
    PanelVisitEvent,
    SuspiciousIp,
    User,
    UserRole,
)
from app.models.usage import UsageOwnerType
from app.services import moments
from app.services.alarm_engine import _ensure_builtin_rules, _val_moment_silent
from app.services.credits import CreditOwner, get_or_create_account
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"mh{secrets.token_hex(3)}"
PASSWORD = "MomentHealth!26"
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
    print(f"\n=== Moment sağlık smoke — {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: dict = {}
    with SessionLocal() as db:
        # 3 koç: kritik-deneme · sağlıklı-deneme (10 gün) · kredi-düşük aktif abone
        crit = User(email=f"{PFX}-c@t.invalid", password_hash=hash_password(PASSWORD),
                    full_name="Kritik Deneme", role=UserRole.TEACHER, is_active=True,
                    plan="solo_trial", trial_ends_at=now + timedelta(days=2),
                    last_login_at=now, must_change_password=False)
        okc = User(email=f"{PFX}-o@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name="Sağlıklı Deneme", role=UserRole.TEACHER, is_active=True,
                   plan="solo_trial", trial_ends_at=now + timedelta(days=10),
                   last_login_at=now, must_change_password=False)
        low = User(email=f"{PFX}-l@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name="Kredi Düşük", role=UserRole.TEACHER, is_active=True,
                   plan="solo_pro", subscription_status="active",
                   last_login_at=now, must_change_password=False)
        db.add_all([crit, okc, low])
        db.commit()
        ids = {"crit": crit.id, "ok": okc.id, "low": low.id}
        # id-reuse kalıntıları
        db.execute(sa_delete(MomentEvent).where(MomentEvent.user_id.in_(list(ids.values()))))
        db.execute(sa_delete(PanelVisitEvent).where(
            PanelVisitEvent.user_id.in_(list(ids.values()))))
        db.execute(sa_delete(CreditAccount).where(
            CreditAccount.owner_type == UsageOwnerType.USER,
            CreditAccount.owner_id.in_(list(ids.values()))))
        db.commit()
        # kredi-düşük: 1450/1500
        acc = get_or_create_account(db, owner=CreditOwner(
            type=UsageOwnerType.USER, id=ids["low"], plan_code="solo_pro"))
        acc.used_credits = 1450
        # low koçu /teacher/plan sayfasını ziyaret etmiş (plan_page kanıtı)
        db.add(PanelVisitEvent(user_id=ids["low"], role="teacher",
                               route_key="teacher.plan", dwell_ms=5000, source="web"))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        print("1) Sessizlik taraması — sinyal HENÜZ sunulmadı → yakalar")
        with SessionLocal() as db:
            report = {r.key: r for r in moments.silent_moment_report(db)}
            check("trial_critical: kritik koç sessiz listede",
                  ids["crit"] in report["trial_critical"].silent_user_ids,
                  str(report["trial_critical"]))
            check("trial_critical: sağlıklı koç listede DEĞİL",
                  ids["ok"] not in report["trial_critical"].silent_user_ids)
            check("credit_low: plan sayfası ziyaretli düşük-kredili koç sessiz",
                  ids["low"] in report["credit_low"].silent_user_ids,
                  str(report["credit_low"]))
            check("silent_total > 0", moments.silent_total(db) >= 2)
            check("özet metni iki momenti de sayıyor",
                  "Deneme bitiyor" in moments.silent_summary_text(db)
                  and "Kredi azaldı" in moments.silent_summary_text(db))

        print("\n2) Sinyal sunulunca iz yazılır + sessizlik temizlenir")
        cc = TestClient(app)
        cc.post("/api/v2/auth/login", json={"email": f"{PFX}-c@t.invalid", "password": PASSWORD})
        r = cc.get("/api/v2/teacher/trial-status")
        check("trial-status 200 + trial_critical sinyali",
              r.status_code == 200 and r.json().get("trial_critical") is True,
              r.text[:120])
        cl = TestClient(app)
        cl.post("/api/v2/auth/login", json={"email": f"{PFX}-l@t.invalid", "password": PASSWORD})
        r = cl.get("/api/v2/teacher/plan")
        check("plan 200 (credit_low sinyal taşıyıcı)", r.status_code == 200, r.text[:120])
        with SessionLocal() as db:
            rows = {(e.user_id, e.moment_key) for e in db.query(MomentEvent).filter(
                MomentEvent.user_id.in_(list(ids.values()))).all()}
            check("MomentEvent: kritik koça trial_critical izi",
                  (ids["crit"], "trial_critical") in rows, str(rows))
            check("MomentEvent: düşük-kredili koça credit_low izi",
                  (ids["low"], "credit_low") in rows, str(rows))
            check("sağlıklı koça iz YOK (koşul yok → kayıt yok)",
                  not any(u == ids["ok"] for u, _ in rows))
            report = {r_.key: r_.silent_user_ids for r_ in moments.silent_moment_report(db)}
            check("sessizlik temizlendi (iki koç da listeden düştü)",
                  ids["crit"] not in report["trial_critical"]
                  and ids["low"] not in report["credit_low"], str(report))

        print("\n3) Günde tek kayıt (dedup)")
        cc.get("/api/v2/teacher/trial-status")
        cc.get("/api/v2/teacher/trial-status")
        with SessionLocal() as db:
            n = db.query(MomentEvent).filter(
                MomentEvent.user_id == ids["crit"],
                MomentEvent.moment_key == "trial_critical").count()
            check("3 çağrıda 1 kayıt", n == 1, str(n))

        print("\n4) Alarm kuralı")
        with SessionLocal() as db:
            _ensure_builtin_rules(db)
            rule = db.query(AlarmRule).filter(AlarmRule.key == "moment_silent").first()
            check("moment_silent kuralı seed'lendi (eşik 0, push+in_app+email)",
                  rule is not None and rule.threshold == 0
                  and "push" in (rule.channels or ""), str(rule))
            # şu an sessiz yok → değer 0; izleri silince yeniden > 0
            check("değer fonksiyonu: sinyaller kayıtlıyken 0 DEĞİLSE bile "
                  "temizlenmiş kullanıcıları saymaz",
                  all(u not in row.silent_user_ids
                      for row in moments.silent_moment_report(db)
                      for u in (ids["crit"], ids["low"])))
            db.execute(sa_delete(MomentEvent).where(
                MomentEvent.user_id.in_(list(ids.values()))))
            db.commit()
            check("izler silinince değer fonksiyonu yeniden > 0 (kırılma tespiti)",
                  _val_moment_silent(db) >= 2, str(_val_moment_silent(db)))

        print("\n5) Panel kanıtı olmayan kullanıcı SAYILMAZ (yanlış alarm koruması)")
        with SessionLocal() as db:
            u = db.get(User, ids["crit"])
            u.last_login_at = now - timedelta(days=10)  # 48s penceresi dışı
            db.commit()
            report = {r_.key: r_.silent_user_ids for r_ in moments.silent_moment_report(db)}
            check("10 gündür girmeyen kritik koç sessiz SAYILMAZ",
                  ids["crit"] not in report["trial_critical"], str(report))
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(MomentEvent).where(
                MomentEvent.user_id.in_(list(ids.values()))))
            db.execute(sa_delete(PanelVisitEvent).where(
                PanelVisitEvent.user_id.in_(list(ids.values()))))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_type == UsageOwnerType.USER,
                CreditAccount.owner_id.in_(list(ids.values()))))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f_ in failed:
        print("  FAIL:", f_)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
