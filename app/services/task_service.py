"""Görev-rezerv yönetimi.

Model C (Melez):
- reserved_count = göreve atandığı için bloke edilmiş test sayısı
- completed_count = çözülmüş test sayısı
- remaining = test_count - reserved_count - completed_count
- Kısıt: reserved + completed ≤ test_count (her BookSection için)

Görev oluşturulurken rezerv artırılır; silinirken iade edilir.
Tamamlama (Sprint 3) reserved'den completed'e transfer eder.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    TaskBookItem,
)


class ReservationError(ValueError):
    """Rezerv kapasitesi aşıldığında veya veri tutarsızlığında atılır."""


def _get_progress(
    db: Session, student_id: int, book_id: int, section_id: int
) -> tuple[SectionProgress, BookSection]:
    sb = (
        db.query(StudentBook)
        .filter(StudentBook.student_id == student_id, StudentBook.book_id == book_id)
        .first()
    )
    if not sb:
        raise ReservationError("Bu öğrenciye bu kitap atanmamış.")
    section = db.query(BookSection).filter(BookSection.id == section_id).first()
    if not section or section.book_id != book_id:
        raise ReservationError("Bölüm (ünite/deneme) kitapla eşleşmiyor.")
    progress = (
        db.query(SectionProgress)
        .filter(
            SectionProgress.student_book_id == sb.id,
            SectionProgress.book_section_id == section.id,
        )
        .first()
    )
    if not progress:
        # Kitap sonradan ünite eklenmiş olabilir — eksik kaydı yarat
        progress = SectionProgress(
            student_book_id=sb.id,
            book_section_id=section.id,
            reserved_count=0,
            completed_count=0,
        )
        db.add(progress)
        db.flush()
    return progress, section


def reserve_item(
    db: Session,
    *,
    student_id: int,
    book_id: int,
    section_id: int,
    count: int,
) -> SectionProgress:
    """Rezerv ekle. Kapasite aşılırsa ReservationError."""
    if count < 1:
        raise ReservationError("Test sayısı en az 1 olmalı.")
    progress, section = _get_progress(db, student_id, book_id, section_id)
    if progress.reserved_count + progress.completed_count + count > section.test_count:
        kalan = section.test_count - progress.reserved_count - progress.completed_count
        raise ReservationError(
            f"Bu üniteden sadece {kalan} test kaldı; {count} rezerv edilemez."
        )
    progress.reserved_count += count
    return progress


def release_item(
    db: Session,
    *,
    student_id: int,
    book_id: int,
    section_id: int,
    count: int,
) -> SectionProgress:
    """Rezerv geri iade. count negatife inmez; gerekirse sıfıra kırpar."""
    progress, _ = _get_progress(db, student_id, book_id, section_id)
    progress.reserved_count = max(0, progress.reserved_count - count)
    return progress


def complete_item(
    db: Session,
    *,
    student_id: int,
    book_id: int,
    section_id: int,
    count: int,
) -> SectionProgress:
    """Rezerv edilmiş miktarı çözüldü olarak işaretle (reserved → completed).
    Sprint 3'te öğrenci tikleme tarafında kullanılır.
    """
    if count < 1:
        raise ReservationError("Tamamlanan test sayısı en az 1 olmalı.")
    progress, section = _get_progress(db, student_id, book_id, section_id)
    # Eğer rezervde yeterli yoksa, önce rezerv et (bu durum kısmi manuel tamamlama için)
    needed_reserve = count - progress.reserved_count
    if needed_reserve > 0:
        if progress.reserved_count + progress.completed_count + needed_reserve > section.test_count:
            kalan = section.test_count - progress.reserved_count - progress.completed_count
            raise ReservationError(
                f"Tamamlanacak test sayısı kalan kapasiteyi aşıyor (kalan: {kalan})."
            )
        progress.reserved_count += needed_reserve
    progress.reserved_count -= count
    progress.completed_count += count
    return progress


def release_task_items(db: Session, student_id: int, items: list[TaskBookItem]) -> None:
    """Bir görevin tüm kalemlerinin rezervini iade et (görev silme/düzenleme)."""
    for it in items:
        if it.book_id is None:
            continue  # kitapsız deneme kalemi — rezerv yok, iade gerekmez
        # Sadece henüz tamamlanmamış kısmı rezervden iade et
        remaining_reserved = max(0, it.planned_count - it.completed_count)
        if remaining_reserved > 0:
            release_item(
                db,
                student_id=student_id,
                book_id=it.book_id,
                section_id=it.book_section_id,
                count=remaining_reserved,
            )
        # completed kısmı çözüldüye sayılır, geri alınmaz


def complete_task(db: Session, task) -> None:
    """Görevdeki tüm kalemleri planlanan miktar kadar çözüldüye çevir.
    Her kalem için: reserved'den (planned - already_completed) kadarını completed'e transfer et.
    """
    from app.models import TaskStatus  # lokal import — döngü önlemek için

    student_id = task.student_id
    for it in task.book_items:
        to_complete = it.planned_count - it.completed_count
        if to_complete <= 0:
            continue
        if it.book_id is None:
            # Kitapsız deneme kalemi: rezerv/kapasite yok, doğrudan tamamla.
            it.completed_count = it.planned_count
            continue
        progress, section = _get_progress(
            db, student_id, it.book_id, it.book_section_id
        )
        # Güvenlik: rezerv yetersizse rezerv kapasitesi izin veriyorsa ekle
        needed_reserve = to_complete - progress.reserved_count
        if needed_reserve > 0:
            if (
                progress.reserved_count + progress.completed_count + needed_reserve
                > section.test_count
            ):
                kalan = section.test_count - progress.reserved_count - progress.completed_count
                raise ReservationError(
                    f"Tamamlama kapasiteyi aşıyor (kalan {kalan})."
                )
            progress.reserved_count += needed_reserve
        progress.reserved_count -= to_complete
        progress.completed_count += to_complete
        it.completed_count = it.planned_count
    task.status = TaskStatus.COMPLETED
    from datetime import datetime, timezone
    task.completed_at = datetime.now(timezone.utc)


def uncomplete_task(db: Session, task) -> None:
    """Tamamlamayı geri al. Her kalem için completed miktarı tekrar reserved'e döner."""
    from app.models import TaskStatus

    student_id = task.student_id
    for it in task.book_items:
        if it.completed_count <= 0:
            continue
        if it.book_id is None:
            it.completed_count = 0  # kitapsız deneme kalemi — rezerv yok
            continue
        progress, section = _get_progress(
            db, student_id, it.book_id, it.book_section_id
        )
        back = it.completed_count
        progress.completed_count = max(0, progress.completed_count - back)
        progress.reserved_count += back
        # Kitap kapasitesini aşma ihtimali: teorik olarak aşmaz çünkü completed+reserved
        # toplamı yine aynı kalıyor.
        it.completed_count = 0
    task.status = TaskStatus.PENDING
    task.completed_at = None


