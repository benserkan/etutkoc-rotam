"""Katman 11.A — Güvenlik bildirimleri (alert kanalları).

Şu an tek alarm: SUPER_ADMIN her başarılı login → diğer süper admin'lere email.
Email infra (`email_service.send_email`) çağrılır; EMAIL_ENABLED=false ise log'a
yazılır (geliştirme), prod'da SMTP gönderir.

Çerçeve defansif — alarm fail olsa login akışı bozulmasın (caller try/except).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import User, UserRole


logger = logging.getLogger(__name__)


def notify_super_admin_login(
    db: Session, *, user: User, ip: str | None, request: Request | None
) -> None:
    """Yeni bir SUPER_ADMIN login oldu — diğerlerine bildir.

    Şu an: email (template `security_super_admin_login`). İleride: webhook, SMS.
    """
    others = (
        db.query(User)
        .filter(
            User.role == UserRole.SUPER_ADMIN,
            User.is_active.is_(True),
            User.id != user.id,
        )
        .all()
    )
    if not others:
        return
    try:
        from app.services.email_service import send_email
    except Exception:
        logger.warning("email_service import fail — alarm log only")
        send_email = None  # type: ignore[assignment]

    now = datetime.now(timezone.utc)
    ctx = {
        "actor_email": user.email,
        "actor_full_name": user.full_name or user.email,
        "ip": ip or "(bilinmiyor)",
        "user_agent": (
            request.headers.get("user-agent", "")[:200] if request else ""
        ),
        "login_at_iso": now.isoformat(),
        "login_at_display": now.strftime("%d %B %Y, %H:%M UTC"),
    }
    for other in others:
        if not other.email:
            continue
        if send_email is None:
            logger.info(
                "[alarm] super_admin_login actor=%s recipient=%s (email_service unavailable)",
                user.email,
                other.email,
            )
            continue
        try:
            send_email(other.email, "security_super_admin_login", ctx)
        except Exception:
            logger.exception(
                "super_admin_login alarm email fail to=%s", other.email
            )


__all__ = ["notify_super_admin_login"]
