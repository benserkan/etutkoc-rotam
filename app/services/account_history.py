"""Hesap hareketleri (account history) — kurum/öğretmen için birleşik zaman tüneli.

İçerik:
  - PlanChangeHistory (plan değişimleri: signup, upgrade, downgrade, trial_expired,
    pause, resume, garanti uzatma, akademik yenileme)
  - Invoice (faturalar: kesim, ödendi, gecikti, başarısız, iade, iptal)

Tek timeline'da tarih azalan sırada birleşir, "tip" alanı ile ayırt edilir.

Pencere politikası:
  - Varsayılan: son 3 yıl (1095 gün)
  - 3 yıldan eski kayıtlar otomatik gizli — sadece "Arşivi göster" toggle ile
  - Soft archive: archived_at NULL = aktif, dolu = arşive alınmış (silinmedi)

Arşivleme:
  - Tekil: tek plan_history / invoice kaydını arşivle
  - Toplu: bir kurum/öğretmen için X yıldan eski TÜM kayıtları arşivle
  - Geri al: archived_at NULL'a çekilir (admin geri alabilir)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models import (
    INVOICE_STATUS_LABELS_TR,
    Institution,
    Invoice,
    InvoiceStatus,
    PlanChangeHistory,
    PlanChangeReason,
    User,
)
from app.models.plan_history import PlanOwnerType


logger = logging.getLogger(__name__)


# Sade Türkçe açıklamalar — UI'da satır altında gösterilir
PLAN_REASON_LABELS_TR: dict[str, str] = {
    "signup": "Yeni kayıt",
    "trial_expired": "Deneme süresi bitti",
    "upgrade": "Pakete yükseltme",
    "downgrade": "Paket alçaltma",
    "admin_override": "Süper admin manuel değişiklik",
    "pause": "Hesap duraklatıldı",
    "resume": "Hesap devam etti",
    "guarantee_extend": "60 gün garanti uzatması",
    "academic_year_renewal": "Akademik yıl yenileme",
}

# Tipe göre renk paleti (UI badge)
EVENT_TYPE_PALETTE: dict[str, str] = {
    "plan_signup": "emerald",
    "plan_upgrade": "emerald",
    "plan_renewal": "emerald",
    "plan_resume": "emerald",
    "plan_pause": "amber",
    "plan_downgrade": "rose",
    "plan_trial_expired": "amber",
    "plan_admin_override": "violet",
    "plan_guarantee_extend": "indigo",
    "invoice_pending": "slate",
    "invoice_paid": "emerald",
    "invoice_overdue": "rose",
    "invoice_failed": "rose",
    "invoice_refunded": "amber",
    "invoice_cancelled": "slate",
}

# Varsayılan pencere — 3 yıl
DEFAULT_WINDOW_YEARS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------- Timeline ----------------------------


@dataclass
class HistoryEvent:
    """Tek bir hesap hareketi (plan değişim veya fatura)."""
    record_type: Literal["plan", "invoice"]
    record_id: int
    when: datetime
    title: str
    subtitle: str
    badge_label: str
    badge_color: str
    detail: dict
    archived: bool
    archived_at: datetime | None
    archive_note: str | None


def _plan_event(row: PlanChangeHistory) -> HistoryEvent:
    reason_key = row.reason.value if hasattr(row.reason, "value") else str(row.reason)
    reason_label = PLAN_REASON_LABELS_TR.get(reason_key, reason_key)
    title = reason_label
    subtitle_parts: list[str] = []
    if row.from_plan or row.to_plan:
        subtitle_parts.append(f"{row.from_plan or '—'} → {row.to_plan}")
    if row.note:
        subtitle_parts.append(row.note)
    subtitle = " · ".join(subtitle_parts)
    palette_key = f"plan_{reason_key}" if reason_key not in (
        "academic_year_renewal",) else "plan_renewal"
    badge_color = EVENT_TYPE_PALETTE.get(palette_key, "slate")
    return HistoryEvent(
        record_type="plan",
        record_id=row.id,
        when=_aware(row.occurred_at) or _now(),
        title=title,
        subtitle=subtitle,
        badge_label=reason_label,
        badge_color=badge_color,
        detail={
            "from_plan": row.from_plan,
            "to_plan": row.to_plan,
            "reason": reason_key,
            "actor_user_id": row.actor_user_id,
            "note": row.note,
        },
        archived=row.archived_at is not None,
        archived_at=_aware(row.archived_at),
        archive_note=row.archive_note,
    )


def _invoice_event(row: Invoice) -> HistoryEvent:
    status_value = row.status.value
    status_label = INVOICE_STATUS_LABELS_TR.get(row.status, status_value)
    title = f"Fatura — {status_label}"
    subtitle_parts = [
        f"{row.amount_try:,} ₺",
        f"plan: {row.plan}",
    ]
    if row.due_at:
        subtitle_parts.append(f"vade: {row.due_at.strftime('%d.%m.%Y')}")
    if row.paid_at:
        subtitle_parts.append(f"ödendi: {row.paid_at.strftime('%d.%m.%Y')}")
    subtitle = " · ".join(subtitle_parts)
    badge_color = EVENT_TYPE_PALETTE.get(f"invoice_{status_value}", "slate")

    # Olayın "ne zaman" sıralandığı: ödenmiş ise paid_at, yoksa due_at, yoksa created_at
    when = _aware(row.paid_at) or _aware(row.due_at) or _aware(row.created_at) or _now()

    return HistoryEvent(
        record_type="invoice",
        record_id=row.id,
        when=when,
        title=title,
        subtitle=subtitle,
        badge_label=status_label,
        badge_color=badge_color,
        detail={
            "amount_try": row.amount_try,
            "plan": row.plan,
            "status": status_value,
            "due_at": _aware(row.due_at).isoformat() if row.due_at else None,
            "paid_at": _aware(row.paid_at).isoformat() if row.paid_at else None,
            "period_start": _aware(row.period_start).isoformat() if row.period_start else None,
            "period_end": _aware(row.period_end).isoformat() if row.period_end else None,
            "payment_method": row.payment_method.value if row.payment_method else None,
            "attempt_count": row.attempt_count,
        },
        archived=row.archived_at is not None,
        archived_at=_aware(row.archived_at),
        archive_note=row.archive_note,
    )


def account_history(
    db: Session,
    *,
    owner_type: Literal["institution", "user"],
    owner_id: int,
    years: int = DEFAULT_WINDOW_YEARS,
    include_archived: bool = False,
    record_types: set[str] | None = None,
) -> dict:
    """Bir kurum veya kullanıcının birleşik hesap hareketleri timeline'ı.

    Returns:
      {
        "owner_type": "institution" | "user",
        "owner_id": int,
        "owner_name": str | None,
        "window_start": datetime,
        "events": [HistoryEvent, ...],
        "total_count": int,        # gösterilen
        "archived_count": int,     # toplam arşivli (pencere içinde)
        "older_count": int,        # 3 yıldan eski + arşivlenmemiş
        "include_archived": bool,
        "years": int,
      }
    """
    now = _now()
    window_start = now - timedelta(days=365 * years)

    if record_types is None:
        record_types = {"plan", "invoice"}

    events: list[HistoryEvent] = []
    archived_in_window = 0
    older_not_archived = 0

    # ---- PlanChangeHistory ----
    if "plan" in record_types:
        owner_type_enum = (
            PlanOwnerType.INSTITUTION if owner_type == "institution"
            else PlanOwnerType.USER
        )
        plan_q = (
            db.query(PlanChangeHistory)
            .filter(
                PlanChangeHistory.owner_type == owner_type_enum,
                PlanChangeHistory.owner_id == owner_id,
            )
        )
        # Pencere içi (3 yıl)
        in_window = plan_q.filter(PlanChangeHistory.occurred_at >= window_start)
        if not include_archived:
            in_window = in_window.filter(PlanChangeHistory.archived_at.is_(None))
        for row in in_window.order_by(desc(PlanChangeHistory.occurred_at)).all():
            events.append(_plan_event(row))

        # Sayım: pencere içinde arşivlenmiş
        archived_in_window += (
            plan_q.filter(
                PlanChangeHistory.occurred_at >= window_start,
                PlanChangeHistory.archived_at.isnot(None),
            ).count()
        )
        # Sayım: pencere dışı + henüz arşivlenmemiş
        older_not_archived += (
            plan_q.filter(
                PlanChangeHistory.occurred_at < window_start,
                PlanChangeHistory.archived_at.is_(None),
            ).count()
        )

    # ---- Invoice (sadece kurum) ----
    if "invoice" in record_types and owner_type == "institution":
        inv_q = db.query(Invoice).filter(Invoice.institution_id == owner_id)
        # Olayın zamanı: paid_at > due_at > created_at — pencere için en sade kıstas
        # olarak due_at kullan (faturanın "ne zaman" yapıldığını temsil eder).
        in_window = inv_q.filter(Invoice.due_at >= window_start)
        if not include_archived:
            in_window = in_window.filter(Invoice.archived_at.is_(None))
        for row in in_window.order_by(desc(Invoice.due_at)).all():
            events.append(_invoice_event(row))

        archived_in_window += (
            inv_q.filter(
                Invoice.due_at >= window_start,
                Invoice.archived_at.isnot(None),
            ).count()
        )
        older_not_archived += (
            inv_q.filter(
                Invoice.due_at < window_start,
                Invoice.archived_at.is_(None),
            ).count()
        )

    # Birleşik zamanda azalan sıraya göre dizip döndür
    events.sort(key=lambda e: e.when, reverse=True)

    # Owner adı (UI başlığı için)
    owner_name: str | None = None
    if owner_type == "institution":
        inst = db.get(Institution, owner_id)
        owner_name = inst.name if inst else None
    else:
        u = db.get(User, owner_id)
        owner_name = u.full_name if u else None

    return {
        "owner_type": owner_type,
        "owner_id": owner_id,
        "owner_name": owner_name,
        "window_start": window_start,
        "events": events,
        "total_count": len(events),
        "archived_count": archived_in_window,
        "older_count": older_not_archived,
        "include_archived": include_archived,
        "years": years,
    }


# ---------------------------- Arşivleme ----------------------------


def archive_record(
    db: Session,
    *,
    record_type: Literal["plan", "invoice"],
    record_id: int,
    by_user_id: int,
    note: str | None = None,
    autocommit: bool = True,
) -> dict:
    """Tek bir plan_history veya invoice kaydını arşive ekle.

    Soft archive: archived_at = now, archived_by_user_id = by_user_id.
    Eğer zaten arşivli ise no-op (already_archived flag).
    """
    now = _now()
    if record_type == "plan":
        row = db.get(PlanChangeHistory, record_id)
    elif record_type == "invoice":
        row = db.get(Invoice, record_id)
    else:
        return {"ok": False, "error": "invalid_record_type"}
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.archived_at is not None:
        return {"ok": False, "error": "already_archived",
                "archived_at": row.archived_at.isoformat()}
    row.archived_at = now
    row.archived_by_user_id = by_user_id
    row.archive_note = (note or "")[:500] or None
    if autocommit:
        db.commit()
    return {
        "ok": True,
        "record_type": record_type,
        "record_id": record_id,
        "archived_at": now.isoformat(),
    }


def unarchive_record(
    db: Session,
    *,
    record_type: Literal["plan", "invoice"],
    record_id: int,
    autocommit: bool = True,
) -> dict:
    """Arşivlenmiş bir kaydı geri çıkar (admin geri alma)."""
    if record_type == "plan":
        row = db.get(PlanChangeHistory, record_id)
    elif record_type == "invoice":
        row = db.get(Invoice, record_id)
    else:
        return {"ok": False, "error": "invalid_record_type"}
    if row is None:
        return {"ok": False, "error": "not_found"}
    if row.archived_at is None:
        return {"ok": False, "error": "not_archived"}
    row.archived_at = None
    row.archived_by_user_id = None
    row.archive_note = None
    if autocommit:
        db.commit()
    return {"ok": True, "record_type": record_type, "record_id": record_id}


def bulk_archive_older_than(
    db: Session,
    *,
    owner_type: Literal["institution", "user"],
    owner_id: int,
    years: int = DEFAULT_WINDOW_YEARS,
    by_user_id: int,
    note: str | None = None,
    autocommit: bool = True,
) -> dict:
    """Bir kurum/öğretmenin X yıldan eski TÜM kayıtlarını topluca arşivle.

    Returns: {plan_count, invoice_count, total, cutoff}
    """
    now = _now()
    cutoff = now - timedelta(days=365 * years)
    plan_count = 0
    invoice_count = 0

    # Plan history
    owner_type_enum = (
        PlanOwnerType.INSTITUTION if owner_type == "institution"
        else PlanOwnerType.USER
    )
    plan_rows = (
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.owner_type == owner_type_enum,
            PlanChangeHistory.owner_id == owner_id,
            PlanChangeHistory.occurred_at < cutoff,
            PlanChangeHistory.archived_at.is_(None),
        )
        .all()
    )
    for row in plan_rows:
        row.archived_at = now
        row.archived_by_user_id = by_user_id
        row.archive_note = (note or f"Toplu arşiv: {years} yıldan eski")[:500]
        plan_count += 1

    # Invoice (kurum)
    if owner_type == "institution":
        inv_rows = (
            db.query(Invoice)
            .filter(
                Invoice.institution_id == owner_id,
                Invoice.due_at < cutoff,
                Invoice.archived_at.is_(None),
            )
            .all()
        )
        for row in inv_rows:
            row.archived_at = now
            row.archived_by_user_id = by_user_id
            row.archive_note = (note or f"Toplu arşiv: {years} yıldan eski")[:500]
            invoice_count += 1

    if autocommit:
        db.commit()

    return {
        "ok": True,
        "owner_type": owner_type,
        "owner_id": owner_id,
        "plan_count": plan_count,
        "invoice_count": invoice_count,
        "total": plan_count + invoice_count,
        "cutoff": cutoff.isoformat(),
        "years": years,
    }


__all__ = [
    "DEFAULT_WINDOW_YEARS",
    "EVENT_TYPE_PALETTE",
    "HistoryEvent",
    "PLAN_REASON_LABELS_TR",
    "account_history",
    "archive_record",
    "bulk_archive_older_than",
    "unarchive_record",
]
