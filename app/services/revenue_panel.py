"""Katman 11.G — Ticari panel (MRR / Trial / Churn).

Mevcut yapı: Institution.plan (current), trial_ends_at, post_trial_plan,
PlanChangeHistory (signup/upgrade/downgrade/cancel reason). MRR plan fiyatı
PLAN_CATALOG.price_monthly_try alanından türetilir.

Veriler:
  - plan_distribution: plan kodu → aktif kurum sayısı + plan label/fiyat
  - mrr: aktif kurumların aylık gelir toplamı (TRY)
  - trial_ending_soon: trial_ends_at yaklaşan kurumlar (7g pencere)
  - plan_change_trend: son N gün PlanChangeHistory grouping (gün × reason)
  - churn_proxy: tenant_health risk/critical sayısı (kullanım terki sinyali)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Invoice,
    InvoiceStatus,
    PaymentMethod,
    PlanChangeHistory,
    PlanChangeReason,
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


def _plan_catalog() -> dict:
    """Plans servisinin PLAN_CATALOG sözlüğünü güvenli import et."""
    try:
        from app.services.plans import PLAN_CATALOG
        return PLAN_CATALOG
    except Exception:
        logger.warning("PLAN_CATALOG import fail — fiyat 0")
        return {}


def _plan_label_and_price(plan: str) -> tuple[str, int]:
    """plan kodundan (label, monthly_price_try) tuple döndür."""
    catalog = _plan_catalog()
    info = catalog.get(plan)
    if info is None:
        return (plan, 0)
    label = getattr(info, "label", plan)
    price = getattr(info, "price_monthly_try", 0) or 0
    return (label, int(price))


# ---------------------------- Plan dağılımı ----------------------------


def plan_distribution(db: Session) -> list[dict]:
    """Plan kodu → aktif kurum sayısı + label + fiyat + tier."""
    rows = (
        db.query(Institution.plan, func.count(Institution.id))
        .filter(Institution.is_active.is_(True))
        .group_by(Institution.plan)
        .all()
    )
    out: list[dict] = []
    for plan, c in rows:
        label, price = _plan_label_and_price(plan)
        out.append({
            "plan": plan,
            "label": label,
            "count": int(c),
            "monthly_price_try": price,
            "estimated_mrr": int(c) * price if price > 0 else 0,
        })
    # Fiyat azalan sıra (gelir potansiyeli yüksek üstte)
    out.sort(key=lambda r: (-r["estimated_mrr"], -r["count"]))
    return out


def mrr(db: Session) -> dict:
    """Aktif kurumların aylık tekrarlayan gelir toplamı."""
    dist = plan_distribution(db)
    total = sum(r["estimated_mrr"] for r in dist)
    paying = sum(r["count"] for r in dist if r["monthly_price_try"] > 0)
    free = sum(r["count"] for r in dist if r["monthly_price_try"] == 0)
    return {
        "total_try": total,
        "paying_institutions": paying,
        "free_institutions": free,
        "total_institutions": paying + free,
        "avg_per_paying": round(total / paying, 2) if paying > 0 else 0,
    }


# ---------------------------- Trial ----------------------------


@dataclass
class TrialEntry:
    institution_id: int
    institution_name: str
    plan: str
    trial_ends_at: datetime
    days_left: int
    post_trial_plan: str | None


def trial_ending_soon(db: Session, *, days_horizon: int = 7) -> list[TrialEntry]:
    """trial_ends_at önümüzdeki days_horizon gün içinde."""
    now = _now()
    horizon = now + timedelta(days=days_horizon)
    rows = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            Institution.trial_ends_at.isnot(None),
            Institution.trial_ends_at >= now,
            Institution.trial_ends_at <= horizon,
        )
        .order_by(Institution.trial_ends_at)
        .all()
    )
    out: list[TrialEntry] = []
    for r in rows:
        ends = _aware(r.trial_ends_at) or now
        days_left = max(0, (ends - now).days)
        out.append(TrialEntry(
            institution_id=r.id,
            institution_name=r.name,
            plan=r.plan,
            trial_ends_at=ends,
            days_left=days_left,
            post_trial_plan=r.post_trial_plan,
        ))
    return out


def trial_expired_unconverted(db: Session, *, days: int = 30) -> int:
    """Son N gün içinde trial bittiyse ve sonrasında üst tier'a geçmediyse."""
    cutoff = _now() - timedelta(days=days)
    return int(
        (db.query(func.count(PlanChangeHistory.id))
         .filter(
             PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
             PlanChangeHistory.occurred_at >= cutoff,
         )
         .scalar()) or 0
    )


