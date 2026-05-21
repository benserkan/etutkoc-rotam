"""Katman 11.F — Alarm motoru.

Her kuralın "şu anki değerini" hesaplar, eşik aşılırsa AlarmEvent yazıp
kanallara (email süper admin, in-app) gönderim yapar. Cooldown ile
yorgunluğu önler.

İki giriş noktası:
  - evaluate_all(db): cron ya da admin "Şimdi tara" → tüm enabled kuralları çalıştır
  - acknowledge(db, event_id, user_id): admin alarmı gördü → acknowledged_at

Kural değer hesaplamaları:
  - high_failed_logins   = AuditLog 24h LOGIN_FAILED + LOGIN_LOCKED count
  - oldest_queued_long   = oldest_queued_minutes(db)
  - error_groups_open    = ErrorEvent count where resolved_at IS NULL
  - abuse_open           = AbuseSignal count where resolved_at IS NULL
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    AbuseSignal,
    AlarmEvent,
    AlarmRule,
    AuditAction,
    AuditLog,
    ErrorEvent,
    User,
    UserRole,
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


# ---------------------------- Kural değer hesaplama ----------------------------


def _val_high_failed_logins(db: Session) -> int:
    cutoff = _now() - timedelta(hours=24)
    return int(
        (db.query(func.count(AuditLog.id))
         .filter(
             AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
             AuditLog.created_at >= cutoff,
         )
         .scalar()) or 0
    )


def _val_oldest_queued_long(db: Session) -> int:
    """En eski queued bildirimin yaşı (dakika)."""
    from app.services.notification_health import oldest_queued_minutes
    return oldest_queued_minutes(db) or 0


def _val_error_groups_open(db: Session) -> int:
    return int(
        (db.query(func.count(ErrorEvent.id))
         .filter(ErrorEvent.resolved_at.is_(None))
         .scalar()) or 0
    )


def _val_abuse_open(db: Session) -> int:
    return int(
        (db.query(func.count(AbuseSignal.id))
         .filter(AbuseSignal.resolved_at.is_(None))
         .scalar()) or 0
    )


# Kural key → değer hesaplayıcı + severity hesaplayıcı
EVALUATORS = {
    "high_failed_logins": _val_high_failed_logins,
    "oldest_queued_long": _val_oldest_queued_long,
    "error_groups_open": _val_error_groups_open,
    "abuse_open": _val_abuse_open,
}


def _severity_for(rule_key: str, value: int, threshold: int) -> str:
    """Eşiği ne kadar aşmış? 2x → critical, ortası → warn."""
    if threshold <= 0:
        return "warn" if value > 0 else "info"
    ratio = value / threshold
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.0:
        return "warn"
    return "info"


# ---------------------------- Engine ----------------------------


@dataclass
class EvaluationResult:
    rule_key: str
    value: int
    threshold: int
    triggered: bool
    skipped_reason: str | None  # cooldown, disabled, ya da None


def _in_cooldown(rule: AlarmRule, *, now: datetime) -> bool:
    if rule.last_triggered_at is None or rule.cooldown_minutes <= 0:
        return False
    last = _aware(rule.last_triggered_at)
    if last is None:
        return False
    return (now - last).total_seconds() < rule.cooldown_minutes * 60


def evaluate_all(db: Session) -> list[EvaluationResult]:
    """Tüm enabled kuralları çalıştır. Tetiklenenler için AlarmEvent yaz + bildir."""
    now = _now()
    rules = db.query(AlarmRule).all()
    results: list[EvaluationResult] = []

    for rule in rules:
        if not rule.enabled:
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="disabled",
            ))
            continue
        evaluator = EVALUATORS.get(rule.key)
        if evaluator is None:
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="no_evaluator",
            ))
            continue
        try:
            value = evaluator(db)
        except Exception:
            logger.exception("alarm evaluator fail rule=%s", rule.key)
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="evaluator_error",
            ))
            continue

        rule.last_value = value
        rule.updated_at = now

        should_trigger = value > rule.threshold
        # abuse_open: threshold=0 ise her tek sinyal alarmlar
        if rule.key == "abuse_open" and rule.threshold == 0:
            should_trigger = value > 0

        if not should_trigger:
            results.append(EvaluationResult(
                rule_key=rule.key, value=value, threshold=rule.threshold,
                triggered=False, skipped_reason=None,
            ))
            continue

        if _in_cooldown(rule, now=now):
            results.append(EvaluationResult(
                rule_key=rule.key, value=value, threshold=rule.threshold,
                triggered=False, skipped_reason="cooldown",
            ))
            continue

        # TETİK
        severity = _severity_for(rule.key, value, rule.threshold)
        channels = [c.strip() for c in (rule.channels or "").split(",") if c.strip()]
        event = AlarmEvent(
            rule_key=rule.key,
            rule_name=rule.name,
            value=value,
            threshold=rule.threshold,
            severity=severity,
            channels_attempted=",".join(channels),
            delivery_status="pending",
            details_json=json.dumps({"value": value, "threshold": rule.threshold}),
            triggered_at=now,
        )
        db.add(event)
        rule.last_triggered_at = now

        # Kanallara gönder (defansif)
        delivery_parts: list[str] = []
        if "email" in channels:
            try:
                _send_email_to_super_admins(db, rule=rule, event=event)
                delivery_parts.append("email:ok")
            except Exception:
                logger.exception("alarm email fail rule=%s", rule.key)
                delivery_parts.append("email:fail")
        if "in_app" in channels:
            # In-app şu an: AlarmEvent satırı zaten yazılı → /admin/security-monitor/alarms görür
            delivery_parts.append("in_app:ok")
        event.delivery_status = "|".join(delivery_parts) or "noop"

        results.append(EvaluationResult(
            rule_key=rule.key, value=value, threshold=rule.threshold,
            triggered=True, skipped_reason=None,
        ))

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("alarm evaluate_all commit fail")

    return results


def _send_email_to_super_admins(
    db: Session, *, rule: AlarmRule, event: AlarmEvent
) -> None:
    """E-posta tüm aktif süper admin'lere — email_service kullan."""
    try:
        from app.services.email_service import send_email
    except Exception:
        logger.warning("email_service unavailable — alarm log only")
        return
    admins = (
        db.query(User)
        .filter(User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True))
        .all()
    )
    if not admins:
        return
    ctx = {
        "rule_name": rule.name,
        "rule_key": rule.key,
        "rule_description": rule.description or "",
        "value": event.value,
        "threshold": event.threshold,
        "severity": event.severity,
        "triggered_at_display": event.triggered_at.strftime("%d %B %Y, %H:%M UTC"),
    }
    for a in admins:
        if not a.email:
            continue
        try:
            send_email(a.email, "security_alarm_triggered", ctx)
        except Exception:
            logger.exception("alarm email send fail to=%s", a.email)


