"""Sprint D.2 (Ticari Pano 2.0 — Faz G) — Kurum kohort + LTV analizi.

Bu servis "ticari" kohort analizi yapar — institution-level retention/churn.
Öğrenci-bazlı sınıf/alan cohort analizi için `cohort_analysis.py` ayrı kalır.

Ana fonksiyonlar:
  - signup_cohort_matrix: aylık kayıt cohort'u + 1..N ay tutunma
  - plan_churn_summary: PlanChangeHistory'den churn/upgrade/conversion oranı
  - ltv_estimate: plan başına LTV (ortalama yaş × aylık ücret)

Tasarım:
- "Tutundu" = institution.is_active=True + plan'ı PLAN_CATALOG'ta ücretli (price > 0)
- "Trial dönüşüm" = trial bittikten sonra ücretli plana geçti mi
- "Churn" = ücretli plandan ücretsize / inaktife geçti
- Migration veya yeni tablo gerekmez — Institution + PlanChangeHistory + Invoice yeter
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
)
from app.models.plan_history import PlanOwnerType


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
    try:
        from app.services.plans import PLAN_CATALOG
    except ImportError:
        return {}
    return PLAN_CATALOG or {}


def _is_paid_plan(plan: str | None) -> bool:
    """Plan ücretli mi (price_monthly_try > 0)?"""
    if not plan:
        return False
    catalog = _plan_catalog()
    info = catalog.get(plan)
    if info is None:
        return False
    return (getattr(info, "price_monthly_try", 0) or 0) > 0


def _plan_price(plan: str | None) -> int:
    if not plan:
        return 0
    catalog = _plan_catalog()
    info = catalog.get(plan)
    if info is None:
        return 0
    return int(getattr(info, "price_monthly_try", 0) or 0)


def _month_key(dt: datetime) -> str:
    """YYYY-MM"""
    return f"{dt.year:04d}-{dt.month:02d}"


def _month_label_tr(year: int, month: int) -> str:
    months = [
        "Oca", "Şub", "Mar", "Nis", "May", "Haz",
        "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
    ]
    return f"{months[month - 1]} {year}"


def _months_between(start: datetime, end: datetime) -> int:
    """start ve end arası tam ay sayısı (yaklaşık)."""
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month)


def _rate_color(pct: float | None) -> str:
    """Heatmap renk kodu — yeşil → kırmızı gradyanı."""
    if pct is None:
        return "slate"
    if pct >= 80:
        return "emerald"
    if pct >= 60:
        return "lime"
    if pct >= 40:
        return "amber"
    if pct >= 20:
        return "orange"
    return "rose"


# ---------------------------- Signup cohort matrix ----------------------------


def signup_cohort_matrix(
    db: Session,
    *,
    months_back: int = 12,
    horizon_months: int = 12,
) -> dict:
    """Aylık kayıt cohort'u — N ay önceki tüm kurumların 1..M aya tutunması.

    Args:
        months_back: kaç aylık cohort gösterilsin (default 12)
        horizon_months: her cohort için kaç aylık ufuk (default 12)

    Returns:
        {
          "cohorts": [
            {
              "cohort_key": "2025-06",
              "cohort_label": "Haz 2025",
              "signup_count": 12,
              "signup_month_age": 11,  // şu an cohort'tan kaç ay geçti
              "retention": [
                {"month": 1, "count": 11, "pct": 92, "color": "emerald"},
                {"month": 2, "count": 9, "pct": 75, "color": "lime"},
                ...
              ],
            },
            ...
          ],
          "horizon_months": 12,
          "total_signups": 156,
        }
    """
    now = _now()

    # 1) Cohort kapsamına giren kurumları çek
    cutoff = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
    # months_back kadar geri git
    for _ in range(months_back - 1):
        cutoff = (cutoff - timedelta(days=1)).replace(day=1)
    # Şimdi cutoff = en eski cohort ayın 1'i

    insts = (
        db.query(Institution)
        .filter(Institution.created_at >= cutoff)
        .all()
    )

    # 2) Cohort key bazında grupla
    cohort_groups: dict[str, list[Institution]] = defaultdict(list)
    for inst in insts:
        ca = _aware(inst.created_at) or now
        key = _month_key(ca)
        cohort_groups[key].append(inst)

    # 3) Plan değişiklik geçmişini institution_id bazında çek
    # — retained at month N hesabı için
    pch_rows = (
        db.query(
            PlanChangeHistory.owner_id,
            PlanChangeHistory.from_plan,
            PlanChangeHistory.to_plan,
            PlanChangeHistory.occurred_at,
            PlanChangeHistory.reason,
        )
        .filter(PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION)
        .order_by(PlanChangeHistory.occurred_at)
        .all()
    )
    pch_by_inst: dict[int, list] = defaultdict(list)
    for r in pch_rows:
        pch_by_inst[r.owner_id].append(r)

    def _plan_at(inst: Institution, target_dt: datetime) -> str | None:
        """Belirli bir tarihte kurumun planı neydi? PlanChangeHistory'den geriye git."""
        # En son target_dt'den önceki PCH kaydını bul
        last = None
        for r in pch_by_inst.get(inst.id, []):
            occ = _aware(r.occurred_at)
            if occ and occ <= target_dt:
                last = r
            else:
                break
        if last:
            return last.to_plan
        # Hiç PCH yoksa şu anki planı varsay (created_at'tan beri aynı)
        return inst.plan

    # 4) Her cohort için 1..horizon retention hesapla
    cohorts_out: list[dict] = []
    for key, group in sorted(cohort_groups.items()):
        year, month = int(key[:4]), int(key[5:7])
        cohort_start = datetime(year, month, 1, tzinfo=timezone.utc)
        signup_count = len(group)
        if signup_count == 0:
            continue

        # Cohort'tan şu ana kadar kaç ay geçti
        signup_month_age = _months_between(cohort_start, now)

        retention: list[dict] = []
        for m in range(1, horizon_months + 1):
            if m > signup_month_age:
                # Henüz geçmedi bu ay — gösterme
                retention.append({
                    "month": m,
                    "count": None,
                    "pct": None,
                    "color": "slate",
                    "future": True,
                })
                continue
            check_dt = cohort_start + timedelta(days=30 * m)
            retained = 0
            for inst in group:
                if not inst.is_active:
                    # İnaktif → tutmadı
                    continue
                plan_at = _plan_at(inst, check_dt)
                if _is_paid_plan(plan_at):
                    retained += 1
            pct = round(100 * retained / signup_count, 1) if signup_count > 0 else 0
            retention.append({
                "month": m,
                "count": retained,
                "pct": pct,
                "color": _rate_color(pct),
                "future": False,
            })

        cohorts_out.append({
            "cohort_key": key,
            "cohort_label": _month_label_tr(year, month),
            "signup_count": signup_count,
            "signup_month_age": signup_month_age,
            "retention": retention,
        })

    return {
        "cohorts": cohorts_out,
        "horizon_months": horizon_months,
        "months_back": months_back,
        "total_signups": sum(c["signup_count"] for c in cohorts_out),
    }