# ---------------------------- Plan değişim trendi ----------------------------


def plan_change_summary(db: Session, *, days: int = 30) -> dict:
    """Son N gün PlanChangeHistory: reason başına sayım."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(PlanChangeHistory.reason, func.count(PlanChangeHistory.id))
        .filter(PlanChangeHistory.occurred_at >= cutoff)
        .group_by(PlanChangeHistory.reason)
        .all()
    )
    by_reason: dict[str, int] = {}
    for reason, c in rows:
        key = reason.value if hasattr(reason, "value") else str(reason)
        by_reason[key] = int(c)

    upgrades = by_reason.get("upgrade", 0)
    downgrades = by_reason.get("downgrade", 0)
    signups = by_reason.get("signup", 0)
    trial_expired = by_reason.get("trial_expired", 0)
    pauses = by_reason.get("pause", 0)
    return {
        "days": days,
        "by_reason": by_reason,
        "net_growth": upgrades - downgrades,
        "signups": signups,
        "upgrades": upgrades,
        "downgrades": downgrades,
        "trial_expired": trial_expired,
        "pauses": pauses,
    }


def daily_plan_changes(db: Session, *, days: int = 30) -> list[dict]:
    """Günlük PlanChangeHistory bucket (gün × reason)."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(PlanChangeHistory.occurred_at, PlanChangeHistory.reason)
        .filter(PlanChangeHistory.occurred_at >= cutoff)
        .all()
    )
    now = _now()
    buckets: dict[str, dict[str, int]] = {}
    reasons = [r.value for r in PlanChangeReason]
    for i in range(days):
        day = (now - timedelta(days=days - 1 - i)).date().isoformat()
        buckets[day] = {r: 0 for r in reasons}
        buckets[day]["total"] = 0
    for occurred_at, reason in rows:
        occurred_at = _aware(occurred_at)
        if occurred_at is None:
            continue
        day = occurred_at.date().isoformat()
        if day not in buckets:
            continue
        rkey = reason.value if hasattr(reason, "value") else str(reason)
        if rkey in buckets[day]:
            buckets[day][rkey] += 1
        buckets[day]["total"] += 1
    return [{"day": day, **vals} for day, vals in buckets.items()]


# ---------------------------- Churn proxy ----------------------------


def churn_proxy(db: Session) -> dict:
    """Tenant sağlık skoruna göre terk riski özetı."""
    try:
        from app.services.tenant_health import bulk_health_assessment, churn_summary
        insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
        assessments = bulk_health_assessment(db, institutions=insts)
        summary = churn_summary(assessments)
        return summary
    except Exception:
        logger.exception("churn_proxy fail")
        return {"healthy": 0, "watch": 0, "risk": 0, "critical": 0,
                "unhealthy_total": 0}


# ---------------------------- Drill-down: kurum listesi ----------------------------


def _row(inst: Institution, *, reason: str | None = None,
         extra: dict | None = None) -> dict:
    """Tek kurum satırı — drill-down panellerinde gösterilen küçük kart."""
    label, price = _plan_label_and_price(inst.plan)
    base = {
        "institution_id": inst.id,
        "institution_name": inst.name,
        "plan": inst.plan,
        "plan_label": label,
        "monthly_price_try": price,
        "is_active": inst.is_active,
        "trial_ends_at": _aware(inst.trial_ends_at),
        "post_trial_plan": inst.post_trial_plan,
        "created_at": _aware(inst.created_at),
        "reason": reason,
        "detail_url": f"/admin/institutions/{inst.id}",
    }
    if extra:
        base.update(extra)
    return base


