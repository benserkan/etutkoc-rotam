"""Owner iletişim metadata servisi (Ticari Pano 2.0 — Faz B3)."""

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.models import OwnerContact


OwnerType = Literal["institution", "user"]


def get_contact(
    db: Session, *, owner_type: OwnerType, owner_id: int,
) -> OwnerContact | None:
    q = db.query(OwnerContact).filter(OwnerContact.owner_type == owner_type)
    if owner_type == "institution":
        q = q.filter(OwnerContact.institution_id == owner_id)
    else:
        q = q.filter(OwnerContact.user_id == owner_id)
    return q.first()


def upsert_contact(
    db: Session, *,
    owner_type: OwnerType,
    owner_id: int,
    by_user_id: int | None = None,
    fields: dict,
    autocommit: bool = True,
) -> OwnerContact:
    """Mevcut kaydı güncelle veya yeni oluştur."""
    contact = get_contact(db, owner_type=owner_type, owner_id=owner_id)
    if contact is None:
        contact = OwnerContact(
            owner_type=owner_type,
            institution_id=owner_id if owner_type == "institution" else None,
            user_id=owner_id if owner_type == "user" else None,
        )
        db.add(contact)

    allowed = {
        "responsible_person_name", "responsible_person_title",
        "billing_email", "phone", "whatsapp",
        "linkedin_url", "website", "address", "note",
    }
    for k, v in fields.items():
        if k not in allowed:
            continue
        if isinstance(v, str):
            v = v.strip() or None
        setattr(contact, k, v)

    contact.updated_by_user_id = by_user_id

    if autocommit:
        db.commit()
        db.refresh(contact)
    return contact


__all__ = ["get_contact", "upsert_contact"]
