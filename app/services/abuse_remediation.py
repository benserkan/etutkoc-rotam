"""Katman 11.C+ — Abuse sinyaline toplu otomatik aksiyon.

Süper admin abuse sinyallerini sadece "Çöz" olarak işaretlemek yerine, sinyalin
türüne göre **somut bir aksiyon** alabilir:

  - mass_invitation         → o öğretmenin pencere içindeki davetlerini iptal et
                              (soft cancel: expires_at = now)
  - mass_notification       → o kurumun pencere içindeki QUEUED bildirimlerini
                              SUPPRESSED yap (gönderim engelle)
  - multi_account_same_device → o cihazın (UA+IP) aktif oturumlarını revoke et
  - unsubscribe_spike       → otomatik aksiyon yok (sadece bilgi)

Her aksiyon başarılı olursa sinyali otomatik "resolved" işaretler ve
resolution_note alanına ne yapıldığını yazar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    AbuseSignal,
    ActiveSession,
    NotificationLog,
    NotificationStatus,
    ParentInvitation,
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


@dataclass
class RemediationResult:
    ok: bool
    kind: str
    action: str
    affected_count: int
    note: str
    error: str | None = None


# ---------------------------- Per-kind handlers ----------------------------


def _remediate_mass_invitation(
    db: Session, *, sig: AbuseSignal, now: datetime
) -> RemediationResult:
    """Öğretmenin pencere içindeki kullanılmamış davetlerini expire et."""
    if not sig.actor_user_id:
        return RemediationResult(
            ok=False, kind=sig.kind, action="cancel_invitations",
            affected_count=0, note="Aktör user yok", error="no_actor",
        )
    window_start = _aware(sig.window_start)
    affected = (
        db.query(ParentInvitation)
        .filter(
            ParentInvitation.invited_by_id == sig.actor_user_id,
            ParentInvitation.created_at >= window_start,
            ParentInvitation.consumed_at.is_(None),
            ParentInvitation.expires_at > now,
        )
        .all()
    )
    count = 0
    for inv in affected:
        inv.expires_at = now
        count += 1
    return RemediationResult(
        ok=True, kind=sig.kind, action="cancel_invitations",
        affected_count=count,
        note=f"{count} davet iptal edildi (expires_at şimdiki zamana çekildi)",
    )


def _remediate_mass_notification(
    db: Session, *, sig: AbuseSignal, now: datetime
) -> RemediationResult:
    """Tenant'ın pencere içindeki QUEUED bildirimlerini SUPPRESSED yap."""
    if not sig.tenant_id:
        return RemediationResult(
            ok=False, kind=sig.kind, action="suppress_queued",
            affected_count=0, note="Tenant yok", error="no_tenant",
        )
    window_start = _aware(sig.window_start)
    affected = (
        db.query(NotificationLog)
        .join(User, User.id == NotificationLog.parent_id)
        .filter(
            User.institution_id == sig.tenant_id,
            NotificationLog.queued_at >= window_start,
            NotificationLog.status == NotificationStatus.QUEUED,
        )
        .all()
    )
    count = 0
    for n in affected:
        n.status = NotificationStatus.SUPPRESSED
        n.error = (n.error or "") + " [admin_remediation:abuse_signal]"
        count += 1
    return RemediationResult(
        ok=True, kind=sig.kind, action="suppress_queued",
        affected_count=count,
        note=f"{count} bekleyen bildirim bastırıldı (SUPPRESSED)",
    )


