"""CRM aksiyon şablon servisi (Faz B4)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    CrmActionKind,
    CrmActionTemplate,
    Institution,
    User,
)


OwnerType = Literal["institution", "user"]


def list_templates(
    db: Session, *,
    kind: CrmActionKind | str | None = None,
    active_only: bool = True,
) -> list[CrmActionTemplate]:
    q = db.query(CrmActionTemplate)
    if active_only:
        q = q.filter(CrmActionTemplate.is_active.is_(True))
    if kind is not None:
        if isinstance(kind, str):
            try:
                kind = CrmActionKind(kind)
            except ValueError:
                return []
        q = q.filter(CrmActionTemplate.kind == kind)
    return q.order_by(CrmActionTemplate.name.asc()).all()


def get_template(db: Session, template_id: int) -> CrmActionTemplate | None:
    return db.get(CrmActionTemplate, template_id)


def create_template(
    db: Session, *,
    name: str,
    kind: str,
    body: str,
    subject: str | None = None,
    description: str | None = None,
    by_user_id: int | None = None,
    autocommit: bool = True,
) -> CrmActionTemplate | None:
    try:
        k = CrmActionKind(kind)
    except ValueError:
        return None
    if not name.strip() or not body.strip():
        return None
    tpl = CrmActionTemplate(
        name=name.strip()[:255],
        kind=k,
        subject=(subject.strip()[:255] if subject and subject.strip() else None),
        body=body,
        description=(description.strip() if description else None) or None,
        created_by_user_id=by_user_id,
    )
    db.add(tpl)
    if autocommit:
        db.commit()
        db.refresh(tpl)
    return tpl


def update_template(
    db: Session, *,
    template_id: int,
    name: str | None = None,
    kind: str | None = None,
    body: str | None = None,
    subject: str | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    autocommit: bool = True,
) -> CrmActionTemplate | None:
    tpl = db.get(CrmActionTemplate, template_id)
    if tpl is None:
        return None
    if name is not None and name.strip():
        tpl.name = name.strip()[:255]
    if kind is not None:
        try:
            tpl.kind = CrmActionKind(kind)
        except ValueError:
            pass
    if body is not None and body.strip():
        tpl.body = body
    if subject is not None:
        tpl.subject = subject.strip()[:255] if subject.strip() else None
    if description is not None:
        tpl.description = description.strip() or None
    if is_active is not None:
        tpl.is_active = bool(is_active)
    if autocommit:
        db.commit()
        db.refresh(tpl)
    return tpl


def delete_template(
    db: Session, *, template_id: int, autocommit: bool = True,
) -> bool:
    tpl = db.get(CrmActionTemplate, template_id)
    if tpl is None:
        return False
    db.delete(tpl)
    if autocommit:
        db.commit()
    return True


# ---------------------------- Placeholder render ----------------------------


def _owner_context(
    db: Session, *, owner_type: OwnerType, owner_id: int,
) -> dict[str, str]:
    """Şablon placeholderları için owner bağlamı."""
    ctx: dict[str, str] = {"owner_name": "", "plan": "", "trial_ends_at": ""}
    if owner_type == "institution":
        inst = db.get(Institution, owner_id)
        if inst is None:
            return ctx
        ctx["owner_name"] = inst.name or ""
        ctx["plan"] = inst.plan or ""
        if inst.trial_ends_at:
            ctx["trial_ends_at"] = inst.trial_ends_at.strftime("%d.%m.%Y")
        ctx["contact_email"] = inst.contact_email or ""
    else:
        u = db.get(User, owner_id)
        if u is None:
            return ctx
        ctx["owner_name"] = u.full_name or u.email or ""
        ctx["plan"] = u.plan or ""
        if u.trial_ends_at:
            ctx["trial_ends_at"] = u.trial_ends_at.strftime("%d.%m.%Y")
        ctx["contact_email"] = u.email or ""
    ctx["today"] = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    return ctx


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_]+)\s*\}\}")


def render_text(text: str | None, context: dict[str, str]) -> str:
    if not text:
        return ""
    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        return context.get(key, m.group(0))
    return _PLACEHOLDER_RE.sub(_sub, text)


def render_template_for_owner(
    db: Session, *,
    template_id: int,
    owner_type: OwnerType,
    owner_id: int,
) -> dict | None:
    tpl = db.get(CrmActionTemplate, template_id)
    if tpl is None:
        return None
    ctx = _owner_context(db, owner_type=owner_type, owner_id=owner_id)
    return {
        "id": tpl.id,
        "name": tpl.name,
        "kind": tpl.kind.value,
        "subject": render_text(tpl.subject, ctx),
        "body": render_text(tpl.body, ctx),
    }


__all__ = [
    "create_template",
    "delete_template",
    "get_template",
    "list_templates",
    "render_template_for_owner",
    "render_text",
    "update_template",
]
