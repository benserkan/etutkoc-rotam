"""Owner etiket servisi (Ticari Pano 2.0 — Faz B1).

Kurum + bağımsız öğretmen sahiplerine etiket atama/listeleme/kaldırma.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal

from sqlalchemy.orm import Session

from app.models import OwnerTag, OwnerTagKind


logger = logging.getLogger(__name__)


OwnerType = Literal["institution", "user"]


def _xor_kwargs(owner_type: OwnerType, owner_id: int) -> dict:
    if owner_type == "institution":
        return {"institution_id": owner_id, "user_id": None}
    if owner_type == "user":
        return {"institution_id": None, "user_id": owner_id}
    raise ValueError(f"unknown owner_type {owner_type!r}")


def list_tags_for(
    db: Session, *, owner_type: OwnerType, owner_id: int,
) -> list[OwnerTag]:
    q = db.query(OwnerTag).filter(OwnerTag.owner_type == owner_type)
    if owner_type == "institution":
        q = q.filter(OwnerTag.institution_id == owner_id)
    else:
        q = q.filter(OwnerTag.user_id == owner_id)
    return q.order_by(OwnerTag.created_at.desc()).all()


def add_tag(
    db: Session, *,
    owner_type: OwnerType,
    owner_id: int,
    kind: OwnerTagKind | str,
    by_user_id: int | None = None,
    note: str | None = None,
    autocommit: bool = True,
) -> OwnerTag | None:
    """Etiket ekle. Aynı kind aynı owner'a tek kez — duplicate ise mevcut döner."""
    if isinstance(kind, str):
        try:
            kind = OwnerTagKind(kind)
        except ValueError:
            return None

    existing = (
        db.query(OwnerTag)
        .filter(
            OwnerTag.owner_type == owner_type,
            OwnerTag.kind == kind,
            (OwnerTag.institution_id == owner_id) if owner_type == "institution"
            else (OwnerTag.user_id == owner_id),
        )
        .first()
    )
    if existing is not None:
        return existing

    tag = OwnerTag(
        owner_type=owner_type,
        **_xor_kwargs(owner_type, owner_id),
        kind=kind,
        note=(note.strip() if note else None) or None,
        created_by_user_id=by_user_id,
    )
    db.add(tag)
    if autocommit:
        db.commit()
        db.refresh(tag)
    return tag


def remove_tag(
    db: Session, *, tag_id: int, autocommit: bool = True,
) -> bool:
    tag = db.get(OwnerTag, tag_id)
    if tag is None:
        return False
    db.delete(tag)
    if autocommit:
        db.commit()
    return True


def tags_by_owner_map(
    db: Session, *,
    institution_ids: list[int] | None = None,
    user_ids: list[int] | None = None,
) -> dict[tuple[OwnerType, int], list[OwnerTag]]:
    """Bir liste owner için toplu tag fetch — listeleme sayfaları için."""
    out: dict[tuple[OwnerType, int], list[OwnerTag]] = defaultdict(list)
    if institution_ids:
        for t in (
            db.query(OwnerTag)
            .filter(
                OwnerTag.owner_type == "institution",
                OwnerTag.institution_id.in_(institution_ids),
            )
            .all()
        ):
            out[("institution", t.institution_id)].append(t)
    if user_ids:
        for t in (
            db.query(OwnerTag)
            .filter(
                OwnerTag.owner_type == "user",
                OwnerTag.user_id.in_(user_ids),
            )
            .all()
        ):
            out[("user", t.user_id)].append(t)
    return out


__all__ = [
    "add_tag",
    "list_tags_for",
    "remove_tag",
    "tags_by_owner_map",
]
