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

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskStatus,
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
        # "Ölü rezerv" zaten serbest bırakılmışsa (haftası geçmiş görev reconcile
        # ile çözülmüş) → tekrar iade ETME (çift-iade rezervi yanlış düşürür).
        if it.reservation_released_at is not None:
            continue
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


def reconcile_past_reservations(
    db: Session,
    *,
    student_id: int,
    cutoff_date: date,
) -> dict:
    """'Ölü rezervi' serbest bırak — haftası/programı geçmiş, tamamlanmamış,
    yayında görevlerin yapılmamış rezerv kısmını kapasiteye iade et (idempotent).

    Ölü rezerv = `task.date < cutoff_date` AND `status != COMPLETED` AND
    `is_draft == False` olan görevlerin, henüz serbest bırakılmamış
    (reservation_released_at IS NULL) section'lı kalemlerinin (planned - completed)
    kısmı. Görev kaydı (planned/completed/geçmiş) DEĞİŞMEZ — yalnız rezerv kilidi
    kalkar; kalem `reservation_released_at` ile işaretlenir (tekrar iade edilmez).

    cutoff_date genelde aktif programın start_date'i (geçmiş haftalar < cutoff).

    Returns: {"released_tests": int, "released_items": int}.
    """
    items = (
        db.query(TaskBookItem)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(
            Task.student_id == student_id,
            Task.date < cutoff_date,
            Task.status != TaskStatus.COMPLETED,
            Task.is_draft.is_(False),
            TaskBookItem.book_section_id.isnot(None),
            TaskBookItem.reservation_released_at.is_(None),
        )
        .all()
    )
    released_tests = 0
    released_items = 0
    now = datetime.now(timezone.utc)
    for it in items:
        remaining = max(0, it.planned_count - it.completed_count)
        if remaining <= 0:
            # Tam tamamlanmış (yapılmamış kısım yok) — yine de işaretle ki bir daha
            # bakılmasın; rezerv değişmez.
            it.reservation_released_at = now
            continue
        release_item(
            db,
            student_id=student_id,
            book_id=it.book_id,
            section_id=it.book_section_id,
            count=remaining,
        )
        it.reservation_released_at = now
        released_tests += remaining
        released_items += 1
    return {"released_tests": released_tests, "released_items": released_items}


def reconcile_all_active_reservations(
    db: Session, *, today: date | None = None,
) -> dict:
    """Günlük cron: rezervli HER öğrencide 'ölü rezervi' otomatik serbest bırak.

    Koç yeni program/görev-ekle/devret yapmasa bile (yaz tatili veya program-arası
    boşluk) ölü rezerv birikmesin. Her öğrenci için cutoff = aktif program start
    (varsa) yoksa BU HAFTANIN Pazartesi'si — `create_program` ile AYNI mantık
    (cari hafta korunur, yalnız geçmiş haftalar serbest kalır). Yalnız
    `reserved_count>0` olan öğrenciler taranır (verimli). reconcile idempotent +
    release-only → tekrar çalışması güvenli.

    Returns: {students_scanned, students_released, released_tests, released_items}.
    """
    from datetime import timedelta as _td

    from app.services.weekly_program_service import get_active_program

    if today is None:
        today = date.today()
    this_monday = today - _td(days=today.weekday())

    student_ids = [
        sid for (sid,) in (
            db.query(StudentBook.student_id)
            .join(SectionProgress, SectionProgress.student_book_id == StudentBook.id)
            .filter(SectionProgress.reserved_count > 0)
            .distinct()
            .all()
        )
    ]
    released_tests = 0
    released_items = 0
    students_released = 0
    for sid in student_ids:
        active = get_active_program(db, student_id=sid, today=today)
        cutoff = active.start_date if active else this_monday
        res = reconcile_past_reservations(db, student_id=sid, cutoff_date=cutoff)
        if res["released_items"] > 0:
            students_released += 1
            released_tests += res["released_tests"]
            released_items += res["released_items"]
    return {
        "students_scanned": len(student_ids),
        "students_released": students_released,
        "released_tests": released_tests,
        "released_items": released_items,
    }


