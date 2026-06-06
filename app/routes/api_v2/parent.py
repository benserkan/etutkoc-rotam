"""API v2 — Veli (PARENT) endpoint'leri (Dalga 5 Paket 1+2).

Paket 1 (login-gerekli):
  GET  /api/v2/parent/dashboard              → ParentDashboardResponse
  GET  /api/v2/parent/students/{id}          → ParentStudentOverviewResponse
  GET  /api/v2/parent/students/{id}/week     → ParentWeekResponse
  GET  /api/v2/parent/notifications          → ParentNotificationsResponse
  GET  /api/v2/parent/settings               → ParentSettingsResponse
  POST /api/v2/parent/settings/preferences   → MutationResponse[ParentPreferencesInfo]
  POST /api/v2/parent/settings/students/{id}/mute  → MutationResponse[ParentChildLink]
  POST /api/v2/parent/settings/whatsapp/start      → MutationResponse[ParentWhatsAppInfo]
  POST /api/v2/parent/settings/whatsapp/verify     → MutationResponse[ParentWhatsAppInfo]
  POST /api/v2/parent/settings/whatsapp/disable    → MutationResponse[ParentWhatsAppInfo]

Paket 2 (public endpoint'ler, P2'de doldurulacak):
  GET  /api/v2/parent/invitation/{token}            → ParentInvitationInfo
  POST /api/v2/parent/invitation/{token}/accept     → ParentInvitationAcceptResult
  GET  /api/v2/parent/unsubscribe/{token}           → ParentUnsubscribeResult

GİZLİLİK:
- Tüm /students/{id} endpoint'leri parent_view.assert_parent_can_view() ile
  KVKK guard'lar; bağ yoksa **404 not_found** (403 değil — sızıntı önleme).
- Veri yapısı/sorgu Jinja services'le birebir aynı (kullanıcı kuralı).
"""
from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, time as dt_time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db
from app.models import (
    NOTIFICATION_KIND_LABELS,
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    PARENT_RELATION_LABELS,
    ParentNotificationPref,
    ParentPhoneVerification,
    ParentSessionLog,
    ParentStudentLink,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import (
    _auth_error,
    get_current_user_v2,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.parent import (
    ParentBillingMonth,
    ParentBillingSummary,
    ParentChildLink,
    ParentDashboardResponse,
    ParentInvitationAcceptBody,
    ParentInvitationAcceptResult,
    ParentInvitationInfo,
    ParentMuteBody,
    ParentNotificationItem,
    ParentNotificationsResponse,
    ParentPaymentItem,
    ParentPreferencesBody,
    ParentPreferencesInfo,
    ParentSessionItem,
    ParentSessionsResponse,
    ParentSettingsResponse,
    ParentStudentOverviewResponse,
    ParentUnsubscribeResult,
    ParentWeekResponse,
    ParentWhatsAppInfo,
    ParentWhatsAppStartBody,
    ParentWhatsAppVerifyBody,
    WeeklyReportResponse,
)
from app.services.parent_invitation import (
    can_register_parent_email,
    consume_invitation,
    find_user_by_email,
    lookup_token,
)
from app.services.parent_view import (
    ParentAccessDenied,
    assert_parent_can_view,
    list_parent_students,
    list_recent_notifications,
    student_overview,
    student_week,
)
from app.services.security import hash_password
from app.services.whatsapp import normalize_phone, send_otp


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parent", tags=["api-v2-parent"])


# =============================================================================
# Auth dep — _require_parent (rol kapısı)
# =============================================================================


def _require_parent(user: User = Depends(get_current_user_v2)) -> User:
    """PARENT rolü zorunlu. Aksi halde 403 role_required."""
    if user.role != UserRole.PARENT:
        raise _auth_error(
            "Bu işlem sadece veliler içindir.",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _client_meta(request) -> tuple[str | None, str | None]:
    """ParentSessionLog audit için IP + UA."""
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request.headers else None
    return ip, ua


def _invalidate_self() -> list[str]:
    """Veli mutation'larında invalidate edilecek queryKey prefix'leri."""
    return ["parent:me"]


# =============================================================================
# Dashboard
# =============================================================================


@router.get("/dashboard", response_model=ParentDashboardResponse)
def parent_dashboard_v2(
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veliye bağlı tüm çocuklar + her çocuğun son deneme özeti."""
    from sqlalchemy import desc, func
    from app.models.exam_result import ExamResult

    children = list_parent_students(db, user)
    if not children:
        return ParentDashboardResponse(children=children)

    # Her çocuk için son deneme + toplam sayım — tek sorguda batch yükle
    student_ids = [c["student_id"] for c in children]

    # Toplam sayım
    counts = dict(
        db.query(ExamResult.student_id, func.count(ExamResult.id))
        .filter(ExamResult.student_id.in_(student_ids))
        .group_by(ExamResult.student_id)
        .all()
    )

    # En son deneme (her öğrenci için ayrı sorgu — basit ve hızlı; küçük sayıda çocuk)
    latest_by_student: dict[int, ExamResult] = {}
    for sid in student_ids:
        latest = (
            db.query(ExamResult)
            .filter(ExamResult.student_id == sid)
            .order_by(desc(ExamResult.exam_date), desc(ExamResult.created_at))
            .first()
        )
        if latest is not None:
            latest_by_student[sid] = latest

    # Children dict'lerine yeni alanları enjekte et
    for c in children:
        sid = c["student_id"]
        c["latest_exam_count"] = int(counts.get(sid, 0))
        latest = latest_by_student.get(sid)
        if latest is not None:
            c["latest_exam_title"] = latest.title
            c["latest_exam_date"] = (
                latest.exam_date.isoformat() if latest.exam_date else None
            )
            c["latest_exam_net"] = float(latest.net) if latest.net is not None else None
            c["latest_exam_section"] = (
                latest.section.value if hasattr(latest.section, "value") else str(latest.section)
                if latest.section else None
            )

    return ParentDashboardResponse(children=children)


# =============================================================================
# Student detail (read-only, KVKK guard'lı)
# =============================================================================


@router.get(
    "/students/{student_id}",
    response_model=ParentStudentOverviewResponse,
)
def parent_student_detail_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veliye gösterilecek öğrenci özet sayfası verisi.

    Eşdeğer Jinja: parent.py:267-282 (parent_student_detail).
    """
    try:
        data = student_overview(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "student_not_found",
                "message": "Öğrenci bulunamadı.",
            },
        )
    return data


@router.get("/students/{student_id}/topic-performance")
def parent_student_topic_performance_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veliye: çocuğun ders → konu test performansı (çözülen test + D/Y + doğruluk).

    Gizlilik: assert_parent_can_view → 404 (bağ yoksa sızdırmaz).
    """
    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "student_not_found",
                    "message": "Öğrenci bulunamadı."},
        )
    from app.routes.api_v2.schemas.teacher import build_topic_performance_response
    from app.services.topic_performance import compute_topic_performance
    return build_topic_performance_response(compute_topic_performance(db, student.id))


@router.get("/students/{student_id}/exams")
def parent_student_exams_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veliye: çocuğun TÜM deneme geçmişi (özet + liste).

    Denemeler veliyle PAYLAŞILIR (2026-06-01 kararı). Koça-özel deneme notu (note)
    gizlenir. Gizlilik: assert_parent_can_view → 404.
    """
    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "code": "student_not_found",
                    "message": "Öğrenci bulunamadı."},
        )
    from app.models.exam_result import ExamResult
    from app.routes.api_v2.teacher import _build_exam_row, _exam_section_options
    from app.routes.api_v2.schemas.teacher import (
        ExamListSummary, StudentExamListResponse,
    )
    exams = (
        db.query(ExamResult)
        .filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc())
        .all()
    )
    rows = []
    for e in exams:
        r = _build_exam_row(e, created_by_name=None)
        r.note = None  # koça-özel not veliye gösterilmez
        rows.append(r)
    nets = [e.net for e in exams]
    count = len(nets)
    last_net = nets[0] if nets else None
    first_net = nets[-1] if nets else None
    summary = ExamListSummary(
        count=count,
        avg_net=round(sum(nets) / count, 2) if count else 0.0,
        best_net=round(max(nets), 2) if nets else 0.0,
        last_net=last_net,
        first_net=first_net,
        trend_delta=round(last_net - first_net, 2) if (count >= 2) else None,
    )
    return StudentExamListResponse(
        summary=summary, rows=rows, section_options=_exam_section_options(),
    )


