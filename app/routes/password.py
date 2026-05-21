"""Şifre değiştirme route'u — ilk girişte zorunlu, normal akışta opsiyonel.

Akış:
- Admin tarafından oluşturulan kullanıcı: must_change_password=True
- Login sonrası get_current_user normal döner ama route'lar middleware-benzeri
  kontrol ile /password/change'a yönlendirilir
- Kullanıcı yeni şifre belirleyince must_change_password=False, password_stamp
  güncellenir (diğer oturumlar invalidate olur — ama yeni oturumun kendi
  stamp'i olduğundan etkilenmez).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import AuditAction, User
from app.services.audit import log_action
from app.services.auth_security import (
    is_locked,
    lockout_seconds_remaining,
    register_failed_login,
    register_successful_login,
    validate_password_strength,
)
from app.services.password_breach import breach_check_message, check_password_breach
from app.services.security import hash_password, verify_password
from app.templating import templates


router = APIRouter()


@router.get("/password/change")
def password_change_form(
    request: Request,
    user: User = Depends(require_user),
):
    return templates.TemplateResponse(
        "auth/password_change.html",
        {
            "request": request,
            "user": user,
            "is_forced": user.must_change_password,
            "error": None,
        },
    )


@router.post("/password/change")
def password_change_submit(
    request: Request,
    current_password: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
):
    """Yeni şifre belirleme.

    must_change_password=True ise current_password kontrolü atlanır (admin
    tarafından üretilen geçici şifrenin doğrulanmasına gerek yok — kullanıcı
    zaten oturumda).
    Aksi halde mevcut şifre doğru olmalı.
    """
    err: str | None = None

    # 0) Lockout kontrolü — current_password yanlış denemesi de login lockout'a yansır
    if is_locked(user):
        secs = lockout_seconds_remaining(user)
        mins = max(1, (secs + 59) // 60)
        return templates.TemplateResponse(
            "auth/password_change.html",
            {
                "request": request,
                "user": user,
                "is_forced": user.must_change_password,
                "error": f"Çok fazla başarısız deneme — hesap {mins} dakika kilitli. Bekleyip tekrar dene.",
            },
            status_code=status.HTTP_423_LOCKED,
        )

    # 1) Mevcut şifre kontrol (zorunlu değilse) — yanlışsa rate limit sayacı çalışır
    if not user.must_change_password:
        if not current_password or not verify_password(current_password, user.password_hash):
            triggered_lock = register_failed_login(user)
            log_action(
                db,
                action=AuditAction.LOGIN_LOCKED if triggered_lock else AuditAction.LOGIN_FAILED,
                actor_id=user.id,
                target_type="user", target_id=user.id,
                request=request,
                details={
                    "reason": "wrong_current_password_on_change",
                    "failed_count": user.failed_login_count,
                    "triggered_lock": triggered_lock,
                },
                autocommit=False,
            )
            db.commit()
            if triggered_lock:
                secs = lockout_seconds_remaining(user)
                mins = max(1, (secs + 59) // 60)
                err = f"Çok fazla başarısız deneme — hesap {mins} dakika kilitlendi."
            else:
                err = "Mevcut şifre yanlış."
    # 2) Yeni şifre eşleşme
    if not err and new_password != confirm_password:
        err = "Yeni şifreler birbiriyle eşleşmiyor."
    # 3) Politika
    if not err:
        policy_err = validate_password_strength(new_password, user.role)
        if policy_err:
            err = policy_err
    # 4) Eskiyle aynı olmasın
    if not err and verify_password(new_password, user.password_hash):
        err = "Yeni şifre eski şifreyle aynı olamaz."
    # 5) HaveIBeenPwned breach check — sızdırılmış şifreyi reddet
    if not err:
        breach_count = check_password_breach(new_password)
        if breach_count and breach_count > 0:
            err = breach_check_message(breach_count)

    if err:
        return templates.TemplateResponse(
            "auth/password_change.html",
            {
                "request": request,
                "user": user,
                "is_forced": user.must_change_password,
                "error": err,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Apply
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    # Başarılı şifre değişikliği = güven göstergesi → failed counter sıfırla, kilit kaldır
    user.failed_login_count = 0
    user.locked_until = None
    log_action(
        db,
        action=AuditAction.PASSWORD_CHANGE,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
        details={"forced": False},
        autocommit=False,
    )
    db.commit()
    # Yeni session stamp eşlensin (kendin login'de kal)
    request.session["password_stamp"] = user.password_changed_at.isoformat()

    # Role'e göre home'a yönlendir
    from app.routes.auth import _home_for
    return RedirectResponse(url=_home_for(user), status_code=status.HTTP_303_SEE_OTHER)
