"""Native mobile + external API için JWT auth.

İki tür token:
- **Access token** (1 saat): API çağrılarında `Authorization: Bearer ...`
- **Refresh token** (30 gün): access süresi dolduğunda yenileme için

Token payload:
  {
    "sub": user_id,
    "role": "teacher"|"student"|"parent"|"institution_admin"|"super_admin",
    "type": "access"|"refresh",
    "iat": ...,
    "exp": ...,
    "pwd_stamp": password_changed_at iso  # rotation invalidation
  }

Şifre değiştiğinde tüm eski token'lar invalid (`pwd_stamp` mismatch). Logout için
sunucuda blacklist tutmuyoruz (stateless) — access kısa, refresh client siler.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from app.config import settings
from app.models.user import User


TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Token decode hataları için tek tip."""


@dataclass
class TokenPayload:
    user_id: int
    role: str
    type: TokenType
    issued_at: datetime
    expires_at: datetime
    password_stamp: str | None
    session_id: str | None = None  # BFF ActiveSession takibi (api_v1'de None)
    # Impersonation: bu token bir süper admin tarafından "sahte oturum" için
    # üretildiyse, impersonator (süper admin) id'si. None = normal oturum.
    impersonator_id: int | None = None


# ============================================================================
# Token issue
# ============================================================================


def _make_token(
    *, user: User, kind: TokenType, lifetime: timedelta,
    now: datetime | None = None, sid: str | None = None,
    imp_by: int | None = None,
) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "type": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + lifetime).timestamp()),
        "pwd_stamp": (
            user.password_changed_at.isoformat()
            if user.password_changed_at else None
        ),
    }
    # sid yalnız BFF (api_v2) için set edilir; api_v1 mobile token'ları
    # sid taşımaz → payload birebir aynı kalır (geriye uyum).
    if sid:
        payload["sid"] = sid
    # imp_by yalnız "sahte oturum" (impersonation) token'larında — süper admin'in
    # id'si. Yoksa eklenmez (normal oturum payload'u birebir aynı kalır).
    if imp_by is not None:
        payload["imp_by"] = int(imp_by)
    return jwt.encode(
        payload, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


def issue_access_token(
    user: User, *, now: datetime | None = None, sid: str | None = None,
    imp_by: int | None = None,
) -> str:
    return _make_token(
        user=user, kind="access",
        lifetime=timedelta(minutes=settings.jwt_access_minutes),
        now=now, sid=sid, imp_by=imp_by,
    )


def issue_refresh_token(
    user: User, *, now: datetime | None = None, sid: str | None = None,
    imp_by: int | None = None,
) -> str:
    return _make_token(
        user=user, kind="refresh",
        lifetime=timedelta(days=settings.jwt_refresh_days),
        now=now, sid=sid, imp_by=imp_by,
    )


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in: int  # saniye
    refresh_expires_in: int


def issue_token_pair(
    user: User, *, now: datetime | None = None, sid: str | None = None,
    imp_by: int | None = None,
) -> TokenPair:
    if now is None:
        now = datetime.now(timezone.utc)
    return TokenPair(
        access_token=issue_access_token(user, now=now, sid=sid, imp_by=imp_by),
        refresh_token=issue_refresh_token(user, now=now, sid=sid, imp_by=imp_by),
        access_expires_in=settings.jwt_access_minutes * 60,
        refresh_expires_in=settings.jwt_refresh_days * 86400,
    )


# ============================================================================
# Token decode + verify
# ============================================================================


def decode_token(token: str) -> TokenPayload:
    """Token'ı çöz + doğrula. exp/format hatalarında TokenError fırlatır.
    `pwd_stamp` kontrolü çağıran sorumlu — User'ı yükleyip eşleştirir."""
    try:
        data = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenError(f"Token süresi doldu: {e}") from e
    except jwt.InvalidTokenError as e:
        raise TokenError(f"Geçersiz token: {e}") from e

    try:
        user_id = int(data["sub"])
        role = data["role"]
        kind = data["type"]
        iat = datetime.fromtimestamp(data["iat"], tz=timezone.utc)
        exp = datetime.fromtimestamp(data["exp"], tz=timezone.utc)
        pwd_stamp = data.get("pwd_stamp")
        session_id = data.get("sid")
        imp_by_raw = data.get("imp_by")
        impersonator_id = int(imp_by_raw) if imp_by_raw is not None else None
    except (KeyError, TypeError, ValueError) as e:
        raise TokenError(f"Token payload bozuk: {e}") from e

    if kind not in ("access", "refresh"):
        raise TokenError(f"Geçersiz token tipi: {kind}")

    return TokenPayload(
        user_id=user_id, role=role, type=kind,  # type: ignore[arg-type]
        issued_at=iat, expires_at=exp,
        password_stamp=pwd_stamp, session_id=session_id,
        impersonator_id=impersonator_id,
    )


def verify_against_user(payload: TokenPayload, user: User) -> None:
    """User'la token'ı eşleştir — pwd_stamp + active + role."""
    if not user.is_active:
        raise TokenError("Hesap pasif")
    expected_stamp = (
        user.password_changed_at.isoformat()
        if user.password_changed_at else None
    )
    if payload.password_stamp != expected_stamp:
        raise TokenError(
            "Şifre değişmiş — yeni giriş yapın (token revoke)"
        )
    if payload.role != user.role.value:
        raise TokenError("Rol değişmiş — yeni giriş yapın")
