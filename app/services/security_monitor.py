"""Katman 11.A — Güvenlik Kamerası servisi.

Üç ana işlev:
  1) Aktif oturumların yönetimi (kaydet, heartbeat, revoke, sorgula)
  2) Şüpheli IP takibi (her başarısız login'de upsert + otomatik blok kararı)
  3) Süper admin panosu için veri toplama (active sessions, blocked IPs,
     son 24h failed login dağılımı, kritik aksiyon akışı)

Mevcut auth_security.register_failed_login User üzerinde fail sayar (hesap
lockout için); burada IP üzerinde sayıyoruz (brute force koruması için).
İki ayrı boyut, ayrı tablolar, birbirini etkilemez.

Otomatik blok eşikleri (BRUTE_FORCE_*):
  - 1 saatte 10+ farklı email denemesi → 1 saat blok ("auto_emails_threshold")
  - 1 saatte 30+ toplam başarısız login → 1 saat blok ("auto_fails_threshold")

Sayaç penceresi: 1 saat — son başarısız login 1 saatten eski ise sayaç sıfırlanır
(yeni bir saldırı turu olarak görülür).
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models import (
    ActiveSession,
    AuditAction,
    AuditLog,
    SuspiciousIp,
    User,
)


logger = logging.getLogger(__name__)


# Brute force eşikleri (1 saatlik pencere)
BRUTE_FORCE_WINDOW_HOURS = 1
BRUTE_FORCE_EMAILS_THRESHOLD = 10
BRUTE_FORCE_FAILS_THRESHOLD = 30
AUTO_BLOCK_DURATION_HOURS = 1

# Aktif oturum kabul edilen son aktivite penceresi (sliding session)
ACTIVE_SESSION_HEARTBEAT_WINDOW_HOURS = 24

# distinct_emails JSON listesinde tutulan max email sayısı
MAX_DISTINCT_EMAILS_STORED = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def generate_session_token() -> str:
    """URL-safe 32-byte rastgele token (43 karakter)."""
    return secrets.token_urlsafe(32)


# ---------------------------- Active sessions ----------------------------


def record_session_start(
    db: Session,
    *,
    user: User,
    session_token: str,
    ip: str | None,
    user_agent: str | None,
    autocommit: bool = True,
    imp_by: int | None = None,
) -> ActiveSession:
    """Login başarılı olduğunda ActiveSession kaydı oluştur.

    session_token: starlette session'a yazılacak unique value (bkz.
    generate_session_token). Aynı token zaten varsa o satır canlı kabul edilir
    (idempotent — örn. login tekrarlandı).
    """
    now = _now()
    existing = (
        db.query(ActiveSession)
        .filter(ActiveSession.session_token == session_token)
        .first()
    )
    if existing is not None:
        existing.last_seen_at = now
        if existing.terminated_at is not None:
            existing.terminated_at = None
            existing.terminated_by_user_id = None
            existing.termination_reason = None
        if autocommit:
            db.commit()
        return existing
    row = ActiveSession(
        session_token=session_token,
        user_id=user.id,
        role=user.role.value,
        ip=(ip or "")[:64] or None,
        user_agent=(user_agent or "")[:255] or None,
        login_at=now,
        last_seen_at=now,
        imp_by=imp_by,
    )
    db.add(row)
    if autocommit:
        db.commit()
        db.refresh(row)
    return row


def heartbeat(
    db: Session, *, session_token: str, now: datetime | None = None
) -> bool:
    """last_seen_at güncelle. Oturum sonlandırılmışsa False döner.

    Çağıran (deps.py veya middleware) False ise request.session.clear() yapar.
    """
    if not session_token:
        return True  # token yoksa eski oturum — eski davranışı bozma
    now = now or _now()
    row = (
        db.query(ActiveSession)
        .filter(ActiveSession.session_token == session_token)
        .first()
    )
    if row is None:
        return True  # bilinmeyen token — eski / pre-migration oturum, geçir
    if row.terminated_at is not None:
        return False
    row.last_seen_at = now
    try:
        db.commit()
    except Exception:
        db.rollback()
    return True


def terminate_session(
    db: Session,
    *,
    session_token: str,
    reason: str,
    by_user_id: int | None = None,
    autocommit: bool = True,
) -> ActiveSession | None:
    """Bir oturumu kapat. Reason: logout / admin_revoke / password_change."""
    row = (
        db.query(ActiveSession)
        .filter(ActiveSession.session_token == session_token)
        .first()
    )
    if row is None or row.terminated_at is not None:
        return row
    row.terminated_at = _now()
    row.terminated_by_user_id = by_user_id
    row.termination_reason = reason[:40]
    if autocommit:
        db.commit()
    return row


def list_active_sessions(
    db: Session, *, limit: int = 50
) -> list[dict]:
    """Şu an canlı (terminated_at NULL ve last_seen_at son 24h içinde) oturumlar."""
    cutoff = _now() - timedelta(hours=ACTIVE_SESSION_HEARTBEAT_WINDOW_HOURS)
    rows = (
        db.query(ActiveSession, User)
        .join(User, User.id == ActiveSession.user_id)
        .filter(
            ActiveSession.terminated_at.is_(None),
            ActiveSession.last_seen_at >= cutoff,
        )
        .order_by(desc(ActiveSession.last_seen_at))
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    now = _now()
    for sess, user in rows:
        login_at = _aware(sess.login_at) or now
        last_seen_at = _aware(sess.last_seen_at) or now
        out.append({
            "id": sess.id,
            "session_token": sess.session_token,
            "user_id": user.id,
            "user_email": user.email,
            "user_full_name": user.full_name,
            "role": sess.role,
            "ip": sess.ip,
            "user_agent": sess.user_agent or "",
            "login_at": login_at,
            "last_seen_at": last_seen_at,
            "idle_seconds": int((now - last_seen_at).total_seconds()),
            "age_seconds": int((now - login_at).total_seconds()),
        })
    return out


def revoke_session_by_token(
    db: Session, *, session_token: str, by_user_id: int
) -> bool:
    """Admin tarafından uzaktan oturum sonlandır."""
    row = terminate_session(
        db, session_token=session_token, reason="admin_revoke", by_user_id=by_user_id
    )
    return row is not None


# ---------------------------- Suspicious IPs ----------------------------


def _decode_emails(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return []


def _encode_emails(emails: list[str]) -> str:
    return json.dumps(emails[-MAX_DISTINCT_EMAILS_STORED:], ensure_ascii=False)


def record_failed_login_ip(
    db: Session,
    *,
    ip: str | None,
    email_attempted: str | None,
    autocommit: bool = True,
) -> SuspiciousIp | None:
    """Başarısız login'i SuspiciousIp tablosuna işle. Eşik aşılırsa otomatik blok.

    Pencere mantığı: last_seen_at 1 saatten eski ise sayaçları sıfırla
    (yeni saldırı turu). first_seen_at korunur (uzun süredir göz altında).
    """
    if not ip:
        return None
    ip = ip[:64]
    now = _now()
    row = db.query(SuspiciousIp).filter(SuspiciousIp.ip == ip).first()

    if row is None:
        emails = [email_attempted] if email_attempted else []
        row = SuspiciousIp(
            ip=ip,
            fail_count=1,
            distinct_email_count=len(emails),
            distinct_emails_json=_encode_emails(emails) if emails else None,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
        if autocommit:
            db.commit()
            db.refresh(row)
        return row

    # Pencere reset?
    last = _aware(row.last_seen_at) or now
    window_age_hours = (now - last).total_seconds() / 3600.0
    if window_age_hours >= BRUTE_FORCE_WINDOW_HOURS:
        row.fail_count = 0
        row.distinct_email_count = 0
        row.distinct_emails_json = None

    row.fail_count = (row.fail_count or 0) + 1
    row.last_seen_at = now

    if email_attempted:
        emails = _decode_emails(row.distinct_emails_json)
        if email_attempted not in emails:
            emails.append(email_attempted)
            row.distinct_emails_json = _encode_emails(emails)
            row.distinct_email_count = min(
                len(emails), MAX_DISTINCT_EMAILS_STORED
            )

    # Otomatik blok kararı (zaten manuel blok varsa dokunma)
    blocked_until = _aware(row.blocked_until)
    is_currently_blocked = blocked_until is not None and blocked_until > now
    if not is_currently_blocked:
        if row.distinct_email_count >= BRUTE_FORCE_EMAILS_THRESHOLD:
            row.blocked_until = now + timedelta(hours=AUTO_BLOCK_DURATION_HOURS)
            row.block_reason = "auto_emails_threshold"
            row.blocked_by_user_id = None
        elif row.fail_count >= BRUTE_FORCE_FAILS_THRESHOLD:
            row.blocked_until = now + timedelta(hours=AUTO_BLOCK_DURATION_HOURS)
            row.block_reason = "auto_fails_threshold"
            row.blocked_by_user_id = None

    if autocommit:
        db.commit()
        db.refresh(row)
    return row


def is_ip_blocked(db: Session, *, ip: str | None) -> tuple[bool, SuspiciousIp | None]:
    """IP şu an blok altında mı? (bool, row) döner."""
    if not ip:
        return False, None
    row = db.query(SuspiciousIp).filter(SuspiciousIp.ip == ip[:64]).first()
    if row is None or row.blocked_until is None:
        return False, row
    blocked_until = _aware(row.blocked_until)
    if blocked_until is None:
        return False, row
    return blocked_until > _now(), row


def block_ip_manual(
    db: Session,
    *,
    ip: str,
    hours: int,
    note: str | None,
    by_user_id: int,
    autocommit: bool = True,
) -> SuspiciousIp:
    """Süper admin manuel IP blok ekler/uzatır."""
    now = _now()
    row = db.query(SuspiciousIp).filter(SuspiciousIp.ip == ip[:64]).first()
    if row is None:
        row = SuspiciousIp(
            ip=ip[:64],
            fail_count=0,
            distinct_email_count=0,
            first_seen_at=now,
            last_seen_at=now,
        )
        db.add(row)
    row.blocked_until = now + timedelta(hours=hours)
    row.block_reason = "manual"
    row.blocked_by_user_id = by_user_id
    row.block_note = (note or "")[:255] or None
    row.last_seen_at = now
    if autocommit:
        db.commit()
        db.refresh(row)
    return row


def unblock_ip(db: Session, *, ip: str, autocommit: bool = True) -> bool:
    """Manuel veya otomatik blok'u kaldır (geçmişe çek)."""
    row = db.query(SuspiciousIp).filter(SuspiciousIp.ip == ip[:64]).first()
    if row is None:
        return False
    row.blocked_until = None
    row.block_reason = None
    row.blocked_by_user_id = None
    row.block_note = None
    if autocommit:
        db.commit()
    return True


