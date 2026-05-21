"""Katman 11.E — Hata yakalama servisi.

İki ana fonksiyon:
  - record_error: middleware/handler bir HTTP 5xx veya exception gördüğünde çağırır.
    SHA1(endpoint + exception_type + stack_top) → signature. Aynı signature
    için mevcut grup'un count + last_seen_at güncellenir; yenisi yazılmaz.
  - record_slow_request: response_time_ms > eşik ise append-only kayıt.

Stack trace temel kısaltma: ilk 8 frame'in 'File "x", line N, in fn' satırları
+ exception type + message. Stack_top = ilk app/ frame'i (signature için).
"""

from __future__ import annotations

import hashlib
import logging
import re
import traceback
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models import (
    ERROR_RETENTION_DAYS,
    ErrorEvent,
    SLOW_RETENTION_DAYS,
    SlowRequestLog,
    User,
)


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Stack trace içinde "app/...:line" formatını yakalamak için
_APP_FRAME_RE = re.compile(r'File "(.*?app[/\\][^"]+)", line (\d+), in (\w+)')


def _extract_stack_top(stack_str: str) -> str:
    """Stack trace içinde uygulamaya ait ilk frame'i bul (signature için)."""
    if not stack_str:
        return "unknown"
    matches = _APP_FRAME_RE.findall(stack_str)
    if not matches:
        # fallback: ilk "File" satırı
        for line in stack_str.splitlines():
            if line.strip().startswith('File "'):
                return line.strip()[:200]
        return "unknown"
    # En derin app/ frame'i (en son) → spesifik
    path, line, fn = matches[-1]
    return f"{path}:{line}:{fn}"


def compute_signature(*, endpoint: str, exception_type: str | None, stack_top: str) -> str:
    """SHA1 (40 hex) — aynı endpoint + exception + kod konumu = aynı grup."""
    raw = f"{endpoint}|{exception_type or 'http_error'}|{stack_top}"
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def record_error(
    db: Session,
    *,
    endpoint: str,
    method: str,
    status_code: int,
    exception: BaseException | None = None,
    stack_trace: str | None = None,
    actor_user_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    autocommit: bool = True,
) -> ErrorEvent | None:
    """Hata kaydı: aynı signature varsa increment, yoksa yarat.

    exception None ise: HTTP 5xx ama yakalanmamış istisna yok (route handler
    HTTPException fırlattı ve middleware görmedi gibi). stack_trace verilirse
    onu kullanır; yoksa "unknown:unknown:unknown".
    """
    exc_type: str | None = None
    exc_msg: str | None = None
    full_stack: str | None = stack_trace

    if exception is not None:
        exc_type = type(exception).__name__[:100]
        exc_msg = str(exception)[:500]
        if full_stack is None:
            full_stack = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )

    full_stack = (full_stack or "")[:8000]
    stack_top = _extract_stack_top(full_stack)
    signature = compute_signature(
        endpoint=endpoint, exception_type=exc_type, stack_top=stack_top
    )

    now = _now()
    row = (
        db.query(ErrorEvent)
        .filter(ErrorEvent.signature == signature)
        .first()
    )
    if row is None:
        row = ErrorEvent(
            signature=signature,
            endpoint=endpoint[:255],
            method=method[:10].upper(),
            status_code=status_code,
            exception_type=exc_type,
            exception_message=exc_msg,
            stack_trace=full_stack or None,
            count=1,
            first_seen_at=now,
            last_seen_at=now,
            last_actor_user_id=actor_user_id,
            last_ip=(ip or "")[:64] or None,
            last_user_agent=(user_agent or "")[:255] or None,
        )
        db.add(row)
    else:
        row.count = (row.count or 0) + 1
        row.last_seen_at = now
        row.last_actor_user_id = actor_user_id or row.last_actor_user_id
        if ip:
            row.last_ip = ip[:64]
        if user_agent:
            row.last_user_agent = user_agent[:255]
        row.status_code = status_code
        if exc_msg:
            row.exception_message = exc_msg
        if full_stack:
            row.stack_trace = full_stack
        # Resolve edildikten sonra tekrar tetiklenirse "regression" → re-open
        if row.resolved_at is not None:
            row.resolved_at = None
            row.resolved_by_user_id = None
            row.resolution_note = None

    if autocommit:
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            logger.exception("error_event commit fail signature=%s", signature)
            return None
    return row


def record_slow_request(
    db: Session,
    *,
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: int,
    actor_user_id: int | None = None,
    ip: str | None = None,
    autocommit: bool = True,
) -> SlowRequestLog | None:
    row = SlowRequestLog(
        endpoint=endpoint[:255],
        method=method[:10].upper(),
        status_code=status_code,
        response_time_ms=response_time_ms,
        recorded_at=_now(),
        actor_user_id=actor_user_id,
        ip=(ip or "")[:64] or None,
    )
    db.add(row)
    if autocommit:
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            return None
    return row


