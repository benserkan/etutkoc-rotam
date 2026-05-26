"""TaskRequest iş kuralları — onay akışları ve uygulama mantığı.

Akış:
- create_change/remove/add/question → öğrenci talep oluşturur (status=pending)
- approve_request → öğretmen onaylar; talebin tipine göre uygulanır
  * CHANGE: ilgili Task'ı/TaskBookItem'ı günceller (rezerv farkı dengelenir)
  * REMOVE: Task silinir, rezerv tamamen iade edilir
  * ADD: yeni Task + TaskBookItem oluşturulur, rezerv açılır
  * QUESTION: sadece status=resolved (eylem yok)
- reject_request: status=rejected, teacher_response yazılabilir
- withdraw: öğrenci talebi geri çeker (sadece pending iken)
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    RequestStatus,
    RequestType,
    SectionProgress,
    StudentBook,
    Task,
    TaskBookItem,
    TaskRequest,
    TaskStatus,
    TaskType,
    User,
)
from app.services.email_service import (
    notify_student_request_resolved,
    notify_teacher_new_request,
)
from app.services.task_service import (
    ReservationError,
    release_item,
    release_task_items,
    reserve_item,
)


class RequestError(ValueError):
    pass


# ---------------------------- Oluşturma ----------------------------


def max_new_count_for_change(
    db: Session, task: Task, item: TaskBookItem
) -> int:
    """Bir görevin sayı değişikliği talebi için en fazla yeni sayıyı hesaplar.

    Formül: mevcut planlı + (üniteden kalan kapasite) + (aynı ünitede daha geç tarihli
    görevlerin rezerv edilebilir kalan kısmı). Geç görevlerden otomatik olarak rezerv
    çekilebileceği için bu sayı erişilebilir maksimumdur.
    """
    sp = (
        db.query(SectionProgress)
        .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
        .filter(
            StudentBook.student_id == task.student_id,
            SectionProgress.book_section_id == item.book_section_id,
        )
        .first()
    )
    section = db.query(BookSection).filter(BookSection.id == item.book_section_id).first()
    if not sp or not section:
        return item.planned_count
    kalan = section.test_count - sp.reserved_count - sp.completed_count

    # Aynı section'da geç tarihli görevlerin movable rezervleri
    future_movable = (
        db.query(func.coalesce(
            func.sum(TaskBookItem.planned_count - TaskBookItem.completed_count), 0
        ))
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(
            Task.student_id == task.student_id,
            Task.id != task.id,
            Task.date > task.date,
            TaskBookItem.book_section_id == item.book_section_id,
        )
        .scalar() or 0
    )
    return item.planned_count + kalan + int(future_movable)


def _ensure_teacher_id(student: User) -> int:
    if not student.teacher_id:
        raise RequestError("Öğrencinin öğretmeni atanmamış.")
    return student.teacher_id


def _notify_new_safe(req: TaskRequest) -> None:
    """E-posta bildirimini try/except ile güvene al; commit'e blok olmasın."""
    try:
        notify_teacher_new_request(req)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("notify_teacher_new_request failed")


def _notify_resolved_safe(req: TaskRequest, action: str) -> None:
    try:
        notify_student_request_resolved(req, action)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("notify_student_request_resolved failed")


def create_change_request(
    db: Session,
    *,
    student: User,
    task: Task,
    proposed_count: int | None = None,
    message: str | None = None,
) -> TaskRequest:
    if task.student_id != student.id:
        raise RequestError("Bu görev size ait değil.")
    if proposed_count is not None and proposed_count < 1:
        raise RequestError("Önerilen sayı 1'den küçük olamaz.")
    # Pre-doğrulama: kapasite (kalan + gelecek rezervler) yeterli mi?
    if proposed_count is not None and len(task.book_items) == 1:
        item = task.book_items[0]
        max_count = max_new_count_for_change(db, task, item)
        if proposed_count > max_count:
            raise RequestError(
                f"Bu üniteden en fazla {max_count} test çözebilirsin "
                f"(şu an {item.planned_count} planlı + kalan + gelecekteki diğer rezervlerin tamamı). "
                f"Talep edilen {proposed_count} bu sınırı aşıyor."
            )
    req = TaskRequest(
        student_id=student.id,
        teacher_id=_ensure_teacher_id(student),
        task_id=task.id,
        type=RequestType.CHANGE,
        status=RequestStatus.PENDING,
        message=(message or "").strip() or None,
        proposed_count=proposed_count,
    )
    db.add(req)
    db.flush()
    _notify_new_safe(req)
    return req


