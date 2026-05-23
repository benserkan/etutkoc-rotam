"""Paket yükseltmede pasif öğrencilerin OTOMATİK aktifleşmesi — çok koçlu sağlam test.

Senaryolar (her biri ayrı koç):
   A — Self-serve yükseltme (ücretsiz → solo_pro):
       8 öğr, 5'i pasif (paywall'da arşivlenmiş) → /teacher/plan/upgrade
       → 8 öğrencinin TAMAMI aktif + paywall kalkar + program yayınlanabilir.
   B — Admin aktivasyon (ücretsiz → solo_elite):
       6 öğr, 4'ü pasif → /admin/users/{id}/activate-plan
       → 6 öğrencinin TAMAMI aktif.
   C — past_due yenileme (AYNI plan, solo_pro):
       5 öğr, 2'si pasif, subscription_status=past_due → admin activate-plan solo_pro
       → change_plan erken-return olsa bile 5 öğrencinin TAMAMI aktif.
   D — KONTROL (aktif-ücretli koç, kasıtlı arşiv KORUNUR):
       solo_pro + active, 4 öğr, 1'i kasıtlı pasif → solo_elite'e yükselt
       → kasıtlı pasif öğrenci PASİF KALIR (3 aktif), yanlış geri-açma YOK.
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
from app.models import User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"react_{secrets.token_hex(3)}"
PWD = hash_password("ReactTest!23")
PWDH = "ReactTest!23"
now = datetime.now(timezone.utc)

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _mk_coach(db, suffix, plan, *, sub_status=None):
    u = User(
        email=f"{PFX}_{suffix.lower()}@test.invalid", password_hash=PWD,
        full_name=f"{PFX} {suffix}", role=UserRole.TEACHER, institution_id=None,
        is_active=True, plan=plan, trial_ends_at=None, post_trial_plan="solo_free",
        subscription_status=sub_status,
        password_changed_at=now, must_change_password=False)
    db.add(u); db.flush()
    return u


def _mk_students(db, coach, total, passive):
    """total öğrenci; ilk `passive` tanesi is_active=False."""
    for i in range(total):
        s = User(
            email=f"{PFX}_{coach.id}_s{i}@test.invalid", password_hash=PWD,
            full_name=f"{PFX} Öğr {coach.id}-{i}", role=UserRole.STUDENT,
            teacher_id=coach.id, institution_id=None, grade_level=8,
            is_active=(i >= passive),
            password_changed_at=now, must_change_password=False)
        db.add(s)
    db.flush()


def _active_count(coach_id):
    with SessionLocal() as db:
        return db.query(User).filter(
            User.teacher_id == coach_id, User.role == UserRole.STUDENT,
            User.is_active.is_(True)).count()


def _total_count(coach_id):
    with SessionLocal() as db:
        return db.query(User).filter(
            User.teacher_id == coach_id, User.role == UserRole.STUDENT).count()


def _paywall(coach_id):
    from app.services import plans
    with SessionLocal() as db:
        return plans.solo_trial_status(db, user=db.get(User, coach_id))["paywall"]


def login(suffix):
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{suffix.lower()}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text}")
    return c


def setup():
    with SessionLocal() as db:
        a = _mk_coach(db, "A", "solo_free")
        b = _mk_coach(db, "B", "solo_free")
        c = _mk_coach(db, "C", "solo_pro", sub_status="past_due")
        d = _mk_coach(db, "D", "solo_pro", sub_status="active")
        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash=PWD,
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN, institution_id=None,
            is_active=True, password_changed_at=now, must_change_password=False)
        db.add(admin); db.flush()
        ctx.update(A=a.id, B=b.id, C=c.id, D=d.id, admin=admin.id)
        _mk_students(db, a, 8, 4)   # 4 aktif (>3 → paywall) / 4 pasif
        _mk_students(db, b, 6, 4)   # 2 aktif / 4 pasif
        _mk_students(db, c, 5, 2)   # 3 aktif / 2 pasif (past_due → paywall)
        _mk_students(db, d, 4, 1)   # 3 aktif / 1 KASITLI pasif
        db.commit()


def main() -> int:
    print(f"\n=== YÜKSELTMEDE PASİF ÖĞRENCİ GERİ-AKTİFLEŞME — {PFX} ===\n")
    get_login_limiter().reset()
    setup()
    try:
        # ── A — Self-serve yükseltme (ücretsiz → solo_pro) ──
        print("A — Self-serve yükseltme (ücretsiz → solo_pro):")
        check("A0 başlangıç: 4 aktif / 8 toplam + paywall=True",
              _active_count(ctx["A"]) == 4 and _total_count(ctx["A"]) == 8 and _paywall(ctx["A"]) is True,
              f"aktif={_active_count(ctx['A'])} paywall={_paywall(ctx['A'])}")
        ca = login("A")
        r = ca.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_pro"})
        check("A1 upgrade → 200", r.status_code == 200, f"status={r.status_code} {r.text[:140]}")
        check("A2 TÜM öğrenciler aktifleşti (8/8)", _active_count(ctx["A"]) == 8, f"aktif={_active_count(ctx['A'])}")
        check("A3 paywall kalktı (False)", _paywall(ctx["A"]) is False, f"paywall={_paywall(ctx['A'])}")
        # program yayınlama artık serbest
        with SessionLocal() as db:
            sid = db.query(User.id).filter(User.teacher_id == ctx["A"], User.role == UserRole.STUDENT).first()[0]
        from datetime import date as _date
        r = ca.post(f"/api/v2/teacher/students/{sid}/publish-day", json={"task_date": _date.today().isoformat()})
        check("A4 publish-day → 200 (koçluk yeniden aktif)", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

        # ── B — Admin aktivasyon (ücretsiz → solo_elite) ──
        print("\nB — Admin aktivasyon (ücretsiz → solo_elite):")
        check("B0 başlangıç: 2 aktif / 6 toplam", _active_count(ctx["B"]) == 2 and _total_count(ctx["B"]) == 6,
              f"aktif={_active_count(ctx['B'])}")
        adm = login("admin")
        r = adm.post(f"/api/v2/admin/users/{ctx['B']}/activate-plan", json={"plan": "solo_elite", "cycle": "monthly"})
        check("B1 admin activate-plan → 200", r.status_code == 200, f"status={r.status_code} {r.text[:140]}")
        check("B2 TÜM öğrenciler aktifleşti (6/6)", _active_count(ctx["B"]) == 6, f"aktif={_active_count(ctx['B'])}")

        # ── C — past_due yenileme (AYNI plan solo_pro) ──
        print("\nC — past_due yenileme (aynı plan, change_plan erken-return):")
        check("C0 başlangıç: 3 aktif / 5 toplam + paywall=True (past_due)",
              _active_count(ctx["C"]) == 3 and _total_count(ctx["C"]) == 5 and _paywall(ctx["C"]) is True,
              f"aktif={_active_count(ctx['C'])} paywall={_paywall(ctx['C'])}")
        r = adm.post(f"/api/v2/admin/users/{ctx['C']}/activate-plan", json={"plan": "solo_pro", "cycle": "monthly"})
        check("C1 admin activate-plan (aynı plan) → 200", r.status_code == 200, f"status={r.status_code} {r.text[:140]}")
        check("C2 TÜM öğrenciler aktifleşti (5/5) — erken-return'e rağmen", _active_count(ctx["C"]) == 5,
              f"aktif={_active_count(ctx['C'])}")
        check("C3 paywall kalktı (False)", _paywall(ctx["C"]) is False, f"paywall={_paywall(ctx['C'])}")

        # ── D — KONTROL: aktif-ücretli koç, kasıtlı arşiv KORUNUR ──
        print("\nD — KONTROL (aktif solo_pro → solo_elite, kasıtlı arşiv korunmalı):")
        check("D0 başlangıç: 3 aktif / 4 toplam (1 kasıtlı pasif)",
              _active_count(ctx["D"]) == 3 and _total_count(ctx["D"]) == 4, f"aktif={_active_count(ctx['D'])}")
        cd = login("D")
        r = cd.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_elite"})
        check("D1 upgrade → 200", r.status_code == 200, f"status={r.status_code} {r.text[:140]}")
        check("D2 kasıtlı pasif KORUNDU (hâlâ 3 aktif, geri-açılmadı)", _active_count(ctx["D"]) == 3,
              f"aktif={_active_count(ctx['D'])} (yanlış geri-açma!)")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