def drill_health(db: Session, *, level: str) -> list[dict]:
    """level ∈ {critical, risk, watch, healthy} → o seviyedeki kurumlar."""
    try:
        from app.services.tenant_health import bulk_health_assessment
    except Exception:
        logger.exception("tenant_health import fail")
        return []
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    assessments = bulk_health_assessment(db, institutions=insts)
    out: list[dict] = []
    for a in assessments:
        if a.level != level:
            continue
        # Sebebi göstermek için en yüksek ağırlıklı indicator
        reason = a.level_label
        if a.indicators:
            top = a.indicators[0]
            reason_text = getattr(top, "message", None) or getattr(top, "name", None)
            if reason_text:
                reason = f"{a.level_label} · {reason_text}"
        out.append(_row(
            a.institution,
            reason=reason,
            extra={
                "health_score": a.score,
                "health_level": a.level,
                "active_teacher_pct": a.teacher_active_pct,
                "active_student_pct": a.student_active_pct,
                "last_teacher_login": _aware(a.last_teacher_login),
            },
        ))
    # Sağlığı en kötü olan üstte (yüksek skor = tehlike)
    out.sort(key=lambda r: -(r.get("health_score") or 0))
    return out


def drill_plan_members(db: Session, *, plan: str) -> list[dict]:
    """Belirli bir paketteki tüm aktif kurumlar."""
    rows = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True), Institution.plan == plan)
        .order_by(Institution.name)
        .all()
    )
    return [_row(r) for r in rows]


def drill_paying(db: Session) -> list[dict]:
    """Ödeyen (price > 0) tüm aktif kurumlar."""
    catalog = _plan_catalog()
    paying_plans = [
        p for p, info in catalog.items()
        if (getattr(info, "price_monthly_try", 0) or 0) > 0
    ]
    if not paying_plans:
        return []
    rows = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True), Institution.plan.in_(paying_plans))
        .order_by(Institution.name)
        .all()
    )
    return [_row(r) for r in rows]


def drill_free(db: Session) -> list[dict]:
    """Ücretsiz (price = 0) tüm aktif kurumlar."""
    catalog = _plan_catalog()
    free_plans = [
        p for p, info in catalog.items()
        if (getattr(info, "price_monthly_try", 0) or 0) == 0
    ]
    rows = (
        db.query(Institution)
        .filter(Institution.is_active.is_(True))
        .order_by(Institution.name)
        .all()
    )
    # free_plans boşsa fallback: trial veya bilinmeyen plan da ücretsiz say
    out: list[dict] = []
    for r in rows:
        _, price = _plan_label_and_price(r.plan)
        if price == 0:
            out.append(_row(r))
    return out


def drill_plan_changes(
    db: Session, *, reason_key: str, days: int = 30,
) -> list[dict]:
    """Son N gün içinde belirli bir sebeple plan değiştiren kurumlar.

    reason_key: PlanChangeReason değerlerinden biri (signup, upgrade, downgrade,
    pause, trial_expired, resume, vb.)
    """
    from app.models import PlanOwnerType  # local import — institution scope
    try:
        reason_enum = PlanChangeReason(reason_key)
    except Exception:
        return []
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.reason == reason_enum,
            PlanChangeHistory.occurred_at >= cutoff,
            PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION,
        )
        .order_by(desc(PlanChangeHistory.occurred_at))
        .all()
    )
    inst_ids = {r.owner_id for r in rows}
    if not inst_ids:
        return []
    insts = {
        i.id: i for i in
        db.query(Institution).filter(Institution.id.in_(inst_ids)).all()
    }
    out: list[dict] = []
    for r in rows:
        inst = insts.get(r.owner_id)
        if inst is None:
            continue
        when = _aware(r.occurred_at)
        days_ago = (_now() - when).days if when else None
        reason_label_map = {
            "signup": "Yeni kayıt",
            "upgrade": "Pakete yükseltme",
            "downgrade": "Paket alçaltma",
            "pause": "Hesabı duraklatma",
            "resume": "Hesabı devam ettirme",
            "trial_expired": "Deneme süresi bitti",
            "admin_override": "Süper admin manuel değişiklik",
            "guarantee_extend": "60 gün garanti uzatma",
            "academic_year_renewal": "Akademik yıl yenileme",
        }
        reason_text = reason_label_map.get(reason_key, reason_key)
        from_to = (
            f"{r.from_plan or '—'} → {r.to_plan}"
            if r.from_plan or r.to_plan else ""
        )
        out.append(_row(
            inst,
            reason=f"{reason_text} · {from_to}",
            extra={
                "event_at": when,
                "event_days_ago": days_ago,
                "from_plan": r.from_plan,
                "to_plan": r.to_plan,
                "event_note": r.note,
            },
        ))
    return out


