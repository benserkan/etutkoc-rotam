"""Kopuk-cron düzeltmeleri smoke — health_snapshot_daily + offers_expire.

Senaryolar:
   1. KOPUK cron kalmadı: JOB_REGISTRY == CronSchedule job_key kümesi
   2. health_snapshot_daily çalışır → bugünün HealthScoreSnapshot'ları oluşur
   3. health_snapshot_daily idempotent (ikinci koşu bugün için satır artırmaz)
   4. offers_expire çalışır → dict döner (expired sayısı)
   5. cron_runner force tick ikisini de çalıştırır (success)

NOT: health_snapshot bugünün gerçek snapshot'larını yazar (upsert, idempotent) —
bu istenen "yakalama" etkisidir; temizlenmez.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import date, datetime, timezone

from sqlalchemy import func

from app.database import SessionLocal
from app.models import CronSchedule, HealthScoreSnapshot
from app.services.cron_jobs import JOB_REGISTRY, health_snapshot_daily, offers_expire

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


def main() -> int:
    print("\n=== Kopuk-cron düzeltmeleri smoke ===\n")
    now = datetime.now(timezone.utc)
    today = date.today()

    # 1. kopuk cron kalmadı
    with SessionLocal() as db:
        sched = {r.job_key for r in db.query(CronSchedule).all()}
    reg = set(JOB_REGISTRY)
    check("1. KOPUK cron yok (registry == schedule)", reg == sched,
          f"reg-sched={sorted(reg - sched)} sched-reg={sorted(sched - reg)}")

    # 2. health_snapshot_daily çalışır + bugünün snapshot'ları
    with SessionLocal() as db:
        res = health_snapshot_daily(db, now=now)
    with SessionLocal() as db:
        n_today = db.query(func.count(HealthScoreSnapshot.id)).filter(
            HealthScoreSnapshot.snapshot_date == today).scalar()
    check("2. health_snapshot_daily → bugünün snapshot'ları oluştu",
          isinstance(res, dict) and n_today > 0, f"res={res} bugün_satır={n_today}")

    # 3. idempotent
    with SessionLocal() as db:
        health_snapshot_daily(db, now=now)
    with SessionLocal() as db:
        n_today2 = db.query(func.count(HealthScoreSnapshot.id)).filter(
            HealthScoreSnapshot.snapshot_date == today).scalar()
    check("3. health_snapshot_daily idempotent (satır artmadı)", n_today2 == n_today,
          f"ilk={n_today} ikinci={n_today2}")

    # 4. offers_expire çalışır
    with SessionLocal() as db:
        ores = offers_expire(db, now=now)
    check("4. offers_expire → dict döner", isinstance(ores, dict), f"{ores}")

    # 5. cron_runner force tick ikisini de kapsar
    from app.services.cron_runner import tick
    with SessionLocal() as db:
        results = tick(db, now=now, force=True)
    both = "health_snapshot_daily" in results and "offers_expire" in results
    no_fail = all("error" not in (v or {}) for k, v in results.items()
                  if k in ("health_snapshot_daily", "offers_expire"))
    check("5. force tick ikisini de çalıştırır (hatasız)", both and no_fail,
          f"keys={sorted(results)[:6]}…")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
