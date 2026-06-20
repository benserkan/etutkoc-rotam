"""İletişim Sağlığı — communication_logs üzerinden süper admin gözlem katmanı.

İki çıktı:
  - get_overview: kanal başına (e-posta/push/whatsapp/sms) sağlık özeti
    (24s + N günlük pencere: durum kırılımı + başarı %).
  - list_logs: filtreli + sayfalı drill-down (kanal/durum/tarih/alıcı arama/tür).

Salt-okuma; UI render'ında tetiklenir (DB write yok).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import CommunicationLog, User
from app.models.communication_log import (
    CHANNEL_LABELS_TR,
    CHANNELS,
    FAILURE_STATUSES,
    STATUS_LABELS_TR,
    SUCCESS_STATUSES,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _success_pct(success: int, failure: int) -> float | None:
    denom = success + failure
    if denom == 0:
        return None
    return round(success * 100.0 / denom, 1)


def _counts_by_status(db: Session, channel: str, since: datetime) -> dict[str, int]:
    rows = (
        db.query(CommunicationLog.status, func.count(CommunicationLog.id))
        .filter(
            CommunicationLog.channel == channel,
            CommunicationLog.created_at >= since,
        )
        .group_by(CommunicationLog.status)
        .all()
    )
    return {str(s): int(c) for s, c in rows}


def _summary(counts: dict[str, int]) -> dict:
    success = sum(counts.get(s, 0) for s in SUCCESS_STATUSES)
    failure = sum(counts.get(s, 0) for s in FAILURE_STATUSES)
    total = sum(counts.values())
    return {
        "total": total,
        "sent": counts.get("sent", 0),
        "delivered": counts.get("delivered", 0),
        "bounced": counts.get("bounced", 0),
        "complained": counts.get("complained", 0),
        "failed": counts.get("failed", 0),
        "queued": counts.get("queued", 0),
        "suppressed": counts.get("suppressed", 0),
        "success_pct": _success_pct(success, failure),
    }


def get_overview(db: Session, *, days: int = 7) -> dict:
    """Kanal başına 24s + N günlük sağlık özeti + genel toplam."""
    now = _now()
    since_window = now - timedelta(days=days)
    since_24h = now - timedelta(hours=24)

    channels = []
    overall_w = {"success": 0, "failure": 0, "total": 0}
    for ch in CHANNELS:
        c_window = _counts_by_status(db, ch, since_window)
        c_24h = _counts_by_status(db, ch, since_24h)
        w = _summary(c_window)
        h = _summary(c_24h)
        channels.append({
            "channel": ch,
            "label": CHANNEL_LABELS_TR[ch],
            "window": w,
            "last24h": {
                "total": h["total"],
                "failed": h["failed"] + h["bounced"] + h["complained"],
                "success_pct": h["success_pct"],
            },
        })
        overall_w["success"] += sum(c_window.get(s, 0) for s in SUCCESS_STATUSES)
        overall_w["failure"] += sum(c_window.get(s, 0) for s in FAILURE_STATUSES)
        overall_w["total"] += w["total"]

    return {
        "generated_at": now,
        "window_days": days,
        "channels": channels,
        "overall": {
            "total": overall_w["total"],
            "success_pct": _success_pct(overall_w["success"], overall_w["failure"]),
        },
    }


def list_logs(
    db: Session,
    *,
    channel: str | None = None,
    status: str | None = None,
    days: int = 7,
    q: str | None = None,
    category: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict:
    """Filtreli + sayfalı gönderim listesi (en yeni üstte)."""
    since = _now() - timedelta(days=max(1, days))
    base = db.query(CommunicationLog).filter(CommunicationLog.created_at >= since)
    if channel and channel in CHANNELS:
        base = base.filter(CommunicationLog.channel == channel)
    if status:
        base = base.filter(CommunicationLog.status == status)
    if category:
        base = base.filter(CommunicationLog.category == category)
    if q:
        like = f"%{q.strip()}%"
        base = base.filter(
            or_(
                CommunicationLog.to_address.ilike(like),
                CommunicationLog.subject.ilike(like),
            )
        )

    total = base.count()
    limit = max(1, min(limit, 200))
    page = max(1, page)
    rows = (
        base.order_by(CommunicationLog.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # Alıcı adlarını tek sorguda çöz
    uids = {r.to_user_id for r in rows if r.to_user_id}
    names: dict[int, str] = {}
    if uids:
        for u in db.query(User.id, User.full_name).filter(User.id.in_(uids)).all():
            names[u.id] = u.full_name

    items = [
        {
            "id": r.id,
            "channel": r.channel,
            "channel_label": CHANNEL_LABELS_TR.get(r.channel, r.channel),
            "category": r.category,
            "to_address": r.to_address,
            "to_user_id": r.to_user_id,
            "to_user_name": names.get(r.to_user_id) if r.to_user_id else None,
            "subject": r.subject,
            "status": r.status,
            "status_label": STATUS_LABELS_TR.get(r.status, r.status),
            "provider": r.provider,
            "error": r.error,
            "created_at": r.created_at,
            "sent_at": r.sent_at,
        }
        for r in rows
    ]
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total else 0,
    }