def drill_trial_expired_unconverted(
    db: Session, *, days: int = 30,
) -> list[dict]:
    """Son N gün içinde denemesi bitip ödeyene dönüşmeyen kurumlar.

    plan_change_history'de TRIAL_EXPIRED olayı sonrasında upgrade gelmediyse
    bu kurum "kaybedilen fırsat".
    """
    from app.models import PlanOwnerType
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
            PlanChangeHistory.occurred_at >= cutoff,
            PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION,
        )
        .order_by(desc(PlanChangeHistory.occurred_at))
        .all()
    )
    inst_ids = list({r.owner_id for r in rows})
    if not inst_ids:
        return []
    # Bu kurumlar trial sonrası upgrade etmiş mi?
    upgraded_ids = {
        r.owner_id for r in
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.owner_id.in_(inst_ids),
            PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION,
            PlanChangeHistory.reason == PlanChangeReason.UPGRADE,
            PlanChangeHistory.occurred_at >= cutoff,
        )
        .all()
    }
    insts = {
        i.id: i for i in
        db.query(Institution).filter(Institution.id.in_(inst_ids)).all()
    }
    out: list[dict] = []
    for r in rows:
        if r.owner_id in upgraded_ids:
            continue
        inst = insts.get(r.owner_id)
        if inst is None:
            continue
        when = _aware(r.occurred_at)
        days_ago = (_now() - when).days if when else None
        out.append(_row(
            inst,
            reason=f"Deneme bitti, ödemeye geçmedi · {days_ago} gün önce",
            extra={"event_at": when, "event_days_ago": days_ago},
        ))
    # Yakın geçmişten geriye sırala
    out.sort(key=lambda r: (r.get("event_days_ago") or 999))
    return out


# Drill key → (label, handler) eşlemesi (route'tan dispatch için)
DRILL_REGISTRY: dict[str, dict] = {
    # Sağlık seviyeleri (Churn proxy alt kırılım)
    "health:critical": {"title": "Kritik — Acil müdahale",
                        "icon": "🚨",
                        "handler": lambda db: drill_health(db, level="critical")},
    "health:risk": {"title": "Risk altında",
                    "icon": "⚠️",
                    "handler": lambda db: drill_health(db, level="risk")},
    "health:watch": {"title": "İzleme listesinde",
                     "icon": "👀",
                     "handler": lambda db: drill_health(db, level="watch")},
    "health:healthy": {"title": "Sağlıklı kurumlar",
                       "icon": "✅",
                       "handler": lambda db: drill_health(db, level="healthy")},
    # Trial
    "trial:expired_30d": {
        "title": "Denemesi bitti, ödemeye geçmedi (son 30 gün)",
        "icon": "💔",
        "handler": lambda db: drill_trial_expired_unconverted(db, days=30),
    },
    # Plan hareketleri (son 30 gün)
    "plan_change:signup": {"title": "Yeni kayıt (son 30 gün)",
                            "icon": "✨",
                            "handler": lambda db: drill_plan_changes(db, reason_key="signup")},
    "plan_change:upgrade": {"title": "Pakete yükseltme (son 30 gün)",
                            "icon": "↑",
                            "handler": lambda db: drill_plan_changes(db, reason_key="upgrade")},
    "plan_change:downgrade": {"title": "Paket alçaltma (son 30 gün)",
                              "icon": "↓",
                              "handler": lambda db: drill_plan_changes(db, reason_key="downgrade")},
    "plan_change:pause": {"title": "Hesabı duraklatma (son 30 gün)",
                          "icon": "⏸",
                          "handler": lambda db: drill_plan_changes(db, reason_key="pause")},
    "plan_change:resume": {"title": "Hesabı devam ettirme (son 30 gün)",
                           "icon": "▶",
                           "handler": lambda db: drill_plan_changes(db, reason_key="resume")},
    "plan_change:trial_expired": {"title": "Deneme bitti olayları (son 30 gün)",
                                  "icon": "⏰",
                                  "handler": lambda db: drill_plan_changes(db, reason_key="trial_expired")},
    "plan_change:guarantee_extend": {"title": "60 gün garanti uzatma (son 30 gün)",
                                     "icon": "🛡",
                                     "handler": lambda db: drill_plan_changes(db, reason_key="guarantee_extend")},
    "plan_change:academic_year_renewal": {"title": "Akademik yıl yenileme (son 30 gün)",
                                          "icon": "📅",
                                          "handler": lambda db: drill_plan_changes(db, reason_key="academic_year_renewal")},
    # Ödeme tipi
    "paying": {"title": "Ödeyen kurumlar", "icon": "💰",
                "handler": lambda db: drill_paying(db)},
    "free": {"title": "Ücretsiz kurumlar", "icon": "🆓",
             "handler": lambda db: drill_free(db)},
}


