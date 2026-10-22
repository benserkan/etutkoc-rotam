"""Sayfa birimli kaynaksız görevlerde "kaldığı yer" — TEK MERKEZ (2026-10-22).

Koç bir kaynağı sayfa aralığıyla böler ("Hız Fen — s. 45–50", ertesi gün "s. 51–55").
Aralıklar kayıtlı tutulur; yeni görev girerken son verilen aralık gösterilir ve devam
sayfası önerilir. Süreklilik KİTAP NOTUNA göre aranır (aynı kitap konular arasında
akar); not yoksa konuya göre. Gün gün görevleri ve havuz kalemleri birlikte taranır.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import Book, StudentBook, Task, TaskBookItem, Topic
from app.models.pool import PoolItem


@dataclass
class LastRange:
    page_from: int
    page_to: int
    on: date | None
    note: str | None
    source: str  # "gorev" | "havuz"


@dataclass
class PageSuggestion:
    last: LastRange | None = None
    next_from: int | None = None
    notes: list[str] = field(default_factory=list)


def _norm(s: str | None) -> str:
    return (s or "").strip().casefold()


def suggest(db: Session, student_id: int, *, topic_id: int | None = None,
            note: str | None = None, exclude_task_id: int | None = None) -> PageSuggestion:
    out = PageSuggestion()
    cands: list[LastRange] = []

    q = (
        db.query(TaskBookItem, Task.date)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(Task.student_id == student_id, TaskBookItem.unit == "sayfa",
                TaskBookItem.page_to.isnot(None))
    )
    if exclude_task_id:
        # Düzenlenen görev kendi aralığını "son verilen" saymasın (2026-10-22)
        q = q.filter(Task.id != exclude_task_id)
    pq = db.query(PoolItem).filter(PoolItem.student_id == student_id, PoolItem.removed_at.is_(None),
                                   PoolItem.unit == "sayfa", PoolItem.page_to.isnot(None))
    if note and note.strip():
        key = _norm(note)
        rows = [(it, d) for it, d in q.all() if _norm(it.label) == key]
        prow = [p for p in pq.all() if _norm(p.label) == key]
    elif topic_id:
        rows = q.filter(TaskBookItem.topic_id == topic_id).all()
        prow = pq.filter(PoolItem.topic_id == topic_id).all()
    else:
        rows, prow = [], []
    for it, d in rows:
        cands.append(LastRange(it.page_from or it.page_to, it.page_to, d, it.label, "gorev"))
    for p in prow:
        on = p.created_at.date() if getattr(p, "created_at", None) else None
        cands.append(LastRange(p.page_from or p.page_to, p.page_to, on, p.label, "havuz"))
    if cands:
        # "Son" = en ileri sayfa (aynı kaynağı ilerleterek bölüyoruz); eşitlikte en yeni tarih.
        best = max(cands, key=lambda c: (c.page_to, c.on or date.min))
        out.last = best
        out.next_from = best.page_to + 1

    # Not önerileri: daha önce sayfa görevinde yazılan notlar + öğrencinin aktif kitapları.
    seen: set[str] = set()
    used = (
        db.query(TaskBookItem.label, func.max(Task.date))
        .join(Task, Task.id == TaskBookItem.task_id)
        .outerjoin(Topic, Topic.id == TaskBookItem.topic_id)
        .filter(Task.student_id == student_id, TaskBookItem.unit == "sayfa",
                TaskBookItem.label.isnot(None),
                # not yazılmayınca etiket konu adıdır — öneri listesine girmez
                or_(Topic.id.is_(None), TaskBookItem.label != Topic.name))
        .group_by(TaskBookItem.label)
        .order_by(func.max(Task.date).desc())
        .limit(10)
        .all()
    )
    books = (
        db.query(Book.name)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(StudentBook.student_id == student_id, StudentBook.archived_at.is_(None))
        .order_by(Book.name)
        .all()
    )
    for (name, *_rest) in list(used) + list(books):
        k = _norm(name)
        if name and k not in seen:
            seen.add(k)
            out.notes.append(name.strip())
    return out
