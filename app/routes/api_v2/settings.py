"""API v2 — Öğretmen ayarları + kredi paneli (Dalga 3 Paket 9).

Endpoint haritası (prefix `/teacher/settings` + `/teacher/usage`):
  GET    /teacher/settings                                 → TeacherSettingsResponse
  POST   /teacher/settings/test-email                      → MutationResponse[TestEmailResult]
  PATCH  /teacher/settings/cron/{schedule_id}              → MutationResponse[CronScheduleItem]
  POST   /teacher/settings/cron/run-now                    → MutationResponse[CronRunNowResult]
  GET    /teacher/usage/current                            → TeacherUsageResponse

Servis sözleşmeleri korunur:
  - app.services.credits (CreditOwner, get_or_create_account, ...)
  - app.services.email_service.send_email
  - app.services.cron_runner.tick + notification_dispatcher.dispatch_pending
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.deps import get_db
from app.models import (
    USAGE_KIND_LABELS_TR,
    CronSchedule,
    UsageKind,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import _auth_error, get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.settings import (
    CronJobInfo,
    CronRunNowResult,
    CronSchedulePatchBody,
    CronScheduleItem,
    EmailConfigStatus,
    PlanAllocationItem,
    TeacherProfileBrief,
    TeacherSettingsResponse,
    TeacherUsageResponse,
    TestEmailBody,
    TestEmailResult,
    UsageBreakdownItem,
    UsageDailyPoint,
    UsageEventItem,
    UsagePeriodAccount,
)
from app.routes.teacher_settings import JOB_INFO, _summarize_run, _utc_to_tr_label
from app.services.credits import (
    KIND_CREDITS,
    PLAN_ALLOCATIONS,
    CreditOwner,
    current_period,
    daily_usage_series,
    get_or_create_account,
    recent_events,
    usage_breakdown_by_kind,
)
from app.services.email_service import send_email


router = APIRouter(tags=["v2-teacher-settings"])


# =============================================================================
# Auth kapısı
# =============================================================================


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise _auth_error(
            "Bu uç nokta öğretmen hesabı bekler",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _not_found(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": code, "message": message},
    )


def _validation_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={"error": "validation", "code": code, "message": message},
    )


def _invalidate_settings(teacher_id: int) -> list[str]:
    return [f"teacher:{teacher_id}:settings"]


def _invalidate_usage(teacher_id: int) -> list[str]:
    return [
        f"teacher:{teacher_id}:usage",
        f"teacher:{teacher_id}:settings",
    ]


def _build_cron_item(sch: CronSchedule) -> CronScheduleItem:
    info_dict = JOB_INFO.get(sch.job_key)
    info = CronJobInfo(**info_dict) if info_dict else None
    return CronScheduleItem(
        id=sch.id,
        job_key=sch.job_key,
        description=sch.description,
        hour=sch.hour,
        minute=sch.minute,
        day_of_week=sch.day_of_week,
        interval_minutes=sch.interval_minutes,
        enabled=bool(sch.enabled),
        last_run_at=sch.last_run_at,
        last_status=sch.last_status,
        last_error=sch.last_error,
        time_label=sch.time_label,
        tr_time_label=_utc_to_tr_label(sch.hour, sch.minute),
        dow_label=sch.dow_label,
        info=info,
    )


def _build_profile(user: User) -> TeacherProfileBrief:
    return TeacherProfileBrief(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.value,
        institution_id=user.institution_id,
        plan=getattr(user, "plan", None),
    )


def _email_status() -> EmailConfigStatus:
    host = app_settings.smtp_host or None
    port = getattr(app_settings, "smtp_port", None)
    return EmailConfigStatus(
        enabled=bool(app_settings.email_enabled),
        smtp_host=host,
        smtp_port=int(port) if port else None,
        from_address=getattr(app_settings, "smtp_from", None) or None,
    )


# =============================================================================
# GET /teacher/settings
# =============================================================================


@router.get("/teacher/settings", response_model=TeacherSettingsResponse)
def get_settings(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> TeacherSettingsResponse:
    cron = db.query(CronSchedule).order_by(CronSchedule.id.asc()).all()
    return TeacherSettingsResponse(
        teacher=_build_profile(user),
        email_config=_email_status(),
        cron_schedules=[_build_cron_item(s) for s in cron],
    )


# =============================================================================
# POST /teacher/settings/test-email
# =============================================================================


@router.post(
    "/teacher/settings/test-email",
    response_model=MutationResponse[TestEmailResult],
)
def test_email(
    body: TestEmailBody,
    user: User = Depends(_require_teacher),
) -> MutationResponse[TestEmailResult]:
    target = (body.to or "").strip() or (user.email or "")
    if not target:
        raise _validation_error("email_required", "Test için bir e-posta adresi gerekli.")

    ok = send_email(
        to=target,
        template="teacher_new_request",
        ctx={
            "teacher": user,
            "student": user,
            "request": type("R", (), {
                "type": type("T", (), {"value": "question"})(),
                "task": None,
                "proposed_count": None,
                "proposed_book": None,
                "proposed_section": None,
                "message": "Bu bir test e-postasıdır. Mail yapılandırmanız çalışıyor.",
            })(),
            "type_label": "Test E-postası",
        },
    )
    if ok:
        message = f"Test e-postası gönderildi: {target}"
    elif not app_settings.email_enabled:
        message = "E-posta gönderimi devre dışı (EMAIL_ENABLED=false)."
    elif not app_settings.smtp_host:
        message = "SMTP_HOST tanımlı değil."
    else:
        message = "Test e-postası gönderilemedi. Sunucu loglarında ayrıntı vardır."

    return MutationResponse[TestEmailResult](
        data=TestEmailResult(sent=bool(ok), to=target, message=message),
        invalidate=_invalidate_settings(user.id),
    )


# =============================================================================
# PATCH /teacher/settings/cron/{schedule_id}
# =============================================================================


@router.patch(
    "/teacher/settings/cron/{schedule_id}",
    response_model=MutationResponse[CronScheduleItem],
)
def update_cron(
    schedule_id: int,
    body: CronSchedulePatchBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[CronScheduleItem]:
    sch = db.get(CronSchedule, schedule_id)
    if not sch:
        raise _not_found("cron_not_found", "Cron zamanlaması bulunamadı.")

    if body.hour is not None:
        if not (0 <= body.hour <= 23):
            raise _validation_error("invalid_hour", "Saat 0-23 aralığında olmalı.")
        sch.hour = body.hour
    if body.minute is not None:
        if not (0 <= body.minute <= 59):
            raise _validation_error("invalid_minute", "Dakika 0-59 aralığında olmalı.")
        sch.minute = body.minute
    if body.clear_day_of_week:
        sch.day_of_week = None
    elif body.day_of_week is not None:
        if not (0 <= body.day_of_week <= 6):
            raise _validation_error("invalid_day_of_week", "Hafta günü 0-6 aralığında olmalı.")
        sch.day_of_week = body.day_of_week
    if body.enabled is not None:
        sch.enabled = bool(body.enabled)

    db.commit()
    db.refresh(sch)
    return MutationResponse[CronScheduleItem](
        data=_build_cron_item(sch),
        invalidate=_invalidate_settings(user.id),
    )


# =============================================================================
# POST /teacher/settings/cron/run-now
# =============================================================================


@router.post(
    "/teacher/settings/cron/run-now",
    response_model=MutationResponse[CronRunNowResult],
)
def run_cron_now(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> MutationResponse[CronRunNowResult]:
    from app.services.cron_runner import tick as cron_tick
    from app.services.notification_dispatcher import dispatch_pending

    try:
        results = cron_tick(db, now=datetime.now(timezone.utc), force=True)
        disp = dispatch_pending(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal",
                "code": "cron_run_failed",
                "message": f"Manuel cron çalıştırma hatası: {e}",
            },
        )

    if results:
        summary = _summarize_run(results)
    else:
        summary = (
            "Manuel tetikleme: hiç açık bildirim türü bulunamadı. "
            "Aşağıdaki tabloda 'Durum' sütununu kontrol edin."
        )
    sent = int(disp.get("sent", 0) or 0)
    suppressed = int(disp.get("suppressed", 0) or 0)
    return MutationResponse[CronRunNowResult](
        data=CronRunNowResult(summary=summary, sent=sent, suppressed=suppressed),
        invalidate=_invalidate_settings(user.id),
    )


# =============================================================================
# GET /teacher/usage/current
# =============================================================================


@router.get("/teacher/usage/current", response_model=TeacherUsageResponse)
def teacher_usage_current(
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
) -> TeacherUsageResponse:
    is_independent = user.institution_id is None

    # Plan + kind referans tabloları (her durumda gönderiyoruz)
    plan_allocations = [
        PlanAllocationItem(plan_code=code, monthly_credits=credits)
        for code, credits in PLAN_ALLOCATIONS.items()
    ]
    kind_costs = [
        UsageBreakdownItem(
            kind=k.value,
            label=USAGE_KIND_LABELS_TR.get(k, k.value),
            credits=0,
            cost_per_call=KIND_CREDITS.get(k, 1),
        )
        for k in UsageKind
    ]

    if not is_independent:
        return TeacherUsageResponse(
            is_independent=False,
            institution_id=user.institution_id,
            account=None,
            breakdown=[],
            daily_series=[],
            recent_events=[],
            plan_allocations=plan_allocations,
            kind_costs=kind_costs,
        )

    owner = CreditOwner.for_user(user)
    period = current_period()
    account = get_or_create_account(db, owner=owner, period=period)
    db.commit()

    breakdown_raw = usage_breakdown_by_kind(db, owner=owner, period=period)
    breakdown = [
        UsageBreakdownItem(
            kind=k,
            label=USAGE_KIND_LABELS_TR.get(UsageKind(k), k) if k in {x.value for x in UsageKind} else k,
            credits=int(c),
            cost_per_call=KIND_CREDITS.get(UsageKind(k), 1) if k in {x.value for x in UsageKind} else 1,
        )
        for k, c in sorted(breakdown_raw.items(), key=lambda kv: -kv[1])
    ]

    daily = daily_usage_series(db, owner=owner, days=30)
    series = [UsageDailyPoint(date=d, credits=int(c)) for d, c in daily]

    events_raw = recent_events(db, owner=owner, limit=50)
    events: list[UsageEventItem] = []
    for ev in events_raw:
        try:
            meta = json.loads(ev.metadata_json) if ev.metadata_json else None
        except (TypeError, ValueError):
            meta = None
        events.append(UsageEventItem(
            id=ev.id,
            kind=ev.kind.value,
            label=USAGE_KIND_LABELS_TR.get(ev.kind, ev.kind.value),
            credits=int(ev.credits or 0),
            occurred_at=ev.occurred_at,
            actor_user_id=ev.actor_user_id,
            metadata=meta if isinstance(meta, dict) else None,
        ))

    account_dto = UsagePeriodAccount(
        period=account.period_year_month,
        plan_code=account.plan_code,
        allocated_credits=int(account.allocated_credits),
        used_credits=int(account.used_credits),
        bonus_credits=int(account.bonus_credits),
        remaining_credits=int(account.remaining_credits),
        usage_pct=int(account.usage_pct),
        hard_block_enabled=bool(account.hard_block_enabled),
        blocked_until=account.blocked_until,
        warn_80_sent_at=account.warn_80_sent_at,
        is_currently_blocked=account.is_currently_blocked(),
    )

    return TeacherUsageResponse(
        is_independent=True,
        institution_id=None,
        account=account_dto,
        breakdown=breakdown,
        daily_series=series,
        recent_events=events,
        plan_allocations=plan_allocations,
        kind_costs=kind_costs,
    )
