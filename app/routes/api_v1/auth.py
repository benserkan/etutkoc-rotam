"""API v1 — Auth: login / refresh / logout / me.

JSON-only akış. Cookie session yok; client `Authorization: Bearer ...`
ile access token gönderir. Refresh ise `/auth/refresh` endpoint'ine
`Authorization: Bearer <refresh_token>` gönderir.

Hata formatı: `{"error": "...", "code": "..."}` + HTTP status.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import AuditAction, User, UserRole
from app.routes.api_v1.dependencies import (
    get_current_api_user,
    get_current_refresh_user,
)
from app.services.audit import log_action
from app.services.auth_security import (
    is_locked,
    lockout_seconds_remaining,
    register_failed_login,
    register_successful_login,
)
from app.services.jwt_auth import issue_token_pair
from app.services.rate_limit import enforce_login_rate_limit
from app.services.security import verify_password


router = APIRouter(prefix="/auth", tags=["auth"])


# ============================================================================
# Schemas
# ============================================================================


class LoginIn(BaseModel):
    email: str
    password: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    access_expires_in: int
    refresh_expires_in: int


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    access_expires_in: int


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    grade_level: int | None = None
    is_graduate: bool = False
    institution_id: int | None = None
    institution_name: str | None = None
    must_change_password: bool = False

    @classmethod
    def from_orm_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            grade_level=user.grade_level,
            is_graduate=user.is_graduate,
            institution_id=user.institution_id,
            institution_name=user.institution.name if user.institution else None,
            must_change_password=user.must_change_password,
        )


class LoginOut(BaseModel):
    tokens: TokenPairOut
    user: UserOut


# ============================================================================
# Helpers
# ============================================================================


def _request_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else None)


def _err(status_code: int, error: str, code: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": error, "code": code})


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/login", response_model=LoginOut)
def api_login(
    payload: LoginIn,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """E-posta + şifre → access + refresh token.

    Web login akışıyla aynı politikayı uygular: lockout, audit log,
    pasif hesap engeli. Generic hata mesajı (e-posta enumeration koruması).
    """
    email_norm = payload.email.strip().lower()
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.email == email_norm)
        .first()
    )
    ip = _request_ip(request)

    GENERIC = "E-posta veya şifre hatalı."

    if not user:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=None,
            email_attempted=email_norm,
            request=request,
            details={"reason": "user_not_found", "channel": "api_v1"},
        )
        raise _err(status.HTTP_401_UNAUTHORIZED, GENERIC, "invalid_credentials")

    if not user.is_active:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={"reason": "inactive_account", "channel": "api_v1"},
        )
        raise _err(status.HTTP_401_UNAUTHORIZED, GENERIC, "invalid_credentials")

    if is_locked(user):
        seconds = lockout_seconds_remaining(user)
        log_action(
            db,
            action=AuditAction.LOGIN_LOCKED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={
                "reason": "locked_active",
                "seconds_remaining": seconds,
                "channel": "api_v1",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "Hesap geçici olarak kilitli.",
                "code": "locked",
                "retry_after_seconds": seconds,
            },
        )

    if not verify_password(payload.password, user.password_hash):
        triggered = register_failed_login(user)
        action = AuditAction.LOGIN_LOCKED if triggered else AuditAction.LOGIN_FAILED
        log_action(
            db,
            action=action,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={
                "reason": "wrong_password",
                "failed_count": user.failed_login_count,
                "triggered_lock": triggered,
                "channel": "api_v1",
            },
            autocommit=False,
        )
        db.commit()
        if triggered:
            seconds = lockout_seconds_remaining(user)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error": "Çok fazla başarısız deneme — hesap kilitlendi.",
                    "code": "locked",
                    "retry_after_seconds": seconds,
                },
            )
        raise _err(status.HTTP_401_UNAUTHORIZED, GENERIC, "invalid_credentials")

    register_successful_login(user, ip=ip)
    log_action(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        actor_id=user.id,
        email_attempted=email_norm,
        request=request,
        details={"role": user.role.value, "channel": "api_v1"},
        autocommit=False,
    )
    db.commit()

    now = datetime.now(timezone.utc)
    pair = issue_token_pair(user, now=now)
    return LoginOut(
        tokens=TokenPairOut(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            access_expires_in=pair.access_expires_in,
            refresh_expires_in=pair.refresh_expires_in,
        ),
        user=UserOut.from_orm_user(user),
    )


@router.post("/refresh", response_model=AccessTokenOut)
def api_refresh(user: User = Depends(get_current_refresh_user)):
    """Refresh token → yeni access token.

    Refresh token rotation YOK (stateless). Refresh süresi dolana kadar
    aynı refresh ile yeni access alınır. Şifre değişirse pwd_stamp
    mismatch ile refresh de invalid olur.
    """
    from app.services.jwt_auth import issue_access_token
    from app.config import settings

    now = datetime.now(timezone.utc)
    token = issue_access_token(user, now=now)
    return AccessTokenOut(
        access_token=token,
        access_expires_in=settings.jwt_access_minutes * 60,
    )


@router.post("/logout")
def api_logout(
    request: Request,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    """Stateless logout — server tarafta blacklist yok.

    Client token'larını silmekten sorumlu. Audit için kayıt düşülür;
    şifre değişirse `pwd_stamp` ile invalidate yapılır (gerçek revoke).
    """
    log_action(
        db,
        action=AuditAction.LOGOUT,
        actor_id=user.id,
        request=request,
        details={"channel": "api_v1"},
    )
    return {"ok": True}


# /me is mounted at /api/v1/me (top-level), see app/routes/api_v1/__init__.py
