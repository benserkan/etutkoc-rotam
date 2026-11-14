"""API v2 — Veliye bağlantıyla giden deneme analiz raporu (2026-11-13).

Login GEREKTİRMEZ; tahmin edilemez token (32 karakter) + 60 gün süre + koç
iptali. Sayfa: /rapor/{token} (Next.js). Ses Rota'nın sesiyle, ilk dinlemede
bir kez üretilir (koçun kredisi, 2), sonrası önbellekten ücretsiz; koçun
paketi/onayı uygun değilse sayfa telefonun kendi sesine düşer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User

router = APIRouter(prefix="/public/exam-report", tags=["v2-exam-report-public"])


class ParentReportPublic(BaseModel):
    """Genel rapor yapısı — tür (exam|progress|weekly) ne olursa olsun aynı biçim."""
    kind: str
    title: str
    subtitle: str
    student_first: str
    brand_name: str
    brand_logo_url: str | None = None
    coach_name: str | None = None
    hero: dict[str, Any]
    #: bölümler: bullets · levels · bars · table · gains · tips · text
    sections: list[dict[str, Any]]
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
    """(bağlantı, rapor verisi) — bağlantı geçersizse ya da kaynağı silinmişse 404."""
    from app.services.exam_parent_report import build_link_data, get_usable_by_token

    rep = get_usable_by_token(db, token)
    if rep is None:
        raise _not_found()
    data = build_link_data(db, rep)
    if data is None:
        raise _not_found()
    return rep, data


def _voice_gate(db: Session, student_id: int) -> tuple[User | None, bool]:
    from app.routes.api_v2.parent import _parent_insight_gate

    student = db.get(User, student_id)
    if student is None:
        return None, False
    coach, ok, _ = _parent_insight_gate(db, student)
    return coach, ok


@router.get("/{token}", response_model=ParentReportPublic)
def exam_report_view(token: str, db: Session = Depends(get_db)):
    rep, data = _load(db, token)
    _, gate_ok = _voice_gate(db, rep.student_id)
    voice_ready = bool(rep.audio_content_type) and rep.audio_signature == data["speech_signature"]
    rep.view_count = (rep.view_count or 0) + 1
    rep.last_viewed_at = datetime.now(timezone.utc)
    db.commit()
    return ParentReportPublic(
        **{k: v for k, v in data.items() if k in ParentReportPublic.model_fields},
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
    from app.services.tts import synthesize_speech

    rep, data = _load(db, token)
    sig = data["speech_signature"]
    if rep.audio_content_type and rep.audio_signature == sig:
        return ReportVoiceResult(ready=True)

    coach, ok = _voice_gate(db, rep.student_id)
    student_id = rep.student_id
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
            ctx.set_metadata({"student_id": student_id, "report_kind": data["kind"], "by": "parent_report"})
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
    from app.services.exam_parent_report import pdf_filename, render_report_pdf

    _, data = _load(db, token)
    pdf = render_report_pdf(data)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{pdf_filename(data)}"',
        "Cache-Control": "private, max-age=0, no-store",
    })
