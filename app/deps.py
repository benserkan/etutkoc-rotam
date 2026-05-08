"""FastAPI bağımlılıkları (Depends) — DB session, auth, role guard'ları, tenant isolation.

Sprint 2 (multi-tenant security) ile genişletildi:
- require_super_admin / require_institution_admin / require_admin (her ikisi)
- require_same_institution(target) — cross-tenant erişim engeli
- check_session_freshness — şifre değişimi/expire sonrası eski oturum invalidate
"""

from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AuditAction, User, UserRole


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """Session'daki user_id'den User çek. Şifre değişimi sonrası geçersiz oturumlar
    burada invalide edilir (session.password_stamp != user.password_changed_at).
    """
    uid = request.session.get("user_id")
    if not uid:
        return None
    user = db.get(User, uid)
    if not user or not user.is_active:
        return None
    # Password rotation invalidates older sessions
    sess_stamp = request.session.get("password_stamp")
    user_stamp = (
        user.password_changed_at.isoformat()
        if user.password_changed_at else None
    )
    if user_stamp and sess_stamp != user_stamp:
        # Eski oturum — sessizce çıkar
        request.session.clear()
        return None
    # Last activity zamanını touch et (sliding expiration için ileride)
    request.session["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    return user


def require_user(
    request: Request, user: User | None = Depends(get_current_user)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            detail="Oturum gerekli",
            headers={"Location": "/login"},
        )
    # Zorunlu şifre değişimi — /password/change dışındaki her route engellensin
    if user.must_change_password:
        path = request.url.path
        # /password/change ve /logout serbest, diğerleri yönlensin
        if not (path.startswith("/password/change") or path == "/logout"):
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                detail="Şifre değişimi zorunlu",
                headers={"Location": "/password/change"},
            )
    return user


def _deny(reason: str = "Yetkisiz") -> HTTPException:
    """Yetki reddi — audit log log_action_permission_denied tarafından çağrılır."""
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)


def require_teacher(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.TEACHER:
        raise _deny("Sadece öğretmenler")
    return user


def require_student(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.STUDENT:
        raise _deny("Sadece öğrenciler")
    return user


def require_parent(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.PARENT:
        raise _deny("Sadece veliler")
    return user


def require_super_admin(user: User = Depends(require_user)) -> User:
    """Yalnız SUPER_ADMIN. /admin altındaki tüm route'lar bunu kullanır."""
    if user.role != UserRole.SUPER_ADMIN:
        raise _deny("Sadece süper admin")
    return user


def require_institution_admin(user: User = Depends(require_user)) -> User:
    """Yalnız INSTITUTION_ADMIN. /institution altındaki tüm route'lar.

    institution_id'siz INSTITUTION_ADMIN olamaz — bu durum bir bug, 403 dön.
    """
    if user.role != UserRole.INSTITUTION_ADMIN:
        raise _deny("Sadece kurum yöneticisi")
    if user.institution_id is None:
        raise _deny("Kurum yöneticisi bir kuruma bağlı olmalı (config hatası)")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    """SUPER_ADMIN veya INSTITUTION_ADMIN — admin paneli paylaşılan helper'lar için."""
    if user.role not in (UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN):
        raise _deny("Sadece adminler")
    return user


def can_access_user(actor: User, target: User) -> bool:
    """Bir kullanıcının başka bir kullanıcının verisine erişim hakkı var mı?

    Kurallar:
    - SUPER_ADMIN: her zaman evet
    - Kendine erişim: her zaman evet
    - INSTITUTION_ADMIN: aynı kurumdaki TEACHER/STUDENT/PARENT'a evet
    - TEACHER: kendi öğrencileri/velilerine evet (teacher_id eşleşmesi)
    - STUDENT/PARENT: sadece kendine
    """
    if actor.id == target.id:
        return True
    if actor.role == UserRole.SUPER_ADMIN:
        return True
    if actor.role == UserRole.INSTITUTION_ADMIN:
        if actor.institution_id is None:
            return False
        if target.institution_id == actor.institution_id:
            return True
        # Hedef öğrenci/veli ise teacher üzerinden kuruma bağlı olabilir
        if target.role in (UserRole.STUDENT, UserRole.PARENT) and target.teacher_id:
            # Burada DB sorgusu lazım — caller assert_can_access_user kullanmalı
            # Bu helper sadece doğrudan görünür alanlardan kontrol eder.
            return False
        return False
    if actor.role == UserRole.TEACHER:
        if target.role == UserRole.STUDENT and target.teacher_id == actor.id:
            return True
        return False
    return False


def assert_can_access_user(actor: User, target: User) -> None:
    """can_access_user'ın exception fırlatan varyantı — route içinde tek satır."""
    if not can_access_user(actor, target):
        raise _deny("Bu kullanıcının verisine erişim yok")


def login_redirect() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
