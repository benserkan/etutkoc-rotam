"""Veli Güveni Görünürlüğü — kurum yöneticisi için (KP3, 2026-05-20).

Kurumun veli nezdindeki değeri: veli kapsaması + iletişim sağlığı. Kayıt
yenileme/tavsiye bu güvenden beslenir.

Metrikler (kurum aktif öğrencileri üzerinden):
  • Veli kapsaması — kaç öğrencinin bağlı velisi var (ParentStudentLink)
  • Aktif veli — son N günde giriş yapan veli sayısı
  • Bekleyen davet — kabul edilmemiş, süresi geçmemiş ParentInvitation
  • Bildirim teslimatı — velilere giden NotificationLog başarı oranı + kanal kırılımı

Veri yapısı: ParentStudentLink + ParentInvitation + NotificationLog (student_id
kurum filtreli) + User.last_login_at. Migration YOK.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from sqlalchemy.orm import aliased

from app.models import (
    NOTIFICATION_KIND_LABELS,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentInvitation,
    ParentStudentLink,
    User,
    UserRole,
)

CHANNEL_LABELS = {"email": "E-posta", "whatsapp": "WhatsApp", "sms": "SMS"}
STATUS_LABELS = {"sent": "Ulaştı", "failed": "Başarısız", "suppressed": "Engellendi", "queued": "Kuyrukta"}


def _success_pct(sent: int, failed: int) -> int | None:
    total = sent + failed
    if total <= 0:
        return None
    return int(round(100 * sent / total))


def compute_parent_trust(db: Session, *, institution_id: int, days: int = 30) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    student_ids = [
        int(r[0]) for r in db.query(User.id).filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        ).all()
    ]
    total_students = len(student_ids)

    if not student_ids:
        return {
            "summary": {
                "total_students": 0, "covered_students": 0, "coverage_pct": None,
                "parent_count": 0, "active_parents": 0, "pending_invites": 0,
                "notif_sent": 0, "notif_failed": 0, "notif_suppressed": 0,
                "notif_success_pct": None, "days": days,
            },
            "channels": [],
        }

    # Veli kapsaması + veli kümesi
    link_rows = (
        db.query(ParentStudentLink.parent_id, ParentStudentLink.student_id)
        .filter(ParentStudentLink.student_id.in_(student_ids))
        .all()
    )
    covered_students = {int(r.student_id) for r in link_rows}
    parent_ids = {int(r.parent_id) for r in link_rows}

    # Aktif veli (son N gün giriş)
    active_parents = 0
    if parent_ids:
        active_parents = int(
            db.query(func.count(User.id)).filter(
                User.id.in_(parent_ids),
                User.role == UserRole.PARENT,
                User.last_login_at >= cutoff,
            ).scalar() or 0
        )

    # Bekleyen davet (kabul edilmemiş + süresi geçmemiş)
    pending_invites = int(
        db.query(func.count(ParentInvitation.id)).filter(
            ParentInvitation.student_id.in_(student_ids),
            ParentInvitation.consumed_at.is_(None),
            ParentInvitation.expires_at > now,
        ).scalar() or 0
    )

    # Bildirim teslimatı (son N gün) — durum + kanal kırılımı
    notif_rows = (
        db.query(
            NotificationLog.channel,
            NotificationLog.status,
            func.count(NotificationLog.id),
        )
        .filter(
            NotificationLog.student_id.in_(student_ids),
            NotificationLog.queued_at >= cutoff,
        )
        .group_by(NotificationLog.channel, NotificationLog.status)
        .all()
    )
    status_total = {"sent": 0, "failed": 0, "suppressed": 0, "queued": 0}
    by_channel: dict[str, dict] = {}
    for ch, st, c in notif_rows:
        ch_v = ch.value if hasattr(ch, "value") else str(ch)
        st_v = st.value if hasattr(st, "value") else str(st)
        c = int(c)
        if st_v in status_total:
            status_total[st_v] += c
        chan = by_channel.setdefault(ch_v, {"sent": 0, "failed": 0, "suppressed": 0, "queued": 0})
        if st_v in chan:
            chan[st_v] += c

    channels = []
    for ch_v, st in by_channel.items():
        channels.append({
            "channel": ch_v,
            "channel_label": CHANNEL_LABELS.get(ch_v, ch_v),
            "sent": st["sent"],
            "failed": st["failed"],
            "suppressed": st["suppressed"],
            "success_pct": _success_pct(st["sent"], st["failed"]),
        })
    channels.sort(key=lambda c: -(c["sent"] + c["failed"]))

    return {
        "summary": {
            "total_students": total_students,
            "covered_students": len(covered_students),
            "coverage_pct": int(round(100 * len(covered_students) / total_students)),
            "parent_count": len(parent_ids),
            "active_parents": active_parents,
            "pending_invites": pending_invites,
            "notif_sent": status_total["sent"],
            "notif_failed": status_total["failed"],
            "notif_suppressed": status_total["suppressed"],
            "notif_success_pct": _success_pct(status_total["sent"], status_total["failed"]),
            "days": days,
        },
        "channels": channels,
    }


def list_notifications(
    db: Session,
    *,
    institution_id: int,
    days: int = 30,
    status_filter: str | None = None,
    limit: int = 200,
) -> tuple[list[dict], int]:
    """Kurum bağlamında son N gün NotificationLog detayı.

    Filtre: status_filter (sent/failed/suppressed/queued) veya None=hepsi.
    Geri dönüş: (items, total_count) — total_count filtre uygulanmış toplam
    (limit'ten önceki).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    ParentU = aliased(User)
    StudentU = aliased(User)
    Teacher = aliased(User)

    q = (
        db.query(NotificationLog, ParentU, StudentU)
        .outerjoin(ParentU, NotificationLog.parent_id == ParentU.id)
        .join(StudentU, NotificationLog.student_id == StudentU.id)
        .join(Teacher, StudentU.teacher_id == Teacher.id)
        .filter(
            Teacher.institution_id == institution_id,
            NotificationLog.created_at >= since,
        )
    )
    if status_filter:
        try:
            q = q.filter(NotificationLog.status == NotificationStatus(status_filter))
        except ValueError:
            pass

    total_count = q.count()
    rows = q.order_by(NotificationLog.created_at.desc()).limit(limit).all()

    items: list[dict] = []
    for log, parent_user, student_user in rows:
        items.append({
            "id": log.id,
            "status": log.status.value,
            "status_label": STATUS_LABELS.get(log.status.value, log.status.value),
            "kind": log.kind.value,
            "kind_label": NOTIFICATION_KIND_LABELS.get(log.kind, log.kind.value),
            "channel": log.channel.value,
            "channel_label": CHANNEL_LABELS.get(log.channel.value, log.channel.value),
            "subject": log.subject,
            "error": log.error,
            "student_name": student_user.full_name if student_user else None,
            "parent_email": parent_user.email if parent_user else None,
            "parent_name": parent_user.full_name if parent_user else None,
            "created_at": log.created_at,
            "sent_at": log.sent_at,
        })
    return items, total_count
