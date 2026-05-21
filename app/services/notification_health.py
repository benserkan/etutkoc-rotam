"""Katman 11.D — Bildirim teslimat sağlık paneli.

NotificationLog tablosundan zamana-yayılı sağlık göstergeleri çıkarır:
  - 24h ve 7d toplu başarı yüzdesi (sent / (sent + failed))
  - Kanal × durum matrisi (email/whatsapp/sms × queued/sent/failed/suppressed)
  - Bildirim türü × durum matrisi (daily_summary, drop_alert, exam_approaching...)
  - Suppress nedeni dağılımı (error field'ı): child_muted, unsubscribed, pref:*, vb.
  - En eski queued bekleyenin yaşı (dakika)
  - Son 7 gün günlük trend (sent/failed/queued count)

Hızlı: tek query'de count + GROUP BY. UI render sırasında tetiklenir (DB write yok).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _success_pct(sent: int, failed: int) -> float | None:
    """sent / (sent + failed). Sıfır bölme → None."""
    total = sent + failed
    if total == 0:
        return None
    return round(100.0 * sent / total, 1)


# ---------------------------- Üst özet ----------------------------


@dataclass
class WindowSummary:
    window_label: str
    window_hours: int
    total: int
    sent: int
    failed: int
    queued: int
    suppressed: int
    success_pct: float | None  # None = yeterli veri yok


def window_summary(db: Session, *, hours: int, label: str) -> WindowSummary:
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(NotificationLog.status, func.count(NotificationLog.id))
        .filter(NotificationLog.queued_at >= cutoff)
        .group_by(NotificationLog.status)
        .all()
    )
    by: dict[str, int] = {r[0].value if hasattr(r[0], "value") else str(r[0]): int(r[1]) for r in rows}
    sent = by.get("sent", 0)
    failed = by.get("failed", 0)
    queued = by.get("queued", 0)
    suppressed = by.get("suppressed", 0)
    total = sent + failed + queued + suppressed
    return WindowSummary(
        window_label=label,
        window_hours=hours,
        total=total,
        sent=sent,
        failed=failed,
        queued=queued,
        suppressed=suppressed,
        success_pct=_success_pct(sent, failed),
    )


def oldest_queued_minutes(db: Session) -> int | None:
    """En eski queued bekleyenin yaşı (dakika). Yoksa None."""
    oldest = (
        db.query(func.min(NotificationLog.queued_at))
        .filter(NotificationLog.status == NotificationStatus.QUEUED)
        .scalar()
    )
    if oldest is None:
        return None
    oldest = _aware(oldest)
    age_sec = (_now() - oldest).total_seconds()
    return max(0, int(age_sec / 60))


# ---------------------------- Matrisler ----------------------------


def channel_status_matrix(
    db: Session, *, hours: int = 24
) -> dict:
    """Channel × Status matrisi + her kanal için success%."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(
            NotificationLog.channel,
            NotificationLog.status,
            func.count(NotificationLog.id),
        )
        .filter(NotificationLog.queued_at >= cutoff)
        .group_by(NotificationLog.channel, NotificationLog.status)
        .all()
    )
    # init
    channels = [c.value for c in NotificationChannel]
    statuses = [s.value for s in NotificationStatus]
    matrix: dict[str, dict[str, int]] = {
        c: {s: 0 for s in statuses} for c in channels
    }
    for ch, st, c in rows:
        ch_v = ch.value if hasattr(ch, "value") else str(ch)
        st_v = st.value if hasattr(st, "value") else str(st)
        if ch_v in matrix and st_v in matrix[ch_v]:
            matrix[ch_v][st_v] = int(c)
    rollups: dict[str, dict] = {}
    for ch in channels:
        sent = matrix[ch]["sent"]
        failed = matrix[ch]["failed"]
        rollups[ch] = {
            "total": sum(matrix[ch].values()),
            "success_pct": _success_pct(sent, failed),
        }
    return {
        "channels": channels,
        "statuses": statuses,
        "matrix": matrix,
        "rollups": rollups,
        "window_hours": hours,
    }


