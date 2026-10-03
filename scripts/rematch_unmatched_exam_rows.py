"""Kayıtlı deneme soru satırlarını GÜNCEL eşleştirme kurallarıyla yeniden dene.

Kullanım:
    python -m scripts.rematch_unmatched_exam_rows            # kuru çalışma (yazmaz)
    python -m scripts.rematch_unmatched_exam_rows --apply    # yazar
    ... --exam 91            # tek deneme
    ... --no-prefer-school   # yalnız eşleşmemişleri dene, okul tercihini atla

Ne yapar (2026-10-02):
  1. Eşleşmemiş (topic_id NULL) satırları, koçun "Satırları düzelt" ekranının
     kullandığı AYNI yolla (`build_edit_draft`: sözlük + deterministik +
     ücretsiz anahtarla kapalı-küme AI) yeniden eşler. Taksonomiye sonradan
     eklenen konular geriye dönük bağlanır.
  2. Okul-müfredat (karma havuz) denemelerinde aynı adlı konu hem okul hem
     TYT/AYT listesinde varsa OKUL konusuna çevirir (`_prefer_school_topics`).
  Koçun elle düzelttiği satıra (manually_edited) DOKUNULMAZ. Ders kırılımı
  (subject_nets) satırlardan yeniden kurulur; toplam/net DEĞİŞMEZ.
  İdempotent: ikinci koşu 0 değişiklik verir.
"""
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal  # noqa: E402
from app.models import ExamResult, User  # noqa: E402
from app.models.exam_result import ExamResultQuestion  # noqa: E402
from app.services import exam_import_service as eis  # noqa: E402


def _pool(db, exam: ExamResult, student: User):
    universe = eis.universe_for_section(exam.section)
    try:
        meta = json.loads(exam.analysis_meta) if exam.analysis_meta else {}
    except ValueError:
        meta = {}
    grade_cap = meta.get("grade_hint") or student.grade_level
    school_grade = eis._school_grade_signal(exam.title, meta.get("grade_hint"), student)
    subjects, topics, _display = eis._normalization_pool(
        db, universe, student, grade_cap=grade_cap, school_grade=school_grade,
        section=exam.section,
        raw_keys={eis._subject_key(q.subject_name_raw) for q in exam.questions})
    return subjects, topics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--exam", type=int)
    ap.add_argument("--no-prefer-school", action="store_true")
    ap.add_argument("--skip-qid", type=int, action="append", default=[],
                    help="Bu soru satırı id'sini yeniden eşleme (yanlış AI önerisi)")
    args = ap.parse_args()

    db = SessionLocal()
    q = db.query(ExamResult).filter(ExamResult.import_source == "pdf_import")
    if args.exam:
        q = q.filter(ExamResult.id == args.exam)
    total_rematched = total_swapped = touched = 0
    for exam in q.order_by(ExamResult.id).all():
        student = db.get(User, exam.student_id)
        qs = sorted(exam.questions, key=lambda x: x.id)
        if student is None or not qs:
            continue
        rematched = swapped = 0
        details: list[str] = []

        # 1 — eşleşmemiş satırlar
        if any(x.topic_id is None and not x.manually_edited for x in qs):
            try:
                draft = eis.build_edit_draft(db, student, exam)
            except eis.ExamImportError:
                draft = None
            if draft is not None:
                for row_q, r in zip(qs, draft["rows"]):
                    if row_q.manually_edited or row_q.topic_id is not None or row_q.id in args.skip_qid:
                        continue
                    if r.get("topic_id"):
                        details.append(f"  + S{row_q.question_no} '{row_q.topic_label_raw}' -> {r.get('topic_name')}")
                        if args.apply:
                            row_q.topic_id = r["topic_id"]
                            row_q.subject_id = r.get("subject_id")
                        rematched += 1

        # 2 — karma havuzda okul konusu tercihi
        if not args.no_prefer_school:
            subjects, topics = _pool(db, exam, student)
            subj_by_id = {s.id: s for s in subjects}
            rows = []
            for row_q in qs:
                if row_q.manually_edited or row_q.topic_id is None:
                    continue
                rows.append({"_q": row_q, "topic_id": row_q.topic_id, "topic_source": "ai"})
            if rows and eis._prefer_school_topics(rows, topics, subj_by_id):
                for r in rows:
                    row_q = r["_q"]
                    if r["topic_id"] != row_q.topic_id:
                        details.append(f"  ~ S{row_q.question_no} '{row_q.topic_label_raw}' -> okul: {r['topic_name']}")
                        if args.apply:
                            row_q.topic_id = r["topic_id"]
                            row_q.subject_id = r.get("subject_id")
                        swapped += 1

        if rematched or swapped:
            touched += 1
            total_rematched += rematched
            total_swapped += swapped
            print(f"#{exam.id} {exam.title} (öğrenci {exam.student_id}): "
                  f"{rematched} yeniden eşlendi · {swapped} okul konusuna çevrildi")
            for d in details[:40]:
                print(d)
            if args.apply:
                db.flush()
                eis.rebuild_subject_nets(db, exam, student)

    remaining = (db.query(ExamResultQuestion).join(ExamResult)
                 .filter(ExamResult.import_source == "pdf_import",
                         ExamResultQuestion.topic_id.is_(None)).count())
    if args.apply:
        db.commit()
    else:
        db.rollback()
    print(f"\n{'UYGULANDI' if args.apply else 'KURU ÇALIŞMA'}: {touched} deneme · "
          f"{total_rematched} satır yeniden eşlendi · {total_swapped} satır okul konusuna çevrildi"
          f"{'' if args.apply else ' (yazılmadı)'} · eşleşmemiş kalan: {remaining}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
