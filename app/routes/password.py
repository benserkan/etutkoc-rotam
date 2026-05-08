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
from app.services.auth_security import validate_password_strength
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

    # 1) Mevcut şifre kontrol (zorunlu değilse)
    if not user.must_change_password:
        if not current_password or not verify_password(current_password, user.password_hash):
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
