"""Sprint B (Ticari Pano 2.0 — Faz B) — Kurum 360 verisi.

Tek bir kurumun "her şeyi"ni tek panoda toplayan aggregator. UI'da
`/admin/revenue/institutions/{id}` sayfası bu fonksiyonun çıktısını render eder.

İçerikler:
  - identity: ad, plan, durum, slug, oluşturma, iletişim, yetkili adminler
  - mrr: bu kurumun aylık katkısı
  - health: tenant_health'ten 0-100 sağlık skoru (yüksek = sağlıklı, ters çevrilmiş)
  - usage: 7/30/90 gün aktif öğretmen/öğrenci/soru çözüm/bildirim
  - billing_summary: son fatura, sonraki vade, ödenmemiş toplam
  - account_history_summary: timeline'da ilk N olay
  - crm: pinned notlar + son notlar + bekleyen aksiyonlar
  - risks: tenant_health indicator'ları + ödeme gecikme + trial bitiş yakın
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models import (
    CrmAction,
    CrmActionResult,
    CrmNote,
    Institution,
    Invoice,
    InvoiceStatus,
    NotificationLog,
    PlanChangeHistory,
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


# ---------------------------- Kullanım metrikleri ----------------------------


def usage_metrics(
    db: Session, *, institution_id: int, days: int = 30,
) -> dict:
    """Son N gün için kurum kullanım metrikleri.

    Returns:
      {
        "days": int,
        "active_teacher_count": int,
        "total_teacher_count": int,
        "active_student_count": int,
        "total_student_count": int,
        "notification_sent": int,
        "notification_failed": int,
        "study_sessions": int  # 0 — ileride study_session tablosundan
      }
    """
    cutoff = _now() - timedelta(days=days)

    # Teacher sayıları
    teacher_q = db.query(User).filter(
        User.institution_id == institution_id,
        User.role == UserRole.TEACHER,
    )
    total_teacher = teacher_q.count()
    active_teacher = teacher_q.filter(
        User.last_login_at.isnot(None),
        User.last_login_at >= cutoff,
    ).count()

    # Student sayıları: institution_id öğrenci tablosunda mevcut (Sprint 6+)
    student_q = db.query(User).filter(
        User.institution_id == institution_id,
        User.role == UserRole.STUDENT,
    )
    total_student = student_q.count()
    active_student = student_q.filter(
        User.last_login_at.isnot(None),
        User.last_login_at >= cutoff,
    ).count()

    # Notification: bu kurumdaki parent'lara gönderilen bildirimler
    parent_ids_q = (
        db.query(User.id)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.PARENT,
        )
    )
    parent_ids = [r[0] for r in parent_ids_q.all()]
    notif_sent = 0
    notif_failed = 0
    if parent_ids:
        rows = (
            db.query(NotificationLog.status, func.count(NotificationLog.id))
            .filter(
                NotificationLog.parent_id.in_(parent_ids),
                NotificationLog.queued_at >= cutoff,
            )
            .group_by(NotificationLog.status)
            .all()
        )
        for st, c in rows:
            v = st.value if hasattr(st, "value") else str(st)
            if v == "sent":
                notif_sent = int(c)
            elif v == "failed":
                notif_failed = int(c)

    return {
        "days": days,
        "active_teacher_count": active_teacher,
        "total_teacher_count": total_teacher,
        "teacher_active_pct": int(round(100 * active_teacher / total_teacher))
            if total_teacher > 0 else None,
        "active_student_count": active_student,
        "total_student_count": total_student,
        "student_active_pct": int(round(100 * active_student / total_student))
            if total_student > 0 else None,
        "notification_sent": notif_sent,
        "notification_failed": notif_failed,
        "study_sessions": 0,  # ileride study_session tablosu eklendiğinde
    }


# ---------------------------- Fatura özeti ----------------------------


def billing_summary(db: Session, *, institution_id: int) -> dict:
    """Bir kurumun fatura durumu özeti."""
    now = _now()
    # Son ödenmiş
    last_paid = (
        db.query(Invoice)
        .filter(
            Invoice.institution_id == institution_id,
            Invoice.status == InvoiceStatus.PAID,
            Invoice.paid_at.isnot(None),
        )
        .order_by(desc(Invoice.paid_at))
        .first()
    )
    # Sonraki vade (pending + gelecekteki en yakın)
    next_due = (
        db.query(Invoice)
        .filter(
            Invoice.institution_id == institution_id,
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.due_at >= now,
        )
        .order_by(Invoice.due_at)
        .first()
    )
    # Gecikmiş veya overdue toplam
    overdue_rows = (
        db.query(Invoice)
        .filter(
            Invoice.institution_id == institution_id,
            Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING]),
            Invoice.due_at < now,
        )
        .all()
    )
    overdue_count = len(overdue_rows)
    overdue_total = sum(r.amount_try for r in overdue_rows)

    # Toplam ödenmiş (yaşam boyu kabaca — şu ana kadar)
    paid_total = int(
        db.query(func.coalesce(func.sum(Invoice.amount_try), 0))
        .filter(
            Invoice.institution_id == institution_id,
            Invoice.status == InvoiceStatus.PAID,
        )
        .scalar() or 0
    )

    return {
        "last_paid_at": _aware(last_paid.paid_at) if last_paid else None,
        "last_paid_amount_try": last_paid.amount_try if last_paid else None,
        "next_due_at": _aware(next_due.due_at) if next_due else None,
        "next_due_amount_try": next_due.amount_try if next_due else None,
        "overdue_count": overdue_count,
        "overdue_total_try": overdue_total,
        "lifetime_paid_try": paid_total,
    }


# ---------------------------- CRM ----------------------------


def crm_notes_for(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    limit: int = 20,
) -> list[CrmNote]:
    """Bir owner'ın (kurum veya bağımsız öğretmen) notları — sabitlenenler
    üstte, sonra kronolojik. Tam biri verilmeli."""
    q = db.query(CrmNote).order_by(
        desc(CrmNote.pinned), desc(CrmNote.created_at),
    )
    if institution_id is not None and user_id is None:
        q = q.filter(CrmNote.institution_id == institution_id)
    elif user_id is not None and institution_id is None:
        q = q.filter(CrmNote.user_id == user_id)
    else:
        raise ValueError("crm_notes_for: institution_id veya user_id (tam biri)")
    return q.limit(limit).all()


def crm_actions_for(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    limit: int = 20,
) -> list[CrmAction]:
    """Bir owner'ın aksiyonları — bekleyenler ve takip yaklaşanlar üstte."""
    q = db.query(CrmAction).order_by(
        # pending/scheduled önce
        CrmAction.completed_at.is_(None).desc(),
        desc(CrmAction.created_at),
    )
    if institution_id is not None and user_id is None:
        q = q.filter(CrmAction.institution_id == institution_id)
    elif user_id is not None and institution_id is None:
        q = q.filter(CrmAction.user_id == user_id)
    else:
        raise ValueError("crm_actions_for: institution_id veya user_id (tam biri)")
    return q.limit(limit).all()


