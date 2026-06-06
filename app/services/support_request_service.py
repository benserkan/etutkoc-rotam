"""SupportRequest iş kuralları — rol-bazlı talep akışı.

Yönler (talep eden → muhatap):
  - Bağımsız koç (TEACHER, institution_id NULL) → Süper Admin
  - Kurum yöneticisi (INSTITUTION_ADMIN)        → Süper Admin
  - Kuruma bağlı öğretmen (TEACHER, institution) → kendi Kurum yöneticisi

Yaşam döngüsü: open → under_review → answered → resolved (+ withdrawn).
Thread: ilk mesaj talep gövdesi; sonrası karşılıklı (add_message).

Yetki: talep eden yalnız kendi taleplerini; süper admin audience=super_admin
tümünü; kurum yöneticisi audience=institution_admin + KENDİ kurumunu (tenant
izolasyonu). get_* fonksiyonları yetkisiz/bulunamadıda None döner (endpoint 404).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import (
    SUPPORT_ATTACH_ALLOWED_TYPES,
    SUPPORT_ATTACH_MAX_BYTES,
    SUPPORT_ATTACH_MAX_PER_REQUEST,
    SUPPORT_AUDIENCE_INSTITUTION_ADMIN,
    SUPPORT_AUDIENCE_SUPER_ADMIN,
    SUPPORT_AUDIENCE_TEACHER,
    SUPPORT_RECIPIENT_PENDING_STATUSES,
    SUPPORT_STATUS_ANSWERED,
    SUPPORT_STATUS_OPEN,
    SUPPORT_STATUS_RESOLVED,
    SUPPORT_STATUS_UNDER_REVIEW,
    SUPPORT_STATUS_WITHDRAWN,
    SUPPORT_TERMINAL_STATUSES,
    SupportAttachment,
    SupportRequest,
    SupportRequestMessage,
    User,
    UserRole,
)
from app.models.support_request import SUPPORT_CATEGORY_LABELS_TR

MAX_SUBJECT = 200
MAX_BODY = 5000


class SupportError(ValueError):
    """İş kuralı ihlali → endpoint 400/409'a çevirir."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ----------------------------- Yön çözümleme -----------------------------


def audience_for_requester(user: User) -> tuple[str, int | None]:
    """Talep edenin rolüne göre muhatap + (varsa) kurum bağlamı döndürür."""
    if user.role == UserRole.TEACHER:
        if user.institution_id is None:
            return SUPPORT_AUDIENCE_SUPER_ADMIN, None
        return SUPPORT_AUDIENCE_INSTITUTION_ADMIN, user.institution_id
    if user.role == UserRole.INSTITUTION_ADMIN:
        return SUPPORT_AUDIENCE_SUPER_ADMIN, user.institution_id
    raise SupportError("role_not_allowed", "Bu rol talep oluşturamaz.")


def can_request(user: User) -> bool:
    return user.role in (UserRole.TEACHER, UserRole.INSTITUTION_ADMIN)


# ----------------------------- Oluşturma -----------------------------


def create_request(
    db: Session, *, requester: User, category: str, subject: str, body: str,
) -> SupportRequest:
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        raise SupportError("subject_required", "Konu boş olamaz.")
    if len(subject) > MAX_SUBJECT:
        raise SupportError("subject_too_long", f"Konu en fazla {MAX_SUBJECT} karakter.")
    if not body:
        raise SupportError("body_required", "Mesaj boş olamaz.")
    if len(body) > MAX_BODY:
        raise SupportError("body_too_long", f"Mesaj en fazla {MAX_BODY} karakter.")
    if category not in SUPPORT_CATEGORY_LABELS_TR:
        category = "other"

    audience, institution_id = audience_for_requester(requester)
    if audience == SUPPORT_AUDIENCE_INSTITUTION_ADMIN and not institution_id:
        raise SupportError("no_institution", "Kurum bilginiz bulunamadı.")

    now = datetime.now(timezone.utc)
    req = SupportRequest(
        requester_id=requester.id,
        requester_role=requester.role.value,
        audience=audience,
        institution_id=institution_id,
        category=category,
        subject=subject,
        status=SUPPORT_STATUS_OPEN,
        last_activity_at=now,
    )
    db.add(req)
    db.flush()
    db.add(SupportRequestMessage(request_id=req.id, sender_id=requester.id, body=body))
    db.flush()
    return req


