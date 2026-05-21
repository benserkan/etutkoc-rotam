"""E-posta doğrulama servisi (Dalga 7 P3, soft doğrulama).

Akış:
  1. issue_and_send(db, user) — kayıt/resend sonrası token üretip doğrulama maili
     gönderir (eski kullanılmamış tokenlar geçersiz kılınır).
  2. verify(db, token) — token geçerliyse User.email_verified_at doldurur + tüketir.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import EmailVerificationToken, User, default_verification_expiry


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_and_send(db: Session, *, user: User, autocommit: bool = True) -> str:
    """Kullanıcı için yeni doğrulama token'ı üret + e-posta gönder.

    Returns: token (test/log için). Zaten doğrulanmışsa yine token üretir
    (resend güvenli; verify zaten-doğrulanmışı no-op yapar)."""
    now = _now()
    olds = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .all()
    )
    for o in olds:
        o.consumed_at = now

    token = secrets.token_urlsafe(32)
    row = EmailVerificationToken(
        token=token, user_id=user.id, expires_at=default_verification_expiry()
    )
    db.add(row)
    if autocommit:
        db.commit()

    try:
        from app.config import settings
        from app.services.email_service import send_email
        verify_url = f"{settings.app_base_url.rstrip('/')}/verify-email/{token}"
        send_email(
            user.email,
            "email_verify",
            {
                "full_name": user.full_name or user.email,
                "verify_url": verify_url,
                "ttl_days": 7,
            },
        )
    except Exception:
        logger.exception("email verify send fail user=%s", user.id)

    return token


def verify(db: Session, *, token: str) -> User | None:
    """Token geçerliyse User.email_verified_at doldurur + tüketir. Yoksa None."""
    if not token:
        return None
    row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token == token.strip())
        .first()
    )
    if row is None or not row.is_usable:
        return None
    now = _now()
    user = row.user
    if user.email_verified_at is None:
        user.email_verified_at = now
    row.consumed_at = now
    db.commit()
    return user