def drill_invoice_bucket(db: Session, *, bucket: str) -> list[dict]:
    """Belirli bir ödeme takvimi bandında bulunan faturaları kurum bazlı döndür.

    Faz F drill — UI'da "3 gün içinde 5 fatura" gibi sayıya tıklayınca
    açılan liste. Her satır {institution_name, plan, amount, due_at, ...}.
    """
    summary = payment_calendar_summary(db, days_horizon=30)
    for b in summary["buckets"]:
        if b["key"] != bucket:
            continue
        out: list[dict] = []
        for inv in b["items"]:
            inst_name = inv["institution_name"] or f"Kurum #{inv['institution_id']}"
            reason_parts = []
            if inv["days_overdue"] > 0:
                reason_parts.append(f"{inv['days_overdue']} gün gecikti")
            elif inv["days_until_due"] is not None:
                if inv["days_until_due"] == 0:
                    reason_parts.append("Bugün dolacak")
                elif inv["days_until_due"] == 1:
                    reason_parts.append("Yarın dolacak")
                else:
                    reason_parts.append(f"{inv['days_until_due']} gün kaldı")
            reason_parts.append(f"{inv['amount_try']:,} ₺")
            reason_parts.append(inv["status_label"])
            out.append({
                "institution_id": inv["institution_id"],
                "institution_name": inst_name,
                "plan": inv["plan"],
                "plan_label": inv["plan_label"],
                "monthly_price_try": inv["amount_try"],
                "reason": " · ".join(reason_parts),
                "event_at": inv["due_at"],
                "event_days_ago": -inv["days_until_due"]
                    if inv["days_until_due"] is not None else None,
                "detail_url": inv["detail_url"],
                "invoice_id": inv["invoice_id"],
                "invoice_status": inv["status"],
            })
        return out
    return []


def drill_for_key(db: Session, *, key: str, plan: str | None = None) -> dict:
    """Route handler için dispatch.

    Dönen dict: {title, icon, key, plan, rows, count}.
    """
    # plan:<code> dinamik anahtarı destekle
    if key.startswith("plan:"):
        plan_code = key.split(":", 1)[1] or plan
        if not plan_code:
            return {"title": "Plan", "icon": "📦", "key": key, "rows": [], "count": 0}
        label, _ = _plan_label_and_price(plan_code)
        rows = drill_plan_members(db, plan=plan_code)
        return {
            "title": f"{label} planındaki kurumlar",
            "icon": "📦",
            "key": key,
            "plan": plan_code,
            "rows": rows,
            "count": len(rows),
        }

    # invoice_bucket:<bucket_key> dinamik anahtarı
    if key.startswith("invoice_bucket:"):
        bucket_key = key.split(":", 1)[1]
        rows = drill_invoice_bucket(db, bucket=bucket_key)
        is_overdue = bucket_key.startswith("overdue")
        return {
            "title": f"{BUCKET_LABELS_TR.get(bucket_key, bucket_key)} — faturalar",
            "icon": "🔴" if is_overdue else "⏰",
            "key": key,
            "rows": rows,
            "count": len(rows),
        }

    entry = DRILL_REGISTRY.get(key)
    if entry is None:
        return {"title": "Bilinmeyen kategori", "icon": "❓",
                "key": key, "rows": [], "count": 0,
                "error": "unknown_key"}
    rows = entry["handler"](db)
    return {
        "title": entry["title"],
        "icon": entry["icon"],
        "key": key,
        "plan": plan,
        "rows": rows,
        "count": len(rows),
    }


