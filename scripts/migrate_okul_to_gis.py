"""Lisede "Okul Denemesi" olarak kaydedilmiş denemeleri gelişim izleme türüne taşı (2026-10-27).

Koç: lisede "okul denemesi" diye bir tür yok — bunlar sınıf düzeyi Gelişim İzleme
sınavları. Tür, öğrencinin DENEMEYİ ÇÖZDÜĞÜ andaki sınıfından (sınıf dönemi kaydı;
yoksa bugünkü sınıfı) belirlenir:
    9 → 9. Sınıf Gelişim İzleme · 10 → 10. · 11 → 11. · 12 / mezun → 12. Sınıf (AYT)
Ortaokul (5-8) ve sınıfı bilinmeyen kayıtlara dokunulmaz (raporlanır).
Net, soru satırları ve konu eşleşmeleri DEĞİŞMEZ; yalnız tür (section) güncellenir.

    python -m scripts.migrate_okul_to_gis            # kuru çalışma (yazmaz)
    python -m scripts.migrate_okul_to_gis --apply
    python -m scripts.migrate_okul_to_gis --student 84
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import ExamResult, User  # noqa: E402
from app.models.curriculum import EXAM_SECTION_LABELS, ExamSection  # noqa: E402
from app.services.grade_period_service import period_for_date  # noqa: E402

_BY_GRADE = {9: ExamSection.MAARIF_9, 10: ExamSection.MAARIF_10, 11: ExamSection.MAARIF_11}


def target_for(grade: int | None, graduate: bool) -> ExamSection | None:
    if graduate or (grade or 0) >= 12:
        return ExamSection.GIS_12
    return _BY_GRADE.get(grade or 0)


def migrate(db, *, apply: bool, student_id: int | None = None) -> tuple[list[dict], list[dict]]:
    q = db.query(ExamResult).filter(ExamResult.section == ExamSection.OKUL)
    if student_id:
        q = q.filter(ExamResult.student_id == student_id)
    moved: list[dict] = []
    skipped: list[dict] = []
    for e in q.order_by(ExamResult.student_id, ExamResult.exam_date).all():
        st = db.get(User, e.student_id)
        if st is None:
            continue
        per = period_for_date(db, st.id, e.exam_date)
        grade = per.grade_level if per else st.grade_level
        grad = bool(per.is_graduate) if per else bool(st.is_graduate)
        tgt = target_for(grade, grad)
        row = dict(exam_id=e.id, student_id=st.id, student=st.full_name, title=e.title,
                   date=e.exam_date.isoformat(), grade="mezun" if grad else grade)
        if tgt is None:
            skipped.append(row)
            continue
        row["to"] = EXAM_SECTION_LABELS[tgt]
        moved.append(row)
        if apply:
            e.section = tgt
    if apply:
        db.commit()
    return moved, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--student", type=int, default=None)
    a = ap.parse_args()
    with SessionLocal() as db:
        moved, skipped = migrate(db, apply=a.apply, student_id=a.student)
    for m in moved:
        print(f"  #{m['exam_id']} öğrenci {m['student_id']} ({m['student']}, {m['grade']}. sınıf) "
              f"{m['date']} «{m['title']}» → {m['to']}")
    for s in skipped:
        print(f"  [dokunulmadı] #{s['exam_id']} öğrenci {s['student_id']} ({s['grade']}) «{s['title']}»")
    print(f"\n{len(moved)} kayıt {'taşındı' if a.apply else 'taşınacak (kuru çalışma)'} · "
          f"{len(skipped)} kayda dokunulmadı (ortaokul / sınıf bilinmiyor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
