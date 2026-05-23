"""API v2 — rol-bazlı talep sistemi (SupportRequest) — TEK paylaşılan router.

3 panele dağıtmak yerine tek `/support` yüzeyi; davranış rol'den türetilir:
  - Talep eden (TEACHER / INSTITUTION_ADMIN): kendi taleplerini oluşturur/görür/
    yanıtlar/geri çeker.
  - Muhatap (SUPER_ADMIN → super_admin kuyruğu; INSTITUTION_ADMIN → kendi kurumu):
    gelen kutusunu görür, incelemeye alır, yanıtlar, çözümler.

Yön çözümleme servis katmanında (audience_for_requester). Tenant izolasyonu
get_for_recipient + list_inbox_institution_admin içinde.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import User, UserRole
from app.routes.api_v2.dependencies import get_current_user_v2
from app.routes.api_v2.schemas.common import MutationResponse
from app.routes.api_v2.schemas.support import (
    SupportEscalateBody,
    SupportListResponse,
    SupportRequestCreateBody,
    SupportRequestDetail,
    SupportReplyBody,
    category_options,
    detail as build_detail,
    list_item as build_list_item,
)
from app.services import support_request_service as svc

router = APIRouter(prefix="/support", tags=["v2-support"])


def _svc_error(e: svc.SupportError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "validation", "code": e.code, "message": e.message},
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "not_found", "code": "request_not_found",
                "message": "Talep bulunamadı."},
    )


def _forbidden(msg: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error": "forbidden", "code": "role_required", "message": msg},
    )


def _is_recipient_role(user: User) -> bool:
    return user.role in (UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN)


# ----------------------------- Talep eden tarafı -----------------------------


@router.get("/requests", response_model=SupportListResponse)
def list_my_requests_v2(
    status_param: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kendi taleplerim (talep eden görünümü)."""
    if not svc.can_request(user):
        raise _forbidden("Bu rol talep oluşturamaz.")
    rows = svc.list_for_requester(db, user, status_filter=status_param)
    return SupportListResponse(
        items=[build_list_item(r, user) for r in rows],
        pending_count=svc.open_count_for_requester(db, user),
        categories=category_options(),
    )


@router.post("/requests", response_model=MutationResponse[SupportRequestDetail])
def create_request_v2(
    body: SupportRequestCreateBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    if not svc.can_request(user):
        raise _forbidden("Bu rol talep oluşturamaz.")
    try:
        req = svc.create_request(
            db, requester=user, category=body.category, subject=body.subject, body=body.body,
        )
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:mine", "support:inbox"],
    )


@router.post("/requests/{request_id}/withdraw", response_model=MutationResponse[SupportRequestDetail])
def withdraw_request_v2(
    request_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    req = svc.get_for_requester(db, user, request_id)
    if req is None:
        raise _not_found()
    try:
        svc.withdraw_request(db, req=req, requester=user)
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:mine", "support:inbox"],
    )


# ----------------------------- Muhatap tarafı -----------------------------


@router.get("/inbox", response_model=SupportListResponse)
def inbox_v2(
    status_param: str | None = Query(None, alias="status"),
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Gelen kutusu (muhatap görünümü)."""
    if user.role == UserRole.SUPER_ADMIN:
        rows = svc.list_inbox_super_admin(db, status_filter=status_param)
        pending = svc.pending_count_super_admin(db)
    elif user.role == UserRole.INSTITUTION_ADMIN:
        rows = svc.list_inbox_institution_admin(db, user, status_filter=status_param)
        pending = svc.pending_count_institution_admin(db, user)
    else:
        raise _forbidden("Bu rolün gelen kutusu yok.")
    return SupportListResponse(
        items=[build_list_item(r, user) for r in rows],
        pending_count=pending,
        categories=category_options(),
    )


@router.post("/requests/{request_id}/review", response_model=MutationResponse[SupportRequestDetail])
def review_request_v2(
    request_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    if not _is_recipient_role(user):
        raise _forbidden("Bu işlem yalnız muhatap içindir.")
    req = svc.get_for_recipient(db, user, request_id)
    if req is None:
        raise _not_found()
    try:
        svc.mark_under_review(db, req=req, recipient=user)
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:inbox", "support:mine"],
    )


@router.post("/requests/{request_id}/escalate", response_model=MutationResponse[SupportRequestDetail])
def escalate_request_v2(
    request_id: int,
    body: SupportEscalateBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Kurum yöneticisi, çözemeyeceği talebi süper yöneticiye yönlendirir."""
    if user.role != UserRole.INSTITUTION_ADMIN:
        raise _forbidden("Yönlendirme yalnız kurum yöneticisi içindir.")
    req = svc.get_for_recipient(db, user, request_id)
    if req is None:
        raise _not_found()
    try:
        svc.escalate_to_super_admin(db, req=req, admin=user, note=body.note)
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:inbox", "support:mine"],
    )


@router.post("/requests/{request_id}/resolve", response_model=MutationResponse[SupportRequestDetail])
def resolve_request_v2(
    request_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    if not _is_recipient_role(user):
        raise _forbidden("Bu işlem yalnız muhatap içindir.")
    req = svc.get_for_recipient(db, user, request_id)
    if req is None:
        raise _not_found()
    try:
        svc.resolve_request(db, req=req, recipient=user)
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:inbox", "support:mine"],
    )


# ----------------------------- Ortak (her iki taraf) -----------------------------


def _resolve_access(db: Session, user: User, request_id: int):
    """Talebe görüntüleme erişimini çöz: (req, by_recipient).

    Erişenler: talep eden · aktif muhatap · yönlendiren kurum yöneticisi.
    by_recipient = kullanıcı AKTİF muhatap mı (yanıt cevabı 'Cevaplandı' yapar).
    Erişim yoksa 404.
    """
    req = svc.get_viewable(db, user, request_id)
    if req is None:
        raise _not_found()
    return req, svc.is_active_recipient(req, user)


@router.get("/requests/{request_id}", response_model=SupportRequestDetail)
def get_request_v2(
    request_id: int,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    req, _ = _resolve_access(db, user, request_id)
    return build_detail(req, user)


@router.post("/requests/{request_id}/reply", response_model=MutationResponse[SupportRequestDetail])
def reply_request_v2(
    request_id: int,
    body: SupportReplyBody,
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    req, by_recipient = _resolve_access(db, user, request_id)
    try:
        svc.add_message(db, req=req, sender=user, body=body.body, by_recipient=by_recipient)
    except svc.SupportError as e:
        db.rollback()
        raise _svc_error(e)
    db.commit()
    db.refresh(req)
    return MutationResponse[SupportRequestDetail](
        data=build_detail(req, user), invalidate=["support:mine", "support:inbox"],
    )
