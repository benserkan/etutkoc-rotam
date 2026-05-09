"""Stage 8 — Tenant backup snapshot.

Bir kurumun tüm verisini tek JSON dict'te toplar. Süper admin
'/admin/institutions/{id}/backup' endpoint'inden indirir.

Kullanım amaçları:
- Müşteri terk ederse veri taşıma (KVKK madde 11 — veri taşıma hakkı)
- Migrasyon / geri yükleme provası
- Ad-hoc inceleme / yedek

İçerik (kurum ile sınırlı):
- institution metadata
- users (kurum altındaki tüm aktif/pasif) — password_hash YOK
- books + sections (kurum öğretmenlerine ait)
- tasks + task_book_items (kurum öğrencilerinin)
- notification_logs (son 30 gün)
- audit_logs (kurum hedefli, son 90 gün)
- credit_account + usage_events (kurum havuzu)
- admin_weekly_digests (tüm geçmiş)
- feature_flag_overrides + quota_overrides
- parent_student_links (kurum öğrencileriyle ilgili)

Hassas alanlar sanitize:
- password_hash → 'REDACTED'
- session token / cookie YOK (DB'de tutulmuyor zaten)
- failed_login_count tutulur (audit önemli olabilir)

Performans: 10K öğrenci × 100 task × 2 item = ~2M satır extreme; pratikte
<1M satır bekleniyor. Bellek dostu için JSON streaming yok — tek dict.
İhtiyaç olunca chunked dump'a geçilir.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AdminWeeklyDigest,
    AuditLog,
    Book,
    BookSection,
    CreditAccount,
    FeatureFlagOverride,
    Institution,
    InstitutionQuotaOverride,
    NotificationLog,
    ParentStudentLink,
    Task,
    TaskBookItem,
    UsageEvent,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# Audit + notification için look-back penceresi (büyük export'tan kaçınmak için)
AUDIT_LOOKBACK_DAYS = 90
NOTIFICATION_LOOKBACK_DAYS = 30


def _serialize_dt(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _user_to_dict(u: User) -> dict[str, Any]:
    """Kullanıcıyı dict'e çevir — password_hash REDACTED."""
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role.value if u.role else None,
        "is_active": u.is_active,
        "teacher_id": u.teacher_id,
        "institution_id": u.institution_id,
        "academic_year_id": u.academic_year_id,
        "grade_level": u.grade_level,
        "is_graduate": u.is_graduate,
        "track": u.track.value if u.track else None,
        "graduate_mode": u.graduate_mode.value if u.graduate_mode else None,
        "entry_year_grade9": u.entry_year_grade9,
        "plan": getattr(u, "plan", None),
        "last_login_at": _serialize_dt(u.last_login_at),
        "last_login_ip": u.last_login_ip,
        "failed_login_count": u.failed_login_count,
        "locked_until": _serialize_dt(u.locked_until),
        "password_changed_at": _serialize_dt(u.password_changed_at),
        "must_change_password": u.must_change_password,
        "created_at": _serialize_dt(u.created_at),
        "password_hash": "REDACTED",
    }


def _institution_to_dict(inst: Institution) -> dict[str, Any]:
    return {
        "id": inst.id,
        "name": inst.name,
        "slug": inst.slug,
        "contact_email": inst.contact_email,
        "plan": inst.plan,
        "is_active": inst.is_active,
        "created_at": _serialize_dt(inst.created_at),
    }


def _book_to_dict(b: Book) -> dict[str, Any]:
    return {
        "id": b.id,
        "teacher_id": b.teacher_id,
        "subject_id": b.subject_id,
        "name": b.name,
        "publisher": b.publisher,
        "type": b.type.value if b.type else None,
        "avg_questions_per_test": b.avg_questions_per_test,
        "notes": b.notes,
        "target_grade_min": b.target_grade_min,
        "target_grade_max": b.target_grade_max,
        "target_graduate": b.target_graduate,
        "created_at": _serialize_dt(b.created_at),
    }


def _section_to_dict(s: BookSection) -> dict[str, Any]:
    return {
        "id": s.id,
        "book_id": s.book_id,
        "topic_id": s.topic_id,
        "label": s.label,
        "test_count": s.test_count,
        "order": s.order,
    }


def _task_to_dict(t: Task) -> dict[str, Any]:
    return {
        "id": t.id,
        "student_id": t.student_id,
        "date": t.date.isoformat() if t.date else None,
        "type": t.type.value if t.type else None,
        "title": t.title,
        "status": t.status.value if t.status else None,
        "notes": t.notes,
        "order": t.order,
        "completed_at": _serialize_dt(t.completed_at),
        "created_at": _serialize_dt(t.created_at),
    }