def release_due_reservations_for_pause(
    db: Session, *, student_id: int, today: date | None = None,
) -> dict:
    """Mola moduna (yaz molası) geçişte: BUGÜNE KADARKİ (date <= today) yapılmamış,
    yayında görevlerin ölü rezervini hemen serbest bırak. cutoff = today + 1 gün
    (bugün dahil) → cari haftanın bekleyen rezervleri de düşer (koç takibi
    duraklattı). GELECEK tarihli görevlerin rezervi KORUNUR (gerçek plan).
    İdempotent (reservation_released_at işaretli kalemler tekrar iade edilmez)."""
    from datetime import timedelta as _td

    if today is None:
        today = date.today()
    return reconcile_past_reservations(
        db, student_id=student_id, cutoff_date=today + _td(days=1),
    )


def list_carryover_candidates(
    db: Session,
    *,
    student_id: int,
    cutoff_date: date,
    since_date: date | None = None,
    include_plain_tests: bool = False,
) -> list[dict]:
    """Devret adayları — GÖREV düzeyinde 'yapılmadan kalan' görevler.

    `since_date <= task.date < cutoff_date` + `status != COMPLETED` + yayında +
    `carried_at IS NULL` (henüz taşınmamış) görevler. Görev düzeyinde tek aday;
    her aday: görevin YAPILMAMIŞ section kalemleri (planned-completed>0) + itemless
    kalemleri + toplam kalan. Görev taşınınca `carried_at` ile işaretlenir → düşer.

    `include_plain_tests=False` (plan modu, varsayılan): düz TEST görevleri (kitaptan
    section, blok değil, kitapsız kalem yok) LİSTELENMEZ — rezerv reconcile ile
    iade edildi, kitapta 'çözülmedi' görünür. `True` (browse modu, geçmiş program
    BİLGİ AMAÇLI): TÜM tipler (test dahil) listelenir.
    """
    q = (
        db.query(Task)
        .options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        .filter(
            Task.student_id == student_id,
            Task.date < cutoff_date,
            Task.status != TaskStatus.COMPLETED,
            Task.is_draft.is_(False),
            Task.carried_at.is_(None),
        )
    )
    if since_date is not None:
        q = q.filter(Task.date >= since_date)
    tasks = q.order_by(Task.date.asc(), Task.order.asc(), Task.id.asc()).all()

    out: list[dict] = []
    for t in tasks:
        section_items: list[dict] = []
        itemless: list[dict] = []
        total_remaining = 0
        for it in t.book_items:
            if it.book_section_id is not None:
                rem = max(0, it.planned_count - it.completed_count)
                if rem <= 0:
                    continue
                book = it.book
                section = it.section
                if book is None or section is None:
                    continue
                section_items.append({
                    "book_id": it.book_id,
                    "section_id": it.book_section_id,
                    "book_name": book.name,
                    "section_label": (getattr(section, "label", None)
                                      or getattr(section, "name", "") or ""),
                    "remaining": rem,
                })
                total_remaining += rem
            else:
                # Kitapsız (deneme / blok-counter) kalem — yapılmamışsa taşınır.
                rem = max(0, it.planned_count - it.completed_count)
                itemless.append({
                    "label": it.label or t.title,
                    "count": it.planned_count,
                })
                total_remaining += rem
        is_activity = len(t.book_items) == 0
        is_block = t.work_block_id is not None
        # DÜZ TEST görevi (kitaptan section, blok DEĞİL, kitapsız kalem yok) →
        # PLAN modunda LİSTELENMEZ (rezerv iade edildi, kitapta 'çözülmedi' görünür;
        # koç normal akıştan yeniden atar). BROWSE modunda (geçmiş program, bilgi
        # amaçlı) TÜM görevler listelenir → include_plain_tests=True ile gösterilir.
        if (not include_plain_tests
                and section_items and not is_block and not itemless and not is_activity):
            continue
        # Gösterilecek içerik yoksa atla.
        if not section_items and not itemless and not is_activity:
            continue
        out.append({
            "task_id": t.id,
            "task_date": t.date,
            "title": t.title,
            "type": t.type.value if hasattr(t.type, "value") else str(t.type),
            "is_activity": is_activity,
            "is_block": t.work_block_id is not None,
            "period": t.period,
            "section_items": section_items,
            "itemless_items": itemless,
            "total_remaining": total_remaining,
        })
    return out


