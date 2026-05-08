"""Öğretmenin öğrenci × veli yönetimi.

Sprint 2 kapsamı:
- POST /teacher/students/{id}/parents/invite → davet token üret + email at + log
- POST /teacher/students/{id}/parents/cancel-invitation/{inv_id} → kullanılmamış daveti iptal
- POST /teacher/students/{id}/parents/unlink/{link_id} → mevcut veli bağını kaldır

Hepsi /teacher/students/{id}#parents'a yönlenir; öğretmen detay sayfasında "Veliler"
sekmesi yenilenmiş listeyi gösterir.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from starlette import status

from app.deps import get_db, require_teacher
from app.models import (
    PARENT_RELATION_LABELS,
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentInvitation,
    ParentRelation,
    ParentStudentLink,
    User,
    UserRole,
)
from app.services.email_service import notify_parent_invitation
from app.services.parent_invitation import (
    can_register_parent_email,
    create_invitation,
    has_pending_invitation,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher/students")


def _ensure_owns_student(db: Session, teacher: User, student_id: int) -> User:
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == teacher.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")
    return student


def _back_to_parents_tab(student_id: int, flash: str | None = None) -> RedirectResponse:
    url = f"/teacher/students/{student_id}#parents"
    if flash:
        sep = "&" if "?" in url else "?"
        # hash'tan önce query gelir
        url = f"/teacher/students/{student_id}?flash={flash}#parents"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{student_id}/parents/invite")
def invite_parent(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    invited_email: str = Form(...),
    relation: str = Form("diger"),
    is_primary: str = Form(""),
):
    student = _ensure_owns_student(db, user, student_id)

    email = invited_email.strip().lower()
    if "@" not in email or len(email) < 5:
        return _back_to_parents_tab(student_id, flash="invalid_email")

    # Rol çakışma kontrolü (KARAR a)
    can_register, conflict_role = can_register_parent_email(db, email)
    if not can_register:
        return _back_to_parents_tab(
            student_id,
            flash=("conflict_teacher" if conflict_role == UserRole.TEACHER else "conflict_student"),
        )

    # Açık davet zaten var mı (rate limit için MVP guard)
    pending = has_pending_invitation(db, invited_email=email, student_id=student_id)
    if pending:
        return _back_to_parents_tab(student_id, flash="already_invited")

    # Mevcut bağlantı var mı (zaten veli) — yine güvenli olalım
    parent_user = (
        db.query(User).filter(User.email == email, User.role == UserRole.PARENT).first()
    )
    if parent_user:
        existing_link = (
            db.query(ParentStudentLink)
            .filter(
                ParentStudentLink.parent_id == parent_user.id,
                ParentStudentLink.student_id == student_id,
            )
            .first()
        )
        if existing_link:
            return _back_to_parents_tab(student_id, flash="already_linked")

    # Relation parse — geçersizse default
    try:
        rel_enum = ParentRelation(relation.strip().lower())
    except ValueError:
        rel_enum = ParentRelation.DIGER

    is_primary_bool = is_primary == "yes" or is_primary == "1" or is_primary == "on"

    inv = create_invitation(
        db,
        invited_email=email,
        student_id=student_id,
        invited_by_id=user.id,
        relation=rel_enum,
        is_primary=is_primary_bool,
    )

    # Email gönderim — ana akışı kırma
    sent_ok = False
    try:
        sent_ok = notify_parent_invitation(
            inv,
            teacher=user,
            student=student,
            relation_label=PARENT_RELATION_LABELS[rel_enum],
        )
    except Exception as e:
        logger.exception("Veli davet maili gönderim hatası: %s", e)

    # notification_log: dummy parent_id yok (hesap henüz açılmadı) → davet maili
    # log'una INVITATION kaydı invited_by ile değil, "henüz parent_id yok" olarak girer.
    # Geçici çözüm: parent_id'yi invited_by_id ile yaz, student_id ile bağla; status'a göre.
    # Bu kayıt KVKK denetiminde "öğretmen veliye davet attı" izi.
    db.add(NotificationLog(
        parent_id=user.id,  # davet eden öğretmen — sonradan veli kaydolunca da iz kalır
        student_id=student_id,
        kind=NotificationKind.INVITATION,
        channel=NotificationChannel.EMAIL,
        status=NotificationStatus.SENT if sent_ok else NotificationStatus.QUEUED,
        subject=f"Veli daveti: {student.full_name}",
        payload_json=None,
        external_id=None,
        sent_at=datetime.now(timezone.utc) if sent_ok else None,
    ))

    db.commit()

    return _back_to_parents_tab(student_id, flash="invited" if sent_ok else "invited_log_only")


@router.post("/{student_id}/parents/cancel-invitation/{inv_id}")
def cancel_invitation(
    student_id: int,
    inv_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    student = _ensure_owns_student(db, user, student_id)

    inv = (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.id == inv_id,
            ParentInvitation.student_id == student_id,
            ParentInvitation.invited_by_id == user.id,
            ParentInvitation.consumed_at.is_(None),
        )
        .first()
    )
    if not inv:
        return _back_to_parents_tab(student_id, flash="cancel_not_found")

    # Soft cancel: expires_at = now (geçerlilik bitir). Sonra UI listesinde "iptal edildi"
    # olarak gözüksün diye consumed_at'i de set edebiliriz; ama consumed semantiği
    # "kullanıldı" anlamında. Burada expires_at'i geçmişe çekmek temiz.
    inv.expires_at = datetime.now(timezone.utc)
    db.commit()

    return _back_to_parents_tab(student_id, flash="cancelled")


@router.post("/{student_id}/parents/unlink/{link_id}")
def unlink_parent(
    student_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    student = _ensure_owns_student(db, user, student_id)

    link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.id == link_id,
            ParentStudentLink.student_id == student_id,
        )
        .first()
    )
    if not link:
        return _back_to_parents_tab(student_id, flash="unlink_not_found")

    # Veli kullanıcısını silmiyoruz — sadece bu öğrenciyle olan bağı kaldırıyoruz.
    # Veli başka çocuklarına ait link'ler korunur.
    db.delete(link)
    db.commit()

    return _back_to_parents_tab(student_id, flash="unlinked")
