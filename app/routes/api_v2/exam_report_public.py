"""API v2 — Veliye bağlantıyla giden deneme analiz raporu (2026-11-13).

Login GEREKTİRMEZ; tahmin edilemez token (32 karakter) + 60 gün süre + koç
iptali. Sayfa: /rapor/{token} (Next.js). Ses Rota'nın sesiyle, ilk dinlemede
bir kez üretilir (koçun kredisi, 2), sonrası önbellekten ücretsiz; koçun
paketi/onayı uygun değilse sayfa telefonun kendi sesine düşer.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import ExamResult, User

router = APIRouter(prefix="/public/exam-report", tags=["v2-exam-report-public"])


class ReportSubject(BaseModel):
    name: str
    questions: int
    correct: int
    wrong: int
    blank: int
    net_text: str
    pct: int
    level: str
    level_label: str
    sentence: str


class ReportOpportunity(BaseModel):
    subject: str
    topic: str
    gain_text: str


class ReportHistoryExam(BaseModel):
    title: str
    date_tr: str
    net_text: str
    is_current: bool


class ReportHistoryRow(BaseModel):
    subject: str
    nets: list[str | None]
    direction: str | None = None


class ReportHistory(BaseModel):
    has_data: bool = False
    exams: list[ReportHistoryExam] = []
    rows: list[ReportHistoryRow] = []
    totals: list[str] = []


class ExamReportPublic(BaseModel):
    student_first: str
    student_gen: str
    exam_title: str
    exam_date_tr: str
    section_label: str | None = None
    brand_name: str
    brand_logo_url: str | None = None
    coach_name: str | None = None
    net_text: str
    correct: int
    wrong: int
    blank: int
    total_questions: int
    correct_pct: int
    headline: str
    trend_text: str
    delta_direction: str | None = None
    prev_net_text: str | None = None
    narrative: list[str]
    explain: str
    subjects: list[ReportSubject]
    history: ReportHistory
    opportunities: list[ReportOpportunity]
    opportunity_total_text: str | None = None
    opportunity_exam_count: int = 0
    tips: list[str]
    speech_text: str
    #: Rota'nın sesi kullanılabilir mi (hazır ya da üretilebilir). False →
    #: sayfa telefonun kendi sesini kullanır.
    voice_available: bool
    voice_ready: bool
    expires_at: str


class ReportVoiceResult(BaseModel):
    ready: bool
    fallback: bool = False
    message: str | None = None


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail={
        "error": "not_found", "code": "report_not_found",
        "message": "Bu rapor bağlantısının süresi dolmuş ya da koç tarafından kapatılmış."})


def _load(db: Session, token: str):
    from app.services.exam_parent_report import get_usable_by_token

    rep = get_usable_by_token(db, token)
    if rep is None:
        raise _not_found()
    exam = db.get(ExamResult, rep.exam_id)
    if exam is None:
        raise _not_found()
    return rep, exam


def _voice_gate(db: Session, exam: ExamResult) -> tuple[User | None, bool]:
    from app.routes.api_v2.parent import _parent_insight_gate

    student = db.get(User, exam.student_id)
    if student is None:
        return None, False
    coach, ok, _ = _parent_insight_gate(db, student)
    return coach, ok


@router.get("/{token}", response_model=ExamReportPublic)
def exam_report_view(token: str, db: Session = Depends(get_db)):
    from app.services.exam_parent_report import build_report_data

    rep, exam = _load(db, token)
    data = build_report_data(db, exam)
    _, gate_ok = _voice_gate(db, exam)
    voice_ready = bool(rep.audio_content_type) and rep.audio_signature == data["speech_signature"]
    rep.view_count = (rep.view_count or 0) + 1
    rep.last_viewed_at = datetime.now(timezone.utc)
    db.commit()
    return ExamReportPublic(
        **{k: v for k, v in data.items() if k in ExamReportPublic.model_fields},
        voice_available=voice_ready or gate_ok,
        voice_ready=voice_ready,
        expires_at=rep.expires_at.isoformat(),
    )


@router.post("/{token}/voice", response_model=ReportVoiceResult)
def exam_report_voice(token: str, db: Session = Depends(get_db)):
    """Rota'nın sesi — yalnız İLK istekte üretilir (koçun kredisi), sonra önbellek.

    Uzun TTS çağrısı açık DB işlemi içinde yapılmaz (kilit dersi)."""
    from app.models import UsageKind
    from app.services.ai_book_template import AIServiceUnavailable
    from app.services.credits import CreditBlocked, CreditOwner, check_credit_available, consume_credits
    from app.services.exam_parent_report import build_report_data
    from app.services.tts import synthesize_speech

    rep, exam = _load(db, token)
    data = build_report_data(db, exam)
    sig = data["speech_signature"]
    if rep.audio_content_type and rep.audio_signature == sig:
        return ReportVoiceResult(ready=True)

    coach, ok = _voice_gate(db, exam)
    if not ok or coach is None:
        return ReportVoiceResult(ready=False, fallback=True)
    owner = CreditOwner.for_user(coach)
    if not check_credit_available(db, owner=owner, kind=UsageKind.AI_PARENT_COMMENTARY_VOICE).ok:
        return ReportVoiceResult(ready=False, fallback=True)

    speech = data["speech_text"]
    rep_id = rep.id
    db.commit()
    try:
        audio, content_type = synthesize_speech(speech)
    except AIServiceUnavailable:
        return ReportVoiceResult(ready=False, fallback=True,
                                 message="Seslendirme şu an hazırlanamadı.")

    from app.models.exam_parent_report import ExamParentReport

    rep = db.get(ExamParentReport, rep_id)
    if rep is None:
        raise _not_found()
    if rep.audio_content_type and rep.audio_signature == sig:
        return ReportVoiceResult(ready=True)  # eşzamanlı istek üretti — ücretsiz
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_PARENT_COMMENTARY_VOICE,
            actor_user_id=None, autocommit=False,
        ) as ctx:
            ctx.set_metadata({"student_id": exam.student_id, "exam_id": exam.id, "by": "exam_report"})
        rep.audio = audio
        rep.audio_content_type = content_type
        rep.audio_signature = sig
        rep.audio_generated_at = datetime.now(timezone.utc)
        db.commit()
    except CreditBlocked:
        db.rollback()
        return ReportVoiceResult(ready=False, fallback=True)
    return ReportVoiceResult(ready=True)


@router.get("/{token}/audio")
def exam_report_audio(token: str, db: Session = Depends(get_db)):
    from sqlalchemy.orm import undefer

    from app.models.exam_parent_report import ExamParentReport

    rep, _ = _load(db, token)
    row = (db.query(ExamParentReport).options(undefer(ExamParentReport.audio))
           .filter(ExamParentReport.id == rep.id).first())
    if row is None or not row.audio or not row.audio_content_type:
        raise HTTPException(status_code=404, detail={
            "error": "not_found", "code": "audio_not_found", "message": "Henüz ses yok."})
    return Response(content=row.audio, media_type=row.audio_content_type,
                    headers={"Cache-Control": "private, max-age=0, no-store"})


@router.get("/{token}/pdf")
def exam_report_pdf(token: str, db: Session = Depends(get_db)):
    from app.services.exam_parent_report import build_report_data, pdf_filename, render_report_pdf

    _, exam = _load(db, token)
    data = build_report_data(db, exam)
    pdf = render_report_pdf(data)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{pdf_filename(data)}"',
        "Cache-Control": "private, max-age=0, no-store",
    })
