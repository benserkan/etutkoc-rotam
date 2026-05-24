"""CANLI Vitrin Kartları 'Şimdi tara' — gerçek çalışan sunucuya HTTP + cookie jar.

Tarayıcı yolu: süper admin login → discovery-queue sayımı → POST scan →
sayım arttı mı → sayfa render. (Next.js :3000 → rewrite → FastAPI :8081.)

Testin AÇTIĞI kesif kartları (delta) sonda silinir — DB kirlenmez.

Kullanım:  python scripts/live_discovery_scan.py [BASE_URL]
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete, or_

from app.database import SessionLocal
from app.models import AuditLog, FeatureCard, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"livedisc_{secrets.token_hex(3)}"
PWD = hash_password("LiveDisc!23")
PWDH = "LiveDisc!23"
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


def _kesif_ids() -> set[int]:
    with SessionLocal() as db:
        return {
            r[0] for r in db.query(FeatureCard.id).filter(
                or_(FeatureCard.slug.like("kesif-mig-%"), FeatureCard.slug.like("kesif-c-%"))
            ).all()
        }


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        sa = User(email=f"{PFX}_sa@test.invalid", password_hash=PWD, full_name=f"{PFX} SA",
                  role=UserRole.SUPER_ADMIN, institution_id=None, is_active=True,
                  password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add(sa); db.commit()
        ctx["sa_id"] = sa.id


def login(local) -> httpx.Client:
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=60.0, follow_redirects=False)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{local}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {local} @ {BASE}: {r.status_code} {r.text[:200]}")
    return c


def main() -> int:
    print(f"\n=== CANLI DISCOVERY 'ŞİMDİ TARA' — BASE={BASE} — {PFX} ===\n")
    setup()
    before = _kesif_ids()
    created_ids: set[int] = set()
    try:
        sa = login("sa")

        # 0. tazelik: scan ucu var mı (stale backend tespiti)
        rq = sa.get("/api/v2/admin/feature-catalog/discovery-queue")
        check("0. discovery-queue erişilebilir", rq.status_code == 200, f"{rq.status_code}")
        total_before = rq.json()["counts"]["total"] if rq.status_code == 200 else -1

        # 1. Şimdi tara
        r = sa.post("/api/v2/admin/feature-catalog/discovery-queue/scan")
        if r.status_code == 404:
            check("1. scan ucu mevcut (404 değil) — :8081 GÜNCEL", False, "404 — backend stale")
            return 1
        j = r.json().get("data", {}) if r.status_code == 200 else {}
        check("1. Şimdi tara → 200 + shape",
              r.status_code == 200 and all(k in j for k in ("created", "skipped", "candidates")),
              f"{r.status_code} {r.text[:160]}")
        print(f"     ↪ tarama: created={j.get('created')} skipped={j.get('skipped')} candidates={j.get('candidates')}")

        after = _kesif_ids()
        created_ids = after - before

        # 2. aday > 0
        check("2. aday > 0 (repo migration/commit)", j.get("candidates", 0) > 0, f"{j.get('candidates')}")

        # 3. kuyruk sayımı arttı (ilk taramaysa) veya en az aynı
        rq2 = sa.get("/api/v2/admin/feature-catalog/discovery-queue")
        total_after = rq2.json()["counts"]["total"]
        check("3. kuyruk sayımı arttı/korundu (created kadar)",
              total_after >= total_before and (j.get("created", 0) == 0 or total_after > total_before),
              f"before={total_before} after={total_after} created={j.get('created')}")

        # 4. idempotent: tekrar tara → created 0
        r = sa.post("/api/v2/admin/feature-catalog/discovery-queue/scan")
        check("4. tekrar tara idempotent → created=0", r.json()["data"]["created"] == 0, f"{r.text[:120]}")

        # 5. sayfa render
        if BASE.endswith(":3000"):
            print("\nSayfa render (Next.js :3000):")
            rr = sa.get("/admin/feature-catalog/discovery-queue", follow_redirects=True)
            check("PAGE /admin/feature-catalog/discovery-queue → 200", rr.status_code == 200, f"{rr.status_code}")

        sa.close()

    finally:
        # delta kesif kartlarını + audit'lerini sil (DB temiz kalsın)
        with SessionLocal() as db:
            if created_ids:
                db.execute(sa_delete(AuditLog).where(AuditLog.target_id.in_(created_ids),
                                                     AuditLog.target_type == "feature_card"))
                db.execute(sa_delete(FeatureCard).where(FeatureCard.id.in_(created_ids)))
            if ctx.get("sa_id"):
                db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == ctx["sa_id"]))
                db.execute(sa_delete(User).where(User.id == ctx["sa_id"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
