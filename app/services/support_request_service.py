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
    SUPPORT_AUDIENCE_INSTITUTION_ADMIN,
    SUPPORT_AUDIENCE_SUPER_ADMIN,
    SUPPORT_RECIPIENT_PENDING_STATUSES,
    SUPPORT_STATUS_ANSWERED,
    SUPPORT_STATUS_OPEN,
    SUPPORT_STATUS_RESOLVED,
    SUPPORT_STATUS_UNDER_REVIEW,
    SUPPORT_STATUS_WITHDRAWN,
    SUPPORT_TERMINAL_STATUSES,
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


# ----------------------------- Sorgular -----------------------------


_LOAD = (
    joinedload(SupportRequest.requester),
    joinedload(SupportRequest.handled_by),
    joinedload(SupportRequest.messages).joinedload(SupportRequestMessage.sender),
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