# ---------------------------- Listing + ack ----------------------------


def list_recent_events(
    db: Session, *, hours: int = 72, only_unacknowledged: bool = False, limit: int = 50
) -> list[dict]:
    cutoff = _now() - timedelta(hours=hours)
    q = db.query(AlarmEvent).filter(AlarmEvent.triggered_at >= cutoff)
    if only_unacknowledged:
        q = q.filter(AlarmEvent.acknowledged_at.is_(None))
    rows = q.order_by(desc(AlarmEvent.triggered_at)).limit(limit).all()
    now = _now()
    out: list[dict] = []
    for r in rows:
        tr = _aware(r.triggered_at) or now
        out.append({
            "id": r.id,
            "rule_key": r.rule_key,
            "rule_name": r.rule_name,
            "value": r.value,
            "threshold": r.threshold,
            "severity": r.severity,
            "delivery_status": r.delivery_status,
            "triggered_at": tr,
            "acknowledged_at": _aware(r.acknowledged_at),
            "age_seconds": int((now - tr).total_seconds()),
        })
    return out


def acknowledge(
    db: Session, *, event_id: int, user_id: int, autocommit: bool = True
) -> AlarmEvent | None:
    row = db.get(AlarmEvent, event_id)
    if row is None or row.acknowledged_at is not None:
        return row
    row.acknowledged_at = _now()
    row.acknowledged_by_user_id = user_id
    if autocommit:
        db.commit()
    return row


def unacknowledged_count(db: Session) -> int:
    return int(
        (db.query(func.count(AlarmEvent.id))
         .filter(AlarmEvent.acknowledged_at.is_(None))
         .scalar()) or 0
    )


def list_rules(db: Session) -> list[AlarmRule]:
    return list(
        db.query(AlarmRule).order_by(AlarmRule.key).all()
    )


def update_rule(
    db: Session,
    *,
    rule_id: int,
    threshold: int | None = None,
    cooldown_minutes: int | None = None,
    enabled: bool | None = None,
    channels: str | None = None,
    autocommit: bool = True,
) -> AlarmRule | None:
    row = db.get(AlarmRule, rule_id)
    if row is None:
        return None
    if threshold is not None:
        row.threshold = int(threshold)
    if cooldown_minutes is not None:
        row.cooldown_minutes = int(cooldown_minutes)
    if enabled is not None:
        row.enabled = bool(enabled)
    if channels is not None:
        row.channels = channels[:60]
    row.updated_at = _now()
    if autocommit:
        db.commit()
    return row


# ---------------------------- Live feed ----------------------------


def live_event_stream(db: Session, *, since_seconds: int = 300, limit: int = 50) -> list[dict]:
    """Son N saniyenin AuditLog + AlarmEvent karışık akışı (descending)."""
    cutoff = _now() - timedelta(seconds=since_seconds)
    audits = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= cutoff)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    alarms = (
        db.query(AlarmEvent)
        .filter(AlarmEvent.triggered_at >= cutoff)
        .order_by(desc(AlarmEvent.triggered_at))
        .limit(limit)
        .all()
    )
    items: list[dict] = []
    for a in audits:
        items.append({
            "type": "audit",
            "ts": _aware(a.created_at),
            "title": a.action.value if hasattr(a.action, "value") else str(a.action),
            "actor_id": a.actor_id,
            "ip": a.ip_address,
            "details": a.email_attempted or "",
            "severity": "critical" if a.action.value in (
                "user_delete", "institution_delete", "impersonate_start",
                "login_locked", "permission_denied"
            ) else "info",
        })
    for e in alarms:
        items.append({
            "type": "alarm",
            "ts": _aware(e.triggered_at),
            "title": e.rule_name,
            "actor_id": None,
            "ip": None,
            "details": f"{e.value} (eşik: {e.threshold})",
            "severity": e.severity,
        })
    items.sort(key=lambda x: x["ts"] or _now(), reverse=True)
    return items[:limit]


__all__ = [
    "EvaluationResult",
    "acknowledge",
    "evaluate_all",
    "list_recent_events",
    "list_rules",
    "live_event_stream",
    "unacknowledged_count",
    "update_rule",
]
