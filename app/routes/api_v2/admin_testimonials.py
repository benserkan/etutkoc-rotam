"""API v2 — Süper Admin: Sosyal kanıt (testimonials) yönetimi.

Kurum referansı / kullanıcı yorumu / başarı hikâyesi giriş + moderasyon
(yayınla/gizle) + uygulama-içi gönderimleri onaylama. Public taraf:
testimonials_public.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import (
    TESTIMONIAL_KIND_LABELS_TR,
    TESTIMONIAL_ROLE_LABELS_TR,
    TESTIMONIAL_SOURCE_LABELS_TR,
    TESTIMONIAL_STATUS_LABELS_TR,
    Testimonial,
    User,
)
from app.models.audit_log import AuditAction
from app.routes.api_v2.admin import _require_super_admin
from app.routes.api_v2.schemas.common import MutationResponse, SimpleOk
from app.routes.api_v2.schemas.testimonial import (
    TestimonialAdminItem,
    TestimonialAdminListResponse,
    TestimonialCreateBody,
    TestimonialStatusBody,
    TestimonialUpdateBody,
)
from app.services import audit
from app.services import testimonial_service as svc

router = APIRouter(prefix="/admin/testimonials", tags=["v2-admin-testimonials"])

_INVALIDATE = ["admin:testimonials", "testimonials:public"]


def _to_item(t: Testimonial) -> TestimonialAdminItem:
    return TestimonialAdminItem(
        id=t.id,
        kind=t.kind,
        kind_label=TESTIMONIAL_KIND_LABELS_TR.get(t.kind, t.kind),
        author_name=t.author_name,
        author_role=t.author_role,
        author_role_label=TESTIMONIAL_ROLE_LABELS_TR.get(t.author_role or "", None),
        author_title=t.author_title,
        institution_name=t.institution_name,
        rating=t.rating,
        content=t.content,
        status=t.status,
        status_label=TESTIMONIAL_STATUS_LABELS_TR.get(t.status, t.status),
        source=t.source,
        source_label=TESTIMONIAL_SOURCE_LABELS_TR.get(t.source, t.source),
        submitted_by_id=t.submitted_by_id,
        consent_public=t.consent_public,
        featured=t.featured,
        sort_order=t.sort_order,
        published_at=t.published_at,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _get_or_404(db: Session, testimonial_id: int) -> Testimonial:
    t = svc.get(db, testimonial_id)
    if t is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "testimonial_not_found",
                    "message": "Kayıt bulunamadı."},
        )
    return t


@router.get("", response_model=TestimonialAdminListResponse)
def admin_list_testimonials(
    status_filter: str | None = Query(None, alias="status", max_length=20),
    kind: str | None = Query(None, max_length=30),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    rows = svc.admin_list(db, status=status_filter, kind=kind)
    return TestimonialAdminListResponse(
        items=[_to_item(t) for t in rows],
        counts=svc.admin_counts(db),
        kinds=TESTIMONIAL_KIND_LABELS_TR,
        statuses=TESTIMONIAL_STATUS_LABELS_TR,
        roles=TESTIMONIAL_ROLE_LABELS_TR,
    )


@router.post("", response_model=MutationResponse[TestimonialAdminItem])
def admin_create_testimonial(
    body: TestimonialCreateBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    t = svc.create_manual(
        db,
        admin=user,
        kind=body.kind,
        author_name=body.author_name,
        author_role=body.author_role,
        author_title=body.author_title,
        institution_name=body.institution_name,
        rating=body.rating,
        content=body.content,
        status=body.status,
        consent_public=body.consent_public,
        featured=body.featured,
        sort_order=body.sort_order,
    )
    audit.log_action(
        db,
        action=AuditAction.TESTIMONIAL_MODERATE,
        actor_id=user.id,
        target_type="testimonial",
        target_id=t.id,
        request=request,
        details={"op": "create", "status": t.status, "kind": t.kind},
    )
    return MutationResponse[TestimonialAdminItem](data=_to_item(t), invalidate=_INVALIDATE)


@router.post("/{testimonial_id}", response_model=MutationResponse[TestimonialAdminItem])
def admin_update_testimonial(
    testimonial_id: int,
    body: TestimonialUpdateBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    t = _get_or_404(db, testimonial_id)
    t = svc.update_fields(
        db,
        t=t,
        admin=user,
        kind=body.kind,
        author_name=body.author_name,
        author_role=body.author_role,
        author_title=body.author_title,
        institution_name=body.institution_name,
        rating=body.rating,
        content=body.content,
        consent_public=body.consent_public,
        featured=body.featured,
        sort_order=body.sort_order,
    )
    return MutationResponse[TestimonialAdminItem](data=_to_item(t), invalidate=_INVALIDATE)


@router.post("/{testimonial_id}/status", response_model=MutationResponse[TestimonialAdminItem])
def admin_set_testimonial_status(
    testimonial_id: int,
    body: TestimonialStatusBody,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    t = _get_or_404(db, testimonial_id)
    t = svc.set_status(db, t=t, status=body.status, admin=user)
    audit.log_action(
        db,
        action=AuditAction.TESTIMONIAL_MODERATE,
        actor_id=user.id,
        target_type="testimonial",
        target_id=t.id,
        request=request,
        details={"op": "status", "status": t.status},
    )
    return MutationResponse[TestimonialAdminItem](data=_to_item(t), invalidate=_INVALIDATE)


@router.post("/{testimonial_id}/delete", response_model=MutationResponse[SimpleOk])
def admin_delete_testimonial(
    testimonial_id: int,
    request: Request,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    t = _get_or_404(db, testimonial_id)
    audit.log_action(
        db,
        action=AuditAction.TESTIMONIAL_MODERATE,
        actor_id=user.id,
        target_type="testimonial",
        target_id=t.id,
        request=request,
        details={"op": "delete"},
    )
    svc.delete(db, t=t)
    return MutationResponse[SimpleOk](data=SimpleOk(), invalidate=_INVALIDATE)