def notify_coach(
    db: Session, *, admin: User, teacher: User, subject: str, body: str,
    category: str = "student_risk",
) -> SupportRequest:
    """Aşağı yönlü talep: kurum yöneticisi → kendi kurumundaki koç (audience=
    teacher, target_user_id=teacher). Riskli öğrenci için "Koça ilet" akışı.

    Tenant izolasyonu: koç, yöneticinin kurumuna bağlı olmalı (endpoint doğrular;
    burada savunmacı kontrol)."""
    if admin.role != UserRole.INSTITUTION_ADMIN or admin.institution_id is None:
        raise SupportError("role_not_allowed", "Yalnız kurum yöneticisi koça talep iletebilir.")
    if (
        teacher.role != UserRole.TEACHER
        or teacher.institution_id != admin.institution_id
    ):
        raise SupportError("coach_not_found", "Koç bu kuruma bağlı değil.")

    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        raise SupportError("subject_required", "Konu boş olamaz.")
    if len(subject) > MAX_SUBJECT:
        raise SupportError("subject_too_long", f"Konu en fazla {MAX_SUBJECT} karakter.")
    if not body:
        raise SupportError("body_required", "Mesaj boş olamaz.")
    if len(body) > MAX_BODY:
        raise SupportError("body_too_long", f"Mesaj en fazla {MAX_BODY} karakter.")
    if category not in SUPPORT_CATEGORY_LABELS_TR:
        category = "student_risk"

    now = datetime.now(timezone.utc)
    req = SupportRequest(
        requester_id=admin.id,
        requester_role=admin.role.value,
        audience=SUPPORT_AUDIENCE_TEACHER,
        institution_id=admin.institution_id,
        target_user_id=teacher.id,
        category=category,
        subject=subject,
        status=SUPPORT_STATUS_OPEN,
        last_activity_at=now,
    )
    db.add(req)
    db.flush()
    db.add(SupportRequestMessage(request_id=req.id, sender_id=admin.id, body=body))
    db.flush()
    return req


def parent_request_to_coach(
    db: Session, *, parent: User, student: User, subject: str, body: str,
    category: str = "progress_question",
) -> SupportRequest:
    """Veli → çocuğunun koçuna talep (audience=teacher, target_user_id=koç).

    Çift yönlü thread: koç gelen kutusunda görür (list_inbox_teacher), cevaplar;
    veli kendi taleplerinde (list_for_requester) görür + izler. Çocuğun bir koçu
    olmalı (student.teacher_id). Veli-çocuk bağı endpoint'te doğrulanır."""
    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    if coach is None or coach.role != UserRole.TEACHER:
        raise SupportError("coach_not_found", "Çocuğun bağlı bir koçu yok.")

    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject:
        raise SupportError("subject_required", "Konu boş olamaz.")
    if len(subject) > MAX_SUBJECT:
        raise SupportError("subject_too_long", f"Konu en fazla {MAX_SUBJECT} karakter.")
    if not body:
        raise SupportError("body_required", "Mesaj boş olamaz.")
    if len(body) > MAX_BODY:
        raise SupportError("body_too_long", f"Mesaj en fazla {MAX_BODY} karakter.")
    if category not in SUPPORT_CATEGORY_LABELS_TR:
        category = "progress_question"

    now = datetime.now(timezone.utc)
    req = SupportRequest(
        requester_id=parent.id,
        requester_role=parent.role.value,
        audience=SUPPORT_AUDIENCE_TEACHER,
        institution_id=coach.institution_id,
        target_user_id=coach.id,
        category=category,
        subject=subject,
        status=SUPPORT_STATUS_OPEN,
        last_activity_at=now,
    )
    db.add(req)
    db.flush()
    db.add(SupportRequestMessage(request_id=req.id, sender_id=parent.id, body=body))
    db.flush()
    return req


# ----------------------------- Sorgular -----------------------------


_LOAD = (
    joinedload(SupportRequest.requester),
    joinedload(SupportRequest.handled_by),
    joinedload(SupportRequest.target_user),
    joinedload(SupportRequest.escalated_by),
    joinedload(SupportRequest.messages).joinedload(SupportRequestMessage.sender),
    joinedload(SupportRequest.attachments).joinedload(SupportAttachment.uploaded_by),
)


def _base_query(db: Session):
    return db.query(SupportRequest).options(*_LOAD)


def list_for_requester(
    db: Session, requester: User, *, status_filter: str | None = None,
) -> list[SupportRequest]:
    q = _base_query(db).filter(SupportRequest.requester_id == requester.id)
    if status_filter:
        q = q.filter(SupportRequest.status == status_filter)
    return q.order_by(SupportRequest.last_activity_at.desc()).all()


