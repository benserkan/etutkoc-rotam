"""SUPER_ADMIN paneli — sistem genelinde kurum/kullanıcı yönetimi.

Sprint 3 multi-tenant — tüm `/admin` route'ları require_super_admin altında.
Audit log her CRUD aksiyonunda yazılır (oluşturma/güncelleme/silme/rol-değişimi).
"""

from __future__ import annotations

import re
import secrets
import string
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
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


def _independent_teacher_activity(db: Session) -> tuple[dict, list[dict]]:
    """Bağımsız öğretmen (role=TEACHER, institution_id=NULL, is_active=True)
    aktivite özeti. Login-bazlı heuristik bantlar:
      healthy  : son 7g içinde giriş
      watch    : 7-14 gün
      risk     : 14-30 gün
      critical : 30g+ veya hiç giriş yok

    Dönen tuple:
      (summary_dict, all_rows)
      summary_dict: {healthy, watch, risk, critical, unhealthy_total, total}
      all_rows: tüm öğretmenler için {user, band, days_since_login, label,
                                       last_login_at}
                — risk yoğun olanlar önde, sonra yakın login olanlar
    """
    from datetime import datetime as _dt, timezone as _tz
    now_utc = _dt.now(_tz.utc)
    indep_teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.full_name.asc(), User.id.asc())
        .all()
    )
    summary = {"healthy": 0, "watch": 0, "risk": 0, "critical": 0}
    rows: list[dict] = []
    for t in indep_teachers:
        last = t.last_login_at
        if last is None:
            days = None
            band = "critical"
            label = "hiç giriş yok"
        else:
            if last.tzinfo is None:
                last = last.replace(tzinfo=_tz.utc)
            days = (now_utc - last).days
            if days >= 30:
                band = "critical"
            elif days >= 14:
                band = "risk"
            elif days >= 7:
                band = "watch"
            else:
                band = "healthy"
            label = f"{days}g önce" if days > 0 else "bugün"
        summary[band] += 1
        rows.append({
            "user": t,
            "band": band,
            "days_since_login": days,
            "label": label,
            "last_login_at": t.last_login_at,
        })
    # Sıralama: dikkat çeken üstte (critical → risk → watch → healthy);
    # aynı bantta daha eski daha öncelikli (days_since_login büyük)
    band_order = {"critical": 0, "risk": 1, "watch": 2, "healthy": 3}
    rows.sort(
        key=lambda r: (band_order.get(r["band"], 9), -(r["days_since_login"] or 9999)),
    )
    summary["unhealthy_total"] = summary["risk"] + summary["critical"]
    summary["total"] = len(indep_teachers)
    return summary, rows


@router.get("/independent-teachers")
def independent_teachers_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bağımsız öğretmenler listesi — her satırdan Bağımsız 360'a erişim."""
    summary, rows = _independent_teacher_activity(db)
    return templates.TemplateResponse(
        "admin/independent_teachers_list.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
            "rows": rows,
        },
    )


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

    # Sprint F.3 — bağımsız öğretmen aktivite özeti (login-bazlı heuristik).
    # Helper paylaşımlı: /admin ve /admin/independent-teachers aynı veriyi kullanır.
    teacher_activity_summary, teacher_risk_rows = _independent_teacher_activity(db)
    top_teacher_risk = teacher_risk_rows[:3]
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
            "teacher_activity_summary": teacher_activity_summary,
            "top_teacher_risk": top_teacher_risk,
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


# Stage 8 — Tenant backup snapshot (KVKK madde 11 veri taşıma + manuel yedekleme)


