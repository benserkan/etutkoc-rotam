"""SUPER_ADMIN paneli — sistem genelinde kurum/kullanıcı yönetimi.

Sprint 3 multi-tenant — tüm `/admin` route'ları require_super_admin altında.
Audit log her CRUD aksiyonunda yazılır (oluşturma/güncelleme/silme/rol-değişimi).
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_super_admin
from app.models import (
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.audit import log_action
from app.services.auth_security import generate_strong_password
from app.services.security import hash_password
from app.services.tenant_health import (
    bulk_health_assessment,
    churn_summary,
    compute_health_score,
    filter_unhealthy,
)
from app.templating import templates


router = APIRouter(prefix="/admin")


def _slugify(text: str) -> str:
    """Türkçe karakter desteğiyle URL-safe slug üret."""
    text = (text or "").strip().lower()
    replacements = {
        "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
        "İ": "i", "Ç": "c", "Ğ": "g", "Ö": "o", "Ş": "s", "Ü": "u",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:64] or "kurum"


# Eski yardımcı kaldırıldı — generate_strong_password (auth_security.py)
# kullanılır; rol-bazlı güçlü şifre üretir, must_change_password=True ile
# birlikte kullanıcının ilk girişte kendi şifresini belirlemesini zorunlu kılar.


# ---------------------------- Dashboard ----------------------------


@router.get("")
def admin_dashboard(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Genel bakış — sayılar + son audit olayları."""
    counts = {
        "institutions": db.query(Institution).count(),
        "active_institutions": db.query(Institution).filter(Institution.is_active.is_(True)).count(),
        "teachers": db.query(User).filter(User.role == UserRole.TEACHER).count(),
        "students": db.query(User).filter(User.role == UserRole.STUDENT).count(),
        "parents": db.query(User).filter(User.role == UserRole.PARENT).count(),
        "institution_admins": db.query(User).filter(User.role == UserRole.INSTITUTION_ADMIN).count(),
        "super_admins": db.query(User).filter(User.role == UserRole.SUPER_ADMIN).count(),
        "independent_teachers": db.query(User).filter(
            User.role == UserRole.TEACHER, User.institution_id.is_(None)
        ).count(),
    }
    # Stage 5.4 — kurum sağlık özeti + en kritik 3 kurum
    all_insts = db.query(Institution).all()
    health_assessments = bulk_health_assessment(db, institutions=all_insts)
    health_summary = churn_summary(health_assessments)
    top_unhealthy = filter_unhealthy(health_assessments, min_level="risk")[:3]
    # Son 10 audit olayı
    recent_audits = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    # Son 24 saatte başarısız login sayısı (sezgisel uyarı için)
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    failed_logins_24h = (
        db.query(AuditLog)
        .filter(
            AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
            AuditLog.created_at >= cutoff,
        )
        .count()
    )

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "counts": counts,
            "recent_audits": recent_audits,
            "failed_logins_24h": failed_logins_24h,
            "health_summary": health_summary,
            "top_unhealthy": top_unhealthy,
        },
    )


# ---------------------------- Institutions ----------------------------


