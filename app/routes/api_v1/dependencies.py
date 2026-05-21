"""API v1 — Bearer JWT dependency.

`Authorization: Bearer <access_token>` header'ından token'ı çöz + user yükle.
401 dönüş yapısı: `{"error": "...", "code": "..."}`.

Cookie session (web) ile koegzist; her iki yöntem aynı User modeli ile çalışır.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import User, UserRole
from app.services.jwt_auth import (
    TokenError,
    TokenPayload,
    decode_token,
    verify_against_user,
)


bearer_scheme = HTTPBearer(auto_error=False)


def _auth_error(detail: str, code: str = "unauthorized") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": detail, "code": code},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _resolve_user(
    creds: HTTPAuthorizationCredentials | None,
    db: Session,
    *,
    required_type: str = "access",
) -> User:
    if creds is None or not creds.credentials:
        raise _auth_error("Authorization header eksik", "missing_token")
    token = creds.credentials.strip()
    try:
        payload: TokenPayload = decode_token(token)
    except TokenError as e:
        raise _auth_error(str(e), "invalid_token")
    if payload.type != required_type:
        raise _auth_error(
            f"Bu endpoint {required_type} token bekler, gelen: {payload.type}",
            "wrong_token_type",
        )
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == payload.user_id)
        .first()
    )
    if user is None:
        raise _auth_error("Kullanıcı bulunamadı", "user_not_found")
    try:
        verify_against_user(payload, user)
    except TokenError as e:
        raise _auth_error(str(e), "token_revoked")
    return user


def get_current_api_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Access token gerektirir."""
    return _resolve_user(creds, db, required_type="access")


def get_current_refresh_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Refresh token gerektirir (yalnız /auth/refresh)."""
    return _resolve_user(creds, db, required_type="refresh")


def require_role(*allowed_roles: UserRole):
    """Belirli rolleri gerektirir."""
    def _checker(user: User = Depends(get_current_api_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "Yetki yok", "code": "forbidden"},
            )
        return user
    return _checker


require_api_student = require_role(UserRole.STUDENT)
require_api_teacher = require_role(UserRole.TEACHER, UserRole.INSTITUTION_ADMIN)