def resolve_error(
    db: Session, *, error_id: int, resolved_by_user_id: int, note: str | None,
    autocommit: bool = True,
) -> ErrorEvent | None:
    row = db.get(ErrorEvent, error_id)
    if row is None or row.resolved_at is not None:
        return row
    row.resolved_at = _now()
    row.resolved_by_user_id = resolved_by_user_id
    row.resolution_note = (note or "")[:500] or None
    if autocommit:
        db.commit()
    return row


# ---------------------------- Listing / aggregation ----------------------------


def list_error_groups(
    db: Session, *, only_open: bool = True, limit: int = 50
) -> list[dict]:
    q = db.query(ErrorEvent)
    if only_open:
        q = q.filter(ErrorEvent.resolved_at.is_(None))
    q = q.order_by(desc(ErrorEvent.last_seen_at)).limit(limit)
    now = _now()
    out: list[dict] = []
    for r in q.all():
        first = _aware(r.first_seen_at) or now
        last = _aware(r.last_seen_at) or now
        out.append({
            "id": r.id,
            "signature": r.signature,
            "endpoint": r.endpoint,
            "method": r.method,
            "status_code": r.status_code,
            "exception_type": r.exception_type or "HTTPError",
            "exception_message": r.exception_message,
            "stack_trace": r.stack_trace,
            "count": r.count or 0,
            "first_seen_at": first,
            "last_seen_at": last,
            "age_seconds": int((now - last).total_seconds()),
            "resolved_at": _aware(r.resolved_at),
            "last_ip": r.last_ip,
            "last_actor_user_id": r.last_actor_user_id,
        })
    return out


def error_summary(db: Session, *, hours: int = 24) -> dict:
    cutoff = _now() - timedelta(hours=hours)
    total_open = (
        db.query(func.count(ErrorEvent.id))
        .filter(ErrorEvent.resolved_at.is_(None))
        .scalar()
    ) or 0
    new_in_window = (
        db.query(func.count(ErrorEvent.id))
        .filter(ErrorEvent.first_seen_at >= cutoff)
        .scalar()
    ) or 0
    total_count_window = (
        db.query(func.coalesce(func.sum(ErrorEvent.count), 0))
        .filter(ErrorEvent.last_seen_at >= cutoff)
        .scalar()
    ) or 0
    return {
        "open_groups": int(total_open),
        "new_groups_24h": int(new_in_window),
        "total_events_24h": int(total_count_window),
        "window_hours": hours,
    }


def list_slow_requests(
    db: Session, *, hours: int = 24, limit: int = 50
) -> list[dict]:
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(SlowRequestLog)
        .filter(SlowRequestLog.recorded_at >= cutoff)
        .order_by(desc(SlowRequestLog.response_time_ms))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "endpoint": r.endpoint,
            "method": r.method,
            "status_code": r.status_code,
            "response_time_ms": r.response_time_ms,
            "recorded_at": _aware(r.recorded_at),
            "ip": r.ip,
        }
        for r in rows
    ]


def endpoint_error_rates(
    db: Session, *, hours: int = 24, limit: int = 10
) -> list[dict]:
    """Endpoint başına son N saatte error count (top N)."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(
            ErrorEvent.endpoint,
            ErrorEvent.method,
            func.sum(ErrorEvent.count).label("total"),
            func.count(ErrorEvent.id).label("groups"),
        )
        .filter(ErrorEvent.last_seen_at >= cutoff)
        .group_by(ErrorEvent.endpoint, ErrorEvent.method)
        .order_by(desc(func.sum(ErrorEvent.count)))
        .limit(limit)
        .all()
    )
    return [
        {
            "endpoint": r.endpoint,
            "method": r.method,
            "total": int(r.total or 0),
            "groups": int(r.groups or 0),
        }
        for r in rows
    ]


def get_system_health_data(db: Session) -> dict:
    return {
        "generated_at": _now(),
        "summary": error_summary(db, hours=24),
        "error_groups": list_error_groups(db, only_open=True, limit=30),
        "endpoint_top": endpoint_error_rates(db, hours=24, limit=10),
        "slow_requests": list_slow_requests(db, hours=24, limit=20),
    }


def humanize_ago(seconds: int) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return "az önce"
    if s < 3600:
        return f"{s // 60} dk önce"
    if s < 86400:
        return f"{s // 3600} saat önce"
    return f"{s // 86400} gün önce"


__all__ = [
    "compute_signature",
    "endpoint_error_rates",
    "error_summary",
    "get_system_health_data",
    "humanize_ago",
    "list_error_groups",
    "list_slow_requests",
    "record_error",
    "record_slow_request",
    "resolve_error",
]
