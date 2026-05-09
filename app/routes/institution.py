"""INSTITUTION_ADMIN paneli — kurum yöneticisi için roster + agrega.

GİZLİLİK KURALI (2026-05-08 mimari kararı):
Kurum yöneticisi öğretmenin DETAY verisini (program, notlar, öğrenci günlüğü)
GÖREMEZ. Sadece toplu istatistikleri görür. Bu route'lar /teacher/* veya
/student/* route'larına link sağlamamalıdır.

Yetki: require_institution_admin (institution_id zorunlu).
Tenant isolation: tüm sorgular institution_id == admin.institution_id ile filtreli.
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_institution_admin
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
from app.services.auth_security import generate_strong_password
from app.services.institution_view import (
    institution_aggregate,
    institution_roster,
    teacher_summaries,
)
from app.services.security import hash_password
from app.templating import templates


router = APIRouter(prefix="/institution")


# Eski yardımcı kaldırıldı — generate_strong_password (auth_security.py)
# kullanılır; rol-bazlı güçlü şifre üretir, must_change_password=True ile
# birlikte kullanıcının ilk girişte kendi şifresini belirlemesini zorunlu kılar.


@router.get("")
def institution_dashboard(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli özet dashboard."""
    from app.services.risk_analysis import bulk_risk_assessment, filter_at_risk
    inst = db.get(Institution, user.institution_id)
    if not inst or not inst.is_active:
        raise HTTPException(status_code=403, detail="Kurum aktif değil")
    agg = institution_aggregate(db, institution_id=inst.id)
    summaries = teacher_summaries(db, institution_id=inst.id)

    # Risk paneli özet — kurumdaki tüm aktif öğrencileri skorla
    teacher_ids = [s.teacher.id for s in summaries]
    at_risk_count = 0
    at_risk_critical = 0
    if teacher_ids:
        active_students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
            )
            .all()
        )
        risk_assessments = bulk_risk_assessment(db, students=active_students)
        at_risk = filter_at_risk(risk_assessments, min_level="medium")
        at_risk_count = len(at_risk)
        at_risk_critical = sum(1 for a in at_risk if a.level == "critical")

    # Pasif öğretmen sayısı — son 7 günde hiç aktivite yok
    from app.services.teacher_activity import inactive_teachers
    inactives = inactive_teachers(db, institution_id=user.institution_id, days=7)
    inactive_teacher_count = len(inactives)
    inactive_teacher_names = [t.full_name for t in inactives[:3]]   # en fazla 3 isim

    return templates.TemplateResponse(
        "institution/dashboard.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "agg": agg,
            "teacher_summaries": summaries,
            "at_risk_count": at_risk_count,
            "at_risk_critical": at_risk_critical,
            "inactive_teacher_count": inactive_teacher_count,
            "inactive_teacher_names": inactive_teacher_names,
        },
    )


@router.get("/teachers")
def list_teachers(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Kurumdaki öğretmenler — agrega tabloda göster."""
    inst = db.get(Institution, user.institution_id)
    summaries = teacher_summaries(db, institution_id=user.institution_id)
    return templates.TemplateResponse(
        "institution/teachers_list.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "teacher_summaries": summaries,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/teachers")
def create_teacher(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum yöneticisi yeni öğretmen ekler.

    Güvenlik: şifre admin tarafından belirlenmez — sistem güçlü rastgele
    üretir, öğretmen ilk girişte kendi şifresini belirlemek zorunda
    (must_change_password=True). Ücretli üyelik akışında bu yer davetiye
    token'ı + ödeme akışı ile değiştirilecek.
    """
    full_name_clean = (full_name or "").strip()
    email_clean = (email or "").strip().lower()
    if not full_name_clean or not email_clean:
        return RedirectResponse(
            url="/institution/teachers?err=" + quote("Ad ve e-posta zorunlu."),
            status_code=303,
        )
    if db.query(User).filter(User.email == email_clean).first():
        return RedirectResponse(
            url="/institution/teachers?err=" + quote("Bu e-posta zaten kayıtlı."),
            status_code=303,
        )
    pwd = generate_strong_password(UserRole.TEACHER)
    new_teacher = User(
        email=email_clean,
        password_hash=hash_password(pwd),
        full_name=full_name_clean,
        role=UserRole.TEACHER,
        institution_id=user.institution_id,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=True,
    )
    db.add(new_teacher)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=user.id,
        target_type="user",
        target_id=new_teacher.id,
        request=request,
        details={
            "email": email_clean,
            "role": "teacher",
            "institution_id": user.institution_id,
            "created_by_role": "institution_admin",
            "temp_password_issued": True,
        },
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/institution/teachers?ok=" + quote(
            f"{full_name_clean} eklendi — geçici şifre: {pwd} "
            f"(ilk girişte kendi şifresini belirleyecek)"
        ),
        status_code=303,
    )


