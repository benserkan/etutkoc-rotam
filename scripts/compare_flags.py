"""SALT OKUMA — eski uyarılar ile bayrak motorunu yan yana döker (2026-09-29).

Kullanım: python -m scripts.compare_flags <koç_id>
"""
from __future__ import annotations

import sys
from datetime import date

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import analytics
from app.services.risk_analysis import compute_risk_score
from app.services.student_flags import evaluate_flags


def main() -> None:
    cid = int(sys.argv[1])
    today = date.today()
    with SessionLocal() as db:
        studs = (db.query(User).filter(User.teacher_id == cid, User.role == UserRole.STUDENT,
                                       User.is_active.is_(True)).order_by(User.full_name).all())
        for s in studs:
            proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
            old = analytics.legacy_warnings(db, s, today, proj)
            r = evaluate_flags(db, s, today, proj)
            risk = compute_risk_score(db, student=s, today=today)
            print(f"\n#{s.id} {s.full_name}")
            print(f"  ESKİ ({len(old)}): " + "; ".join(f"[{w.level}] {w.title}" for w in old))
            print(f"  YENİ özet: {r.headline}  | seviye {r.level} · veli {r.parent_level} · risk {risk.level}")
            for w in r.primary:
                print(f"    ANA [{w.level}] {w.layer} {w.title} — {w.detail}")
            for w in r.secondary:
                print(f"    ek  [{w.level}] {w.layer} {w.title}")
            for w in r.good:
                print(f"    iyi {w.title}")


if __name__ == "__main__":
    main()
