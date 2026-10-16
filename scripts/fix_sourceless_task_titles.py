"""Kaynaksız (konuya bağlı) tek kalemli görevlerde "Görev" yer tutucu başlığını
"Konu — N test" yap (2026-10-16). Kuru çalışma varsayılan; --apply ile yazar.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import selectinload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, Topic  # noqa: E402


def main() -> None:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    try:
        tasks = (
            db.query(Task)
            .options(selectinload(Task.book_items))
            .filter(Task.title.in_(["Görev", "—", ""]))
            .all()
        )
        n = 0
        for t in tasks:
            items = list(t.book_items or [])
            if len(items) != 1:
                continue
            it = items[0]
            if it.book_id is not None or not getattr(it, "topic_id", None):
                continue
            topic = db.get(Topic, it.topic_id)
            name = (topic.name if topic else None) or (it.label or "").strip()
            if not name:
                continue
            new = f"{name} — {it.planned_count or 0} test"
            print(f"#{t.id} öğrenci {t.student_id} {t.date}: {t.title!r} -> {new!r}")
            if apply:
                t.title = new
            n += 1
        if apply:
            db.commit()
        print(f"{n} görev {'güncellendi' if apply else 'güncellenecek (kuru çalışma)'}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
