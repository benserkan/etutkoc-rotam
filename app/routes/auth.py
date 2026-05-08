from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import AuditAction, User, UserRole
from app.services.audit import log_action
from app.services.auth_security import (
    is_locked,
    lockout_seconds_remaining,
    register_failed_login,
    register_successful_login,
    session_max_age_for,
)
from app.services.security import verify_password
from app.templating import templates


router = APIRouter()


def _home_for(user: User) -> str:
    """Role bazlı login-sonrası yönlendirme."""
    if user.role == UserRole.SUPER_ADMIN:
        return "/admin"
    if user.role == UserRole.INSTITUTION_ADMIN:
        return "/institution"
    if user.role == UserRole.TEACHER:
        return "/teacher"
    if user.role == UserRole.PARENT:
        return "/parent"
    return "/student"


def _request_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else None)


@router.get("/login")
def login_form(request: Request, user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse(url=_home_for(user), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Login akışı — lockout + audit + last_login tracking ile sertleştirilmiş.

    Akış:
      1. E-posta normalize, kullanıcı bul
      2. Kullanıcı yoksa: audit (login_failed, actor=NULL), generic mesaj
      3. Lockout kontrol: aktif kilitli ise audit (login_locked) + retry sonrası dakikayı söyle
      4. Şifre yanlışsa: register_failed_login → eşik aşılırsa kilitle + audit
      5. Şifre doğru: register_successful_login + session set + audit (login_success)
      6. Yanlış şifre veya yokluk için aynı generic mesaj (e-posta enumeration koruması)
    """
    email_norm = email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    ip = _request_ip(request)

    GENERIC_ERR = "E-posta veya şifre hatalı."

    # 1) Kullanıcı yok
    if not user:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=None,
            email_attempted=email_norm,
            request=request,
            details={"reason": "user_not_found"},
        )
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": GENERIC_ERR},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 2) Pasif hesap
    if not user.is_active:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={"reason": "inactive_account"},
        )
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": GENERIC_ERR},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 3) Lockout aktif mi?
    if is_locked(user):
        seconds = lockout_seconds_remaining(user)
        minutes = max(1, (seconds + 59) // 60)
        log_action(
            db,
            action=AuditAction.LOGIN_LOCKED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={"reason": "locked_active", "seconds_remaining": seconds},
        )
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": (
                    f"Hesap geçici olarak kilitli. Yaklaşık {minutes} dakika sonra "
                    "tekrar deneyin."
                ),
            },
            status_code=status.HTTP_423_LOCKED,
        )

    # 4) Şifre kontrol
    if not verify_password(password, user.password_hash):
        triggered_lock = register_failed_login(user)
        action = AuditAction.LOGIN_LOCKED if triggered_lock else AuditAction.LOGIN_FAILED
        log_action(
            db,
            action=action,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={
                "reason": "wrong_password",
                "failed_count": user.failed_login_count,
                "triggered_lock": triggered_lock,
            },
            autocommit=False,
        )
        db.commit()
        if triggered_lock:
            seconds = lockout_seconds_remaining(user)
            minutes = max(1, (seconds + 59) // 60)
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": (
                        f"Çok fazla başarısız deneme — hesap {minutes} dakika kilitlendi."
                    ),
                },
                status_code=status.HTTP_423_LOCKED,
            )
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": GENERIC_ERR},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 5) Başarılı login
    register_successful_login(user, ip=ip)
    log_action(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        actor_id=user.id,
        email_attempted=email_norm,
        request=request,
        details={"role": user.role.value},
        autocommit=False,
    )
    db.commit()

    # Session bind: password rotation invalidate işareti + role bilgisi
    request.session.clear()  # eski state'i temizle
    request.session["user_id"] = user.id
    request.session["password_stamp"] = (
        user.password_changed_at.isoformat() if user.password_changed_at else None
    )
    request.session["role"] = user.role.value
    request.session["login_at"] = datetime.now(timezone.utc).isoformat()
    # Sliding session: kullanıcı aktivitesi olduğunda last_seen_at güncellenir (deps.py)

    response = RedirectResponse(url=_home_for(user), status_code=status.HTTP_303_SEE_OTHER)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    if uid:
        log_action(
            db,
            action=AuditAction.LOGOUT,
            actor_id=uid,
            request=request,
        )
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
