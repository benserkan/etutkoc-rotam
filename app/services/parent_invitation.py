"""Veli davet token üretimi, doğrulama ve tüketimi.

Akış:
- Öğretmen veli davet eder → secrets.token_urlsafe(48) ile 64-char token üretilir
- Token + (öğrenci, davet eden, ilişki, primary, expires_at) parent_invitations'a yazılır
- Veli linke tıklar → token'la kayıt aranır; geçersiz/expired/consumed = hata
- Veli formu doldurur → token consumed_at=now ile işaretlenir; aynı token ikinci kez geçmez
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from sqlalchemy.orm import Session, joinedload

from app.models import (
    ParentInvitation,
    ParentRelation,
    User,
    UserRole,
)


# Davet linki ömrü
INVITATION_TTL = timedelta(days=7)
TOKEN_BYTES = 48  # secrets.token_urlsafe(48) → ~64 karakterlik token


class InvitationError(Enum):
    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    EMAIL_IN_USE_OTHER_ROLE = "email_in_use_other_role"
    PASSWORD_TOO_SHORT = "password_too_short"
    KVKK_NOT_ACCEPTED = "kvkk_not_accepted"
    NAME_REQUIRED = "name_required"


@dataclass
class InvitationLookup:
    """Token'la bulunan davet + durum."""
    invitation: ParentInvitation | None
    error: InvitationError | None


def create_invitation(
    db: Session,
    *,
    invited_email: str,
    student_id: int,
    invited_by_id: int,
    relation: ParentRelation = ParentRelation.DIGER,
    is_primary: bool = False,
) -> ParentInvitation:
    """Yeni davet kaydı oluştur. Token, expiry, normalize email."""
    email = invited_email.strip().lower()
    token = secrets.token_urlsafe(TOKEN_BYTES)
    expires = datetime.now(timezone.utc) + INVITATION_TTL

    inv = ParentInvitation(
        invited_email=email,
        student_id=student_id,
        invited_by_id=invited_by_id,
        relation=relation,
        is_primary=is_primary,
        token=token,
        expires_at=expires,
    )
    db.add(inv)
    db.flush()
    return inv


def has_pending_invitation(
    db: Session, *, invited_email: str, student_id: int
) -> ParentInvitation | None:
    """Bu öğrenci × email için açık (henüz tüketilmemiş, süresi geçmemiş) davet var mı?

    UI'da "zaten gönderilmiş davet var" uyarısı için.
    """
    email = invited_email.strip().lower()
    now = datetime.now(timezone.utc)
    return (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.invited_email == email,
            ParentInvitation.student_id == student_id,
            ParentInvitation.consumed_at.is_(None),
            ParentInvitation.expires_at > now,
        )
        .first()
    )


def lookup_token(db: Session, token: str) -> InvitationLookup:
    """Token'a bakıp uygun mu/expired mı/tüketilmiş mi belirle."""
    if not token:
        return InvitationLookup(None, InvitationError.NOT_FOUND)

    inv = (
        db.query(ParentInvitation)
        .options(
            joinedload(ParentInvitation.student),
            joinedload(ParentInvitation.invited_by),
        )
        .filter(ParentInvitation.token == token)
        .first()
    )
    if not inv:
        return InvitationLookup(None, InvitationError.NOT_FOUND)

    if inv.consumed_at is not None:
        return InvitationLookup(inv, InvitationError.CONSUMED)

    now = datetime.now(timezone.utc)
    # SQLite naive datetime dönebilir — TZ ekle ki karşılaştırma güvenli olsun
    expires = inv.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return InvitationLookup(inv, InvitationError.EXPIRED)

    return InvitationLookup(inv, None)


def consume_invitation(db: Session, inv: ParentInvitation) -> None:
    """Daveti tükenmiş olarak işaretle. İdempotent değildir — bir kez kullanıldıktan
    sonra bir daha consume edilmemeli (zaten consumed_at != None ile bloklanır).
    """
    inv.consumed_at = datetime.now(timezone.utc)
    db.flush()


def find_user_by_email(db: Session, email: str) -> User | None:
    """Email normalize ederek mevcut kullanıcıyı bul."""
    return (
        db.query(User)
        .filter(User.email == email.strip().lower())
        .first()
    )


def can_register_parent_email(db: Session, email: str) -> tuple[bool, UserRole | None]:
    """KARAR (a): Aynı email başka bir rolde varsa kayıt yasak.

    Returns: (izin var mı, çakışan rol).
    - Kullanıcı yoksa → (True, None) → yeni veli hesabı açılabilir
    - Mevcut PARENT → (True, None) → mevcut hesaba bağ eklenir (çoklu öğrenci senaryosu)
    - Mevcut TEACHER veya STUDENT → (False, role) → hata
    """
    existing = find_user_by_email(db, email)
    if existing is None:
        return True, None
    if existing.role == UserRole.PARENT:
        return True, None
    return False, existing.role
