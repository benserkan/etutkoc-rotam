# -*- coding: utf-8 -*-
"""Haftalık koç raporu — API v2 router (2026-08-19).

"Haftalık rapor oluştur" butonu: `weekly_coach_report` servisi pencereyi seçer
(programın işlendiği son güne kadar 7 gün), tüm analizleri toplar, kural
motoruyla seans gündemi üretir ve CoachingReport olarak saklar. HTML görünüm
her istekte aynı formatla data_json'dan üretilir (saklanmaz).

AI gündemi (KS4): POST /ai-agenda — kredili (AI_COACHING_INSIGHT), sonuç rapora
cache'lenir; sonraki görüntülemeler ücretsiz.

Sahiplik dışı her şey 404. Veli/öğrenci erişemez (koç-özel).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import CoachingReport, CoachingSession, User, UserRole
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.coaching_report import (
    CoachingReportCreateBody,
    CoachingReportDetail,
    CoachingReportListResponse,
    CoachingReportRow,
    ReportAgendaItem,
)
from app.routes.api_v2.schemas.common import MutationResponse
from app.services import weekly_coach_report as wcr

router = APIRouter(prefix="/teacher", tags=["v2-coaching-reports"])


def _require_teacher(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "role_required",
            "message": "Bu uç yalnız koç hesabıyla kullanılabilir.",
        })
    return user


def _get_owned_student(db: Session, student_id: int, teacher_id: int) -> User:
    st = (db.query(User)
          .filter(User.id == student_id, User.role == UserRole.STUDENT,
                  User.teacher_id == teacher_id)
          .first())
    if not st:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "student_not_found",
            "message": "Öğrenci bulunamadı.",
        })
    return st


def _get_owned_report(db: Session, report_id: int, teacher_id: int) -> CoachingReport:
    r = (db.query(CoachingReport)
         .join(User, User.id == CoachingReport.student_id)
         .filter(CoachingReport.id == report_id, User.teacher_id == teacher_id)
         .first())
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "report_not_found",
            "message": "Rapor bulunamadı.",
        })
    return r


def _agenda_items(raw: list[dict]) -> list[ReportAgendaItem]:
    return [ReportAgendaItem(key=a.get("key"), title=str(a.get("title") or ""),
                             detail=str(a.get("detail") or ""), severity=a.get("severity"))
            for a in raw]


def _report_row(db: Session, r: CoachingReport) -> CoachingReportRow:
    n_sessions = (db.query(func.count(CoachingSession.id))
                  .filter(CoachingSession.report_id == r.id).scalar() or 0)
    return CoachingReportRow(
        id=r.id, week_start=r.week_start.isoformat(), week_end=r.week_end.isoformat(),
        version=r.version, generated_at=r.generated_at,
        has_ai_agenda=bool(r.ai_agenda_json), agenda_count=len(wcr.load_agenda(r)),
        session_count=int(n_sessions),
    )


def _report_detail(db: Session, r: CoachingReport) -> CoachingReportDetail:
    st = db.get(User, r.student_id)
    ai = wcr.load_ai_agenda(r)
    ai_meta: dict = {}
    if r.ai_agenda_json:
        try:
            ai_meta = json.loads(r.ai_agenda_json)
            if not isinstance(ai_meta, dict):
                ai_meta = {}
        except (ValueError, TypeError):
            ai_meta = {}
    return CoachingReportDetail(
        id=r.id, student_id=r.student_id, student_name=(st.full_name if st else ""),
        week_start=r.week_start.isoformat(), week_end=r.week_end.isoformat(),
        version=r.version, generated_at=r.generated_at,
        agenda=_agenda_items(wcr.load_agenda(r)),
        ai_agenda=(_agenda_items(ai) if ai else None),
        ai_summary=(ai_meta.get("summary") or None),
        ai_tips=[str(x) for x in (ai_meta.get("psychological_tips") or [])],
        ai_watch_outs=[str(x) for x in (ai_meta.get("watch_outs") or [])],
        ai_generated_at=r.ai_generated_at,
    )


@router.get("/students/{student_id}/weekly-reports", response_model=CoachingReportListResponse)
def list_weekly_reports_v2(
    student_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    _get_owned_student(db, student_id, user.id)
    rows = (db.query(CoachingReport)
            .filter(CoachingReport.student_id == student_id)
            .order_by(CoachingReport.week_end.desc(), CoachingReport.version.desc())
            .limit(30).all())
    return CoachingReportListResponse(rows=[_report_row(db, r) for r in rows])


@router.post("/students/{student_id}/weekly-reports", response_model=MutationResponse[CoachingReportRow])
def create_weekly_report_v2(
    student_id: int,
    body: CoachingReportCreateBody,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Haftalık raporu üret (kredisiz — kural motoru). Aynı hafta → yeni sürüm."""
    student = _get_owned_student(db, student_id, user.id)
    week_start = week_end = None
    days = body.days or wcr.DEFAULT_DAYS
    if not (3 <= days <= 31):
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "invalid_days",
            "message": "Gün sayısı 3-31 arası olmalı.",
        })
    if body.week_end:
        try:
            week_end = date.fromisoformat(body.week_end.strip())
        except ValueError:
            raise HTTPException(status_code=422, detail={
                "error": "validation", "code": "invalid_date",
                "message": "Geçersiz tarih. YYYY-MM-DD bekleniyor.",
            })
        week_start = week_end - timedelta(days=days - 1)
    else:
        ws, we = wcr.default_window(db, student, days=days)
        week_start, week_end = ws, we
    r = wcr.create_report(db, user, student, week_start=week_start, week_end=week_end)
    db.commit()
    db.refresh(r)
    return MutationResponse[CoachingReportRow](
        data=_report_row(db, r),
        invalidate=[f"teacher:{user.id}:students:{student.id}:weekly-reports"],
    )