@router.get("/institutions")
def list_institutions(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
    sort: str = "health",  # 'health' (default, en kritik üstte) | 'name' | 'created'
    filter_level: str | None = None,  # None | 'unhealthy' | 'critical'
):
    institutions = db.query(Institution).all()

    # Her kuruma teacher sayısı (üst kart için kalıyor; assessment de hesaplıyor)
    iids = [i.id for i in institutions]
    teacher_counts: dict[int, int] = {}
    if iids:
        rows = (
            db.query(User.institution_id, sa_func.count(User.id))
            .filter(User.institution_id.in_(iids), User.role == UserRole.TEACHER)
            .group_by(User.institution_id)
            .all()
        )
        teacher_counts = {iid: cnt for iid, cnt in rows}

    # Sağlık skorları — bulk
    assessments = bulk_health_assessment(db, institutions=institutions)
    summary = churn_summary(assessments)

    # Filtreleme
    if filter_level == "unhealthy":
        assessments = filter_unhealthy(assessments, min_level="watch")
    elif filter_level == "critical":
        assessments = filter_unhealthy(assessments, min_level="critical")

    # Sıralama (bulk_health_assessment skor desc döner; alternatifleri uygula)
    if sort == "name":
        assessments.sort(key=lambda a: a.institution.name.lower())
    elif sort == "created":
        assessments.sort(key=lambda a: a.institution.created_at, reverse=True)
    # 'health' default — bulk_health_assessment zaten doğru sırada

    return templates.TemplateResponse(
        "admin/institutions_list.html",
        {
            "request": request,
            "user": user,
            "assessments": assessments,
            "summary": summary,
            "teacher_counts": teacher_counts,
            "sort": sort,
            "filter_level": filter_level,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/institutions")
def create_institution(
    request: Request,
    name: str = Form(...),
    slug: str = Form(""),
    contact_email: str = Form(""),
    plan: str = Form("free"),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    name_clean = (name or "").strip()
    if not name_clean:
        return RedirectResponse(
            url="/admin/institutions?err=" + quote("Kurum adı zorunlu."),
            status_code=303,
        )
    slug_clean = _slugify(slug or name_clean)
    # Çakışmayı kontrol et
    existing = db.query(Institution).filter(Institution.slug == slug_clean).first()
    if existing:
        return RedirectResponse(
            url="/admin/institutions?err=" + quote(
                f"'{slug_clean}' slug'ı zaten kullanılıyor. Farklı bir ad seçin."
            ),
            status_code=303,
        )
    inst = Institution(
        name=name_clean,
        slug=slug_clean,
        contact_email=(contact_email or "").strip().lower() or None,
        plan=(plan or "free").strip() or "free",
        is_active=True,
    )
    db.add(inst)
    db.flush()
    log_action(
        db,
        action=AuditAction.INSTITUTION_CREATE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"name": name_clean, "slug": slug_clean, "plan": inst.plan},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/admin/institutions?ok=" + quote(f"'{name_clean}' kurumu oluşturuldu."),
        status_code=303,
    )


@router.get("/institutions/{institution_id}")
def institution_detail(
    institution_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Kurum bulunamadı")

    teachers = (
        db.query(User)
        .filter(User.institution_id == inst.id, User.role == UserRole.TEACHER)
        .order_by(User.full_name)
        .all()
    )
    institution_admins = (
        db.query(User)
        .filter(User.institution_id == inst.id, User.role == UserRole.INSTITUTION_ADMIN)
        .order_by(User.full_name)
        .all()
    )
    # Bu kuruma ait toplam öğrenci sayısı (teacher üzerinden)
    teacher_ids = [t.id for t in teachers]
    student_count = 0
    if teacher_ids:
        student_count = (
            db.query(User)
            .filter(User.role == UserRole.STUDENT, User.teacher_id.in_(teacher_ids))
            .count()
        )

    # Sağlık skoru — Stage 5.3
    health = compute_health_score(db, institution=inst)

    return templates.TemplateResponse(
        "admin/institution_detail.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "teachers": teachers,
            "institution_admins": institution_admins,
            "student_count": student_count,
            "health": health,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/institutions/{institution_id}/edit")
def edit_institution(
    institution_id: int,
    request: Request,
    name: str = Form(...),
    contact_email: str = Form(""),
    plan: str = Form("free"),
    is_active: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404)
    before = {
        "name": inst.name,
        "contact_email": inst.contact_email,
        "plan": inst.plan,
        "is_active": inst.is_active,
    }
    name_clean = (name or "").strip()
    if not name_clean:
        return RedirectResponse(
            url=f"/admin/institutions/{inst.id}?err=" + quote("Kurum adı zorunlu."),
            status_code=303,
        )
    inst.name = name_clean
    inst.contact_email = (contact_email or "").strip().lower() or None
    inst.plan = (plan or "free").strip() or "free"
    inst.is_active = is_active.strip().lower() in ("on", "1", "true", "yes")
    after = {
        "name": inst.name,
        "contact_email": inst.contact_email,
        "plan": inst.plan,
        "is_active": inst.is_active,
    }
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"before": before, "after": after},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url=f"/admin/institutions/{inst.id}?ok=" + quote("Kurum güncellendi."),
        status_code=303,
    )


@router.post("/institutions/{institution_id}/delete")
def delete_institution(
    institution_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404)
    # Kurumu silince bağlı kullanıcıların institution_id'si SET NULL olur
    # (bağımsız öğretmen olarak yaşamaya devam ederler).
    affected = (
        db.query(User).filter(User.institution_id == inst.id).count()
    )
    name = inst.name
    log_action(
        db,
        action=AuditAction.INSTITUTION_DELETE,
        actor_id=user.id,
        target_type="institution",
        target_id=inst.id,
        request=request,
        details={"name": name, "affected_users": affected},
        autocommit=False,
    )
    db.delete(inst)
    db.commit()
    return RedirectResponse(
        url="/admin/institutions?ok=" + quote(
            f"'{name}' kurumu silindi. {affected} kullanıcı bağımsız oldu."
        ),
        status_code=303,
    )


# ---------------------------- Users ----------------------------


ROLE_LABELS = {
    UserRole.SUPER_ADMIN: "Süper Admin",
    UserRole.INSTITUTION_ADMIN: "Kurum Yöneticisi",
    UserRole.TEACHER: "Öğretmen",
    UserRole.STUDENT: "Öğrenci",
    UserRole.PARENT: "Veli",
}


@router.get("/users")
def list_users(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    role: str | None = None,
    institution_id: str | None = None,
    q: str | None = None,
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm kullanıcılar — rol, kurum, isim/e-posta arama ile filtre."""
    query = db.query(User).options(joinedload(User.institution))
    if role:
        try:
            role_enum = UserRole[role.strip().upper()]
            query = query.filter(User.role == role_enum)
        except KeyError:
            pass
    if institution_id:
        try:
            iid = int(institution_id)
            query = query.filter(User.institution_id == iid)
        except ValueError:
            pass
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.email.ilike(like)) | (User.full_name.ilike(like)))
    users = query.order_by(User.created_at.desc()).limit(500).all()
    institutions = (
        db.query(Institution).order_by(Institution.name).all()
    )
    return templates.TemplateResponse(
        "admin/users_list.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "institutions": institutions,
            "ROLE_LABELS": ROLE_LABELS,
            "filter_role": role,
            "filter_institution_id": institution_id,
            "filter_q": q,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/users")
def create_user(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    institution_id: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin yeni kullanıcı oluşturur.

    Güvenlik: şifre admin tarafından belirlenmez — sistem rol-bazlı güçlü
    şifre üretir, kullanıcı ilk girişte zorunlu olarak kendi şifresini
    belirler (must_change_password=True). Ücretli üyelik akışında bu yer
    davetiye token'ı ile değiştirilecek.
    """
    full_name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()
    if not full_name_clean or not email_clean:
        return RedirectResponse(
            url="/admin/users?err=" + quote("Ad ve e-posta zorunlu."),
            status_code=303,
        )
    try:
        role_enum = UserRole[role.strip().upper()]
    except KeyError:
        return RedirectResponse(
            url="/admin/users?err=" + quote("Geçersiz rol."),
            status_code=303,
        )
    if db.query(User).filter(User.email == email_clean).first():
        return RedirectResponse(
            url="/admin/users?err=" + quote("Bu e-posta zaten kayıtlı."),
            status_code=303,
        )
    iid: int | None = None
    if institution_id.strip():
        try:
            iid = int(institution_id)
            if not db.get(Institution, iid):
                iid = None
        except ValueError:
            iid = None
    if role_enum == UserRole.INSTITUTION_ADMIN and iid is None:
        return RedirectResponse(
            url="/admin/users?err=" + quote(
                "Kurum yöneticisi için kurum seçimi zorunlu."
            ),
            status_code=303,
        )

    # Rol-bazlı güçlü geçici şifre — tek seferlik, kullanıcı ilk girişte değişecek
    pwd = generate_strong_password(role_enum)
    new_user = User(
        email=email_clean,
        password_hash=hash_password(pwd),
        full_name=full_name_clean,
        role=role_enum,
        institution_id=iid,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=True,  # ilk girişte zorunlu değişim
    )
    db.add(new_user)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=user.id,
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={
            "email": email_clean,
            "role": role_enum.value,
            "institution_id": iid,
            "temp_password_issued": True,
        },
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/admin/users?ok=" + quote(
            f"{full_name_clean} oluşturuldu — geçici şifre: {pwd} "
            f"(ilk girişte kendi şifresini belirleyecek)"
        ),
        status_code=303,
    )


@router.get("/users/{user_id}")
def user_detail(
    user_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    target = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == user_id)
        .first()
    )
    if not target:
        raise HTTPException(status_code=404)
    institutions = db.query(Institution).order_by(Institution.name).all()
    # Bu kullanıcının son audit olayları (actor olarak)
    recent_audits = (
        db.query(AuditLog)
        .filter(AuditLog.actor_id == target.id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    return templates.TemplateResponse(
        "admin/user_detail.html",
        {
            "request": request,
            "user": user,
            "target": target,
            "institutions": institutions,
            "ROLE_LABELS": ROLE_LABELS,
            "ROLES": list(UserRole),
            "recent_audits": recent_audits,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/users/{user_id}/edit")
def edit_user(
    user_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    institution_id: str = Form(""),
    is_active: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404)
    full_name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()
    if not full_name_clean or not email_clean:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote("Ad ve e-posta zorunlu."),
            status_code=303,
        )
    if email_clean != target.email:
        if db.query(User).filter(User.email == email_clean).first():
            return RedirectResponse(
                url=f"/admin/users/{user_id}?err=" + quote("Bu e-posta zaten kayıtlı."),
                status_code=303,
            )
    iid: int | None = None
    if institution_id.strip():
        try:
            iid = int(institution_id)
            if not db.get(Institution, iid):
                iid = None
        except ValueError:
            iid = None

    new_active = is_active.strip().lower() in ("on", "1", "true", "yes")
    before = {
        "full_name": target.full_name, "email": target.email,
        "institution_id": target.institution_id, "is_active": target.is_active,
    }
    target.full_name = full_name_clean
    target.email = email_clean
    target.institution_id = iid
    was_active = target.is_active
    target.is_active = new_active
    after = {
        "full_name": target.full_name, "email": target.email,
        "institution_id": target.institution_id, "is_active": target.is_active,
    }
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={"before": before, "after": after},
        autocommit=False,
    )
    if was_active and not new_active:
        log_action(
            db,
            action=AuditAction.USER_DEACTIVATE,
            actor_id=user.id,
            target_type="user",
            target_id=target.id,
            request=request,
            autocommit=False,
        )
    db.commit()
    return RedirectResponse(
        url=f"/admin/users/{user_id}?ok=" + quote("Kullanıcı güncellendi."),
        status_code=303,
    )


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Şifreyi sıfırla — sistem güçlü geçici şifre üretir, kullanıcı ilk
    girişte değiştirmeye zorlanır. Kilit varsa açılır.
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404)
    pwd = generate_strong_password(target.role)
    target.password_hash = hash_password(pwd)
    target.password_changed_at = datetime.now(timezone.utc)
    target.must_change_password = True
    target.failed_login_count = 0
    target.locked_until = None
    log_action(
        db,
        action=AuditAction.PASSWORD_RESET,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={"forced_by_admin": True, "temp_password_issued": True},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url=f"/admin/users/{user_id}?ok=" + quote(
            f"Geçici şifre üretildi: {pwd} (kullanıcı ilk girişte değiştirecek)"
        ),
        status_code=303,
    )


@router.post("/users/{user_id}/change-role")
def change_user_role(
    user_id: int,
    request: Request,
    new_role: str = Form(...),
    institution_id: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404)
    try:
        role_enum = UserRole[new_role.strip().upper()]
    except KeyError:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote("Geçersiz rol."),
            status_code=303,
        )
    # Süper admin kendisinin rolünü değiştirme — diğer süper adminlerden biri yapsın
    if target.id == user.id:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Kendi rolünü değiştiremezsin (kilitlenme riski)."
            ),
            status_code=303,
        )
    iid: int | None = None
    if institution_id.strip():
        try:
            iid = int(institution_id)
        except ValueError:
            iid = None
    if role_enum == UserRole.INSTITUTION_ADMIN and iid is None:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Kurum yöneticisi için kurum seçimi zorunlu."
            ),
            status_code=303,
        )
    old_role = target.role
    target.role = role_enum
    if iid is not None:
        target.institution_id = iid
    log_action(
        db,
        action=AuditAction.ROLE_CHANGE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "from": old_role.value, "to": role_enum.value,
            "institution_id": target.institution_id,
        },
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url=f"/admin/users/{user_id}?ok=" + quote(
            f"Rol değişti: {ROLE_LABELS[old_role]} → {ROLE_LABELS[role_enum]}"
        ),
        status_code=303,
    )


