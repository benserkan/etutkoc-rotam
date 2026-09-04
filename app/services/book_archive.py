"""Öğrenci kitap arşivi — TEK MERKEZ (P4, 2026-09-04).

Neden: sınıf atlayınca geçen yılın kitapları kütüphanede kalıyor ve zamanla
yönetilemez oluyordu (8→9 geçen Yiğit'te 58 kitap ataması). Silme YANLIŞ —
yaz tekrarı için kitap hâlâ gerekebilir ve görev geçmişi kitaba bağlı.

ARŞİV = SOFT + GERİ ALINABİLİR. `student_books.archived_at` dolu demektir:
  · Kayıt SİLİNMEZ; görev geçmişi, sayaçlar (SectionProgress), deneme/analiz
    yüzeyleri AYNEN kalır.
  · Yalnız İLERİYE DÖNÜK yüzeylerde gizlenir: kitap paneli, öğrenci
    "Kitaplarım", görev kaynak seçici, öneri motoru, müfredat kapsama,
    bağımsız çalışma bildirimi.
  · Arşivli kitaba YENİ GÖREV ATANAMAZ (gizli kaynağa atama tutarsızlık olur);
    arşivden önce oluşturulmuş görevler bozulmadan çalışmaya devam eder.

Yeniden atama (`assign`) arşivden ÇIKARIR — koç kitabı tekrar kullanmak
isterse ayrıca "geri al" demek zorunda kalmaz.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Book, StudentBook


def _now() -> datetime:
    return datetime.now(timezone.utc)


def set_archived(
    db: Session, student_id: int, book_ids: list[int], *, archived: bool
) -> int:
    """Kitapları arşivle / arşivden çıkar. Değişen kayıt sayısını döndürür.

    İdempotent: zaten istenen durumda olan kayıt sayılmaz.
    """
    if not book_ids:
        return 0
    rows = (
        db.query(StudentBook)
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.book_id.in_(book_ids),
        )
        .all()
    )
    changed = 0
    stamp = _now() if archived else None
    for sb in rows:
        if bool(sb.archived_at) == archived:
            continue
        sb.archived_at = stamp
        changed += 1
    if changed:
        db.flush()
    return changed


def archived_count(db: Session, student_id: int) -> int:
    return (
        db.query(StudentBook)
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.isnot(None),
        )
        .count()
    )


def archive_candidates(
    db: Session, student_id: int, *, before: date | None
) -> list[dict]:
    """Arşiv adayları: `before` tarihinden ÖNCE atanmış, hâlâ aktif kitaplar.

    Sınıf yükseltme sonrası "geçen dönemin kitaplarını arşivleyelim mi?" adımı
    bunu kullanır; `before` = güncel dönemin başlangıcı (P2 sınırı).
    """
    q = (
        db.query(StudentBook)
        .options(joinedload(StudentBook.book).joinedload(Book.subject))
        .filter(
            StudentBook.student_id == student_id,
            StudentBook.archived_at.is_(None),
        )
    )
    if before is not None:
        q = q.filter(StudentBook.assigned_at < datetime(
            before.year, before.month, before.day, tzinfo=timezone.utc
        ))
    rows = q.all()

    out: list[dict] = []
    for sb in rows:
        book = sb.book
        if book is None:
            continue
        subject = getattr(book, "subject", None)
        out.append(
            {
                "book_id": book.id,
                "book_name": book.name,
                "subject_name": getattr(subject, "name", None),
                "assigned_on": sb.assigned_at.date().isoformat()
                if sb.assigned_at
                else None,
                "total_tests": book.total_tests,
                "completed_tests": sum(
                    p.completed_count for p in sb.section_progress
                ),
                "reserved_tests": sum(
                    p.reserved_count for p in sb.section_progress
                ),
            }
        )
    out.sort(key=lambda r: ((r["subject_name"] or ""), r["book_name"]))
    return out
