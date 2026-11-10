"""Kayıtlı deneme sorularını kesin kazanım kuralıyla yeniden bağla (2026-11-10).

Öğrenilmiş YZ sözlüğü "ana fikir / yardımcı fikir / söz sanatı / hikâye unsuru" kazanımlarını alt
konular eklenmeden önce genel başlığa ("Paragrafta Anlam", "Metin Türleri") bağlamıştı.
Koçun elle düzelttiği satıra (manually_edited) dokunulmaz. Değişen denemenin ders kırılımı
rebuild_subject_nets ile yeniden kurulur (net değişmez). Kuru çalışma varsayılan; --apply yazar.
"""
from __future__ import annotations

import sys
from collections import Counter

from app.database import SessionLocal
from app.models import Topic, User
from app.models.exam_result import ExamResult, ExamResultQuestion
from app.services.exam_import_service import _kazanim_rule, rebuild_subject_nets


def main(apply: bool) -> None:
    with SessionLocal() as db:
        by_subject: dict[int, list[Topic]] = {}
        moves: Counter = Counter()
        touched: set[int] = set()
        qs = (db.query(ExamResultQuestion)
              .filter(ExamResultQuestion.topic_id.isnot(None), ExamResultQuestion.topic_label_raw.isnot(None),
                      ExamResultQuestion.manually_edited.is_(False)).all())
        for q in qs:
            cur = db.get(Topic, q.topic_id)
            if cur is None:
                continue
            if cur.subject_id not in by_subject:
                by_subject[cur.subject_id] = db.query(Topic).filter(Topic.subject_id == cur.subject_id).all()
            tp = _kazanim_rule(q.topic_label_raw, by_subject[cur.subject_id], cur.subject_id)
            if tp is None or tp.id == cur.id:
                continue
            moves[(cur.name, tp.name)] += 1
            if '--v' in sys.argv:
                print('   ', q.exam_result_id, repr((q.topic_label_raw or '')[:70]), cur.name, '→', tp.name)
            touched.add(q.exam_result_id)
            if apply:
                q.topic_id = tp.id
        for (a, b), n in moves.most_common():
            print(f"{n:4d}  {a} → {b}")
        print(f"{sum(moves.values())} soru · {len(touched)} deneme {'güncellendi' if apply else 'değişecek (kuru)'}")
        if apply:
            db.flush()
            for eid in touched:
                e = db.get(ExamResult, eid)
                rebuild_subject_nets(db, e, db.get(User, e.student_id))
            db.commit()


if __name__ == "__main__":
    main("--apply" in sys.argv)
