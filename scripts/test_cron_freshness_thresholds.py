"""Cron tazelik eşiği smoke (2026-07-31).

Bulgu: Bütünlük paneli TÜM cron'lara düz 25s/48s eşiği uyguluyordu. Haftalık
işler (feature_discovery_scan, drop_alert, admin_weekly_digest — Pazartesi
çalışır) Çarşamba'dan itibaren "Kritik" görünüyordu; prod'da üçü de sağlıklıyken
Cuma günü kırmızıydı. Dikkat Odası da aynı fonksiyonu kullandığı için oradan da
yanlış alarm üretiyordu.

Eşikler artık işin sıklığına göre (`system_health.cron_thresholds_hours`) ve
Bütünlük paneli ile Sistem Sağlığı sayfası AYNI kaynağı paylaşır.

Senaryolar:
  1-3. Eşikler sıklığa göre: günlük / haftalık / aralıklı
  4.   Haftalık iş 89 saat sonra OK (gerçek prod durumu — eski kodda kritikti)
  5.   Haftalık iş gerçekten 2 tur kaçırırsa kritik olur (koruma kaybolmadı)
  6.   Günlük iş 49 saat sonra kritik (mevcut davranış korunur)
  7.   Aralıklı iş saatlerce sessizse yakalanır (eskiden 25s'e kadar "ok"tu)
  8.   İki yüzey (Bütünlük + Sistem Sağlığı) aynı sonucu verir
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timedelta, timezone

from app.models import CronSchedule
from app.services.system_health import _cron_health, cron_thresholds_hours

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


def mk(*, day_of_week=None, interval_minutes=None, hours_ago: float | None = 1.0):
    s = CronSchedule(
        job_key="test", hour=3, minute=0, enabled=True,
        day_of_week=day_of_week, interval_minutes=interval_minutes,
    )
    s.last_run_at = (
        None if hours_ago is None
        else datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    )
    return s


def level(schedule) -> str:
    return _cron_health(schedule, datetime.now(timezone.utc))[1]


def main() -> int:
    print("\n=== Cron tazelik eşikleri (sıklığa duyarlı) ===\n")

    w, c = cron_thresholds_hours(mk())
    check("1. Günlük iş: 25s uyarı / 48s kritik", (w, c) == (25.0, 48.0), f"{w}/{c}")

    w, c = cron_thresholds_hours(mk(day_of_week=0))
    check("2. Haftalık iş: 169s uyarı / 192s kritik", (w, c) == (169.0, 192.0), f"{w}/{c}")

    w, c = cron_thresholds_hours(mk(interval_minutes=10))
    check("3. 10 dk aralıklı iş: 2s uyarı / 6s kritik", (w, c) == (2.0, 6.0), f"{w}/{c}")

    # 4. GERÇEK PROD DURUMU — eski kodda kritikti
    check(
        "4. Haftalık iş 89 saat sonra OK (prod: Pazartesi çalıştı, Cuma bakıldı)",
        level(mk(day_of_week=0, hours_ago=89)) == "ok",
        f"seviye={level(mk(day_of_week=0, hours_ago=89))}",
    )

    # 5. Koruma kaybolmadı: 2 tur kaçarsa kritik
    check(
        "5. Haftalık iş 9 gün sessizse kritik (gerçek arıza yakalanır)",
        level(mk(day_of_week=0, hours_ago=24 * 9)) == "crit",
        f"seviye={level(mk(day_of_week=0, hours_ago=24 * 9))}",
    )

    # 6. Günlük davranış korunur
    check(
        "6. Günlük iş 49 saat sonra kritik (mevcut davranış korunur)",
        level(mk(hours_ago=49)) == "crit", f"seviye={level(mk(hours_ago=49))}",
    )
    check(
        "6b. Günlük iş 22 saat sonra OK (prod: tüm günlükler sağlıklı)",
        level(mk(hours_ago=22)) == "ok", f"seviye={level(mk(hours_ago=22))}",
    )

    # 7. Aralıklı iş: eskiden 25 saate kadar "ok" görünürdü
    check(
        "7. 10 dk aralıklı iş 8 saat sessizse kritik (eskiden 'ok'tu)",
        level(mk(interval_minutes=10, hours_ago=8)) == "crit",
        f"seviye={level(mk(interval_minutes=10, hours_ago=8))}",
    )
    check(
        "7b. 60 dk aralıklı iş 1 saat sonra OK (prod: abuse_scan)",
        level(mk(interval_minutes=60, hours_ago=1)) == "ok",
        f"seviye={level(mk(interval_minutes=60, hours_ago=1))}",
    )

    # 8. İki yüzey aynı eşiği kullanıyor mu (kaynak paylaşımı)
    import inspect

    from app.services import data_integrity as di
    src = inspect.getsource(di.cron_drift_check)
    check(
        "8. Bütünlük paneli aynı eşik kaynağını kullanıyor",
        "cron_thresholds_hours" in src and "hours_crit" not in src,
        "data_integrity hâlâ kendi eşiğini hesaplıyor",
    )

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