# ---------------------------------------------------------------------------
# P2b — AI veli içgörüsü (konu performansı + deneme → veliye analiz)
# Kredi öğrencinin KOÇUNUN havuzundan düşer; cache ile tekrar okuma ücretsiz.
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402


def _parent_insight_gate(db: Session, student: User):
    """Veli içgörüsü için (coach, ai_available, reason) döndür.

    Üretim öğrencinin koçunun ücretli paketi + AI onayı + kredisini kullanır.
    """
    from app.services.plans import ai_premium_allowed
    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    if coach is None:
        return None, False, "Bu öğrencinin bağlı bir koçu yok; analiz oluşturulamıyor."
    if not ai_premium_allowed(db, coach):
        return coach, False, "Yapay zekâ analizi koçun paketinde aktif değil."
    if coach.ai_capture_consent_at is None:
        return coach, False, "Koç henüz yapay zekâ onayını vermemiş; analiz oluşturulamıyor."
    return coach, True, None


def _current_solved_and_exams(db: Session, student: User) -> tuple[int, int]:
    """(çözülen test toplamı, deneme sayısı) — bayatlık hesabı için."""
    from app.services.topic_performance import compute_topic_performance
    from app.models.exam_result import ExamResult
    subjects = compute_topic_performance(db, student.id)
    solved = sum(s.tests_solved for s in subjects)
    exam_count = db.query(ExamResult).filter(ExamResult.student_id == student.id).count()
    return solved, exam_count


def _parent_insight_to_data(row):
    from app.routes.api_v2.schemas.parent import ParentInsightData
    def _lst(s):
        if not s:
            return []
        try:
            v = _json.loads(s)
            return [str(x) for x in v] if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []
    return ParentInsightData(
        summary=row.summary or "",
        strengths=_lst(row.strengths),
        focus_areas=_lst(row.focus_areas),
        parent_tips=_lst(row.parent_tips),
        based_on_exams=row.based_on_exams,
        based_on_solved=row.based_on_solved,
        generated_at=row.generated_at,
    )


