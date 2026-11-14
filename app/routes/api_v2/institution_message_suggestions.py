"""API v2 — Kurum yöneticisi "Koçlara mesajlar" (2026-11-14).

GET  /institution/message-suggestions        → koç bazında öneriler + bugün gönderilen
POST /institution/message-suggestions/send   → koça WhatsApp bağlantısı + kayıt
POST /institution/message-suggestions/skip   → öneri atlanır

Yalnız kendi kurumunun aktif koçları (başka kurum 404). Ölçüm Müdahale Merkezi /
Program Uyumu ile aynı. Gönderim yöneticinin kendi WhatsApp'ından (wa.me).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User, UserRole
from app.models.message_suggestion import ACTION_SENT, ACTION_SKIPPED
from app.routes.api_v2.institution import _get_institution_or_403, _require_institution_admin
from app.routes.api_v2.message_suggestions import (
    SendResult,
    SuggestionItem,
    SuggestionsResponse,
    SuggestionTarget,
)
from app.services import message_suggestions as ms

router = APIRouter(prefix="/institution/message-suggestions", tags=["v2-institution-message-suggestions"])

AUD = "coach"


class InstSendBody(BaseModel):
    coach_id: int
    key: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2000)


class InstSkipBody(BaseModel):
    coach_id: int
    key: str = Field(min_length=1, max_length=120)


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "code": code, "message": message})


def _coach(db: Session, admin: User, coach_id: int) -> User:
    c = db.get(User, coach_id)
    if (c is None or c.role != UserRole.TEACHER or not c.is_active
            or c.institution_id != admin.institution_id):
        raise _err(404, "coach_not_found", "Koç bulunamadı.")
    return c


def _target(c: User) -> SuggestionTarget:
    from app.services.whatsapp_link_service import can_message_phone, mask_phone_e164

    return SuggestionTarget(user_id=c.id, full_name=c.full_name, relation_label="Koç",
                            phone_masked=mask_phone_e164(c.phone) if c.phone else None,
                            can_message=can_message_phone(c))


@router.get("", response_model=SuggestionsResponse)
def list_inst_suggestions(user: User = Depends(_require_institution_admin), db: Session = Depends(get_db)):
    _get_institution_or_403(db, user.institution_id)
    data = ms.cached_for_institution(db, user.institution_id)
    decided = ms.decided_keys(db, list(data))
    items: list[SuggestionItem] = []
    for cid, sugg in data.items():
        c = db.get(User, cid)
        if c is None or not c.is_active:
            continue
        for s in sugg:
            if (cid, AUD, s.key) in decided:
                continue
            items.append(SuggestionItem(
                group_id=cid, group_name=c.full_name, student_id=cid, student_name=c.full_name,
                key=s.key, audience=AUD, kind=s.kind, kind_label=ms.KIND_LABELS.get(s.kind, s.kind),
                title=s.title, reason=s.reason, text=s.text, has_report=False, targets=[_target(c)],
            ))
    return SuggestionsResponse(sent_today=ms.sent_today(db, user.id), items=items, students_checked=len(data))


@router.post("/send", response_model=SendResult)
def send_inst_suggestion(body: InstSendBody, user: User = Depends(_require_institution_admin),
                         db: Session = Depends(get_db)):
    from app.services.whatsapp_link_service import WaDispatchError

    c = _coach(db, user, body.coach_id)
    keys = {s.key for s in ms.cached_for_institution(db, user.institution_id).get(c.id, [])}
    if body.key not in keys:
        raise _err(409, "suggestion_gone", "Bu öneri artık geçerli değil; listeyi yenile.")
    try:
        res = ms.dispatch_direct(db, sender=user, target=c, text=body.text, key=body.key)
    except WaDispatchError as e:
        db.rollback()
        raise _err(e.status, e.code, e.message)
    ms.record(db, coach_id=user.id, student_id=c.id, audience=AUD, key=body.key, action=ACTION_SENT,
              target_user_id=c.id)
    db.commit()
    return SendResult(wa_url=res["wa_url"], target_name=res.get("target_name"), sent_today=ms.sent_today(db, user.id))


@router.post("/skip")
def skip_inst_suggestion(body: InstSkipBody, user: User = Depends(_require_institution_admin),
                         db: Session = Depends(get_db)):
    c = _coach(db, user, body.coach_id)
    ms.record(db, coach_id=user.id, student_id=c.id, audience=AUD, key=body.key, action=ACTION_SKIPPED,
              target_user_id=None)
    db.commit()
    return {"ok": True}