def _resolve_owner_kwargs(
    *, institution_id: int | None = None, user_id: int | None = None,
) -> dict:
    """CRM kayıtlarında owner_type+FK ataması için ortak helper.

    XOR: tam birinin verilmesi gerekir. Eski çağrıların `institution_id=...`
    formu hâlâ geçerli (owner_type='institution' türetilir).
    """
    if institution_id is None and user_id is None:
        raise ValueError("CRM kaydı için institution_id veya user_id zorunlu")
    if institution_id is not None and user_id is not None:
        raise ValueError("CRM kaydında institution_id ile user_id birlikte verilemez")
    if institution_id is not None:
        return {
            "owner_type": "institution",
            "institution_id": institution_id,
            "user_id": None,
        }
    return {
        "owner_type": "user",
        "institution_id": None,
        "user_id": user_id,
    }


def create_note(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    content: str,
    by_user_id: int,
    pinned: bool = False,
    autocommit: bool = True,
) -> CrmNote:
    """CrmNote yarat. `institution_id` veya `user_id` — birinden biri."""
    owner_kw = _resolve_owner_kwargs(
        institution_id=institution_id, user_id=user_id,
    )
    note = CrmNote(
        content=content[:5000],
        pinned=pinned,
        created_by_user_id=by_user_id,
        **owner_kw,
    )
    db.add(note)
    if autocommit:
        db.commit()
        db.refresh(note)
    return note