@router.get("/students/{student_id}/insight")
def parent_student_insight_get_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veli AI içgörüsü — cache'den OKU (ücretsiz). Yoksa insight=null.

    is_stale: kayıt sonrası yeni deneme/çözülen test eklendiyse True (yenile önerilir).
    ai_available: koç paketi + onayı uygun mu (üret butonu için).
    """
    from app.models.coaching_session import ParentInsight
    from app.routes.api_v2.schemas.parent import ParentInsightResponse
    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "student_not_found", "message": "Öğrenci bulunamadı."})

    _coach, ai_available, reason = _parent_insight_gate(db, student)
    row = db.query(ParentInsight).filter(ParentInsight.student_id == student.id).first()
    if row is None:
        return ParentInsightResponse(insight=None, is_stale=False, ai_available=ai_available, unavailable_reason=reason)
    solved, exam_count = _current_solved_and_exams(db, student)
    is_stale = (solved != row.based_on_solved) or (exam_count != row.based_on_exams)
    return ParentInsightResponse(
        insight=_parent_insight_to_data(row), is_stale=is_stale,
        ai_available=ai_available, unavailable_reason=reason,
    )


@router.post("/students/{student_id}/insight")
def parent_student_insight_generate_v2(
    student_id: int,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veli AI içgörüsü ÜRET/YENİLE — koçun kredisinden düşer.

    Konu performansı + deneme sonuçlarından veliye yönelik analiz. Yeterli veri
    yoksa 422. Koç paketi/onayı uygun değilse 403/402.
    """
    from app.models.coaching_session import ParentInsight
    from app.models.exam_result import ExamResult
    from app.models import UsageKind
    from app.routes.api_v2.schemas.parent import ParentInsightResponse
    from app.services.topic_performance import compute_topic_performance
    from app.services.ai_parent_insight import generate_parent_insight
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "student_not_found", "message": "Öğrenci bulunamadı."})

    coach, ai_available, reason = _parent_insight_gate(db, student)
    if not ai_available:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "ai_not_available",
            "message": reason or "Yapay zekâ analizi şu an kullanılamıyor."})

    subjects = compute_topic_performance(db, student.id)
    exams = (
        db.query(ExamResult).filter(ExamResult.student_id == student.id)
        .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc()).limit(8).all()
    )
    if not subjects and not exams:
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "not_enough_data",
            "message": "Analiz için yeterli veri yok. Çocuk test çözüp doğru/yanlış girdikçe veya deneme sonucu eklendikçe oluşturulabilir."})

    # Prompt verisi (zorlandığı/iyi konular)
    subj_payload: list[dict] = []
    for s in subjects:
        weak = [{"name": t.topic_name, "accuracy_pct": t.accuracy_pct}
                for t in s.topics if t.accuracy_pct is not None and t.accuracy_pct < 50][:3]
        strong = [{"name": t.topic_name, "accuracy_pct": t.accuracy_pct}
                  for t in s.topics if t.accuracy_pct is not None and t.accuracy_pct >= 70][:2]
        subj_payload.append({
            "subject_name": s.subject_name, "accuracy_pct": s.accuracy_pct,
            "tests_solved": s.tests_solved, "weak_topics": weak, "strong_topics": strong,
        })
    from app.models import EXAM_SECTION_LABELS
    exam_payload = [
        {"exam_date": e.exam_date.isoformat(),
         "section_label": EXAM_SECTION_LABELS.get(e.section, str(e.section)), "net": e.net}
        for e in exams
    ]
    solved = sum(s.tests_solved for s in subjects)

    owner = CreditOwner.for_user(coach)
    insight: dict | None = None
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_PARENT_INSIGHT,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            insight = generate_parent_insight(student.full_name, subj_payload, exam_payload)
            ctx.set_metadata({"student_id": student_id, "by": "parent"})
    except CreditBlocked:
        db.rollback()
        raise HTTPException(status_code=402, detail={
            "error": "payment_required", "code": "ai_credit_exhausted",
            "message": "Koçun yapay zekâ kredisi bu ay için doldu. Daha sonra tekrar deneyin."})
    except AIInvalidResponse:
        db.rollback()
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "insight_unreadable",
            "message": "Analiz oluşturulamadı, lütfen tekrar deneyin."})
    except AIServiceUnavailable:
        db.rollback()
        raise HTTPException(status_code=502, detail={
            "error": "upstream_unavailable", "code": "ai_unavailable",
            "message": "Yapay zekâ servisi şu an kullanılamıyor, birkaç dakika sonra deneyin."})

    row = db.query(ParentInsight).filter(ParentInsight.student_id == student.id).first()
    if row is None:
        row = ParentInsight(student_id=student.id)
        db.add(row)
    row.generated_by_id = user.id
    row.summary = insight["summary"]
    row.strengths = _json.dumps(insight["strengths"], ensure_ascii=False)
    row.focus_areas = _json.dumps(insight["focus_areas"], ensure_ascii=False)
    row.parent_tips = _json.dumps(insight["parent_tips"], ensure_ascii=False)
    row.based_on_exams = len(exams)
    row.based_on_solved = solved
    db.commit()
    db.refresh(row)
    return ParentInsightResponse(
        insight=_parent_insight_to_data(row), is_stale=False, ai_available=True, unavailable_reason=None,
    )


@router.get(
    "/students/{student_id}/week",
    response_model=ParentWeekResponse,
)
def parent_student_week_v2(
    student_id: int,
    start: str | None = Query(None, description="YYYY-MM-DD; yoksa bugün"),
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """7 günlük read-only program.

    Eşdeğer Jinja: parent.py:285-309 (parent_student_week).
    """
    today = date.today()
    if start:
        try:
            start_date = date.fromisoformat(start)
        except ValueError:
            start_date = today
    else:
        # WP4 — Veli sayfası açılınca aktif program varsa onun başlangıcına snap.
        # Yoksa bugün — eski davranış (geri uyum).
        from app.services.weekly_program_service import get_active_program
        active_prog = get_active_program(
            db, student_id=student_id, today=today,
        )
        start_date = active_prog.start_date if active_prog else today
    try:
        data = student_week(db, user, student_id, start_date)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "student_not_found",
                "message": "Öğrenci bulunamadı.",
            },
        )
    return data


