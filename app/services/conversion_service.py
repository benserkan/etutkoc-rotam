"""Dönüşüm (conversion) servisi — landing hunisi + A/B varyant dönüşümü.

İki iş:
  1. Üye olunca ilişkilendirme kaydı: anonim landing oturumu (fc_telemetry_sid)
     + gördüğü A/B varyant → SignupAttribution.
  2. Süper admin dönüşüm panosu: ziyaretçi → kart etkileşimi → demo → üye →
     ücretli hunisi + varyant kırılımı.

Tüm metrikler agregat (KVKK: kişiyi tek tek ifşa etmez).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.models import FeatureCardEvent, SignupAttribution, User
from app.models.signup_attribution import SIGNUP_SOURCE_DIRECT, SIGNUP_SOURCE_LANDING
from app.services import plans
from app.services.telemetry import SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)

# Kart "etkileşimi" sayılan olaylar (impression = sadece DOM'a binme; etkileşim
# için görünme/tıklama).
_ENGAGE_EVENTS = ("view", "demo_click", "cta_click")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ attribution

def record_signup_attribution(
    db: Session,
    *,
    user: User,
    request: Request,
    signup_role: str | None = None,
) -> SignupAttribution | None:
    """Üyelik kaydında landing oturumunu + A/B varyantını ilişkilendir (best-effort).

    Hata akışı bloklamaz — None döner. Kullanıcı başına tek satır (idempotent).
    """
    try:
        existing = (
            db.query(SignupAttribution)
            .filter(SignupAttribution.user_id == user.id)
            .first()
        )
        if existing is not None:
            return existing

        sid = (request.cookies.get(SESSION_COOKIE_NAME) or "").strip() or None
        variant: str | None = None
        if sid:
            try:
                from app.services import experiments as exp

                active = exp.get_active_experiment(db)
                if active is not None:
                    vslug, _strategy = exp.assign_variant(active, sid)
                    variant = vslug or None
            except Exception:
                variant = None

        row = SignupAttribution(
            user_id=user.id,
            session_id=sid,
            variant_slug=variant,
            signup_role=signup_role,
            source=SIGNUP_SOURCE_LANDING if sid else SIGNUP_SOURCE_DIRECT,
        )
        db.add(row)
        db.commit()
        return row
    except Exception:
        logger.exception("record_signup_attribution fail user=%s", getattr(user, "id", None))
        try:
            db.rollback()
        except Exception:
            pass
        return None


# ------------------------------------------------------------------ funnel

def _is_paid_user(db: Session, user: User | None) -> bool:
    if user is None:
        return False
    try:
        return plans.is_paid_plan(plans.effective_plan_for_user(db, user))
    except Exception:
        return False


def _pct(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round(part / whole * 100, 1)


def compute_funnel(db: Session, *, days: int = 30) -> dict:
    """Landing dönüşüm hunisi + A/B varyant kırılımı (son N gün)."""
    days = max(1, min(days, 365))
    start = _now() - timedelta(days=days)

    # --- Landing oturum metrikleri (FeatureCardEvent) ---
    visitors = (
        db.query(func.count(distinct(FeatureCardEvent.session_id)))
        .filter(FeatureCardEvent.created_at >= start)
        .scalar()
    ) or 0
    engaged = (
        db.query(func.count(distinct(FeatureCardEvent.session_id)))
        .filter(
            FeatureCardEvent.created_at >= start,
            FeatureCardEvent.event_type.in_(_ENGAGE_EVENTS),
        )
        .scalar()
    ) or 0
    demo = (
        db.query(func.count(distinct(FeatureCardEvent.session_id)))
        .filter(
            FeatureCardEvent.created_at >= start,
            FeatureCardEvent.event_type == "demo_click",
        )
        .scalar()
    ) or 0
    # Tıklayan ziyaretçi: karta tıkladı (cta_click → signup) veya "Demo İzle" (demo_click)
    clicked = (
        db.query(func.count(distinct(FeatureCardEvent.session_id)))
        .filter(
            FeatureCardEvent.created_at >= start,
            FeatureCardEvent.event_type.in_(("cta_click", "demo_click")),
        )
        .scalar()
    ) or 0

    # --- Üyelikler (SignupAttribution) ---
    attrs = (
        db.query(SignupAttribution)
        .filter(SignupAttribution.created_at >= start)
        .all()
    )
    user_ids = [a.user_id for a in attrs]
    users = (
        {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}
        if user_ids
        else {}
    )

    signups_total = len(attrs)
    landing_attrs = [a for a in attrs if a.source == SIGNUP_SOURCE_LANDING]
    signups_landing = len(landing_attrs)
    signups_direct = signups_total - signups_landing

    paid_total = sum(1 for a in attrs if _is_paid_user(db, users.get(a.user_id)))
    paid_landing = sum(
        1 for a in landing_attrs if _is_paid_user(db, users.get(a.user_id))
    )

    funnel = {
        "visitors": int(visitors),
        "engaged": int(engaged),
        "clicked": int(clicked),
        "demo": int(demo),
        "signups_landing": signups_landing,
        "signups_direct": signups_direct,
        "signups_total": signups_total,
        "paid_total": paid_total,
        "paid_landing": paid_landing,
        # Oranlar (landing hunisi)
        "rate_visitor_engaged": _pct(int(engaged), int(visitors)),
        "rate_engaged_demo": _pct(int(demo), int(engaged)),
        "rate_visitor_signup": _pct(signups_landing, int(visitors)),
        "rate_signup_paid": _pct(paid_landing, signups_landing),
        "rate_visitor_paid": _pct(paid_landing, int(visitors)),
    }

    # --- A/B varyant kırılımı (doğrudan veriden — deney bitse bile görünür) ---
    variants: list[dict] = []
    experiment_name: str | None = None
    has_experiment = False
    try:
        from app.services import experiments as exp

        active = exp.get_active_experiment(db)
        if active is not None:
            has_experiment = True
            experiment_name = getattr(active, "name", None) or getattr(active, "slug", None)
    except Exception:
        logger.exception("conversion active experiment lookup fail")

    try:
        sess_rows = (
            db.query(
                FeatureCardEvent.variant_slug,
                func.count(distinct(FeatureCardEvent.session_id)),
            )
            .filter(
                FeatureCardEvent.created_at >= start,
                FeatureCardEvent.variant_slug.isnot(None),
            )
            .group_by(FeatureCardEvent.variant_slug)
            .all()
        )
        sess_by_variant = {v: int(n) for v, n in sess_rows}

        sign_by_variant: dict[str, int] = {}
        paid_by_variant: dict[str, int] = {}
        for a in attrs:
            if not a.variant_slug:
                continue
            sign_by_variant[a.variant_slug] = sign_by_variant.get(a.variant_slug, 0) + 1
            if _is_paid_user(db, users.get(a.user_id)):
                paid_by_variant[a.variant_slug] = paid_by_variant.get(a.variant_slug, 0) + 1

        slugs = sorted(set(sess_by_variant) | set(sign_by_variant))
        for s in slugs:
            sess = sess_by_variant.get(s, 0)
            sign = sign_by_variant.get(s, 0)
            paid = paid_by_variant.get(s, 0)
            variants.append({
                "slug": s,
                "sessions": sess,
                "signups": sign,
                "conversion_pct": _pct(sign, sess),
                "paid": paid,
                "paid_pct": _pct(paid, sign),
            })
    except Exception:
        logger.exception("conversion variant breakdown fail")

    return {
        "days": days,
        "funnel": funnel,
        "variants": variants,
        "has_experiment": has_experiment,
        "experiment_name": experiment_name,
    }