def create_replace_request(
    db: Session,
    *,
    student: User,
    task: Task,
    new_book_id: int,
    new_section_id: int,
    new_count: int,
    message: str | None = None,
) -> TaskRequest:
    if task.student_id != student.id:
        raise RequestError("Bu görev size ait değil.")
    if new_count < 1:
        raise RequestError("Yeni sayı 1'den küçük olamaz.")
    # Tamamlanmış kalem varsa engelle (öğretmen aşamasında da kontrol var, kullanıcıyı erken uyar)
    if any(it.completed_count > 0 for it in task.book_items):
        raise RequestError(
            "Bu görevde kısmen çözüm var. Tamamen değiştirmek yerine 'Çıkar' talebi gönderip yeni bir görev önermenizi öneririz."
        )
    req = TaskRequest(
        student_id=student.id,
        teacher_id=_ensure_teacher_id(student),
        task_id=task.id,
        type=RequestType.REPLACE,
        status=RequestStatus.PENDING,
        message=(message or "").strip() or None,
        proposed_book_id=new_book_id,
        proposed_section_id=new_section_id,
        proposed_count=new_count,
    )
    db.add(req)
    db.flush()
    _notify_new_safe(req)
    return req


def create_remove_request(
    db: Session,
    *,
    student: User,
    task: Task,
    message: str | None = None,
) -> TaskRequest:
    if task.student_id != student.id:
        raise RequestError("Bu görev size ait değil.")
    req = TaskRequest(
        student_id=student.id,
        teacher_id=_ensure_teacher_id(student),
        task_id=task.id,
        type=RequestType.REMOVE,
        status=RequestStatus.PENDING,
        message=(message or "").strip() or None,
    )
    db.add(req)
    db.flush()
    _notify_new_safe(req)
    return req


def create_add_request(
    db: Session,
    *,
    student: User,
    target_date: date,
    book_id: int,
    section_id: int,
    proposed_count: int,
    message: str | None = None,
) -> TaskRequest:
    if proposed_count < 1:
        raise RequestError("Önerilen sayı 1'den küçük olamaz.")
    req = TaskRequest(
        student_id=student.id,
        teacher_id=_ensure_teacher_id(student),
        task_id=None,
        type=RequestType.ADD,
        status=RequestStatus.PENDING,
        message=(message or "").strip() or None,
        proposed_book_id=book_id,
        proposed_section_id=section_id,
        proposed_count=proposed_count,
        proposed_date=target_date,
    )
    db.add(req)
    db.flush()
    _notify_new_safe(req)
    return req


def create_question(
    db: Session,
    *,
    student: User,
    task: Task | None,
    message: str,
) -> TaskRequest:
    msg = (message or "").strip()
    if not msg:
        raise RequestError("Mesaj boş olamaz.")
    if task and task.student_id != student.id:
        raise RequestError("Bu görev size ait değil.")
    req = TaskRequest(
        student_id=student.id,
        teacher_id=_ensure_teacher_id(student),
        task_id=task.id if task else None,
        type=RequestType.QUESTION,
        status=RequestStatus.PENDING,
        message=msg,
    )
    db.add(req)
    db.flush()
    _notify_new_safe(req)
    return req


# ---------------------------- Onay / Red / Geri çekme ----------------------------


def withdraw_request(db: Session, *, student: User, req: TaskRequest) -> None:
    if req.student_id != student.id:
        raise RequestError("Bu talep size ait değil.")
    if req.status != RequestStatus.PENDING:
        raise RequestError("Sadece bekleyen talepler geri çekilebilir.")
    req.status = RequestStatus.WITHDRAWN
    req.responded_at = datetime.now(timezone.utc)


def reject_request(
    db: Session, *, teacher: User, req: TaskRequest, response: str | None = None
) -> None:
    if req.teacher_id != teacher.id:
        raise RequestError("Bu talep size ait değil.")
    if req.status != RequestStatus.PENDING:
        raise RequestError("Sadece bekleyen talepler reddedilebilir.")
    req.status = RequestStatus.REJECTED
    req.teacher_response = (response or "").strip() or None
    req.responded_at = datetime.now(timezone.utc)
    _notify_resolved_safe(req, "rejected")


