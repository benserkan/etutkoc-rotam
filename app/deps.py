from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User, UserRole


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.get(User, uid)


def require_user(
    request: Request, user: User | None = Depends(get_current_user)
) -> User:
    if not user or not user.is_active:
        # Redirect to login for browser requests
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Oturum gerekli",
            headers={"Location": "/login"},
        )
    return user


def require_teacher(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sadece öğretmenler")
    return user


def require_student(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sadece öğrenciler")
    return user


def require_parent(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sadece veliler")
    return user


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
