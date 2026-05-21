"""İki faktörlü doğrulama (TOTP) servisi (Dalga 7 P4).

pyotp tabanlı zaman-bazlı tek-kullanımlık şifre (Google Authenticator vb.).
Yalnız Süper Admin + Kurum Yöneticisi etkinleştirebilir (rol kısıtı endpoint'te).

Akış:
  1. setup(db, user) — secret üret (pending, totp_enabled_at NULL) + yedek kodlar
     (plain bir kez döner, hash saklanır) + provisioning_uri (QR için).
  2. enable(db, user, code) — TOTP kodu doğrulanırsa totp_enabled_at dolar (aktif).
  3. disable(db, user) — secret + enabled_at temizlenir, yedek kodlar silinir.
  4. verify_login(db, user, code) — login 2. adımı: TOTP veya yedek kod doğrula.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

import pyotp
from sqlalchemy import delete as sa_delete
from sqlalchemy.orm import Session

from app.models import TotpBackupCode, User, UserRole
from app.services.security import hash_password, verify_password


# 2FA'yı yalnız bu roller etkinleştirebilir (kullanıcı kararı 2026-05-20)
TWO_FACTOR_ROLES = {UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN}
BACKUP_CODE_COUNT = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def can_use_2fa(user: User) -> bool:
    return user.role in TWO_FACTOR_ROLES


def generate_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, email: str) -> str:
    from app.config import settings
    issuer = settings.app_name or "ETÜTKOÇ"
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    """TOTP kodu doğrula (±1 pencere = ±30 sn saat sapması toleransı)."""
    if not secret or not code:
        return False
    code = code.strip().replace(" ", "")
    try:
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except Exception:
        return False


def _new_backup_code() -> str:
    """Okunabilir yedek kod: xxxx-xxxx (8 alfanumerik, karışık karakter yok)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 0/O/1/I yok
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _generate_backup_codes(db: Session, user: User) -> list[str]:
    """Eski kodları sil, yeni N kod üret (plain döner, hash saklanır)."""
    db.execute(sa_delete(TotpBackupCode).where(TotpBackupCode.user_id == user.id))
    plain: list[str] = []
    for _ in range(BACKUP_CODE_COUNT):
        code = _new_backup_code()
        plain.append(code)
        db.add(TotpBackupCode(user_id=user.id, code_hash=hash_password(code)))
    return plain


def setup(db: Session, *, user: User) -> tuple[str, str, list[str]]:
    """Secret üret (pending) + yedek kodlar. (secret, provisioning_uri, backup_codes)."""
    secret = generate_secret()
    user.totp_secret = secret
    user.totp_enabled_at = None  # henüz aktif değil; enable ile aktiflenir
    backup_codes = _generate_backup_codes(db, user)
    db.commit()
    return secret, provisioning_uri(secret, email=user.email), backup_codes


def enable(db: Session, *, user: User, code: str) -> bool:
    """Setup'taki secret'ı doğrula → 2FA'yı aktifleştir. Başarı/başarısız."""
    if not user.totp_secret:
        return False
    if not verify_code(user.totp_secret, code):
        return False
    user.totp_enabled_at = _now()
    db.commit()
    return True


def disable(db: Session, *, user: User) -> None:
    user.totp_secret = None
    user.totp_enabled_at = None
    db.execute(sa_delete(TotpBackupCode).where(TotpBackupCode.user_id == user.id))
    db.commit()


def verify_login(db: Session, *, user: User, code: str) -> bool:
    """Login 2. adımı: önce TOTP, eşleşmezse yedek kod (tek kullanım)."""
    if not user.totp_secret:
        return False
    if verify_code(user.totp_secret, code):
        return True
    # Yedek kod denemesi
    norm = (code or "").strip().upper().replace(" ", "")
    rows = (
        db.query(TotpBackupCode)
        .filter(
            TotpBackupCode.user_id == user.id,
            TotpBackupCode.consumed_at.is_(None),
        )
        .all()
    )
    for row in rows:
        if verify_password(norm, row.code_hash):
            row.consumed_at = _now()
            db.commit()
            return True
    return False


def remaining_backup_codes(db: Session, *, user: User) -> int:
    from sqlalchemy import func
    return int(
        db.query(func.count(TotpBackupCode.id))
        .filter(
            TotpBackupCode.user_id == user.id,
            TotpBackupCode.consumed_at.is_(None),
        )
        .scalar()
        or 0
    )
