# -*- coding: utf-8 -*-
"""Öğrenci haftalık koçluk raporu için SALT-OKUMA veri dökümü (JSON).

Tek kaynak: app/services/weekly_coach_report.collect (sistemdeki "Haftalık rapor"
butonu aynı fonksiyonu kullanır). Container içinde:
    python -m scripts.dump_student_weekly_report --student-id 113 > /tmp/emir.json
    python -m scripts.dump_student_weekly_report --name Emir --week-end 2026-08-18 --days 7
Pencere verilmezse programın işlendiği son güne kadar geriye 7 gün. Hiçbir yazma yapmaz.
"""
from __future__ import annotations
import argparse, json, sys
from datetime import date, timedelta

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import weekly_coach_report as w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--student-id", type=int)
    ap.add_argument("--name")
    ap.add_argument("--days", type=int, default=w.DEFAULT_DAYS)
    ap.add_argument("--week-end", help="YYYY-MM-DD (varsayılan: programın işlendiği son gün)")
    args = ap.parse_args()
    db = SessionLocal()
    if args.student_id:
        st = db.get(User, args.student_id)
    else:
        st = (db.query(User).filter(User.full_name.ilike(f"%{args.name}%"), User.role == UserRole.STUDENT).first())
    if not st:
        print("student not found", file=sys.stderr); sys.exit(1)
    if args.week_end:
        we = date.fromisoformat(args.week_end); ws = we - timedelta(days=args.days - 1)
    else:
        ws, we = w.default_window(db, st, days=args.days)
    data = w.collect(db, st, ws, we)
    print(json.dumps(data, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