@router.get(
    "/students/{student_id}/weekly-report",
    response_model=WeeklyReportResponse,
)
def parent_student_weekly_report_v2(
    student_id: int,
    week_start: str | None = Query(
        None, description="YYYY-MM-DD (Pazartesi'ye snap'lenir); yoksa son tamamlanmış hafta"
    ),
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veliye doyurucu haftalık analiz raporu.

    İçerik: bu hafta özeti + GEÇEN HAFTAYA KIYAS + ders kırılımı (en çok çözülen /
    en çok aksatılan) + deneme net trendi + gün gün tamamlama + koç notları +
    sade-dil genel değerlendirme. Web + mobil paylaşır.

    `week_start` verilmezse en son TAMAMLANMIŞ hafta (geçen Pazartesi) gösterilir.
    Verilen tarih daima haftanın Pazartesi'sine snap'lenir.
    """
    from app.services.parent_weekly_report import build_weekly_report

    ws: date | None = None
    if week_start:
        try:
            ws = date.fromisoformat(week_start)
        except ValueError:
            ws = None
    try:
        data = build_weekly_report(db, user, student_id, ws)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "student_not_found",
                "message": "Öğrenci bulunamadı.",
            },
        )
    return data


# =============================================================================
# M4 — Veli seans hareketleri
# =============================================================================


@router.get(
    "/students/{student_id}/sessions",
    response_model=ParentSessionsResponse,
)
def parent_student_sessions_v2(
    student_id: int,
    months: int = Query(12, ge=1, le=36, description="Kapsam ay (1-36)"),
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Veli için seans hareketleri + tahsilat özeti.

    KVKK: koça-özel alanlar (coach_note, agenda, next_change, mood, tags,
    auto_snapshot, capture_source) response'a DAHİL DEĞİL. Veli yalnız
    tarih + status + duration + channel + ödeme görür.

    Aylık hesap servis tarafında compute edilir (modelde değil): her ay için
    status=DONE seans sayısı × cari ücret = tahakkuk; ödemeler period_month'a
    göre dağıtılır; bakiye = tahakkuk − ödeme.
    """
    try:
        student = assert_parent_can_view(db, user, student_id)
    except ParentAccessDenied:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "student_not_found",
                "message": "Öğrenci bulunamadı.",
            },
        )

    # Lokal import — döngü riski yok ama parent.py giriş yolu temiz.
    from datetime import date as _date
    from app.models.coach_billing import (
        COACH_PAYMENT_METHOD_LABELS,
        CoachPayment,
        CoachStudentRate,
    )
    from app.models.coaching_session import (
        COACHING_CHANNEL_LABELS,
        COACHING_STATUS_LABELS,
        CoachingSession,
        CoachingSessionStatus,
    )

    today = _date.today()
    # Pencere başı: months ay önceki ayın 1'i
    start_year = today.year
    start_month = today.month - (months - 1)
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    window_start = _date(start_year, start_month, 1)

    # Seanslar — en yeni → en eski
    sessions = (
        db.query(CoachingSession)
        .filter(
            CoachingSession.student_id == student.id,
            CoachingSession.session_date >= window_start,
        )
        .order_by(CoachingSession.session_date.desc(), CoachingSession.id.desc())
        .all()
    )

    session_items: list[ParentSessionItem] = []
    for s in sessions:
        session_items.append(ParentSessionItem(
            id=s.id,
            session_date=s.session_date,
            status=s.status.value,
            status_label=COACHING_STATUS_LABELS.get(s.status, s.status.value),
            duration_min=s.duration_min,
            channel=s.channel.value if s.channel else None,
            channel_label=COACHING_CHANNEL_LABELS.get(s.channel) if s.channel else None,
        ))

    # Cari ücret (öğrenci başına, koça-spesifik değil)
    rate_row = (
        db.query(CoachStudentRate)
        .filter(CoachStudentRate.student_id == student.id)
        .first()
    )
    fee = int(rate_row.session_fee) if rate_row else 0

    # Ödemeler — pencere içinde
    payments = (
        db.query(CoachPayment)
        .filter(
            CoachPayment.student_id == student.id,
            CoachPayment.paid_at >= window_start,
        )
        .order_by(CoachPayment.paid_at.desc(), CoachPayment.id.desc())
        .all()
    )

    # Aylık tahakkuk hesabı
    TR_MONTHS = [
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
        "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
    ]
    month_data: dict[str, dict[str, int]] = {}
    # months pencere init (boş aylar bile görünsün)
    cur_y, cur_m = start_year, start_month
    while (cur_y, cur_m) <= (today.year, today.month):
        key = f"{cur_y:04d}-{cur_m:02d}"
        month_data[key] = {"sessions_done": 0, "paid": 0}
        cur_m += 1
        if cur_m > 12:
            cur_m = 1
            cur_y += 1

    # DONE seansları aya dağıt
    for s in sessions:
        if s.status != CoachingSessionStatus.DONE:
            continue
        key = f"{s.session_date.year:04d}-{s.session_date.month:02d}"
        if key in month_data:
            month_data[key]["sessions_done"] += 1

    # Ödemeleri period_month'a göre dağıt; period_month yoksa paid_at'a düşür
    for p in payments:
        if p.period_month and p.period_month in month_data:
            key = p.period_month
        else:
            key = f"{p.paid_at.year:04d}-{p.paid_at.month:02d}"
        if key in month_data:
            month_data[key]["paid"] += int(p.amount)

    months_out: list[ParentBillingMonth] = []
    total_accrued = 0
    total_paid = 0
    for key in sorted(month_data.keys()):
        y, m = key.split("-")
        label = f"{TR_MONTHS[int(m) - 1]} {y}"
        sd = month_data[key]["sessions_done"]
        pa = month_data[key]["paid"]
        accrued = sd * fee
        total_accrued += accrued
        total_paid += pa
        months_out.append(ParentBillingMonth(
            period_month=key,
            period_label=label,
            sessions_done=sd,
            session_fee=fee,
            accrued=accrued,
            paid=pa,
            balance=accrued - pa,
        ))

    payment_items: list[ParentPaymentItem] = []
    for p in payments[:50]:  # en yeni 50 ödeme
        payment_items.append(ParentPaymentItem(
            id=p.id,
            paid_at=p.paid_at,
            amount=int(p.amount),
            method=p.method.value,
            method_label=COACH_PAYMENT_METHOD_LABELS.get(p.method, p.method.value),
            period_month=p.period_month,
            note=p.note,
        ))

    return ParentSessionsResponse(
        student_id=student.id,
        student_name=student.full_name,
        sessions=session_items,
        billing=ParentBillingSummary(
            session_fee=fee,
            total_accrued=total_accrued,
            total_paid=total_paid,
            open_balance=total_accrued - total_paid,
            months=months_out,
            payments=payment_items,
        ),
    )


# =============================================================================
# Notifications
# =============================================================================


