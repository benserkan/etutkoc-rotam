"""Stage 14 — Pomodoro odak + gamification route'ları.

- GET  /student/focus                — pomodoro sayfası (timer + bugünkü özet)
- POST /student/focus/start          — yeni session başlat (form: planned_minutes, kind, label?)
- POST /student/focus/{sid}/end      — session bitir (form: actual_minutes, interrupted?)
- GET  /student/badges               — kazanılmış + kilitli rozetler
- GET  /teacher/students/{id}/focus  — öğretmen tarafında öğrencinin pomodoro istatistikleri
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_teacher
from app.models import PomodoroSession, StudentBadge, User, UserRole
from app.models.focus import PomodoroKind
from app.services.gamification import (
    BADGES,
    compute_points,
    compute_streak,
    evaluate_badges_for_student,
    list_student_badges,
    longest_streak,
)
from app.services.pomodoro import (
    auto_close_stale_sessions,
    end_session,
    end_session_and_start_break,
    recent_sessions,
    start_session,
    today_summary,
    total_work_minutes,
)
from app.templating import templates


router = APIRouter()


# ============================================================================
# ÖĞRENCİ — pomodoro
# ============================================================================


@router.get("/student/focus")
def student_focus(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)

    now = datetime.now(timezone.utc)
    # 3+ saatlik açık seansları otomatik kapat — öğrenci unutup gitmiş, veriyi temizle
    closed_n = auto_close_stale_sessions(db, student_id=user.id, hours=3, now=now)
    if closed_n:
        db.commit()
    # Aktif session (ended_at NULL, en son başlatılan) — sayaç bunu kullanır
    active = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.student_id == user.id,
            PomodoroSession.ended_at.is_(None),
        )
        .order_by(PomodoroSession.started_at.desc())
        .first()
    )
    # Aktif seans varsa elapsed_seconds'ı server'da hesapla (TZ-safe).
    # SQLite naive datetime döndürdüğü için browser'a isoformat geçmek TZ
    # karmaşası yaratıyor — server-side hesap kullanılarak bu sorun aşılır.
    active_elapsed_seconds = 0
    if active is not None:
        started = active.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        active_elapsed_seconds = int(max(0, (now - started).total_seconds()))
    summary = today_summary(db, student_id=user.id, now=now)
    recent = recent_sessions(db, student_id=user.id, limit=10)
    streak = compute_streak(db, student_id=user.id, now=now)
    points = compute_points(db, student_id=user.id)
    badges = list_student_badges(db, student_id=user.id)

    flash_ok = request.query_params.get("ok")
    return templates.TemplateResponse(
        "student/focus.html",
        {
            "request": request,
            "user": user,
            "active_session": active,
            "active_elapsed_seconds": active_elapsed_seconds,
            "summary": summary,
            "recent_sessions": recent,
            "streak": streak,
            "points": points,
            "badges": badges,
            "flash_ok": flash_ok,
        },
    )


@router.post("/student/focus/start")
def student_focus_start(
    planned_minutes: int = Form(25),
    kind: str = Form("work"),
    label: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    try:
        pk = PomodoroKind(kind)
    except ValueError:
        pk = PomodoroKind.WORK
    start_session(
        db,
        student_id=user.id,
        planned_minutes=planned_minutes,
        kind=pk,
        label=label,
    )
    db.commit()
    return RedirectResponse(url="/student/focus", status_code=303)


@router.post("/student/focus/{session_id}/end")
def student_focus_end(
    session_id: int,
    actual_minutes: int = Form(0),
    interrupted: str = Form(""),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    sess = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.id == session_id,
            PomodoroSession.student_id == user.id,
        )
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404)
    is_interrupted = interrupted.strip().lower() in ("on", "1", "true", "yes")
    end_session(
        db,
        session=sess,
        actual_minutes=actual_minutes if actual_minutes > 0 else None,
        interrupted=is_interrupted,
    )
    # Pomodoro bitiminde badge kontrolü
    evaluate_badges_for_student(db, student_id=user.id)
    db.commit()
    return RedirectResponse(url="/student/focus", status_code=303)


@router.post("/student/focus/{session_id}/delete")
def student_focus_delete(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test/eski pomodoro seansını sil.

    Kısıt: sadece kendi BİTMİŞ seansları (ended_at NOT NULL). Aktif seans
    silinemez — önce bitirilmesi gerekir. Bu sayede çalışan sayacın kaza
    sonucu yok olmasını önler. Silme sonrası bugünkü özet, streak, puan
    yeniden hesaplanır (sayfa yenilenmesiyle).
    """
    if user is None or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    sess = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.id == session_id,
            PomodoroSession.student_id == user.id,
        )
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404)
    if sess.ended_at is None:
        raise HTTPException(
            status_code=400,
            detail="Aktif (devam eden) seans silinemez — önce bitir.",
        )
    db.delete(sess)
    db.commit()
    return RedirectResponse(url="/student/focus", status_code=303)


