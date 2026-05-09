"""Self-signup ve davetiyeli signup akışları.

İki giriş noktası:
- /signup/teacher: bağımsız öğretmen kaydı (institution_id = NULL)
- /signup/invite/{token}: davetiyeli kayıt (kurum/rol token'dan gelir)

Güvenlik:
- Bağımsız öğretmen kaydı için CAPTCHA yok (şu an), email doğrulama yok
  (sonraki sprint). Rate-limit eklenmeli ama şimdilik IP başına audit trail
  yeterli görüyoruz.
- Davetiye token'ı tek seferlik; consumed olunca tekrar kullanılamaz.
- Token süresi geçmiş, iptal edilmiş veya tüketilmişse 410 Gone döner.
- Şifre kullanıcı tarafından belirlenir → must_change_password=False (admin
  oluştursaydı True olurdu).
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, get_current_user
from app.models import (
    AuditAction,
    Institution,
    Invitation,
    InvitationStatus,
    User,
    UserRole,
    invitation_default_expiry,
)
from app.services.audit import log_action
from app.services.auth_security import validate_password_strength
from app.services.security import hash_password
from app.templating import templates


router = APIRouter()


# ---------------------------- Bağımsız öğretmen kaydı ----------------------------


@router.get("/signup/teacher")
def signup_teacher_form(
    request: Request,
    user: User | None = Depends(get_current_user),
):
    """Bağımsız öğretmen kayıt formu. Zaten giriş yapılmışsa home'a yönlendir."""
    if user:
        from app.routes.auth import _home_for
        return RedirectResponse(url=_home_for(user), status_code=303)
    return templates.TemplateResponse(
        "auth/signup_teacher.html",
        {"request": request, "error": None, "filled": {}},
    )