@router.post("/users/{user_id}/delete")
def delete_user(
    user_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404)
    if target.id == user.id:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Kendi hesabını silemezsin."
            ),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_DELETE,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "email": target.email, "role": target.role.value,
        },
        autocommit=False,
    )
    db.delete(target)
    db.commit()
    return RedirectResponse(
        url="/admin/users?ok=" + quote(
            f"{target.full_name} silindi."
        ),
        status_code=303,
    )


# ---------------------------- Impersonate ----------------------------


@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin başka bir kullanıcı olarak sahte oturum açar.

    Session yapısı:
    - user_id: target.id (current_user olarak target döner)
    - role: target.role.value
    - password_stamp: target.password_changed_at
    - impersonator_id: gerçek admin'in id'si (geri dönüş için)
    - impersonate_started_at: ISO timestamp

    Get_current_user normal akışında çalışır — target user görünür. Header
    banner impersonator_id'ye bakıp uyarı gösterir.

    Audit: IMPERSONATE_START actor=admin, target=hedef. Sahte oturum sırasında
    yapılan aksiyonlar target'ın audit trail'inde görünür (admin-as-target).
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404)
    if target.id == user.id:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Kendin olarak sahte oturum aç(a)mazsın."
            ),
            status_code=303,
        )
    if target.role == UserRole.SUPER_ADMIN:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Diğer süper admin olarak oturum açamazsın (yetki sızıntısı)."
            ),
            status_code=303,
        )
    if not target.is_active:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(
                "Pasif kullanıcı olarak sahte oturum açılamaz."
            ),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.IMPERSONATE_START,
        actor_id=user.id,
        target_type="user",
        target_id=target.id,
        request=request,
        details={
            "admin_email": user.email,
            "target_email": target.email,
            "target_role": target.role.value,
        },
    )
    request.session["impersonator_id"] = user.id
    request.session["impersonate_started_at"] = datetime.now(timezone.utc).isoformat()
    request.session["user_id"] = target.id
    request.session["role"] = target.role.value
    request.session["password_stamp"] = (
        target.password_changed_at.isoformat() if target.password_changed_at else None
    )
    # Hedef rolünün ana sayfasına yönlendir
    if target.role == UserRole.TEACHER:
        dest = "/teacher"
    elif target.role == UserRole.STUDENT:
        dest = "/student"
    elif target.role == UserRole.PARENT:
        dest = "/parent"
    elif target.role == UserRole.INSTITUTION_ADMIN:
        dest = "/institution"
    else:
        dest = "/"
    return RedirectResponse(url=dest, status_code=303)


