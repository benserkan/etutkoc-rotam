# -*- coding: utf-8 -*-
"""Bağımsız çalışma kayıtları — TEK MERKEZ servis.

Tatil/koçsuz dönemde öğrencinin program dışında çözdüğü testlerin izli kaydı.
Tüm ilerleme yazımları (öğrenci beyanı onayı, koç doğrudan girişi, eski
"toplam çözülmüş" mutlak seti, silme/geri alma) buradan geçer:

- Uygulama anında bölümün boş kapasitesine KIRPILIR (test − rezerv − çözülmüş);
  uygulanan miktar entry.applied_count'ta saklanır → silme birebir geri alır.
- SectionProgress.manual_count elle/bağımsız eklenen toplamı taşır
  (completed = görevle çözülen + manual). AZALTMA yalnız manual kısımdan
  yapılabilir — görevle çözülen kısım görev üzerinden düzeltilir. Bu kural
  kurum koçunun görev-bazlı uyum metriklerini buradan oynayamamasının teminatı.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    SS_SOURCE_COACH,
    SS_SOURCE_STUDENT,
    SS_STATUS_APPROVED,
    SS_STATUS_PENDING,
    SS_STATUS_REJECTED,
    BookSection,
    SectionProgress,
    SelfStudyEntry,
    StudentBook,
    User,
)

logger = logging.getLogger(__name__)

# Tek kayıtta makul üst sınır (tek bölümün test sayısını zaten aşamaz; bu,
# bozuk istemci/istem dışı devasa sayılara karşı ikinci kemer).
MAX_ITEMS_PER_REQUEST = 100


class SelfStudyError(Exception):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_progress(
    db: Session, student_book_id: int, section_id: int
) -> SectionProgress:
    sp = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.student_book_id == student_book_id,
            SectionProgress.book_section_id == section_id,
        )
        .first()
    )
    if not sp:
        sp = SectionProgress(
            student_book_id=student_book_id,
            book_section_id=section_id,
            reserved_count=0,
            completed_count=0,
            manual_count=0,
        )
        db.add(sp)
        db.flush()
    return sp


def available_for(sp: SectionProgress, section: BookSection) -> int:
    """Bölümde uygulanabilir boş kapasite (test − rezerv − çözülmüş)."""
    return max(
        0,
        int(section.test_count or 0)
        - int(sp.reserved_count or 0)
        - int(sp.completed_count or 0),
    )


def _apply(db: Session, entry: SelfStudyEntry, sp: SectionProgress, section: BookSection) -> int:
    """Kaydı ilerlemeye uygula (kapasiteye kırparak). Uygulanan miktarı döner."""
    applied = min(int(entry.test_count), available_for(sp, section))
    entry.applied_count = applied
    if applied > 0:
        sp.completed_count = int(sp.completed_count or 0) + applied
        sp.manual_count = int(sp.manual_count or 0) + applied
    return applied


def create_entries(
    db: Session,
    *,
    student: User,
    actor: User,
    source: str,
    items: list[tuple[StudentBook, BookSection, int]],
    note: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[list[SelfStudyEntry], list[dict]]:
    """Toplu kayıt oluştur.

    source=coach → anında onaylı + uygulanır (kapasite 0 olan bölüm atlanır,
    skipped listesinde raporlanır). source=student → pending (ilerlemeye
    DOKUNMAZ; koç onaylayınca uygulanır).
    """
    if source not in (SS_SOURCE_COACH, SS_SOURCE_STUDENT):
        raise SelfStudyError("invalid_source", "Geçersiz kaynak.")
    if not items:
        raise SelfStudyError("no_items", "En az bir bölüm girmelisin.")
    if len(items) > MAX_ITEMS_PER_REQUEST:
        raise SelfStudyError("too_many_items", "Tek seferde en fazla 100 bölüm girilebilir.")

    created: list[SelfStudyEntry] = []
    skipped: list[dict] = []
    for sb, section, count in items:
        count = int(count)
        if count <= 0:
            continue
        if count > int(section.test_count or 0):
            skipped.append({
                "section_id": section.id,
                "section_label": section.label,
                "reason": f"Bölümde toplam {section.test_count} test var.",
            })
            continue
        entry = SelfStudyEntry(
            student_id=student.id,
            student_book_id=sb.id,
            book_section_id=section.id,
            test_count=count,
            source=source,
            status=SS_STATUS_PENDING,
            note=(note or None),
            period_start=period_start,
            period_end=period_end,
            created_by_id=actor.id,
        )
        if source == SS_SOURCE_COACH:
            sp = get_or_create_progress(db, sb.id, section.id)
            if available_for(sp, section) <= 0:
                skipped.append({
                    "section_id": section.id,
                    "section_label": section.label,
                    "reason": "Boş kapasite yok (tümü çözülmüş/rezerve).",
                })
                continue
            entry.status = SS_STATUS_APPROVED
            entry.reviewed_by_id = actor.id
            entry.reviewed_at = _now()
            db.add(entry)
            db.flush()
            _apply(db, entry, sp, section)
        else:
            db.add(entry)
            db.flush()
        created.append(entry)

    if not created and not skipped:
        raise SelfStudyError("no_items", "En az bir bölüme 1+ test girmelisin.")
    return created, skipped


def review_entry(
    db: Session,
    entry: SelfStudyEntry,
    *,
    approve: bool,
    reviewer: User,
    review_note: str | None = None,
) -> SelfStudyEntry:
    """Bekleyen öğrenci beyanını onayla (uygula) / reddet."""
    if entry.status != SS_STATUS_PENDING:
        raise SelfStudyError("not_pending", "Bu kayıt zaten sonuçlanmış.")
    if approve:
        sp = get_or_create_progress(db, entry.student_book_id, entry.book_section_id)
        section = db.get(BookSection, entry.book_section_id)
        if section is None:
            raise SelfStudyError("section_missing", "Bölüm bulunamadı.", status=404)
        if available_for(sp, section) <= 0:
            raise SelfStudyError(
                "no_capacity",
                "Bu bölümde uygulanacak boş kapasite kalmamış (tümü çözülmüş "
                "veya rezerve). Kaydı reddedebilirsin.",
            )
        entry.status = SS_STATUS_APPROVED
        _apply(db, entry, sp, section)
    else:
        entry.status = SS_STATUS_REJECTED
        entry.applied_count = 0
    entry.reviewed_by_id = reviewer.id
    entry.reviewed_at = _now()
    if review_note:
        entry.review_note = review_note
    return entry


def delete_entry(db: Session, entry: SelfStudyEntry) -> int:
    """Kaydı sil; uygulanmışsa etkisini birebir geri al. Geri alınan miktarı döner."""
    reverted = 0
    if entry.status == SS_STATUS_APPROVED and int(entry.applied_count or 0) > 0:
        sp = (
            db.query(SectionProgress)
            .filter(
                SectionProgress.student_book_id == entry.student_book_id,
                SectionProgress.book_section_id == entry.book_section_id,
            )
            .first()
        )
        if sp is not None:
            reverted = min(
                int(entry.applied_count),
                int(sp.manual_count or 0),
                int(sp.completed_count or 0),
            )
            sp.completed_count = int(sp.completed_count or 0) - reverted
            sp.manual_count = int(sp.manual_count or 0) - reverted
    db.delete(entry)
    return reverted


def set_absolute_completed(
    db: Session,
    *,
    student: User,
    sb: StudentBook,
    section: BookSection,
    actor: User,
    target: int,
    note: str | None = None,
) -> SectionProgress:
    """Eski "toplam çözülmüş = N" mutlak girişi (kitap paneli inline alanı).

    Artık izli: artış → koç kaydı (anında onaylı); azalış → yalnız MANUAL
    kısımdan düşülür (en yeni kayıtlardan geriye doğru). Görevle çözülen kısım
    buradan azaltılamaz (422 manual_reduce_exceeds).
    """
    sp = get_or_create_progress(db, sb.id, section.id)
    max_allowed = max(0, int(section.test_count or 0) - int(sp.reserved_count or 0))
    if target > max_allowed:
        raise SelfStudyError(
            "exceeds_available",
            f"En fazla {max_allowed} test işaretlenebilir "
            f"(bölüm {section.test_count} test, {sp.reserved_count} rezerv).",
        )
    delta = int(target) - int(sp.completed_count or 0)
    if delta > 0:
        entry = SelfStudyEntry(
            student_id=student.id,
            student_book_id=sb.id,
            book_section_id=section.id,
            test_count=delta,
            source=SS_SOURCE_COACH,
            status=SS_STATUS_APPROVED,
            note=(note or f"Toplam çözülmüş {target} olarak işaretlendi."),
            created_by_id=actor.id,
            reviewed_by_id=actor.id,
            reviewed_at=_now(),
        )
        db.add(entry)
        db.flush()
        _apply(db, entry, sp, section)
    elif delta < 0:
        reduce = -delta
        if reduce > int(sp.manual_count or 0):
            raise SelfStudyError(
                "manual_reduce_exceeds",
                f"Yalnız elle/bağımsız girilen kısım azaltılabilir (elle girilen: "
                f"{sp.manual_count}). Görevle çözülenler ilgili görev üzerinden düzeltilir.",
            )
        remaining = reduce
        entries = (
            db.query(SelfStudyEntry)
            .filter(
                SelfStudyEntry.student_book_id == sb.id,
                SelfStudyEntry.book_section_id == section.id,
                SelfStudyEntry.status == SS_STATUS_APPROVED,
                SelfStudyEntry.applied_count > 0,
            )
            .order_by(SelfStudyEntry.created_at.desc(), SelfStudyEntry.id.desc())
            .all()
        )
        for e in entries:
            if remaining <= 0:
                break
            take = min(int(e.applied_count), remaining)
            e.applied_count = int(e.applied_count) - take
            remaining -= take
            if e.applied_count == 0:
                db.delete(e)
        # Kalan (remaining>0) = backfill'den gelen, kayıtsız eski elle kısım —
        # manual_count guard'ı yeterli, doğrudan düşülür.
        sp.completed_count = int(sp.completed_count or 0) - reduce
        sp.manual_count = int(sp.manual_count or 0) - reduce
    return sp


def list_for_student(
    db: Session, student_id: int, *, limit: int = 100
) -> tuple[list[SelfStudyEntry], int]:
    """Öğrencinin kayıtları (yeni→eski) + bekleyen sayısı."""
    q = (
        db.query(SelfStudyEntry)
        .options(
            joinedload(SelfStudyEntry.section),
            joinedload(SelfStudyEntry.student_book).joinedload(StudentBook.book),
            joinedload(SelfStudyEntry.created_by),
        )
        .filter(SelfStudyEntry.student_id == student_id)
        .order_by(SelfStudyEntry.created_at.desc(), SelfStudyEntry.id.desc())
    )
    items = q.limit(limit).all()
    pending = (
        db.query(SelfStudyEntry)
        .filter(
            SelfStudyEntry.student_id == student_id,
            SelfStudyEntry.status == SS_STATUS_PENDING,
        )
        .count()
    )
    return items, pending
