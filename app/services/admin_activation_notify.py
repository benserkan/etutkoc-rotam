"""Elle paket aktivasyonu — ayrı kanaldan bildirim + hediye sayımı (2026-10-28).

Süper admin panelinden ödeme sistemi dışında açılan her ücretli paket,
saldırgan panele girmiş olsa bile ondan saklanamayan kanallara bildirilir:
tüm aktif süper admin e-postaları + ALARM_EXTRA_EMAILS (kişisel adres) +
süper adminlerin telefonlarına push. Kayıt (audit) zaten yazılmıştır.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog, User

logger = logging.getLogger(__name__)

GIFT_WINDOW_DAYS = 30


def gift_activation_count(db: Session, *, days: int = GIFT_WINDOW_DAYS) -> int:
    """Son N günde 'hediye' türüyle yapılan elle aktivasyon sayısı."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(AuditLog.details_json)
        .filter(
            AuditLog.action == AuditAction.USER_UPDATE,
            AuditLog.created_at >= since,
            AuditLog.details_json.like('%"activate_plan"%'),
        )
        .all()
    )
    n = 0
    for (raw,) in rows:
        try:
            d = json.loads(raw or "{}")
        except Exception:
            continue
        if d.get("action") == "activate_plan" and d.get("grant_kind") == "gift":
            n += 1
    return n


def notify_manual_activation_bg(
    *, actor_id: int, target_id: int, plan_label: str, grant_kind: str,
    note: str, period_end: str, ip: str,
) -> None:
    from app.database import SessionLocal
    from app.services.alarm_engine import _active_super_admins, _alarm_email_recipients
    from app.services.email_service import send_email
    from app.services.push_notifications import safe_push

    try:
        with SessionLocal() as db:
            actor = db.get(User, actor_id)
            target = db.get(User, target_id)
            if target is None:
                return
            gifts = gift_activation_count(db)
            ctx = {
                "target_id": target.id,
                "target_name": target.full_name or target.email,
                "target_email": target.email,
                "plan_label": plan_label,
                "grant_kind": grant_kind,
                "note": note or "—",
                "period_end": period_end or "—",
                "actor_name": (actor.full_name if actor else "?"),
                "actor_email": (actor.email if actor else "?"),
                "ip": ip or "?",
                "at_display": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
                "gifts_30d": gifts,
            }
            for addr in _alarm_email_recipients(db):
                try:
                    send_email(addr, "admin_manual_activation", ctx)
                except Exception:
                    logger.exception("manual activation email fail to=%s", addr)
            kind_tr = "hediye" if grant_kind == "gift" else "ödeme"
            for admin in _active_super_admins(db):
                safe_push(
                    db, user_id=admin.id,
                    title="Elle paket aktivasyonu",
                    body=f"{ctx['target_name']} · {plan_label} · {kind_tr}",
                    data={"type": "admin", "screen": "users", "id": target.id},
                )
    except Exception:
        logger.exception("manual activation notify fail target=%s", target_id)
