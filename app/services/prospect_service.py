"""Hedef Havuzu (sales_prospects) servisi — süper admin satış adayı yönetimi.

Sisteme üye olmayan kurum/koç adaylarını oluştur/listele/güncelle/sil + durum.
Üyelik teklifi (membership) bir prospect'i hedef alabilir (K1b).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import SalesProspect
from app.models.sales_prospect import (
    PROSPECT_KINDS, PROSPECT_KIND_COACH, PROSPECT_STATUSES, PROSPECT_STATUS_NEW,
    PROSPECT_SOURCES,
)
from app.services.phone_service import normalize_e164_tr


class ProspectError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_prospect(
    db: Session, *, actor_user_id: int | None,
    name: str, phone: str, kind: str = PROSPECT_KIND_COACH,
    org_name: str | None = None, email: str | None = None, city: str | None = None,
    source: str = "manual", opt_in: bool = False, note: str | None = None,
) -> SalesProspect:
    name = (name or "").strip()
    if len(name) < 2:
        raise ProspectError("invalid_name", "Ad en az 2 karakter olmalı.")
    norm = normalize_e164_tr(phone or "")
    if not norm:
        raise ProspectError("invalid_phone", "Geçerli bir cep telefonu girin (5XX...).")
    if kind not in PROSPECT_KINDS:
        kind = PROSPECT_KIND_COACH
    if source not in PROSPECT_SOURCES:
        source = "manual"
    # Aynı telefon zaten varsa tekrar ekleme (dedup)
    existing = db.query(SalesProspect).filter(SalesProspect.phone == norm).first()
    if existing is not None:
        raise ProspectError("duplicate_phone",
                            f"Bu telefon zaten havuzda: {existing.name}")
    p = SalesProspect(
        name=name, phone=norm, kind=kind,
        org_name=(org_name or "").strip() or None,
        email=(email or "").strip() or None,
        city=(city or "").strip() or None,
        source=source, opt_in=bool(opt_in),
        note=(note or "").strip() or None,
        status=PROSPECT_STATUS_NEW, created_by_admin_id=actor_user_id,
    )
    db.add(p)
    db.flush()
    return p


def list_prospects(
    db: Session, *, status: str | None = None, kind: str | None = None,
    q: str | None = None, limit: int = 300,
) -> list[SalesProspect]:
    query = db.query(SalesProspect)
    if status and status in PROSPECT_STATUSES:
        query = query.filter(SalesProspect.status == status)
    if kind and kind in PROSPECT_KINDS:
        query = query.filter(SalesProspect.kind == kind)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            SalesProspect.name.ilike(like),
            SalesProspect.phone.ilike(like),
            SalesProspect.org_name.ilike(like),
            SalesProspect.email.ilike(like),
        ))
    return query.order_by(SalesProspect.created_at.desc()).limit(max(1, min(limit, 1000))).all()


def get_prospect(db: Session, prospect_id: int) -> SalesProspect | None:
    return db.get(SalesProspect, prospect_id)


def update_prospect(db: Session, p: SalesProspect, **fields) -> SalesProspect:
    if "name" in fields and fields["name"] is not None:
        nm = fields["name"].strip()
        if len(nm) < 2:
            raise ProspectError("invalid_name", "Ad en az 2 karakter olmalı.")
        p.name = nm
    if fields.get("phone"):
        norm = normalize_e164_tr(fields["phone"])
        if not norm:
            raise ProspectError("invalid_phone", "Geçerli cep telefonu girin.")
        dup = db.query(SalesProspect).filter(
            SalesProspect.phone == norm, SalesProspect.id != p.id).first()
        if dup is not None:
            raise ProspectError("duplicate_phone", f"Bu telefon başka adayda: {dup.name}")
        p.phone = norm
    for f in ("org_name", "email", "city", "note"):
        if f in fields:
            v = fields[f]
            setattr(p, f, (v or "").strip() or None if isinstance(v, str) else v)
    if fields.get("kind") in PROSPECT_KINDS:
        p.kind = fields["kind"]
    if "opt_in" in fields and fields["opt_in"] is not None:
        p.opt_in = bool(fields["opt_in"])
    if fields.get("status") in PROSPECT_STATUSES:
        p.status = fields["status"]
    db.flush()
    return p


def set_status(db: Session, p: SalesProspect, status: str) -> SalesProspect:
    if status not in PROSPECT_STATUSES:
        raise ProspectError("invalid_status", "Geçersiz durum.")
    p.status = status
    db.flush()
    return p


def mark_contacted(db: Session, p: SalesProspect) -> None:
    p.last_contacted_at = _now()
    if p.status == PROSPECT_STATUS_NEW:
        p.status = "contacted"
    db.flush()


def delete_prospect(db: Session, p: SalesProspect) -> None:
    db.delete(p)
    db.flush()


def counts_by_status(db: Session) -> dict[str, int]:
    from sqlalchemy import func as _f
    rows = db.query(SalesProspect.status, _f.count(SalesProspect.id)).group_by(
        SalesProspect.status).all()
    return {str(s): int(c) for s, c in rows}