@router.post("/teachers/{teacher_id}/deactivate")
def deactivate_teacher(
    teacher_id: int,
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Bir öğretmeni pasifleştir (giriş yapamaz). Tam silme yetkisi YOK —
    veri kaybını önlemek için. Tam silme işlemi süper admin'e bırakılır.
    """
    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")
    teacher.is_active = False
    log_action(
        db,
        action=AuditAction.USER_DEACTIVATE,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={"performed_by_role": "institution_admin"},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/institution/teachers?ok=" + quote(
            f"{teacher.full_name} pasifleştirildi (verisi korundu)."
        ),
        status_code=303,
    )


@router.post("/teachers/{teacher_id}/activate")
def activate_teacher(
    teacher_id: int,
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Pasif öğretmeni geri aktif et."""
    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=404)
    teacher.is_active = True
    log_action(
        db,
        action=AuditAction.USER_UPDATE,
        actor_id=user.id,
        target_type="user",
        target_id=teacher.id,
        request=request,
        details={"action": "activate", "performed_by_role": "institution_admin"},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/institution/teachers?ok=" + quote(f"{teacher.full_name} aktifleştirildi."),
        status_code=303,
    )


@router.get("/teachers/{teacher_id}")
def teacher_card(
    teacher_id: int,
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Öğretmen kart — sadece roster ve agrega. Program/not GÖZÜKMEZ.

    Bu sayfa /teacher/students/X gibi öğretmen detay sayfalarına link İÇERMEZ.
    Öğrenci listesi sadece ad + sınıf + haftalık tamamlama oranı şeklindedir.
    """
    teacher = (
        db.query(User)
        .filter(
            User.id == teacher_id,
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
        .first()
    )
    if not teacher:
        raise HTTPException(status_code=404, detail="Öğretmen bulunamadı")

    # Bu öğretmenin öğrencileri + haftalık özetleri
    from app.services.analytics import week_stats_for
    from datetime import date as _date
    today = _date.today()
    students = (
        db.query(User)
        .filter(User.role == UserRole.STUDENT, User.teacher_id == teacher.id)
        .order_by(User.full_name)
        .all()
    )
    student_rows = []
    total_planned = total_completed = 0
    for s in students:
        w = week_stats_for(db, s.id, today)
        rate = (
            int(round(100 * w.completed / w.planned)) if w.planned > 0 else None
        )
        student_rows.append({
            "student": s,
            "planned": w.planned,
            "completed": w.completed,
            "rate_pct": rate,
        })
        total_planned += w.planned
        total_completed += w.completed
    overall_rate = (
        int(round(100 * total_completed / total_planned)) if total_planned > 0 else None
    )

    return templates.TemplateResponse(
        "institution/teacher_card.html",
        {
            "request": request,
            "user": user,
            "teacher": teacher,
            "student_rows": student_rows,
            "total_planned": total_planned,
            "total_completed": total_completed,
            "overall_rate": overall_rate,
        },
    )


# ---------------------------- Davetiye yönetimi (Sprint 5) ----------------------------


@router.get("/invitations")
def list_invitations(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Bu kurumun davetiyelerini listele — tüm statüler."""
    invs = (
        db.query(Invitation)
        .filter(Invitation.institution_id == user.institution_id)
        .order_by(Invitation.created_at.desc())
        .all()
    )
    inst = db.get(Institution, user.institution_id)
    # Frontend tam URL'yi oluşturmak için origin lazım (dev'de localhost)
    origin = f"{request.url.scheme}://{request.url.netloc}"
    return templates.TemplateResponse(
        "institution/invitations.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "invitations": invs,
            "origin": origin,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/invitations")
def create_invitation(
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Yeni öğretmen davetiyesi üret. E-posta opsiyonel — boşsa "açık davetiye"
    olur (linki olan herkes kullanabilir, dolu olursa sadece o e-posta).

    NOT: Şu an pre-fill için email/name boş olabilir; signup formunda kullanıcı
    düzenleyebilir. İleride email zorunlu + email gönderme entegrasyonu.
    """
    full_name_clean = (full_name or "").strip() or None
    email_clean = (email or "").strip().lower() or None
    # E-posta zaten var mı kontrol — açık davetiye için skip
    if email_clean and db.query(User).filter(User.email == email_clean).first():
        return RedirectResponse(
            url="/institution/invitations?err=" + quote(
                f"{email_clean} zaten kayıtlı — davetiye gerekmez."
            ),
            status_code=303,
        )

    # Stage 8 — kuota kontrolü (öğretmen davet ediliyor)
    inst = db.get(Institution, user.institution_id)
    if inst is not None:
        from app.services.quotas import check_quota_for_create, QuotaExceeded
        try:
            check_quota_for_create(db, institution=inst, quota_key="teachers")
        except QuotaExceeded as e:
            return RedirectResponse(
                url="/institution/invitations?err=" + quote(e.message),
                status_code=303,
            )

    token = secrets.token_urlsafe(32)
    inv = Invitation(
        token=token,
        email=email_clean,
        full_name=full_name_clean,
        role=UserRole.TEACHER,
        institution_id=user.institution_id,
        created_by_user_id=user.id,
        expires_at=invitation_default_expiry(),
    )
    db.add(inv)
    db.flush()
    log_action(
        db,
        action=AuditAction.USER_CREATE,  # davetiye = potansiyel user oluşturma
        actor_id=user.id,
        target_type="invitation",
        target_id=inv.id,
        request=request,
        details={
            "type": "invitation_created",
            "role": "teacher",
            "institution_id": user.institution_id,
            "email": email_clean,
        },
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/institution/invitations?ok=" + quote(
            f"Davetiye oluşturuldu — link aşağıdaki tabloda. {('E-posta: ' + email_clean) if email_clean else 'Açık davetiye'}"
        ),
        status_code=303,
    )


@router.post("/invitations/{invitation_id}/revoke")
def revoke_invitation(
    invitation_id: int,
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Bekleyen davetiyeyi iptal et."""
    inv = (
        db.query(Invitation)
        .filter(
            Invitation.id == invitation_id,
            Invitation.institution_id == user.institution_id,
        )
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404)
    if not inv.is_usable:
        return RedirectResponse(
            url="/institution/invitations?err=" + quote(
                "Bu davetiye zaten kullanılmış, süresi geçmiş veya iptal edilmiş."
            ),
            status_code=303,
        )
    inv.revoked_at = datetime.now(timezone.utc)
    inv.revoked_by_user_id = user.id
    log_action(
        db,
        action=AuditAction.USER_DEACTIVATE,
        actor_id=user.id,
        target_type="invitation",
        target_id=inv.id,
        request=request,
        details={"type": "invitation_revoked"},
        autocommit=False,
    )
    db.commit()
    return RedirectResponse(
        url="/institution/invitations?ok=" + quote("Davetiye iptal edildi."),
        status_code=303,
    )


@router.get("/activity-heatmap")
def activity_heatmap_panel(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    weeks: int = 4,
):
    """Öğretmen aktivite ısı haritası — son N hafta (4 default, 12 max-istek).

    Aktivite kaynakları: login + task oluşturma + öğretmen-veli notu.
    Hücre rengi 0..1 skoruna göre yeşilin tonunu değiştirir.
    """
    from app.services.teacher_activity import teacher_activity_heatmap, INACTIVE_DAYS
    inst = db.get(Institution, user.institution_id)
    if not inst:
        raise HTTPException(status_code=403)

    # 4 veya 12 hafta — kötü inputs için 4'e düş
    if weeks not in (4, 12):
        weeks = 4

    heatmaps = teacher_activity_heatmap(
        db, institution_id=user.institution_id, weeks=weeks,
    )
    inactive_count = sum(1 for h in heatmaps if h.is_inactive)

    return templates.TemplateResponse(
        "institution/activity_heatmap.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "heatmaps": heatmaps,
            "weeks": weeks,
            "days_count": weeks * 7,
            "inactive_threshold_days": INACTIVE_DAYS,
            "inactive_count": inactive_count,
        },
    )


@router.get("/admin-digest")
def admin_digest_archive(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    """Haftalık yönetici özetleri arşivi — son 12 hafta + manuel tetik butonu."""
    from app.models import AdminWeeklyDigest
    inst = db.get(Institution, user.institution_id)
    digests = (
        db.query(AdminWeeklyDigest)
        .filter(AdminWeeklyDigest.institution_id == user.institution_id)
        .order_by(AdminWeeklyDigest.week_start_date.desc())
        .limit(12)
        .all()
    )
    return templates.TemplateResponse(
        "institution/admin_digest_list.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "digests": digests,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/admin-digest/send-now")
def admin_digest_send_now(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Manuel tetik — bu hafta için özet üret + e-posta gönder.

    Idempotency: aynı hafta için zaten varsa, force=True ile yeniden gönderir
    (test/güncelleme amaçlı). Çoklu tetik audit log'da görünür.
    """
    from urllib.parse import quote
    from app.services.admin_digest import send_admin_weekly_digest
    inst = db.get(Institution, user.institution_id)
    try:
        digest = send_admin_weekly_digest(
            db, institution=inst, force=True,
        )
        msg = (
            f"Haftalık özet üretildi. Durum: {digest.send_status}, "
            f"alıcı: {digest.recipient_count}"
        )
        return RedirectResponse(
            url="/institution/admin-digest?ok=" + quote(msg),
            status_code=303,
        )
    except Exception as e:
        return RedirectResponse(
            url="/institution/admin-digest?err=" + quote(f"Hata: {type(e).__name__}: {e}"),
            status_code=303,
        )


@router.get("/admin-digest/{digest_id}")
def admin_digest_detail(
    digest_id: int,
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Tek bir özet kaydının detayı — payload'ı snapshot olarak göster."""
    import json as _json
    from app.models import AdminWeeklyDigest
    digest = (
        db.query(AdminWeeklyDigest)
        .filter(
            AdminWeeklyDigest.id == digest_id,
            AdminWeeklyDigest.institution_id == user.institution_id,
        )
        .first()
    )
    if not digest:
        raise HTTPException(status_code=404)
    payload = {}
    if digest.payload_json:
        try:
            payload = _json.loads(digest.payload_json)
        except (ValueError, TypeError):
            pass
    return templates.TemplateResponse(
        "institution/admin_digest_detail.html",
        {
            "request": request,
            "user": user,
            "institution": db.get(Institution, user.institution_id),
            "digest": digest,
            "payload": payload,
        },
    )


@router.get("/cohorts/print")
def cohort_panel_print(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Tüm 4 kohort tipini birleşik tek A4 landscape sayfada — yazdırılabilir."""
    from datetime import date as _date
    from app.services.cohort_analysis import (
        cohort_by_curriculum,
        cohort_by_exam_target,
        cohort_by_grade,
        cohort_by_track,
        institution_week_over_week,
    )
    inst = db.get(Institution, user.institution_id)
    if not inst:
        raise HTTPException(status_code=403)

    all_cohorts = [
        {"label": "Sınıf seviyesi", "cohorts": cohort_by_grade(db, institution_id=inst.id)},
        {"label": "Alan (11+/Mezun)", "cohorts": cohort_by_track(db, institution_id=inst.id)},
        {"label": "Müfredat modeli", "cohorts": cohort_by_curriculum(db, institution_id=inst.id)},
        {"label": "Hedef sınav", "cohorts": cohort_by_exam_target(db, institution_id=inst.id)},
    ]
    wow = institution_week_over_week(db, institution_id=inst.id)

    return templates.TemplateResponse(
        "institution/cohorts_print.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "all_cohorts": all_cohorts,
            "wow": wow,
            "today": _date.today(),
        },
    )


@router.get("/at-risk/print")
def at_risk_print(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Risk altındaki öğrenciler — yazdırılabilir A4 portrait."""
    from datetime import date as _date
    from app.services.risk_analysis import (
        bulk_risk_assessment,
        filter_at_risk,
        get_active_mutes_for_students,
    )
    inst = db.get(Institution, user.institution_id)
    if not inst:
        raise HTTPException(status_code=403)

    teacher_ids_q = (
        db.query(User.id).filter(
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
    )
    teacher_ids = [t[0] for t in teacher_ids_q.all()]

    students = []
    if teacher_ids:
        students = (
            db.query(User)
            .filter(
                User.role == UserRole.STUDENT,
                User.teacher_id.in_(teacher_ids),
                User.is_active.is_(True),
            )
            .order_by(User.full_name)
            .all()
        )

    teacher_map = {}
    if teacher_ids:
        for t in db.query(User).filter(User.id.in_(teacher_ids)).all():
            teacher_map[t.id] = t

    assessments = bulk_risk_assessment(db, students=students)
    at_risk = filter_at_risk(assessments, min_level="medium")
    counts = {
        "critical": sum(1 for a in at_risk if a.level == "critical"),
        "high":     sum(1 for a in at_risk if a.level == "high"),
        "medium":   sum(1 for a in at_risk if a.level == "medium"),
    }

    return templates.TemplateResponse(
        "institution/at_risk_print.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "at_risk": at_risk,
            "teacher_map": teacher_map,
            "counts": counts,
            "today": _date.today(),
        },
    )


@router.get("/activity-heatmap/print")
def activity_heatmap_print(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    weeks: int = 4,
):
    """Öğretmen aktivite haritası — yazdırılabilir A4 landscape."""
    from datetime import date as _date
    from app.services.teacher_activity import (
        teacher_activity_heatmap,
        INACTIVE_DAYS,
    )
    inst = db.get(Institution, user.institution_id)
    if not inst:
        raise HTTPException(status_code=403)
    if weeks not in (4, 12):
        weeks = 4
    heatmaps = teacher_activity_heatmap(
        db, institution_id=user.institution_id, weeks=weeks,
    )
    inactive_count = sum(1 for h in heatmaps if h.is_inactive)

    return templates.TemplateResponse(
        "institution/activity_heatmap_print.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "heatmaps": heatmaps,
            "weeks": weeks,
            "days_count": weeks * 7,
            "inactive_threshold_days": INACTIVE_DAYS,
            "inactive_count": inactive_count,
            "today": _date.today(),
        },
    )


@router.get("/cohorts")
def cohort_panel(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    tab: str = "grade",
):
    """Kohort karşılaştırma — sınıf / alan / müfredat / hedef sınav.

    `tab` query param ile aktif sekme seçilir; default 'grade'.
    """
    from app.services.cohort_analysis import (
        cohort_by_curriculum,
        cohort_by_exam_target,
        cohort_by_grade,
        cohort_by_track,
        institution_week_over_week,
    )
    inst = db.get(Institution, user.institution_id)
    if not inst:
        raise HTTPException(status_code=403)

    # Geçerli tab — bilinmiyorsa grade
    valid_tabs = {"grade", "track", "curriculum", "exam_target"}
    if tab not in valid_tabs:
        tab = "grade"

    # Sadece aktif tab'ın verisini hesapla — performans için
    cohort_fns = {
        "grade": cohort_by_grade,
        "track": cohort_by_track,
        "curriculum": cohort_by_curriculum,
        "exam_target": cohort_by_exam_target,
    }
    cohorts = cohort_fns[tab](db, institution_id=user.institution_id)
    wow = institution_week_over_week(db, institution_id=user.institution_id)

    tab_labels = {
        "grade": "Sınıf",
        "track": "Alan",
        "curriculum": "Müfredat",
        "exam_target": "Hedef Sınav",
    }

    return templates.TemplateResponse(
        "institution/cohorts.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "active_tab": tab,
            "tab_labels": tab_labels,
            "cohorts": cohorts,
            "wow": wow,
        },
    )


# ---------------------------- Stage 8 — Kuota ----------------------------


@router.get("/quota")
def quota_dashboard(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumun aktif entity kuotaları — öğretmen / öğrenci / yönetici sayım+limit."""
    from app.services.quotas import get_quota_summary, PLAN_QUOTAS
    inst = db.get(Institution, user.institution_id)
    summary = get_quota_summary(db, institution=inst)
    return templates.TemplateResponse(
        "institution/quota_dashboard.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "summary": summary,
            "plan_quotas": PLAN_QUOTAS,
        },
    )


# ---------------------------- Stage 6 — Kullanım & krediler ----------------------------


@router.get("/usage")
def usage_dashboard(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurumun aylık kredi tüketimi paneli — bu ay X / Y kredi + kırılım + son eventler."""
    from app.models import USAGE_KIND_LABELS_TR
    from app.services.credits import (
        CreditOwner, current_period, daily_usage_series,
        get_or_create_account, recent_events, usage_breakdown_by_kind,
        PLAN_ALLOCATIONS, KIND_CREDITS,
    )
    inst = db.get(Institution, user.institution_id)
    owner = CreditOwner.for_institution(inst)
    period = current_period()
    account = get_or_create_account(db, owner=owner, period=period)
    db.commit()  # yeni satır oluştuysa kaydet

    breakdown = usage_breakdown_by_kind(db, owner=owner, period=period)
    series = daily_usage_series(db, owner=owner, days=30)
    events = recent_events(db, owner=owner, limit=50)

    return templates.TemplateResponse(
        "institution/usage_dashboard.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "account": account,
            "period": period,
            "breakdown": breakdown,
            "series": series,
            "events": events,
            "kind_labels": USAGE_KIND_LABELS_TR,
            "plan_allocations": PLAN_ALLOCATIONS,
            "kind_costs": KIND_CREDITS,
        },
    )


@router.get("/roster")
def roster(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
    teacher_id: str | None = None,
    grade: str | None = None,
):
    """Kurum altındaki tüm öğrenciler — basit filtreli liste."""
    rows = institution_roster(db, institution_id=user.institution_id)
    # Filtreler
    if teacher_id:
        try:
            tid = int(teacher_id)
            rows = [r for r in rows if r.student.teacher_id == tid]
        except ValueError:
            pass
    if grade:
        if grade.strip().lower() == "graduate":
            rows = [r for r in rows if r.student.is_graduate]
        else:
            try:
                g = int(grade)
                rows = [r for r in rows if r.student.grade_level == g]
            except ValueError:
                pass
    teachers = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
        .order_by(User.full_name)
        .all()
    )
    return templates.TemplateResponse(
        "institution/roster.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "teachers": teachers,
            "filter_teacher_id": teacher_id,
            "filter_grade": grade,
        },
    )
