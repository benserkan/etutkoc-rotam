"""SALT OKUMA — aynı öğrencide aynı adı taşıyan birden çok aktif kitap kaydı (2026-09-29).

Kullanım: python -m scripts.diagnose_duplicate_books
Her grup için: kitap id, sahibi, kaynağı, bölüm sayısı/test, öğrencinin ilerlemesi,
görev kalemi sayısı, aktif rezerv, bölüm yapısı birebir mi.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Book, BookSection, SectionProgress, StudentBook, Task, TaskBookItem, User


def norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def main() -> None:
    with SessionLocal() as db:
        rows = (db.query(StudentBook, Book).join(Book, Book.id == StudentBook.book_id)
                .filter(StudentBook.archived_at.is_(None)).all())
        groups: dict[tuple, list] = defaultdict(list)
        for sb, b in rows:
            groups[(sb.student_id, b.subject_id, norm(b.name))].append((sb, b))
        dup = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"Aktif atama: {len(rows)} · aynı adlı çoklu grup: {len(dup)}\n")
        for (sid, _subj, name), items in sorted(dup.items()):
            st = db.get(User, sid)
            print(f"#{sid} {st.full_name if st else '?'} · {items[0][1].name}")
            sigs = []
            for sb, b in items:
                secs = (db.query(BookSection).filter(BookSection.book_id == b.id)
                        .order_by(BookSection.order, BookSection.id).all())
                sig = [(norm(s.label), s.test_count) for s in secs]
                sigs.append(sig)
                prog = (db.query(func.coalesce(func.sum(SectionProgress.completed_count), 0),
                                 func.coalesce(func.sum(SectionProgress.reserved_count), 0))
                        .filter(SectionProgress.student_book_id == sb.id).one())
                items_n = (db.query(func.count(TaskBookItem.id)).join(Task, Task.id == TaskBookItem.task_id)
                           .filter(Task.student_id == sid, TaskBookItem.book_id == b.id).scalar())
                others = (db.query(func.count(StudentBook.id))
                          .filter(StudentBook.book_id == b.id, StudentBook.student_id != sid).scalar())
                print(f"   kitap #{b.id} sahip {b.teacher_id} kaynak {b.source_kind} · {len(secs)} bölüm "
                      f"{sum(s.test_count for s in secs)} test · çözülen {prog[0]} rezerv {prog[1]} · "
                      f"görev kalemi {items_n} · başka öğrencide {others} · atama {sb.assigned_at:%Y-%m-%d}")
            same = all(s == sigs[0] for s in sigs)
            print(f"   bölüm yapısı birebir: {'EVET' if same else 'HAYIR'}\n")


if __name__ == "__main__":
    main()