def set_item_completion(db: Session, item: TaskBookItem, new_completed: int) -> None:
    """Tek bir kalemin tamamlanan sayısını manuel ayarla (kısmi tamamlama).
    new_completed: 0..planned_count arası. SectionProgress'i uygun şekilde günceller.
    """
    from app.models import TaskStatus

    if new_completed < 0:
        new_completed = 0
    if new_completed > item.planned_count:
        new_completed = item.planned_count
    delta = new_completed - item.completed_count
    if delta == 0:
        return
    if item.book_id is None:
        # Kitapsız deneme kalemi: rezerv/kapasite yok, doğrudan ayarla.
        item.completed_count = new_completed
        return
    progress, section = _get_progress(
        db, item.task.student_id, item.book_id, item.book_section_id
    )
    if delta > 0:
        # completed'i artır, reserved'den al (yetmiyorsa kapasiteyi kontrol et)
        needed_reserve = delta - progress.reserved_count
        if needed_reserve > 0:
            if (
                progress.reserved_count + progress.completed_count + needed_reserve
                > section.test_count
            ):
                kalan = section.test_count - progress.reserved_count - progress.completed_count
                raise ReservationError(
                    f"Tamamlama kapasiteyi aşıyor (kalan {kalan})."
                )
            progress.reserved_count += needed_reserve
        progress.reserved_count -= delta
        progress.completed_count += delta
    else:
        # completed azalıyor, geri rezerve dön
        progress.completed_count = max(0, progress.completed_count + delta)  # delta negatif
        progress.reserved_count -= delta  # delta negatif; yani arttırır
    item.completed_count = new_completed
    # Görev durumu güncelleme çağrı yerinde yapılabilir