def list_inbox_super_admin(
    db: Session, *, status_filter: str | None = None,
) -> list[SupportRequest]:
    q = _base_query(db).filter(SupportRequest.audience == SUPPORT_AUDIENCE_SUPER_ADMIN)
    if status_filter:
        q = q.filter(SupportRequest.status == status_filter)
    return q.order_by(SupportRequest.last_activity_at.desc()).all()


def list_inbox_institution_admin(
    db: Session, admin: User, *, status_filter: str | None = None,
) -> list[SupportRequest]:
    """Kurum yöneticisinin gelen kutusu: AKTİF kuyruğu (audience=institution_admin
    + kendi kurumu) + KENDİ YÖNLENDİRDİKLERİ (escalated_by_id == admin.id). İkincisi
    süper yöneticiye iletilmiş olsa da burada kalır → yönetici cevabı izleyebilir."""
    if admin.institution_id is None:
        return []
    q = _base_query(db).filter(
        or_(
            (SupportRequest.audience == SUPPORT_AUDIENCE_INSTITUTION_ADMIN)
            & (SupportRequest.institution_id == admin.institution_id),
            SupportRequest.escalated_by_id == admin.id,
        )
    )
    if status_filter:
        q = q.filter(SupportRequest.status == status_filter)
    return q.order_by(SupportRequest.last_activity_at.desc()).all()


def list_inbox_teacher(
    db: Session, teacher: User, *, status_filter: str | None = None,
) -> list[SupportRequest]:
    """Koçun gelen kutusu: kurum yöneticisinin kendisine ilettiği talepler
    (audience=teacher + target_user_id == koç)."""
    q = _base_query(db).filter(
        SupportRequest.audience == SUPPORT_AUDIENCE_TEACHER,
        SupportRequest.target_user_id == teacher.id,
    )
    if status_filter:
        q = q.filter(SupportRequest.status == status_filter)
    return q.order_by(SupportRequest.last_activity_at.desc()).all()


def list_inbox(db: Session, user: User, *, status_filter: str | None = None) -> list[SupportRequest]:
    """Rol-temelli gelen kutusu dağıtıcı (endpoint tek uç kullanır)."""
    if user.role == UserRole.SUPER_ADMIN:
        return list_inbox_super_admin(db, status_filter=status_filter)
    if user.role == UserRole.INSTITUTION_ADMIN:
        return list_inbox_institution_admin(db, user, status_filter=status_filter)
    if user.role == UserRole.TEACHER:
        return list_inbox_teacher(db, user, status_filter=status_filter)
    return []


def get_for_requester(db: Session, requester: User, req_id: int) -> SupportRequest | None:
    return (
        _base_query(db)
        .filter(SupportRequest.id == req_id, SupportRequest.requester_id == requester.id)
        .first()
    )


def is_active_recipient(req: SupportRequest, user: User) -> bool:
    """Kullanıcı talebin AKTİF muhatabı mı (eyleme yetkili: incele/cevapla/çözümle/
    yönlendir). Süper admin → audience=super_admin; kurum yöneticisi →
    audience=institution_admin + kendi kurumu."""
    if user.role == UserRole.SUPER_ADMIN:
        return req.audience == SUPPORT_AUDIENCE_SUPER_ADMIN
    if user.role == UserRole.INSTITUTION_ADMIN:
        return (
            req.audience == SUPPORT_AUDIENCE_INSTITUTION_ADMIN
            and req.institution_id is not None
            and req.institution_id == user.institution_id
        )
    if user.role == UserRole.TEACHER:
        return (
            req.audience == SUPPORT_AUDIENCE_TEACHER
            and req.target_user_id is not None
            and req.target_user_id == user.id
        )
    return False


def get_for_recipient(db: Session, recipient: User, req_id: int) -> SupportRequest | None:
    """AKTİF muhatap erişimi (eylemler için). Aksi → None (tenant izolasyonu)."""
    req = _base_query(db).filter(SupportRequest.id == req_id).first()
    if req is None:
        return None
    return req if is_active_recipient(req, recipient) else None


def get_viewable(db: Session, user: User, req_id: int) -> SupportRequest | None:
    """GÖRÜNTÜLEME erişimi (thread okuma): talep eden VEYA aktif muhatap VEYA
    yönlendiren kurum yöneticisi. Yönlendiren, talep süper yöneticiye geçse bile
    görmeye + cevabı izlemeye devam eder."""
    req = _base_query(db).filter(SupportRequest.id == req_id).first()
    if req is None:
        return None
    if req.requester_id == user.id:
        return req
    if is_active_recipient(req, user):
        return req
    if req.escalated_by_id is not None and req.escalated_by_id == user.id:
        return req
    return None