# ---------------------------- Ödeme Takvimi (Faz F-1) ----------------------------


def _invoice_row(inv: Invoice, *,
                 inst_name: str | None = None,
                 user_name: str | None = None,
                 now: datetime | None = None) -> dict:
    """Bir Invoice satırını ödeme takvimi UI'ı için dict'e çevir.
    Owner-aware: institution veya user — owner_type alanına göre name/url üretir.
    """
    now = now or _now()
    due = _aware(inv.due_at)
    paid = _aware(inv.paid_at)
    days_until_due = (due - now).days if due else None
    days_overdue = (now - due).days if (due and now > due) else 0
    label, _ = _plan_label_and_price(inv.plan)
    # Owner kimliği — backward compat için institution_id/institution_name alanları
    # institution sahipler için dolu, user sahipler için None döner.
    if inv.owner_type == "user":
        owner_name = user_name
        owner_url = f"/admin/revenue/users/{inv.user_id}"
        owner_id = inv.user_id
    else:
        owner_name = inst_name
        owner_url = f"/admin/revenue/institutions/{inv.institution_id}"
        owner_id = inv.institution_id
    return {
        "invoice_id": inv.id,
        # Backward-compat alanlar (mevcut template'ler hâlâ institution_id kullanır)
        "institution_id": inv.institution_id,
        "institution_name": inst_name,
        # Owner-aware alanlar
        "owner_type": inv.owner_type,
        "owner_id": owner_id,
        "owner_name": owner_name,
        "user_id": inv.user_id,
        "user_name": user_name,
        "plan": inv.plan,
        "plan_label": label,
        "amount_try": inv.amount_try,
        "status": inv.status.value,
        "status_label": INVOICE_STATUS_LABELS_TR.get(inv.status, inv.status.value),
        "due_at": due,
        "paid_at": paid,
        "days_until_due": days_until_due,
        "days_overdue": days_overdue,
        "payment_method": inv.payment_method.value if inv.payment_method else None,
        "attempt_count": inv.attempt_count,
        "last_reminder_kind": inv.last_reminder_kind,
        # Owner detay URL — UI'da satır linki için
        "detail_url": owner_url,
    }


def _resolve_invoice_owners(
    db: Session, invs: list[Invoice],
) -> tuple[dict[int, "Institution"], dict[int, "User"]]:
    """Bir invoice listesi için ihtiyaç duyulan Institution + User name map'lerini çek.

    Tek pass: hangi institution_id'ler ve hangi user_id'ler kullanılıyor onları
    bulup tek SQL ile yükler.
    """
    inst_ids = {r.institution_id for r in invs if r.institution_id is not None}
    user_ids = {r.user_id for r in invs if r.user_id is not None}
    insts: dict[int, "Institution"] = {}
    users: dict[int, "User"] = {}
    if inst_ids:
        insts = {
            i.id: i for i in
            db.query(Institution).filter(Institution.id.in_(inst_ids)).all()
        }
    if user_ids:
        from app.models import User as _UserMdl
        users = {
            u.id: u for u in
            db.query(_UserMdl).filter(_UserMdl.id.in_(user_ids)).all()
        }
    return insts, users


# Try import labels — module-level so eval/render hızlı
try:
    from app.models import INVOICE_STATUS_LABELS_TR