@router.get("/weekly-reports/{report_id}", response_model=CoachingReportDetail)
def get_weekly_report_v2(
    report_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    r = _get_owned_report(db, report_id, user.id)
    return _report_detail(db, r)


@router.get("/weekly-reports/{report_id}/html")
def get_weekly_report_html_v2(
    report_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Rapor HTML görünümü (yeni sekme; yazdır → PDF). data_json'dan her istekte üretilir."""
    r = _get_owned_report(db, report_id, user.id)
    data = wcr.load_data(r)
    html = wcr.render_html(
        data, wcr.load_agenda(r), wcr.load_ai_agenda(r),
        report_id=r.id, version=r.version,
        session_url=f"/teacher/students/{r.student_id}?report={r.id}#sessions",
    )
    return HTMLResponse(content=html)


@router.get("/weekly-reports/{report_id}/parent-html")
def get_weekly_report_parent_html_v2(
    report_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Raporun VELİ SÜRÜMÜ (sade, olumlu dil; koç gündemi/mesajlar yok).

    Koç açar, yazdırır/PDF'ler ve veliyle paylaşır. Aynı data_json'dan üretilir.
    """
    from app.services.weekly_parent_report import render_parent_html

    r = _get_owned_report(db, report_id, user.id)
    return HTMLResponse(content=render_parent_html(wcr.load_data(r)))


@router.post("/weekly-reports/{report_id}/ai-agenda", response_model=CoachingReportDetail)
def generate_report_ai_agenda_v2(
    report_id: int,
    user: User = Depends(_require_teacher),
    db: Session = Depends(get_db),
):
    """Rapor verisinden AI seans gündemi üret (KS4 kredisi: AI_COACHING_INSIGHT).

    Sonuç rapora cache'lenir (has_ai_agenda) — sonraki görüntülemeler ücretsiz.
    KS4 içgörü cache'i de bayatlatılmaz; bu rapor-yerel bir gündemdir.
    """
    from app.models import UsageKind
    from app.routes.api_v2.teacher import _ai_credit_exhausted_error, _require_ai_premium
    from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
    from app.services.ai_coaching_insight import generate_report_agenda
    from app.services.credits import CreditBlocked, CreditOwner, consume_credits

    r = _get_owned_report(db, report_id, user.id)
    student = db.get(User, r.student_id)
    _require_ai_premium(db, user)
    if user.ai_capture_consent_at is None:
        raise HTTPException(status_code=403, detail={
            "error": "forbidden", "code": "consent_required",
            "message": "AI özellikleri için önce açık rıza vermelisiniz.",
        })

    data = wcr.load_data(r)
    bundle = wcr.insight_bundle(data, wcr.load_agenda(r))
    prev_sessions = [
        {"session_date": s.session_date.isoformat(), "agenda": s.agenda,
         "coach_note": s.coach_note, "next_change": s.next_change}
        for s in (db.query(CoachingSession)
                  .filter(CoachingSession.student_id == r.student_id)
                  .order_by(CoachingSession.session_date.desc()).limit(4).all())
    ]

    # Kilit hijyeni: uzun AI çağrısı öncesi açık işlem bırakma (oku + commit,
    # dışarıda çağır, kısa atomik yaz) — parent_commentary deseni.
    db.commit()
    owner = CreditOwner.for_user(user)
    out: dict | None = None
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_COACHING_INSIGHT,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            out = generate_report_agenda(student.full_name if student else "Öğrenci", bundle, prev_sessions)
            ctx.set_metadata({"report_id": r.id, "student_id": r.student_id, "kind": "weekly_report_agenda"})
    except CreditBlocked as e:
        db.rollback()
        raise _ai_credit_exhausted_error(user, e.message)
    except AIInvalidResponse as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={
            "error": "validation", "code": "agenda_unreadable",
            "message": f"Gündem üretilemedi: {e}",
        })
    except AIServiceUnavailable as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail={
            "error": "upstream_unavailable", "code": "ai_unavailable",
            "message": f"AI servisi şu an kullanılamıyor: {e}",
        })

    r = _get_owned_report(db, report_id, user.id)  # taze satır (commit sonrası)
    r.ai_agenda_json = json.dumps(out, ensure_ascii=False)
    r.ai_generated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(r)
    return _report_detail(db, r)
