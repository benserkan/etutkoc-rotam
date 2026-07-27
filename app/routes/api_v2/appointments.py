"""Online görüşme / randevu sistemi — API v2 router (koç + öğrenci + veli).

Akışlar:
- Koç randevu atar (tek/haftalık) → öğrenci+veli bilgilendirilir.
- Koç uygunluk pencereleri tanımlar → öğrenci boş slottan İSTEK açar (pending)
  → koç onaylar/reddeder.
- Görüşme linki: koç elle yapıştırır VEYA Google bağlıysa sistem koçun kendi
  hesabından Meet linki üretir (best-effort — akış asla bloklanmaz).
- Bildirimler BackgroundTasks ile (yanıt bloklanmaz); hatırlatmalar cron'da
  (appointment_maintenance).

Sahiplik dışı her şey 404 (varlık sızıntısı yok). Veli yalnız kendi çocuğunun
YAKLAŞAN randevularını görür (salt-okuma).
"""

from __future__ import annotations

import logging
from datetime import date as date_cls, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.deps import get_db
from app.models import (
    APPT_SOURCE_LABELS_TR,
    APPT_SOURCE_STUDENT,
    APPT_STATUS_CANCELLED,
    APPT_STATUS_LABELS_TR,
    APPT_STATUS_PENDING,
    APPT_STATUS_SCHEDULED,
    CoachAvailabilityWindow,
    CoachingAppointment,
    CoachingAppointmentSeries,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.appointment import (
    WEEKDAY_LABELS_TR,
    AppointmentCreateBody,
    AppointmentItem,
    AppointmentMutationResult,
    AppointmentStatusBody,
    AppointmentUpdateBody,
    AvailabilityMutationResult,
    AvailabilityReplaceBody,
    AvailabilityWindowItem,
    GoogleConnectUrlResponse,
    GoogleStatusInfo,
    ParentAppointmentsResponse,
    RecordSessionBody,
    RecordSessionResult,
    RejectBody,
    SeriesItem,
    SeriesUpdateBody,
    SeriesUpdateResult,
    SimpleOkResult,
    SlotDay,
    SlotItem,
    StudentAppointmentsResponse,
    StudentRequestBody,
    StudentSlotsResponse,
    TeacherAppointmentsResponse,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.services import appointment_service as svc
from app.services import google_meet
from app.services.parent_view import ParentAccessDenied, assert_parent_can_view

logger = logging.getLogger(__name__)

router = APIRouter(tags=["v2-appointments"])


# ============================================================================
# Yardımcılar
# ============================================================================


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": "not_found", "code": "appointment_not_found",
        "message": "Randevu bulunamadı.",
    })


def _svc_error(e: svc.AppointmentError) -> HTTPException:
    return HTTPException(status_code=e.status, detail={
        "error": "validation" if e.status == 422 else "not_found",
        "code": e.code, "message": e.message,
    })


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız koç hesabıyla kullanılabilir.",
        })
    return user


def _require_student(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız öğrenci hesabıyla kullanılabilir.",
        })
    return user


def _require_parent(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.PARENT:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız veli hesabıyla kullanılabilir.",
        })
    return user


def _get_owned_student(db: Session, coach: User, student_id: int) -> User:
    student = db.get(User, student_id)
    if (
        student is None
        or student.role != UserRole.STUDENT
        or student.teacher_id != coach.id
    ):
        raise _not_found()
    return student


def _get_coach_appt(db: Session, coach: User, appt_id: int) -> CoachingAppointment:
    appt = db.get(CoachingAppointment, appt_id)
    if appt is None or appt.coach_id != coach.id:
        raise _not_found()
    return appt


def _parse_date(value: str, *, code: str = "invalid_date") -> date_cls:
    try:
        return date_cls.fromisoformat((value or "").strip())
    except ValueError:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": code,
            "message": "Tarih YYYY-AA-GG biçiminde olmalı.",
        })


