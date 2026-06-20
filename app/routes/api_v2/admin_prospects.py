"""API v2 — Süper Admin: Hedef Havuzu (sales_prospects) yönetimi (K1a).

Sisteme üye olmayan kurum/koç adaylarını CRUD. Üyelik teklifi bunları hedef alır
(K1b) → markalı /membership linki + (Meta hazır olunca) WhatsApp branded mesaj.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import SalesProspect, User
from app.models.sales_prospect import (
    PROSPECT_KIND_LABELS_TR, PROSPECT_SOURCE_LABELS_TR, PROSPECT_STATUS_LABELS_TR,
)
from app.routes.api_v2.admin import _require_super_admin
from app.services import prospect_service as ps

router = APIRouter(prefix="/admin/prospects", tags=["v2-admin-prospects"])


class ProspectCreateBody(BaseModel):
    name: str
    phone: str
    kind: str = "coach"
    org_name: str | None = None
    email: str | None = None
    city: str | None = None
    source: str = "manual"
    opt_in: bool = False
    note: str | None = None


class ProspectUpdateBody(BaseModel):
    name: str | None = None
    phone: str | None = None
    kind: str | None = None
    org_name: str | None = None
    email: str | None = None
    city: str | None = None
    opt_in: bool | None = None
    note: str | None = None
    status: str | None = None


class StatusBody(BaseModel):
    status: str


def _item(p: SalesProspect) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "phone": p.phone,
        "kind": p.kind,
        "kind_label": PROSPECT_KIND_LABELS_TR.get(p.kind, p.kind),
        "org_name": p.org_name,
        "email": p.email,
        "city": p.city,
        "source": p.source,
        "source_label": PROSPECT_SOURCE_LABELS_TR.get(p.source, p.source),
        "status": p.status,
        "status_label": PROSPECT_STATUS_LABELS_TR.get(p.status, p.status),
        "opt_in": p.opt_in,
        "note": p.note,
        "last_contacted_at": p.last_contacted_at.isoformat() if p.last_contacted_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _err(e: ps.ProspectError):
    code = 409 if e.code in ("duplicate_phone",) else 422
    raise HTTPException(status_code=code, detail={"error": "prospect", "code": e.code, "message": e.message})


@router.get("")
def list_prospects(
    status_filter: str | None = Query(None, alias="status"),
    kind: str | None = Query(None),
    q: str | None = Query(None),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    rows = ps.list_prospects(db, status=status_filter, kind=kind, q=q)
    return {
        "items": [_item(p) for p in rows],
        "counts": ps.counts_by_status(db),
        "meta": {
            "kinds": PROSPECT_KIND_LABELS_TR,
            "statuses": PROSPECT_STATUS_LABELS_TR,
            "sources": PROSPECT_SOURCE_LABELS_TR,
        },
    }


@router.post("")
def create_prospect(
    body: ProspectCreateBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    try:
        p = ps.create_prospect(
            db, actor_user_id=user.id, name=body.name, phone=body.phone,
            kind=body.kind, org_name=body.org_name, email=body.email,
            city=body.city, source=body.source, opt_in=body.opt_in, note=body.note,
        )
        db.commit()
    except ps.ProspectError as e:
        db.rollback()
        _err(e)
    return {"data": _item(p), "invalidate": ["admin:prospects"]}


@router.post("/{prospect_id}")
def update_prospect(
    prospect_id: int,
    body: ProspectUpdateBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    p = ps.get_prospect(db, prospect_id)
    if p is None:
        raise HTTPException(status_code=404, detail={"error": "prospect", "code": "not_found"})
    try:
        ps.update_prospect(db, p, **body.model_dump(exclude_unset=True))
        db.commit()
    except ps.ProspectError as e:
        db.rollback()
        _err(e)
    return {"data": _item(p), "invalidate": ["admin:prospects"]}


@router.post("/{prospect_id}/status")
def set_status(
    prospect_id: int,
    body: StatusBody,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    p = ps.get_prospect(db, prospect_id)
    if p is None:
        raise HTTPException(status_code=404, detail={"error": "prospect", "code": "not_found"})
    try:
        ps.set_status(db, p, body.status)
        db.commit()
    except ps.ProspectError as e:
        db.rollback()
        _err(e)
    return {"data": _item(p), "invalidate": ["admin:prospects"]}


@router.post("/{prospect_id}/delete")
def delete_prospect(
    prospect_id: int,
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    p = ps.get_prospect(db, prospect_id)
    if p is None:
        raise HTTPException(status_code=404, detail={"error": "prospect", "code": "not_found"})
    ps.delete_prospect(db, p)
    db.commit()
    return {"data": {"deleted": True}, "invalidate": ["admin:prospects"]}
