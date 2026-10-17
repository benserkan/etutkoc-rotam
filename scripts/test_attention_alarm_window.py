"""Dikkat Odası alarm kartları: 72 saat penceresi + kural başına tek kart.

Saha (2026-10-17): Ağustos'tan kalma 6 onaylanmamış "Açık abuse sinyali"
alarmı 6 ayrı kart olarak duruyordu.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete

from app.database import SessionLocal
from app.models.alarm import AlarmEvent
from app.services import attention_engine as ae

KEY_OLD, KEY_NEW = "zz_test_old", "zz_test_new"
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def ev(key, name, hours_ago):
    return AlarmEvent(rule_key=key, rule_name=name, value=1, threshold=0, severity="warn",
                      channels_attempted="", delivery_status="ok",
                      triggered_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago))


def main() -> int:
    with SessionLocal() as db:
        db.execute(delete(AlarmEvent).where(AlarmEvent.rule_key.in_([KEY_OLD, KEY_NEW])))
        db.add_all([ev(KEY_OLD, "ZZ Eski", 24 * 60 + i) for i in range(6)]
                   + [ev(KEY_NEW, "ZZ Yeni", i) for i in range(3)])
        db.commit()
        try:
            titles = [i.title for i in ae._detect_unack_alarms(db)]
            chk("72 saatten eski alarm kart üretmez", not any("ZZ Eski" in t for t in titles), titles)
            new = [t for t in titles if "ZZ Yeni" in t]
            chk("aynı kuralın 3 tetiği TEK kart", len(new) == 1, new)
            chk("kartta tekrar sayısı yazar", bool(new) and "(3 kez)" in new[0], new)
        finally:
            db.execute(delete(AlarmEvent).where(AlarmEvent.rule_key.in_([KEY_OLD, KEY_NEW])))
            db.commit()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