# ----------------------------- Eylemler -----------------------------


def _touch(req: SupportRequest) -> None:
    req.last_activity_at = datetime.now(timezone.utc)


def add_message(
    db: Session, *, req: SupportRequest, sender: User, body: str, by_recipient: bool,
) -> SupportRequestMessage:
    body = (body or "").strip()
    if not body:
        raise SupportError("body_required", "Mesaj boş olamaz.")
    if len(body) > MAX_BODY:
        raise SupportError("body_too_long", f"Mesaj en fazla {MAX_BODY} karakter.")
    if req.status in SUPPORT_TERMINAL_STATUSES:
        raise SupportError("request_closed", "Bu talep kapanmış; yeni mesaj eklenemez.")

    msg = SupportRequestMessage(request_id=req.id, sender_id=sender.id, body=body)
    db.add(msg)
    if by_recipient:
        # Muhatap cevap yazdı → Cevaplandı; üstlenen atanır
        req.status = SUPPORT_STATUS_ANSWERED
        if req.handled_by_id is None:
            req.handled_by_id = sender.id
            req.handled_at = datetime.now(timezone.utc)
    else:
        # Talep eden tekrar yazdı → cevaplanmışsa yeniden değerlendirmeye al
        if req.status == SUPPORT_STATUS_ANSWERED:
            req.status = SUPPORT_STATUS_UNDER_REVIEW
    _touch(req)
    db.flush()
    return msg


def mark_under_review(db: Session, *, req: SupportRequest, recipient: User) -> None:
    if req.status not in (SUPPORT_STATUS_OPEN, SUPPORT_STATUS_ANSWERED):
        raise SupportError("invalid_transition", "Yalnız açık/cevaplanmış talepler incelemeye alınır.")
    req.status = SUPPORT_STATUS_UNDER_REVIEW
    if req.handled_by_id is None:
        req.handled_by_id = recipient.id
        req.handled_at = datetime.now(timezone.utc)
    _touch(req)
    db.flush()


def escalate_to_super_admin(
    db: Session, *, req: SupportRequest, admin: User, note: str | None = None,
) -> SupportRequestMessage:
    """Kurum yöneticisi, çözemeyeceği talebi (teknik/şifre vb.) süper yöneticiye
    yönlendirir. Muhatap institution_admin → super_admin olur; talep kurum
    yöneticisinin aktif kuyruğundan çıkar, süper admin gelen kutusunda 'Açık'
    olarak belirir. Thread korunur + yönlendirme notu eklenir.

    Yalnız ilgili kurumun yöneticisi + audience=institution_admin + kapanmamış
    talep yönlendirilebilir (endpoint get_for_recipient ile aktif muhataplığı
    doğrular).
    """
    if req.audience != SUPPORT_AUDIENCE_INSTITUTION_ADMIN:
        raise SupportError("not_escalatable", "Bu talep süper yöneticiye yönlendirilemez.")
    if req.status in SUPPORT_TERMINAL_STATUSES:
        raise SupportError("already_closed", "Kapanmış talep yönlendirilemez.")

    note = (note or "").strip()
    sys_body = "[Yönlendirme] Kurum yöneticisi bu talebi süper yöneticiye iletti."
    if note:
        if len(note) > MAX_BODY:
            raise SupportError("body_too_long", f"Not en fazla {MAX_BODY} karakter.")
        sys_body += f" Not: {note}"

    req.audience = SUPPORT_AUDIENCE_SUPER_ADMIN
    req.status = SUPPORT_STATUS_OPEN
    req.handled_by_id = None
    req.handled_at = None
    req.escalated_by_id = admin.id
    req.escalated_at = datetime.now(timezone.utc)
    msg = SupportRequestMessage(request_id=req.id, sender_id=admin.id, body=sys_body)
    db.add(msg)
    _touch(req)
    db.flush()
    return msg


def resolve_request(db: Session, *, req: SupportRequest, recipient: User) -> None:
    if req.status in SUPPORT_TERMINAL_STATUSES:
        raise SupportError("already_closed", "Talep zaten kapanmış.")
    req.status = SUPPORT_STATUS_RESOLVED
    req.resolved_at = datetime.now(timezone.utc)
    if req.handled_by_id is None:
        req.handled_by_id = recipient.id
        req.handled_at = datetime.now(timezone.utc)
    _touch(req)
    db.flush()