@router.get("/notifications", response_model=ParentNotificationsResponse)
def parent_notifications_v2(
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Bildirim geçmişi — son 100.

    Eşdeğer Jinja: parent.py:315-325 (parent_notifications).
    """
    items = list_recent_notifications(db, user, limit=100)
    return ParentNotificationsResponse(items=items, total=len(items))


# =============================================================================
# Settings — read
# =============================================================================


def _format_time(t: dt_time | None, default: str) -> str:
    if t is None:
        return default
    return f"{t.hour:02d}:{t.minute:02d}"


def _build_preferences(pref: ParentNotificationPref | None) -> ParentPreferencesInfo:
    """ParentNotificationPref ORM → Pydantic. P0: e-posta + WA kanalları ayrı."""
    if pref is None:
        # Yeni veli — varsayılan e-posta açık, WhatsApp kapalı (opt-in)
        return ParentPreferencesInfo(
            daily_summary_enabled=True,
            weekly_report_enabled=True,
            empty_day_alert_enabled=True,
            drop_alert_enabled=True,
            new_program_alert_enabled=True,
            teacher_note_enabled=True,
            exam_approaching_enabled=True,
            daily_summary_wa_enabled=False,
            weekly_report_wa_enabled=False,
            empty_day_alert_wa_enabled=False,
            drop_alert_wa_enabled=False,
            new_program_alert_wa_enabled=False,
            teacher_note_wa_enabled=False,
            exam_approaching_wa_enabled=False,
            child_whatsapp_consent=False,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            unsubscribed_at=None,
        )
    return ParentPreferencesInfo(
        daily_summary_enabled=pref.daily_summary_enabled,
        weekly_report_enabled=pref.weekly_report_enabled,
        empty_day_alert_enabled=pref.empty_day_alert_enabled,
        drop_alert_enabled=pref.drop_alert_enabled,
        new_program_alert_enabled=pref.new_program_alert_enabled,
        teacher_note_enabled=pref.teacher_note_enabled,
        exam_approaching_enabled=pref.exam_approaching_enabled,
        daily_summary_wa_enabled=bool(getattr(pref, "daily_summary_wa_enabled", False)),
        weekly_report_wa_enabled=bool(getattr(pref, "weekly_report_wa_enabled", False)),
        empty_day_alert_wa_enabled=bool(getattr(pref, "empty_day_alert_wa_enabled", False)),
        drop_alert_wa_enabled=bool(getattr(pref, "drop_alert_wa_enabled", False)),
        new_program_alert_wa_enabled=bool(getattr(pref, "new_program_alert_wa_enabled", False)),
        teacher_note_wa_enabled=bool(getattr(pref, "teacher_note_wa_enabled", False)),
        exam_approaching_wa_enabled=bool(getattr(pref, "exam_approaching_wa_enabled", False)),
        child_whatsapp_consent=bool(getattr(pref, "child_whatsapp_consent", False)),
        quiet_hours_start=_format_time(pref.quiet_hours_start, "22:00"),
        quiet_hours_end=_format_time(pref.quiet_hours_end, "07:00"),
        unsubscribed_at=pref.unsubscribed_at,
    )


def _build_whatsapp(
    pref: ParentNotificationPref | None,
    pending: ParentPhoneVerification | None,
    *,
    is_dev_stub: bool = False,
) -> ParentWhatsAppInfo:
    enabled = bool(pref and pref.whatsapp_enabled and pref.whatsapp_phone_verified_at)
    return ParentWhatsAppInfo(
        enabled=enabled,
        phone=pref.whatsapp_phone if pref else None,
        verified_at=pref.whatsapp_phone_verified_at if pref else None,
        pending_verify=pending is not None,
        pending_phone=pending.phone if pending else None,
        pending_expires_at=pending.expires_at if pending else None,
        # DEV stub mode: WA gönderim devre dışıysa veliye kodu kendi panelinde göster
        dev_test_code=(pending.code if pending and is_dev_stub else None),
    )


def _build_children(
    db: Session, parent_id: int,
) -> list[ParentChildLink]:
    links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.student))
        .filter(ParentStudentLink.parent_id == parent_id)
        .all()
    )
    out: list[ParentChildLink] = []
    for link in links:
        if not link.student:
            continue
        rel = link.relation
        out.append(
            ParentChildLink(
                student_id=link.student_id,
                full_name=link.student.full_name,
                relation=rel.value if rel else None,
                relation_label=PARENT_RELATION_LABELS.get(rel, "—") if rel else "—",
                is_primary=link.is_primary,
                muted=bool(link.muted),
            )
        )
    return out


@router.get("/settings", response_model=ParentSettingsResponse)
def parent_settings_v2(
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Tercih + WhatsApp durumu + çocuk listesi (mute toggle için).

    Eşdeğer Jinja: parent.py:384-428 (parent_settings).
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    pending = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.consumed_at.is_(None),
            ParentPhoneVerification.expires_at > datetime.now(timezone.utc),
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )

    from app.config import settings as app_settings
    is_dev_stub = bool(
        getattr(app_settings, "debug", False)
        and not getattr(app_settings, "whatsapp_enabled", False)
    )

    return ParentSettingsResponse(
        preferences=_build_preferences(pref),
        whatsapp=_build_whatsapp(pref, pending, is_dev_stub=is_dev_stub),
        children=_build_children(db, user.id),
    )


# =============================================================================
# Settings — preferences mutation
# =============================================================================


def _parse_time_str(s: str | None) -> tuple[int, int] | None:
    """'HH:MM' → (hour, minute) ya da None. Jinja parent.py:434-448 ile birebir."""
    if not s:
        return None
    s = s.strip()
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


@router.post(
    "/settings/preferences",
    response_model=MutationResponse[ParentPreferencesInfo],
)
def update_preferences_v2(
    body: ParentPreferencesBody,
    request: Request,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """7 toggle + sessiz saatler. unsubscribed_at varsa otomatik kalkar.

    Eşdeğer Jinja: parent.py:451-521 (update_preferences).
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref is None:
        pref = ParentNotificationPref(
            parent_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref)
        db.flush()

    pref.daily_summary_enabled = body.daily_summary
    pref.weekly_report_enabled = body.weekly_report
    pref.empty_day_alert_enabled = body.empty_day
    pref.new_program_alert_enabled = body.new_program
    pref.drop_alert_enabled = body.drop_alert
    pref.teacher_note_enabled = body.teacher_note
    pref.exam_approaching_enabled = body.exam_approaching

    # P0 — WhatsApp kanal toggle'ları
    pref.daily_summary_wa_enabled = body.daily_summary_wa
    pref.weekly_report_wa_enabled = body.weekly_report_wa
    pref.empty_day_alert_wa_enabled = body.empty_day_wa
    pref.new_program_alert_wa_enabled = body.new_program_wa
    pref.drop_alert_wa_enabled = body.drop_alert_wa
    pref.teacher_note_wa_enabled = body.teacher_note_wa
    pref.exam_approaching_wa_enabled = body.exam_approaching_wa
    pref.child_whatsapp_consent = body.child_whatsapp_consent

    qs = _parse_time_str(body.quiet_start)
    qe = _parse_time_str(body.quiet_end)
    if qs is None or qe is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "invalid_quiet_hours",
                "message": "Sessiz saat formatı geçersiz (HH:MM bekleniyor).",
            },
        )
    pref.quiet_hours_start = dt_time(qs[0], qs[1])
    pref.quiet_hours_end = dt_time(qe[0], qe[1])

    # Veli bu sayfadan tekrar ayar yapıyorsa unsubscribed durumu otomatik kalksın
    if pref.unsubscribed_at is not None:
        pref.unsubscribed_at = None

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id, action="preferences_updated", ip=ip, user_agent=ua,
    ))
    db.commit()

    return MutationResponse[ParentPreferencesInfo](
        data=_build_preferences(pref),
        invalidate=_invalidate_self(),
    )