def _task_item_to_dict(i: TaskBookItem) -> dict[str, Any]:
    return {
        "id": i.id,
        "task_id": i.task_id,
        "book_id": i.book_id,
        "book_section_id": i.book_section_id,
        "planned_count": i.planned_count,
        "completed_count": i.completed_count,
        "correct_count": i.correct_count,
        "wrong_count": i.wrong_count,
    }


def _notification_to_dict(n: NotificationLog) -> dict[str, Any]:
    return {
        "id": n.id,
        "parent_id": n.parent_id,
        "student_id": n.student_id,
        "kind": n.kind.value if n.kind else None,
        "channel": n.channel.value if n.channel else None,
        "status": n.status.value if n.status else None,
        "subject": n.subject,
        "external_id": n.external_id,
        "error": n.error,
        "queued_at": _serialize_dt(n.queued_at),
        "sent_at": _serialize_dt(getattr(n, "sent_at", None)),
    }


def _audit_to_dict(a: AuditLog) -> dict[str, Any]:
    return {
        "id": a.id,
        "action": a.action.value if a.action else None,
        "actor_id": a.actor_id,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "ip_address": a.ip_address,
        "email_attempted": a.email_attempted,
        "details_json": a.details_json,
        "created_at": _serialize_dt(a.created_at),
    }


def _credit_account_to_dict(c: CreditAccount) -> dict[str, Any]:
    return {
        "id": c.id,
        "owner_type": c.owner_type.value if c.owner_type else None,
        "owner_id": c.owner_id,
        "period_year_month": c.period_year_month,
        "allocated_credits": c.allocated_credits,
        "used_credits": c.used_credits,
        "bonus_credits": c.bonus_credits,
        "plan_code": c.plan_code,
        "warn_80_sent_at": _serialize_dt(c.warn_80_sent_at),
        "hard_block_enabled": c.hard_block_enabled,
        "blocked_until": _serialize_dt(c.blocked_until),
    }


def _usage_event_to_dict(e: UsageEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "owner_type": e.owner_type.value if e.owner_type else None,
        "owner_id": e.owner_id,
        "kind": e.kind.value if e.kind else None,
        "credits": e.credits,
        "period_year_month": e.period_year_month,
        "actor_user_id": e.actor_user_id,
        "metadata_json": e.metadata_json,
        "occurred_at": _serialize_dt(e.occurred_at),
    }


def _digest_to_dict(d: AdminWeeklyDigest) -> dict[str, Any]:
    return {
        "id": d.id,
        "institution_id": d.institution_id,
        "week_start_date": d.week_start_date.isoformat() if d.week_start_date else None,
        "week_end_date": d.week_end_date.isoformat() if d.week_end_date else None,
        "payload_json": d.payload_json,
        "recipient_count": d.recipient_count,
        "recipient_emails": d.recipient_emails,
        "send_status": d.send_status,
        "error_message": d.error_message,
        "sent_at": _serialize_dt(d.sent_at),
    }


def _ff_override_to_dict(o: FeatureFlagOverride) -> dict[str, Any]:
    return {
        "id": o.id,
        "feature_flag_id": o.feature_flag_id,
        "institution_id": o.institution_id,
        "enabled": o.enabled,
        "note": o.note,
    }


def _quota_override_to_dict(q: InstitutionQuotaOverride) -> dict[str, Any]:
    return {
        "id": q.id,
        "institution_id": q.institution_id,
        "quota_key": q.quota_key,
        "override_value": q.override_value,
        "note": q.note,
    }


def _parent_link_to_dict(pl: ParentStudentLink) -> dict[str, Any]:
    return {
        "id": pl.id,
        "parent_id": pl.parent_id,
        "student_id": pl.student_id,
        "relation": pl.relation.value if pl.relation else None,
        "created_at": _serialize_dt(pl.created_at),
    }


# ---------------------------- Public ----------------------------


SCHEMA_VERSION = 1


