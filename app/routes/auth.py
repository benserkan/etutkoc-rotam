import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

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
from app.services import security_monitor as secmon
from app.services.turnstile import get_site_key as turnstile_site_key
from app.services.turnstile import is_enabled as turnstile_enabled
from app.services.turnstile import verify_token as turnstile_verify
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
    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": None,
            "turnstile_site_key": turnstile_site_key(),
        },
    )


@router.post("/login")
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    cf_turnstile_response: str = Form("", alias="cf-turnstile-response"),
    db: Session = Depends(get_db),
):
    """Login akışı — lockout + audit + last_login tracking ile sertleştirilmiş.

    Akış:
      0. Turnstile CAPTCHA kontrol (aktifse) — bot/script saldırı koruması
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

    # 0a) IP brute-force blok kontrolü (auth_security'den önce — hesap bile
    # tespit edilmeden önce reddet)
    blocked, _row = secmon.is_ip_blocked(db, ip=ip)
    if blocked:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=user.id if user else None,
            email_attempted=email_norm,
            request=request,
            details={"reason": "ip_blocked"},
        )
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": (
                    "Bu IP geçici olarak engellendi. Lütfen daha sonra tekrar deneyin."
                ),
                "turnstile_site_key": turnstile_site_key(),
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # 0) CAPTCHA — sadece Turnstile aktifse kontrol edilir; disabled ise geçilir
    if turnstile_enabled():
        if not turnstile_verify(cf_turnstile_response, ip=ip):
            log_action(
                db,
                action=AuditAction.LOGIN_FAILED,
                actor_id=user.id if user else None,
                email_attempted=email_norm,
                request=request,
                details={"reason": "captcha_failed"},
            )
            return templates.TemplateResponse(
                "auth/login.html",
                {
                    "request": request,
                    "error": "Bot doğrulaması başarısız. Sayfayı yenile ve tekrar dene.",
                    "turnstile_site_key": turnstile_site_key(),
                },
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

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
        secmon.record_failed_login_ip(db, ip=ip, email_attempted=email_norm)
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
        secmon.record_failed_login_ip(
            db, ip=ip, email_attempted=email_norm, autocommit=False
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
    # Otonom resume: pasif user "auto_*" sebepliyse giriş = aktivite sinyali
    # → derhal aktife alınır. Manuel pasif olanlar etkilenmez (koç kararı korunur).
    try:
        from app.services.pause import maybe_auto_resume
        if maybe_auto_resume(db, user):
            log_action(
                db,
                action=AuditAction.USER_AUTO_RESUME,
                actor_id=None,
                target_type="user",
                target_id=user.id,
                request=request,
                details={"trigger": "login"},
                autocommit=False,
            )
    except Exception:
        # auto-resume hatası login akışını bozmasın
        logger.exception("auto-resume login hatasi user=%s", user.id)
    db.commit()

    # Session bind: password rotation invalidate işareti + role bilgisi
    request.session.clear()  # eski state'i temizle
    request.session["user_id"] = user.id
    request.session["password_stamp"] = (
        user.password_changed_at.isoformat() if user.password_changed_at else None
    )
    request.session["role"] = user.role.value
    request.session["login_at"] = datetime.now(timezone.utc).isoformat()
    # Katman 11.A — ActiveSession kaydı + heartbeat için unique token
    session_token = secmon.generate_session_token()
    request.session["session_token"] = session_token
    try:
        secmon.record_session_start(
            db,
            user=user,
            session_token=session_token,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        logger.exception("active_session record fail user=%s", user.id)
    # Süper admin login alarmı (in-app rozet için audit kalır; email isteğe bağlı)
    if user.role == UserRole.SUPER_ADMIN:
        try:
            from app.services.security_monitor_alerts import notify_super_admin_login
            notify_super_admin_login(db, user=user, ip=ip, request=request)
        except Exception:
            logger.exception("super_admin login alarm fail user=%s", user.id)

    response = RedirectResponse(url=_home_for(user), status_code=status.HTTP_303_SEE_OTHER)
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    uid = request.session.get("user_id")
    token = request.session.get("session_token")
    if uid:
        log_action(
            db,
            action=AuditAction.LOGOUT,
            actor_id=uid,
            request=request,
        )
    if token:
        try:
            secmon.terminate_session(db, session_token=token, reason="logout")
        except Exception:
            logger.exception("active_session terminate (logout) fail")
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