@router.post("/signup/teacher")
def signup_teacher_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    accept_terms: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Bağımsız öğretmen oluşturur (institution_id=NULL).

    Doğrulamalar:
    - E-posta benzersiz
    - Şifre eşleşmesi + politika (TEACHER min 10 + özel karakter)
    - Şartları kabul (accept_terms checkbox)
    """
    if user:
        from app.routes.auth import _home_for
        return RedirectResponse(url=_home_for(user), status_code=303)

    full_name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()
    filled = {"full_name": full_name_clean, "email": email_clean}

    err: str | None = None
    if not full_name_clean or not email_clean:
        err = "Ad ve e-posta zorunlu."
    elif "@" not in email_clean or "." not in email_clean:
        err = "Geçerli bir e-posta girin."
    elif not accept_terms.strip():
        err = "Kullanım şartlarını kabul etmelisin."
    elif password != password_confirm:
        err = "Şifreler birbiriyle eşleşmiyor."
    else:
        policy_err = validate_password_strength(password, UserRole.TEACHER)
        if policy_err:
            err = policy_err
        elif db.query(User).filter(User.email == email_clean).first():
            err = "Bu e-posta zaten kayıtlı. Giriş yapmayı dene veya farklı bir e-posta kullan."

    if err:
        return templates.TemplateResponse(
            "auth/signup_teacher.html",
            {"request": request, "error": err, "filled": filled},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    new_user = User(
        email=email_clean,
        password_hash=hash_password(password),
        full_name=full_name_clean,
        role=UserRole.TEACHER,
        institution_id=None,  # bağımsız
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=False,  # kullanıcı kendi belirledi
    )
    db.add(new_user)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=new_user.id,  # self-signup → actor = kendisi
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={
            "email": email_clean, "role": "teacher", "self_signup": True,
            "institution_id": None,
        },
        autocommit=False,
    )
    db.commit()

    # Otomatik giriş yap
    request.session.clear()
    request.session["user_id"] = new_user.id
    request.session["role"] = new_user.role.value
    request.session["password_stamp"] = (
        new_user.password_changed_at.isoformat()
        if new_user.password_changed_at else None
    )
    request.session["login_at"] = datetime.now(timezone.utc).isoformat()
    return RedirectResponse(url="/teacher", status_code=303)


# ---------------------------- Davetiyeli kayıt ----------------------------


def _get_invitation(db: Session, token: str) -> Invitation | None:
    return (
        db.query(Invitation)
        .options(joinedload(Invitation.institution))
        .filter(Invitation.token == token)
        .first()
    )


@router.get("/signup/invite/{token}")
def signup_invite_form(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    """Davetiye token'ı ile kayıt formu. Token geçerli değilse açıklayıcı sayfa.

    Halihazırda giriş yapmışsa logout'a yönlendir — davetiyeyi kabul etmek
    için temiz oturum gerek.
    """
    inv = _get_invitation(db, token)
    if inv is None:
        raise HTTPException(status_code=404, detail="Davetiye bulunamadı")

    template_ctx = {
        "request": request,
        "invitation": inv,
        "error": None,
        "filled": {
            "full_name": inv.full_name or "",
            "email": inv.email or "",
        },
    }

    if not inv.is_usable:
        return templates.TemplateResponse(
            "auth/signup_invite_unusable.html",
            template_ctx,
            status_code=status.HTTP_410_GONE,
        )
    if user:
        # Mevcut oturum davetiyeyi tüketmemeli — açıkla
        return templates.TemplateResponse(
            "auth/signup_invite_logged_in.html",
            {"request": request, "invitation": inv, "user": user},
        )
    return templates.TemplateResponse("auth/signup_invite.html", template_ctx)


@router.post("/signup/invite/{token}")
def signup_invite_submit(
    token: str,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    accept_terms: str = Form(""),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    inv = _get_invitation(db, token)
    if inv is None:
        raise HTTPException(status_code=404)
    if not inv.is_usable:
        return templates.TemplateResponse(
            "auth/signup_invite_unusable.html",
            {"request": request, "invitation": inv, "error": None},
            status_code=status.HTTP_410_GONE,
        )
    if user:
        return RedirectResponse(url=f"/signup/invite/{token}", status_code=303)

    full_name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()
    filled = {"full_name": full_name_clean, "email": email_clean}

    err: str | None = None
    if not full_name_clean or not email_clean:
        err = "Ad ve e-posta zorunlu."
    elif "@" not in email_clean or "." not in email_clean:
        err = "Geçerli bir e-posta girin."
    elif not accept_terms.strip():
        err = "Kullanım şartlarını kabul etmelisin."
    elif password != password_confirm:
        err = "Şifreler birbiriyle eşleşmiyor."
    else:
        policy_err = validate_password_strength(password, inv.role)
        if policy_err:
            err = policy_err
        elif db.query(User).filter(User.email == email_clean).first():
            err = "Bu e-posta zaten kayıtlı. Davetiyeyi farklı e-postaya yönlendirin."

    if err:
        return templates.TemplateResponse(
            "auth/signup_invite.html",
            {"request": request, "invitation": inv, "error": err, "filled": filled},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Stage 8 — kuota kontrolü (davet kabul aşamasında)
    if inv.institution_id is not None:
        from app.models import Institution
        from app.services.quotas import check_quota_for_create, QuotaExceeded
        inst = db.get(Institution, inv.institution_id)
        if inst is not None:
            qkey = (
                "institution_admins" if inv.role.value == "institution_admin"
                else "teachers" if inv.role.value == "teacher"
                else "students" if inv.role.value == "student"
                else None
            )
            if qkey:
                try:
                    check_quota_for_create(db, institution=inst, quota_key=qkey)
                except QuotaExceeded as e:
                    return templates.TemplateResponse(
                        "auth/signup_invite.html",
                        {"request": request, "invitation": inv,
                         "error": f"Kuota: {e.message}", "filled": filled},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )

    # Atomik akış: kullanıcıyı oluştur + davetiyeyi tüket
    new_user = User(
        email=email_clean,
        password_hash=hash_password(password),
        full_name=full_name_clean,
        role=inv.role,
        institution_id=inv.institution_id,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=False,
    )
    db.add(new_user)
    db.flush()
    inv.consumed_at = datetime.now(timezone.utc)
    inv.consumed_by_user_id = new_user.id
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=new_user.id,
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={
            "email": email_clean,
            "role": inv.role.value,
            "institution_id": inv.institution_id,
            "via_invitation_id": inv.id,
        },
        autocommit=False,
    )
    db.commit()

    # Otomatik giriş
    request.session.clear()
    request.session["user_id"] = new_user.id
    request.session["role"] = new_user.role.value
    request.session["password_stamp"] = new_user.password_changed_at.isoformat()
    request.session["login_at"] = datetime.now(timezone.utc).isoformat()

    from app.routes.auth import _home_for
    return RedirectResponse(url=_home_for(new_user), status_code=303)
