"""API v2 — "Bugünün mesajları": WhatsApp mesaj önerileri (2026-11-14).

GET  /teacher/message-suggestions[?student_id=]  → öneriler + bugün gönderilen sayısı
POST /teacher/message-suggestions/send          → WhatsApp bağlantısı + kayıt
POST /teacher/message-suggestions/skip          → öneri atlanır (bir daha çıkmaz)

Koç (bağımsız ya da kuruma bağlı) yalnız kendi öğrencileri için. Gönderim koçun
kendi WhatsApp'ından (wa.me); cevap takibi yok.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User, UserRole
from app.models.message_suggestion import ACTION_SENT, ACTION_SKIPPED
from app.routes.api_v2.teacher import _require_teacher
from app.services import message_suggestions as ms

router = APIRouter(prefix="/teacher/message-suggestions", tags=["v2-message-suggestions"])


class SuggestionTarget(BaseModel):
    user_id: int
    full_name: str
    relation_label: str
    phone_masked: str | None = None
    can_message: bool


class SuggestionItem(BaseModel):
    student_id: int
    student_name: str
    key: str
    audience: Literal["parent", "student"]
    kind: str
    kind_label: str
    title: str
    reason: str
    text: str
    has_report: bool
    targets: list[SuggestionTarget]


class SuggestionsResponse(BaseModel):
    sent_today: int
    items: list[SuggestionItem]
    students_checked: int


class SendBody(BaseModel):
    student_id: int
    audience: Literal["parent", "student"]
    key: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=2000)
    target_user_id: int | None = None


class SendResult(BaseModel):
    wa_url: str
    target_name: str | None = None
    sent_today: int


class SkipBody(BaseModel):
    student_id: int
    audience: Literal["parent", "student"]
    key: str = Field(min_length=1, max_length=120)


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": code, "code": code, "message": message})


def _own_students(db: Session, coach: User, student_id: int | None) -> list[User]:
    q = db.query(User).filter(User.teacher_id == coach.id, User.role == UserRole.STUDENT,
                              User.is_active.is_(True))
    if student_id is not None:
        q = q.filter(User.id == student_id)
    return q.order_by(User.full_name).all()


def _targets_by_audience(db: Session, coach: User, student: User) -> dict[str, list[dict]]:
    from app.services.whatsapp_link_service import share_targets_for_student

    _, targets = share_targets_for_student(db, sender=coach, student_id=student.id)
    parents = [t for t in targets if t["relation_label"] != "Öğrencinin kendisi"]
    me = [t for t in targets if t["relation_label"] == "Öğrencinin kendisi"]
    return {"parent": parents, "student": me}


@router.get("", response_model=SuggestionsResponse)
def list_suggestions(student_id: int | None = None, user: User = Depends(_require_teacher),
                     db: Session = Depends(get_db)):
    students = _own_students(db, user, student_id)
    if student_id is not None and not students:
        raise _err(404, "student_not_found", "Öğrenci bulunamadı.")
    decided = ms.decided_keys(db, [s.id for s in students])
    items: list[SuggestionItem] = []
    for st in students:
        try:
            sugg = ms.build_for_student(db, st)
        except Exception:  # noqa: BLE001 — bir öğrencinin hatası listeyi düşürmesin
            import logging

            logging.getLogger(__name__).exception("message suggestions failed for student %s", st.id)
            continue
        sugg = [s for s in sugg if (st.id, s.audience, s.key) not in decided]
        if not sugg:
            continue
        tg = _targets_by_audience(db, user, st)
        for s in sugg:
            targets = tg.get(s.audience) or []
            if s.audience == "parent" and not targets:
                continue  # velisi bağlı değil
            items.append(SuggestionItem(
                student_id=st.id, student_name=st.full_name, key=s.key, audience=s.audience, kind=s.kind,
                kind_label=ms.KIND_LABELS.get(s.kind, s.kind), title=s.title, reason=s.reason, text=s.text,
                has_report=s.report is not None, targets=[SuggestionTarget(**t) for t in targets],
            ))
    db.commit()
    return SuggestionsResponse(sent_today=ms.sent_today(db, user.id), items=items,
                               students_checked=len(students))


def _find(db: Session, student: User, audience: str, key: str) -> ms.Suggestion | None:
    for s in ms.build_for_student(db, student):
        if s.audience == audience and s.key == key:
            return s
    return None


@router.post("/send", response_model=SendResult)
def send_suggestion(body: SendBody, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    from app.services.whatsapp_link_service import WaDispatchError, build_share_dispatch

    students = _own_students(db, user, body.student_id)
    if not students:
        raise _err(404, "student_not_found", "Öğrenci bulunamadı.")
    st = students[0]
    sugg = _find(db, st, body.audience, body.key)
    if sugg is None:
        raise _err(409, "suggestion_gone", "Bu öneri artık geçerli değil; listeyi yenile.")
    allowed = {t["user_id"] for t in _targets_by_audience(db, user, st).get(body.audience, [])}
    if body.target_user_id is not None and body.target_user_id not in allowed:
        raise _err(404, "target_not_found", "Kişi bulunamadı.")

    text = body.text.strip()
    if ms.LINK_TOKEN in text or sugg.report:
        url = ms.report_link(db, student=st, report=sugg.report or {}, actor_id=user.id) if sugg.report else None
        if url:
            text = text.replace(ms.LINK_TOKEN, url) if ms.LINK_TOKEN in text else f"{text}\n{url}"
        else:
            text = text.replace(ms.LINK_TOKEN, "").strip()
    try:
        res = build_share_dispatch(db, sender=user, kind="coach_message", text=text, student_id=st.id,
                                   target_user_id=body.target_user_id, ref_id=None)
    except WaDispatchError as e:
        db.rollback()
        raise _err(e.status, e.code, e.message)
    ms.record(db, coach_id=user.id, student_id=st.id, audience=body.audience, key=body.key,
              action=ACTION_SENT, target_user_id=body.target_user_id)
    db.commit()
    return SendResult(wa_url=res["wa_url"], target_name=res.get("target_name"),
                      sent_today=ms.sent_today(db, user.id))


@router.post("/skip")
def skip_suggestion(body: SkipBody, user: User = Depends(_require_teacher), db: Session = Depends(get_db)):
    if not _own_students(db, user, body.student_id):
        raise _err(404, "student_not_found", "Öğrenci bulunamadı.")
    ms.record(db, coach_id=user.id, student_id=body.student_id, audience=body.audience, key=body.key,
              action=ACTION_SKIPPED, target_user_id=None)
    db.commit()
    return {"ok": True}
