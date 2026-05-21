"""At-risk öğrenci paneli — risk skoru sıralı liste, mute/unmute aksiyonları.

İki giriş noktası:
- /teacher/at-risk: öğretmen kendi öğrencilerinin risk panelini görür
  + 7 günlük yanlış-alarm sustur özelliği
- /institution/at-risk: kurum yöneticisi kurum geneli özetini görür
  (öğretmen-öğrenci eşlemesini gösterir, programa link YOK — gizlilik)

Skor + göstergeler `app/services/risk_analysis.py`'de hesaplanır.
Mute edilen öğrenciler default olarak gizlenir; "mute'lu olanlar dahil"
filter'ıyla görülebilir (öğretmen tarafında).
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_institution_admin, require_teacher
from app.models import (
    AtRiskMute,
    Institution,
    User,
    UserRole,
    at_risk_mute_default_expiry,
)
from app.services.risk_analysis import (
    bulk_risk_assessment,
    filter_at_risk,
    get_active_mutes,
    get_active_mutes_for_students,
)
from app.templating import templates


router = APIRouter()


# ---------------------------- Teacher panel ----------------------------


@router.get("/teacher/at-risk")
def teacher_at_risk_panel(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    show_muted: str | None = None,
    ok: str | None = None,
):
    """Öğretmenin kendi öğrencilerinin risk paneli.

    show_muted=1 ise muted öğrenciler de görünür (default gizli).
    """
    students = (
        db.query(User)
        .filter(
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        )
        .order_by(User.full_name)
        .all()
    )
    # NOT: pasif öğrenciler de listede görünür, sadece template'de silik
    # render edilir. Gerçek bildirim üreticileri (cron, event_triggers)
    # zaten pasifleri atlıyor — burada filtre yok ki koç pasif öğrencisini
    # ekranda görmeye devam etsin.
    assessments = bulk_risk_assessment(db, students=students)

    muted_ids = get_active_mutes(db, user.id)
    show_muted_flag = show_muted in ("1", "true", "yes")
    if not show_muted_flag:
        assessments = [a for a in assessments if a.student.id not in muted_ids]

    at_risk = filter_at_risk(assessments, min_level="medium")
    healthy = [a for a in assessments if a.level == "ok"]

    return templates.TemplateResponse(
        "teacher/at_risk_list.html",
        {
            "request": request,
            "user": user,
            "at_risk": at_risk,
            "healthy_count": len(healthy),
            "total_students": len(students),
            "muted_ids": muted_ids,
            "show_muted_flag": show_muted_flag,
            "flash_ok": ok,
        },
    )


@router.post("/teacher/at-risk/{student_id}/mute")
def teacher_mute_at_risk(
    student_id: int,
    request: Request,
    reason: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Öğrenciyi 7 gün boyunca risk panelinden gizle (yanlış alarm)."""
    # Öğrenci öğretmenin mi?
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.role == UserRole.STUDENT,
            User.teacher_id == user.id,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404)

    # Mevcut mute varsa süresini uzat (idempotent)
    existing = (
        db.query(AtRiskMute)
        .filter(
            AtRiskMute.teacher_id == user.id,
            AtRiskMute.student_id == student_id,
        )
        .first()
    )
    reason_clean = (reason or "").strip()[:255] or None
    if existing:
        existing.expires_at = at_risk_mute_default_expiry()
        if reason_clean:
            existing.reason = reason_clean
    else:
        m = AtRiskMute(
            teacher_id=user.id,
            student_id=student_id,
            reason=reason_clean,
            expires_at=at_risk_mute_default_expiry(),
        )
        db.add(m)
    db.commit()
    return RedirectResponse(
        url="/teacher/at-risk?ok=" + quote(
            f"{student.full_name} 7 gün risk panelinden gizlendi."
        ),
        status_code=303,
    )


@router.post("/teacher/at-risk/{student_id}/unmute")
def teacher_unmute_at_risk(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Mute'u kaldır — öğrenci tekrar panelde görünür."""
    deleted = (
        db.query(AtRiskMute)
        .filter(
            AtRiskMute.teacher_id == user.id,
            AtRiskMute.student_id == student_id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    msg = "Mute kaldırıldı." if deleted else "Aktif mute yok."
    return RedirectResponse(
        url="/teacher/at-risk?show_muted=1&ok=" + quote(msg),
        status_code=303,
    )


# ---------------------------- Institution admin panel ----------------------------


@router.get("/institution/at-risk")
def institution_at_risk_panel(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli risk panel — gizlilik korunur (program/not detayı YOK).

    Öğretmen-öğrenci eşlemesi görünür ama tıklanabilir link yok.
    Kurum admin'i öğretmenle iletişime geçer.
    """
    inst = db.get(Institution, user.institution_id)
    teacher_ids_query = (
        db.query(User.id)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id == user.institution_id,
        )
    )
    teacher_ids = [t[0] for t in teacher_ids_query.all()]
    if not teacher_ids:
        students: list[User] = []
    else:
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
        # NOT: pasif öğrenciler kurum panelinde de görünür (silik render);
        # bildirim/email üreticileri zaten pasifleri atlıyor.

    # Öğretmen ad eşlemesi
    teacher_map: dict[int, User] = {}
    if teacher_ids:
        for t in db.query(User).filter(User.id.in_(teacher_ids)).all():
            teacher_map[t.id] = t

    assessments = bulk_risk_assessment(db, students=students)
    at_risk = filter_at_risk(assessments, min_level="medium")
    healthy_count = sum(1 for a in assessments if a.level == "ok")

    # Mute durumu — kurum admin'e gizleme YOK ama "öğretmen mute etmiş" rozeti gösterilir
    student_ids = [a.student.id for a in at_risk]
    muted_map = get_active_mutes_for_students(db, student_ids)

    # Seviye sayım kartları
    counts = {
        "critical": sum(1 for a in at_risk if a.level == "critical"),
        "high": sum(1 for a in at_risk if a.level == "high"),
        "medium": sum(1 for a in at_risk if a.level == "medium"),
    }

    return templates.TemplateResponse(
        "institution/at_risk_list.html",
        {
            "request": request,
            "user": user,
            "institution": inst,
            "at_risk": at_risk,
            "teacher_map": teacher_map,
            "muted_map": muted_map,
            "counts": counts,
            "healthy_count": healthy_count,
            "total_students": len(students),
        },
    )
