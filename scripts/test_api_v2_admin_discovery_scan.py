"""API v2 — Vitrin Kartları 'Şimdi tara' (discovery scan) + cron smoke.

Senaryolar:
   1.  Anonim → 401
   2.  Teacher → 403
   3.  Süper admin tara → 200 + shape (created/skipped/candidates)
   4.  Aday > 0 (repo'da migration/commit var) + yeni kart açıldı
   5.  İkinci tarama idempotent → created=0 (hepsi zaten var)
   6.  cron fonksiyonu (feature_discovery_scan) doğrudan → created=0 + shape
   7.  cron schedule + JOB_REGISTRY eşleşiyor (kopuk cron değil)

Temizlik: testin AÇTIĞI kesif kartları (delta) + audit silinir — DB kirlenmez.
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
from sqlalchemy import delete as sa_delete, or_

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, FeatureCard, Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"discscan{secrets.token_hex(3)}"
PASSWORD = "DiscScan1!@xyz"
SA = f"{PFX}_sa@test.invalid"
TEACHER = f"{PFX}_tch@test.invalid"

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


def _kesif_ids() -> set[int]:
    with SessionLocal() as db:
        return {
            r[0] for r in db.query(FeatureCard.id).filter(
                or_(FeatureCard.slug.like("kesif-mig-%"), FeatureCard.slug.like("kesif-c-%"))
            ).all()
        }


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} K", slug=f"{PFX}-k", plan="etut_standart", is_active=True)
        db.add(inst); db.flush()
        sa = User(email=SA, password_hash=pwd, full_name="SA", role=UserRole.SUPER_ADMIN,
                  institution_id=None, is_active=True, password_changed_at=now,
                  must_change_password=False, email_verified_at=now)
        tch = User(email=TEACHER, password_hash=pwd, full_name="T", role=UserRole.TEACHER,
                   institution_id=inst.id, is_active=True, password_changed_at=now,
                   must_change_password=False, email_verified_at=now)
        db.add_all([sa, tch]); db.flush()
        out = {"inst_id": inst.id, "sa_id": sa.id, "uids": [sa.id, tch.id]}
        db.commit()
        return out


def _cleanup(seed: dict, created_ids: set[int]) -> None:
    with SessionLocal() as db:
        if created_ids:
            db.execute(sa_delete(AuditLog).where(AuditLog.target_id.in_(created_ids),
                                                 AuditLog.target_type == "feature_card"))
            db.execute(sa_delete(FeatureCard).where(FeatureCard.id.in_(created_ids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(seed["uids"])))
        db.execute(sa_delete(User).where(User.id.in_(seed["uids"])))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.commit()


def _login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login {email} {r.status_code}")
    return c


SCAN = "/api/v2/admin/feature-catalog/discovery-queue/scan"


def main() -> int:
    print(f"\n=== Discovery scan + cron smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    before = _kesif_ids()
    created_ids: set[int] = set()
    try:
        # 1. anonim
        r = TestClient(app).post(SCAN)
        check("1. Anonim → 401", r.status_code == 401, f"{r.status_code}")

        sa = _login(SA)
        tch = _login(TEACHER)

        # 2. teacher → 403
        r = tch.post(SCAN)
        check("2. Teacher → 403", r.status_code == 403, f"{r.status_code}")

        # 3. süper admin tara
        r = sa.post(SCAN)
        j = r.json().get("data", {}) if r.status_code == 200 else {}
        shape = all(k in j for k in ("created", "skipped", "candidates", "message"))
        check("3. Süper admin tara → 200 + shape", r.status_code == 200 and shape, f"{r.status_code} {r.text[:140]}")

        after = _kesif_ids()
        created_ids = after - before
        # 4. aday > 0 + kart açıldı (ilk kez taranıyorsa created>0; daha önce
        # tarandıysa created 0 olabilir ama candidates yine > 0 olmalı)
        check("4. aday > 0 (repo'da migration/commit var)", j.get("candidates", 0) > 0, f"candidates={j.get('candidates')}")

        # 5. ikinci tarama idempotent → created=0
        r = sa.post(SCAN)
        j2 = r.json()["data"]
        check("5. İkinci tarama idempotent → created=0",
              r.status_code == 200 and j2["created"] == 0 and j2["candidates"] > 0, f"{j2}")

        # 6. cron fonksiyonu doğrudan → created=0 + shape
        from app.services.cron_jobs import feature_discovery_scan
        with SessionLocal() as db:
            res = feature_discovery_scan(db, now=datetime.now(timezone.utc))
        check("6. cron feature_discovery_scan → created=0 + shape",
              res.get("created") == 0 and "candidates" in res and res["candidates"] > 0, f"{res}")

        # 7. cron schedule + JOB_REGISTRY eşleşmesi (kopuk değil)
        from app.models import CronSchedule
        from app.services.cron_jobs import JOB_REGISTRY
        with SessionLocal() as db:
            sch = db.query(CronSchedule).filter(CronSchedule.job_key == "feature_discovery_scan").first()
        check("7. cron schedule var + JOB_REGISTRY'de + enabled",
              sch is not None and sch.enabled and "feature_discovery_scan" in JOB_REGISTRY,
              f"sch={sch is not None}")

    finally:
        _cleanup(seed, created_ids)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