# =============================================================================
# Settings — child mute mutation
# =============================================================================


@router.post(
    "/settings/students/{student_id}/mute",
    response_model=MutationResponse[ParentChildLink],
)
def toggle_child_mute_v2(
    student_id: int,
    body: ParentMuteBody,
    request: Request,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """Belirli çocuk için tüm bildirimleri sustur/aç.

    Eşdeğer Jinja: parent.py:524-565 (toggle_child_mute).
    """
    link = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.student))
        .filter(
            ParentStudentLink.parent_id == user.id,
            ParentStudentLink.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found",
                "code": "child_not_found",
                "message": "Çocuk bağlantısı bulunamadı.",
            },
        )

    link.muted = body.muted
    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id,
        action=f"child_{'muted' if body.muted else 'unmuted'}",
        ip=ip, user_agent=ua,
    ))
    db.commit()

    rel = link.relation
    return MutationResponse[ParentChildLink](
        data=ParentChildLink(
            student_id=link.student_id,
            full_name=link.student.full_name if link.student else f"#{student_id}",
            relation=rel.value if rel else None,
            relation_label=PARENT_RELATION_LABELS.get(rel, "—") if rel else "—",
            is_primary=link.is_primary,
            muted=bool(link.muted),
        ),
        invalidate=_invalidate_self(),
    )


# =============================================================================
# Settings — WhatsApp OTP flow
# =============================================================================


OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


def _generate_otp_code() -> str:
    """6 haneli, kriptografik güvenli OTP kodu."""
    return f"{secrets.randbelow(1_000_000):06d}"


@router.post(
    "/settings/whatsapp/start",
    response_model=MutationResponse[ParentWhatsAppInfo],
)
def whatsapp_start_v2(
    body: ParentWhatsAppStartBody,
    request: Request,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """OTP gönder. 60 sn cooldown + 10dk TTL.

    Eşdeğer Jinja: parent.py:580-656 (whatsapp_start).
    """
    normalized = normalize_phone(body.phone)
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "invalid_phone",
                "message": (
                    "Telefon numarası geçersiz. Türkiye numarası için 0532... "
                    "veya +90532... yazabilirsiniz."
                ),
            },
        )

    now = datetime.now(timezone.utc)
    recent = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.created_at
            > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )
    if recent and not recent.consumed_at:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "code": "otp_cooldown",
                "message": (
                    "Az önce kod gönderildi. Lütfen 1 dakika bekleyip tekrar deneyin."
                ),
            },
        )

    code = _generate_otp_code()
    ppv = ParentPhoneVerification(
        parent_id=user.id,
        phone=normalized,
        code=code,
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(ppv)
    db.flush()

    result = send_otp(to_phone=normalized, code=code)
    if not result.success:
        db.rollback()
        logger.warning(
            "WA OTP gönderimi başarısız: parent=%s phone=%s err=%s",
            user.id, normalized, result.error,
        )
        raise HTTPException(
            status_code=502,
            detail={
                "error": "bad_gateway",
                "code": "otp_send_failed",
                "message": (
                    "WhatsApp kodu gönderilemedi. Numaranızı kontrol edin veya "
                    "biraz sonra tekrar deneyin."
                ),
            },
        )

    # Audit log
    nl = NotificationLog(
        parent_id=user.id,
        student_id=None,
        kind=NotificationKind.OTP,
        channel=NotificationChannel.WHATSAPP,
        status=NotificationStatus.SENT,
        external_id=result.external_id,
        sent_at=now,
        subject=f"OTP → {normalized}",
    )
    db.add(nl)
    db.commit()

    # Freshly built whatsapp info (with pending)
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    from app.config import settings as app_settings
    is_dev_stub = bool(
        getattr(app_settings, "debug", False)
        and not getattr(app_settings, "whatsapp_enabled", False)
    )
    return MutationResponse[ParentWhatsAppInfo](
        data=_build_whatsapp(pref, ppv, is_dev_stub=is_dev_stub),
        invalidate=_invalidate_self(),
    )


@router.post(
    "/settings/whatsapp/verify",
    response_model=MutationResponse[ParentWhatsAppInfo],
)
def whatsapp_verify_v2(
    body: ParentWhatsAppVerifyBody,
    request: Request,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """OTP doğrula → pref güncelle.

    Eşdeğer Jinja: parent.py:659-738 (whatsapp_verify).
    """
    code = (body.code or "").strip()
    if not code or not code.isdigit() or len(code) != 6:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "invalid_code",
                "message": "Kod 6 hane olmalıdır.",
            },
        )

    now = datetime.now(timezone.utc)
    ppv = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.consumed_at.is_(None),
            ParentPhoneVerification.expires_at > now,
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )
    if not ppv:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "no_active_otp",
                "message": (
                    "Aktif bir doğrulama oturumu bulunamadı. "
                    "Lütfen tekrar telefonunuzu girin."
                ),
            },
        )

    if ppv.attempts >= OTP_MAX_ATTEMPTS:
        ppv.expires_at = now
        db.commit()
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "code": "otp_too_many_attempts",
                "message": "Çok fazla yanlış deneme. Yeni bir kod isteyin.",
            },
        )

    ppv.attempts += 1
    if not secrets.compare_digest(ppv.code, code):
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - ppv.attempts
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "otp_mismatch",
                "message": f"Kod yanlış. Kalan deneme hakkı: {max(remaining, 0)}.",
            },
        )

    # Başarılı
    ppv.consumed_at = now
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref is None:
        pref = ParentNotificationPref(
            parent_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref)
        db.flush()

    pref.whatsapp_phone = ppv.phone
    pref.whatsapp_phone_verified_at = now
    pref.whatsapp_enabled = True

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id, action="whatsapp_verified", ip=ip, user_agent=ua,
    ))
    db.commit()

    return MutationResponse[ParentWhatsAppInfo](
        data=_build_whatsapp(pref, None),
        invalidate=_invalidate_self(),
    )


