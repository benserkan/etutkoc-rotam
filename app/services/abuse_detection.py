"""Katman 11.C — Kötüye kullanım (abuse) dedektörleri.

Periyodik tarama servisi: 4 kuralı çalıştırır, eşik aşılırsa AbuseSignal yazar.
Dedup: aynı (kind, actor, tenant) için son 24h içinde resolved olmayan kayıt
varsa count + window_end + last_seen_at güncellenir; yenisi yazılmaz.

Sorgu kaynakları:
  MASS_INVITATION       — parent_invitations (invited_by_id, created_at)
  MASS_NOTIFICATION     — notification_logs (parent_id → user.institution_id)
  MULTI_ACCOUNT         — active_sessions (ua + ip → distinct user_id 24h)
  UNSUBSCRIBE_SPIKE     — audit_logs USER_PAUSE_ALERTS (actor → institution_id)

Cron'dan veya panodan elle çağrılır: run_all(db). Pano render sırasında
otomatik çalışmaz (DB write maliyeti); admin "Şimdi tara" butonuyla başlatır
ya da abuse_scan cron'u yapar.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models import (
    ABUSE_DEDUP_WINDOW_HOURS,
    ABUSE_KIND_LABELS_TR,
    AbuseSignal,
    ActiveSession,
    AuditAction,
    AuditLog,
    Institution,
    NotificationLog,
    ParentInvitation,
    THRESHOLD_MASS_INVITATION_PER_HOUR,
    THRESHOLD_MASS_NOTIFICATION_PER_HOUR,
    THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS,
    THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


KIND_MASS_INVITATION = "mass_invitation"
KIND_MASS_NOTIFICATION = "mass_notification"
KIND_MULTI_ACCOUNT = "multi_account_same_device"
KIND_UNSUBSCRIBE_SPIKE = "unsubscribe_spike"
KIND_SIGNUP_VELOCITY = "signup_velocity"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class DetectionHit:
    kind: str
    actor_user_id: int | None
    tenant_id: int | None
    count: int
    window_start: datetime
    window_end: datetime
    details: dict
    severity: str = "warn"


def _upsert_signal(db: Session, hit: DetectionHit, *, autocommit: bool = True) -> AbuseSignal:
    """Aynı (kind, actor, tenant) için son DEDUP_WINDOW_HOURS içinde
    resolved olmayan kayıt varsa güncelle; yoksa yenisini yarat.
    """
    now = _now()
    cutoff = now - timedelta(hours=ABUSE_DEDUP_WINDOW_HOURS)

    q = db.query(AbuseSignal).filter(
        AbuseSignal.kind == hit.kind,
        AbuseSignal.resolved_at.is_(None),
        AbuseSignal.last_seen_at >= cutoff,
    )
    if hit.actor_user_id is not None:
        q = q.filter(AbuseSignal.actor_user_id == hit.actor_user_id)
    else:
        q = q.filter(AbuseSignal.actor_user_id.is_(None))
    if hit.tenant_id is not None:
        q = q.filter(AbuseSignal.tenant_id == hit.tenant_id)
    else:
        q = q.filter(AbuseSignal.tenant_id.is_(None))

    existing = q.order_by(desc(AbuseSignal.last_seen_at)).first()

    if existing is not None:
        existing.count = hit.count
        existing.window_end = hit.window_end
        existing.last_seen_at = now
        existing.severity = hit.severity
        existing.details_json = json.dumps(hit.details, ensure_ascii=False)
        if autocommit:
            db.commit()
            db.refresh(existing)
        return existing

    row = AbuseSignal(
        kind=hit.kind,
        severity=hit.severity,
        actor_user_id=hit.actor_user_id,
        tenant_id=hit.tenant_id,
        count=hit.count,
        window_start=hit.window_start,
        window_end=hit.window_end,
        details_json=json.dumps(hit.details, ensure_ascii=False),
        detected_at=now,
        last_seen_at=now,
    )
    db.add(row)
    if autocommit:
        db.commit()
        db.refresh(row)
    return row


# ---------------------------- Dedektörler ----------------------------


def detect_mass_invitation(
    db: Session, *, window_hours: int = 1, threshold: int | None = None
) -> list[DetectionHit]:
    """Bir öğretmen window_hours saatte threshold+ veli daveti göndermiş mi?"""
    threshold = threshold or THRESHOLD_MASS_INVITATION_PER_HOUR
    now = _now()
    cutoff = now - timedelta(hours=window_hours)
    rows = (
        db.query(
            ParentInvitation.invited_by_id.label("uid"),
            func.count(ParentInvitation.id).label("c"),
        )
        .filter(ParentInvitation.created_at >= cutoff)
        .group_by(ParentInvitation.invited_by_id)
        .having(func.count(ParentInvitation.id) >= threshold)
        .all()
    )
    hits: list[DetectionHit] = []
    for r in rows:
        hits.append(
            DetectionHit(
                kind=KIND_MASS_INVITATION,
                actor_user_id=int(r.uid),
                tenant_id=None,
                count=int(r.c),
                window_start=cutoff,
                window_end=now,
                details={"threshold": threshold, "window_hours": window_hours},
                severity="warn",
            )
        )
    return hits


def detect_mass_notification(
    db: Session, *, window_hours: int = 1, threshold: int | None = None
) -> list[DetectionHit]:
    """Bir tenant window_hours saatte threshold+ bildirim üretmiş mi?
    NotificationLog.parent_id → User.institution_id ile tenant tespit edilir.
    """
    threshold = threshold or THRESHOLD_MASS_NOTIFICATION_PER_HOUR
    now = _now()
    cutoff = now - timedelta(hours=window_hours)
    # parent_id'lerin institution'ını join ile bul
    rows = (
        db.query(
            User.institution_id.label("tid"),
            func.count(NotificationLog.id).label("c"),
        )
        .join(User, User.id == NotificationLog.parent_id)
        .filter(
            NotificationLog.queued_at >= cutoff,
            User.institution_id.isnot(None),
        )
        .group_by(User.institution_id)
        .having(func.count(NotificationLog.id) >= threshold)
        .all()
    )
    hits: list[DetectionHit] = []
    for r in rows:
        hits.append(
            DetectionHit(
                kind=KIND_MASS_NOTIFICATION,
                actor_user_id=None,
                tenant_id=int(r.tid),
                count=int(r.c),
                window_start=cutoff,
                window_end=now,
                details={"threshold": threshold, "window_hours": window_hours},
                severity="warn",
            )
        )
    return hits


def detect_multi_account_same_device(
    db: Session, *, window_hours: int = 24, threshold: int | None = None
) -> list[DetectionHit]:
    """Aynı UA + IP kombinasyonu window_hours içinde threshold+ farklı user_id
    ile login yapmış mı?"""
    threshold = threshold or THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS
    now = _now()
    cutoff = now - timedelta(hours=window_hours)
    # ActiveSession bazında ua+ip → distinct user_id say
    rows = (
        db.query(
            ActiveSession.ip.label("ip"),
            ActiveSession.user_agent.label("ua"),
            func.count(func.distinct(ActiveSession.user_id)).label("uc"),
        )
        .filter(
            ActiveSession.login_at >= cutoff,
            ActiveSession.ip.isnot(None),
            ActiveSession.user_agent.isnot(None),
            # Yanlış-pozitif fix: impersonation (sahte oturum) ile süper admin'in
            # KENDİ girişleri "çoklu hesap abuse" değildir — sayımdan dışla.
            ActiveSession.imp_by.is_(None),
            ActiveSession.role != UserRole.SUPER_ADMIN.value,
        )
        .group_by(ActiveSession.ip, ActiveSession.user_agent)
        .having(func.count(func.distinct(ActiveSession.user_id)) >= threshold)
        .all()
    )
    hits: list[DetectionHit] = []
    for r in rows:
        hits.append(
            DetectionHit(
                kind=KIND_MULTI_ACCOUNT,
                actor_user_id=None,
                tenant_id=None,
                count=int(r.uc),
                window_start=cutoff,
                window_end=now,
                details={
                    "ip": r.ip,
                    "user_agent": (r.ua or "")[:120],
                    "threshold": threshold,
                    "window_hours": window_hours,
                },
                severity="info" if int(r.uc) < threshold + 2 else "warn",
            )
        )
    return hits


def detect_unsubscribe_spike(
    db: Session, *, window_hours: int = 24, threshold: int | None = None
) -> list[DetectionHit]:
    """Bir tenant window_hours içinde threshold+ USER_PAUSE_ALERTS üretmiş mi?
    AuditLog.actor_id → User.institution_id ile tenant tespit edilir.
    """
    threshold = threshold or THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY
    now = _now()
    cutoff = now - timedelta(hours=window_hours)
    rows = (
        db.query(
            User.institution_id.label("tid"),
            func.count(AuditLog.id).label("c"),
        )
        .join(User, User.id == AuditLog.actor_id)
        .filter(
            AuditLog.action.in_([
                AuditAction.USER_PAUSE_ALERTS, AuditAction.USER_AUTO_PAUSE
            ]),
            AuditLog.created_at >= cutoff,
            User.institution_id.isnot(None),
        )
        .group_by(User.institution_id)
        .having(func.count(AuditLog.id) >= threshold)
        .all()
    )
    hits: list[DetectionHit] = []
    for r in rows:
        hits.append(
            DetectionHit(
                kind=KIND_UNSUBSCRIBE_SPIKE,
                actor_user_id=None,
                tenant_id=int(r.tid),
                count=int(r.c),
                window_start=cutoff,
                window_end=now,
                details={"threshold": threshold, "window_hours": window_hours},
                severity="warn",
            )
        )
    return hits


def detect_signup_velocity(
    db: Session, *, window_hours: int = 24, threshold: int | None = None
) -> list[DetectionHit]:
    """Aynı IP window_hours içinde threshold+ koç self-signup'ı yapmış mı?

    USER_CREATE audit'leri (details self_signup=true) IP'ye göre gruplanır.
    Çoklu-hesap çiftliği (#5) işareti — signup_guard hard-block'tan ayrı, süper
    admin görünürlüğü için. IP'siz audit'ler hariç.
    """
    from app.services.signup_guard import SIGNUP_IP_FLAG_THRESHOLD
    threshold = threshold or SIGNUP_IP_FLAG_THRESHOLD
    now = _now()
    cutoff = now - timedelta(hours=window_hours)
    rows = (
        db.query(
            AuditLog.ip_address.label("ip"),
            func.count(AuditLog.id).label("c"),
        )
        .filter(
            AuditLog.action == AuditAction.USER_CREATE,
            AuditLog.ip_address.isnot(None),
            AuditLog.created_at >= cutoff,
            AuditLog.details_json.like('%"self_signup": true%'),
        )
        .group_by(AuditLog.ip_address)
        .having(func.count(AuditLog.id) >= threshold)
        .all()
    )
    hits: list[DetectionHit] = []
    for r in rows:
        hits.append(
            DetectionHit(
                kind=KIND_SIGNUP_VELOCITY,
                actor_user_id=None,
                tenant_id=None,
                count=int(r.c),
                window_start=cutoff,
                window_end=now,
                details={"ip": r.ip, "threshold": threshold, "window_hours": window_hours},
                severity="warn" if int(r.c) >= threshold + 2 else "info",
            )
        )
    return hits


# ---------------------------- Run-all + listing ----------------------------


def run_all(db: Session) -> dict:
    """Tüm dedektörleri çalıştır, sinyalleri upsert et. Cron + manuel tarama için.
    Returns: {kind: hit_count} özet.
    """
    summary: dict[str, int] = {}
    for fn in (
        detect_mass_invitation,
        detect_mass_notification,
        detect_multi_account_same_device,
        detect_unsubscribe_spike,
        detect_signup_velocity,
    ):
        try:
            hits = fn(db)
        except Exception:
            logger.exception("abuse detector %s fail", fn.__name__)
            hits = []
        for h in hits:
            try:
                _upsert_signal(db, h, autocommit=False)
            except Exception:
                logger.exception("abuse upsert fail kind=%s", h.kind)
        summary[fn.__name__] = len(hits)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("abuse run_all commit fail")
    return summary


def list_signals(
    db: Session,
    *,
    only_open: bool = True,
    kind: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Sinyal listesi (UI için zenginleştirilmiş)."""
    q = db.query(AbuseSignal)
    if only_open:
        q = q.filter(AbuseSignal.resolved_at.is_(None))
    if kind:
        q = q.filter(AbuseSignal.kind == kind)
    q = q.order_by(desc(AbuseSignal.last_seen_at)).limit(limit)
    rows = q.all()

    # Toplu user/tenant lookup
    actor_ids = {r.actor_user_id for r in rows if r.actor_user_id}
    tenant_ids = {r.tenant_id for r in rows if r.tenant_id}
    users_map: dict[int, User] = {}
    if actor_ids:
        for u in db.query(User).filter(User.id.in_(actor_ids)).all():
            users_map[u.id] = u
    insts_map: dict[int, Institution] = {}
    if tenant_ids:
        for i in db.query(Institution).filter(Institution.id.in_(tenant_ids)).all():
            insts_map[i.id] = i

    out: list[dict] = []
    for r in rows:
        details: dict = {}
        if r.details_json:
            try:
                details = json.loads(r.details_json)
            except Exception:
                details = {}
        actor = users_map.get(r.actor_user_id) if r.actor_user_id else None
        tenant = insts_map.get(r.tenant_id) if r.tenant_id else None
        out.append({
            "id": r.id,
            "kind": r.kind,
            "kind_label": ABUSE_KIND_LABELS_TR.get(r.kind, r.kind),
            "severity": r.severity,
            "count": r.count,
            "window_start": _aware(r.window_start),
            "window_end": _aware(r.window_end),
            "detected_at": _aware(r.detected_at),
            "last_seen_at": _aware(r.last_seen_at),
            "resolved_at": _aware(r.resolved_at),
            "actor_user_id": r.actor_user_id,
            "actor_full_name": actor.full_name if actor else None,
            "actor_email": actor.email if actor else None,
            "tenant_id": r.tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "details": details,
        })
    return out


def resolve_signal(
    db: Session,
    *,
    signal_id: int,
    resolved_by_user_id: int,
    note: str | None,
    autocommit: bool = True,
) -> AbuseSignal | None:
    row = db.get(AbuseSignal, signal_id)
    if row is None or row.resolved_at is not None:
        return row
    row.resolved_at = _now()
    row.resolved_by_user_id = resolved_by_user_id
    row.resolution_note = (note or "")[:500] or None
    if autocommit:
        db.commit()
    return row


def open_signal_count(db: Session) -> int:
    return (
        db.query(func.count(AbuseSignal.id))
        .filter(AbuseSignal.resolved_at.is_(None))
        .scalar()
    ) or 0


__all__ = [
    "DetectionHit",
    "KIND_MASS_INVITATION",
    "KIND_MASS_NOTIFICATION",
    "KIND_MULTI_ACCOUNT",
    "KIND_UNSUBSCRIBE_SPIKE",
    "detect_mass_invitation",
    "detect_mass_notification",
    "detect_multi_account_same_device",
    "detect_unsubscribe_spike",
    "list_signals",
    "open_signal_count",
    "resolve_signal",
    "run_all",
]
