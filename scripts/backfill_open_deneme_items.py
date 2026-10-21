"""Açık (tamamlanmamış) deneme görevlerini deneme kalemine çevir (2026-10-21).

D1 (deneme görevi tanıma) canlıya çıkmadan önce deneme kitabından verilen görevler
`exam_kind` taşımıyor → öğrenci sonuç penceresi yerine eski "çözdüğüm test" formunu
görüyordu. Bu betik YALNIZ henüz tamamlanmamış ve `--since` tarihinden sonraki görevleri
çevirir (geçmiş toplu kayıtlar bilinçli dokunulmaz — D3 notu):

  - kalem: exam_kind (branş/genel) + exam_section + question_count (D1 ile aynı kural)
  - planned N > 1 → N kalem (1 kalem = 1 deneme); çözülen kısım ilk kalemlere dağıtılır
  - rezerv toplamı değişmez (aynı bölüm, planned toplamı aynı)
  - otomatik başlık yenilenir (koçun elle başlığına dokunulmaz)

Kuru çalışma varsayılan:  PYTHONPATH=. python scripts/backfill_open_deneme_items.py [--since 2026-10-01] [--apply]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from app.database import SessionLocal
from app.models import Book, BookSection, Task, TaskBookItem
from app.models.task import TaskStatus
from app.services import deneme_service as ds
from app.services.task_titles import refresh_auto_title


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="YYYY-MM-DD (varsayılan: bugün − 14 gün)")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    since = date.fromisoformat(a.since) if a.since else date.fromordinal(date.today().toordinal() - 14)

    with SessionLocal() as db:
        rows = (
            db.query(TaskBookItem, Task, Book)
            .join(Task, Task.id == TaskBookItem.task_id)
            .join(Book, Book.id == TaskBookItem.book_id)
            .filter(
                Book.type.in_(list(ds.DENEME_BOOK_TYPES)),
                TaskBookItem.exam_kind.is_(None),
                Task.status != TaskStatus.COMPLETED,
                Task.date >= since,
            )
            .order_by(Task.date, Task.id, TaskBookItem.id)
            .all()
        )
        touched: set[int] = set()
        added = 0
        for it, task, book in rows:
            section = db.get(BookSection, it.book_section_id) if it.book_section_id else None
            qn, _ = ds.resolve_question_count(book=book, section=section, subject=book.subject)
            kind = ds.EXAM_KIND_BRANS if book.type == ds.DENEME_BOOK_TYPES[0] else ds.EXAM_KIND_GENEL
            exam_section = ds.exam_section_for_subject(book.subject)
            n = max(1, int(it.planned_count or 1))
            done = int(it.completed_count or 0)
            print(f"  görev #{task.id} {task.date} öğr #{task.student_id} · {task.title[:60]} · {n} deneme ({done} çözüldü)")
            it.exam_kind, it.exam_section, it.question_count = kind, exam_section, qn
            it.planned_count = 1
            it.completed_count = 1 if done >= 1 else 0
            if done < 1:
                it.correct_count = it.wrong_count = it.blank_count = None
            for k in range(1, n):
                db.add(TaskBookItem(
                    task_id=task.id, book_id=it.book_id, book_section_id=it.book_section_id,
                    planned_count=1, completed_count=1 if done > k else 0,
                    reservation_released_at=it.reservation_released_at,
                    exam_kind=kind, exam_section=exam_section, question_count=qn,
                ))
                added += 1
            touched.add(task.id)
        db.flush()
        for tid in touched:
            t = db.get(Task, tid)
            db.refresh(t)
            refresh_auto_title(t)
        print(f"\n{len(rows)} kalem · {len(touched)} görev · {added} yeni kalem")
        if a.apply:
            db.commit()
            print("UYGULANDI")
        else:
            db.rollback()
            print("kuru çalışma — yazmak için --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