def list_suspicious_ips(
    db: Session,
    *,
    only_blocked: bool = False,
    limit: int = 50,
) -> list[dict]:
    q = db.query(SuspiciousIp)
    if only_blocked:
        q = q.filter(SuspiciousIp.blocked_until.isnot(None))
        q = q.filter(SuspiciousIp.blocked_until > _now())
    q = q.order_by(
        desc(SuspiciousIp.blocked_until.isnot(None)),
        desc(SuspiciousIp.last_seen_at),
    ).limit(limit)
    now = _now()
    out: list[dict] = []
    for row in q.all():
        blocked_until = _aware(row.blocked_until)
        is_blocked = blocked_until is not None and blocked_until > now
        emails = _decode_emails(row.distinct_emails_json)
        out.append({
            "id": row.id,
            "ip": row.ip,
            "fail_count": row.fail_count or 0,
            "distinct_email_count": row.distinct_email_count or 0,
            "distinct_emails": emails,
            "first_seen_at": _aware(row.first_seen_at) or now,
            "last_seen_at": _aware(row.last_seen_at) or now,
            "is_blocked": is_blocked,
            "blocked_until": blocked_until,
            "block_reason": row.block_reason,
            "block_note": row.block_note,
        })
    return out


# ---------------------------- Dashboard data ----------------------------


