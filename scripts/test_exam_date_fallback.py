"""Sınav tarihi: akademik yılı atanmamış / geçmişte kalmış öğrenci (2026-09-29).

Prod: 12. sınıf ve mezunların çoğunda akademik yıl yoktu → tarih None → sınav
tahmini ve velinin "sınav yaklaşıyor" bildirimi sessizce kapalıydı.
"""
from __future__ import annotations

import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.models import AcademicYear, User, UserRole

passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def mk(grade=None, grad=False, ay=None):
    u = User(email="x@test.invalid", password_hash="x", full_name="x", role=UserRole.STUDENT,
             grade_level=grade, is_graduate=grad)
    if ay:
        u.academic_year = AcademicYear(start_year=ay)
    return u


def main() -> int:
    t = date.today()
    yks = date(t.year if (t.month, t.day) <= (6, 20) else t.year + 1, 6, 20)
    lgs = date(t.year if (t.month, t.day) <= (6, 7) else t.year + 1, 6, 7)
    chk("12. sınıf, akademik yıl yok → önümüzdeki YKS", mk(12).effective_exam_date == yks,
        str(mk(12).effective_exam_date))
    chk("mezun, akademik yıl yok → önümüzdeki YKS", mk(grad=True).effective_exam_date == yks)
    chk("8. sınıf, akademik yıl yok → önümüzdeki LGS", mk(8).effective_exam_date == lgs)
    chk("geçmiş akademik yıl (2020) → önümüzdeki dönem", mk(12, ay=2020).effective_exam_date == yks)
    chk("güncel akademik yıl korunur", mk(12, ay=yks.year - 1).effective_exam_date == yks)
    chk("9. sınıf → sınav hedefi yok", mk(9).effective_exam_date is None)
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
