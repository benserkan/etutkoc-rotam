"""Manşet "% tamam" kısmi görev payı — "1/6 test · %0 tamam" çelişkisi regresyonu.

Öğrenci Bugün ekranında 6 testlik görevin 1'i işaretlenince yüzde 0 değil ~%17
olmalı (koç yüzeyiyle aynı formül: gorev_stats.gorev_fraction). Saf (DB'siz).
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.models.book import BookType
from app.models.task import TaskStatus
from app.services import gorev_stats as gs

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


mat = SimpleNamespace(type=BookType.SORU_BANKASI, subject_id=2,
                      subject=SimpleNamespace(name="Matematik", order=2))


def task(planned, completed, status=TaskStatus.PENDING, bk=mat):
    items = [] if planned == 0 else [SimpleNamespace(planned_count=planned, completed_count=completed,
                                                     book_id=102 if bk else None, book=bk)]
    return SimpleNamespace(book_items=items, status=status, title="G", work_block_id=None,
                           block_detached=False, solved_count=None, is_draft=False)


def main() -> int:
    print("\n=== manşet % — kısmi görev payı ===\n")
    one = [task(6, 1)]
    chk("1/6 test → %17 (sıfır değil)", round(gs.completion_pct(one) * 100) == 17, gs.completion_pct(one))
    chk("ikili gorev_done hâlâ 0 (X/Y görev sayımı değişmez)", gs.summarize(one).gorev_done == 0)
    chk("COMPLETED → 1.0", gs.gorev_fraction(task(6, 2, TaskStatus.COMPLETED)) == 1.0)
    chk("bitmemiş etkinlik → 0", gs.gorev_fraction(task(0, 0)) == 0.0)
    chk("biten etkinlik → 1", gs.gorev_fraction(task(0, 0, TaskStatus.COMPLETED)) == 1.0)
    mixed = [task(6, 3), task(0, 0, TaskStatus.COMPLETED), task(4, 0)]
    chk("karışık gün (0.5+1+0)/3 = %50", round(gs.completion_pct(mixed) * 100) == 50, gs.completion_pct(mixed))
    chk("boş gün → 0", gs.completion_pct([]) == 0.0)
    chk("fazla işaret %100'ü aşmaz", gs.gorev_fraction(task(4, 9)) == 1.0)

    from app.routes.api_v2.student import _build_day_summary
    s = _build_day_summary(one)
    chk("öğrenci gün özeti pct = 1/6", abs(s.pct - 1 / 6) < 1e-9, s.pct)

    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
