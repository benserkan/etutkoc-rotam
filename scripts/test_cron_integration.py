"""Katman 11.J — Cron entegrasyonu smoke test.

Senaryolar:
  1) 5 yeni cron schedule seed edildi
  2) JOB_REGISTRY tüm yeni job_key'leri içeriyor
  3) is_due interval_minutes mantığı:
     a) last_run_at NULL → due
     b) last_run_at çok yakın → due değil
     c) last_run_at + interval geçtiyse → due
  4) is_due klasik mod hâlâ çalışıyor (interval_minutes NULL)
  5) Job çağrılabilir — security_alarm_evaluate dict döner
  6) Job çağrılabilir — abuse_scan dict döner
  7) Job çağrılabilir — error_event_retention dict döner
  8) Job çağrılabilir — slow_request_retention dict döner
  9) Job çağrılabilir — security_integrity_scan dict döner
 10) tick(db, force=True) — yeni job'lar tetiklenir + last_run_at güncellenir
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import CronSchedule, ErrorEvent, SlowRequestLog
from app.services.cron_jobs import (
    JOB_REGISTRY,
    abuse_scan,
    error_event_retention,
    security_alarm_evaluate,
    security_integrity_scan,
    slow_request_retention,
)
from app.services.cron_runner import is_due, tick


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


def main() -> int:
    print("=== Katman 11.J (Cron entegrasyonu) smoke ===")

    NEW_KEYS = [
        "security_alarm_evaluate",
        "abuse_scan",
        "error_event_retention",
        "slow_request_retention",
        "security_integrity_scan",
    ]

    # ---- 1) Seed schedule'lar var ----
    with SessionLocal() as db:
        for key in NEW_KEYS:
            row = db.query(CronSchedule).filter(CronSchedule.job_key == key).first()
            check(f"seed: '{key}' kaydı var", row is not None)
            if key == "security_alarm_evaluate" and row:
                check(f"'{key}' interval=5 dk",
                      row.interval_minutes == 5,
                      f"got {row.interval_minutes}")
            elif key == "abuse_scan" and row:
                check(f"'{key}' interval=60 dk",
                      row.interval_minutes == 60)
            elif key in ("error_event_retention", "slow_request_retention",
                         "security_integrity_scan") and row:
                check(f"'{key}' interval NULL (klasik HH:MM mod)",
                      row.interval_minutes is None)

    # ---- 2) JOB_REGISTRY ----
    for key in NEW_KEYS:
        check(f"JOB_REGISTRY['{key}'] callable",
              callable(JOB_REGISTRY.get(key)))

    # ---- 3) is_due interval mantığı ----
    now = datetime.now(timezone.utc)

    # 3a) last_run_at NULL → due
    sch = CronSchedule(
        job_key="test_interval", description="test",
        hour=0, minute=0, day_of_week=None,
        interval_minutes=5, enabled=True,
        last_run_at=None,
        created_at=now, updated_at=now,
    )
    check("interval mode: last_run_at NULL → due",
          is_due(sch, now) is True)

    # 3b) last_run_at 2 dk önce (interval 5dk) → due değil
    sch.last_run_at = now - timedelta(minutes=2)
    check("interval mode: 2dk önce → değil",
          is_due(sch, now) is False)

    # 3c) last_run_at 6 dk önce (interval 5dk) → due
    sch.last_run_at = now - timedelta(minutes=6)
    check("interval mode: 6dk önce → due",
          is_due(sch, now) is True)

    # 3d) enabled=False → due değil
    sch.enabled = False
    check("disabled → due değil", is_due(sch, now) is False)
    sch.enabled = True

    # ---- 4) Klasik mod hâlâ çalışıyor ----
    sch_classic = CronSchedule(
        job_key="test_classic", description="test",
        hour=now.hour, minute=now.minute, day_of_week=None,
        interval_minutes=None, enabled=True,
        last_run_at=None,
        created_at=now, updated_at=now,
    )
    check("classic mode: HH:MM eşleşti + last_run_at NULL → due",
          is_due(sch_classic, now) is True)

    sch_future = CronSchedule(
        job_key="test_future", description="test",
        hour=(now.hour + 1) % 24, minute=0, day_of_week=None,
        interval_minutes=None, enabled=True,
        last_run_at=None,
        created_at=now, updated_at=now,
    )
    # Eğer şu an gece yarısından sonraysa, hour+1 < 24 → gelecek
    if now.hour < 23:
        check("classic mode: gelecek saat → due değil",
              is_due(sch_future, now) is False)

    # ---- 5-9) Her job çağrılabilir ----
    with SessionLocal() as db:
        r1 = security_alarm_evaluate(db, now=now)
        check("security_alarm_evaluate dict döner",
              isinstance(r1, dict) and "rules_evaluated" in r1)

        r2 = abuse_scan(db, now=now)
        check("abuse_scan dict döner",
              isinstance(r2, dict) and "detector_hits" in r2)

        r3 = error_event_retention(db, now=now)
        check("error_event_retention dict döner",
              isinstance(r3, dict) and "deleted" in r3)
        check("error_retention günsayı = 30",
              r3.get("retention_days") == 30)

        r4 = slow_request_retention(db, now=now)
        check("slow_request_retention dict döner",
              isinstance(r4, dict) and "deleted" in r4)
        check("slow_retention günsayı = 7",
              r4.get("retention_days") == 7)

        r5 = security_integrity_scan(db, now=now)
        check("security_integrity_scan dict döner",
              isinstance(r5, dict) and
              {"orphan_findings", "kvkk_overdue", "kvkk_open"} <= set(r5.keys()))

    # ---- 10) tick(force=True) yeni job'ları tetikler ----
    with SessionLocal() as db:
        # last_run_at sıfırla — daha önce tetiklenmemiş kabul et
        for key in NEW_KEYS:
            row = db.query(CronSchedule).filter(CronSchedule.job_key == key).first()
            if row:
                row.last_run_at = None
                row.last_status = None
                row.last_error = None
        db.commit()

        results = tick(db, force=True)
        # Yalnız yeni job'ları kontrol et (mevcut prod cron'lar da çalışmış olabilir)
        for key in NEW_KEYS:
            check(f"force tick: '{key}' çalıştı",
                  key in results, f"results.keys={list(results.keys())}")
            row = db.query(CronSchedule).filter(CronSchedule.job_key == key).first()
            check(f"'{key}' last_run_at güncellendi",
                  row is not None and row.last_run_at is not None)
            check(f"'{key}' last_status = success",
                  row is not None and row.last_status == "success",
                  f"got {row.last_status if row else None}, err={row.last_error if row else None}")

    # ---- Retention smoke: 35 günlük resolved ErrorEvent → silinmeli ----
    pfx = f"crj-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        old_event = ErrorEvent(
            signature=f"{pfx}-test-signature",
            endpoint=f"/test/{pfx}/retention",
            method="GET", status_code=500,
            exception_type="Test", exception_message="retention",
            count=1,
            first_seen_at=datetime.now(timezone.utc) - timedelta(days=40),
            last_seen_at=datetime.now(timezone.utc) - timedelta(days=35),
            resolved_at=datetime.now(timezone.utc) - timedelta(days=35),
        )
        db.add(old_event)
        db.commit()
        old_id = old_event.id

        result = error_event_retention(db, now=datetime.now(timezone.utc))
        db.commit()
        check("eski resolved ErrorEvent silindi",
              result["deleted"] >= 1)
    # Yeni session — identity map cache'i bypass et
    with SessionLocal() as db2:
        gone = db2.get(ErrorEvent, old_id)
        check("DB'de gerçekten yok",
              gone is None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        db.query(ErrorEvent).filter(ErrorEvent.endpoint.like(f"%{pfx}%")).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