def kind_status_matrix(db: Session, *, hours: int = 24) -> dict:
    """Bildirim türü × durum + her kind için success%."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(
            NotificationLog.kind,
            NotificationLog.status,
            func.count(NotificationLog.id),
        )
        .filter(NotificationLog.queued_at >= cutoff)
        .group_by(NotificationLog.kind, NotificationLog.status)
        .all()
    )
    kinds = [k.value for k in NotificationKind]
    statuses = [s.value for s in NotificationStatus]
    matrix: dict[str, dict[str, int]] = {
        k: {s: 0 for s in statuses} for k in kinds
    }
    for kd, st, c in rows:
        kd_v = kd.value if hasattr(kd, "value") else str(kd)
        st_v = st.value if hasattr(st, "value") else str(st)
        if kd_v in matrix and st_v in matrix[kd_v]:
            matrix[kd_v][st_v] = int(c)
    rollups = {}
    for k in kinds:
        sent = matrix[k]["sent"]
        failed = matrix[k]["failed"]
        rollups[k] = {
            "total": sum(matrix[k].values()),
            "success_pct": _success_pct(sent, failed),
        }
    return {
        "kinds": kinds,
        "statuses": statuses,
        "matrix": matrix,
        "rollups": rollups,
        "window_hours": hours,
    }


# ---------------------------- Suppress reason dağılımı ----------------------------


# error field'ı suppressed kayıtlarda genelde tek anahtar kelime/aile:
# "child_muted", "unsubscribed", "whatsapp_not_enabled", "pref:daily_summary", vb.
# Bunları aileler halinde gruplayalım.
_SUPPRESS_FAMILIES = [
    ("pref_*", re.compile(r"\bpref:?", re.IGNORECASE), "Kullanıcı tercihi kapalı"),
    ("child_muted", re.compile(r"child[_\s]?muted", re.IGNORECASE), "Çocuk susturulmuş"),
    ("unsubscribed", re.compile(r"unsubscrib", re.IGNORECASE), "Aboneliği iptal etti"),
    ("whatsapp_off", re.compile(r"whatsapp[_\s]?(not[_\s]?enabled|off)", re.IGNORECASE), "WhatsApp kapalı"),
    ("quiet_hours", re.compile(r"quiet[_\s]?hours", re.IGNORECASE), "Sessiz saat"),
    ("daily_cap", re.compile(r"daily[_\s]?cap", re.IGNORECASE), "Günlük tavan"),
    ("invalid_recipient", re.compile(r"invalid[_\s]?recipient|no[_\s]?email|no[_\s]?phone", re.IGNORECASE), "Alıcı geçersiz"),
]


def _classify_suppress(error: str | None) -> tuple[str, str]:
    """error metnini aileye eşle. (slug, label_tr) döner."""
    if not error:
        return ("unknown", "Belirsiz")
    for slug, regex, label in _SUPPRESS_FAMILIES:
        if regex.search(error):
            return (slug, label)
    return ("other", "Diğer")


def suppress_reason_distribution(db: Session, *, hours: int = 24) -> list[dict]:
    """Suppressed kayıtlardaki neden dağılımı (descending)."""
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(NotificationLog.error, func.count(NotificationLog.id))
        .filter(
            NotificationLog.status == NotificationStatus.SUPPRESSED,
            NotificationLog.queued_at >= cutoff,
        )
        .group_by(NotificationLog.error)
        .all()
    )
    family_count: dict[tuple[str, str], int] = defaultdict(int)
    for err, c in rows:
        slug, label = _classify_suppress(err)
        family_count[(slug, label)] += int(c)
    out = [
        {"slug": k[0], "label": k[1], "count": v}
        for k, v in family_count.items()
    ]
    out.sort(key=lambda r: r["count"], reverse=True)
    return out


# ---------------------------- Günlük trend ----------------------------


def daily_trend(db: Session, *, days: int = 7) -> list[dict]:
    """Son N gün için günlük sent/failed/queued/suppressed sayımı.

    SQLite + tzinfo karışıklığını önlemek için Python tarafında bucket yapıyoruz.
    """
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(NotificationLog.queued_at, NotificationLog.status)
        .filter(NotificationLog.queued_at >= cutoff)
        .all()
    )
    buckets: dict[str, dict[str, int]] = {}
    now = _now()
    # initialize last N days
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).date().isoformat()
        buckets[day] = {"sent": 0, "failed": 0, "queued": 0, "suppressed": 0}
    for qa, st in rows:
        qa = _aware(qa)
        if qa is None:
            continue
        day = qa.date().isoformat()
        if day not in buckets:
            continue
        st_v = st.value if hasattr(st, "value") else str(st)
        if st_v in buckets[day]:
            buckets[day][st_v] += 1
    return [
        {
            "day": day,
            "sent": v["sent"],
            "failed": v["failed"],
            "queued": v["queued"],
            "suppressed": v["suppressed"],
            "total": sum(v.values()),
            "success_pct": _success_pct(v["sent"], v["failed"]),
        }
        for day, v in buckets.items()
    ]


# ---------------------------- Son hatalar (kim, ne zaman, ne) ----------------------------


def recent_failures(
    db: Session, *, hours: int = 24, limit: int = 30
) -> list[dict]:
    """Son N saat içindeki FAILED bildirimler — UI'da satır satır gösterim için.

    Admin "4 hata" gördüğünde hangi veliye/öğrenciye, hangi kanalda, hangi hata
    mesajıyla başarısız olduğunu görmek ister. UI'nın "neyi düzelteyim" sorusunun
    cevabı.
    """
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(NotificationLog)
        .filter(
            NotificationLog.status == NotificationStatus.FAILED,
            NotificationLog.queued_at >= cutoff,
        )
        .order_by(NotificationLog.queued_at.desc())
        .limit(limit)
        .all()
    )
    parent_ids = {r.parent_id for r in rows if r.parent_id}
    student_ids = {r.student_id for r in rows if r.student_id}
    user_ids = parent_ids | student_ids
    users_map: dict[int, User] = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            users_map[u.id] = u
    out: list[dict] = []
    for r in rows:
        parent = users_map.get(r.parent_id) if r.parent_id else None
        student = users_map.get(r.student_id) if r.student_id else None
        out.append({
            "id": r.id,
            "queued_at": _aware(r.queued_at),
            "parent_id": r.parent_id,
            "parent_name": parent.full_name if parent else None,
            "parent_email": parent.email if parent else None,
            "student_id": r.student_id,
            "student_name": student.full_name if student else None,
            "kind": r.kind.value if hasattr(r.kind, "value") else str(r.kind),
            "channel": r.channel.value if hasattr(r.channel, "value") else str(r.channel),
            "attempts": r.attempts,
            "error": (r.error or "").strip(),
        })
    return out


# ---------------------------- Aggregator ----------------------------


def get_health_data(db: Session) -> dict:
    """Pano render için toplu veri."""
    s24 = window_summary(db, hours=24, label="Son 24 saat")
    s7d = window_summary(db, hours=24 * 7, label="Son 7 gün")
    return {
        "generated_at": _now(),
        "summary_24h": s24,
        "summary_7d": s7d,
        "oldest_queued_minutes": oldest_queued_minutes(db),
        "channel_matrix_24h": channel_status_matrix(db, hours=24),
        "kind_matrix_24h": kind_status_matrix(db, hours=24),
        "suppress_distribution_24h": suppress_reason_distribution(db, hours=24),
        "daily_trend_7d": daily_trend(db, days=7),
        "recent_failures_24h": recent_failures(db, hours=24, limit=30),
    }


__all__ = [
    "WindowSummary",
    "channel_status_matrix",
    "daily_trend",
    "get_health_data",
    "kind_status_matrix",
    "oldest_queued_minutes",
    "recent_failures",
    "suppress_reason_distribution",
    "window_summary",
]