# ---------------------------- Plan churn / conversion ----------------------------


def plan_churn_summary(db: Session, *, days: int = 90) -> dict:
    """Son N gün içindeki plan değişimi özeti.

    Returns:
        {
          "window_days": 90,
          "signup_count": 23,        // SIGNUP olayı
          "trial_expired_count": 15, // TRIAL_EXPIRED olayı
          "upgrade_count": 8,        // UPGRADE olayı
          "downgrade_count": 3,      // DOWNGRADE olayı
          "cancel_count": 5,         // is_active=False olan kurumlar (yaklaşık)
          "trial_conversion_pct": 27, // trial sonrası ücretli plana geçen %
          "net_movement": +5,        // upgrade - downgrade - cancel
        }
    """
    now = _now()
    cutoff = now - timedelta(days=days)

    # Olay sayıları
    def _count_reason(reason: PlanChangeReason) -> int:
        return int(
            (db.query(func.count(PlanChangeHistory.id))
             .filter(
                 PlanChangeHistory.reason == reason,
                 PlanChangeHistory.occurred_at >= cutoff,
             )
             .scalar()) or 0
        )

    signup_count = _count_reason(PlanChangeReason.SIGNUP)
    trial_expired_count = _count_reason(PlanChangeReason.TRIAL_EXPIRED)
    upgrade_count = _count_reason(PlanChangeReason.UPGRADE)
    downgrade_count = _count_reason(PlanChangeReason.DOWNGRADE)

    # Trial conversion: TRIAL_EXPIRED olaylarından sonra to_plan ücretli mi
    trial_expired_rows = (
        db.query(PlanChangeHistory.to_plan)
        .filter(
            PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
            PlanChangeHistory.occurred_at >= cutoff,
        )
        .all()
    )
    trial_converted = sum(
        1 for r in trial_expired_rows if _is_paid_plan(r.to_plan)
    )
    trial_conversion_pct: int | None = None
    if trial_expired_count > 0:
        trial_conversion_pct = int(round(100 * trial_converted / trial_expired_count))

    # Cancel: bu pencerede inaktif olmuş kurumlar (yaklaşık — is_active flag)
    # Daha doğrusu DOWNGRADE'den ücretsize geçenler
    cancel_count = 0
    downgrade_to_free = (
        db.query(PlanChangeHistory.to_plan)
        .filter(
            PlanChangeHistory.reason == PlanChangeReason.DOWNGRADE,
            PlanChangeHistory.occurred_at >= cutoff,
        )
        .all()
    )
    for r in downgrade_to_free:
        if not _is_paid_plan(r.to_plan):
            cancel_count += 1

    net = upgrade_count - downgrade_count

    return {
        "window_days": days,
        "signup_count": signup_count,
        "trial_expired_count": trial_expired_count,
        "trial_converted_count": trial_converted,
        "trial_conversion_pct": trial_conversion_pct,
        "upgrade_count": upgrade_count,
        "downgrade_count": downgrade_count,
        "cancel_count": cancel_count,
        "net_movement": net,
    }