@dataclass
class FailedLoginBucket:
    ip: str | None
    fail_count: int
    distinct_email_count: int
    last_seen_at: datetime


def recent_failed_login_ips(
    db: Session, *, hours: int = 24, limit: int = 20
) -> list[FailedLoginBucket]:
    """Son N saatte başarısız login üreten IP'leri, fail sayısına göre sıralı.

    AuditLog tablosundan agregasyon (LOGIN_FAILED + LOGIN_LOCKED).
    """
    cutoff = _now() - timedelta(hours=hours)
    q = (
        db.query(
            AuditLog.ip_address.label("ip"),
            func.count(AuditLog.id).label("fail_count"),
            func.count(func.distinct(AuditLog.email_attempted)).label("dec"),
            func.max(AuditLog.created_at).label("last_seen_at"),
        )
        .filter(
            AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
            AuditLog.created_at >= cutoff,
        )
        .group_by(AuditLog.ip_address)
        .order_by(desc(func.count(AuditLog.id)))
        .limit(limit)
    )
    out: list[FailedLoginBucket] = []
    for r in q.all():
        last = _aware(r.last_seen_at) or _now()
        out.append(
            FailedLoginBucket(
                ip=r.ip,
                fail_count=int(r.fail_count or 0),
                distinct_email_count=int(r.dec or 0),
                last_seen_at=last,
            )
        )
    return out