def respond_question(
    db: Session, *, teacher: User, req: TaskRequest, response: str
) -> None:
    if req.teacher_id != teacher.id:
        raise RequestError("Bu talep size ait değil.")
    if req.status != RequestStatus.PENDING:
        raise RequestError("Bu talep zaten yanıtlanmış.")
    if req.type != RequestType.QUESTION:
        raise RequestError("Sadece sorular için cevap yazılır.")
    if not (response or "").strip():
        raise RequestError("Cevap boş olamaz.")
    req.teacher_response = response.strip()
    req.status = RequestStatus.RESOLVED
    req.responded_at = datetime.now(timezone.utc)
    _notify_resolved_safe(req, "answered")


def approve_request(
    db: Session, *, teacher: User, req: TaskRequest, response: str | None = None
) -> Task | None:
    """Talebi onayla ve uygula. Uygulanan/yeni Task döner (varsa)."""
    if req.teacher_id != teacher.id:
        raise RequestError("Bu talep size ait değil.")
    if req.status != RequestStatus.PENDING:
        raise RequestError("Sadece bekleyen talepler onaylanabilir.")

    affected_task: Task | None = None

    if req.type == RequestType.CHANGE:
        affected_task = _apply_change(db, req)
    elif req.type == RequestType.REPLACE:
        affected_task = _apply_replace(db, req)
    elif req.type == RequestType.REMOVE:
        _apply_remove(db, req)
    elif req.type == RequestType.ADD:
        affected_task = _apply_add(db, req)
    elif req.type == RequestType.QUESTION:
        # Soru tipinde "onay" anlamı yok, resolved gibi davran
        req.status = RequestStatus.RESOLVED
        req.teacher_response = (response or "").strip() or req.teacher_response
        req.responded_at = datetime.now(timezone.utc)
        return None

    req.status = RequestStatus.APPROVED
    req.teacher_response = (response or "").strip() or req.teacher_response
    req.responded_at = datetime.now(timezone.utc)
    _notify_resolved_safe(req, "approved")
    return affected_task


# ---------------------------- Uygulama yardımcıları ----------------------------


