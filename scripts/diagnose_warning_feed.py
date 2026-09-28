"""SALT OKUMA — bir koçun Uyarı Akışını öğrenci/kod bazında döker (2026-09-29).

Kullanım: python -m scripts.diagnose_warning_feed <coach_id>
Amaç: uyarılar doğru mu, aynı olgu kaç ayrı uyarı üretiyor, liste neden uzun.
"""
from __future__ import annotations

import sys
from collections import Counter
from datetime import date

from app.database import SessionLocal
from app.models import User, UserRole
from app.services.analytics import student_snapshot


def main() -> None:
    cid = int(sys.argv[1])
    today = date.today()
    with SessionLocal() as db:
        studs = (db.query(User).filter(User.teacher_id == cid, User.role == UserRole.STUDENT,
                                       User.is_active.is_(True)).order_by(User.full_name).all())
        codes = Counter()
        total = 0
        for s in studs:
            sn = student_snapshot(db, s, today=today)
            if not sn.warnings:
                print(f"#{s.id} {s.full_name}: uyarı yok")
                continue
            print(f"#{s.id} {s.full_name} (sınıf {s.grade_level}, sınav {getattr(s, 'exam_date', None)}):")
            for w in sn.warnings:
                total += 1
                codes[w.code.split('_')[0] + "_" + w.code.split('_')[1] if w.code.startswith('subject') else w.code] += 1
                print(f"   [{w.level}] {w.code}: {w.title} — {w.detail}")
            print(f"   bugün planlı test {sn.today.planned}, çözülen {sn.today.completed}; "
                  f"hız7 {sn.rate_7d if hasattr(sn, 'rate_7d') else '?'}")
        print(f"\nToplam {len(studs)} aktif öğrenci, {total} uyarı")
        for k, v in codes.most_common():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