except Exception:  # pragma: no cover
    INVOICE_STATUS_LABELS_TR = {}  # type: ignore[assignment]


def _bucket_label(days_until_due: int | None, days_overdue: int) -> str:
    """Bir faturayı insan dostu bandlara ayırır."""
    if days_overdue > 0:
        if days_overdue >= 7:
            return "overdue_7plus"
        if days_overdue >= 3:
            return "overdue_3_6"
        return "overdue_1_2"
    if days_until_due is None:
        return "unknown"
    if days_until_due <= 0:
        return "due_today"
    if days_until_due == 1:
        return "due_tomorrow"
    if days_until_due <= 3:
        return "due_in_3d"
    if days_until_due <= 7:
        return "due_in_7d"
    if days_until_due <= 14:
        return "due_in_14d"
    return "later"


BUCKET_ORDER = [
    "overdue_7plus", "overdue_3_6", "overdue_1_2",
    "due_today", "due_tomorrow", "due_in_3d", "due_in_7d", "due_in_14d",
]

BUCKET_LABELS_TR = {
    "overdue_7plus": "7+ gün gecikti",
    "overdue_3_6": "3-6 gün gecikti",
    "overdue_1_2": "1-2 gün gecikti",
    "due_today": "Bugün dolacak",
    "due_tomorrow": "Yarın dolacak",
    "due_in_3d": "3 gün içinde",
    "due_in_7d": "7 gün içinde",
    "due_in_14d": "14 gün içinde",
    "later": "Sonra",
    "unknown": "Bilinmiyor",
}


def upcoming_invoices(db: Session, *, days_horizon: int = 14) -> list[dict]:
    """Önümüzdeki N gün içinde dolacak (PENDING + OVERDUE) faturalar.

    Owner-aware: hem institution hem bağımsız öğretmen (user) faturalarını
    döndürür. Sıralama: önce gecikmiş (en eski tarihli üstte), sonra yaklaşan.
    """
    now = _now()
    horizon = now + timedelta(days=days_horizon)
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            Invoice.due_at <= horizon,
        )
        .order_by(Invoice.due_at)
        .all()
    )
    if not rows:
        return []
    insts, users = _resolve_invoice_owners(db, rows)
    out: list[dict] = []
    for r in rows:
        inst = insts.get(r.institution_id) if r.institution_id else None
        u = users.get(r.user_id) if r.user_id else None
        d = _invoice_row(
            r,
            inst_name=inst.name if inst else None,
            user_name=(u.full_name or u.email) if u else None,
            now=now,
        )
        d["bucket"] = _bucket_label(d["days_until_due"], d["days_overdue"])
        out.append(d)
    return out


def overdue_invoices(db: Session) -> list[dict]:
    """Vade geçmiş, hâlâ ödenmemiş tüm faturalar (owner-aware)."""
    now = _now()
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            Invoice.due_at < now,
        )
        .order_by(Invoice.due_at)
        .all()
    )
    insts, users = _resolve_invoice_owners(db, rows)
    out: list[dict] = []
    for r in rows:
        inst = insts.get(r.institution_id) if r.institution_id else None
        u = users.get(r.user_id) if r.user_id else None
        out.append(_invoice_row(
            r,
            inst_name=inst.name if inst else None,
            user_name=(u.full_name or u.email) if u else None,
            now=now,
        ))
    return out


def invoices_for_owner(
    db: Session, *,
    institution_id: int | None = None,
    user_id: int | None = None,
    include_archived: bool = False,
    limit: int = 100,
) -> list[dict]:
    """Bir owner'ın tüm faturaları (status fark etmez). User 360 Billing sekmesi
    için. XOR: institution_id veya user_id — tam biri verilmeli.
    """
    q = db.query(Invoice).order_by(Invoice.due_at.desc(), Invoice.id.desc())
    if institution_id is not None and user_id is None:
        q = q.filter(Invoice.institution_id == institution_id)
    elif user_id is not None and institution_id is None:
        q = q.filter(Invoice.user_id == user_id)
    else:
        raise ValueError("invoices_for_owner: institution_id veya user_id (tam biri)")
    if not include_archived:
        q = q.filter(Invoice.archived_at.is_(None))
    rows = q.limit(limit).all()
    if not rows:
        return []
    insts, users = _resolve_invoice_owners(db, rows)
    now = _now()
    out: list[dict] = []
    for r in rows:
        inst = insts.get(r.institution_id) if r.institution_id else None
        u = users.get(r.user_id) if r.user_id else None
        out.append(_invoice_row(
            r,
            inst_name=inst.name if inst else None,
            user_name=(u.full_name or u.email) if u else None,
            now=now,
        ))
    return out


