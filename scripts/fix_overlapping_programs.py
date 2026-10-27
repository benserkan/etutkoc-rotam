"""Çakışan program kayıtlarını düzelt (2026-10-27, Beril vakası).

Erken bitirme akışı gelmeden önce koç "çakışmaya rağmen oluştur" ile yeni programı eski
program bitmeden başlatabiliyordu → eski programın `end_date`'i kesilen günleri hâlâ
kapsıyordu. Kural (create_program ile aynı): sonra başlayan program eski programın
içine düşüyorsa eski program yeni başlangıçtan bir gün önce biter; görevler tarihe
bağlı olduğundan yerinde kalır (yeni programın günleri olur). Not eklenir.

Aynı gün başlayan iki program otomatik düzeltilmez — yalnız raporlanır (koç karar verir).

    python -m scripts.fix_overlapping_programs            # kuru çalışma (yazmaz)
    python -m scripts.fix_overlapping_programs --apply
    python -m scripts.fix_overlapping_programs --student 123
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from datetime import timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import WeeklyProgram  # noqa: E402


def fix(db, *, apply: bool, student_id: int | None = None) -> tuple[list[dict], list[dict]]:
    q = db.query(WeeklyProgram)
    if student_id:
        q = q.filter(WeeklyProgram.student_id == student_id)
    by_student: dict[int, list[WeeklyProgram]] = defaultdict(list)
    for p in q.all():
        by_student[p.student_id].append(p)
    fixed: list[dict] = []
    same_start: list[dict] = []
    for sid, progs in by_student.items():
        progs.sort(key=lambda p: (p.start_date, p.created_at or p.start_date, p.id))
        for i, p in enumerate(progs):
            later = [o for o in progs[i + 1:] if p.start_date <= o.start_date <= p.end_date]
            if not later:
                continue
            same = [o for o in later if o.start_date == p.start_date]
            for o in same:
                same_start.append(dict(student_id=sid, a=p.id, b=o.id, start=p.start_date.isoformat()))
            nxt = [o for o in later if o.start_date > p.start_date]
            if not nxt:
                continue
            new_end = min(o.start_date for o in nxt) - timedelta(days=1)
            if new_end >= p.end_date:
                continue
            fixed.append(dict(student_id=sid, program_id=p.id, start=p.start_date.isoformat(),
                              old_end=p.end_date.isoformat(), new_end=new_end.isoformat()))
            if apply:
                stamp = (f"Erken bitirildi ({p.end_date.strftime('%d.%m')} yerine "
                         f"{new_end.strftime('%d.%m')}): sonraki program bu tarihten sonra başladı "
                         f"(otomatik düzeltme) · kalan günler yeni programa aktarıldı")
                p.notes = (f"{p.notes}\n{stamp}" if p.notes else stamp)[:2000]
                p.end_date = new_end
    if apply:
        db.commit()
    return fixed, same_start


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--student", type=int, default=None)
    a = ap.parse_args()
    with SessionLocal() as db:
        fixed, same = fix(db, apply=a.apply, student_id=a.student)
    for f in fixed:
        print(f"  öğrenci {f['student_id']} · program #{f['program_id']} {f['start']} → "
              f"{f['old_end']} ⇒ {f['new_end']}")
    for s in same:
        print(f"  [elle bak] öğrenci {s['student_id']} · #{s['a']} ve #{s['b']} aynı gün başlıyor ({s['start']})")
    print(f"\n{len(fixed)} program {'düzeltildi' if a.apply else 'düzeltilecek (kuru çalışma)'} · "
          f"{len(same)} aynı-gün çakışması raporlandı")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
