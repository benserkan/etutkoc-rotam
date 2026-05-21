"""Stage 13 — Çalışma DNA + burnout route'ları.

- GET /student/dna                          — öğrenci kendi profilini görür
- GET /teacher/students/{id}/dna            — öğretmen + burnout uyarıları
- GET /teacher/burnout                      — öğretmenin tüm öğrencileri risk listesi
- GET /institution/burnout                  — kurum geneli risk listesi (gizlilik korunur)

Yetki:
- Öğrenci yalnız kendi
- Öğretmen kendi öğrencilerine
- Institution admin kendi kurumundaki öğretmen-öğrenci eşleşmelerine
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import (
    get_current_user,
    get_db,
    require_institution_admin,
    require_teacher,
)
from app.models import TeacherNoteToParent, User, UserRole
from app.services.burnout import (
    SIGNAL_EMOJI,
    SIGNAL_LABELS_TR,
    bulk_burnout_for_teacher,
    compute_burnout,
)
from app.services.dna_parent_message import build_dna_parent_message
from app.services.event_triggers import (
    _active_parents_for,
    on_teacher_note_created,
)
from app.services.study_dna import (
    CHRONOTYPE_EMOJI,
    CHRONOTYPE_LABELS_TR,
    DAY_NAMES_TR,
    compute_profile,
)
from app.templating import templates


router = APIRouter()


# ============================================================================
# ÖĞRENCİ
# ============================================================================


@router.get("/student/dna")
def student_dna(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/login", status_code=303)
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Bu sayfa öğrencilere özeldir.")

    now = datetime.now(timezone.utc)
    profile = compute_profile(db, student_id=user.id, now=now)
    burnout = compute_burnout(db, student_id=user.id, now=now)

    return templates.TemplateResponse(
        "student/dna.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "burnout": burnout,
            "chronotype_labels": CHRONOTYPE_LABELS_TR,
            "chronotype_emoji": CHRONOTYPE_EMOJI,
            "day_names": DAY_NAMES_TR,
        },
    )


# ============================================================================
# ÖĞRETMEN
# ============================================================================


@router.get("/teacher/students/{student_id}/dna")
def teacher_student_dna(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı.")

    now = datetime.now(timezone.utc)
    profile = compute_profile(db, student_id=student.id, now=now)
    burnout = compute_burnout(db, student_id=student.id, now=now)

    # Veliye duyur — preview text + bağlı veli sayısı (modal'da kullanılır)
    parent_count = len(_active_parents_for(db, student.id))
    parent_message_preview = build_dna_parent_message(
        student=student, teacher=user, burnout=burnout, profile=profile,
    )

    flash_ok = request.query_params.get("ok")
    return templates.TemplateResponse(
        "teacher/student_dna.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "profile": profile,
            "burnout": burnout,
            "chronotype_labels": CHRONOTYPE_LABELS_TR,
            "chronotype_emoji": CHRONOTYPE_EMOJI,
            "day_names": DAY_NAMES_TR,
            "parent_count": parent_count,
            "parent_message_preview": parent_message_preview,
            "flash_ok": flash_ok,
        },
    )


@router.post("/teacher/students/{student_id}/dna/notify-parent")
def teacher_student_dna_notify_parent(
    student_id: int,
    body: str = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """DNA panelinden veliye otomatik mesaj gönder.

    Akış: form'dan gelen body (öğretmen önizlemede düzenlemiş olabilir) ile
    `TeacherNoteToParent` kaydı oluştur → `on_teacher_note_created` tetikle
    (mevcut veli bildirim kuyruğunu kullanır: email + WA).

    Yetki: sadece öğretmenin kendi öğrencisi.
    Boş gövde reddedilir. Veli yoksa 400 (UI butonu zaten disable etmeli).
    """
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Öğrenci bulunamadı.")

    body = (body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")
    if len(body) > 2000:
        body = body[:2000]

    parents = _active_parents_for(db, student.id)
    if not parents:
        raise HTTPException(
            status_code=400,
            detail="Bu öğrenciye bağlı aktif veli yok.",
        )

    note = TeacherNoteToParent(
        student_id=student.id,
        teacher_id=user.id,
        body=body,
    )
    db.add(note)
    db.flush()  # note.id gerekli

    on_teacher_note_created(db, note)
    db.commit()

    return RedirectResponse(
        url=f"/teacher/students/{student.id}/dna?ok=parent_notified",
        status_code=303,
    )


@router.get("/teacher/burnout")
def teacher_burnout_dashboard(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    rows = bulk_burnout_for_teacher(db, teacher_id=user.id, now=now)
    return templates.TemplateResponse(
        "teacher/burnout_dashboard.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
        },
    )


# ============================================================================
# INSTITUTION ADMIN
# ============================================================================


@router.get("/institution/burnout")
def institution_burnout(
    request: Request,
    user: User = Depends(require_institution_admin),
    db: Session = Depends(get_db),
):
    """Kurum geneli burnout listesi. Gizlilik: öğrenci ad-soyad + öğretmen
    görünür ama detay sayfasına link yok."""
    if not user.institution_id:
        raise HTTPException(status_code=403)
    now = datetime.now(timezone.utc)
    students = (
        db.query(User)
        .filter(
            User.institution_id == user.institution_id,
            User.role == UserRole.STUDENT,
        )
        .order_by(User.full_name)
        .all()
    )
    rows = []
    for s in students:
        report = compute_burnout(db, student_id=s.id, now=now)
        if report.risk_score == 0:
            continue
        rows.append({
            "student": s,
            "report": report,
            "risk_score": report.risk_score,
            "risk_level": report.risk_level,
            "signal_count": len(report.signals),
        })
    rows.sort(key=lambda r: (-r["risk_score"], r["student"].full_name.lower()))
    return templates.TemplateResponse(
        "institution/burnout.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
        },
    )