def mark_task_carried(db: Session, task: Task) -> None:
    """Görevi 'taşındı' olarak işaretle (devret listesinden düşsün)."""
    if task.carried_at is None:
        task.carried_at = datetime.now(timezone.utc)


def complete_task(
    db: Session,
    task,
    *,
    correct: int | None = None,
    wrong: int | None = None,
) -> None:
    """Görevdeki tüm kalemleri planlanan miktar kadar çözüldüye çevir.
    Her kalem için: reserved'den (planned - already_completed) kadarını completed'e transfer et.

    Opsiyonel `correct` / `wrong`: yalnız **tek kalemli** görevlerde anlamlı (tek
    tıkla tamamla sheet'i). Çoklu kalemli görevlerde kalem-bazlı set_item_completion
    ile girilir; bu params yok sayılır.

    Validation çağrı yerinde (endpoint Pydantic body) yapılır; servis defansif
    olarak yalnız non-negatif değerleri yazar.
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
    # Tek kalemli görevde D/Y uygulanır (mobil "Tamam + sayıyla" sheet'i).
    if len(task.book_items) == 1 and (correct is not None or wrong is not None):
        single = task.book_items[0]
        if correct is not None and correct >= 0:
            single.correct_count = correct
        if wrong is not None and wrong >= 0:
            single.wrong_count = wrong
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
        # Tamamlama geri alınınca D/Y de sıfırlanır — eski sonucun stale kalmasını önle.
        it.correct_count = None
        it.wrong_count = None
    task.status = TaskStatus.PENDING
    task.completed_at = None


def set_item_completion(
    db: Session,
    item: TaskBookItem,
    new_completed: int,
    *,
    correct: int | None = None,
    wrong: int | None = None,
) -> None:
    """Tek bir kalemin tamamlanan sayısını manuel ayarla (kısmi tamamlama).
    new_completed: 0..planned_count arası. SectionProgress'i uygun şekilde günceller.

    Opsiyonel `correct` / `wrong`: bu kalem için doğru/yanlış sonucu.
    Endpoint validation: correct + wrong ≤ new_completed. Servis defansif:
      - new_completed == 0 → D/Y de None'a düşer (tutarlılık)
      - sentinel `None` geçilirse alan güncellenmez (mevcut değer korunur)
      - `0` geçilirse alan 0 olarak yazılır (kullanıcı eski D/Y'yi temizleyebilir)
    """
    from app.models import TaskStatus

    if new_completed < 0:
        new_completed = 0
    if new_completed > item.planned_count:
        new_completed = item.planned_count
    delta = new_completed - item.completed_count
    if delta == 0:
        # Sayım değişmediyse bile D/Y güncellemesi yapılabilir (örn. öğrenci
        # tamamlama yaptıktan sonra D/Y'yi sonradan girer).
        _apply_result_fields(item, new_completed, correct, wrong)
        return
    if item.book_id is None:
        # Kitapsız deneme kalemi: rezerv/kapasite yok, doğrudan ayarla.
        item.completed_count = new_completed
        _apply_result_fields(item, new_completed, correct, wrong)
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
    _apply_result_fields(item, new_completed, correct, wrong)
    # Görev durumu güncelleme çağrı yerinde yapılabilir


def _apply_result_fields(
    item: TaskBookItem,
    new_completed: int,
    correct: int | None,
    wrong: int | None,
) -> None:
    """D/Y alanlarını item üzerine güvenle uygula.

    - new_completed == 0 → D/Y daima None (tamamlama yoksa sonuç da yok)
    - sentinel None → alan değişmez (kullanıcı güncellemedi)
    - sayı geçildi → alan üzerine yazılır (0 da yazılır — "sıfırla" anlamı)

    Bu helper, D/Y validation'ını **yapmaz** (correct+wrong ≤ completed kuralı
    endpoint Pydantic body'sinde uygulanır; servis pratik klamp yapar).
    """
    if new_completed == 0:
        item.correct_count = None
        item.wrong_count = None
        return
    if correct is not None:
        item.correct_count = max(0, correct)
    if wrong is not None:
        item.wrong_count = max(0, wrong)


