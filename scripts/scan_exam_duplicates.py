"""Mevcut deneme kayıtlarında mükerrer taraması — SALT OKUMA (rapor).

Koruma (2026-09-19) yeni kayıtları engeller; bu betik daha önce açılmış
çiftleri bulur: aynı öğrenci içinde (1) aynı PDF parmak izi, (2) soru soru
aynı/yakın cevap dizisi, (3) normalize ad + aynı/yakın tarih. Hiçbir şey
SİLMEZ — hangisinin kalacağına koç karar verir (deneme listesindeki çöp
simgesi). Sıralama öğrenci → eski kayıt → yeni kayıt.

Kullanım: PYTHONPATH=. python scripts/scan_exam_duplicates.py [--student-id N]
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from collections import defaultdict

from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import ExamResult, User
from app.services import exam_duplicate as dup


def _arg(name: str) -> str | None:
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None


def main() -> int:
    sid = _arg("--student-id")
    with SessionLocal() as db:
        q = db.query(ExamResult).options(selectinload(ExamResult.questions))
        if sid:
            q = q.filter(ExamResult.student_id == int(sid))
        exams = q.order_by(ExamResult.student_id, ExamResult.id).all()
        by_student: dict[int, list[ExamResult]] = defaultdict(list)
        for e in exams:
            by_student[e.student_id].append(e)
        names = {
            u.id: u.full_name
            for u in db.query(User.id, User.full_name).filter(User.id.in_(list(by_student))).all()
        } if by_student else {}

        pairs = []
        for st, rows in by_student.items():
            for i, a in enumerate(rows):
                sig_a = dup.answer_signature(a.questions) if a.questions else ()
                for b in rows[i + 1:]:
                    reason = None
                    sim = 1.0
                    if a.import_pdf_sha256 and a.import_pdf_sha256 == b.import_pdf_sha256:
                        reason = "same_file"
                    elif sig_a and b.questions and a.section == b.section:
                        sim = dup.similarity(sig_a, dup.answer_signature(b.questions))
                        if sim >= 1.0:
                            reason = "same_answers"
                        elif sim >= dup.NEAR_ANSWER_RATIO:
                            reason = "near_answers"
                    if reason is None and dup.normalize_title(a.title) == dup.normalize_title(b.title):
                        gap = abs((a.exam_date - b.exam_date).days)
                        if gap == 0:
                            reason = "same_title_date"
                        elif gap <= dup.NEAR_DATE_DAYS:
                            reason = "near_title_date"
                    if reason:
                        pairs.append((st, a, b, reason, sim))

    print(f"Taranan deneme: {len(exams)} · öğrenci: {len(by_student)} · şüpheli çift: {len(pairs)}\n")
    for st, a, b, reason, sim in pairs:
        lvl = "KESİN" if reason in ("same_file", "same_answers") else "olası"
        extra = f" · benzerlik %{sim * 100:.0f}" if reason == "near_answers" else ""
        print(f"[{lvl}] öğrenci #{st} {names.get(st, '')}: "
              f"#{a.id} ({a.exam_date}, {a.title[:40]}) ↔ #{b.id} ({b.exam_date}, {b.title[:40]}) "
              f"— {dup.REASON_LABELS_TR.get(reason, reason)}{extra}")
    if not pairs:
        print("Mükerrer bulunmadı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