def export_tenant(
    db: Session, *, institution: Institution,
) -> dict[str, Any]:
    """Bir kurumun tüm verisini JSON-serialize edilebilir dict olarak döner.

    Şema versiyonu sürüm kontrolü için; geri yükleme zamanı ileride önem kazanır.
    """
    now = datetime.now(timezone.utc)
    audit_cutoff = now - timedelta(days=AUDIT_LOOKBACK_DAYS)
    notif_cutoff = now - timedelta(days=NOTIFICATION_LOOKBACK_DAYS)
    iid = institution.id

    # 1) Kurum
    institution_d = _institution_to_dict(institution)

    # 2) Tüm kullanıcılar (kurum altındakiler)
    users = (
        db.query(User)
        .filter(User.institution_id == iid)
        .all()
    )
    user_ids = [u.id for u in users]
    teacher_ids = [u.id for u in users if u.role == UserRole.TEACHER]
    student_ids = [u.id for u in users if u.role == UserRole.STUDENT]

    # 3) Books — öğretmenlere ait
    books = []
    sections = []
    if teacher_ids:
        books_q = (
            db.query(Book).filter(Book.teacher_id.in_(teacher_ids)).all()
        )
        books = books_q
        book_ids = [b.id for b in books]
        if book_ids:
            sections = (
                db.query(BookSection)
                .filter(BookSection.book_id.in_(book_ids))
                .all()
            )

    # 4) Tasks + items — öğrencilere ait
    tasks = []
    task_items = []
    if student_ids:
        tasks = (
            db.query(Task).filter(Task.student_id.in_(student_ids)).all()
        )
        task_ids = [t.id for t in tasks]
        if task_ids:
            task_items = (
                db.query(TaskBookItem)
                .filter(TaskBookItem.task_id.in_(task_ids))
                .all()
            )

    # 5) Notifications — son 30g
    notifications = []
    if student_ids:
        notifications = (
            db.query(NotificationLog)
            .filter(NotificationLog.student_id.in_(student_ids))
            .filter(NotificationLog.queued_at >= notif_cutoff)
            .all()
        )

    # 6) Audit logs — son 90g, kurum kullanıcılarını ilgilendiren
    audits = []
    if user_ids:
        audits = (
            db.query(AuditLog)
            .filter(
                (AuditLog.actor_id.in_(user_ids))
                | (AuditLog.target_id.in_(user_ids))
            )
            .filter(AuditLog.created_at >= audit_cutoff)
            .all()
        )

    # 7) Credit accounts + usage events (kurum havuzu)
    from app.models import UsageOwnerType
    credits = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
            CreditAccount.owner_id == iid,
        )
        .all()
    )
    usage_events = (
        db.query(UsageEvent)
        .filter(
            UsageEvent.owner_type == UsageOwnerType.INSTITUTION,
            UsageEvent.owner_id == iid,
        )
        .all()
    )

    # 8) Admin weekly digests
    digests = (
        db.query(AdminWeeklyDigest)
        .filter(AdminWeeklyDigest.institution_id == iid)
        .all()
    )

    # 9) Feature flag overrides
    ff_overrides = (
        db.query(FeatureFlagOverride)
        .filter(FeatureFlagOverride.institution_id == iid)
        .all()
    )

    # 10) Quota overrides
    quota_overrides = (
        db.query(InstitutionQuotaOverride)
        .filter(InstitutionQuotaOverride.institution_id == iid)
        .all()
    )

    # 11) Parent links — kurum öğrencileriyle ilgili
    parent_links = []
    if student_ids:
        parent_links = (
            db.query(ParentStudentLink)
            .filter(ParentStudentLink.student_id.in_(student_ids))
            .all()
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "exported_at": _serialize_dt(now),
        "audit_lookback_days": AUDIT_LOOKBACK_DAYS,
        "notification_lookback_days": NOTIFICATION_LOOKBACK_DAYS,
        "institution": institution_d,
        "counts": {
            "users": len(users),
            "teachers": len(teacher_ids),
            "students": len(student_ids),
            "books": len(books),
            "sections": len(sections),
            "tasks": len(tasks),
            "task_items": len(task_items),
            "notifications": len(notifications),
            "audit_logs": len(audits),
            "credit_accounts": len(credits),
            "usage_events": len(usage_events),
            "admin_weekly_digests": len(digests),
            "feature_flag_overrides": len(ff_overrides),
            "quota_overrides": len(quota_overrides),
            "parent_links": len(parent_links),
        },
        "users": [_user_to_dict(u) for u in users],
        "books": [_book_to_dict(b) for b in books],
        "book_sections": [_section_to_dict(s) for s in sections],
        "tasks": [_task_to_dict(t) for t in tasks],
        "task_book_items": [_task_item_to_dict(i) for i in task_items],
        "notification_logs": [_notification_to_dict(n) for n in notifications],
        "audit_logs": [_audit_to_dict(a) for a in audits],
        "credit_accounts": [_credit_account_to_dict(c) for c in credits],
        "usage_events": [_usage_event_to_dict(e) for e in usage_events],
        "admin_weekly_digests": [_digest_to_dict(d) for d in digests],
        "feature_flag_overrides": [_ff_override_to_dict(o) for o in ff_overrides],
        "quota_overrides": [_quota_override_to_dict(q) for q in quota_overrides],
        "parent_student_links": [_parent_link_to_dict(pl) for pl in parent_links],
    }


def export_tenant_json(
    db: Session, *, institution: Institution, indent: int = 2,
) -> str:
    """JSON string olarak (dosya download için)."""
    payload = export_tenant(db, institution=institution)
    return json.dumps(payload, ensure_ascii=False, indent=indent)
