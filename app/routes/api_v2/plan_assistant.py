"""Paket asistanı uçları — /api/v2/teacher/plan-assistant (2026-10-03).

GET  /teacher/plan-assistant              karşılama + hazır sorular (yapay zekâsız)
POST /teacher/plan-assistant/ask          {chip} → hazır cevap · {question, history} → Gemini
POST /teacher/plan-assistant/handoff      {message, transcript} → "Üyelik / ödeme" destek talebi

Kilit hijyeni: durum okunur → işlem KAPATILIR → Gemini işlem DIŞINDA → kısa yazım.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.routes.api_v2.teacher import _require_teacher
from app.services import plan_assistant as pa

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/teacher", tags=["plan-assistant"])


class PAAction(BaseModel):
    type: str
    label: str | None = None
    plan: str | None = None
    section: str | None = None


class PAChip(BaseModel):
    id: str
    label: str


class PAState(BaseModel):
    greeting: str
    chips: list[PAChip]
    daily_left: int
    suggested_plan: str | None = None


class PAMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    text: str = Field(max_length=2000)


class PAAskBody(BaseModel):
    chip: str | None = Field(default=None, max_length=40)
    question: str | None = Field(default=None, max_length=800)
    history: list[PAMessage] = Field(default_factory=list, max_length=20)
    channel: str | None = Field(default=None, max_length=10)


class PAAnswer(BaseModel):
    answer: str
    action: PAAction | None = None
    source: str               # rule | ai | fallback
    daily_left: int


class PAHandoffBody(BaseModel):
    message: str = Field(min_length=3, max_length=2000)
    transcript: list[PAMessage] = Field(default_factory=list, max_length=30)


class PAHandoffResult(BaseModel):
    ok: bool
    request_id: int
    message: str


def _ch(channel: str | None) -> str:
    return channel if channel in pa.CHANNELS else "web"


@router.get("/plan-assistant", response_model=PAState)
def plan_assistant_state(channel: str | None = None, user: User = Depends(_require_teacher),
                         db: Session = Depends(get_db)):
    ch = _ch(channel)
    state = pa.build_state(db, user)
    sug = pa.suggested_plan(state) if state["plan"]["is_solo"] else None
    return PAState(
        greeting=pa.greeting_for(state, ch),
        chips=[PAChip(**c) for c in pa.chips_for(state, ch)],
        daily_left=max(0, pa.PA_DAILY_LIMIT - pa.ask_count_today(db, user.id)),
        suggested_plan=sug["code"] if sug else None,
    )


@router.post("/plan-assistant/ask", response_model=PAAnswer)
def plan_assistant_ask(body: PAAskBody, user: User = Depends(_require_teacher),
                       db: Session = Depends(get_db)):
    ch = _ch(body.channel)
    state = pa.build_state(db, user)
    used = pa.ask_count_today(db, user.id)
    left = max(0, pa.PA_DAILY_LIMIT - used)

    if body.chip:
        res = pa.rule_answer(body.chip, state, ch)
        return PAAnswer(answer=res["answer"], action=res["action"], source="rule", daily_left=left)

    q = (body.question or "").strip()
    if not q:
        raise HTTPException(status_code=422, detail={"code": "question_required",
                                                     "message": "Bir soru yaz ya da hazır sorulardan birini seç."})
    if left <= 0:
        chip = pa.keyword_chip(q) or "human"
        res = pa.rule_answer(chip, state, ch)
        return PAAnswer(answer="Bugünlük serbest soru hakkın doldu; en yakın hazır cevabı veriyorum. "
                               + res["answer"], action=res["action"], source="fallback", daily_left=0)

    db.commit()  # uzun dış çağrı açık işlem içinde yapılmaz
    try:
        res = pa.ai_answer(q, [h.model_dump() for h in body.history], state, ch)
        source = "ai"
    except Exception:  # noqa: BLE001 — asistan asla boş dönmez
        logger.warning("plan assistant AI failed", exc_info=True)
        chip = pa.keyword_chip(q)
        res = pa.rule_answer(chip or "human", state, ch)
        if not chip:
            res = {"answer": "Şu an bu soruyu yanıtlayamadım. Aşağıdaki hazır sorulardan birini "
                             "seçebilir ya da 'Bize yaz' ile ekibimize iletebilirsin.",
                   "action": {"type": "handoff", "label": "Bize yaz"}}
        source = "fallback"
    if source == "ai":
        pa.record_ask(db, user, source="ai")
        db.commit()
        left = max(0, left - 1)
    return PAAnswer(answer=res["answer"], action=res["action"], source=source, daily_left=left)


@router.post("/plan-assistant/handoff", response_model=PAHandoffResult)
def plan_assistant_handoff(body: PAHandoffBody, user: User = Depends(_require_teacher),
                           db: Session = Depends(get_db)):
    from app.services import support_request_service as srs

    state = pa.build_state(db, user)
    p = state["plan"]
    lines = [body.message.strip(), "", "— Paket asistanından aktarıldı —",
             f"Paket: {p['plan_label']} · durum: {p['status']} · aktif öğrenci: {p['student_count']}"]
    if p.get("last_payment_issue"):
        lines.append(f"Son ödeme: {p['last_payment_issue']['title']}")
    if body.transcript:
        lines.append("")
        lines.append("Konuşma:")
        for m in body.transcript[-12:]:
            lines.append(f"{'Koç' if m.role == 'user' else 'Asistan'}: {m.text[:400]}")
    try:
        req = srs.create_request(db, requester=user, category="billing",
                                 subject="Paket / ödeme sorusu", body="\n".join(lines)[:3900])
    except srs.SupportError as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": str(exc)}) from exc
    db.commit()
    who = "kurum yöneticine" if user.institution_id else "ekibimize"
    return PAHandoffResult(ok=True, request_id=req.id,
                           message=f"Mesajın {who} iletildi. Cevabı Destek sayfandan takip edebilirsin.")