def _remediate_multi_account(
    db: Session, *, sig: AbuseSignal, now: datetime
) -> RemediationResult:
    """Aynı UA+IP'den aktif oturumları sonlandır.

    details_json içinde ip ve user_agent var.
    """
    import json
    try:
        details = json.loads(sig.details_json or "{}")
    except Exception:
        details = {}
    ip = details.get("ip")
    ua = details.get("user_agent")
    if not ip or not ua:
        return RemediationResult(
            ok=False, kind=sig.kind, action="revoke_sessions",
            affected_count=0, note="IP/UA yok", error="missing_details",
        )
    # UA tam eşleşmesi yerine prefix — details'taki UA 120 char truncate edilmiş
    rows = (
        db.query(ActiveSession)
        .filter(
            ActiveSession.terminated_at.is_(None),
            ActiveSession.ip == ip,
            ActiveSession.user_agent.like(ua[:80] + "%"),
        )
        .all()
    )
    count = 0
    for sess in rows:
        sess.terminated_at = now
        sess.termination_reason = "admin_revoke"
        count += 1
    return RemediationResult(
        ok=True, kind=sig.kind, action="revoke_sessions",
        affected_count=count,
        note=f"{count} aktif oturum uzaktan kapatıldı (IP={ip[:40]})",
    )


def _remediate_unsubscribe_spike(
    db: Session, *, sig: AbuseSignal, now: datetime
) -> RemediationResult:
    """Otomatik aksiyon yok — sadece izle/incele."""
    return RemediationResult(
        ok=False, kind=sig.kind, action="none",
        affected_count=0,
        note="Otomatik aksiyon yok — kullanıcı şikayeti olabilir; manuel incele",
        error="manual_only",
    )


HANDLERS = {
    "mass_invitation": _remediate_mass_invitation,
    "mass_notification": _remediate_mass_notification,
    "multi_account_same_device": _remediate_multi_account,
    "unsubscribe_spike": _remediate_unsubscribe_spike,
}


# ---------------------------- Public API ----------------------------


def auto_remediate_signal(
    db: Session,
    *,
    signal_id: int,
    by_user_id: int,
    autocommit: bool = True,
) -> RemediationResult:
    """Sinyal kind'ına göre uygun otomatik aksiyonu çalıştır.

    Aksiyon başarılı olursa sinyal otomatik resolved işaretlenir
    (resolution_note + resolved_by_user_id set edilir).
    """
    sig = db.get(AbuseSignal, signal_id)
    if sig is None:
        return RemediationResult(
            ok=False, kind="?", action="none", affected_count=0,
            note="Sinyal yok", error="not_found",
        )
    if sig.resolved_at is not None:
        return RemediationResult(
            ok=False, kind=sig.kind, action="none", affected_count=0,
            note="Sinyal zaten çözülmüş",
            error="already_resolved",
        )

    handler = HANDLERS.get(sig.kind)
    if handler is None:
        return RemediationResult(
            ok=False, kind=sig.kind, action="none", affected_count=0,
            note=f"'{sig.kind}' için handler tanımlı değil",
            error="no_handler",
        )

    now = _now()
    result = handler(db, sig=sig, now=now)

    # Aksiyon başarılıysa sinyali otomatik resolve et
    if result.ok:
        sig.resolved_at = now
        sig.resolved_by_user_id = by_user_id
        sig.resolution_note = f"[{result.action}] {result.note}"[:500]

    if autocommit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("abuse remediation commit fail signal=%s", signal_id)
            return RemediationResult(
                ok=False, kind=sig.kind, action=result.action,
                affected_count=0, note="DB hatası",
                error="commit_failed",
            )

    return result


# Kind → kullanıcıya gösterilecek buton etiketi
ACTION_BUTTON_LABELS_TR: dict[str, str] = {
    "mass_invitation": "Davetleri iptal et",
    "mass_notification": "Bildirimleri durdur",
    "multi_account_same_device": "Oturumları kapat",
    "unsubscribe_spike": "—",  # otomatik aksiyon yok
}


def get_action_label(kind: str) -> str | None:
    """UI için: bu kind hangi etikette buton gösterir? None ise gösterme."""
    label = ACTION_BUTTON_LABELS_TR.get(kind)
    if label is None or label == "—":
        return None
    return label


__all__ = [
    "ACTION_BUTTON_LABELS_TR",
    "HANDLERS",
    "RemediationResult",
    "auto_remediate_signal",
    "get_action_label",
]
