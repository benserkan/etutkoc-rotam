"""Branş denemesi kayıtlarında 0'a kırpılmış negatif neti düzelt (2026-11-08).

Program görevinden açılan branş kaydı (import_source="task") eskiden genel deneme kuralıyla
"taban 0" alıyordu: 1D 10Y → pencere ve kart −1,5, kayıt/analiz 0,00. Artık branş kaydı ders
neti gibi negatif olabilir (deneme_bridge). Bu betik eski kayıtları aynı kurala çeker: kalemi
köprüyle yeniden eşitler. Kuru çalışma varsayılan; --apply yazar. İdempotent.

    python -m scripts.fix_brans_negative_net
    python -m scripts.fix_brans_negative_net --apply
"""
from __future__ import annotations

import argparse
import sys

from app.database import SessionLocal
from app.models import ExamResult, TaskBookItem
from app.models.exam_result import SOURCE_TASK, subject_net
from app.services import exam_scope
from app.services.deneme_bridge import sync_item


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = SessionLocal()
    n = 0
    for rec in db.query(ExamResult).filter(ExamResult.import_source == SOURCE_TASK).all():
        if exam_scope.exam_scope(rec).kind != "brans":
            continue
        want = subject_net(rec.total_correct, rec.total_wrong, rec.section)
        if abs(want - rec.net) < 0.005:
            continue
        n += 1
        print(f"#{rec.id} öğrenci {rec.student_id} · {rec.title}: net {rec.net} → {want}")
        if args.apply and rec.task_book_item_id:
            it = db.get(TaskBookItem, rec.task_book_item_id)
            if it is not None:
                sync_item(db, it)
    print(f"\nÖZET: {n} kayıt")
    if args.apply:
        db.commit()
        print("UYGULANDI.")
    else:
        db.rollback()
        print("(kuru çalışma — yazmak için --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
