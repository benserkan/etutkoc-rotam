"""SALT OKUMA — ders bazlı sınav hazırlığını öğrenci başına döker (2026-09-29).

Kullanım: python -m scripts.compare_readiness <koç_id>
"""
from __future__ import annotations

import sys
from datetime import date

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.exam_readiness import compute_readiness


def main() -> None:
    cid = int(sys.argv[1])
    today = date.today()
    with SessionLocal() as db:
        for s in (db.query(User).filter(User.teacher_id == cid, User.role == UserRole.STUDENT,
                                        User.is_active.is_(True), User.is_paused.is_(False))
                  .order_by(User.full_name)):
            rd = compute_readiness(db, s, today)
            print(f"\n#{s.id} {s.full_name} · sınav {rd.exam_date} · hedef {rd.target_date}")
            for sr in rd.subjects:
                books = " · ".join(f"{b['name']}({b['remaining']})" for b in sr.active_books)
                print(f"  {sr.subject_name:14} {sr.status:8} kalan {sr.remaining_tests:4} hız {sr.pace:4.1f}/g"
                      f" bitiş {sr.finish_date} geride {sr.days_late} | {books}"
                      + (f" | bırakılan: {', '.join(sr.dropped_books)}" if sr.dropped_books else ""))


if __name__ == "__main__":
    main()
