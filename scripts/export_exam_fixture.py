"""Canlı deneme verisini ANONİM test fikstürüne dök (SALT OKUMA — prod'da koşulur).

Gerçek öğrencilerin (demo/silinmiş hariç) deneme kayıtları + soru satırlarını JSON'a yazar.
Kişisel veri TAŞINMAZ: ad/e-posta/telefon yok, karne PDF'i yok; öğrenci yalnız sıra no +
sınıf/alan/müfredat modeli ile temsil edilir. Konular (ders adı, konu adı) çiftiyle taşınır;
yerel içe aktarma (`import_exam_fixture`) bu çifti yerel konu kimliğine eşler.

  python -m scripts.export_exam_fixture > exam_fixture.json
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Topic, User  # noqa: E402
from app.models.exam_result import ExamResult  # noqa: E402


def main() -> None:
    db = SessionLocal()
    sids = [r[0] for r in db.query(ExamResult.student_id).distinct()]
    users = [u for u in db.query(User).filter(User.id.in_(sids)).order_by(User.id).all()
             if u.is_active is not False and "demo" not in (u.full_name or "").lower()
             and "silinen" not in (u.full_name or "").lower()
             and not (u.email or "").startswith("anonymized-")]
    topics = {t.id: t for t in db.query(Topic).all()}
    subjects = {s.id: s.name for s in db.query(Subject).all()}
    out = []
    for n, u in enumerate(users, 1):
        exams = (db.query(ExamResult).filter(ExamResult.student_id == u.id)
                 .order_by(ExamResult.exam_date, ExamResult.id).all())
        ex_out = []
        for e in exams:
            qs = []
            for q in sorted(e.questions, key=lambda x: (x.question_no or 0, x.id)):
                t = topics.get(q.topic_id) if q.topic_id else None
                qs.append({
                    "no": q.question_no, "subject_raw": q.subject_name_raw,
                    "subject": subjects.get(q.subject_id) if q.subject_id else None,
                    "topic_raw": q.topic_label_raw,
                    "topic": [subjects.get(t.subject_id), t.name] if t else None,
                    "ans": q.correct_answer, "stu": q.student_answer, "res": q.result,
                    "suspect": bool(q.is_suspect),
                })
            ex_out.append({
                "title": e.title, "date": e.exam_date.isoformat(), "section": e.section.value,
                "c": e.total_correct, "w": e.total_wrong, "b": e.total_blank, "net": e.net,
                "subject_nets": e.subject_nets, "note": None, "import_source": e.import_source,
                "analysis_meta": e.analysis_meta, "questions": qs,
            })
        out.append({"n": n, "grade": u.grade_level, "track": getattr(u.track, "value", u.track),
                    "is_graduate": bool(getattr(u, "is_graduate", False)), "exams": ex_out})
    json.dump(out, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
