"""Kitap → öğrenci atamasının TEK MERKEZİ (2026-09-27).

Öğrenciye kitap atamak her yerde aynı iki adımdır: StudentBook satırı + kitabın
her bölümü için 0-baseline SectionProgress. Arşivli atama "zaten var" SAYILMAZ —
yeniden atanınca arşivden çıkar (P4 kuralı). Commit ETMEZ; çağıran commit eder.

Kullananlar: öğrenci panelinden toplu atama (`/students/{id}/books/bulk`) ve
kitap setini birden çok öğrenciye uygulama (`/library/book-sets/{id}/apply`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models import Book, SectionProgress, StudentBook


@dataclass
class AssignOutcome:
    created: list[StudentBook] = field(default_factory=list)
    already_ids: list[int] = field(default_factory=list)      # zaten aktif atalı
    unarchived_ids: list[int] = field(default_factory=list)   # arşivden geri açıldı


def assign_books_to_student(db: Session, student_id: int, books: list[Book]) -> AssignOutcome:
    """Kitapları öğrenciye atar (idempotent). Kitap listesi sahiplik süzgecinden
    geçmiş olmalı (çağıranın işi)."""
    out = AssignOutcome()
    if not books:
        return out
    ids = [b.id for b in books]
    existing = {
        sb.book_id: sb
        for sb in db.query(StudentBook).filter(
            StudentBook.student_id == student_id, StudentBook.book_id.in_(ids)
        )
    }
    for book in books:
        sb = existing.get(book.id)
        if sb is not None:
            if sb.archived_at is not None:
                sb.archived_at = None
                out.unarchived_ids.append(book.id)
            else:
                out.already_ids.append(book.id)
            continue
        sb = StudentBook(student_id=student_id, book_id=book.id)
        db.add(sb)
        db.flush()
        for section in book.sections or []:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=section.id,
                reserved_count=0,
                completed_count=0,
            ))
        existing[book.id] = sb
        out.created.append(sb)
    return out


def grade_fits(student, target_min: int | None, target_max: int | None, target_graduate: bool) -> bool:
    """Öğrencinin sınıfı set/kitap hedefine uyuyor mu? Hedef yoksa her zaman uyar."""
    if target_min is None and target_max is None and not target_graduate:
        return True
    if student.is_graduate:
        return bool(target_graduate)
    g = student.grade_level
    if g is None:
        return True
    lo = target_min if target_min is not None else 1
    hi = target_max if target_max is not None else 12
    return lo <= g <= hi