def _to_item(
    appt: CoachingAppointment,
    *,
    viewer_role: str = "teacher",
    session_map: dict[int, int] | None = None,
) -> AppointmentItem:
    is_past = False
    try:
        end_dt = svc.appt_start_dt(appt) + timedelta(minutes=appt.duration_min or 40)
        is_past = end_dt < svc.now_tr()
    except svc.AppointmentError:
        pass
    return AppointmentItem(
        id=appt.id,
        student_id=appt.student_id,
        student_name=(appt.student.full_name if appt.student else "—"),
        coach_name=(appt.coach.full_name if appt.coach else None),
        session_id=(session_map or {}).get(appt.id),
        date=appt.date.isoformat(),
        start_time=appt.start_time,
        duration_min=appt.duration_min or 40,
        weekday_label=WEEKDAY_LABELS_TR[appt.date.weekday()],
        status=appt.status,
        status_label=APPT_STATUS_LABELS_TR.get(appt.status, appt.status),
        source=appt.source,
        source_label=APPT_SOURCE_LABELS_TR.get(appt.source, appt.source),
        meeting_link=appt.meeting_link,
        link_source=appt.link_source,
        note=(appt.note if viewer_role == "teacher" else None),
        request_note=appt.request_note,
        cancel_reason=appt.cancel_reason,
        series_id=appt.series_id,
        is_past=is_past,
    )


def _series_item(s: CoachingAppointmentSeries) -> SeriesItem:
    return SeriesItem(
        id=s.id,
        student_id=s.student_id,
        student_name=(s.student.full_name if s.student else "—"),
        weekday=s.weekday,
        weekday_label=WEEKDAY_LABELS_TR[s.weekday],
        start_time=s.start_time,
        duration_min=s.duration_min,
        meeting_link=s.meeting_link,
        link_source=s.link_source,
        active=s.active,
        note=s.note,
    )


def _availability_items(db: Session, coach_id: int) -> list[AvailabilityWindowItem]:
    rows = (
        db.query(CoachAvailabilityWindow)
        .filter(
            CoachAvailabilityWindow.coach_id == coach_id,
            CoachAvailabilityWindow.active.is_(True),
        )
        .order_by(
            CoachAvailabilityWindow.weekday, CoachAvailabilityWindow.start_time
        )
        .all()
    )
    return [
        AvailabilityWindowItem(
            weekday=w.weekday, start_time=w.start_time,
            end_time=w.end_time, slot_minutes=w.slot_minutes,
        )
        for w in rows
    ]


def _teacher_invalidate(coach_id: int, student_id: int | None = None) -> list[str]:
    keys = [f"teacher:{coach_id}:appointments", "student:appointments"]
    if student_id:
        keys.append(f"teacher:{coach_id}:students:{student_id}")
    return keys


def _notify_bg(appt_id: int, event: str) -> None:
    svc.notify_appointment_event_bg(appt_id, event)


def _push_coach_bg(coach_id: int, title: str, body: str) -> None:
    """Koça best-effort push (taze session)."""
    from app.services.push_notifications import safe_push

    db = SessionLocal()
    try:
        safe_push(
            db, user_id=coach_id, title=title, body=body,
            data={"type": "coach", "screen": "appointments"},
        )
    finally:
        db.close()


# ============================================================================
# Koç uçları
# ============================================================================