def toggle_note_pin(
    db: Session, *, note_id: int, autocommit: bool = True,
) -> CrmNote | None:
    note = db.get(CrmNote, note_id)
    if note is None:
        return None
    note.pinned = not note.pinned
    if autocommit:
        db.commit()
    return note


def delete_note(
    db: Session, *, note_id: int, autocommit: bool = True,
) -> bool:
    note = db.get(CrmNote, note_id)
    if note is None:
        return False
    db.delete(note)
    if autocommit:
        db.commit()
    return True


def create_action(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    kind: str,
    summary: str,
    by_user_id: int,
    notes: str | None = None,
    result: str = "pending",
    follow_up_at: datetime | None = None,
    autocommit: bool = True,
    dedup: bool = False,
) -> CrmAction | None:
    """CrmAction yarat. `institution_id` veya `user_id` — birinden biri.

    `dedup=True` ise: aynı owner + kind + summary için hâlâ AÇIK (pending) bir
    aksiyon varsa yenisini yaratmaz, mevcudu döndürür (öneri butonuna hızlı/
    mükerrer basışta tekrar kayıt önlenir). Manuel "Yeni Aksiyon" formu dedup=False.
    """
    from app.models import CrmActionKind, CrmActionResult
    try:
        kind_enum = CrmActionKind(kind)
    except ValueError:
        return None
    try:
        result_enum = CrmActionResult(result)
    except ValueError:
        result_enum = CrmActionResult.PENDING
    owner_kw = _resolve_owner_kwargs(
        institution_id=institution_id, user_id=user_id,
    )
    if dedup:
        q = db.query(CrmAction).filter(
            CrmAction.kind == kind_enum,
            CrmAction.summary == summary[:500],
            CrmAction.result == CrmActionResult.PENDING,
        )
        for k, v in owner_kw.items():
            q = q.filter(getattr(CrmAction, k) == v)
        existing = q.order_by(CrmAction.id.desc()).first()
        if existing is not None:
            return existing
    action = CrmAction(
        kind=kind_enum,
        summary=summary[:500],
        notes=notes,
        result=result_enum,
        follow_up_at=follow_up_at,
        created_by_user_id=by_user_id,
        completed_at=_now() if result_enum in (
            CrmActionResult.SUCCESS, CrmActionResult.DONE,
            CrmActionResult.DECLINED,
        ) else None,
        **owner_kw,
    )
    db.add(action)
    if autocommit:
        db.commit()
        db.refresh(action)
    return action


def complete_action(
    db: Session, *,
    action_id: int,
    result: str,
    by_user_id: int,
    notes: str | None = None,
    autocommit: bool = True,
) -> CrmAction | None:
    from app.models import CrmActionResult
    action = db.get(CrmAction, action_id)
    if action is None:
        return None
    try:
        result_enum = CrmActionResult(result)
    except ValueError:
        return None
    action.result = result_enum
    action.completed_at = _now()
    if notes:
        action.notes = ((action.notes or "") + "\n[Sonuç] " + notes)[:8000]
    if autocommit:
        db.commit()
    return action


def delete_action(
    db: Session, *, action_id: int, autocommit: bool = True,
) -> bool:
    a = db.get(CrmAction, action_id)
    if a is None:
        return False
    db.delete(a)
    if autocommit:
        db.commit()
    return True


# ---------------------------- Riskler ----------------------------


def open_risks(db: Session, *, institution: Institution) -> list[dict]:
    """Bir kurum için "şu an dikkat" gerektiren riskler.

    Tenant_health indicator + ödeme gecikme + trial bitiş yakın birleşimi.
    """
    now = _now()
    risks: list[dict] = []

    # 1) Tenant_health indicators
    try:
        from app.services.tenant_health import compute_health_score
        h = compute_health_score(db, institution=institution)
        for ind in h.indicators:
            risks.append({
                "kind": "health_indicator",
                "severity": h.level,
                "title": getattr(ind, "name", "Sağlık göstergesi"),
                "message": getattr(ind, "message", ""),
                "weight": getattr(ind, "weight", 0),
            })
    except Exception:
        logger.exception("open_risks: tenant_health hata")

    # 2) Ödeme gecikti
    overdue = (
        db.query(Invoice)
        .filter(
            Invoice.institution_id == institution.id,
            Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING]),
            Invoice.due_at < now,
        )
        .count()
    )
    if overdue > 0:
        risks.append({
            "kind": "billing_overdue",
            "severity": "critical" if overdue >= 2 else "risk",
            "title": "Ödeme gecikti",
            "message": f"{overdue} adet gecikmiş fatura var",
            "weight": 100,
        })

    # 3) Trial bitişi yakın
    if institution.trial_ends_at:
        te = _aware(institution.trial_ends_at)
        days_left = (te - now).days if te else None
        if days_left is not None and 0 <= days_left <= 7:
            sev = "critical" if days_left <= 2 else "risk"
            risks.append({
                "kind": "trial_ending",
                "severity": sev,
                "title": "Deneme bitiyor",
                "message": f"{days_left} gün içinde trial dolacak",
                "weight": 90,
            })

    risks.sort(key=lambda r: -r.get("weight", 0))
    return risks