@router.post("/student/focus/{session_id}/end-and-break")
def student_focus_end_and_break(
    session_id: int,
    actual_minutes: int = Form(0),
    interrupted: str = Form(""),
    break_kind: str = Form("short_break"),  # "short_break" veya "long_break"
    break_minutes: int = Form(5),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut seansı bitir + sıradaki molayı tek tıkla otomatik başlat.

    Klasik Pomodoro akışı: 25 dk çalış → 5 dk mola → 25 dk çalış ...
    Süre dolduğunda öğrenci bu butona basarak ikisini tek hamle ile yapar.
    """
    if user is None or user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)
    sess = (
        db.query(PomodoroSession)
        .filter(
            PomodoroSession.id == session_id,
            PomodoroSession.student_id == user.id,
        )
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404)
    try:
        bk = PomodoroKind(break_kind)
        if bk == PomodoroKind.WORK:
            bk = PomodoroKind.SHORT_BREAK
    except ValueError:
        bk = PomodoroKind.SHORT_BREAK
    bm = max(1, min(break_minutes, 30))
    is_interrupted = interrupted.strip().lower() in ("on", "1", "true", "yes")
    end_session_and_start_break(
        db,
        session=sess,
        actual_minutes=actual_minutes if actual_minutes > 0 else None,
        interrupted=is_interrupted,
        break_kind=bk,
        break_minutes=bm,
    )
    evaluate_badges_for_student(db, student_id=user.id)
    db.commit()
    return RedirectResponse(url="/student/focus", status_code=303)


# ============================================================================
# ÖĞRENCİ — rozetler
# ============================================================================


@router.get("/student/badges")
def student_badges(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403)

    earned = list_student_badges(db, student_id=user.id)
    earned_kinds = {b.kind for b, _ in earned}
    locked = [b for k, b in BADGES.items() if k not in earned_kinds]

    streak = compute_streak(db, student_id=user.id)
    longest = longest_streak(db, student_id=user.id)
    points = compute_points(db, student_id=user.id)

    return templates.TemplateResponse(
        "student/badges.html",
        {
            "request": request,
            "user": user,
            "earned": earned,
            "locked": locked,
            "streak": streak,
            "longest_streak": longest,
            "points": points,
        },
    )


# ============================================================================
# ÖĞRETMEN — öğrencinin odak istatistikleri
# ============================================================================


@router.get("/teacher/students/{student_id}/focus")
def teacher_student_focus(
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
        raise HTTPException(status_code=404)

    now = datetime.now(timezone.utc)
    summary = today_summary(db, student_id=student.id, now=now)
    recent = recent_sessions(db, student_id=student.id, limit=20)
    streak = compute_streak(db, student_id=student.id, now=now)
    longest = longest_streak(db, student_id=student.id)
    points = compute_points(db, student_id=student.id)
    badges = list_student_badges(db, student_id=student.id)
    work_min_30d = total_work_minutes(db, student_id=student.id, since_days=30)

    return templates.TemplateResponse(
        "teacher/student_focus.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "summary": summary,
            "recent_sessions": recent,
            "streak": streak,
            "longest_streak": longest,
            "points": points,
            "badges": badges,
            "work_min_30d": work_min_30d,
        },
    )