def payment_calendar_summary(db: Session, *, days_horizon: int = 14) -> dict:
    """Ödeme takvimi özeti — üst banner için.

    Şunu döner:
      - buckets: {bucket_key: {label, count, total_try, items: [...]}}
      - total_count, total_amount_try
      - overdue_total_try (gecikmiş toplam ₺)
      - upcoming_total_try (gelecek N gün gelen ₺)
    """
    invs = upcoming_invoices(db, days_horizon=days_horizon)
    buckets: dict[str, dict] = {}
    overdue_total = 0
    upcoming_total = 0
    for inv in invs:
        b = inv["bucket"]
        buckets.setdefault(b, {
            "key": b,
            "label": BUCKET_LABELS_TR.get(b, b),
            "count": 0,
            "total_try": 0,
            "items": [],
        })
        buckets[b]["count"] += 1
        buckets[b]["total_try"] += inv["amount_try"]
        buckets[b]["items"].append(inv)
        if b.startswith("overdue"):
            overdue_total += inv["amount_try"]
        else:
            upcoming_total += inv["amount_try"]

    # BUCKET_ORDER sırasına göre liste
    ordered = [buckets[k] for k in BUCKET_ORDER if k in buckets]
    return {
        "buckets": ordered,
        "total_count": len(invs),
        "total_amount_try": overdue_total + upcoming_total,
        "overdue_total_try": overdue_total,
        "upcoming_total_try": upcoming_total,
        "days_horizon": days_horizon,
    }


def mark_overdue(db: Session, *, autocommit: bool = True) -> int:
    """due_at < now olan PENDING faturaları OVERDUE'ye taşı.

    Bu fonksiyon cron tarafından çağrılır (günlük 02:00 gibi). Manuel da
    çağırılabilir. Geri döner: state değiştirilen kayıt sayısı.
    """
    now = _now()
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.status == InvoiceStatus.PENDING,
            Invoice.due_at < now,
        )
        .all()
    )
    count = 0
    for inv in rows:
        inv.status = InvoiceStatus.OVERDUE
        count += 1
    if autocommit:
        db.commit()
    return count


# ---------------------------- Aggregator ----------------------------


def get_revenue_panel_data(db: Session) -> dict:
    return {
        "generated_at": _now(),
        "mrr": mrr(db),
        "plan_distribution": plan_distribution(db),
        "trial_ending_soon": trial_ending_soon(db, days_horizon=7),
        "trial_expired_30d": trial_expired_unconverted(db, days=30),
        "change_summary_30d": plan_change_summary(db, days=30),
        "daily_changes_30d": daily_plan_changes(db, days=30),
        "churn_proxy": churn_proxy(db),
        "payment_calendar": payment_calendar_summary(db, days_horizon=14),
    }


__all__ = [
    "BUCKET_LABELS_TR",
    "BUCKET_ORDER",
    "DRILL_REGISTRY",
    "TrialEntry",
    "churn_proxy",
    "daily_plan_changes",
    "drill_for_key",
    "drill_free",
    "drill_health",
    "drill_paying",
    "drill_plan_changes",
    "drill_plan_members",
    "drill_trial_expired_unconverted",
    "get_revenue_panel_data",
    "mark_overdue",
    "mrr",
    "overdue_invoices",
    "payment_calendar_summary",
    "plan_change_summary",
    "plan_distribution",
    "trial_ending_soon",
    "trial_expired_unconverted",
    "upcoming_invoices",
]
