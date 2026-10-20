"""Canlıdan dökülmüş ANONİM deneme fikstürünü yerel DEV veritabanına yükle (YALNIZ DEV).

`export_exam_fixture` çıktısındaki her öğrenci "Canlı Örnek N" adıyla Demo Öğretmen'e
bağlanır; denemeleri ve soru satırları birebir yazılır, konular (ders adı, konu adı) çiftiyle
yerel müfredat konusuna eşlenir. Deneme analizi ekranları bu GERÇEK veriyle geliştirilir ve
test edilir (`test_exam_live_fixture`).

  python -m scripts.import_exam_fixture <fixture.json>          # kur (varsa yeniden kurar)
  python -m scripts.import_exam_fixture --delete                # sil
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, time, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Topic, User, UserRole  # noqa: E402
from app.models.exam_result import ExamResult, ExamResultQuestion, ExamSection  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services.security import hash_password  # noqa: E402

COACH_EMAIL = "ogretmen@lgs.local"
PREFIX = "canli-ornek-"
PWD = "CanliOrnek2026!"


def delete(db) -> None:
    ids = [u.id for u in db.query(User).filter(User.email.like(f"{PREFIX}%")).all()]
    if not ids:
        return
    eids = [e.id for e in db.query(ExamResult.id).filter(ExamResult.student_id.in_(ids))]
    if eids:
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(eids)))
    db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
    db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(ids)))
    db.execute(sa_delete(User).where(User.id.in_(ids)))
    db.commit()


def main() -> None:
    db = SessionLocal()
    delete(db)
    if "--delete" in sys.argv:
        print("Silindi.")
        return
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    coach = db.query(User).filter(User.email == COACH_EMAIL).first()
    subj_by_name: dict[str, list[int]] = {}
    for s in db.query(Subject).all():
        subj_by_name.setdefault(s.name, []).append(s.id)
    topic_by_pair: dict[tuple[str, str], int] = {}
    sname = {s.id: s.name for s in db.query(Subject).all()}
    for t in db.query(Topic).all():
        topic_by_pair.setdefault((sname.get(t.subject_id, ""), t.name), t.id)
    tsubj = {t.id: t.subject_id for t in db.query(Topic).all()}
    miss = 0
    total_q = 0
    for s in data:
        first = min((date.fromisoformat(e["date"]) for e in s["exams"]), default=date.today())
        u = User(email=f"{PREFIX}{s['n']}@lgs.local", password_hash=hash_password(PWD),
                 full_name=f"Canlı Örnek {s['n']}", role=UserRole.STUDENT, is_active=True,
                 teacher_id=coach.id, institution_id=coach.institution_id, grade_level=s["grade"],
                 track=Track(s["track"]) if s["track"] else None, must_change_password=False,
                 created_at=datetime.combine(first - timedelta(days=7), time(9)))
        db.add(u)
        db.flush()
        db.add(StudentGradePeriod(student_id=u.id, started_on=first - timedelta(days=7),
                                  grade_level=s["grade"], is_graduate=s.get("is_graduate", False),
                                  track=s["track"]))
        for e in s["exams"]:
            ex = ExamResult(student_id=u.id, created_by_id=coach.id, title=e["title"],
                            exam_date=date.fromisoformat(e["date"]), section=ExamSection(e["section"]),
                            total_correct=e["c"], total_wrong=e["w"], total_blank=e["b"], net=e["net"],
                            subject_nets=e["subject_nets"], import_source=e["import_source"],
                            analysis_meta=e["analysis_meta"])
            db.add(ex)
            db.flush()
            for q in e["questions"]:
                tid = topic_by_pair.get(tuple(q["topic"])) if q["topic"] else None
                if q["topic"] and tid is None:
                    miss += 1
                total_q += 1
                sid = tsubj.get(tid) if tid else ((subj_by_name.get(q["subject"]) or [None])[0])
                db.add(ExamResultQuestion(exam_result_id=ex.id, question_no=q["no"],
                                          subject_name_raw=q["subject_raw"], subject_id=sid,
                                          topic_label_raw=q["topic_raw"], topic_id=tid,
                                          correct_answer=q["ans"], student_answer=q["stu"],
                                          result=q["res"], is_suspect=q["suspect"]))
        print(f"Canlı Örnek {s['n']}: öğrenci #{u.id} · {len(s['exams'])} deneme")
    db.commit()
    print(f"Soru: {total_q} · yerelde eşlenemeyen konu: {miss}")


if __name__ == "__main__":
    main()
