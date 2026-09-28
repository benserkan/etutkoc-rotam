"""TAMAMLAMA — tek tanım (2026-09-28, kullanıcı kararı).

Kurum panelinde "Tamamlama" dört farklı hesapla üretiliyordu (takvim haftası /
kayan 7 gün, deneme ve taslak dahil / hariç, kaynaksız test sayılır / sayılmaz).
Artık her yüzey bu modülden beslenir:

    TAMAMLAMA = çözülen test ÷ planlanan test
      · dönem: son 7 gün, bugün dahil (kayan pencere; `WINDOW_DAYS`)
      · yalnız YAYINLANMIŞ görevler (taslak sayılmaz)
      · yalnız TEST kalemleri: soru bankası kitabı (deneme kitabı hariç) ya da
        kaynaksız ama konuya bağlı kalem (P2 "kaynak belirtmeden ver")
      · denemeler (branş/genel/kitapsız tam deneme) ve etkinlik görevleri
        (video, özet, tekrar, diğer, iş bloğu) GİRMEZ

"Programı var mı?" sorusu BU ölçü değildir — görev SAYISI ile cevaplanır (yalnız
etkinlik görevi olan hafta da programlıdır).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models import Book, Task, TaskBookItem
from app.services.gorev_stats import DENEME_BOOK_TYPES

WINDOW_DAYS = 7


def window(end: date, days: int = WINDOW_DAYS) -> tuple[date, date]:
    """`end` dahil geriye `days` günlük pencere."""
    return end - timedelta(days=days - 1), end


def item_counts(item) -> bool:
    """Görev kalemi tamamlama hesabına girer mi (Python tarafı)."""
    if getattr(item, "book_id", None) is None:
        return getattr(item, "topic_id", None) is not None
    book = getattr(item, "book", None)
    return book is not None and book.type not in DENEME_BOOK_TYPES


def test_item_filter():
    """SQL karşılığı — sorgu `Book`'u TaskBookItem'a OUTER JOIN etmiş olmalı."""
    return or_(
        and_(TaskBookItem.book_id.isnot(None), Book.type.notin_(list(DENEME_BOOK_TYPES))),
        and_(TaskBookItem.book_id.is_(None), TaskBookItem.topic_id.isnot(None)),
    )


@dataclass
class Totals:
    planned: int = 0
    completed: int = 0
    correct: int = 0
    wrong: int = 0

    @property
    def rate(self) -> int | None:
        return rate(self.planned, self.completed)


def rate(planned: int, completed: int) -> int | None:
    if planned <= 0:
        return None
    return int(round(100 * completed / planned))


def student_totals(
    db: Session, student_ids: list[int], start: date, end: date,
) -> dict[int, Totals]:
    """Öğrenci başına planlanan/çözülen test + doğru/yanlış (tek sorgu)."""
    if not student_ids or end < start:
        return {}
    rows = (
        db.query(
            Task.student_id.label("sid"),
            func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("p"),
            func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("c"),
            func.coalesce(func.sum(TaskBookItem.correct_count), 0).label("ok"),
            func.coalesce(func.sum(TaskBookItem.wrong_count), 0).label("no"),
        )
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .outerjoin(Book, Book.id == TaskBookItem.book_id)
        .filter(
            Task.student_id.in_(student_ids),
            Task.is_draft.is_(False),
            Task.date >= start,
            Task.date <= end,
            test_item_filter(),
        )
        .group_by(Task.student_id)
        .all()
    )
    return {
        int(r.sid): Totals(int(r.p), int(r.c), int(r.ok), int(r.no))
        for r in rows
    }


def sum_totals(totals) -> Totals:
    out = Totals()
    for t in totals:
        out.planned += t.planned
        out.completed += t.completed
        out.correct += t.correct
        out.wrong += t.wrong
    return out
