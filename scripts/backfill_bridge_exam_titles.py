"""Programdaki deneme kayıtlarının başlığını köprünün GÜNCEL kuralıyla yeniden kur (2026-11-10).

Aynı bölümden aynı gün iki deneme "… — Deneme" diye aynı başlıkla görünüyordu (Emir #113, Kimya);
numara kuralı (· 1. deneme) bu kayıtlardan sonra eklendi. Yalnız başlık değişir; net/sonuç dokunulmaz.
Kuru çalışma varsayılan; --apply yazar.
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models.exam_result import ExamResult
from app.models.task import TaskBookItem
from app.services.deneme_bridge import _title


def main(apply: bool) -> None:
    with SessionLocal() as db:
        rows = db.query(ExamResult).filter(ExamResult.task_book_item_id.isnot(None),
                                           ExamResult.import_source == "task").all()
        n = 0
        for e in rows:
            it = db.get(TaskBookItem, e.task_book_item_id)
            if it is None:
                continue
            new = _title(it)
            if new and new != e.title:
                n += 1
                print(f"#{e.id} öğr {e.student_id}: {e.title!r} → {new!r}")
                if apply:
                    e.title = new
        if apply:
            db.commit()
        print(f"{n} kayıt {'güncellendi' if apply else 'değişecek (kuru)'}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