@router.post(
    "/settings/whatsapp/disable",
    response_model=MutationResponse[ParentWhatsAppInfo],
)
def whatsapp_disable_v2(
    request: Request,
    user: User = Depends(_require_parent),
    db: Session = Depends(get_db),
):
    """WhatsApp kanalını kapat. İdempotent.

    Eşdeğer Jinja: parent.py:741-767 (whatsapp_disable).
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref:
        pref.whatsapp_enabled = False
        pref.whatsapp_phone = None
        pref.whatsapp_phone_verified_at = None

        ip, ua = _client_meta(request)
        db.add(ParentSessionLog(
            parent_id=user.id, action="whatsapp_disabled", ip=ip, user_agent=ua,
        ))
        db.commit()

    return MutationResponse[ParentWhatsAppInfo](
        data=_build_whatsapp(pref, None),
        invalidate=_invalidate_self(),
    )


# =============================================================================
# Public — Davet & Unsubscribe (P2)
# =============================================================================


def _invitation_error_http(error_code: str) -> HTTPException:
    """InvitationError → 400 with code + Turkish message."""
    messages = {
        "not_found": "Bu davet bağlantısı tanınmıyor.",
        "expired": "Davetin süresi dolmuş (7 gün geçerli). Lütfen yeni davet talep edin.",
        "consumed": "Bu davet zaten kullanılmış. Hesabınızı kullanarak giriş yapabilirsiniz.",
        "email_in_use_other_role": (
            "Bu e-posta adresi sistemde başka bir rolde kullanılıyor. "
            "Lütfen sizi davet eden eğitim koçunuza farklı bir e-posta ile davet talep edin."
        ),
        "password_too_short": "Şifre en az 8 karakter olmalıdır.",
        "kvkk_not_accepted": (
            "Hesap oluşturmak için aydınlatma metnini onaylamanız gereklidir."
        ),
        "name_required": "Ad-soyad en az 3 karakter olmalıdır.",
    }
    return HTTPException(
        status_code=400,
        detail={
            "error": "invalid",
            "code": error_code,
            "message": messages.get(error_code, "Davet kullanılamıyor."),
        },
    )


@router.get(
    "/invitation/{token}",
    response_model=ParentInvitationInfo,
)
def parent_invitation_info_v2(
    token: str,
    db: Session = Depends(get_db),
):
    """Davet token bilgisi (form prefill için).

    PUBLIC — auth gerekmez. Token'la bulunan davetin ad/email/student bilgisi
    + relation_label döner. Token yok/expired/consumed → 400 + InvitationError code.

    Eşdeğer Jinja: parent.py:95-113 (invitation_form).
    """
    result = lookup_token(db, token)
    if result.error:
        raise _invitation_error_http(result.error.value)

    inv = result.invitation
    return ParentInvitationInfo(
        token=inv.token,
        invited_email=inv.invited_email,
        student_full_name=inv.student.full_name if inv.student else "—",
        invited_by_full_name=inv.invited_by.full_name if inv.invited_by else "—",
        relation=inv.relation.value,
        relation_label=PARENT_RELATION_LABELS.get(inv.relation, "—"),
        is_primary=inv.is_primary,
        expires_at=inv.expires_at,
    )


@router.post(
    "/invitation/{token}/accept",
    response_model=ParentInvitationAcceptResult,
)
def parent_invitation_accept_v2(
    token: str,
    body: ParentInvitationAcceptBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Davet kabul + hesap oluşturma + auth cookie kurulumu.

    Akış (Jinja parent.py:131-236 ile birebir):
      1. Token doğrula
      2. Form validasyonu (name ≥3, password ≥8, password_confirm == password, KVKK)
      3. Email rol çakışması kontrolü (can_register_parent_email)
      4. Mevcut PARENT → link ekle (şifre/ad değişmez)
         Yeni email → User + ParentNotificationPref oluştur
      5. ParentStudentLink kur (UNIQUE check)
      6. consume_invitation
      7. ParentSessionLog audit (invitation_accepted / added_link + login)
      8. JWT token pair + cookies set
    """
    from app.services.jwt_auth import issue_token_pair
    from app.routes.api_v2.auth import _set_access_cookie, _set_refresh_cookie

    # 1. Token doğrula
    result = lookup_token(db, token)
    if result.error:
        raise _invitation_error_http(result.error.value)
    inv = result.invitation

    # 2. Form validasyonu (Jinja birebir)
    name = body.full_name.strip()
    if not name or len(name) < 3:
        raise _invitation_error_http("name_required")
    if len(body.password) < 8:
        raise _invitation_error_http("password_too_short")
    if body.password != body.password_confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "password_mismatch",
                "message": "Şifreler eşleşmiyor.",
            },
        )
    if not body.kvkk_accept:
        raise _invitation_error_http("kvkk_not_accepted")

    # 3. Email rol çakışması
    can_reg, conflict_role = can_register_parent_email(db, inv.invited_email)
    if not can_reg:
        role_label = "öğretmen" if conflict_role == UserRole.TEACHER else "öğrenci"
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid",
                "code": "email_in_use_other_role",
                "message": (
                    f"Bu e-posta adresi sistemde {role_label} olarak kullanılıyor. "
                    "Lütfen sizi davet eden eğitim koçunuza farklı bir e-posta ile davet talep edin."
                ),
            },
        )

    # 4. Mevcut PARENT mı yeni mi?
    parent_user = find_user_by_email(db, inv.invited_email)
    is_new_account = parent_user is None

    now = datetime.now(timezone.utc)

    # P0 — aktivasyondan gelen iletişim tercih matrisini ParentNotificationPref'e
    # uygula. Mevcut veli için sadece child_whatsapp_consent (KVKK güncelleme)
    # işlenir; ana tercihleri zaten ayarlar sayfasından yönetir.
    _np = body.notification_preferences or {}

    def _bool_pref(key: str, default: bool) -> bool:
        v = _np.get(key)
        if v is None:
            return default
        return bool(v)

    # P1 — telefon (opsiyonel; gönderilirse normalize edilip User.phone'a yazılır,
    # verified_at=None — doğrulama panelde banner'la başlatılır)
    phone_normalized: str | None = None
    if body.phone:
        from app.services.phone_service import normalize_e164_tr
        phone_normalized = normalize_e164_tr(body.phone)
        if not phone_normalized:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid",
                    "code": "invalid_phone",
                    "message": "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir.",
                },
            )

    if is_new_account:
        parent_user = User(
            email=inv.invited_email.strip().lower(),
            password_hash=hash_password(body.password),
            full_name=name,
            role=UserRole.PARENT,
            is_active=True,
            password_changed_at=now,
            must_change_password=False,
            phone=phone_normalized,
            # phone_verified_at=None — kullanıcı panelden OTP ile doğrulayacak
        )
        db.add(parent_user)
        db.flush()

        pref = ParentNotificationPref(
            parent_id=parent_user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
            # E-posta — default açık, aktivasyon ekranı kapatabilir
            daily_summary_enabled=_bool_pref("daily_summary_email", True),
            weekly_report_enabled=_bool_pref("weekly_report_email", True),
            empty_day_alert_enabled=_bool_pref("empty_day_email", True),
            drop_alert_enabled=_bool_pref("drop_alert_email", True),
            new_program_alert_enabled=_bool_pref("new_program_email", True),
            teacher_note_enabled=_bool_pref("teacher_note_email", True),
            exam_approaching_enabled=_bool_pref("exam_approaching_email", True),
            # WhatsApp — default kapalı, aktivasyon ekranı açabilir (opt-in)
            daily_summary_wa_enabled=_bool_pref("daily_summary_wa", False),
            weekly_report_wa_enabled=_bool_pref("weekly_report_wa", False),
            empty_day_alert_wa_enabled=_bool_pref("empty_day_wa", False),
            drop_alert_wa_enabled=_bool_pref("drop_alert_wa", False),
            new_program_alert_wa_enabled=_bool_pref("new_program_wa", False),
            teacher_note_wa_enabled=_bool_pref("teacher_note_wa", False),
            exam_approaching_wa_enabled=_bool_pref("exam_approaching_wa", False),
            child_whatsapp_consent=body.child_whatsapp_consent,
        )

        # Sessiz saat — opsiyonel; verilirse uygula
        qs = _parse_time_str(body.quiet_start) if body.quiet_start else None
        qe = _parse_time_str(body.quiet_end) if body.quiet_end else None
        if qs is not None:
            pref.quiet_hours_start = dt_time(qs[0], qs[1])
        if qe is not None:
            pref.quiet_hours_end = dt_time(qe[0], qe[1])

        db.add(pref)
    else:
        # Mevcut veli — yalnız child_whatsapp_consent'i bu davetin parent_id'sine
        # işle. Diğer tercihler ayarlar sayfasından yönetilir; aktivasyon
        # ekranındaki seçimler mevcut velinin kararlarını ezmez.
        existing_pref = (
            db.query(ParentNotificationPref)
            .filter(ParentNotificationPref.parent_id == parent_user.id)
            .first()
        )
        if existing_pref and body.child_whatsapp_consent:
            existing_pref.child_whatsapp_consent = True

    # 5. ParentStudentLink — UNIQUE kontrolü
    existing_link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.parent_id == parent_user.id,
            ParentStudentLink.student_id == inv.student_id,
        )
        .first()
    )
    if not existing_link:
        link = ParentStudentLink(
            parent_id=parent_user.id,
            student_id=inv.student_id,
            relation=inv.relation,
            is_primary=inv.is_primary,
            created_by_id=inv.invited_by_id,
        )
        db.add(link)

    # 6. consume_invitation
    consume_invitation(db, inv)

    # 7. Audit
    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=parent_user.id,
        action="invitation_accepted" if is_new_account else "invitation_added_link",
        ip=ip, user_agent=ua,
    ))
    # P0 — KVKK + iletişim tercihi v2 audit (yeni veli veya çocuk WA onayı verildi)
    if is_new_account or body.child_whatsapp_consent:
        db.add(ParentSessionLog(
            parent_id=parent_user.id,
            action="kvkk_consent_v2",
            ip=ip, user_agent=ua,
        ))
    db.add(ParentSessionLog(
        parent_id=parent_user.id,
        action="login", ip=ip, user_agent=ua,
    ))

    db.commit()

    # 8. JWT cookies — BFF auth
    pair = issue_token_pair(parent_user, now=now)
    _set_access_cookie(response, pair.access_token, pair.access_expires_in)
    _set_refresh_cookie(response, pair.refresh_token, pair.refresh_expires_in)

    return ParentInvitationAcceptResult(
        user_id=parent_user.id,
        full_name=parent_user.full_name,
        email=parent_user.email,
        is_new_account=is_new_account,
        redirect_url="/parent",
    )


@router.get("/unsubscribe/{token}", response_model=ParentUnsubscribeResult)
def parent_unsubscribe_v2(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Tek-tıkla bildirim kapatma — token-based, auth gerekmez.

    Eşdeğer Jinja: parent.py:331-378 (parent_unsubscribe).
    Tüm bildirim türlerini kapatır + WhatsApp'ı disable eder. INVITATION/OTP
    sistem mesajları yine gönderilebilir.
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.unsubscribe_token == token)
        .first()
    )
    if not pref:
        return ParentUnsubscribeResult(status="invalid")

    if pref.unsubscribed_at:
        return ParentUnsubscribeResult(status="already")

    pref.unsubscribed_at = datetime.now(timezone.utc)
    pref.daily_summary_enabled = False
    pref.weekly_report_enabled = False
    pref.empty_day_alert_enabled = False
    pref.drop_alert_enabled = False
    pref.new_program_alert_enabled = False
    pref.teacher_note_enabled = False
    pref.exam_approaching_enabled = False
    pref.whatsapp_enabled = False

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=pref.parent_id, action="unsubscribed", ip=ip, user_agent=ua,
    ))
    db.commit()

    return ParentUnsubscribeResult(status="unsubscribed")