@router.post("/impersonate/end")
def end_impersonation(
    request: Request,
    db: Session = Depends(get_db),
):
    """Sahte oturumu sonlandır, gerçek admin'e geri dön.

    require_super_admin kullanmıyor — çünkü o sırada current_user TARGET'tır.
    Bunun yerine session.impersonator_id'ye bakıyoruz; varsa restore ediyoruz.
    """
    impersonator_id = request.session.get("impersonator_id")
    if not impersonator_id:
        return RedirectResponse(url="/login", status_code=303)
    admin = db.get(User, impersonator_id)
    if not admin or admin.role != UserRole.SUPER_ADMIN or not admin.is_active:
        # Garip durum — admin silinmiş veya pasif olmuş, full logout
        request.session.clear()
        return RedirectResponse(url="/login", status_code=303)
    target_id = request.session.get("user_id")
    log_action(
        db,
        action=AuditAction.IMPERSONATE_END,
        actor_id=admin.id,
        target_type="user",
        target_id=target_id,
        request=request,
        details={"target_user_id": target_id},
    )
    # Admin oturumunu restore et
    request.session.clear()
    request.session["user_id"] = admin.id
    request.session["role"] = admin.role.value
    request.session["password_stamp"] = (
        admin.password_changed_at.isoformat()
        if admin.password_changed_at else None
    )
    request.session["login_at"] = datetime.now(timezone.utc).isoformat()
    return RedirectResponse(url="/admin", status_code=303)