# Kritik audit aksiyonları (panoda ayrı widget)
CRITICAL_AUDIT_ACTIONS = frozenset({
    AuditAction.USER_DELETE,
    AuditAction.USER_DEACTIVATE,
    AuditAction.ROLE_CHANGE,
    AuditAction.PASSWORD_RESET,
    AuditAction.INSTITUTION_DELETE,
    AuditAction.IMPERSONATE_START,
    AuditAction.LOGIN_LOCKED,
})


def recent_critical_audits(db: Session, *, limit: int = 20) -> list[AuditLog]:
    q = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(list(CRITICAL_AUDIT_ACTIONS)))
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    return list(q.all())


def super_admin_logins_24h(db: Session) -> list[AuditLog]:
    """Son 24 saatte SUPER_ADMIN giriş başarıları (saat dışı kontrol için)."""
    cutoff = _now() - timedelta(hours=24)
    # SUPER_ADMIN filtresi için AuditLog.actor_id'den user'a join
    from app.models import UserRole
    q = (
        db.query(AuditLog)
        .join(User, User.id == AuditLog.actor_id)
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            User.role == UserRole.SUPER_ADMIN,
            AuditLog.created_at >= cutoff,
        )
        .order_by(desc(AuditLog.created_at))
    )
    return list(q.all())


def get_security_dashboard_data(db: Session) -> dict:
    """Kamera panosu için toplu veri."""
    now = _now()
    active = list_active_sessions(db, limit=50)
    suspicious = list_suspicious_ips(db, only_blocked=False, limit=20)
    blocked = [r for r in suspicious if r["is_blocked"]]
    cutoff_24h = now - timedelta(hours=24)
    failed_24h_count = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
            AuditLog.created_at >= cutoff_24h,
        )
        .scalar()
    ) or 0
    failed_ips = recent_failed_login_ips(db, hours=24, limit=10)
    critical = recent_critical_audits(db, limit=15)
    sa_logins = super_admin_logins_24h(db)

    # Rol dağılımı aktif oturumlar
    role_counts: dict[str, int] = {}
    for s in active:
        role_counts[s["role"]] = role_counts.get(s["role"], 0) + 1

    return {
        "generated_at": now,
        "summary": {
            "active_sessions": len(active),
            "blocked_ips": len(blocked),
            "watched_ips": len(suspicious),
            "failed_24h": int(failed_24h_count),
            "critical_24h": sum(
                1 for a in critical
                if _aware(a.created_at) and _aware(a.created_at) >= cutoff_24h
            ),
            "super_admin_logins_24h": len(sa_logins),
        },
        "role_counts": role_counts,
        "active_sessions": active,
        "suspicious_ips": suspicious,
        "failed_login_buckets": failed_ips,
        "critical_audits": critical,
        "super_admin_logins": sa_logins,
    }


def humanize_ago(seconds: int) -> str:
    """Saniyeyi Türkçe "X dk önce" tarzı etikete çevir (curator_dashboard ile aynı stil)."""
    s = max(0, int(seconds))
    if s < 60:
        return "az önce"
    if s < 3600:
        return f"{s // 60} dk önce"
    if s < 86400:
        return f"{s // 3600} saat önce"
    if s < 86400 * 14:
        return f"{s // 86400} gün önce"
    return f"{s // (86400 * 7)} hafta önce"


__all__ = [
    "BRUTE_FORCE_EMAILS_THRESHOLD",
    "BRUTE_FORCE_FAILS_THRESHOLD",
    "BRUTE_FORCE_WINDOW_HOURS",
    "AUTO_BLOCK_DURATION_HOURS",
    "CRITICAL_AUDIT_ACTIONS",
    "FailedLoginBucket",
    "block_ip_manual",
    "generate_session_token",
    "get_security_dashboard_data",
    "heartbeat",
    "humanize_ago",
    "is_ip_blocked",
    "list_active_sessions",
    "list_suspicious_ips",
    "recent_critical_audits",
    "recent_failed_login_ips",
    "record_failed_login_ip",
    "record_session_start",
    "revoke_session_by_token",
    "super_admin_logins_24h",
    "terminate_session",
    "unblock_ip",
]
