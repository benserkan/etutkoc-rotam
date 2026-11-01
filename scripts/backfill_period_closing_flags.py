"""Kapanmış havuz dönemlerine kapanış uyarısı anlık görüntüsü yazar (H2, 2026-11-01).

closing_flags_json bu tarihten önce kapanan dönemlerde boştur. Değerlendirme kapanış günü
(`closed_on`) itibarıyla, dönem açıkmış gibi yapılır (pool_flags.closing_snapshot).
Kuru çalışma varsayılan; `--apply` yazar. Yalnız boş olanları doldurur (idempotent).

    python -m scripts.backfill_period_closing_flags [--apply] [--student 84]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.models.pool import PERIOD_OPEN, StudyPeriod  # noqa: E402
from app.services import pool_flags  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--student", type=int)
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with SessionLocal() as db:
        q = db.query(StudyPeriod).filter(StudyPeriod.status != PERIOD_OPEN,
                                         StudyPeriod.closed_on.isnot(None),
                                         StudyPeriod.closing_flags_json.is_(None))
        if a.student:
            q = q.filter(StudyPeriod.student_id == a.student)
        n = 0
        for p in q.order_by(StudyPeriod.id).all():
            st = db.get(User, p.student_id)
            if st is None:
                continue
            raw = pool_flags.closing_snapshot(db, st, p, p.closed_on)
            flags = json.loads(raw)
            n += 1
            print(f"dönem #{p.id} öğrenci #{p.student_id} {p.opened_on}→{p.closed_on}: "
                  + ("; ".join(f"[{f['level']}] {f['title']}" for f in flags) or "uyarı yok"))
            if a.apply:
                p.closing_flags_json = raw
        if a.apply:
            db.commit()
        else:
            db.rollback()
        print(f"\n{n} dönem {'yazıldı' if a.apply else '(kuru çalışma — --apply ile yaz)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