@router.get("/teacher/appointments", response_model=TeacherAppointmentsResponse)
def teacher_appointments_v2(
    start: str | None = None,
    end: str | None = None,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Takvim paketi: aralıktaki randevular + bekleyen istekler + seriler +
    uygunluk + Google durumu (tek sorgu — takvim sayfası bununla dolar)."""
    today = svc.now_tr().date()
    start_d = _parse_date(start) if start else today - timedelta(days=today.weekday())
    end_d = _parse_date(end) if end else start_d + timedelta(days=13)
    if end_d < start_d:
        start_d, end_d = end_d, start_d
    if (end_d - start_d).days > 62:
        end_d = start_d + timedelta(days=62)

    items = svc.list_for_coach(db, user.id, start=start_d, end=end_d)
    pending = svc.pending_for_coach(db, user.id)
    series_rows = (
        db.query(CoachingAppointmentSeries)
        .filter(
            CoachingAppointmentSeries.coach_id == user.id,
            CoachingAppointmentSeries.active.is_(True),
        )
        .all()
    )
    # F4 — hangi randevunun seansı kaydedilmiş (tek sorgu)
    session_map: dict[int, int] = {}
    appt_ids = [a.id for a in items]
    if appt_ids:
        from app.models import CoachingSession

        session_map = dict(
            db.query(CoachingSession.appointment_id, CoachingSession.id)
            .filter(CoachingSession.appointment_id.in_(appt_ids))
            .all()
        )
    g = svc.google_status(db, user)
    return TeacherAppointmentsResponse(
        start=start_d.isoformat(),
        end=end_d.isoformat(),
        items=[_to_item(a, session_map=session_map) for a in items],
        pending=[_to_item(a) for a in pending],
        series=[_series_item(s) for s in series_rows],
        availability=_availability_items(db, user.id),
        google=GoogleStatusInfo(**g),
    )


@router.post(
    "/teacher/appointments",
    response_model=MutationResponse[AppointmentMutationResult],
)
def teacher_appointment_create_v2(
    body: AppointmentCreateBody,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    student = _get_owned_student(db, user, body.student_id)
    d = _parse_date(body.date)
    try:
        appt, series = svc.create_by_coach(
            db,
            coach=user,
            student=student,
            d=d,
            start_time=body.start_time,
            duration_min=body.duration_min,
            meeting_link=body.meeting_link,
            note=body.note,
            weekly=body.weekly,
        )
    except svc.AppointmentError as e:
        raise _svc_error(e)

    # Google bağlıysa + elle link yoksa Meet linki üret (best-effort)
    attached = False
    try:
        attached = google_meet.try_attach_meet_link(db, appt, series=series)
    except Exception as e:  # noqa: BLE001 — link üretimi akışı asla bozmaz
        logger.warning("meet attach failed (non-fatal): %s", e)

    db.commit()
    db.refresh(appt)
    if series:
        db.refresh(series)
    background.add_task(_notify_bg, appt.id, "scheduled")
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(
            appointment=_to_item(appt),
            series=_series_item(series) if series else None,
            google_link_attached=attached,
        ),
        invalidate=_teacher_invalidate(user.id, student.id),
    )


@router.post(
    "/teacher/appointments/{appt_id}",
    response_model=MutationResponse[AppointmentMutationResult],
)
def teacher_appointment_update_v2(
    appt_id: int,
    body: AppointmentUpdateBody,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    appt = _get_coach_appt(db, user, appt_id)
    d = _parse_date(body.date) if body.date else None
    try:
        result = svc.update_appointment(
            db, appt,
            d=d,
            start_time=body.start_time,
            duration_min=body.duration_min,
            meeting_link=body.meeting_link,
            note=body.note,
        )
    except svc.AppointmentError as e:
        raise _svc_error(e)
    if result["time_changed"]:
        try:
            google_meet.try_sync_time_change(db, appt)
        except Exception as e:  # noqa: BLE001
            logger.warning("meet sync failed (non-fatal): %s", e)
    db.commit()
    db.refresh(appt)
    if result["time_changed"] and appt.status == APPT_STATUS_SCHEDULED:
        background.add_task(_notify_bg, appt.id, "updated")
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(appointment=_to_item(appt)),
        invalidate=_teacher_invalidate(user.id, appt.student_id),
    )


@router.post(
    "/teacher/appointments/{appt_id}/status",
    response_model=MutationResponse[AppointmentMutationResult],
)
def teacher_appointment_status_v2(
    appt_id: int,
    body: AppointmentStatusBody,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    appt = _get_coach_appt(db, user, appt_id)
    was_scheduled = appt.status == APPT_STATUS_SCHEDULED
    try:
        svc.set_status(db, appt, status=body.status, reason=body.reason)
    except svc.AppointmentError as e:
        raise _svc_error(e)
    if body.status == APPT_STATUS_CANCELLED:
        try:
            google_meet.try_sync_cancel(db, appt)
        except Exception as e:  # noqa: BLE001
            logger.warning("meet cancel sync failed (non-fatal): %s", e)
    db.commit()
    db.refresh(appt)
    if body.status == APPT_STATUS_CANCELLED and was_scheduled:
        background.add_task(_notify_bg, appt.id, "cancelled")
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(appointment=_to_item(appt)),
        invalidate=_teacher_invalidate(user.id, appt.student_id),
    )


@router.post(
    "/teacher/appointments/{appt_id}/approve",
    response_model=MutationResponse[AppointmentMutationResult],
)
def teacher_appointment_approve_v2(
    appt_id: int,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    appt = _get_coach_appt(db, user, appt_id)
    try:
        svc.approve_request(db, appt)
    except svc.AppointmentError as e:
        raise _svc_error(e)
    attached = False
    try:
        attached = google_meet.try_attach_meet_link(db, appt)
    except Exception as e:  # noqa: BLE001
        logger.warning("meet attach failed (non-fatal): %s", e)
    db.commit()
    db.refresh(appt)
    background.add_task(_notify_bg, appt.id, "request_approved")
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(
            appointment=_to_item(appt), google_link_attached=attached,
        ),
        invalidate=_teacher_invalidate(user.id, appt.student_id),
    )


@router.post(
    "/teacher/appointments/{appt_id}/reject",
    response_model=MutationResponse[AppointmentMutationResult],
)
def teacher_appointment_reject_v2(
    appt_id: int,
    body: RejectBody,
    background: BackgroundTasks,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    appt = _get_coach_appt(db, user, appt_id)
    try:
        svc.reject_request(db, appt, reason=body.reason)
    except svc.AppointmentError as e:
        raise _svc_error(e)
    db.commit()
    db.refresh(appt)
    background.add_task(_notify_bg, appt.id, "request_rejected")
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(appointment=_to_item(appt)),
        invalidate=_teacher_invalidate(user.id, appt.student_id),
    )


@router.post(
    "/teacher/appointment-series/{series_id}",
    response_model=MutationResponse[SeriesUpdateResult],
)
def teacher_series_update_v2(
    series_id: int,
    body: SeriesUpdateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    series = db.get(CoachingAppointmentSeries, series_id)
    if series is None or series.coach_id != user.id:
        raise _not_found()
    try:
        counts = svc.update_series(
            db, series,
            weekday=body.weekday,
            start_time=body.start_time,
            duration_min=body.duration_min,
            meeting_link=body.meeting_link,
            active=body.active,
        )
    except svc.AppointmentError as e:
        raise _svc_error(e)
    db.commit()
    db.refresh(series)
    return MutationResponse[SeriesUpdateResult](
        data=SeriesUpdateResult(
            series=_series_item(series),
            cancelled=counts["cancelled"],
            regenerated=counts["regenerated"],
        ),
        invalidate=_teacher_invalidate(user.id, series.student_id),
    )


@router.post(
    "/teacher/availability",
    response_model=MutationResponse[AvailabilityMutationResult],
)
def teacher_availability_replace_v2(
    body: AvailabilityReplaceBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Uygunluk pencerelerini topluca değiştir (replace-all).

    Boş liste = self-servis kapalı (öğrenci slot göremez); koç doğrudan
    atamaya devam eder.
    """
    try:
        svc.replace_availability(
            db, user, [w.model_dump() for w in body.windows]
        )
    except svc.AppointmentError as e:
        raise _svc_error(e)
    db.commit()
    return MutationResponse[AvailabilityMutationResult](
        data=AvailabilityMutationResult(
            availability=_availability_items(db, user.id)
        ),
        invalidate=_teacher_invalidate(user.id),
    )


# ============================================================================
# F4 — randevudan seans kaydı (KS1 köprüsü; DONE seans KS2 tahsilata sayılır)
# ============================================================================


@router.post(
    "/teacher/appointments/{appt_id}/record-session",
    response_model=MutationResponse[RecordSessionResult],
)
def teacher_appointment_record_session_v2(
    appt_id: int,
    body: RecordSessionBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Biten görüşmeyi tek adımda KS1 seans kaydına çevir.

    - outcome=done → randevu 'done' + DONE seans (KS2 tahsilata sayılır;
      gündem zorunlu — KS1 sözleşmesi).
    - outcome=no_show → randevu 'no_show' + NO_SHOW seans (iz kalır,
      ücrete sayılmaz).
    Randevu başına TEK seans (mükerrer → 422 session_exists). Otomatik
    snapshot (Kova 1) seans anında hesaplanıp saklanır; KS4 içgörü cache'i
    bayatlar.
    """
    import json as _json

    from app.models import (
        APPT_STATUS_DONE,
        APPT_STATUS_NO_SHOW,
        CoachingChannel,
        CoachingSession,
        CoachingSessionStatus,
    )
    from app.routes.api_v2.teacher import (
        _compute_session_prefill,
        _mark_insight_stale,
    )

    appt = _get_coach_appt(db, user, appt_id)

    if appt.status == APPT_STATUS_PENDING:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "pending_needs_review",
            "message": "Bekleyen istek önce onaylanmalı ya da reddedilmeli.",
        })
    if appt.status not in (APPT_STATUS_SCHEDULED, APPT_STATUS_DONE, APPT_STATUS_NO_SHOW):
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "not_recordable",
            "message": "İptal edilmiş/reddedilmiş randevudan seans kaydedilemez.",
        })
    existing = (
        db.query(CoachingSession)
        .filter(CoachingSession.appointment_id == appt.id)
        .first()
    )
    if existing is not None:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "session_exists",
            "message": "Bu görüşmenin seans kaydı zaten var.",
        })

    student = db.get(User, appt.student_id)
    if student is None:
        raise _not_found()

    agenda = (body.agenda or "").strip()
    if body.outcome == "done" and not agenda:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "agenda_required",
            "message": "Yapılan seans için gündem (ne konuşuldu) zorunlu.",
        })
    if body.outcome == "no_show" and not agenda:
        agenda = "Öğrenci görüşmeye gelmedi."

    s = CoachingSession(
        coach_id=user.id,
        student_id=student.id,
        appointment_id=appt.id,
        session_date=appt.date,
        status=(
            CoachingSessionStatus.DONE
            if body.outcome == "done"
            else CoachingSessionStatus.NO_SHOW
        ),
        duration_min=appt.duration_min,
        channel=CoachingChannel.ONLINE,
        agenda=agenda[:5000],
        coach_note=(body.coach_note or "").strip()[:8000] or None,
        next_change=(body.next_change or "").strip()[:2000] or None,
        mood=body.mood,
    )
    s.auto_snapshot = _json.dumps(
        _compute_session_prefill(db, student), ensure_ascii=False
    )
    db.add(s)
    appt.status = (
        APPT_STATUS_DONE if body.outcome == "done" else APPT_STATUS_NO_SHOW
    )
    _mark_insight_stale(db, student.id)  # yeni seans → KS4 içgörü cache bayatlar
    db.commit()
    db.refresh(s)
    db.refresh(appt)
    return MutationResponse[RecordSessionResult](
        data=RecordSessionResult(
            appointment=_to_item(appt, session_map={appt.id: s.id}),
            session_id=s.id,
        ),
        invalidate=[
            f"teacher:{user.id}:appointments",
            f"teacher:{user.id}:students:{student.id}:sessions",
            f"teacher:{user.id}:students:{student.id}",
            "teacher:me:billing",
        ],
    )


# ============================================================================
# Google OAuth
# ============================================================================


@router.get("/teacher/google/connect-url", response_model=GoogleConnectUrlResponse)
def teacher_google_connect_url_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    if not google_meet.is_configured():
        raise HTTPException(status_code=409, detail={
            "error": "conflict", "code": "google_not_configured",
            "message": "Google bağlantısı bu sunucuda henüz açık değil.",
        })
    return GoogleConnectUrlResponse(url=google_meet.build_auth_url(user))


@router.post("/teacher/google/disconnect", response_model=MutationResponse[SimpleOkResult])
def teacher_google_disconnect_v2(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    google_meet.disconnect(db, user)
    db.commit()
    return MutationResponse[SimpleOkResult](
        data=SimpleOkResult(), invalidate=_teacher_invalidate(user.id),
    )


@router.get("/google/oauth/callback", include_in_schema=False)
def google_oauth_callback_v2(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Google OAuth dönüşü (public — kimlik state token'ından çözülür).

    Başarıda/hatada koç takvim sayfasına yönlendirir (?google=connected|error).
    """
    target = f"{settings.app_base_url.rstrip('/')}/teacher/appointments"

    def _redirect(status: str) -> RedirectResponse:
        return RedirectResponse(url=f"{target}?google={status}", status_code=303)

    if error:
        return _redirect("denied")
    if not code or not state:
        return _redirect("error")
    user_id = google_meet.decode_state(state)
    if user_id is None:
        return _redirect("error")
    user = db.get(User, user_id)
    if user is None or user.role != UserRole.TEACHER:
        return _redirect("error")
    try:
        google_meet.exchange_code(db, user, code)
        db.commit()
    except google_meet.GoogleMeetError as e:
        logger.warning("google oauth exchange failed user=%s: %s", user_id, e.message)
        return _redirect("error")
    return _redirect("connected")


# ============================================================================
# Öğrenci uçları
# ============================================================================


def _student_response(db: Session, student: User) -> StudentAppointmentsResponse:
    upcoming_all = svc.upcoming_for_student(db, student.id)
    upcoming = [a for a in upcoming_all if a.status == APPT_STATUS_SCHEDULED]
    pending = [a for a in upcoming_all if a.status == APPT_STATUS_PENDING]
    past = svc.recent_past_for_student(db, student.id)
    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    has_windows = False
    if coach is not None:
        has_windows = (
            db.query(CoachAvailabilityWindow)
            .filter(
                CoachAvailabilityWindow.coach_id == coach.id,
                CoachAvailabilityWindow.active.is_(True),
            )
            .first()
            is not None
        )
    return StudentAppointmentsResponse(
        upcoming=[_to_item(a, viewer_role="student") for a in upcoming],
        pending=[_to_item(a, viewer_role="student") for a in pending],
        past=[_to_item(a, viewer_role="student") for a in past],
        coach_name=(coach.full_name if coach else None),
        can_request=bool(coach and has_windows),
        has_pending=bool(pending),
    )


@router.get("/student/appointments", response_model=StudentAppointmentsResponse)
def student_appointments_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    return _student_response(db, user)


@router.get("/student/appointments/slots", response_model=StudentSlotsResponse)
def student_appointment_slots_v2(
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    if not user.teacher_id:
        return StudentSlotsResponse(days=[])
    days = svc.available_slots(db, coach_id=user.teacher_id)
    return StudentSlotsResponse(days=[
        SlotDay(
            date=d["date"],
            weekday_label=WEEKDAY_LABELS_TR[date_cls.fromisoformat(d["date"]).weekday()],
            slots=[SlotItem(**s) for s in d["slots"]],
        )
        for d in days
    ])


@router.post(
    "/student/appointments/request",
    response_model=MutationResponse[AppointmentMutationResult],
)
def student_appointment_request_v2(
    body: StudentRequestBody,
    background: BackgroundTasks,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    if not user.teacher_id:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "no_coach",
            "message": "Görüşme isteği için bir koça bağlı olman gerekir.",
        })
    coach = db.get(User, user.teacher_id)
    if coach is None:
        raise _not_found()
    d = _parse_date(body.date)
    try:
        appt = svc.create_request(
            db,
            student=user,
            coach=coach,
            d=d,
            start_time=body.start_time,
            note=body.note,
            requested_by=user,
            source=APPT_SOURCE_STUDENT,
        )
    except svc.AppointmentError as e:
        raise _svc_error(e)
    db.commit()
    db.refresh(appt)
    background.add_task(
        _push_coach_bg,
        coach.id,
        "Görüşme isteği",
        f"{user.full_name} görüşme istedi: {appt.date.strftime('%d.%m')} {appt.start_time}.",
    )
    return MutationResponse[AppointmentMutationResult](
        data=AppointmentMutationResult(
            appointment=_to_item(appt, viewer_role="student")
        ),
        invalidate=["student:appointments", f"teacher:{coach.id}:appointments"],
    )


@router.post(
    "/student/appointments/{appt_id}/withdraw",
    response_model=MutationResponse[SimpleOkResult],
)
def student_appointment_withdraw_v2(
    appt_id: int,
    user: User = Depends(_require_student),
    db: Session = Depends(get_db),
):
    """Öğrenci yalnız BEKLEYEN kendi isteğini geri çekebilir."""
    appt = (
        db.query(CoachingAppointment)
        .filter(
            CoachingAppointment.id == appt_id,
            CoachingAppointment.student_id == user.id,
        )
        .first()
    )
    if appt is None:
        raise _not_found()
    if appt.status != APPT_STATUS_PENDING:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "not_pending",
            "message": "Yalnız bekleyen istek geri çekilebilir — koçunla konuş.",
        })
    db.delete(appt)
    db.commit()
    keys = ["student:appointments"]
    if user.teacher_id:
        keys.append(f"teacher:{user.teacher_id}:appointments")
    return MutationResponse[SimpleOkResult](data=SimpleOkResult(), invalidate=keys)


# ============================================================================
# Veli ucu (salt-okuma)
# ============================================================================


@router.get(
    "/parent/students/{student_id}/appointments",
    response_model=ParentAppointmentsResponse,
)
def parent_student_appointments_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "student_not_found",
            "message": "Öğrenci bulunamadı.",
        })
    upcoming = [
        a for a in svc.upcoming_for_student(db, student.id)
        if a.status == APPT_STATUS_SCHEDULED
    ]
    return ParentAppointmentsResponse(
        student_name=student.full_name,
        upcoming=[_to_item(a, viewer_role="parent") for a in upcoming],
    )