@router.get("/institutions/{institution_id}/backup")
def institution_backup_download(
    institution_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurumun tüm verisini JSON olarak indir.

    İçerik: institution + users (password_hash REDACTED) + books + tasks +
    notifications (son 30g) + audit (son 90g) + credits + digests +
    feature_flag/quota overrides + parent links.
    """
    from datetime import date as _date
    from fastapi.responses import Response
    from app.services.tenant_backup import export_tenant_json

    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Kurum bulunamadı")

    payload = export_tenant_json(db, institution=inst)
    today_str = _date.today().isoformat()
    filename = f"{inst.slug}-backup-{today_str}.json"

    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="institution_backup",
        target_id=inst.id,
        request=request,
        details={
            "action": "backup_downloaded",
            "institution_slug": inst.slug,
            "size_bytes": len(payload.encode("utf-8")),
        },
    )

    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/institutions/{institution_id}/account-history")
def institution_account_history(
    institution_id: int,
    request: Request,
    years: int = 3,
    include_archived: int = 0,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum hesap hareketleri — plan değişimleri + faturalar timeline'ı.

    Pencere: son N yıl (varsayılan 3). include_archived=1 ile arşivli kayıtlar
    da gösterilir. 3 yıldan eski + arşivlenmemiş kayıt varsa "Toplu arşivle"
    butonu görünür.
    """
    from app.services.account_history import account_history
    inst = db.get(Institution, institution_id)
    if inst is None:
        raise HTTPException(status_code=404, detail="Kurum bulunamadı")
    years = max(1, min(int(years or 3), 10))
    data = account_history(
        db, owner_type="institution", owner_id=institution_id,
        years=years, include_archived=bool(include_archived),
    )
    return templates.TemplateResponse(
        "admin/account_history.html",
        {
            "request": request, "user": user, "data": data,
            "owner_kind_label": "Kurum",
            "back_url": f"/admin/institutions/{institution_id}",
        },
    )


@router.get("/users/{user_id}/account-history")
def user_account_history(
    user_id: int,
    request: Request,
    years: int = 3,
    include_archived: int = 0,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Öğretmen/kullanıcı hesap hareketleri — plan değişimleri timeline'ı.

    Faturalar şu an sadece kurum bazlı; öğretmenler için boş kalır (ileride
    bireysel öğretmen faturalandırması eklenirse otomatik gelir).
    """
    from app.services.account_history import account_history
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    years = max(1, min(int(years or 3), 10))
    data = account_history(
        db, owner_type="user", owner_id=user_id,
        years=years, include_archived=bool(include_archived),
    )
    return templates.TemplateResponse(
        "admin/account_history.html",
        {
            "request": request, "user": user, "data": data,
            "owner_kind_label": "Kullanıcı",
            "back_url": f"/admin/users/{user_id}",
        },
    )


@router.post("/account-history/archive")
def account_history_archive(
    request: Request,
    record_type: str = Form(...),
    record_id: int = Form(...),
    note: str = Form(""),
    return_to: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Tek bir kaydı (plan_history veya invoice) arşive ekle."""
    from app.services.account_history import archive_record
    result = archive_record(
        db, record_type=record_type, record_id=record_id,
        by_user_id=user.id, note=note or None,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_{record_type}",
        target_id=record_id,
        request=request,
        details={"action": "archive", "ok": result.get("ok"),
                  "error": result.get("error"), "note": (note or "")[:200]},
    )
    msg = "Kayıt arşivlendi" if result.get("ok") else f"Hata: {result.get('error')}"
    url = return_to or "/admin"
    sep = "&" if "?" in url else "?"
    key = "ok" if result.get("ok") else "err"
    return RedirectResponse(url=f"{url}{sep}{key}=" + quote(msg), status_code=303)


@router.post("/account-history/unarchive")
def account_history_unarchive(
    request: Request,
    record_type: str = Form(...),
    record_id: int = Form(...),
    return_to: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Arşivden geri al (soft archive → aktif)."""
    from app.services.account_history import unarchive_record
    result = unarchive_record(
        db, record_type=record_type, record_id=record_id,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_{record_type}",
        target_id=record_id,
        request=request,
        details={"action": "unarchive", "ok": result.get("ok"),
                  "error": result.get("error")},
    )
    msg = "Arşivden çıkarıldı" if result.get("ok") else f"Hata: {result.get('error')}"
    url = return_to or "/admin"
    sep = "&" if "?" in url else "?"
    key = "ok" if result.get("ok") else "err"
    return RedirectResponse(url=f"{url}{sep}{key}=" + quote(msg), status_code=303)


@router.post("/account-history/bulk-archive")
def account_history_bulk_archive(
    request: Request,
    owner_type: str = Form(...),
    owner_id: int = Form(...),
    years: int = Form(3),
    note: str = Form(""),
    return_to: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir kurum/öğretmenin X yıldan eski TÜM kayıtlarını topluca arşivle."""
    from app.services.account_history import bulk_archive_older_than
    if owner_type not in ("institution", "user"):
        raise HTTPException(status_code=400, detail="invalid owner_type")
    years = max(1, min(int(years), 10))
    result = bulk_archive_older_than(
        db, owner_type=owner_type, owner_id=owner_id,
        years=years, by_user_id=user.id, note=note or None,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type=f"account_history_bulk_{owner_type}",
        target_id=owner_id,
        request=request,
        details={
            "action": "bulk_archive",
            "years": years,
            "plan_count": result.get("plan_count"),
            "invoice_count": result.get("invoice_count"),
            "total": result.get("total"),
        },
    )
    msg = (
        f"{result['total']} kayıt arşive eklendi "
        f"({result['plan_count']} plan, {result['invoice_count']} fatura)"
    )
    url = return_to or "/admin"
    sep = "&" if "?" in url else "?"
    return RedirectResponse(url=f"{url}{sep}ok=" + quote(msg), status_code=303)


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
    reason: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin başka bir kullanıcı olarak sahte oturum açar.

    Katman 11.B değişiklikleri:
    - reason form alanı **zorunlu** (10-200 karakter)
    - ImpersonationSession kaydı oluşturulur (30 dk expire ile)
    - request.session["impersonation_id"] saklanır → deps.py auto-end kontrolü
    """
    from app.services.impersonation import (
        find_active_for_actor_target,
        start_session,
        validate_reason,
    )

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

    # 11.B — zorunlu gerekçe
    validation = validate_reason(reason)
    if not validation.ok:
        return RedirectResponse(
            url=f"/admin/users/{user_id}?err=" + quote(validation.error or "Gerekçe gerekli"),
            status_code=303,
        )

    # Aynı admin'in aynı target için zaten aktif oturumu varsa onu kapatıp yenisini aç
    existing = find_active_for_actor_target(
        db, actor_id=user.id, target_id=target.id
    )
    if existing is not None:
        existing.ended_at = datetime.now(timezone.utc)
        existing.end_reason = "manual"
        existing.ended_by_user_id = user.id
        db.commit()

    ip = (request.client.host if request.client else None)
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()[:64]

    imp = start_session(
        db, actor=user, target=target, reason=validation.cleaned, ip=ip
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
            "reason": validation.cleaned,
            "impersonation_id": imp.id,
            "expires_at": imp.expires_at.isoformat(),
        },
    )
    request.session["impersonator_id"] = user.id
    request.session["impersonate_started_at"] = datetime.now(timezone.utc).isoformat()
    request.session["impersonation_id"] = imp.id  # 11.B — deps.py auto-end için
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
    # 11.B — ImpersonationSession kaydını kapat (manuel)
    imp_id = request.session.get("impersonation_id")
    if imp_id:
        try:
            from app.services.impersonation import end_session as _end_imp
            _end_imp(
                db, session_id=imp_id, end_reason="manual",
                ended_by_user_id=admin.id,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "impersonation end fail imp=%s", imp_id
            )
    log_action(
        db,
        action=AuditAction.IMPERSONATE_END,
        actor_id=admin.id,
        target_type="user",
        target_id=target_id,
        request=request,
        details={
            "target_user_id": target_id,
            "impersonation_id": imp_id,
        },
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
    # aksiyonların admin'lerini de aynı sorguda topla.
    # 11.B — details_json bir kez parse edilir; template diff görünümünde kullanılır.
    actor_ids: set[int] = {a.actor_id for a in audits if a.actor_id}
    via_admin_map: dict[int, int] = {}  # audit.id -> admin_id (eğer impersonate ise)
    audit_details_parsed: dict[int, dict] = {}  # audit.id -> parsed details dict
    import json as _json
    for a in audits:
        if not a.details_json:
            continue
        try:
            d = _json.loads(a.details_json)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict):
            audit_details_parsed[a.id] = d
            if d.get("_via_admin"):
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
            "audit_details_parsed": audit_details_parsed,
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


# ---------------------------- Stage 6 — Süper admin kullanım paneli ----------------------------


@router.get("/usage")
def super_admin_usage(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    tab: str = "institutions",  # 'institutions' | 'independents'
    ok: str | None = None,
    err: str | None = None,
):
    """Sistem geneli kullanım paneli — tüm kurumlar + bağımsız öğretmenler.

    Her satır: kullanılan/tahsis, plan, hard-block durumu, son aktivite.
    Hard-block toggle ve bonus kredi ekleme buradan yapılır.
    """
    from app.models import (
        CreditAccount, USAGE_KIND_LABELS_TR, UsageOwnerType,
    )
    from app.services.credits import (
        CreditOwner, current_period, get_or_create_account, KIND_CREDITS,
        PLAN_ALLOCATIONS,
    )

    period = current_period()

    # Kurumlar
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    inst_rows = []
    total_used_inst = 0
    total_alloc_inst = 0
    for inst in insts:
        owner = CreditOwner.for_institution(inst)
        acc = get_or_create_account(db, owner=owner, period=period)
        inst_rows.append({
            "institution": inst,
            "account": acc,
        })
        total_used_inst += acc.used_credits or 0
        total_alloc_inst += acc.total_allocated
    db.commit()
    inst_rows.sort(key=lambda r: -(r["account"].usage_pct))

    # Bağımsız öğretmenler
    indeps = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    indep_rows = []
    total_used_indep = 0
    total_alloc_indep = 0
    for u in indeps:
        owner = CreditOwner.for_user(u)
        acc = get_or_create_account(db, owner=owner, period=period)
        indep_rows.append({
            "user": u,
            "account": acc,
        })
        total_used_indep += acc.used_credits or 0
        total_alloc_indep += acc.total_allocated
    db.commit()
    indep_rows.sort(key=lambda r: -(r["account"].usage_pct))

    return templates.TemplateResponse(
        "admin/usage_dashboard.html",
        {
            "request": request,
            "user": user,
            "tab": tab,
            "period": period,
            "inst_rows": inst_rows,
            "indep_rows": indep_rows,
            "totals": {
                "inst_used": total_used_inst,
                "inst_alloc": total_alloc_inst,
                "indep_used": total_used_indep,
                "indep_alloc": total_alloc_indep,
                "grand_used": total_used_inst + total_used_indep,
                "grand_alloc": total_alloc_inst + total_alloc_indep,
            },
            "kind_labels": USAGE_KIND_LABELS_TR,
            "kind_costs": KIND_CREDITS,
            "plan_allocations": PLAN_ALLOCATIONS,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/usage/{owner_type}/{owner_id}/hard-block")
def super_admin_hard_block_toggle(
    owner_type: str,
    owner_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Hard-block toggle — sadece kurumlar için (bağımsız zaten cooldown'a tabi).

    POST: hard_block_enabled flag'ini ters çevir.
    """
    from app.models import CreditAccount, UsageOwnerType
    from app.services.credits import current_period

    if owner_type != "institution":
        return RedirectResponse(
            url="/admin/usage?err=" + quote("Hard-block sadece kurumlar için"),
            status_code=303,
        )

    period = current_period()
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
            CreditAccount.owner_id == owner_id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if not acc:
        return RedirectResponse(
            url="/admin/usage?err=" + quote("Hesap bulunamadı"),
            status_code=303,
        )

    new_state = not acc.hard_block_enabled
    acc.hard_block_enabled = new_state
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="credit_account",
        target_id=acc.id,
        request=request,
        details={
            "hard_block_enabled": new_state,
            "institution_id": owner_id,
            "period": period,
        },
        autocommit=False,
    )
    db.commit()
    msg = (
        f"Kurum #{owner_id} hard-block aktif edildi"
        if new_state else f"Kurum #{owner_id} hard-block kapatıldı"
    )
    return RedirectResponse(
        url="/admin/usage?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/usage/{owner_type}/{owner_id}/bonus")
def super_admin_add_bonus(
    owner_type: str,
    owner_id: int,
    request: Request,
    bonus_amount: int = Form(...),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bonus kredi ekle — kurum veya bağımsız öğretmen için (manuel)."""
    from app.models import CreditAccount, UsageOwnerType
    from app.services.credits import current_period

    if owner_type not in ("institution", "user"):
        return RedirectResponse(
            url="/admin/usage?err=" + quote("Geçersiz sahip türü"),
            status_code=303,
        )
    if bonus_amount <= 0 or bonus_amount > 100000:
        return RedirectResponse(
            url="/admin/usage?err=" + quote("Bonus 1-100000 arasında olmalı"),
            status_code=303,
        )

    period = current_period()
    owner_enum = (
        UsageOwnerType.INSTITUTION if owner_type == "institution"
        else UsageOwnerType.USER
    )
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == owner_enum,
            CreditAccount.owner_id == owner_id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if not acc:
        return RedirectResponse(
            url="/admin/usage?err=" + quote("Hesap bulunamadı"),
            status_code=303,
        )

    acc.bonus_credits = (acc.bonus_credits or 0) + bonus_amount
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="credit_account",
        target_id=acc.id,
        request=request,
        details={
            "bonus_added": bonus_amount,
            "new_bonus_total": acc.bonus_credits,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "period": period,
        },
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/admin/usage?ok=" + quote(f"+{bonus_amount} bonus kredi eklendi"),
        status_code=303,
    )


# ---------------------------- Stage 7 — Feature flags ----------------------------


@router.get("/feature-flags")
def feature_flags_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm feature flag'ler + global toggle + override sayımı."""
    from app.services.feature_flags import all_flags_for_admin
    flags_data = all_flags_for_admin(db)
    institutions = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .order_by(Institution.name)
        .all()
    )
    return templates.TemplateResponse(
        "admin/feature_flags_list.html",
        {
            "request": request,
            "user": user,
            "flags_data": flags_data,
            "institutions": institutions,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.get("/feature-flags/{flag_id}")
def feature_flag_detail(
    flag_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Tek flag detayı + tüm override'larının yönetimi."""
    from app.models import FeatureFlag
    from app.services.feature_flags import get_overrides_for_flag
    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag bulunamadı")
    overrides = get_overrides_for_flag(db, flag_id)
    institutions = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .order_by(Institution.name)
        .all()
    )
    overridden_inst_ids = {o.institution_id for o in overrides}
    available_institutions = [i for i in institutions if i.id not in overridden_inst_ids]
    return templates.TemplateResponse(
        "admin/feature_flag_detail.html",
        {
            "request": request,
            "user": user,
            "flag": flag,
            "overrides": overrides,
            "available_institutions": available_institutions,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/feature-flags/{flag_id}/toggle")
def feature_flag_toggle_global(
    flag_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Global enabled flag'i toggle et."""
    from app.models import FeatureFlag
    from app.services.feature_flags import set_global
    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag bulunamadı")
    new_state = not flag.enabled_globally
    set_global(db, flag.key, new_state)
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag",
        target_id=flag.id,
        request=request,
        details={"key": flag.key, "enabled_globally": new_state},
    )
    msg = (
        f"'{flag.key}' AÇILDI" if new_state else f"'{flag.key}' KAPATILDI"
    )
    return RedirectResponse(
        url="/admin/feature-flags?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/feature-flags/{flag_id}/overrides")
def feature_flag_add_override(
    flag_id: int,
    request: Request,
    institution_id: int = Form(...),
    enabled: str = Form("on"),  # "on" / "off"
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir kuruma özel override ekle/güncelle."""
    from app.models import FeatureFlag
    from app.services.feature_flags import set_override
    flag = db.get(FeatureFlag, flag_id)
    if not flag:
        raise HTTPException(status_code=404, detail="Flag bulunamadı")
    inst = db.get(Institution, institution_id)
    if not inst:
        return RedirectResponse(
            url=f"/admin/feature-flags/{flag_id}?err=" + quote("Kurum bulunamadı"),
            status_code=303,
        )
    enabled_bool = enabled == "on"
    o = set_override(
        db, flag_id=flag_id, institution_id=institution_id,
        enabled=enabled_bool, note=note.strip() or None,
    )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag_override",
        target_id=o.id,
        request=request,
        details={
            "flag_key": flag.key, "institution_id": institution_id,
            "enabled": enabled_bool,
        },
    )
    return RedirectResponse(
        url=f"/admin/feature-flags/{flag_id}?ok=" + quote(
            f"'{inst.name}' için override {'AÇIK' if enabled_bool else 'KAPALI'}"
        ),
        status_code=303,
    )


@router.post("/feature-flags/overrides/{override_id}/delete")
def feature_flag_remove_override(
    override_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Override sil — kurum global ayara döner."""
    from app.models import FeatureFlagOverride
    from app.services.feature_flags import remove_override
    o = db.get(FeatureFlagOverride, override_id)
    if not o:
        raise HTTPException(status_code=404, detail="Override bulunamadı")
    flag_id = o.feature_flag_id
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="feature_flag_override",
        target_id=override_id,
        request=request,
        details={"deleted": True, "flag_id": flag_id, "institution_id": o.institution_id},
    )
    remove_override(db, override_id)
    return RedirectResponse(
        url=f"/admin/feature-flags/{flag_id}?ok=" + quote("Override silindi (global ayara döndü)"),
        status_code=303,
    )


# ---------------------------- Katman 1 — Özellik Kataloğu ----------------------------


def _parse_dt_local(value: str | None) -> datetime | None:
    """HTML datetime-local input'unu UTC datetime'a çevir. Boş ise None."""
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    # "2026-05-14T10:30" → naive → UTC kabul ediyoruz
    try:
        if "T" in v:
            dt = datetime.fromisoformat(v)
        else:
            dt = datetime.strptime(v, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _split_lines(value: str | None) -> list[str]:
    """Textarea'dan gelen 'her satır bir madde' formatını listeye çevir."""
    if not value:
        return []
    return [ln.strip() for ln in value.splitlines() if ln.strip()]


def _form_roles(value_list: list[str]) -> list[str]:
    """Form'dan gelen UserRole değerlerini filtrele (geçersizleri at)."""
    valid = {r.value for r in UserRole}
    return [v for v in value_list if v in valid]


@router.get("/feature-catalog")
def feature_catalog_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    status_filter: str | None = None,
    domain_filter: str | None = None,
    tier_filter: str | None = None,
    q: str | None = None,
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm vitrin kartları — filtreleme + durum rozetleri."""
    from app.models import (
        FEATURE_DOMAIN_LABELS_TR, FEATURE_STATUS_BADGES,
        FEATURE_STATUS_LABELS_TR, FEATURE_TIER_LABELS_TR,
        FeatureDomain, FeatureStatus, FeatureTier,
    )
    from app.services import feature_catalog as fc

    cards = fc.list_for_admin(
        db,
        status_filter=status_filter,
        domain_filter=domain_filter,
        tier_filter=tier_filter,
        search=q,
    )
    counts = fc.count_by_status(db)
    discovery_pending = _discovery_pending_count(db)

    # Katman 5: landing'e aday olan (PUBLISHED + mockup_type dolu) kartlar için
    # fuzzy skor hesapla. Diğer kartlar tablosunda "—" görünür.
    from app.services.feature_scoring import score_card
    scores: dict[int, object] = {}
    for c in cards:
        if (
            c.status == FeatureStatus.PUBLISHED.value
            and c.mockup_type
            and not c.manual_hide
        ):
            scores[c.id] = score_card(c, role=None)

    # Katman 6: kart başına telemetri sayımları (bulk fetch — tek sorgu)
    from app.services import telemetry as tel
    telemetry_stats = tel.get_bulk_stats(db, [c.id for c in cards])

    # Katman 7: kart başına bandit istatistiği (state varsa)
    from app.models import FeatureBanditState
    from app.services import bandit as bd
    bandit_rows = (
        db.query(FeatureBanditState)
        .filter(FeatureBanditState.card_id.in_([c.id for c in cards]))
        .all()
    )
    # Şu anki bağlam ile beklenen reward (admin için "anon ziyaretçi" perspektifi)
    bandit_ctx = bd.extract_context(None)
    bandit_info: dict[int, dict] = {}
    for st in bandit_rows:
        mean, ucb = bd.score(st, bandit_ctx)
        bandit_info[st.card_id] = {
            "obs": st.reward_count or 0,
            "mean": mean,
            "ucb": ucb,
        }

    # Katman 8: anasayfa kart kümesinin çeşitlilik metrikleri
    # - landing_cards = MMR sonrası gerçek anasayfa sıralaması
    # - neighbor_sim  = her landing kartının ÜST kartla benzerliği (0..1)
    # - overall_div   = 5 kartlık kümenin ortalama farklılığı (0..1, yüksek=iyi)
    from app.services import diversity as dv
    landing_cards = fc.get_for_landing(db)
    landing_ids = {c.id for c in landing_cards}
    neighbor_sim = dv.neighbor_similarity(landing_cards)  # dict[card_id, float]
    overall_diversity = dv.diversity_score(landing_cards)

    # Toplam aktif öğrenme (bandit) sayısı
    learning_count = sum(1 for st in bandit_rows if (st.reward_count or 0) > 0)

    return templates.TemplateResponse(
        "admin/feature_catalog_list.html",
        {
            "request": request,
            "user": user,
            "cards": cards,
            "counts": counts,
            "discovery_pending": discovery_pending,
            "scores": scores,
            "telemetry_stats": telemetry_stats,
            "bandit_info": bandit_info,
            "landing_ids": landing_ids,
            "neighbor_sim": neighbor_sim,
            "overall_diversity": overall_diversity,
            "learning_count": learning_count,
            "landing_card_count": len(landing_cards),
            "status_filter": status_filter,
            "domain_filter": domain_filter,
            "tier_filter": tier_filter,
            "q": q or "",
            "FeatureDomain": FeatureDomain,
            "FeatureTier": FeatureTier,
            "FeatureStatus": FeatureStatus,
            "DOMAIN_LABELS": FEATURE_DOMAIN_LABELS_TR,
            "TIER_LABELS": FEATURE_TIER_LABELS_TR,
            "STATUS_LABELS": FEATURE_STATUS_LABELS_TR,
            "STATUS_BADGES": FEATURE_STATUS_BADGES,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.get("/feature-catalog/new")
def feature_catalog_new_form(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    err: str | None = None,
):
    """Yeni kart oluşturma formu (GET)."""
    from app.models import (
        FEATURE_DOMAIN_LABELS_TR, FEATURE_STATUS_LABELS_TR,
        FEATURE_TIER_LABELS_TR,
        FeatureDomain, FeatureStatus, FeatureTier,
    )
    from app.services.mockup_registry import list_mockups
    return templates.TemplateResponse(
        "admin/feature_catalog_form.html",
        {
            "request": request,
            "user": user,
            "card": None,
            "FeatureDomain": FeatureDomain,
            "FeatureTier": FeatureTier,
            "FeatureStatus": FeatureStatus,
            "DOMAIN_LABELS": FEATURE_DOMAIN_LABELS_TR,
            "TIER_LABELS": FEATURE_TIER_LABELS_TR,
            "STATUS_LABELS": FEATURE_STATUS_LABELS_TR,
            "UserRole": UserRole,
            "MOCKUPS": list_mockups(),
            "flash_err": err,
        },
    )


@router.post("/feature-catalog/new")
def feature_catalog_create(
    request: Request,
    slug: str = Form(""),
    title: str = Form(""),
    tagline: str = Form(""),
    description_md: str = Form(""),
    icon: str = Form("sparkles"),
    accent_color: str = Form("#3b82f6"),
    category_icon: str = Form("✨"),
    category_label: str = Form(""),
    demo_duration_label: str = Form(""),
    mockup_type: str = Form(""),
    target_roles: list[str] = Form(default=[]),
    benefits_text: str = Form(""),
    pain_points_text: str = Form(""),
    demo_slug: str = Form(""),
    domain: str = Form("genel"),
    tier: str = Form("enhancement"),
    status_field: str = Form("draft"),
    introduced_at: str = Form(""),
    introduced_in_commit: str = Form(""),
    pr_url: str = Form(""),
    strategic_priority: int = Form(3),
    manual_pin: str = Form(""),
    pin_until: str = Form(""),
    manual_hide: str = Form(""),
    cta_label: str = Form("Detayları gör"),
    cta_url: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni kart oluştur — başarılıysa listeye dön."""
    from app.services import feature_catalog as fc
    try:
        card = fc.create(
            db,
            actor_id=user.id,
            slug=slug,
            title=title,
            tagline=tagline,
            description_md=description_md,
            icon=icon,
            accent_color=accent_color,
            category_icon=category_icon,
            category_label=category_label,
            demo_duration_label=demo_duration_label,
            mockup_type=(mockup_type or None),
            target_roles=_form_roles(target_roles),
            benefits=_split_lines(benefits_text),
            pain_points=_split_lines(pain_points_text),
            demo_slug=demo_slug,
            domain=domain,
            tier=tier,
            status=status_field,
            introduced_at=_parse_dt_local(introduced_at),
            introduced_in_commit=introduced_in_commit,
            pr_url=pr_url,
            strategic_priority=strategic_priority,
            manual_pin=(manual_pin == "on"),
            pin_until=_parse_dt_local(pin_until),
            manual_hide=(manual_hide == "on"),
            cta_label=cta_label,
            cta_url=cta_url,
        )
    except fc.FeatureCatalogError as e:
        return RedirectResponse(
            url="/admin/feature-catalog/new?err=" + quote(str(e)),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_CREATE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "status": card.status},
    )
    return RedirectResponse(
        url="/admin/feature-catalog?ok=" + quote(f"'{card.slug}' oluşturuldu"),
        status_code=303,
    )


# ---------------------------- Katman 4 — Discovery Onay Kuyruğu ----------------------------
# /discovery-queue route'u {card_id} yakalayıcısından ÖNCE tanımlanmalı.


def _discovery_pending_count(db: Session) -> int:
    """kesif-* slug'lı + DRAFT + henüz reddedilmemiş aday sayısı."""
    from app.models import FeatureCard, FeatureStatus
    return (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .count()
    )


@router.get("/feature-catalog/discovery-queue")
def feature_catalog_discovery_queue(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    source: str | None = None,  # "migration" | "commit" | None (hepsi)
    show_rejected: int = 0,
    ok: str | None = None,
    err: str | None = None,
):
    """Otomatik keşif adayları için onay kuyruğu paneli.

    Yalnızca `kesif-mig-*` / `kesif-c-*` slug'lı DRAFT'ları gösterir.
    Reddedilenler (manual_hide=True) varsayılan olarak gizli — `show_rejected=1`
    query parametresiyle açılır.
    """
    from app.models import AuditAction, AuditLog, FeatureCard, FeatureStatus

    q = (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
        )
    )
    if not show_rejected:
        q = q.filter(FeatureCard.manual_hide.is_(False))
    if source == "migration":
        q = q.filter(FeatureCard.slug.like("kesif-mig-%"))
    elif source == "commit":
        q = q.filter(FeatureCard.slug.like("kesif-c-%"))

    cards = q.order_by(FeatureCard.introduced_at.desc()).all()

    # Her kart için discovery audit detayını al (kaynak ref + raw subject)
    card_ids = [c.id for c in cards]
    audit_by_card: dict[int, AuditLog] = {}
    if card_ids:
        rows = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == AuditAction.FEATURE_CARD_AUTO_DISCOVERED,
                AuditLog.target_id.in_(card_ids),
                AuditLog.target_type == "feature_card",
            )
            .all()
        )
        for r in rows:
            audit_by_card[r.target_id] = r

    # Sayım rozetleri
    total_pending = _discovery_pending_count(db)
    mig_pending = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.slug.like("kesif-mig-%"),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .count()
    )
    com_pending = total_pending - mig_pending

    return templates.TemplateResponse(
        "admin/feature_catalog_discovery_queue.html",
        {
            "request": request,
            "user": user,
            "cards": cards,
            "audit_by_card": audit_by_card,
            "source": source or "",
            "show_rejected": bool(show_rejected),
            "counts": {
                "total": total_pending,
                "migration": mig_pending,
                "commit": com_pending,
            },
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/feature-catalog/{card_id}/reject")
def feature_catalog_reject(
    card_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Discovery adayını reddet — manual_hide=True + audit. Silmez."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    card.manual_hide = True
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_DISCOVERY_REJECTED,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug},
    )
    db.commit()
    return RedirectResponse(
        url="/admin/feature-catalog/discovery-queue?ok="
        + quote(f"'{card.slug}' reddedildi"),
        status_code=303,
    )


@router.post("/feature-catalog/discovery-queue/bulk")
async def feature_catalog_discovery_bulk(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Toplu reddet/sil. Body: action=reject|delete, ids=<int>,<int>,..."""
    from app.models import FeatureCard, FeatureStatus
    from app.services import feature_catalog as fc

    form = await request.form()
    action = (form.get("action") or "").strip()
    ids_raw = form.getlist("ids") if hasattr(form, "getlist") else []
    if not ids_raw:
        # Tek input olarak da gelebilir (virgüllü)
        single = form.get("ids")
        if single:
            ids_raw = [single]
    ids: list[int] = []
    for raw in ids_raw:
        for part in str(raw).split(","):
            try:
                ids.append(int(part.strip()))
            except (TypeError, ValueError):
                continue

    if action not in ("reject", "delete"):
        return RedirectResponse(
            url="/admin/feature-catalog/discovery-queue?err="
            + quote("Geçersiz aksiyon"),
            status_code=303,
        )
    if not ids:
        return RedirectResponse(
            url="/admin/feature-catalog/discovery-queue?err="
            + quote("Aday seçilmedi"),
            status_code=303,
        )

    # Sadece DISCOVERY (kesif-*) DRAFT kartlarda çalışsın — yanlışlıkla manuel
    # kartı sileyim olmasın
    cards = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.id.in_(ids),
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
        )
        .all()
    )

    affected = 0
    for card in cards:
        if action == "reject":
            if card.manual_hide:
                continue
            card.manual_hide = True
            log_action(
                db,
                action=AuditAction.FEATURE_CARD_DISCOVERY_REJECTED,
                actor_id=user.id,
                target_type="feature_card",
                target_id=card.id,
                request=request,
                details={"slug": card.slug, "bulk": True},
            )
            affected += 1
        elif action == "delete":
            log_action(
                db,
                action=AuditAction.FEATURE_CARD_DELETE,
                actor_id=user.id,
                target_type="feature_card",
                target_id=card.id,
                request=request,
                details={"slug": card.slug, "bulk": True, "via": "discovery_queue"},
            )
            fc.delete(db, card)
            affected += 1

    db.commit()
    msg = f"{affected} aday {('reddedildi' if action=='reject' else 'silindi')}"
    return RedirectResponse(
        url="/admin/feature-catalog/discovery-queue?ok=" + quote(msg),
        status_code=303,
    )


# ---------------------------- Katman 10 — Süper Admin Yönetim Paneli ----------------------------


@router.get("/feature-catalog/dashboard")
def feature_catalog_dashboard(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Vitrin Kataloğu Yönetim Paneli (Katman 10) — tüm katmanların özeti."""
    from app.services.curator_dashboard import get_dashboard_data, humanize_ago
    data = get_dashboard_data(db)
    return templates.TemplateResponse(
        "admin/feature_catalog_dashboard.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "humanize_ago": humanize_ago,
        },
    )


# ---------------------------- Katman 9 — A/B Deney Yönetimi ----------------------------
# Bu route'lar {card_id} yakalayıcısından ÖNCE tanımlanmalı.


@router.get("/feature-catalog/experiments")
def experiments_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm deneyler listesi (Katman 9 — A/B test çerçevesi)."""
    from app.models import (
        EXPERIMENT_STATUS_BADGES,
        EXPERIMENT_STATUS_LABELS_TR,
        ExperimentStatus,
        FeatureExperiment,
    )
    rows = (
        db.query(FeatureExperiment)
        .order_by(FeatureExperiment.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "admin/feature_experiments_list.html",
        {
            "request": request,
            "user": user,
            "experiments": rows,
            "ExperimentStatus": ExperimentStatus,
            "STATUS_LABELS": EXPERIMENT_STATUS_LABELS_TR,
            "STATUS_BADGES": EXPERIMENT_STATUS_BADGES,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.get("/feature-catalog/experiments/new")
def experiments_new_form(
    request: Request,
    user: User = Depends(require_super_admin),
    err: str | None = None,
):
    """Yeni deney oluşturma formu."""
    from app.services.landing_strategies import (
        REGISTRY,
        STRATEGY_DESCRIPTIONS_TR,
        STRATEGY_LABELS_TR,
    )
    return templates.TemplateResponse(
        "admin/feature_experiments_form.html",
        {
            "request": request,
            "user": user,
            "experiment": None,
            "STRATEGY_KEYS": list(REGISTRY.keys()),
            "STRATEGY_LABELS": STRATEGY_LABELS_TR,
            "STRATEGY_DESCRIPTIONS": STRATEGY_DESCRIPTIONS_TR,
            "flash_err": err,
        },
    )


@router.post("/feature-catalog/experiments/new")
async def experiments_new_submit(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni deney oluştur. 2 variant: control + test."""
    from app.models import ExperimentStatus, FeatureExperiment
    from app.services import experiments as exp_svc
    from app.services import feature_catalog as fc

    form = await request.form()
    name = (form.get("name") or "").strip()
    slug_in = (form.get("slug") or "").strip()
    hypothesis = (form.get("hypothesis") or "").strip()
    ctrl_strategy = (form.get("ctrl_strategy") or "hybrid_full").strip()
    test_strategy = (form.get("test_strategy") or "fuzzy_only").strip()
    try:
        weight_ctrl = int(form.get("weight_ctrl") or 50)
        weight_test = int(form.get("weight_test") or 50)
    except (TypeError, ValueError):
        weight_ctrl, weight_test = 50, 50

    if not name:
        return RedirectResponse(
            url="/admin/feature-catalog/experiments/new?err=" + quote("Ad zorunlu"),
            status_code=303,
        )
    if weight_ctrl + weight_test != 100 or min(weight_ctrl, weight_test) < 1:
        return RedirectResponse(
            url="/admin/feature-catalog/experiments/new?err=" +
                quote("Ağırlıklar toplamı 100 olmalı (her biri 1-99 arası)"),
            status_code=303,
        )

    slug = fc.slugify(slug_in or name)
    if not slug:
        return RedirectResponse(
            url="/admin/feature-catalog/experiments/new?err=" + quote("Slug üretilemedi"),
            status_code=303,
        )
    # Slug çakışma
    if db.query(FeatureExperiment).filter(FeatureExperiment.slug == slug).first():
        return RedirectResponse(
            url="/admin/feature-catalog/experiments/new?err=" +
                quote(f"'{slug}' slug zaten kullanımda"),
            status_code=303,
        )

    now = exp_svc.now_utc()
    new_exp = FeatureExperiment(
        slug=slug,
        name=name[:160],
        status=ExperimentStatus.DRAFT.value,
        hypothesis=hypothesis[:2000] if hypothesis else None,
        created_at=now,
        updated_at=now,
        created_by=user.id,
    )
    new_exp.variants = [
        {
            "slug": "ctrl",
            "label": "Kontrol",
            "strategy": ctrl_strategy,
            "weight": weight_ctrl,
            "is_control": True,
        },
        {
            "slug": "test",
            "label": "Test",
            "strategy": test_strategy,
            "weight": weight_test,
            "is_control": False,
        },
    ]
    db.add(new_exp)
    db.commit()
    db.refresh(new_exp)
    return RedirectResponse(
        url=f"/admin/feature-catalog/experiments/{new_exp.id}?ok=" + quote("Deney oluşturuldu"),
        status_code=303,
    )


@router.get("/feature-catalog/experiments/{exp_id}")
def experiments_detail(
    exp_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Deney detay sayfası — variant istatistikleri + Wilson CI bar."""
    from app.models import (
        EXPERIMENT_STATUS_BADGES,
        EXPERIMENT_STATUS_LABELS_TR,
        ExperimentStatus,
        FeatureExperiment,
    )
    from app.services import experiments as exp_svc
    from app.services.landing_strategies import (
        STRATEGY_DESCRIPTIONS_TR,
        STRATEGY_LABELS_TR,
    )

    exp = db.get(FeatureExperiment, exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Deney bulunamadı")
    stats = exp_svc.compute_stats(db, experiment_id=exp.id)
    return templates.TemplateResponse(
        "admin/feature_experiments_detail.html",
        {
            "request": request,
            "user": user,
            "experiment": exp,
            "stats": stats,
            "ExperimentStatus": ExperimentStatus,
            "STATUS_LABELS": EXPERIMENT_STATUS_LABELS_TR,
            "STATUS_BADGES": EXPERIMENT_STATUS_BADGES,
            "STRATEGY_LABELS": STRATEGY_LABELS_TR,
            "STRATEGY_DESCRIPTIONS": STRATEGY_DESCRIPTIONS_TR,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/feature-catalog/experiments/{exp_id}/status")
def experiments_set_status(
    exp_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Deney durumunu değiştir (draft/running/paused/completed).

    Eş zamanlı tek RUNNING kuralı: yeni RUNNING'e geçerken diğer RUNNING
    deneyleri PAUSED'a çek (otomatik).
    """
    from app.models import ExperimentStatus, FeatureExperiment
    from app.services import experiments as exp_svc

    exp = db.get(FeatureExperiment, exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Deney bulunamadı")

    # Form değeri direkt query param da olabilir
    new_status = request.query_params.get("status") or ""
    if new_status not in {e.value for e in ExperimentStatus}:
        return RedirectResponse(
            url=f"/admin/feature-catalog/experiments/{exp.id}?err=" +
                quote("Geçersiz durum"),
            status_code=303,
        )

    now = exp_svc.now_utc()
    # RUNNING geçişinde diğerlerini PAUSED'a çek
    if new_status == ExperimentStatus.RUNNING.value:
        for other in db.query(FeatureExperiment).filter(
            FeatureExperiment.status == ExperimentStatus.RUNNING.value,
            FeatureExperiment.id != exp.id,
        ).all():
            other.status = ExperimentStatus.PAUSED.value
            other.updated_at = now
        if exp.start_at is None:
            exp.start_at = now
    elif new_status == ExperimentStatus.COMPLETED.value:
        if exp.end_at is None:
            exp.end_at = now

    exp.status = new_status
    exp.updated_at = now
    db.commit()
    return RedirectResponse(
        url=f"/admin/feature-catalog/experiments/{exp.id}?ok=" +
            quote(f"Durum '{new_status}' olarak güncellendi"),
        status_code=303,
    )


@router.get("/feature-catalog/{card_id}")
def feature_catalog_edit_form(
    card_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Mevcut kartın düzenleme formu."""
    from app.models import (
        FEATURE_DOMAIN_LABELS_TR, FEATURE_STATUS_LABELS_TR,
        FEATURE_TIER_LABELS_TR,
        FeatureDomain, FeatureStatus, FeatureTier,
    )
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    from app.services.mockup_registry import list_mockups
    return templates.TemplateResponse(
        "admin/feature_catalog_form.html",
        {
            "request": request,
            "user": user,
            "card": card,
            "FeatureDomain": FeatureDomain,
            "FeatureTier": FeatureTier,
            "FeatureStatus": FeatureStatus,
            "DOMAIN_LABELS": FEATURE_DOMAIN_LABELS_TR,
            "TIER_LABELS": FEATURE_TIER_LABELS_TR,
            "STATUS_LABELS": FEATURE_STATUS_LABELS_TR,
            "UserRole": UserRole,
            "MOCKUPS": list_mockups(),
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/feature-catalog/{card_id}")
def feature_catalog_update(
    card_id: int,
    request: Request,
    slug: str = Form(""),
    title: str = Form(""),
    tagline: str = Form(""),
    description_md: str = Form(""),
    icon: str = Form("sparkles"),
    accent_color: str = Form("#3b82f6"),
    category_icon: str = Form("✨"),
    category_label: str = Form(""),
    demo_duration_label: str = Form(""),
    mockup_type: str = Form(""),
    target_roles: list[str] = Form(default=[]),
    benefits_text: str = Form(""),
    pain_points_text: str = Form(""),
    demo_slug: str = Form(""),
    domain: str = Form("genel"),
    tier: str = Form("enhancement"),
    status_field: str = Form("draft"),
    introduced_at: str = Form(""),
    introduced_in_commit: str = Form(""),
    pr_url: str = Form(""),
    strategic_priority: int = Form(3),
    manual_pin: str = Form(""),
    pin_until: str = Form(""),
    manual_hide: str = Form(""),
    cta_label: str = Form("Detayları gör"),
    cta_url: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Var olan kartı güncelle."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    try:
        fc.update(
            db, card,
            actor_id=user.id,
            slug=slug,
            title=title,
            tagline=tagline,
            description_md=description_md,
            icon=icon,
            accent_color=accent_color,
            category_icon=category_icon,
            category_label=category_label,
            demo_duration_label=demo_duration_label,
            mockup_type=(mockup_type or None),
            target_roles=_form_roles(target_roles),
            benefits=_split_lines(benefits_text),
            pain_points=_split_lines(pain_points_text),
            demo_slug=demo_slug,
            domain=domain,
            tier=tier,
            status=status_field,
            introduced_at=_parse_dt_local(introduced_at),
            introduced_in_commit=introduced_in_commit,
            pr_url=pr_url,
            strategic_priority=strategic_priority,
            manual_pin=(manual_pin == "on"),
            pin_until=_parse_dt_local(pin_until),
            manual_hide=(manual_hide == "on"),
            cta_label=cta_label,
            cta_url=cta_url,
        )
    except fc.FeatureCatalogError as e:
        return RedirectResponse(
            url=f"/admin/feature-catalog/{card_id}?err=" + quote(str(e)),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_UPDATE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "status": card.status},
    )
    return RedirectResponse(
        url=f"/admin/feature-catalog/{card_id}?ok=" + quote("Kayıt güncellendi"),
        status_code=303,
    )


@router.post("/feature-catalog/{card_id}/status")
def feature_catalog_status(
    card_id: int,
    request: Request,
    status_field: str = Form(...),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kart durumu (DRAFT/PUBLISHED/HIDDEN/DEPRECATED) değiştir."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    old_status = card.status
    try:
        fc.set_status(db, card, status_field, actor_id=user.id)
    except fc.FeatureCatalogError as e:
        return RedirectResponse(
            url="/admin/feature-catalog?err=" + quote(str(e)),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_STATUS_CHANGE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "from": old_status, "to": card.status},
    )
    return RedirectResponse(
        url="/admin/feature-catalog?ok=" + quote(
            f"'{card.slug}' durumu: {card.status}"
        ),
        status_code=303,
    )


@router.post("/feature-catalog/{card_id}/pin")
def feature_catalog_pin(
    card_id: int,
    request: Request,
    pinned: str = Form(""),       # "on" / ""
    pin_until: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Pin durumunu (manuel sabitle) toggle et."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    pin_bool = pinned == "on"
    fc.set_pin(
        db, card,
        pinned=pin_bool,
        until=_parse_dt_local(pin_until),
        actor_id=user.id,
    )
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_PIN,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": card.slug, "pinned": pin_bool},
    )
    msg = "sabitlendi" if pin_bool else "serbest bırakıldı"
    return RedirectResponse(
        url=f"/admin/feature-catalog/{card_id}?ok=" + quote(f"Kart {msg}"),
        status_code=303,
    )


@router.post("/feature-catalog/{card_id}/delete")
def feature_catalog_delete(
    card_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kartı kalıcı sil."""
    from app.services import feature_catalog as fc

    card = fc.get_by_id(db, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Kart bulunamadı")
    slug = card.slug
    log_action(
        db,
        action=AuditAction.FEATURE_CARD_DELETE,
        actor_id=user.id,
        target_type="feature_card",
        target_id=card.id,
        request=request,
        details={"slug": slug},
    )
    fc.delete(db, card)
    return RedirectResponse(
        url="/admin/feature-catalog?ok=" + quote(f"'{slug}' silindi"),
        status_code=303,
    )


# ---------------------------- Stage 7 — Sistem duyuruları ----------------------------


@router.get("/announcements")
def announcements_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm sistem duyuruları listesi (aktif + geçmiş)."""
    from app.models import (
        AUDIENCE_LABELS_TR, AnnouncementAudience, AnnouncementSeverity,
        SEVERITY_LABELS_TR, SystemAnnouncement,
    )
    items = (
        db.query(SystemAnnouncement)
        .order_by(SystemAnnouncement.created_at.desc())
        .limit(50)
        .all()
    )
    now_dt = datetime.now(timezone.utc)
    return templates.TemplateResponse(
        "admin/announcements_list.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "now": now_dt,
            "severities": list(AnnouncementSeverity),
            "audiences": list(AnnouncementAudience),
            "severity_labels": SEVERITY_LABELS_TR,
            "audience_labels": AUDIENCE_LABELS_TR,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/announcements")
def announcements_create(
    request: Request,
    title: str = Form(""),
    message: str = Form(...),
    severity: str = Form("info"),
    audience: str = Form("all"),
    starts_at: str = Form(""),
    ends_at: str = Form(""),
    dismissible: str = Form("on"),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni duyuru oluştur."""
    from app.models import (
        AnnouncementAudience, AnnouncementSeverity, SystemAnnouncement,
    )
    msg_clean = (message or "").strip()
    if not msg_clean:
        return RedirectResponse(
            url="/admin/announcements?err=" + quote("Mesaj zorunlu"),
            status_code=303,
        )
    try:
        sev = AnnouncementSeverity(severity)
    except ValueError:
        sev = AnnouncementSeverity.INFO
    try:
        aud = AnnouncementAudience(audience)
    except ValueError:
        aud = AnnouncementAudience.ALL

    sa: datetime | None = None
    ea: datetime | None = None
    try:
        if starts_at:
            sa = datetime.fromisoformat(starts_at).replace(tzinfo=timezone.utc)
        if ends_at:
            ea = datetime.fromisoformat(ends_at).replace(tzinfo=timezone.utc)
    except ValueError:
        return RedirectResponse(
            url="/admin/announcements?err=" + quote("Tarih formatı hatalı (YYYY-MM-DDTHH:MM)"),
            status_code=303,
        )

    ann = SystemAnnouncement(
        title=(title or "").strip() or None,
        message=msg_clean,
        severity=sev,
        audience=aud,
        starts_at=sa or datetime.now(timezone.utc),
        ends_at=ea,
        dismissible=(dismissible == "on"),
        created_by=user.id,
    )
    db.add(ann)
    db.flush()
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="announcement",
        target_id=ann.id,
        request=request,
        details={"severity": sev.value, "audience": aud.value},
        autocommit=False,
    )
    db.commit()
    from app.services.announcements import invalidate_cache as _inv_ann
    _inv_ann()
    return RedirectResponse(
        url="/admin/announcements?ok=" + quote("Duyuru oluşturuldu"),
        status_code=303,
    )


# ---------------------------- Stage 8 — Kuota ----------------------------


@router.get("/quota")
def super_admin_quota(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Tüm kurumların kuota tablosu + override yönetimi."""
    from app.models import InstitutionQuotaOverride
    from app.services.quotas import (
        QUOTA_KEYS, QUOTA_LABELS_TR, PLAN_QUOTAS,
        count_current_usage, get_quota_limit,
    )
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    rows = []
    for inst in insts:
        cells = []
        max_pct = 0
        for key in QUOTA_KEYS:
            limit, has_override, note = get_quota_limit(
                db, institution=inst, quota_key=key,
            )
            current = count_current_usage(
                db, institution_id=inst.id, quota_key=key,
            )
            is_unlimited = limit == -1
            if is_unlimited:
                pct = 0
            elif limit == 0:
                pct = 100 if current > 0 else 0
            else:
                pct = int(round(100 * current / limit)) if limit > 0 else 0
            max_pct = max(max_pct, pct if not is_unlimited else 0)
            cells.append({
                "key": key,
                "label": QUOTA_LABELS_TR.get(key, key),
                "limit": limit,
                "current": current,
                "pct": pct,
                "is_unlimited": is_unlimited,
                "is_at_limit": (not is_unlimited) and current >= limit,
                "has_override": has_override,
                "note": note,
            })
        rows.append({
            "institution": inst,
            "cells": cells,
            "max_pct": max_pct,
        })
    rows.sort(key=lambda r: -r["max_pct"])

    return templates.TemplateResponse(
        "admin/quota_dashboard.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "quota_keys": QUOTA_KEYS,
            "quota_labels": QUOTA_LABELS_TR,
            "plan_quotas": PLAN_QUOTAS,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/quota/{institution_id}/override")
def super_admin_quota_set_override(
    institution_id: int,
    request: Request,
    quota_key: str = Form(...),
    override_value: int = Form(...),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kuruma kuota override koy (veya güncelle)."""
    from app.services.quotas import set_override, QUOTA_KEYS
    inst = db.get(Institution, institution_id)
    if not inst:
        raise HTTPException(status_code=404, detail="Kurum bulunamadı")
    if quota_key not in QUOTA_KEYS:
        return RedirectResponse(
            url="/admin/quota?err=" + quote("Geçersiz kuota anahtarı"),
            status_code=303,
        )
    if override_value < -1 or override_value > 1000000:
        return RedirectResponse(
            url="/admin/quota?err=" + quote("override_value -1 (sınırsız), 0 (kapalı) veya 1-1M"),
            status_code=303,
        )
    o = set_override(
        db, institution_id=institution_id, quota_key=quota_key,
        override_value=override_value, note=note.strip() or None,
    )
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="quota_override",
        target_id=o.id,
        request=request,
        details={
            "institution_id": institution_id,
            "quota_key": quota_key,
            "override_value": override_value,
        },
    )
    return RedirectResponse(
        url="/admin/quota?ok=" + quote(
            f"{inst.name} {quota_key} → "
            f"{'sınırsız' if override_value == -1 else 'kapalı' if override_value == 0 else override_value}"
        ),
        status_code=303,
    )


@router.post("/quota/overrides/{override_id}/delete")
def super_admin_quota_remove_override(
    override_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Override sil — kurum plan default'una döner."""
    from app.models import InstitutionQuotaOverride
    from app.services.quotas import remove_override
    o = db.get(InstitutionQuotaOverride, override_id)
    if not o:
        raise HTTPException(status_code=404, detail="Override bulunamadı")
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="quota_override",
        target_id=override_id,
        request=request,
        details={"deleted": True, "institution_id": o.institution_id, "quota_key": o.quota_key},
    )
    remove_override(db, override_id)
    return RedirectResponse(
        url="/admin/quota?ok=" + quote("Override silindi (plan default'a döndü)"),
        status_code=303,
    )


# ---------------------------- Stage 7 — System health ----------------------------


@router.get("/system-health")
def system_health(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Cron + dispatcher + DB sağlık paneli."""
    from app.services.system_health import collect_snapshot
    snapshot = collect_snapshot(db)
    return templates.TemplateResponse(
        "admin/system_health.html",
        {
            "request": request,
            "user": user,
            "snapshot": snapshot,
        },
    )


@router.post("/announcements/{announcement_id}/delete")
def announcements_delete(
    announcement_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Duyuru sil."""
    from app.models import SystemAnnouncement
    ann = db.get(SystemAnnouncement, announcement_id)
    if not ann:
        raise HTTPException(status_code=404, detail="Duyuru bulunamadı")
    log_action(
        db,
        action=AuditAction.INSTITUTION_UPDATE,
        actor_id=user.id,
        target_type="announcement",
        target_id=announcement_id,
        request=request,
        details={"deleted": True},
    )
    db.delete(ann)
    db.commit()
    from app.services.announcements import invalidate_cache as _inv_ann
    _inv_ann()
    return RedirectResponse(
        url="/admin/announcements?ok=" + quote("Duyuru silindi"),
        status_code=303,
    )


# ============ Stage 10 — KVKK denetim paneli ============


@router.get("/kvkk")
def admin_kvkk_dashboard(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """KVKK denetim genel bakış: durum sayım + bekleyen talepler + envanter linki."""
    from app.models import (
        DATA_REQUEST_KIND_LABELS_TR, DATA_REQUEST_STATUS_LABELS_TR,
        DataSubjectRequest,
    )
    from app.services.kvkk import DATA_INVENTORY, request_summary

    summary = request_summary(db)
    pending_rows = (
        db.query(DataSubjectRequest)
        .options(
            joinedload(DataSubjectRequest.target_user),
            joinedload(DataSubjectRequest.requester_user),
        )
        .filter(DataSubjectRequest.status.in_(["pending", "processing"]))
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(50)
        .all()
    )
    recent_rows = (
        db.query(DataSubjectRequest)
        .options(joinedload(DataSubjectRequest.target_user))
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(20)
        .all()
    )
    return templates.TemplateResponse(
        "admin/kvkk_dashboard.html",
        {
            "request": request,
            "user": user,
            "summary": summary,
            "pending_rows": pending_rows,
            "recent_rows": recent_rows,
            "data_inventory": DATA_INVENTORY,
            "kind_labels": DATA_REQUEST_KIND_LABELS_TR,
            "status_labels": DATA_REQUEST_STATUS_LABELS_TR,
        },
    )


@router.post("/kvkk/requests/{request_id}/apply")
def admin_kvkk_apply(
    request_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bekleyen silme talebini hemen uygula (admin override — 30g grace'i atla).

    Yalnız delete tipi için. Export tipleri zaten oluşturulduğunda tamamlanır.
    """
    from app.models import DataSubjectRequest, DataRequestKind, DataRequestStatus
    from app.services.kvkk import apply_deletion

    req = db.get(DataSubjectRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404)
    if req.kind != DataRequestKind.DELETE:
        return RedirectResponse(
            url="/admin/kvkk?err=" + quote("Yalnız silme talepleri uygulanabilir"),
            status_code=303,
        )
    if req.status not in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING):
        return RedirectResponse(
            url="/admin/kvkk?err=" + quote("Bu talep zaten kapatıldı"),
            status_code=303,
        )

    apply_deletion(db, request=req, by_user=user)
    return RedirectResponse(
        url="/admin/kvkk?ok=" + quote("Silme talebi uygulandı"),
        status_code=303,
    )


@router.post("/kvkk/requests/{request_id}/reject")
def admin_kvkk_reject(
    request_id: int,
    request: Request,
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Talebi reddet — admin gerekçe yazar."""
    from app.models import DataSubjectRequest, DataRequestStatus

    req = db.get(DataSubjectRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404)
    if req.status not in (DataRequestStatus.PENDING, DataRequestStatus.PROCESSING):
        return RedirectResponse(
            url="/admin/kvkk?err=" + quote("Bu talep zaten kapatıldı"),
            status_code=303,
        )
    req.status = DataRequestStatus.REJECTED
    req.processed_by_user_id = user.id
    req.processed_at = datetime.now(timezone.utc)
    req.admin_note = (note or "").strip()[:500] or "Admin reddetti"
    db.commit()
    return RedirectResponse(
        url="/admin/kvkk?ok=" + quote("Talep reddedildi"),
        status_code=303,
    )


# ============ Katman 11.A — Güvenlik Kamerası ============


@router.get("/security-monitor")
def security_monitor(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Hesap güvenliği kamerası: aktif oturumlar, şüpheli/blokli IP'ler,
    son 24h başarısız login dağılımı, kritik aksiyon akışı, süper admin login'leri,
    aktif kimliğe-bürünme (impersonation) oturumları (11.B)."""
    from app.services.security_monitor import (
        get_security_dashboard_data,
        humanize_ago,
    )
    from app.services.impersonation import list_active as list_active_impersonations
    from app.services.abuse_detection import open_signal_count
    from app.services.error_capture import error_summary
    from app.services.alarm_engine import unacknowledged_count
    from app.services.attention_engine import get_attention_summary
    from app.models import AUDIT_ACTION_LABELS, TERMINATION_REASON_LABELS_TR, BLOCK_REASON_LABELS_TR
    data = get_security_dashboard_data(db)
    data["active_impersonations"] = list_active_impersonations(db)
    data["abuse_open_count"] = open_signal_count(db)
    data["system_error_summary"] = error_summary(db, hours=24)
    data["unack_alarm_count"] = unacknowledged_count(db)
    # Katman 11.K.1 — Dikkat Odası
    data["attention"] = get_attention_summary(db)
    return templates.TemplateResponse(
        "admin/security_monitor.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "audit_action_labels": AUDIT_ACTION_LABELS,
            "termination_reason_labels": TERMINATION_REASON_LABELS_TR,
            "block_reason_labels": BLOCK_REASON_LABELS_TR,
            "humanize_ago": humanize_ago,
        },
    )


@router.get("/security-monitor/integrity")
def security_monitor_integrity(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Veri bütünlüğü kamerası (11.I): migration, DB dosyası, orphan, KVKK SLA, cron drift."""
    from app.services.data_integrity import get_integrity_panel_data
    data = get_integrity_panel_data(db)
    return templates.TemplateResponse(
        "admin/security_monitor_integrity.html",
        {"request": request, "user": user, "data": data},
    )


@router.get("/security-monitor/activity")
def security_monitor_activity(
    request: Request,
    tab: str = "today",
    segment: str = "all",
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kurum + Bağımsız Öğretmen Aktivitesi Kamerası — 6 sekme × 3 segment.

    Sekmeler: today, risk, retention, depth, time, benchmark
    Segmentler: all (kurum + bağımsız), institution (kurum), solo (bağımsız öğretmen)
    """
    from app.services.tenant_activity import get_activity_panel_data_with_summary
    valid_tabs = {"today", "risk", "retention", "depth", "time", "benchmark"}
    valid_segments = {"all", "institution", "solo"}
    active_tab = tab if tab in valid_tabs else "today"
    active_segment = segment if segment in valid_segments else "all"
    data = get_activity_panel_data_with_summary(db, segment=active_segment)
    return templates.TemplateResponse(
        "admin/security_monitor_activity.html",
        {
            "request": request, "user": user, "data": data,
            "active_tab": active_tab,
            "active_segment": active_segment,
        },
    )


@router.get("/security-monitor/activity/drill/active-users")
def security_monitor_activity_drill_users(
    request: Request,
    window: str = "dau",
    role: str = "",
    institution_id: int | None = None,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """HTMX partial: aktif kullanıcı listesi (DAU/WAU/MAU drill-down)."""
    from app.services.tenant_activity import active_users_window
    rows = active_users_window(
        db, window=window, role=role or None,
        institution_id=institution_id, limit=100,
    )
    win_label = {"dau": "son 24 saat", "wau": "son 7 gün",
                  "mau": "son 30 gün"}.get(window, window)
    role_label = {
        "teacher": "Öğretmen", "student": "Öğrenci",
        "parent": "Veli", "institution_admin": "Kurum Yöneticisi",
    }.get(role, "Tüm roller") if role else "Tüm roller"
    return templates.TemplateResponse(
        "admin/_activity_drill_users.html",
        {
            "request": request,
            "rows": rows,
            "window": window,
            "window_label": win_label,
            "role": role,
            "role_label": role_label,
        },
    )


@router.get("/security-monitor/activity/drill/heatmap")
def security_monitor_activity_drill_heatmap(
    request: Request,
    institution_id: int,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """HTMX partial: tek bir kurumun heatmap'i + örüntü etiketleri."""
    from app.services.tenant_activity import institution_hour_day_heatmap
    h = institution_hour_day_heatmap(db, institution_id=institution_id)
    return templates.TemplateResponse(
        "admin/_activity_drill_heatmap.html",
        {"request": request, "h": h},
    )


@router.get("/security-monitor/revenue")
def security_monitor_revenue(
    request: Request,
    segment: str = "all",
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Ticari pano (11.G): MRR / plan dağılımı / trial bitiş yaklaşan / aylık trend.

    segment: 'all' (default) | 'institution' | 'user' — kurum vs bağımsız öğretmen
    filtresi. Owner-aware KPI'lar bu seçime göre yeniden hesaplanır.
    `data` (eski kurum-merkezli görünüm) toggle'dan etkilenmez — backward compat.
    """
    from app.services.revenue_panel import get_revenue_panel_data
    from app.services.revenue_owner import (
        mrr_owner_aware,
        plan_distribution_owner_aware,
        trial_ending_soon_owner_aware,
    )
    # Bilinmeyen değer → 'all'
    if segment not in ("all", "institution", "user"):
        segment = "all"
    data = get_revenue_panel_data(db)
    # Sprint F.2/F.3 — owner-aware ek görünüm (segment filtreli)
    try:
        mrr_combined = mrr_owner_aware(db, segment=segment)
        plan_dist_combined = plan_distribution_owner_aware(db, segment=segment)
        trial_combined = trial_ending_soon_owner_aware(
            db, days_horizon=7, segment=segment,
        )
        # Toggle başlıklarında segment-başına toplam sayıyı göstermek için
        # her zaman tüm segmentlerin count'ünü ayrıca getir.
        mrr_all = mrr_owner_aware(db, segment="all")
    except Exception:
        mrr_combined = None
        plan_dist_combined = []
        trial_combined = []
        mrr_all = None
    return templates.TemplateResponse(
        "admin/security_monitor_revenue.html",
        {
            "request": request, "user": user, "data": data,
            "mrr_combined": mrr_combined,
            "plan_dist_combined": plan_dist_combined,
            "trial_combined": trial_combined,
            "segment": segment,
            "segment_counts": {
                "all": (mrr_all.get("total_owners") if mrr_all else 0),
                "institution": (mrr_all.get("institution_count") if mrr_all else 0),
                "user": (mrr_all.get("user_count") if mrr_all else 0),
            },
        },
    )


@router.get("/security-monitor/revenue/drill")
def security_monitor_revenue_drill(
    request: Request,
    key: str,
    plan: str | None = None,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Faz A — Drill-down: bir sayının arkasındaki kurum listesini HTMX partial olarak döner.

    Beklenen key örnekleri:
      - health:critical / health:risk / health:watch / health:healthy
      - trial:expired_30d
      - plan_change:signup / :upgrade / :downgrade / :pause / :resume / :trial_expired
      - plan_change:guarantee_extend / :academic_year_renewal
      - paying / free
      - plan:<plan_code>           (örn. plan:dershane_pro)
      - invoice_bucket:<bucket>    (örn. invoice_bucket:overdue_7plus)
    """
    from app.services.revenue_panel import drill_for_key
    result = drill_for_key(db, key=key, plan=plan)
    return templates.TemplateResponse(
        "admin/_revenue_drill.html",
        {"request": request, "user": user, "data": result},
    )


@router.get("/revenue/action-center")
def revenue_action_center(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sprint C (Faz D) — Aksiyon Merkezi.

    "Bugün ne yapmalıyım?" — kritik kurumlar, trial bitiyor, ödeme gecikti
    olan kurumlar tek panoda öncelik sırasıyla.
    """
    from app.services.action_center import action_center_data
    data = action_center_data(db)
    return templates.TemplateResponse(
        "admin/action_center.html",
        {"request": request, "user": user, "data": data},
    )


@router.get("/revenue/users/{user_id}")
def revenue_user_detail(
    user_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sprint F.2 — Bağımsız öğretmen detay sayfası (User-360 lite).

    Kurum 360'ın bağımsız öğretmen versiyonu. Plan + ödeme + son aktivite +
    teklif geçmişi.
    """
    from app.models import (
        OFFER_KIND_ICONS,
        OFFER_KIND_LABELS_TR,
        OFFER_STATUS_COLORS,
        OFFER_STATUS_LABELS_TR,
        User as _User,
        UserRole as _UserRole,
    )
    from app.services.revenue_owner import get_owner
    owner = get_owner(db, owner_type="user", owner_id=user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Bağımsız öğretmen bulunamadı")
    u = db.get(_User, user_id)
    # Öğrencisi sayısı
    # Bu bağımsız öğretmenin öğrencileri (aktif + pasif birlikte; sağlık
    # sekmesinde aktif/pasif ayrımı + risk bandı gösterilecek)
    all_students = (
        db.query(_User)
        .filter(
            _User.teacher_id == user_id,
            _User.role == _UserRole.STUDENT,
        )
        .order_by(_User.full_name.asc())
        .all()
    )
    active_students = [s for s in all_students if s.is_active]
    student_count = len(active_students)

    # Öğrenci sağlığı — son giriş bazlı bant (öğretmen için kullandığımız
    # heuristik). Öğretmenin değer ürettiği çark öğrencisi pasifse zayıftır.
    now_utc = datetime.now(timezone.utc)
    student_health = {"healthy": 0, "watch": 0, "risk": 0, "critical": 0}
    student_rows: list[dict] = []
    for s in all_students:
        last = s.last_login_at
        if last is None:
            band = "critical"; days = None; label = "hiç giriş yok"
        else:
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days = (now_utc - last).days
            if days >= 30:
                band = "critical"
            elif days >= 14:
                band = "risk"
            elif days >= 7:
                band = "watch"
            else:
                band = "healthy"
            label = f"{days}g önce" if days > 0 else "bugün"
        if s.is_active:
            student_health[band] += 1
        student_rows.append({
            "student": s,
            "band": band,
            "days_since_login": days,
            "label": label,
        })
    band_order = {"critical": 0, "risk": 1, "watch": 2, "healthy": 3}
    student_rows.sort(
        key=lambda r: (
            0 if r["student"].is_active else 1,
            band_order.get(r["band"], 9),
            -(r["days_since_login"] or 9999),
        ),
    )
    student_health["unhealthy_total"] = student_health["risk"] + student_health["critical"]
    student_health["total"] = student_count

    # Son 30 günde bu öğretmenin öğrencilerine düşen görev hareketleri
    from datetime import timedelta as _td2
    cutoff_30 = (now_utc - _td2(days=30)).date()
    from app.models import Task as _Task, TaskBookItem as _TBI
    student_ids = [s.id for s in active_students] if active_students else []
    task_rows = (
        db.query(_Task.is_draft, _TBI.planned_count, _TBI.completed_count)
        .join(_TBI, _TBI.task_id == _Task.id)
        .filter(_Task.student_id.in_(student_ids), _Task.date >= cutoff_30)
        .all()
    ) if student_ids else []
    tasks_planned_30d = sum(r[1] or 0 for r in task_rows if not r[0])
    tasks_completed_30d = sum(r[2] or 0 for r in task_rows if not r[0])
    tasks_draft_30d = sum(1 for r in task_rows if r[0])
    completion_pct = (
        round(100 * tasks_completed_30d / tasks_planned_30d) if tasks_planned_30d > 0 else 0
    )

    # Plan history (PlanChangeHistory: owner_type=user)
    from app.models import PlanChangeHistory
    from app.models.plan_history import PlanOwnerType
    plan_changes = (
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.owner_type == PlanOwnerType.USER,
            PlanChangeHistory.owner_id == user_id,
        )
        .order_by(PlanChangeHistory.occurred_at.desc())
        .limit(20)
        .all()
    )
    # CRM not + aksiyon (Sprint F.3 — owner-aware genişletme)
    from app.services.institution_360 import crm_notes_for, crm_actions_for
    crm_notes = crm_notes_for(db, user_id=user_id)
    crm_actions = crm_actions_for(db, user_id=user_id)
    # Sağlık Skoru 2.0 — User variant (Sprint F.3)
    from app.services.health_score_v2 import (
        compute_health_score_v2_for_user, get_score_history,
    )
    try:
        health_v2 = compute_health_score_v2_for_user(db, user_obj=u)
    except Exception:
        health_v2 = None
    try:
        score_history = get_score_history(db, user_id=user_id, days=14)
    except Exception:
        score_history = []

    # Teklifler (Sprint F.3 — Offer owner-aware)
    from app.services.offers import list_offers_for_owner
    offers = list_offers_for_owner(db, user_id=user_id, limit=50)

    # Faturalar (Sprint F.3 — Invoice owner-aware)
    from app.services.revenue_panel import invoices_for_owner
    invoices = invoices_for_owner(db, user_id=user_id, include_archived=False, limit=100)
    open_invoices = [i for i in invoices if i["status"] in ("pending", "overdue")]
    paid_invoices = [i for i in invoices if i["status"] == "paid"]
    overdue_invoices_count = sum(1 for i in invoices if i["status"] == "overdue")
    overdue_total = sum(
        i["amount_try"] for i in invoices if i["status"] == "overdue"
    )

    # Öğretmenin kendisinin login band'ı (sağlık özetinin üst KPI'sı)
    teacher_last = u.last_login_at
    if teacher_last is None:
        teacher_days = None; teacher_band = "critical"; teacher_label = "hiç giriş yok"
    else:
        if teacher_last.tzinfo is None:
            teacher_last = teacher_last.replace(tzinfo=timezone.utc)
        teacher_days = (now_utc - teacher_last).days
        if teacher_days >= 30:
            teacher_band = "critical"
        elif teacher_days >= 14:
            teacher_band = "risk"
        elif teacher_days >= 7:
            teacher_band = "watch"
        else:
            teacher_band = "healthy"
        teacher_label = f"{teacher_days}g önce" if teacher_days > 0 else "bugün"

    active_tab = request.query_params.get("tab", "health")

    from app.models import (
        OWNER_TAG_COLORS,
        OWNER_TAG_DESCRIPTIONS,
        OWNER_TAG_ICONS,
        OWNER_TAG_LABELS_TR,
        OfferKind,
        OwnerTagKind,
    )
    from app.services.owner_tags import list_tags_for
    from app.services.owner_contact import get_contact
    from app.services.crm_templates import list_templates as _list_tpls
    owner_tags = list_tags_for(db, owner_type="user", owner_id=user_id)
    owner_contact = get_contact(db, owner_type="user", owner_id=user_id)
    action_templates = _list_tpls(db, active_only=True)

    return templates.TemplateResponse(
        "admin/user_detail_revenue.html",
        {
            "request": request,
            "user": user,
            "owner": owner,
            "u": u,
            "active_tab": active_tab,
            "student_count": student_count,
            "student_health": student_health,
            "student_rows": student_rows,
            "all_students_total": len(all_students),
            "tasks_planned_30d": tasks_planned_30d,
            "tasks_completed_30d": tasks_completed_30d,
            "tasks_draft_30d": tasks_draft_30d,
            "completion_pct": completion_pct,
            "teacher_band": teacher_band,
            "teacher_days_since_login": teacher_days,
            "teacher_login_label": teacher_label,
            "plan_changes": plan_changes,
            "crm_notes": crm_notes,
            "crm_actions": crm_actions,
            "invoices": invoices,
            "open_invoices": open_invoices,
            "paid_invoices": paid_invoices,
            "overdue_invoices_count": overdue_invoices_count,
            "overdue_total": overdue_total,
            "health_v2": health_v2,
            "score_history": score_history,
            "offers": offers,
            "offer_kinds": list(OfferKind),
            "offer_kind_labels": OFFER_KIND_LABELS_TR,
            "offer_kind_icons": OFFER_KIND_ICONS,
            "offer_status_labels": OFFER_STATUS_LABELS_TR,
            "offer_status_colors": OFFER_STATUS_COLORS,
            "owner_tags": owner_tags,
            "owner_tag_kinds": list(OwnerTagKind),
            "owner_tag_labels": OWNER_TAG_LABELS_TR,
            "owner_tag_colors": OWNER_TAG_COLORS,
            "owner_tag_icons": OWNER_TAG_ICONS,
            "owner_tag_descriptions": OWNER_TAG_DESCRIPTIONS,
            "owner_contact": owner_contact,
            "action_templates": action_templates,
        },
    )


@router.post("/revenue/users/{user_id}/crm/notes/add")
def user_crm_note_add(
    user_id: int,
    request: Request,
    content: str = Form(...),
    pinned: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import create_note
    if not content.strip():
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?err="
                + quote("Not içeriği boş olamaz"),
            status_code=303,
        )
    note = create_note(
        db, user_id=user_id,
        content=content.strip(), by_user_id=user.id,
        pinned=bool(pinned),
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_note",
        target_id=note.id,
        request=request,
        details={"action": "create", "owner_type": "user",
                  "user_id": user_id, "pinned": bool(pinned)},
    )
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?ok=" + quote("Not eklendi"),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/crm/notes/{note_id}/pin")
def user_crm_note_pin(
    user_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import toggle_note_pin
    note = toggle_note_pin(db, note_id=note_id)
    if note is None:
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?err=" + quote("Not yok"),
            status_code=303,
        )
    msg = "Not sabitlendi" if note.pinned else "Sabitleme kaldırıldı"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/crm/notes/{note_id}/delete")
def user_crm_note_delete(
    user_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import delete_note
    ok = delete_note(db, note_id=note_id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_note",
        target_id=note_id,
        request=request,
        details={"action": "delete", "ok": ok, "user_id": user_id},
    )
    msg = "Not silindi" if ok else "Not bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/crm/actions/add")
def user_crm_action_add(
    user_id: int,
    request: Request,
    kind: str = Form(...),
    summary: str = Form(...),
    notes: str = Form(""),
    result: str = Form("pending"),
    follow_up_at: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import create_action
    if not summary.strip():
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?err=" + quote("Özet boş olamaz"),
            status_code=303,
        )
    follow_dt: datetime | None = None
    if follow_up_at.strip():
        try:
            from datetime import datetime as _dt
            s = follow_up_at.strip()
            try:
                follow_dt = _dt.fromisoformat(s).replace(tzinfo=timezone.utc)
            except Exception:
                follow_dt = _dt.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            follow_dt = None
    action = create_action(
        db, user_id=user_id, kind=kind, summary=summary.strip(),
        notes=notes.strip() or None, result=result, by_user_id=user.id,
        follow_up_at=follow_dt,
    )
    if action is None:
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?err=" + quote("Geçersiz aksiyon tipi"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action.id,
        request=request,
        details={"action": "create", "kind": kind, "result": result,
                  "owner_type": "user", "user_id": user_id},
    )
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?ok=" + quote("Aksiyon eklendi"),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/crm/actions/{action_id}/complete")
def user_crm_action_complete(
    user_id: int,
    action_id: int,
    request: Request,
    result: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import complete_action
    a = complete_action(
        db, action_id=action_id, result=result, by_user_id=user.id,
        notes=notes.strip() or None,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action_id,
        request=request,
        details={"action": "complete", "ok": a is not None, "result": result,
                  "user_id": user_id},
    )
    msg = "Aksiyon tamamlandı" if a else "Aksiyon bulunamadı / geçersiz sonuç"
    key = "ok" if a else "err"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/crm/actions/{action_id}/delete")
def user_crm_action_delete(
    user_id: int,
    action_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import delete_action
    ok = delete_action(db, action_id=action_id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action_id,
        request=request,
        details={"action": "delete", "ok": ok, "user_id": user_id},
    )
    msg = "Aksiyon silindi" if ok else "Aksiyon bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.get("/revenue/forecast")
def revenue_forecast(
    request: Request,
    save_rate: float = 0.5,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sprint E.2 (Faz H) — MRR Tahmin & Senaryo karşılaştırma.

    30/60/90 günlük MRR projeksiyonu + risk altında MRR + status quo vs
    müdahale senaryo.
    """
    from app.services.revenue_forecast import (
        mrr_projection,
        risk_at_mrr,
        scenario_comparison,
    )
    save_rate = max(0.0, min(1.0, float(save_rate)))
    risk = risk_at_mrr(db)
    proj_30 = mrr_projection(db, horizon_days=30, intervention_save_rate=save_rate)
    proj_60 = mrr_projection(db, horizon_days=60, intervention_save_rate=save_rate)
    proj_90 = mrr_projection(db, horizon_days=90, intervention_save_rate=save_rate)
    scenario = scenario_comparison(db, save_rate=save_rate)
    return templates.TemplateResponse(
        "admin/revenue_forecast.html",
        {
            "request": request,
            "user": user,
            "risk": risk,
            "proj_30": proj_30,
            "proj_60": proj_60,
            "proj_90": proj_90,
            "scenario": scenario,
            "save_rate": save_rate,
            "save_rate_pct": int(save_rate * 100),
        },
    )


@router.get("/revenue/cohort")
def revenue_cohort(
    request: Request,
    months_back: int = 12,
    horizon: int = 12,
    churn_days: int = 90,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sprint D.2 (Faz G) — Kohort & LTV analizi.

    Aylık kayıt cohort'u + N aylık tutunma matrisi + plan churn + LTV.
    """
    from app.services.revenue_cohort import (
        ltv_estimate,
        plan_churn_summary,
        signup_cohort_matrix,
    )
    months_back = max(3, min(24, int(months_back)))
    horizon = max(3, min(24, int(horizon)))
    churn_days = max(7, min(365, int(churn_days)))
    matrix = signup_cohort_matrix(
        db, months_back=months_back, horizon_months=horizon,
    )
    churn = plan_churn_summary(db, days=churn_days)
    ltv = ltv_estimate(db)
    return templates.TemplateResponse(
        "admin/revenue_cohort.html",
        {
            "request": request,
            "user": user,
            "matrix": matrix,
            "churn": churn,
            "ltv": ltv,
            "months_back": months_back,
            "horizon": horizon,
            "churn_days": churn_days,
        },
    )


@router.post("/revenue/action-center/quick-action")
def revenue_quick_action(
    request: Request,
    institution_id: int = Form(...),
    kind: str = Form(...),
    summary: str = Form(...),
    result: str = Form("pending"),
    follow_up_days: int = Form(0),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Aksiyon merkezinde 'önerilen aksiyon' butonu — hızlı CrmAction oluştur."""
    from app.services.institution_360 import create_action
    follow_dt = None
    if follow_up_days and follow_up_days > 0:
        follow_dt = datetime.now(timezone.utc) + timedelta(days=int(follow_up_days))
    action = create_action(
        db, institution_id=institution_id,
        kind=kind, summary=summary.strip(),
        by_user_id=user.id, result=result,
        follow_up_at=follow_dt,
    )
    if action is None:
        return RedirectResponse(
            url="/admin/revenue/action-center?err=" + quote("Geçersiz aksiyon tipi"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action.id,
        request=request,
        details={"action": "quick_create", "kind": kind,
                  "institution_id": institution_id},
    )
    return RedirectResponse(
        url="/admin/revenue/action-center?ok=" + quote("Aksiyon eklendi"),
        status_code=303,
    )


# ---------------------------- Manuel Ödeme Müdahaleleri ----------------------------


@router.post("/invoices/{invoice_id}/postpone")
def invoice_postpone(
    invoice_id: int,
    request: Request,
    days: int = Form(7),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir faturanın vadesini X gün ileri al (ödeme erteleme)."""
    from app.models import Invoice, InvoiceStatus
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        return RedirectResponse(
            url="/admin/security-monitor/revenue?err=" + quote("Fatura yok"),
            status_code=303,
        )
    if inv.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&err="
                + quote("Bu fatura artık ertelenemez"),
            status_code=303,
        )
    days = max(1, min(int(days), 90))
    old_due = inv.due_at
    # SQLite naive datetime ile aware datetime karışmaması için _aware ile sar
    base_due = inv.due_at
    if base_due is not None and base_due.tzinfo is None:
        base_due = base_due.replace(tzinfo=timezone.utc)
    inv.due_at = base_due + timedelta(days=days)
    # OVERDUE ise ve yeni vade hâlâ geçmişte değilse PENDING'e döndür
    if inv.status == InvoiceStatus.OVERDUE and inv.due_at >= datetime.now(timezone.utc):
        inv.status = InvoiceStatus.PENDING
    inv.notes = ((inv.notes or "") + f"\n[Ötelendi {days}g — {(note or '').strip()}]")[:8000]
    db.commit()
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="invoice",
        target_id=invoice_id,
        request=request,
        details={
            "action": "postpone", "days": days,
            "institution_id": inv.institution_id,
            "old_due": old_due.isoformat() if old_due else None,
            "new_due": inv.due_at.isoformat(),
            "note": (note or "")[:200],
        },
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&ok="
            + quote(f"Vade {days} gün ileri alındı"),
        status_code=303,
    )


@router.post("/invoices/{invoice_id}/mark-paid")
def invoice_mark_paid(
    invoice_id: int,
    request: Request,
    method: str = Form("manual"),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Manuel ödenmiş olarak işaretle (EFT/havale geldikten sonra)."""
    from app.models import Invoice, InvoiceStatus, PaymentMethod
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        return RedirectResponse(
            url="/admin/security-monitor/revenue?err=" + quote("Fatura yok"),
            status_code=303,
        )
    if inv.status == InvoiceStatus.PAID:
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&err="
                + quote("Zaten ödendi"),
            status_code=303,
        )
    try:
        pm = PaymentMethod(method)
    except ValueError:
        pm = PaymentMethod.MANUAL
    inv.status = InvoiceStatus.PAID
    inv.paid_at = datetime.now(timezone.utc)
    inv.payment_method = pm
    if note.strip():
        inv.notes = ((inv.notes or "") + f"\n[Manuel öden: {note.strip()}]")[:8000]
    db.commit()
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="invoice",
        target_id=invoice_id,
        request=request,
        details={
            "action": "mark_paid", "method": pm.value,
            "institution_id": inv.institution_id,
            "amount_try": inv.amount_try,
            "note": (note or "")[:200],
        },
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&ok="
            + quote("Fatura ödenmiş olarak işaretlendi"),
        status_code=303,
    )


@router.post("/invoices/{invoice_id}/cancel")
def invoice_cancel(
    invoice_id: int,
    request: Request,
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Faturayı iptal et (silmez, status=cancelled)."""
    from app.models import Invoice, InvoiceStatus
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        return RedirectResponse(
            url="/admin/security-monitor/revenue?err=" + quote("Fatura yok"),
            status_code=303,
        )
    if inv.status in (InvoiceStatus.PAID, InvoiceStatus.REFUNDED):
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&err="
                + quote("Ödenmiş veya iade edilmiş fatura iptal edilemez"),
            status_code=303,
        )
    inv.status = InvoiceStatus.CANCELLED
    if note.strip():
        inv.notes = ((inv.notes or "") + f"\n[İptal: {note.strip()}]")[:8000]
    db.commit()
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="invoice",
        target_id=invoice_id,
        request=request,
        details={"action": "cancel", "institution_id": inv.institution_id,
                  "note": (note or "")[:200]},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{inv.institution_id}?tab=billing&ok="
            + quote("Fatura iptal edildi"),
        status_code=303,
    )


@router.post("/invoices/{invoice_id}/send-reminder")
def invoice_send_reminder(
    invoice_id: int,
    request: Request,
    kind: str = Form("manual"),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Manuel olarak ödeme hatırlatması gönder (e-posta + kayıt)."""
    from app.services.dunning import send_reminder
    result = send_reminder(
        db, invoice_id=invoice_id, kind=kind,
        triggered_by_user_id=user.id, manual=True,
    )
    if not result.get("ok"):
        return RedirectResponse(
            url="/admin/security-monitor/revenue?err=" + quote(result.get("error", "Hata")),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="invoice",
        target_id=invoice_id,
        request=request,
        details={"action": "send_reminder_manual", "kind": kind,
                  "institution_id": result.get("institution_id")},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{result['institution_id']}?tab=billing&ok="
            + quote(f"Hatırlatma gönderildi ({kind})"),
        status_code=303,
    )


@router.get("/revenue/institutions/{institution_id}")
def revenue_institution_360(
    institution_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sprint B (Faz B) — Kurum 360.

    Bir kurumun her şeyi tek panoda: kimlik + sağlık + kullanım + ödeme +
    notlar + aksiyonlar + riskler.
    """
    from app.services.institution_360 import get_institution_360
    data = get_institution_360(db, institution_id=institution_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Kurum bulunamadı")
    from app.models import (
        CRM_ACTION_KIND_ICONS,
        CRM_ACTION_KIND_LABELS_TR,
        CRM_ACTION_RESULT_COLORS,
        CRM_ACTION_RESULT_LABELS_TR,
        OFFER_KIND_ICONS,
        OFFER_KIND_LABELS_TR,
        OFFER_STATUS_COLORS,
        OFFER_STATUS_LABELS_TR,
        CrmActionKind,
        CrmActionResult,
        OfferKind,
    )
    from app.services.offers import describe_offer, list_offers_for_institution
    offers = list_offers_for_institution(db, institution_id=institution_id)
    offer_summaries = {o.id: describe_offer(o) for o in offers}
    # Sprint F.1 — Sağlık Skoru 2.0
    from app.models import Institution as _Inst
    from app.services.health_score_v2 import (
        compute_health_score_v2,
        detect_warning_triggers,
        get_score_history,
    )
    inst_obj = db.get(_Inst, institution_id)
    try:
        health_v2 = compute_health_score_v2(db, institution=inst_obj)
        triggers = detect_warning_triggers(db, institution=inst_obj)
        history = get_score_history(db, institution_id=institution_id, days=14)
    except Exception:
        health_v2 = None
        triggers = []
        history = []
    from app.models import (
        OWNER_TAG_COLORS,
        OWNER_TAG_DESCRIPTIONS,
        OWNER_TAG_ICONS,
        OWNER_TAG_LABELS_TR,
        OwnerTagKind,
        PlanChangeHistory as _PCH2,
    )
    from app.models.plan_history import PlanOwnerType as _POT2
    from app.services.owner_tags import list_tags_for
    from app.services.owner_contact import get_contact
    from app.services.crm_templates import list_templates as _list_tpls
    owner_tags = list_tags_for(
        db, owner_type="institution", owner_id=institution_id,
    )
    owner_contact = get_contact(
        db, owner_type="institution", owner_id=institution_id,
    )
    action_templates = _list_tpls(db, active_only=True)
    plan_changes = (
        db.query(_PCH2)
        .filter(
            _PCH2.owner_type == _POT2.INSTITUTION,
            _PCH2.owner_id == institution_id,
        )
        .order_by(_PCH2.occurred_at.desc())
        .limit(30)
        .all()
    )
    return templates.TemplateResponse(
        "admin/institution_360.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "crm_kind_labels": CRM_ACTION_KIND_LABELS_TR,
            "crm_kind_icons": CRM_ACTION_KIND_ICONS,
            "crm_result_labels": CRM_ACTION_RESULT_LABELS_TR,
            "crm_result_colors": CRM_ACTION_RESULT_COLORS,
            "crm_kinds": list(CrmActionKind),
            "crm_results": list(CrmActionResult),
            "offers": offers,
            "offer_summaries": offer_summaries,
            "offer_kinds": list(OfferKind),
            "offer_kind_labels": OFFER_KIND_LABELS_TR,
            "offer_kind_icons": OFFER_KIND_ICONS,
            "offer_status_labels": OFFER_STATUS_LABELS_TR,
            "offer_status_colors": OFFER_STATUS_COLORS,
            "health_v2": health_v2,
            "health_triggers": triggers,
            "health_history": history,
            "owner_tags": owner_tags,
            "owner_tag_kinds": list(OwnerTagKind),
            "owner_tag_labels": OWNER_TAG_LABELS_TR,
            "owner_tag_colors": OWNER_TAG_COLORS,
            "owner_tag_icons": OWNER_TAG_ICONS,
            "owner_tag_descriptions": OWNER_TAG_DESCRIPTIONS,
            "plan_changes": plan_changes,
            "owner_contact": owner_contact,
            "action_templates": action_templates,
        },
    )


@router.post("/revenue/institutions/{institution_id}/crm/notes/add")
def crm_note_add(
    institution_id: int,
    request: Request,
    content: str = Form(...),
    pinned: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import create_note
    if not content.strip():
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=notes"
                + "&err=" + quote("Not içeriği boş olamaz"),
            status_code=303,
        )
    note = create_note(
        db, institution_id=institution_id,
        content=content.strip(), by_user_id=user.id,
        pinned=bool(pinned),
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_note",
        target_id=note.id,
        request=request,
        details={"action": "create", "institution_id": institution_id,
                  "pinned": bool(pinned), "len": len(content)},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=notes&ok="
            + quote("Not eklendi"),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/crm/notes/{note_id}/pin")
def crm_note_pin(
    institution_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import toggle_note_pin
    note = toggle_note_pin(db, note_id=note_id)
    if note is None:
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=notes&err="
                + quote("Not yok"),
            status_code=303,
        )
    msg = "Not sabitlendi" if note.pinned else "Not sabitlemesi kaldırıldı"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=notes&ok="
            + quote(msg),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/crm/notes/{note_id}/delete")
def crm_note_delete(
    institution_id: int,
    note_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import delete_note
    ok = delete_note(db, note_id=note_id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_note",
        target_id=note_id,
        request=request,
        details={"action": "delete", "ok": ok,
                  "institution_id": institution_id},
    )
    msg = "Not silindi" if ok else "Not bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=notes&{key}="
            + quote(msg),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/crm/actions/add")
def crm_action_add(
    institution_id: int,
    request: Request,
    kind: str = Form(...),
    summary: str = Form(...),
    notes: str = Form(""),
    result: str = Form("pending"),
    follow_up_at: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import create_action
    if not summary.strip():
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=actions"
                + "&err=" + quote("Özet boş olamaz"),
            status_code=303,
        )
    follow_dt: datetime | None = None
    if follow_up_at.strip():
        try:
            # YYYY-MM-DD veya YYYY-MM-DDTHH:MM kabul et
            from datetime import datetime as _dt
            s = follow_up_at.strip()
            try:
                follow_dt = _dt.fromisoformat(s).replace(tzinfo=timezone.utc)
            except Exception:
                follow_dt = _dt.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            follow_dt = None
    action = create_action(
        db, institution_id=institution_id, kind=kind, summary=summary.strip(),
        notes=notes.strip() or None, result=result, by_user_id=user.id,
        follow_up_at=follow_dt,
    )
    if action is None:
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=actions"
                + "&err=" + quote("Geçersiz aksiyon tipi"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action.id,
        request=request,
        details={"action": "create", "kind": kind, "result": result,
                  "institution_id": institution_id},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=actions&ok="
            + quote("Aksiyon eklendi"),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/crm/actions/{action_id}/complete")
def crm_action_complete(
    institution_id: int,
    action_id: int,
    request: Request,
    result: str = Form(...),
    notes: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import complete_action
    a = complete_action(
        db, action_id=action_id, result=result, by_user_id=user.id,
        notes=notes.strip() or None,
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action_id,
        request=request,
        details={"action": "complete", "ok": a is not None, "result": result,
                  "institution_id": institution_id},
    )
    msg = "Aksiyon tamamlandı" if a else "Aksiyon bulunamadı / geçersiz sonuç"
    key = "ok" if a else "err"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=actions&{key}="
            + quote(msg),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/offers/create")
def offer_create(
    institution_id: int,
    request: Request,
    kind: str = Form(...),
    title: str = Form(...),
    value: str = Form(""),
    duration_months: str = Form(""),
    new_plan: str = Form(""),
    public_message: str = Form(""),
    admin_note: str = Form(""),
    expires_in_days: int = Form(14),
    send_now: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kuruma yeni teklif oluştur. send_now=1 ise hemen gönder."""
    from app.services.offers import create_offer, send_offer
    val: float | None = None
    if value.strip():
        try:
            val = float(value.replace(",", "."))
        except ValueError:
            val = None
    dur: int | None = None
    if duration_months.strip():
        try:
            dur = int(duration_months)
        except ValueError:
            dur = None
    offer = create_offer(
        db, institution_id=institution_id,
        kind=kind, title=title, by_user_id=user.id,
        value=val, duration_months=dur,
        new_plan=new_plan.strip() or None,
        public_message=public_message.strip() or None,
        admin_note=admin_note.strip() or None,
        expires_in_days=int(expires_in_days) if expires_in_days else None,
    )
    if offer is None:
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=offers&err="
                + quote("Geçersiz teklif türü"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="offer",
        target_id=offer.id,
        request=request,
        details={"action": "create", "kind": kind,
                  "institution_id": institution_id,
                  "value": val, "duration_months": dur,
                  "new_plan": new_plan or None},
    )
    msg = "Teklif oluşturuldu"
    if send_now:
        result = send_offer(db, offer_id=offer.id)
        if result.get("ok"):
            log_action(
                db,
                action=AuditAction.USER_UPDATE,
                actor_id=user.id,
                target_type="offer",
                target_id=offer.id,
                request=request,
                details={"action": "send", "institution_id": institution_id,
                          "sent_via_email": result.get("sent_via_email")},
            )
            msg = "Teklif oluşturuldu ve gönderildi"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=offers&ok="
            + quote(msg),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/offers/{offer_id}/send")
def offer_send_endpoint(
    institution_id: int,
    offer_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir DRAFT teklifi SENT'e taşı + e-posta tetikle."""
    from app.services.offers import send_offer
    result = send_offer(db, offer_id=offer_id)
    if not result.get("ok"):
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}?tab=offers&err="
                + quote(f"Hata: {result.get('error')}"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="offer",
        target_id=offer_id,
        request=request,
        details={"action": "send", "institution_id": institution_id,
                  "sent_via_email": result.get("sent_via_email")},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=offers&ok="
            + quote("Teklif gönderildi"),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/offers/{offer_id}/cancel")
def offer_cancel_endpoint(
    institution_id: int,
    offer_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.offers import cancel_offer
    result = cancel_offer(db, offer_id=offer_id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="offer",
        target_id=offer_id,
        request=request,
        details={"action": "cancel", "ok": result.get("ok"),
                  "institution_id": institution_id},
    )
    key = "ok" if result.get("ok") else "err"
    msg = "Teklif iptal edildi" if result.get("ok") else f"Hata: {result.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=offers&{key}="
            + quote(msg),
        status_code=303,
    )


# ---------------------------- User (bağımsız öğretmen) offers ---------------------------


@router.post("/revenue/users/{user_id}/offers/create")
def user_offer_create(
    user_id: int,
    request: Request,
    kind: str = Form(...),
    title: str = Form(...),
    value: str = Form(""),
    duration_months: str = Form(""),
    new_plan: str = Form(""),
    public_message: str = Form(""),
    admin_note: str = Form(""),
    expires_in_days: int = Form(14),
    send_now: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bağımsız öğretmene yeni teklif (Sprint F.3 — Offer owner-aware)."""
    from app.services.offers import create_offer, send_offer
    val: float | None = None
    if value.strip():
        try:
            val = float(value.replace(",", "."))
        except ValueError:
            val = None
    dur: int | None = None
    if duration_months.strip():
        try:
            dur = int(duration_months)
        except ValueError:
            dur = None
    offer = create_offer(
        db, user_id=user_id,
        kind=kind, title=title, by_user_id=user.id,
        value=val, duration_months=dur,
        new_plan=new_plan.strip() or None,
        public_message=public_message.strip() or None,
        admin_note=admin_note.strip() or None,
        expires_in_days=int(expires_in_days) if expires_in_days else None,
    )
    if offer is None:
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?tab=offers&err="
                + quote("Geçersiz teklif türü"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer.id, request=request,
        details={"action": "create", "kind": kind, "owner_type": "user",
                  "user_id": user_id, "value": val, "duration_months": dur,
                  "new_plan": new_plan or None},
    )
    msg = "Teklif oluşturuldu"
    if send_now:
        result = send_offer(db, offer_id=offer.id)
        if result.get("ok"):
            log_action(
                db, action=AuditAction.USER_UPDATE, actor_id=user.id,
                target_type="offer", target_id=offer.id, request=request,
                details={"action": "send", "user_id": user_id,
                          "sent_via_email": result.get("sent_via_email")},
            )
            msg = "Teklif oluşturuldu ve gönderildi"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?tab=offers&ok=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/offers/{offer_id}/send")
def user_offer_send_endpoint(
    user_id: int,
    offer_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.offers import send_offer
    result = send_offer(db, offer_id=offer_id)
    if not result.get("ok"):
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}?tab=offers&err="
                + quote(f"Hata: {result.get('error')}"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer_id, request=request,
        details={"action": "send", "user_id": user_id,
                  "sent_via_email": result.get("sent_via_email")},
    )
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?tab=offers&ok=" + quote("Teklif gönderildi"),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/offers/{offer_id}/cancel")
def user_offer_cancel_endpoint(
    user_id: int,
    offer_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.offers import cancel_offer
    result = cancel_offer(db, offer_id=offer_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="offer", target_id=offer_id, request=request,
        details={"action": "cancel", "ok": result.get("ok"), "user_id": user_id},
    )
    key = "ok" if result.get("ok") else "err"
    msg = "Teklif iptal edildi" if result.get("ok") else f"Hata: {result.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?tab=offers&{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/crm/actions/{action_id}/delete")
def crm_action_delete(
    institution_id: int,
    action_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.institution_360 import delete_action
    ok = delete_action(db, action_id=action_id)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="crm_action",
        target_id=action_id,
        request=request,
        details={"action": "delete", "ok": ok,
                  "institution_id": institution_id},
    )
    msg = "Aksiyon silindi" if ok else "Aksiyon bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?tab=actions&{key}="
            + quote(msg),
        status_code=303,
    )


# ---------------------------- Owner Tag endpoints (Faz B1) ----------------------------


# ---------------------------- CRM aksiyon şablonları (Faz B4) ----------------------------


@router.get("/revenue/action-templates")
def revenue_action_templates_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Şablon listeleme + ekleme formu (tek sayfada)."""
    from app.models import (
        CRM_ACTION_KIND_ICONS,
        CRM_ACTION_KIND_LABELS_TR,
        CrmActionKind,
    )
    from app.services.crm_templates import list_templates
    tpls = list_templates(db, active_only=False)
    return templates.TemplateResponse(
        "admin/action_templates.html",
        {
            "request": request,
            "user": user,
            "templates": tpls,
            "kinds": list(CrmActionKind),
            "kind_labels": CRM_ACTION_KIND_LABELS_TR,
            "kind_icons": CRM_ACTION_KIND_ICONS,
        },
    )


@router.post("/revenue/action-templates/create")
def revenue_action_template_create(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    body: str = Form(...),
    subject: str = Form(""),
    description: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.crm_templates import create_template
    tpl = create_template(
        db, name=name, kind=kind, body=body,
        subject=subject or None,
        description=description or None,
        by_user_id=user.id,
    )
    if tpl is None:
        return RedirectResponse(
            url="/admin/revenue/action-templates?err="
                + quote("Şablon oluşturulamadı (eksik alan veya geçersiz tür)"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=tpl.id, request=request,
        details={"action": "create", "name": name, "kind": kind},
    )
    return RedirectResponse(
        url="/admin/revenue/action-templates?ok="
            + quote(f"Şablon eklendi: {tpl.name}"),
        status_code=303,
    )


@router.post("/revenue/action-templates/{template_id}/update")
def revenue_action_template_update(
    template_id: int,
    request: Request,
    name: str = Form(""),
    kind: str = Form(""),
    body: str = Form(""),
    subject: str = Form(""),
    description: str = Form(""),
    is_active: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.crm_templates import update_template
    tpl = update_template(
        db, template_id=template_id,
        name=name or None, kind=kind or None,
        body=body or None,
        subject=subject if subject is not None else None,
        description=description if description is not None else None,
        is_active=bool(is_active) if is_active != "" else None,
    )
    if tpl is None:
        return RedirectResponse(
            url="/admin/revenue/action-templates?err="
                + quote("Şablon bulunamadı"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=template_id, request=request,
        details={"action": "update"},
    )
    return RedirectResponse(
        url="/admin/revenue/action-templates?ok="
            + quote(f"Şablon güncellendi: {tpl.name}"),
        status_code=303,
    )


@router.post("/revenue/action-templates/{template_id}/delete")
def revenue_action_template_delete(
    template_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.crm_templates import delete_template
    ok = delete_template(db, template_id=template_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="crm_template", target_id=template_id, request=request,
        details={"action": "delete", "ok": ok},
    )
    key = "ok" if ok else "err"
    msg = "Şablon silindi" if ok else "Şablon bulunamadı"
    return RedirectResponse(
        url=f"/admin/revenue/action-templates?{key}=" + quote(msg),
        status_code=303,
    )


@router.get("/revenue/action-templates/{template_id}/render")
def revenue_action_template_render(
    template_id: int,
    owner_type: str = "institution",
    owner_id: int = 0,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """JSON: bir şablonu owner bağlamında render eder (HTMX/JS prefill için)."""
    if owner_type not in ("institution", "user") or owner_id <= 0:
        return JSONResponse(
            {"ok": False, "error": "invalid_owner"}, status_code=400,
        )
    from app.services.crm_templates import render_template_for_owner
    result = render_template_for_owner(
        db, template_id=template_id,
        owner_type=owner_type, owner_id=owner_id,
    )
    if result is None:
        return JSONResponse(
            {"ok": False, "error": "not_found"}, status_code=404,
        )
    return JSONResponse({"ok": True, **result})


@router.post("/revenue/institutions/{institution_id}/contact/save")
def institution_contact_save(
    institution_id: int,
    request: Request,
    responsible_person_name: str = Form(""),
    responsible_person_title: str = Form(""),
    billing_email: str = Form(""),
    phone: str = Form(""),
    whatsapp: str = Form(""),
    linkedin_url: str = Form(""),
    website: str = Form(""),
    address: str = Form(""),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_contact import upsert_contact
    upsert_contact(
        db, owner_type="institution", owner_id=institution_id,
        by_user_id=user.id,
        fields={
            "responsible_person_name": responsible_person_name,
            "responsible_person_title": responsible_person_title,
            "billing_email": billing_email,
            "phone": phone,
            "whatsapp": whatsapp,
            "linkedin_url": linkedin_url,
            "website": website,
            "address": address,
            "note": note,
        },
    )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_contact", target_id=institution_id, request=request,
        details={"action": "upsert", "owner_type": "institution"},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?ok="
            + quote("İletişim bilgileri kaydedildi"),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/contact/save")
def user_contact_save(
    user_id: int,
    request: Request,
    responsible_person_name: str = Form(""),
    responsible_person_title: str = Form(""),
    billing_email: str = Form(""),
    phone: str = Form(""),
    whatsapp: str = Form(""),
    linkedin_url: str = Form(""),
    website: str = Form(""),
    address: str = Form(""),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_contact import upsert_contact
    upsert_contact(
        db, owner_type="user", owner_id=user_id,
        by_user_id=user.id,
        fields={
            "responsible_person_name": responsible_person_name,
            "responsible_person_title": responsible_person_title,
            "billing_email": billing_email,
            "phone": phone,
            "whatsapp": whatsapp,
            "linkedin_url": linkedin_url,
            "website": website,
            "address": address,
            "note": note,
        },
    )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_contact", target_id=user_id, request=request,
        details={"action": "upsert", "owner_type": "user"},
    )
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?ok="
            + quote("İletişim bilgileri kaydedildi"),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/tags/add")
def institution_tag_add(
    institution_id: int,
    request: Request,
    kind: str = Form(...),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_tags import add_tag
    tag = add_tag(
        db, owner_type="institution", owner_id=institution_id,
        kind=kind, note=note or None, by_user_id=user.id,
    )
    if tag is None:
        return RedirectResponse(
            url=f"/admin/revenue/institutions/{institution_id}"
                "?err=" + quote("Geçersiz etiket türü"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag.id, request=request,
        details={"action": "add", "owner_type": "institution",
                  "owner_id": institution_id, "kind": kind},
    )
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?ok="
            + quote(f"Etiket eklendi"),
        status_code=303,
    )


@router.post("/revenue/institutions/{institution_id}/tags/{tag_id}/delete")
def institution_tag_delete(
    institution_id: int,
    tag_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_tags import remove_tag
    ok = remove_tag(db, tag_id=tag_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag_id, request=request,
        details={"action": "delete", "owner_type": "institution",
                  "owner_id": institution_id, "ok": ok},
    )
    msg = "Etiket silindi" if ok else "Etiket bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/institutions/{institution_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/tags/add")
def user_tag_add(
    user_id: int,
    request: Request,
    kind: str = Form(...),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_tags import add_tag
    tag = add_tag(
        db, owner_type="user", owner_id=user_id,
        kind=kind, note=note or None, by_user_id=user.id,
    )
    if tag is None:
        return RedirectResponse(
            url=f"/admin/revenue/users/{user_id}"
                "?err=" + quote("Geçersiz etiket türü"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag.id, request=request,
        details={"action": "add", "owner_type": "user",
                  "owner_id": user_id, "kind": kind},
    )
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?ok="
            + quote(f"Etiket eklendi"),
        status_code=303,
    )


@router.post("/revenue/users/{user_id}/tags/{tag_id}/delete")
def user_tag_delete(
    user_id: int,
    tag_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.owner_tags import remove_tag
    ok = remove_tag(db, tag_id=tag_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="owner_tag", target_id=tag_id, request=request,
        details={"action": "delete", "owner_type": "user",
                  "owner_id": user_id, "ok": ok},
    )
    msg = "Etiket silindi" if ok else "Etiket bulunamadı"
    key = "ok" if ok else "err"
    return RedirectResponse(
        url=f"/admin/revenue/users/{user_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.get("/security-monitor/revenue/invoices")
def security_monitor_revenue_invoices(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    status_filter: str | None = None,
):
    """Faz F — Tüm faturalar listesi sayfası.

    status_filter: pending/paid/overdue/failed/refunded/cancelled
    """
    from app.models import (
        INVOICE_STATUS_BADGE_COLOR,
        INVOICE_STATUS_LABELS_TR,
        Invoice,
        InvoiceStatus,
        Institution,
    )
    q = db.query(Invoice).order_by(Invoice.due_at.desc())
    if status_filter:
        try:
            q = q.filter(Invoice.status == InvoiceStatus(status_filter))
        except ValueError:
            pass
    rows = q.limit(200).all()
    # Owner-aware: hem kurum hem bağımsız öğretmen sahipli faturalar var
    inst_ids = {r.institution_id for r in rows if r.institution_id is not None}
    user_ids = {r.user_id for r in rows if r.user_id is not None}
    insts: dict[int, Institution] = {}
    if inst_ids:
        for inst in db.query(Institution).filter(Institution.id.in_(inst_ids)).all():
            insts[inst.id] = inst
    users_map: dict[int, User] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_map[u.id] = u

    # Status başına özet
    from sqlalchemy import func as sa_func
    status_counts_raw = (
        db.query(Invoice.status, sa_func.count(Invoice.id), sa_func.coalesce(sa_func.sum(Invoice.amount_try), 0))
        .group_by(Invoice.status)
        .all()
    )
    status_counts = {
        s.value: {"count": int(c), "total_try": int(t)}
        for s, c, t in status_counts_raw
    }
    return templates.TemplateResponse(
        "admin/security_monitor_invoices.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "insts_map": insts,
            "users_map": users_map,
            "status_counts": status_counts,
            "status_labels": INVOICE_STATUS_LABELS_TR,
            "status_colors": INVOICE_STATUS_BADGE_COLOR,
            "status_filter": status_filter,
            "all_statuses": list(InvoiceStatus),
        },
    )


@router.get("/security-monitor/alarms")
def security_monitor_alarms(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Alarm kuralları + son tetiklenenler (11.F)."""
    from app.services.alarm_engine import (
        list_recent_events,
        list_rules,
        unacknowledged_count,
    )
    rules = list_rules(db)
    events = list_recent_events(db, hours=72, limit=50)
    unack = unacknowledged_count(db)
    return templates.TemplateResponse(
        "admin/security_monitor_alarms.html",
        {
            "request": request,
            "user": user,
            "rules": rules,
            "events": events,
            "unack_count": unack,
        },
    )


@router.post("/security-monitor/alarms/scan")
def security_monitor_alarms_scan(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Tüm kuralları anlık değerlendir (cron yerine elle)."""
    from app.services.alarm_engine import evaluate_all
    results = evaluate_all(db)
    triggered = sum(1 for r in results if r.triggered)
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="alarm_scan",
        request=request,
        details={"triggered": triggered, "total_rules": len(results)},
    )
    return RedirectResponse(
        url="/admin/security-monitor/alarms?ok=" + quote(
            f"Tarama tamam — {triggered} alarm tetiklendi"
        ),
        status_code=303,
    )


@router.post("/security-monitor/alarms/{event_id}/ack")
def security_monitor_alarms_ack(
    event_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bir alarm olayını gördüm olarak işaretle."""
    from app.services.alarm_engine import acknowledge
    row = acknowledge(db, event_id=event_id, user_id=user.id)
    if row is None:
        return RedirectResponse(
            url="/admin/security-monitor/alarms?err=" + quote("Alarm bulunamadı"),
            status_code=303,
        )
    return RedirectResponse(
        url="/admin/security-monitor/alarms?ok=" + quote("Alarm onaylandı"),
        status_code=303,
    )


@router.post("/security-monitor/alarms/rules/{rule_id}/update")
def security_monitor_alarms_update_rule(
    rule_id: int,
    request: Request,
    threshold: int = Form(...),
    cooldown_minutes: int = Form(...),
    enabled: int = Form(0),
    channels: str = Form("email,in_app"),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Alarm kuralının eşik/cooldown/enabled/kanal ayarlarını güncelle."""
    from app.services.alarm_engine import update_rule
    row = update_rule(
        db, rule_id=rule_id, threshold=threshold,
        cooldown_minutes=cooldown_minutes, enabled=bool(enabled),
        channels=channels,
    )
    if row is None:
        return RedirectResponse(
            url="/admin/security-monitor/alarms?err=" + quote("Kural yok"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="alarm_rule",
        target_id=rule_id,
        request=request,
        details={
            "key": row.key, "threshold": threshold,
            "cooldown_minutes": cooldown_minutes, "enabled": bool(enabled),
        },
    )
    return RedirectResponse(
        url="/admin/security-monitor/alarms?ok=" + quote("Kural güncellendi"),
        status_code=303,
    )


@router.get("/security-monitor/live")
def security_monitor_live(
    request: Request,
    user: User = Depends(require_super_admin),
):
    """Canlı akış sayfası (HTMX ile 5 sn'de bir partial poll)."""
    return templates.TemplateResponse(
        "admin/security_monitor_live.html",
        {"request": request, "user": user},
    )


@router.get("/security-monitor/live/feed")
def security_monitor_live_feed(
    request: Request,
    since_seconds: int = 600,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """HTMX partial: son N saniye akışı (audit + alarm karışık)."""
    from app.services.alarm_engine import live_event_stream
    items = live_event_stream(db, since_seconds=since_seconds, limit=80)
    return templates.TemplateResponse(
        "admin/_live_feed.html",
        {"request": request, "items": items},
    )


@router.get("/security-monitor/sessions")
def security_monitor_sessions(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Oturum + IP alt sayfası (11.K.2 öncüsü) — aktif oturumlar, şüpheli IP'ler,
    24h fail bucket'ları, manuel IP blok formu, uzaktan oturum sonlandırma,
    aktif sahte oturumlar (impersonate)."""
    from app.services.security_monitor import (
        get_security_dashboard_data,
        humanize_ago,
    )
    from app.services.impersonation import list_active as list_active_impersonations
    from app.models import (
        BLOCK_REASON_LABELS_TR,
        TERMINATION_REASON_LABELS_TR,
    )
    data = get_security_dashboard_data(db)
    data["active_impersonations"] = list_active_impersonations(db)
    return templates.TemplateResponse(
        "admin/security_monitor_sessions.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "termination_reason_labels": TERMINATION_REASON_LABELS_TR,
            "block_reason_labels": BLOCK_REASON_LABELS_TR,
            "humanize_ago": humanize_ago,
        },
    )


@router.get("/security-monitor/system")
def security_monitor_system(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sistem hata izleme kamerası (11.E).
    Exception grouping (Sentry-tarzı) + slow request + endpoint başına error rate."""
    from app.services.error_capture import get_system_health_data, humanize_ago
    data = get_system_health_data(db)
    return templates.TemplateResponse(
        "admin/security_monitor_system.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "humanize_ago": humanize_ago,
        },
    )


@router.post("/security-monitor/system/{error_id}/resolve")
def security_monitor_system_resolve(
    error_id: int,
    request: Request,
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Hata grubunu resolved olarak işaretle."""
    from app.services.error_capture import resolve_error
    row = resolve_error(
        db, error_id=error_id, resolved_by_user_id=user.id, note=note
    )
    if row is None:
        return RedirectResponse(
            url="/admin/security-monitor/system?err=" + quote("Hata kaydı yok"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="error_event",
        target_id=error_id,
        request=request,
        details={"action": "resolve", "signature": row.signature, "note": (note or "")[:200]},
    )
    return RedirectResponse(
        url="/admin/security-monitor/system?ok=" + quote("Hata çözüldü"),
        status_code=303,
    )


@router.get("/security-monitor/notifications")
def security_monitor_notifications(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Bildirim teslimat sağlık paneli (11.D)."""
    from app.services.notification_health import get_health_data
    from app.models import NOTIFICATION_KIND_LABELS

    data = get_health_data(db)
    return templates.TemplateResponse(
        "admin/security_monitor_notifications.html",
        {
            "request": request,
            "user": user,
            "data": data,
            "notification_kind_labels": NOTIFICATION_KIND_LABELS,
        },
    )


@router.get("/security-monitor/abuse")
def security_monitor_abuse(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
    only_open: int = 1,
    kind: str | None = None,
):
    """Kötüye kullanım (abuse) sinyalleri panosu (11.C).

    Bir öğretmenin toplu davet, bir kurumun bildirim üretim hızı, aynı cihazdan
    çoklu hesap, toplu unsubscribe gibi kalıpları gösterir.
    """
    from app.services.abuse_detection import list_signals, open_signal_count
    from app.services.abuse_remediation import ACTION_BUTTON_LABELS_TR
    from app.models import (
        ABUSE_KIND_DESCRIPTIONS_TR,
        ABUSE_KIND_LABELS_TR,
        ABUSE_SEVERITY_BADGE_COLOR,
        ABUSE_SEVERITY_LABELS_TR,
    )

    signals = list_signals(db, only_open=bool(only_open), kind=kind, limit=200)
    open_count = open_signal_count(db)
    return templates.TemplateResponse(
        "admin/security_monitor_abuse.html",
        {
            "request": request,
            "user": user,
            "signals": signals,
            "open_count": open_count,
            "filter_only_open": bool(only_open),
            "filter_kind": kind,
            "kind_labels": ABUSE_KIND_LABELS_TR,
            "kind_descriptions": ABUSE_KIND_DESCRIPTIONS_TR,
            "severity_labels": ABUSE_SEVERITY_LABELS_TR,
            "severity_colors": ABUSE_SEVERITY_BADGE_COLOR,
            "action_button_labels": ACTION_BUTTON_LABELS_TR,
        },
    )


@router.post("/security-monitor/abuse/scan")
def security_monitor_abuse_scan(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Anlık tarama: tüm dedektörleri çalıştırır, sinyalleri upsert eder."""
    from app.services.abuse_detection import run_all
    summary = run_all(db)
    total = sum(summary.values())
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="abuse_scan",
        request=request,
        details={"manual_scan": True, "summary": summary, "total_hits": total},
    )
    msg = f"Tarama tamam — {total} sinyal değerlendirildi"
    return RedirectResponse(
        url="/admin/security-monitor/abuse?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/security-monitor/abuse/{signal_id}/resolve")
def security_monitor_abuse_resolve(
    signal_id: int,
    request: Request,
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sinyali resolved olarak işaretle."""
    from app.services.abuse_detection import resolve_signal
    row = resolve_signal(
        db, signal_id=signal_id, resolved_by_user_id=user.id, note=note
    )
    if row is None:
        return RedirectResponse(
            url="/admin/security-monitor/abuse?err=" + quote("Sinyal bulunamadı"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="abuse_signal",
        target_id=signal_id,
        request=request,
        details={"action": "resolve", "kind": row.kind, "note": (note or "")[:200]},
    )
    return RedirectResponse(
        url="/admin/security-monitor/abuse?ok=" + quote("Sinyal çözüldü"),
        status_code=303,
    )


@router.post("/security-monitor/abuse/{signal_id}/remediate")
def security_monitor_abuse_remediate(
    signal_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Sinyal türüne göre toplu aksiyon uygula (11.C+).

    mass_invitation → davetleri iptal
    mass_notification → bekleyen bildirimleri SUPPRESSED
    multi_account_same_device → eşleşen aktif oturumları kapat
    unsubscribe_spike → otomatik aksiyon yok (manuel inceleme)
    """
    from app.services.abuse_remediation import auto_remediate_signal

    result = auto_remediate_signal(
        db, signal_id=signal_id, by_user_id=user.id, autocommit=True
    )
    if not result.ok:
        return RedirectResponse(
            url="/admin/security-monitor/abuse?err="
            + quote(f"Aksiyon yapılamadı: {result.note}"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.ABUSE_REMEDIATION,
        actor_id=user.id,
        target_type="abuse_signal",
        target_id=signal_id,
        request=request,
        details={
            "kind": result.kind,
            "action": result.action,
            "affected_count": result.affected_count,
            "note": result.note[:200],
        },
    )
    msg = f"{result.note} (sinyal otomatik çözüldü)"
    return RedirectResponse(
        url="/admin/security-monitor/abuse?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/security-monitor/impersonations/{imp_id}/end")
def security_monitor_end_impersonation(
    imp_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Başka bir admin'in aktif sahte oturumunu uzaktan sonlandır.

    Kullanım: oturum sahibi admin uzakta veya rapor uyarıcı; başka süper admin
    panodan kapatır. ImpersonationSession.end_reason="revoked" + IMPERSONATE_REVOKED audit.
    """
    from app.services.impersonation import end_session as _end_imp
    row = _end_imp(
        db, session_id=imp_id, end_reason="revoked", ended_by_user_id=user.id
    )
    if row is None:
        return RedirectResponse(
            url="/admin/security-monitor?err=" + quote("Oturum bulunamadı"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.IMPERSONATE_REVOKED,
        actor_id=user.id,
        target_type="user",
        target_id=row.target_user_id,
        request=request,
        details={
            "impersonation_id": imp_id,
            "original_actor_id": row.actor_user_id,
        },
    )
    return RedirectResponse(
        url="/admin/security-monitor?ok=" + quote("Sahte oturum kapatıldı"),
        status_code=303,
    )


@router.post("/security-monitor/sessions/{session_token}/revoke")
def security_monitor_revoke_session(
    session_token: str,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Süper admin uzaktan oturum sonlandır."""
    from app.services.security_monitor import revoke_session_by_token
    ok = revoke_session_by_token(db, session_token=session_token, by_user_id=user.id)
    if not ok:
        return RedirectResponse(
            url="/admin/security-monitor?err=" + quote("Oturum bulunamadı"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="active_session",
        request=request,
        details={"action": "revoke", "session_token_prefix": session_token[:8]},
    )
    return RedirectResponse(
        url="/admin/security-monitor?ok=" + quote("Oturum kapatıldı"),
        status_code=303,
    )


@router.post("/security-monitor/ips/block")
def security_monitor_block_ip(
    request: Request,
    ip: str = Form(...),
    hours: int = Form(1),
    note: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Manuel IP blok ekle."""
    from app.services.security_monitor import block_ip_manual
    ip_clean = (ip or "").strip()[:64]
    if not ip_clean:
        return RedirectResponse(
            url="/admin/security-monitor?err=" + quote("IP boş olamaz"),
            status_code=303,
        )
    hours = max(1, min(int(hours or 1), 24 * 30))
    block_ip_manual(
        db, ip=ip_clean, hours=hours, note=note, by_user_id=user.id
    )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="suspicious_ip",
        request=request,
        details={"action": "block", "ip": ip_clean, "hours": hours, "note": note[:100]},
    )
    return RedirectResponse(
        url="/admin/security-monitor?ok=" + quote(f"IP engellendi: {ip_clean}"),
        status_code=303,
    )


@router.post("/security-monitor/ips/unblock")
def security_monitor_unblock_ip(
    request: Request,
    ip: str = Form(...),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """IP blok'unu kaldır."""
    from app.services.security_monitor import unblock_ip
    ip_clean = (ip or "").strip()[:64]
    ok = unblock_ip(db, ip=ip_clean)
    if not ok:
        return RedirectResponse(
            url="/admin/security-monitor?err=" + quote("IP kaydı yok"),
            status_code=303,
        )
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="suspicious_ip",
        request=request,
        details={"action": "unblock", "ip": ip_clean},
    )
    return RedirectResponse(
        url="/admin/security-monitor?ok=" + quote(f"IP serbest: {ip_clean}"),
        status_code=303,
    )


# ============================================================================
# Sprint E.1 — Toplu Kampanya (Faz E Seviye 2)
# ============================================================================


@router.get("/revenue/campaigns")
def revenue_campaigns_list(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Kampanya listesi — DRAFT/RUNNING/COMPLETED hepsi tek listede."""
    from app.models import (
        CAMPAIGN_SEGMENT_LABELS_TR,
        CAMPAIGN_STATUS_COLORS,
        CAMPAIGN_STATUS_LABELS_TR,
    )
    from app.services.campaigns import (
        campaign_stats,
        list_campaigns,
        sync_recipient_statuses,
    )
    campaigns = list_campaigns(db, limit=100)
    # Aktif kampanyaların funnel'ını otomatik sync et
    stats: dict[int, dict] = {}
    for c in campaigns:
        try:
            sync_recipient_statuses(db, campaign_id=c.id)
        except Exception:
            pass
        stats[c.id] = campaign_stats(db, campaign_id=c.id)
    return templates.TemplateResponse(
        "admin/campaigns_list.html",
        {
            "request": request,
            "user": user,
            "campaigns": campaigns,
            "stats": stats,
            "segment_labels": CAMPAIGN_SEGMENT_LABELS_TR,
            "status_labels": CAMPAIGN_STATUS_LABELS_TR,
            "status_colors": CAMPAIGN_STATUS_COLORS,
        },
    )


@router.get("/revenue/campaigns/new")
def revenue_campaigns_new(
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Yeni kampanya oluşturma formu."""
    from app.models import (
        CAMPAIGN_SEGMENT_DESCRIPTIONS,
        CAMPAIGN_SEGMENT_LABELS_TR,
        OFFER_KIND_ICONS,
        OFFER_KIND_LABELS_TR,
        CampaignSegment,
        OfferKind,
    )
    return templates.TemplateResponse(
        "admin/campaign_form.html",
        {
            "request": request,
            "user": user,
            "segments": list(CampaignSegment),
            "segment_labels": CAMPAIGN_SEGMENT_LABELS_TR,
            "segment_descriptions": CAMPAIGN_SEGMENT_DESCRIPTIONS,
            "offer_kinds": list(OfferKind),
            "offer_kind_labels": OFFER_KIND_LABELS_TR,
            "offer_kind_icons": OFFER_KIND_ICONS,
        },
    )


@router.post("/revenue/campaigns/preview")
def revenue_campaigns_preview(
    request: Request,
    segment: str = Form(...),
    filter_plan: str = Form(""),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """HTMX partial: belirli segment için kaç kurum hedeflenir + ilk 10 isim."""
    from app.models import CampaignSegment
    try:
        seg = CampaignSegment(segment)
    except ValueError:
        return templates.TemplateResponse(
            "admin/_campaign_preview.html",
            {"request": request, "count": 0, "preview": [],
             "error": "Geçersiz segment"},
        )
    from app.services.campaigns import preview_segment
    owners = preview_segment(
        db, segment=seg,
        filter_plan=filter_plan.strip() or None,
    )
    preview = owners[:10]
    inst_count = sum(1 for o in owners if o.owner_type == "institution")
    user_count = sum(1 for o in owners if o.owner_type == "user")
    return templates.TemplateResponse(
        "admin/_campaign_preview.html",
        {
            "request": request,
            "count": len(owners),
            "preview": preview,
            "inst_count": inst_count,
            "user_count": user_count,
            "segment": segment,
            "error": None,
        },
    )


@router.post("/revenue/campaigns/create")
def revenue_campaigns_create(
    request: Request,
    name: str = Form(...),
    segment: str = Form(...),
    variant_a_kind: str = Form(...),
    variant_a_title: str = Form(...),
    description: str = Form(""),
    admin_note: str = Form(""),
    filter_plan: str = Form(""),
    variant_a_value: str = Form(""),
    variant_a_duration_months: str = Form(""),
    variant_a_new_plan: str = Form(""),
    variant_a_public_message: str = Form(""),
    has_variant_b: str = Form(""),
    variant_b_kind: str = Form(""),
    variant_b_title: str = Form(""),
    variant_b_value: str = Form(""),
    variant_b_duration_months: str = Form(""),
    variant_b_new_plan: str = Form(""),
    variant_b_public_message: str = Form(""),
    offer_expires_in_days: int = Form(14),
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import create_campaign

    def _to_float(s: str) -> float | None:
        s = (s or "").strip()
        if not s:
            return None
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None

    def _to_int(s: str) -> int | None:
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None

    has_b = bool(has_variant_b)
    camp = create_campaign(
        db,
        name=name,
        segment=segment,
        segment_filter_plan=filter_plan.strip() or None,
        variant_a_kind=variant_a_kind,
        variant_a_title=variant_a_title,
        by_user_id=user.id,
        description=description.strip() or None,
        admin_note=admin_note.strip() or None,
        variant_a_value=_to_float(variant_a_value),
        variant_a_duration_months=_to_int(variant_a_duration_months),
        variant_a_new_plan=variant_a_new_plan.strip() or None,
        variant_a_public_message=variant_a_public_message.strip() or None,
        has_variant_b=has_b,
        variant_b_kind=variant_b_kind.strip() or None,
        variant_b_title=variant_b_title.strip() or None,
        variant_b_value=_to_float(variant_b_value),
        variant_b_duration_months=_to_int(variant_b_duration_months),
        variant_b_new_plan=variant_b_new_plan.strip() or None,
        variant_b_public_message=variant_b_public_message.strip() or None,
        offer_expires_in_days=int(offer_expires_in_days or 14),
    )
    if camp is None:
        return RedirectResponse(
            url="/admin/revenue/campaigns/new?err="
                + quote("Kampanya oluşturulamadı (geçersiz segment veya teklif türü)"),
            status_code=303,
        )
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=camp.id,
        request=request,
        details={"action": "create", "segment": segment,
                  "name": name, "has_variant_b": has_b},
    )
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{camp.id}?ok="
            + quote("Kampanya taslak olarak kaydedildi"),
        status_code=303,
    )


@router.get("/revenue/campaigns/{campaign_id}")
def revenue_campaign_detail(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Tek kampanya detay sayfası — bilgi + funnel + recipient liste."""
    from app.models import (
        CAMPAIGN_SEGMENT_LABELS_TR,
        CAMPAIGN_STATUS_COLORS,
        CAMPAIGN_STATUS_LABELS_TR,
        Campaign,
        CampaignRecipient,
        Institution,
        OFFER_KIND_LABELS_TR,
        RECIPIENT_STATUS_LABELS_TR,
    )
    from app.services.campaigns import campaign_stats, sync_recipient_statuses
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        raise HTTPException(status_code=404, detail="Kampanya bulunamadı")
    sync_recipient_statuses(db, campaign_id=campaign_id)
    stats = campaign_stats(db, campaign_id=campaign_id)
    recips = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .order_by(CampaignRecipient.id.desc())
        .limit(200)
        .all()
    )
    inst_ids = [r.institution_id for r in recips
                if r.owner_type == "institution" and r.institution_id]
    user_ids = [r.user_id for r in recips
                if r.owner_type == "user" and r.user_id]
    inst_map = {}
    if inst_ids:
        inst_map = {
            i.id: i for i in db.query(Institution).filter(
                Institution.id.in_(set(inst_ids))
            ).all()
        }
    users_map = {}
    if user_ids:
        users_map = {
            u.id: u for u in db.query(User).filter(
                User.id.in_(set(user_ids))
            ).all()
        }
    return templates.TemplateResponse(
        "admin/campaign_detail.html",
        {
            "request": request,
            "user": user,
            "campaign": camp,
            "stats": stats,
            "recipients": recips,
            "inst_map": inst_map,
            "users_map": users_map,
            "segment_labels": CAMPAIGN_SEGMENT_LABELS_TR,
            "status_labels": CAMPAIGN_STATUS_LABELS_TR,
            "status_colors": CAMPAIGN_STATUS_COLORS,
            "offer_kind_labels": OFFER_KIND_LABELS_TR,
            "recipient_status_labels": RECIPIENT_STATUS_LABELS_TR,
        },
    )


@router.post("/revenue/campaigns/{campaign_id}/launch")
def revenue_campaign_launch(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import launch_campaign
    result = launch_campaign(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id,
        request=request,
        details={"action": "launch", "result": result},
    )
    if not result.get("ok"):
        return RedirectResponse(
            url=f"/admin/revenue/campaigns/{campaign_id}?err="
                + quote(f"Başlatılamadı: {result.get('error')}"),
            status_code=303,
        )
    msg = (
        f"Kampanya başlatıldı — {result['sent']}/{result['recipient_count']} "
        f"e-posta gönderildi"
        + (f" ({result['errors']} hata)" if result.get("errors") else "")
    )
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{campaign_id}?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/campaigns/{campaign_id}/pause")
def revenue_campaign_pause(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import pause_campaign
    r = pause_campaign(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id,
        request=request,
        details={"action": "pause", "ok": r.get("ok")},
    )
    key = "ok" if r.get("ok") else "err"
    msg = "Kampanya duraklatıldı" if r.get("ok") else f"Hata: {r.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{campaign_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/campaigns/{campaign_id}/resume")
def revenue_campaign_resume(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import resume_campaign
    r = resume_campaign(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id,
        request=request,
        details={"action": "resume", "ok": r.get("ok")},
    )
    key = "ok" if r.get("ok") else "err"
    msg = "Kampanya devam ediyor" if r.get("ok") else f"Hata: {r.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{campaign_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/campaigns/{campaign_id}/complete")
def revenue_campaign_complete(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import complete_campaign
    r = complete_campaign(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id,
        request=request,
        details={"action": "complete", "ok": r.get("ok")},
    )
    key = "ok" if r.get("ok") else "err"
    msg = "Kampanya tamamlandı" if r.get("ok") else f"Hata: {r.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{campaign_id}?{key}=" + quote(msg),
        status_code=303,
    )


@router.post("/revenue/campaigns/{campaign_id}/cancel")
def revenue_campaign_cancel(
    campaign_id: int,
    request: Request,
    user: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    from app.services.campaigns import cancel_campaign
    r = cancel_campaign(db, campaign_id=campaign_id)
    log_action(
        db, action=AuditAction.USER_UPDATE, actor_id=user.id,
        target_type="campaign", target_id=campaign_id,
        request=request,
        details={"action": "cancel", "ok": r.get("ok")},
    )
    key = "ok" if r.get("ok") else "err"
    msg = "Kampanya iptal edildi" if r.get("ok") else f"Hata: {r.get('error')}"
    return RedirectResponse(
        url=f"/admin/revenue/campaigns/{campaign_id}?{key}=" + quote(msg),
        status_code=303,
    )