def withdraw_request(db: Session, *, req: SupportRequest, requester: User) -> None:
    if req.requester_id != requester.id:
        raise SupportError("not_owner", "Bu talep size ait değil.")
    if req.status in SUPPORT_TERMINAL_STATUSES:
        raise SupportError("already_closed", "Talep zaten kapanmış.")
    req.status = SUPPORT_STATUS_WITHDRAWN
    _touch(req)
    db.flush()


# ----------------------------- Ekler (dosya) -----------------------------


def _sanitize_filename(name: str) -> str:
    name = (name or "").strip().replace("\\", "/").split("/")[-1]
    name = name.replace("\r", "").replace("\n", "").replace('"', "")
    return name[:255] or "dosya"


def add_attachment(
    db: Session, *, req: SupportRequest, uploader: User, filename: str,
    content_type: str, data: bytes,
) -> SupportAttachment:
    """Talebe dosya eki ekle (ekran görüntüsü / fatura). Boyut + tür + adet
    doğrulanır. Erişim/açık-olma kontrolü endpoint'te (get_viewable + terminal)."""
    if req.status in SUPPORT_TERMINAL_STATUSES:
        raise SupportError("request_closed", "Kapanmış talebe dosya eklenemez.")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in SUPPORT_ATTACH_ALLOWED_TYPES:
        raise SupportError(
            "invalid_file_type",
            "Yalnız resim (jpg/png/webp/gif) ve PDF dosyası eklenebilir.",
        )
    if not data:
        raise SupportError("empty_file", "Dosya boş.")
    if len(data) > SUPPORT_ATTACH_MAX_BYTES:
        mb = SUPPORT_ATTACH_MAX_BYTES // (1024 * 1024)
        raise SupportError("file_too_large", f"Dosya en fazla {mb} MB olabilir.")
    count = (
        db.query(SupportAttachment)
        .filter(SupportAttachment.request_id == req.id)
        .count()
    )
    if count >= SUPPORT_ATTACH_MAX_PER_REQUEST:
        raise SupportError(
            "too_many_files",
            f"Bir talebe en fazla {SUPPORT_ATTACH_MAX_PER_REQUEST} dosya eklenebilir.",
        )
    att = SupportAttachment(
        request_id=req.id,
        uploaded_by_id=uploader.id,
        filename=_sanitize_filename(filename),
        content_type=ctype,
        size_bytes=len(data),
        data=data,
    )
    db.add(att)
    _touch(req)
    db.flush()
    return att


def get_attachment(db: Session, att_id: int) -> SupportAttachment | None:
    """Eki (data dahil) getirir. Erişim kontrolü çağıran tarafta: ekin talebine
    get_viewable ile bakılır."""
    return db.query(SupportAttachment).filter(SupportAttachment.id == att_id).first()


# ----------------------------- Sayımlar -----------------------------


def pending_count_super_admin(db: Session) -> int:
    return (
        db.query(SupportRequest)
        .filter(
            SupportRequest.audience == SUPPORT_AUDIENCE_SUPER_ADMIN,
            SupportRequest.status.in_(SUPPORT_RECIPIENT_PENDING_STATUSES),
        )
        .count()
    )


def pending_count_institution_admin(db: Session, admin: User) -> int:
    if admin.institution_id is None:
        return 0
    return (
        db.query(SupportRequest)
        .filter(
            SupportRequest.audience == SUPPORT_AUDIENCE_INSTITUTION_ADMIN,
            SupportRequest.institution_id == admin.institution_id,
            SupportRequest.status.in_(SUPPORT_RECIPIENT_PENDING_STATUSES),
        )
        .count()
    )


def pending_count_teacher(db: Session, teacher: User) -> int:
    """Koça iletilmiş, koçun henüz cevaplamadığı talep sayısı (gelen kutusu rozeti)."""
    return (
        db.query(SupportRequest)
        .filter(
            SupportRequest.audience == SUPPORT_AUDIENCE_TEACHER,
            SupportRequest.target_user_id == teacher.id,
            SupportRequest.status.in_(SUPPORT_RECIPIENT_PENDING_STATUSES),
        )
        .count()
    )


def open_count_for_requester(db: Session, requester: User) -> int:
    from app.models import SUPPORT_OPEN_STATUSES

    return (
        db.query(SupportRequest)
        .filter(
            SupportRequest.requester_id == requester.id,
            SupportRequest.status.in_(SUPPORT_OPEN_STATUSES),
        )
        .count()
    )