def _apply_change(db: Session, req: TaskRequest) -> Task:
    """CHANGE: Mevcut görevin kalem sayısını günceller (proposed_count zorunlu)."""
    task = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.id == req.task_id)
        .first()
    )
    if not task:
        raise RequestError("İlgili görev artık mevcut değil.")
    if req.proposed_count is None or req.proposed_count < 1:
        raise RequestError("Yeni sayı belirtilmemiş.")

    # Tek kalemli görevde basit güncelleme — çok kalemli ise
    # değişiklik öğretmen tarafından düzenleme sayfasından daha güvenli yapılır.
    if len(task.book_items) != 1:
        raise RequestError(
            "Çok kalemli görevde sayı değişikliği için öğretmen panelinden manuel düzenleyin."
        )
    item = task.book_items[0]
    delta = req.proposed_count - item.planned_count
    if delta == 0:
        return task

    if delta > 0:
        # Kapasite analizi
        sp = (
            db.query(SectionProgress)
            .join(StudentBook, StudentBook.id == SectionProgress.student_book_id)
            .filter(
                StudentBook.student_id == task.student_id,
                SectionProgress.book_section_id == item.book_section_id,
            )
            .first()
        )
        section = db.query(BookSection).filter(BookSection.id == item.book_section_id).first()
        rebalance_notes: list[str] = []
        if sp and section:
            kalan = section.test_count - sp.reserved_count - sp.completed_count
            if delta > kalan:
                # Otomatik dengeleme: gelecekteki aynı ünite rezervlerinden ihtiyaç kadar serbest bırak
                needed = delta - kalan
                future_items = (
                    db.query(TaskBookItem)
                    .join(Task, Task.id == TaskBookItem.task_id)
                    .options(joinedload(TaskBookItem.task), joinedload(TaskBookItem.book), joinedload(TaskBookItem.section))
                    .filter(
                        Task.student_id == task.student_id,
                        Task.id != task.id,
                        Task.date > task.date,
                        TaskBookItem.book_section_id == item.book_section_id,
                    )
                    .order_by(Task.date.desc(), Task.id.desc())
                    .all()
                )
                for fit in future_items:
                    if needed <= 0:
                        break
                    reducible = fit.planned_count - fit.completed_count
                    if reducible <= 0:
                        continue
                    take = min(reducible, needed)
                    release_item(
                        db,
                        student_id=task.student_id,
                        book_id=fit.book_id,
                        section_id=fit.book_section_id,
                        count=take,
                    )
                    parent = fit.task
                    date_str = parent.date.strftime("%d.%m")
                    if take >= fit.planned_count:
                        db.delete(fit)
                        db.flush()
                        remaining = (
                            db.query(TaskBookItem)
                            .filter(TaskBookItem.task_id == parent.id)
                            .count()
                        )
                        if remaining == 0:
                            rebalance_notes.append(f"{date_str} görevi tamamen silindi (-{take})")
                            db.delete(parent)
                        else:
                            rebalance_notes.append(f"{date_str} görevinde bu üniteye ait kalem kaldırıldı (-{take})")
                    else:
                        fit.planned_count -= take
                        parent_items_count = (
                            db.query(TaskBookItem)
                            .filter(TaskBookItem.task_id == parent.id)
                            .count()
                        )
                        if parent_items_count == 1 and fit.book and fit.section:
                            unit_word = "deneme" if fit.book.type.value in ("brans_denemesi", "genel_deneme") else "test"
                            parent.title = f"{fit.book.name} — {fit.section.label}: {fit.planned_count} {unit_word}"
                        rebalance_notes.append(f"{date_str} görevinden {take} test çıkarıldı")
                    needed -= take
                if needed > 0:
                    raise RequestError(
                        f"Yeterli kapasite ayarlanamadı (eksik {needed} test). "
                        f"Bu nadiren olur — öğrencinin talep ettiği sayı kapasiteyi tamamen aşıyor."
                    )
        # Şimdi yeni rezervi al
        try:
            reserve_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=delta,
            )
        except ReservationError as e:
            raise RequestError(str(e))
        # Otomatik dengeleme notlarını teacher_response'a ekle (varsa)
        if rebalance_notes:
            note = "Otomatik dengeleme: " + "; ".join(rebalance_notes)
            existing = (req.teacher_response or "").strip()
            req.teacher_response = (existing + " · " + note).strip(" ·") if existing else note
    else:
        # Rezerv iade et
        # Tamamlanmış kısma dokunma; sadece planned − completed üzerindeki fazlalığı iade
        not_yet_done = item.planned_count - item.completed_count
        to_release = min(abs(delta), not_yet_done)
        if to_release > 0:
            release_item(
                db,
                student_id=task.student_id,
                book_id=item.book_id,
                section_id=item.book_section_id,
                count=to_release,
            )

    item.planned_count = req.proposed_count
    # Başlığı yeniden üret (basit format)
    book = item.book if item.book else None
    section = item.section if item.section else None
    if book and section:
        unit_word = "deneme" if book.type.value in ("brans_denemesi", "genel_deneme") else "test"
        task.title = f"{book.name} — {section.label}: {req.proposed_count} {unit_word}"
    return task