# ---------------------------- LTV estimate ----------------------------


@dataclass
class PlanLtv:
    plan: str
    label: str
    monthly_price_try: int
    active_count: int
    avg_age_months: float
    estimated_ltv_try: int


def ltv_estimate(db: Session) -> dict:
    """Plan başına LTV tahmini.

    Yöntem: LTV = ortalama_yaş_ay × aylık_fiyat
    (Marj yüzdesi şimdilik dahil edilmedi; net rakam ileride çarpılabilir.)
    """
    now = _now()
    catalog = _plan_catalog()
    rows = (
        db.query(Institution.plan, Institution.created_at)
        .filter(Institution.is_active.is_(True))
        .all()
    )
    by_plan: dict[str, list[float]] = defaultdict(list)
    for plan, created_at in rows:
        ca = _aware(created_at) or now
        age_months = max(0.0, (now - ca).days / 30.0)
        by_plan[plan].append(age_months)

    out: list[PlanLtv] = []
    total_ltv = 0
    for plan, ages in by_plan.items():
        info = catalog.get(plan)
        price = int(getattr(info, "price_monthly_try", 0) or 0) if info else 0
        label = getattr(info, "label", plan) if info else plan
        if not ages:
            continue
        avg_age = sum(ages) / len(ages)
        # Tahmini LTV: ücretsiz planlar 0
        ltv = int(round(avg_age * price)) if price > 0 else 0
        out.append(PlanLtv(
            plan=plan,
            label=label,
            monthly_price_try=price,
            active_count=len(ages),
            avg_age_months=round(avg_age, 1),
            estimated_ltv_try=ltv,
        ))
        # Toplam LTV = her plan için (count × LTV)
        total_ltv += ltv * len(ages)

    # Ücretli üstte
    out.sort(key=lambda r: (-r.monthly_price_try, -r.active_count))
    return {
        "plans": out,
        "total_ltv_try": total_ltv,
        "paying_count": sum(p.active_count for p in out if p.monthly_price_try > 0),
        "avg_ltv_per_paying": (
            int(round(total_ltv / sum(p.active_count for p in out if p.monthly_price_try > 0)))
            if any(p.monthly_price_try > 0 for p in out)
            else 0
        ),
    }


__all__ = [
    "PlanLtv",
    "ltv_estimate",
    "plan_churn_summary",
    "signup_cohort_matrix",
]