# ---------------------------- Audit Log Viewer ----------------------------


def _parse_date_filter(s: str | None) -> "date | None":
    """YYYY-MM-DD parse et; geçersizse None döner (sessizce)."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        from datetime import date as _date
        return _date.fromisoformat(s)
    except ValueError:
        return None


@router.get("/audit")
def audit_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    action: str | None = None,
    actor_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
):
    """Audit olaylarını listele — filtre + sayfalama (50 per page).

    Filtreler: action (enum value), actor_id (int), start_date/end_date
    (YYYY-MM-DD). Tarih aralığı INCLUSIVE: end_date günü dahil (cutoff
    end_date+1 gün UTC).
    """
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    PER_PAGE = 50
    page = max(1, page)
    query = db.query(AuditLog)
    if action:
        try:
            action_enum = AuditAction[action.strip().upper()]
            query = query.filter(AuditLog.action == action_enum)
        except KeyError:
            pass
    if actor_id:
        try:
            aid = int(actor_id)
            query = query.filter(AuditLog.actor_id == aid)
        except ValueError:
            pass

    sd = _parse_date_filter(start_date)
    ed = _parse_date_filter(end_date)
    if sd is not None:
        sd_dt = _dt.combine(sd, _dt.min.time(), tzinfo=_tz.utc)
        query = query.filter(AuditLog.created_at >= sd_dt)
    if ed is not None:
        # Inclusive: o günün sonu = ertesi günün başı
        ed_dt = _dt.combine(ed + _td(days=1), _dt.min.time(), tzinfo=_tz.utc)
        query = query.filter(AuditLog.created_at < ed_dt)

    total = query.count()
    audits = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * PER_PAGE)
        .limit(PER_PAGE)
        .all()
    )
    # Actor isim eşlemesi (tek toplu sorgu) + sahte oturum ile yapılan
    # aksiyonların admin'lerini de aynı sorguda topla
    actor_ids: set[int] = {a.actor_id for a in audits if a.actor_id}
    via_admin_map: dict[int, int] = {}  # audit.id -> admin_id (eğer impersonate ise)
    import json as _json
    for a in audits:
        if not a.details_json:
            continue
        try:
            d = _json.loads(a.details_json)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict) and d.get("_via_admin"):
            try:
                admin_id = int(d["_via_admin"])
                via_admin_map[a.id] = admin_id
                actor_ids.add(admin_id)
            except (ValueError, TypeError):
                pass

    actors_map: dict[int, User] = {}
    if actor_ids:
        for u in db.query(User).filter(User.id.in_(actor_ids)).all():
            actors_map[u.id] = u

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    return templates.TemplateResponse(
        "admin/audit_list.html",
        {
            "request": request,
            "user": user,
            "audits": audits,
            "actors_map": actors_map,
            "via_admin_map": via_admin_map,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "per_page": PER_PAGE,
            "filter_action": action,
            "filter_actor_id": actor_id,
            "filter_start_date": (sd.isoformat() if sd else ""),
            "filter_end_date": (ed.isoformat() if ed else ""),
            "all_actions": list(AuditAction),
        },
    )
