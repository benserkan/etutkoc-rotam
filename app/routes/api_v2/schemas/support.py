"""API v2 — rol-bazlı talep (SupportRequest) şemaları + serileştiriciler.

Talep eden (koç/kurum yöneticisi/öğretmen) + muhatap (süper admin/kurum
yöneticisi) panelleri AYNI şemaları paylaşır; `is_me`/`is_mine` viewer'a göre
hesaplanır.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models import (
    SUPPORT_AUDIENCE_INSTITUTION_ADMIN,
    SUPPORT_AUDIENCE_LABELS_TR,
    SUPPORT_AUDIENCE_SUPER_ADMIN,
    SUPPORT_STATUS_LABELS_TR,
    SUPPORT_TERMINAL_STATUSES,
    SupportRequest,
    SupportRequestMessage,
    User,
    UserRole,
)
from app.models.support_request import SUPPORT_CATEGORY_LABELS_TR


# ----------------------------- Çıkış modelleri -----------------------------


class SupportMessageItem(BaseModel):
    id: int
    sender_id: int | None
    sender_name: str
    sender_role: str | None
    is_me: bool
    body: str
    created_at: datetime


class SupportRequestListItem(BaseModel):
    id: int
    subject: str
    category: str
    category_label: str
    status: str
    status_label: str
    audience: str
    audience_label: str
    requester_id: int
    requester_name: str
    requester_role: str
    institution_id: int | None
    institution_name: str | None
    created_at: datetime
    last_activity_at: datetime
    message_count: int
    last_message_preview: str | None
    handled_by_name: str | None
    resolved_at: datetime | None
    is_mine: bool  # viewer talebin sahibi mi (talep eden mi)
    can_manage: bool  # viewer aktif muhatap mı (incele/cevapla/çözümle)
    can_escalate: bool  # viewer (kurum yöneticisi) süper yöneticiye yönlendirebilir mi
    escalated: bool  # talep süper yöneticiye yönlendirildi mi
    escalated_by_name: str | None
    is_escalator: bool  # viewer bu talebi yönlendiren kurum yöneticisi mi


class SupportRequestDetail(SupportRequestListItem):
    messages: list[SupportMessageItem]


class SupportListResponse(BaseModel):
    items: list[SupportRequestListItem]
    pending_count: int  # muhatap için bekleyen / talep eden için açık
    categories: list["SupportCategoryOption"]


class SupportCategoryOption(BaseModel):
    value: str
    label: str


class SupportRequestCreateBody(BaseModel):
    category: str = "other"
    subject: str
    body: str


class SupportReplyBody(BaseModel):
    body: str


class SupportEscalateBody(BaseModel):
    note: str | None = None


# ----------------------------- Serileştiriciler -----------------------------


def category_options() -> list[SupportCategoryOption]:
    return [SupportCategoryOption(value=k, label=v) for k, v in SUPPORT_CATEGORY_LABELS_TR.items()]


def _name(u: User | None) -> str:
    if u is None:
        return "—"
    return (u.full_name or u.email or "—")


def message_item(msg: SupportRequestMessage, viewer: User) -> SupportMessageItem:
    sender = msg.sender
    return SupportMessageItem(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_name=_name(sender),
        sender_role=(sender.role.value if sender else None),
        is_me=(msg.sender_id == viewer.id),
        body=msg.body,
        created_at=msg.created_at,
    )


def _is_active_recipient(req: SupportRequest, viewer: User) -> bool:
    if viewer.role == UserRole.SUPER_ADMIN:
        return req.audience == SUPPORT_AUDIENCE_SUPER_ADMIN
    if viewer.role == UserRole.INSTITUTION_ADMIN:
        return (
            req.audience == SUPPORT_AUDIENCE_INSTITUTION_ADMIN
            and req.institution_id is not None
            and req.institution_id == viewer.institution_id
        )
    return False


def _can_escalate(req: SupportRequest, viewer: User) -> bool:
    """Kurum yöneticisi, kendi kurumunun (institution_admin muhataplı) kapanmamış
    talebini süper yöneticiye yönlendirebilir."""
    return (
        viewer.role == UserRole.INSTITUTION_ADMIN
        and _is_active_recipient(req, viewer)
        and req.status not in SUPPORT_TERMINAL_STATUSES
    )


def _list_item(req: SupportRequest, viewer: User) -> SupportRequestListItem:
    msgs = req.messages or []
    last = msgs[-1] if msgs else None
    preview = None
    if last:
        preview = last.body.strip().replace("\n", " ")
        if len(preview) > 120:
            preview = preview[:117] + "…"
    return SupportRequestListItem(
        id=req.id,
        subject=req.subject,
        category=req.category,
        category_label=SUPPORT_CATEGORY_LABELS_TR.get(req.category, "Diğer"),
        status=req.status,
        status_label=SUPPORT_STATUS_LABELS_TR.get(req.status, req.status),
        audience=req.audience,
        audience_label=SUPPORT_AUDIENCE_LABELS_TR.get(req.audience, req.audience),
        requester_id=req.requester_id,
        requester_name=_name(req.requester),
        requester_role=req.requester_role,
        institution_id=req.institution_id,
        institution_name=(req.institution.name if req.institution else None),
        created_at=req.created_at,
        last_activity_at=req.last_activity_at,
        message_count=len(msgs),
        last_message_preview=preview,
        handled_by_name=(_name(req.handled_by) if req.handled_by_id else None),
        resolved_at=req.resolved_at,
        is_mine=(req.requester_id == viewer.id),
        can_manage=_is_active_recipient(req, viewer),
        can_escalate=_can_escalate(req, viewer),
        escalated=(req.escalated_by_id is not None),
        escalated_by_name=(_name(req.escalated_by) if req.escalated_by_id else None),
        is_escalator=(req.escalated_by_id is not None and req.escalated_by_id == viewer.id),
    )


def list_item(req: SupportRequest, viewer: User) -> SupportRequestListItem:
    return _list_item(req, viewer)


def detail(req: SupportRequest, viewer: User) -> SupportRequestDetail:
    base = _list_item(req, viewer)
    return SupportRequestDetail(
        **base.model_dump(),
        messages=[message_item(m, viewer) for m in (req.messages or [])],
    )


SupportListResponse.model_rebuild()