# ---------------------------- Aggregator ----------------------------


def get_institution_360(
    db: Session, *, institution_id: int,
) -> dict | None:
    """Bir kurumun tüm verilerini tek aggregator'da topla — UI render için."""
    inst = db.get(Institution, institution_id)
    if inst is None:
        return None

    # Plan & fiyat
    try:
        from app.services.plans import PLAN_CATALOG
        plan_info = PLAN_CATALOG.get(inst.plan)
        plan_label = getattr(plan_info, "label", inst.plan)
        plan_price = getattr(plan_info, "price_monthly_try", 0) or 0
    except Exception:
        plan_label = inst.plan
        plan_price = 0

    # Yetkili adminler
    admins = (
        db.query(User)
        .filter(
            User.institution_id == inst.id,
            User.role == UserRole.INSTITUTION_ADMIN,
            User.is_active.is_(True),
        )
        .all()
    )

    # Sağlık (yüksek = iyi olacak şekilde tersle)
    try:
        from app.services.tenant_health import compute_health_score
        h = compute_health_score(db, institution=inst)
        # tenant_health: yüksek skor = TEHLİKE. Sağlık skoru ise: 100 - tehlike.
        health_score_user_facing = max(0, min(100, 100 - h.score))
        health_level = h.level
        health_emoji = h.level_emoji
        health_color = h.level_color
        health_label = h.level_label
    except Exception:
        logger.exception("get_institution_360: tenant_health hata")
        health_score_user_facing = None
        health_level = "unknown"
        health_emoji = "❓"
        health_color = "slate"
        health_label = "Bilinmiyor"

    return {
        "identity": {
            "id": inst.id,
            "name": inst.name,
            "slug": inst.slug,
            "contact_email": inst.contact_email,
            "is_active": inst.is_active,
            "plan": inst.plan,
            "plan_label": plan_label,
            "plan_monthly_price_try": plan_price,
            "trial_ends_at": _aware(inst.trial_ends_at),
            "post_trial_plan": inst.post_trial_plan,
            "subscription_kind": inst.subscription_kind,
            "subscription_period_end": _aware(inst.subscription_period_end),
            "subscription_pause_until": _aware(inst.subscription_pause_until),
            "performance_guarantee": inst.performance_guarantee,
            "created_at": _aware(inst.created_at),
            "admins": [
                {"id": a.id, "name": a.full_name, "email": a.email}
                for a in admins
            ],
        },
        "health": {
            "score": health_score_user_facing,
            "level": health_level,
            "emoji": health_emoji,
            "color": health_color,
            "label": health_label,
        },
        "usage_30d": usage_metrics(db, institution_id=inst.id, days=30),
        "billing": billing_summary(db, institution_id=inst.id),
        "open_invoices": (
            db.query(Invoice)
            .filter(
                Invoice.institution_id == inst.id,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            )
            .order_by(Invoice.due_at)
            .all()
        ),
        "crm_notes": crm_notes_for(db, institution_id=inst.id),
        "crm_actions": crm_actions_for(db, institution_id=inst.id),
        "risks": open_risks(db, institution=inst),
    }


__all__ = [
    "billing_summary",
    "complete_action",
    "create_action",
    "create_note",
    "crm_actions_for",
    "crm_notes_for",
    "delete_action",
    "delete_note",
    "get_institution_360",
    "open_risks",
    "toggle_note_pin",
    "usage_metrics",
]
