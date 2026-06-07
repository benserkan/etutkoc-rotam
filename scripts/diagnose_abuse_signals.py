"""Açık abuse sinyalleri teşhisi — 'Açık abuse sinyali' alarmı SALT-OKUMA.

abuse_open alarmı threshold=0 → tek bir çözülmemiş AbuseSignal bile her
değerlendirmede alarm üretir. Bu script açık sinyalleri listeler; bayat
(impersonation/süper-admin yanlış-pozitifi) mı yoksa gerçek mi ayırt eder.

  python -m scripts.diagnose_abuse_signals
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import AbuseSignal, User

now = datetime.now(timezone.utc)


def run() -> int:
    db = SessionLocal()
    try:
        openrows = (db.query(AbuseSignal)
                    .filter(AbuseSignal.resolved_at.is_(None))
                    .order_by(AbuseSignal.detected_at.desc()).all())
        print(f"=== Açık (resolved_at NULL) abuse sinyalleri: {len(openrows)} ===\n")
        for s in openrows:
            actor = db.get(User, s.actor_user_id) if s.actor_user_id else None
            det = s.detected_at
            if det and det.tzinfo is None:
                det = det.replace(tzinfo=timezone.utc)
            age = f"{(now-det).total_seconds()/3600:.1f}h önce" if det else "?"
            print(f"  id={s.id} kind={s.kind} severity={s.severity} count={s.count}")
            print(f"     actor_user_id={s.actor_user_id} "
                  f"({(actor.full_name + ' / ' + actor.role.value) if actor else '—'}) "
                  f"tenant_id={s.tenant_id}")
            print(f"     detected={det} ({age}) details={s.details_json or '-'}")
        if not openrows:
            print("  Açık sinyal YOK → abuse_open alarmı artık çalmamalı.")
        else:
            print(f"\n  NOT: abuse_open alarmı bu {len(openrows)} sinyal çözülene kadar (panel →")
            print("  Güvenlik Kamarası → Suistimal → 'Çöz') her değerlendirmede çalar.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(run())
