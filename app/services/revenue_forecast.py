"""Sprint E.2 (Ticari Pano 2.0 — Faz H) — Tahmin & Senaryo.

Bu servis ileri-bakış (forward-looking) projeksiyonlar üretir:

1) MRR projeksiyonu (90 gün):
   - Lineer trend (geçmiş 90 gün gerçek MRR'den)
   - + Trial dönüşüm beklentisi (yaklaşan trial × tarihi conversion rate)
   - − Beklenen churn (paying_at_risk × tarihi churn rate)

2) "Risk Altında MRR":
   - Sağlık skoru kritik/risk olan ödeyen kurumların toplam aylık geliri
   - Hiç müdahale edilmezse 90 günde kaybedilebilecek tutar

3) Senaryo karşılaştırma:
   - Status quo (hiçbir şey yapma) vs Müdahale et (kritiklerin %X'i kurtarılır)
   - 30/60/90 günlük MRR farkı

Tüm hesaplamalar deterministik / tahmin (gerçek olay değil). Marj dahil değil.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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
        return PLAN_CATALOG
    except ImportError:
        return {}


def _plan_price(plan: str | None) -> int:
    if not plan:
        return 0
    info = _plan_catalog().get(plan)
    if info is None:
        return 0
    return max(0, int(getattr(info, "price_monthly_try", 0) or 0))


# ---------------------------- Risk Altında MRR ----------------------------


@dataclass
class AtRiskInstitution:
    institution_id: int       # institution.id (owner_type='institution') veya user.id (owner_type='user')
    name: str
    plan: str
    monthly_price_try: int
    health_score: int | None
    severity: str             # 'critical' | 'risk'
    owner_type: str = "institution"  # 'institution' | 'user' (bağımsız öğretmen)

    @property
    def detail_url(self) -> str:
        if self.owner_type == "user":
            return f"/admin/revenue/users/{self.institution_id}"
        return f"/admin/revenue/institutions/{self.institution_id}"


def risk_at_mrr(db: Session, *, include_independent_teachers: bool = True) -> dict:
    """Sağlık skoru critical/risk olan ödeyen kurumların toplam aylık geliri.

    Sprint F.2: bağımsız ödeyen öğretmenler de eklendi (heuristik — son 30 gün
    login yapmamışlarsa "risk").
    """
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    try:
        from app.services.tenant_health import bulk_health_assessment
        assessments = bulk_health_assessment(
            db, institutions=insts, today=_now().date(),
        )
    except Exception:
        logger.exception("risk_at_mrr: bulk_health_assessment fail")
        assessments = []

    health_map = {a.institution.id: a for a in assessments}

    at_risk: list[AtRiskInstitution] = []
    total_mrr = 0
    critical_mrr = 0
    risk_mrr = 0

    for inst in insts:
        price = _plan_price(inst.plan)
        if price == 0:
            continue
        a = health_map.get(inst.id)
        if a is None:
            continue
        # tenant_health: level "critical"/"risk"/"watch"/"healthy"
        # raw score yüksek = kötü; UI'da 100-score gösterilir
        level = getattr(a, "level", None)
        raw_score = getattr(a, "score", None)
        # User-facing skor (yüksek=sağlıklı) — institution_360 ile tutarlı
        user_facing_score = (
            max(0, min(100, 100 - raw_score)) if raw_score is not None else None
        )
        severity: str | None = None
        if level == "critical":
            severity = "critical"
            critical_mrr += price
        elif level == "risk":
            severity = "risk"
            risk_mrr += price
        else:
            continue
        total_mrr += price
        at_risk.append(AtRiskInstitution(
            institution_id=inst.id,
            name=inst.name,
            plan=inst.plan,
            monthly_price_try=price,
            health_score=user_facing_score,
            severity=severity,
        ))

    # Sprint F.2: bağımsız ödeyen öğretmenler de dahil (heuristik)
    if include_independent_teachers:
        from app.models import User, UserRole
        cutoff_30d = _now() - timedelta(days=30)
        indie_teachers = (
            db.query(User)
            .filter(
                User.role == UserRole.TEACHER,
                User.institution_id.is_(None),
                User.is_active.is_(True),
            )
            .all()
        )
        for u in indie_teachers:
            price = _plan_price(u.plan)
            if price == 0:
                continue
            # Heuristik: 30g'dir login yoksa "critical", 14-30g arası "risk"
            last = _aware(getattr(u, "last_login_at", None))
            if last is None:
                severity = "critical"
                critical_mrr += price
            elif last < cutoff_30d:
                severity = "critical"
                critical_mrr += price
            elif last < _now() - timedelta(days=14):
                severity = "risk"
                risk_mrr += price
            else:
                continue
            total_mrr += price
            at_risk.append(AtRiskInstitution(
                institution_id=u.id,
                name=f"{u.full_name or u.email} (bağımsız)",
                plan=u.plan,
                monthly_price_try=price,
                health_score=None,
                severity=severity,
                owner_type="user",
            ))

    # Önce critical, sonra MRR azalan
    at_risk.sort(key=lambda x: (0 if x.severity == "critical" else 1, -x.monthly_price_try))

    return {
        "total_at_risk_mrr": total_mrr,
        "critical_mrr": critical_mrr,
        "risk_mrr": risk_mrr,
        "critical_count": sum(1 for x in at_risk if x.severity == "critical"),
        "risk_count": sum(1 for x in at_risk if x.severity == "risk"),
        "institutions": at_risk,
    }


# ---------------------------- Tarihi oranlar ----------------------------


def _historical_trial_conversion_rate(db: Session, *, days: int = 180) -> float:
    """Son N gündeki TRIAL_EXPIRED olaylarından ücretliye dönüşüm oranı."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(PlanChangeHistory.to_plan)
        .filter(
            PlanChangeHistory.reason == PlanChangeReason.TRIAL_EXPIRED,
            PlanChangeHistory.occurred_at >= cutoff,
        )
        .all()
    )
    total = len(rows)
    if total == 0:
        return 0.0
    converted = sum(1 for r in rows if _plan_price(r.to_plan) > 0)
    return converted / total