def _apply_replace(db: Session, req: TaskRequest) -> Task:
    """REPLACE: mevcut görevin kaynağını/bölümünü tamamen değiştir.

    Eski rezervler iade edilir, yeni rezerv açılır. Tamamlanmış ilerleme varsa reddedilir
    (yarım kalan ilerleme yeni kaynakla anlamlı şekilde birleştirilemez).
    """
    task = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.id == req.task_id)
        .first()
    )
    if not task:
        raise RequestError("İlgili görev artık mevcut değil.")
    if any(it.completed_count > 0 for it in task.book_items):
        raise RequestError(
            "Görevde kısmen çözüm var; kaynak değişikliği uygulanamaz. Önce çıkarın, sonra yeni görev ekleyin."
        )
    if not (req.proposed_book_id and req.proposed_section_id and req.proposed_count):
        raise RequestError("Yeni kaynak için kitap, bölüm ve sayı gerekli.")

    new_book = db.query(Book).filter(Book.id == req.proposed_book_id).first()
    new_section = db.query(BookSection).filter(BookSection.id == req.proposed_section_id).first()
    if not new_book or not new_section or new_section.book_id != new_book.id:
        raise RequestError("Yeni kitap/bölüm uyumsuz.")

    # Eski rezervleri iade et + kalemleri sil
    release_task_items(db, task.student_id, list(task.book_items))
    for it in list(task.book_items):
        db.delete(it)
    db.flush()

    # Yeni rezerv aç
    try:
        reserve_item(
            db,
            student_id=task.student_id,
            book_id=req.proposed_book_id,
            section_id=req.proposed_section_id,
            count=req.proposed_count,
        )
    except ReservationError as e:
        raise RequestError(str(e))

    db.add(TaskBookItem(
        task_id=task.id,
        book_id=req.proposed_book_id,
        book_section_id=req.proposed_section_id,
        planned_count=req.proposed_count,
        completed_count=0,
    ))

    unit_word = "deneme" if new_book.type.value in ("brans_denemesi", "genel_deneme") else "test"
    task.title = f"{new_book.name} — {new_section.label}: {req.proposed_count} {unit_word}"
    return task


def _apply_remove(db: Session, req: TaskRequest) -> None:
    """REMOVE: Görevi sil, rezerv iade et.

    Silmeden ÖNCE task başlığı + tarihi req.task_title_snapshot/task_date_snapshot'a
    yazılır → task_id SET NULL olsa bile detail sayfasında "Çıkarılan görev: <ad>
    (<tarih>)" gösterilebilir (audit izi).
    """
    task = (
        db.query(Task)
        .options(joinedload(Task.book_items))
        .filter(Task.id == req.task_id)
        .first()
    )
    if not task:
        raise RequestError("İlgili görev artık mevcut değil.")
    # Audit snapshot — task silinince bu alanlar kalır
    req.task_title_snapshot = task.title
    req.task_date_snapshot = task.date
    release_task_items(db, task.student_id, list(task.book_items))
    db.delete(task)


def _apply_add(db: Session, req: TaskRequest) -> Task:
    """ADD: Yeni görev oluştur."""
    if not (req.proposed_book_id and req.proposed_section_id and req.proposed_count and req.proposed_date):
        raise RequestError("Eklenecek görev için tüm alanlar gerekli.")
    book = db.query(Book).filter(Book.id == req.proposed_book_id).first()
    section = db.query(BookSection).filter(BookSection.id == req.proposed_section_id).first()
    if not book or not section or section.book_id != book.id:
        raise RequestError("Kitap/bölüm uyumsuz.")

    try:
        reserve_item(
            db,
            student_id=req.student_id,
            book_id=req.proposed_book_id,
            section_id=req.proposed_section_id,
            count=req.proposed_count,
        )
    except ReservationError as e:
        raise RequestError(str(e))

    unit_word = "deneme" if book.type.value in ("brans_denemesi", "genel_deneme") else "test"
    title = f"{book.name} — {section.label}: {req.proposed_count} {unit_word}"

    max_order = (
        db.query(Task.order)
        .filter(Task.student_id == req.student_id, Task.date == req.proposed_date)
        .order_by(Task.order.desc())
        .first()
    )
    next_order = (max_order[0] + 1) if max_order else 0

    task = Task(
        student_id=req.student_id,
        date=req.proposed_date,
        type=TaskType.TEST,
        title=title,
        status=TaskStatus.PENDING,
        order=next_order,
    )
    db.add(task)
    db.flush()
    db.add(TaskBookItem(
        task_id=task.id,
        book_id=req.proposed_book_id,
        book_section_id=req.proposed_section_id,
        planned_count=req.proposed_count,
        completed_count=0,
    ))
    return task


# ---------------------------- Sayım yardımcıları ----------------------------


def pending_count_for_teacher(db: Session, teacher_id: int) -> int:
    return (
        db.query(TaskRequest)
        .filter(
            TaskRequest.teacher_id == teacher_id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .count()
    )


def pending_count_for_student(db: Session, student_id: int) -> int:
    return (
        db.query(TaskRequest)
        .filter(
            TaskRequest.student_id == student_id,
            TaskRequest.status == RequestStatus.PENDING,
        )
        .count()
    )
