"""Self-service şifre sıfırlama servisi (Dalga 7 P2).

Akış:
  1. request_reset(db, email, ip) — kullanıcı varsa token üretir + e-posta gönderir.
     Enumeration koruması: çağıran her zaman generic yanıt verir; bu fonksiyon
     kullanıcı yoksa sessizce None döner.
  2. get_usable_token(db, token) — geçerli (tüketilmemiş + süresi geçmemiş) token.
  3. consume_reset(db, token_row, new_password) — şifreyi değiştir + token'ı tüket +
     kilit/sayaç sıfırla (pwd_stamp değişir → eski tüm oturumlar revoke).
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PasswordResetToken, User, default_reset_expiry
from app.services.security import hash_password


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def request_reset(db: Session, *, email: str, ip: str | None) -> str | None:
    """Kullanıcı varsa yeni reset token üretip e-posta gönderir.

    Returns: gönderilen token (test/log için) veya None (kullanıcı yok/pasif).
    Çağıran ASLA bu dönüşe göre kullanıcıya farklı yanıt vermemeli (enumeration).
    """
    email_norm = (email or "").strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    # Demo hesabı (is_demo) → sessizce reset YOK (sabit demo şifresi korunur).
    if user is None or not user.is_active or user.is_demo:
        return None

    # Aynı kullanıcının önceki kullanılmamış tokenlarını geçersiz kıl
    now = _now()
    olds = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .all()
    )
    for o in olds:
        o.consumed_at = now

    token = secrets.token_urlsafe(32)
    row = PasswordResetToken(
        token=token,
        user_id=user.id,
        expires_at=default_reset_expiry(),
        requested_ip=(ip or "")[:64] or None,
    )
    db.add(row)
    db.commit()

    # E-posta gönder (disabled ise log-only — dev)
    try:
        from app.config import settings
        from app.services.email_service import send_email
        reset_url = f"{settings.app_base_url.rstrip('/')}/password/reset/{token}"
        send_email(
            user.email,
            "password_reset",
            {
                "full_name": user.full_name or user.email,
                "reset_url": reset_url,
                "ttl_minutes": 60,
            },
        )
    except Exception:
        logger.exception("password reset email fail user=%s", user.id)

    return token


def get_usable_token(db: Session, *, token: str) -> PasswordResetToken | None:
    """Geçerli (tüketilmemiş + süresi geçmemiş) token satırı, yoksa None."""
    if not token:
        return None
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token == token.strip())
        .first()
    )
    if row is None or not row.is_usable:
        return None
    return row


def consume_reset(
    db: Session, *, token_row: PasswordResetToken, new_password: str
) -> User:
    """Şifreyi değiştir + token'ı tüket + kilit/sayaç sıfırla.

    pwd_stamp (password_changed_at) değiştiği için eski tüm access/refresh
    token'lar ve Jinja oturumları otomatik revoke olur.
    """
    now = _now()
    user = token_row.user
    user.password_hash = hash_password(new_password)
    user.password_changed_at = now
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    token_row.consumed_at = now
    db.commit()
    return user