def _historical_churn_rate_monthly(db: Session, *, days: int = 90) -> float:
    """Son N gündeki ücretli plandan ücretsize/inaktife geçiş oranı (aylık)."""
    cutoff = _now() - timedelta(days=days)
    # DOWNGRADE olayları: ücretliden ücretsize
    rows = (
        db.query(PlanChangeHistory.from_plan, PlanChangeHistory.to_plan)
        .filter(
            PlanChangeHistory.reason == PlanChangeReason.DOWNGRADE,
            PlanChangeHistory.occurred_at >= cutoff,
        )
        .all()
    )
    churn_count = sum(
        1 for r in rows
        if _plan_price(r.from_plan) > 0 and _plan_price(r.to_plan) == 0
    )
    # Şu anki ödeyen sayısı
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    paying_count = sum(1 for i in insts if _plan_price(i.plan) > 0)
    if paying_count == 0:
        return 0.0
    # Aylık oran: N gündeki / paying_count → 30 güne normalize
    months = days / 30.0
    if months <= 0:
        return 0.0
    return (churn_count / paying_count) / months


# ---------------------------- MRR projeksiyon ----------------------------


def _current_mrr(db: Session) -> int:
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    return sum(_plan_price(i.plan) for i in insts)


def mrr_projection(
    db: Session, *,
    horizon_days: int = 90,
    intervention_save_rate: float = 0.0,
) -> dict:
    """N gün ileri MRR projeksiyonu.

    Args:
        horizon_days: 30 / 60 / 90 önerilir
        intervention_save_rate: 0.0 = status quo, 0.5 = riskte olanların %50'si kurtarılır

    Returns:
        {
          "current_mrr": int,
          "horizon_days": int,
          "trial_conversion_rate": float,
          "monthly_churn_rate": float,
          "expected_trial_conversions_mrr": int,
          "expected_churn_mrr": int,
          "expected_at_risk_loss_mrr": int,  // sağlık skoruna göre risk altı
          "projected_mrr_status_quo": int,
          "projected_mrr_with_intervention": int,
          "delta_mrr": int,  // intervention - status_quo
          "intervention_save_rate": float,
        }
    """
    current_mrr = _current_mrr(db)
    trial_conv = _historical_trial_conversion_rate(db)
    churn_rate = _historical_churn_rate_monthly(db)
    months = horizon_days / 30.0

    # Beklenen trial dönüşüm geliri (önümüzdeki N gün içinde trial bitenler)
    horizon_dt = _now() + timedelta(days=horizon_days)
    trial_ending = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            Institution.trial_ends_at.isnot(None),
            Institution.trial_ends_at <= horizon_dt,
            Institution.trial_ends_at >= _now(),
        )
        .all()
    )
    # Trial'dan dönüşürse hangi plana geçeceği: post_trial_plan veya solo_pro varsay
    expected_conversion_mrr = 0
    for inst in trial_ending:
        target_plan = inst.post_trial_plan or "solo_pro"
        price = _plan_price(target_plan)
        expected_conversion_mrr += int(price * trial_conv)

    # Beklenen churn: paying_count × monthly_churn × months × avg_paying_price
    insts_all = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    paying_prices = [_plan_price(i.plan) for i in insts_all if _plan_price(i.plan) > 0]
    avg_paying = (sum(paying_prices) / len(paying_prices)) if paying_prices else 0
    paying_count = len(paying_prices)
    expected_churn_mrr = int(paying_count * churn_rate * months * avg_paying / max(1, paying_count))
    # Daha basit: aylık churn × N ay × current MRR
    expected_churn_mrr = int(current_mrr * churn_rate * months)

    # Risk altında MRR — sağlık skoru kötü olanlar
    at_risk = risk_at_mrr(db)
    # Risk altındaki kurumların belli bir oranı 90 gün içinde kaybedilir varsay
    # critical = %80 kayıp, risk = %30 kayıp (kabul edilen sektör ortalaması)
    expected_at_risk_loss = int(
        at_risk["critical_mrr"] * 0.8
        + at_risk["risk_mrr"] * 0.3
    )
    # horizon_days'a göre ölçekle (full effect = 90 gün varsay)
    expected_at_risk_loss = int(expected_at_risk_loss * min(1.0, horizon_days / 90.0))

    # Projeksiyon
    projected_status_quo = (
        current_mrr
        + expected_conversion_mrr
        - expected_churn_mrr
        - expected_at_risk_loss
    )

    # Müdahale: risk altı kayıpların %X'i kurtarılır
    saved_mrr = int(expected_at_risk_loss * intervention_save_rate)
    projected_intervention = projected_status_quo + saved_mrr

    return {
        "current_mrr": current_mrr,
        "horizon_days": horizon_days,
        "trial_conversion_rate": round(trial_conv, 3),
        "monthly_churn_rate": round(churn_rate, 3),
        "trial_ending_count": len(trial_ending),
        "expected_trial_conversions_mrr": expected_conversion_mrr,
        "expected_churn_mrr": expected_churn_mrr,
        "expected_at_risk_loss_mrr": expected_at_risk_loss,
        "projected_mrr_status_quo": max(0, projected_status_quo),
        "projected_mrr_with_intervention": max(0, projected_intervention),
        "delta_mrr": projected_intervention - projected_status_quo,
        "intervention_save_rate": intervention_save_rate,
        "at_risk_critical_count": at_risk["critical_count"],
        "at_risk_risk_count": at_risk["risk_count"],
    }


# ---------------------------- Senaryo karşılaştırma ----------------------------


def scenario_comparison(
    db: Session, *,
    save_rate: float = 0.5,
) -> dict:
    """30/60/90 gün için status quo vs müdahale et karşılaştırması.

    Args:
        save_rate: müdahale senaryosunda riskli MRR'in ne kadarı kurtarılır (0.0-1.0)
    """
    save_rate = max(0.0, min(1.0, save_rate))
    horizons = [30, 60, 90]
    out: list[dict] = []
    for h in horizons:
        proj = mrr_projection(db, horizon_days=h, intervention_save_rate=save_rate)
        out.append({
            "horizon_days": h,
            "status_quo_mrr": proj["projected_mrr_status_quo"],
            "intervention_mrr": proj["projected_mrr_with_intervention"],
            "delta_mrr": proj["delta_mrr"],
        })
    base = _current_mrr(db)
    return {
        "current_mrr": base,
        "save_rate": save_rate,
        "horizons": out,
    }


__all__ = [
    "AtRiskInstitution",
    "mrr_projection",
    "risk_at_mrr",
    "scenario_comparison",
]
