"""Sprint E.1 (Ticari Pano 2.0 — Faz E Seviye 2) — Toplu kampanya servisi.

Owner-aware: hedef kurum (Institution) + bağımsız öğretmen (User role=TEACHER,
institution_id=NULL) karışık olabilir.

Akış:
  1) preview_segment(segment) → eligible owner listesi (Institution VEYA User)
  2) create_campaign(...) → DRAFT
  3) launch_campaign(...) → DRAFT → RUNNING
     - Her recipient için bir Offer üretilir + sent
     - A/B varsa hash(owner_key)%2 ile A/B'ye düşer
  4) pause_campaign / resume_campaign / complete_campaign / cancel_campaign
  5) sync_recipient_statuses(...) → Offer'lardan recipient status'unu güncelle
  6) campaign_stats(...) → funnel istatistikleri (variant bazında)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import (
    Campaign,
    CampaignRecipient,
    CampaignSegment,
    CampaignStatus,
    Institution,
    Offer,
    OfferKind,
    OfferStatus,
    RecipientStatus,
    User,
    UserRole,
)
from app.services.offers import create_offer, send_offer
from app.services.revenue_owner import Owner, iter_owners


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _is_paid_plan(plan: str | None) -> bool:
    if not plan:
        return False
    try:
        from app.services.plans import PLAN_CATALOG
    except ImportError:
        return False
    info = PLAN_CATALOG.get(plan)
    if info is None:
        return False
    return (getattr(info, "price_monthly_try", 0) or 0) > 0


# ---------------------------- Segment çözümleme ----------------------------


def preview_segment(
    db: Session,
    *,
    segment: CampaignSegment,
    filter_plan: str | None = None,
    limit: int | None = None,
) -> list[Owner]:
    """Belirli bir segment için eligible owner'ları döndürür.

    Owner = Institution | bağımsız öğretmen User. PAUSED_30D segmenti yalnızca
    Institution için anlamlıdır (User'da subscription_pause_until yok).

    Args:
        limit: None ise tümü; aksi halde ilk N owner.
    """
    now = _now()
    all_owners = iter_owners(
        db, include_institutions=True,
        include_independent_teachers=True, active_only=True,
    )

    rows: list[Owner] = []

    if segment == CampaignSegment.FREE_PLAN:
        rows = [o for o in all_owners if not _is_paid_plan(o.plan)]

    elif segment == CampaignSegment.TRIAL_ENDING_7D:
        horizon = now + timedelta(days=7)
        rows = [
            o for o in all_owners
            if o.trial_ends_at is not None and now <= o.trial_ends_at <= horizon
        ]

    elif segment == CampaignSegment.PAUSED_30D:
        # Sadece kurum — User'da pause/subscription_kind alanı yok
        cutoff = now - timedelta(days=30)
        inst_owners = [o for o in all_owners if o.owner_type == "institution"]
        inst_objs = {
            i.id: i for i in db.query(Institution).filter(
                Institution.id.in_([o.owner_id for o in inst_owners]),
            ).all()
        }
        rows = []
        for o in inst_owners:
            inst = inst_objs.get(o.owner_id)
            if inst is None or inst.subscription_kind != "paused":
                continue
            pause_until = _aware(inst.subscription_pause_until)
            if pause_until is None or pause_until <= cutoff:
                rows.append(o)

    elif segment == CampaignSegment.CHAMPION:
        rows = _champion_owners(db, all_owners, now)

    elif segment == CampaignSegment.PAYING_AT_RISK:
        rows = _paying_at_risk_owners(db, all_owners)

    elif segment == CampaignSegment.NEVER_LOGGED_IN:
        rows = _never_logged_in_owners(db, all_owners)

    elif segment == CampaignSegment.CUSTOM_PLAN:
        if not filter_plan:
            return []
        rows = [o for o in all_owners if o.plan == filter_plan]

    else:
        rows = []

    rows.sort(key=lambda o: (o.owner_type, o.name.lower()))
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return rows


def _champion_owners(
    db: Session, all_owners: list[Owner], now: datetime,
) -> list[Owner]:
    """Ödeyen + 6+ ay aktif + sağlığı yüksek (level=healthy)."""
    # Sağlık skorları
    inst_health: dict[int, str] = {}
    user_health: dict[int, str] = {}
    try:
        from app.services.tenant_health import bulk_health_assessment
        inst_objs = (
            db.query(Institution)
            .filter(Institution.id.in_(
                [o.owner_id for o in all_owners if o.owner_type == "institution"]
            ))
            .all()
        )
        if inst_objs:
            assessments = bulk_health_assessment(
                db, institutions=inst_objs, today=now.date(),
            )
            inst_health = {
                a.institution.id: getattr(a, "level", None)
                for a in assessments
            }
    except Exception:
        logger.exception("champion: institution health fail")

    # Bağımsız öğretmen sağlığı health_v2 üzerinden
    try:
        from app.services.health_score_v2 import compute_health_score_v2_for_user
        for o in all_owners:
            if o.owner_type != "user":
                continue
            u = db.get(User, o.owner_id)
            if u is None:
                continue
            try:
                hs = compute_health_score_v2_for_user(db, u)
                user_health[o.owner_id] = hs.band
            except Exception:
                logger.exception("user health fail user=%s", o.owner_id)
    except ImportError:
        pass

    out: list[Owner] = []
    for o in all_owners:
        if not _is_paid_plan(o.plan):
            continue
        age_months = (now - o.created_at).days / 30.0
        if age_months < 6:
            continue
        if o.owner_type == "institution":
            level = inst_health.get(o.owner_id)
            if level == "healthy":
                out.append(o)
        else:
            band = user_health.get(o.owner_id)
            if band == "healthy":
                out.append(o)
    return out


def _paying_at_risk_owners(
    db: Session, all_owners: list[Owner],
) -> list[Owner]:
    """Ödeyen + sağlık skoru risk/critical."""
    inst_health: dict[int, str] = {}
    user_health: dict[int, str] = {}
    try:
        from app.services.tenant_health import bulk_health_assessment
        inst_objs = (
            db.query(Institution)
            .filter(Institution.id.in_(
                [o.owner_id for o in all_owners if o.owner_type == "institution"]
            ))
            .all()
        )
        if inst_objs:
            assessments = bulk_health_assessment(
                db, institutions=inst_objs, today=_now().date(),
            )
            inst_health = {
                a.institution.id: getattr(a, "level", None)
                for a in assessments
            }
    except Exception:
        logger.exception("paying_at_risk: institution health fail")

    try:
        from app.services.health_score_v2 import compute_health_score_v2_for_user
        for o in all_owners:
            if o.owner_type != "user":
                continue
            u = db.get(User, o.owner_id)
            if u is None:
                continue
            try:
                hs = compute_health_score_v2_for_user(db, u)
                user_health[o.owner_id] = hs.band
            except Exception:
                pass
    except ImportError:
        pass

    out: list[Owner] = []
    for o in all_owners:
        if not _is_paid_plan(o.plan):
            continue
        if o.owner_type == "institution":
            level = inst_health.get(o.owner_id)
            if level in ("risk", "critical"):
                out.append(o)
        else:
            band = user_health.get(o.owner_id)
            if band in ("risk", "critical"):
                out.append(o)
    return out


def _never_logged_in_owners(
    db: Session, all_owners: list[Owner],
) -> list[Owner]:
    """Kayıt olmuş ama hiç giriş yapmamış."""
    out: list[Owner] = []
    for o in all_owners:
        if o.owner_type == "institution":
            admins = (
                db.query(User)
                .filter(
                    User.institution_id == o.owner_id,
                    User.role == UserRole.INSTITUTION_ADMIN,
                    User.is_active.is_(True),
                )
                .all()
            )
            if not admins:
                continue
            if all(getattr(a, "last_login_at", None) is None for a in admins):
                out.append(o)
        else:
            u = db.get(User, o.owner_id)
            if u is None:
                continue
            if getattr(u, "last_login_at", None) is None:
                out.append(o)
    return out


# ---------------------------- CRUD ----------------------------


def create_campaign(
    db: Session, *,
    name: str,
    segment: str,
    variant_a_kind: str,
    variant_a_title: str,
    by_user_id: int,
    segment_filter_plan: str | None = None,
    description: str | None = None,
    admin_note: str | None = None,
    variant_a_value: float | None = None,
    variant_a_duration_months: int | None = None,
    variant_a_new_plan: str | None = None,
    variant_a_public_message: str | None = None,
    has_variant_b: bool = False,
    variant_b_kind: str | None = None,
    variant_b_title: str | None = None,
    variant_b_value: float | None = None,
    variant_b_duration_months: int | None = None,
    variant_b_new_plan: str | None = None,
    variant_b_public_message: str | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    offer_expires_in_days: int = 14,
    autocommit: bool = True,
) -> Campaign | None:
    """Yeni kampanya oluştur (DRAFT)."""
    try:
        seg = CampaignSegment(segment)
    except ValueError:
        return None
    try:
        OfferKind(variant_a_kind)
    except ValueError:
        return None
    if has_variant_b and variant_b_kind:
        try:
            OfferKind(variant_b_kind)
        except ValueError:
            return None
    if has_variant_b and not (variant_b_kind and variant_b_title):
        return None

    camp = Campaign(
        name=name.strip()[:255],
        description=description,
        admin_note=admin_note,
        segment=seg,
        segment_filter_plan=segment_filter_plan,
        status=CampaignStatus.DRAFT,
        variant_a_kind=variant_a_kind,
        variant_a_title=variant_a_title.strip()[:255],
        variant_a_value=variant_a_value,
        variant_a_duration_months=variant_a_duration_months,
        variant_a_new_plan=variant_a_new_plan,
        variant_a_public_message=variant_a_public_message,
        has_variant_b=has_variant_b,
        variant_b_kind=variant_b_kind if has_variant_b else None,
        variant_b_title=(variant_b_title.strip()[:255]
                         if has_variant_b and variant_b_title else None),
        variant_b_value=variant_b_value if has_variant_b else None,
        variant_b_duration_months=(variant_b_duration_months
                                   if has_variant_b else None),
        variant_b_new_plan=variant_b_new_plan if has_variant_b else None,
        variant_b_public_message=variant_b_public_message if has_variant_b else None,
        starts_at=starts_at,
        ends_at=ends_at,
        offer_expires_in_days=int(offer_expires_in_days),
        created_by_user_id=by_user_id,
    )
    db.add(camp)
    if autocommit:
        db.commit()
        db.refresh(camp)
    return camp


def _assign_variant(owner_type: str, owner_id: int, has_b: bool) -> str:
    """Deterministik A/B split.

    `owner_id % 2` kurum ve user için ayrı uzayda — paritesi aynı olsa bile
    çakışma yok çünkü A/B sadece bir kampanya içinde geçerli.
    """
    if not has_b:
        return "A"
    # Owner type'ı da hash'e dahil et → kurum ve user'lar düzgün dağılır
    seed = owner_id if owner_type == "institution" else (owner_id + 1)
    return "A" if (seed % 2 == 0) else "B"


def launch_campaign(
    db: Session, *,
    campaign_id: int,
    send_emails: bool = True,
    autocommit: bool = True,
) -> dict:
    """DRAFT → RUNNING. Her hedef owner için Offer üret + e-posta gönder."""
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}
    if camp.status != CampaignStatus.DRAFT:
        return {"ok": False, "error": "not_draft",
                "current_status": camp.status.value}

    eligible = preview_segment(
        db, segment=camp.segment, filter_plan=camp.segment_filter_plan,
    )
    if not eligible:
        camp.status = CampaignStatus.COMPLETED
        camp.started_at = _now()
        camp.completed_at = _now()
        if autocommit:
            db.commit()
        return {"ok": True, "recipient_count": 0, "sent": 0,
                "note": "no_eligible_recipients"}

    now = _now()
    camp.status = CampaignStatus.RUNNING
    camp.started_at = now

    sent_count = 0
    error_count = 0
    for owner in eligible:
        variant = _assign_variant(
            owner.owner_type, owner.owner_id, camp.has_variant_b,
        )
        if variant == "A":
            v_kind = camp.variant_a_kind
            v_title = camp.variant_a_title
            v_value = float(camp.variant_a_value) if camp.variant_a_value is not None else None
            v_dur = camp.variant_a_duration_months
            v_plan = camp.variant_a_new_plan
            v_msg = camp.variant_a_public_message
        else:
            v_kind = camp.variant_b_kind
            v_title = camp.variant_b_title
            v_value = float(camp.variant_b_value) if camp.variant_b_value is not None else None
            v_dur = camp.variant_b_duration_months
            v_plan = camp.variant_b_new_plan
            v_msg = camp.variant_b_public_message

        try:
            offer_kw = {}
            if owner.owner_type == "institution":
                offer_kw["institution_id"] = owner.owner_id
            else:
                offer_kw["user_id"] = owner.owner_id

            offer = create_offer(
                db,
                **offer_kw,
                kind=v_kind, title=v_title,
                by_user_id=camp.created_by_user_id or 0,
                value=v_value,
                duration_months=v_dur,
                new_plan=v_plan,
                public_message=v_msg,
                admin_note=f"[Campaign #{camp.id}] {camp.name}",
                expires_in_days=camp.offer_expires_in_days,
                autocommit=False,
            )
        except Exception:
            logger.exception("campaign offer create fail camp=%s %s=%s",
                              camp.id, owner.owner_type, owner.owner_id)
            offer = None

        recip_kw = {
            "campaign_id": camp.id,
            "owner_type": owner.owner_type,
            "variant": variant,
            "institution_id": owner.owner_id if owner.owner_type == "institution" else None,
            "user_id": owner.owner_id if owner.owner_type == "user" else None,
        }

        if offer is None:
            recip = CampaignRecipient(
                **recip_kw,
                offer_id=None,
                status=RecipientStatus.BOUNCED,
                error_note="offer_create_failed",
            )
            db.add(recip)
            error_count += 1
            continue

        db.flush()  # offer.id'yi al
        recip = CampaignRecipient(
            **recip_kw,
            offer_id=offer.id,
            status=RecipientStatus.TARGETED,
        )
        db.add(recip)

        if send_emails:
            try:
                send_result = send_offer(db, offer_id=offer.id, autocommit=False)
                if send_result.get("ok"):
                    recip.status = RecipientStatus.SENT
                    recip.sent_at = now
                    sent_count += 1
                else:
                    recip.status = RecipientStatus.BOUNCED
                    recip.error_note = send_result.get("error") or "send_failed"
                    error_count += 1
            except Exception:
                logger.exception("campaign offer send fail offer=%s", offer.id)
                recip.status = RecipientStatus.BOUNCED
                recip.error_note = "send_exception"
                error_count += 1

    if autocommit:
        db.commit()

    return {
        "ok": True,
        "campaign_id": camp.id,
        "recipient_count": len(eligible),
        "sent": sent_count,
        "errors": error_count,
        "started_at": now.isoformat(),
    }


def pause_campaign(
    db: Session, *, campaign_id: int, autocommit: bool = True,
) -> dict:
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}
    if camp.status != CampaignStatus.RUNNING:
        return {"ok": False, "error": "not_running",
                "current_status": camp.status.value}
    camp.status = CampaignStatus.PAUSED
    if autocommit:
        db.commit()
    return {"ok": True}


def resume_campaign(
    db: Session, *, campaign_id: int, autocommit: bool = True,
) -> dict:
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}
    if camp.status != CampaignStatus.PAUSED:
        return {"ok": False, "error": "not_paused",
                "current_status": camp.status.value}
    camp.status = CampaignStatus.RUNNING
    if autocommit:
        db.commit()
    return {"ok": True}


def complete_campaign(
    db: Session, *, campaign_id: int, autocommit: bool = True,
) -> dict:
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}
    if camp.status not in (CampaignStatus.RUNNING, CampaignStatus.PAUSED):
        return {"ok": False, "error": "not_active",
                "current_status": camp.status.value}
    camp.status = CampaignStatus.COMPLETED
    camp.completed_at = _now()
    if autocommit:
        db.commit()
    return {"ok": True}


def cancel_campaign(
    db: Session, *, campaign_id: int, autocommit: bool = True,
) -> dict:
    """Sadece DRAFT'tayken iptal et."""
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}
    if camp.status != CampaignStatus.DRAFT:
        return {"ok": False, "error": "not_draft",
                "current_status": camp.status.value}
    camp.status = CampaignStatus.CANCELLED
    if autocommit:
        db.commit()
    return {"ok": True}


def list_campaigns(
    db: Session, *, limit: int = 50,
) -> list[Campaign]:
    return (
        db.query(Campaign)
        .order_by(desc(Campaign.created_at))
        .limit(limit)
        .all()
    )


# ---------------------------- Sync + Stats ----------------------------


def sync_recipient_statuses(
    db: Session, *, campaign_id: int, autocommit: bool = True,
) -> dict:
    """Offer.status'a göre recipient.status'u güncelle (cron veya manuel)."""
    recips = (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.offer_id.isnot(None),
            CampaignRecipient.status.in_([
                RecipientStatus.SENT, RecipientStatus.TARGETED,
            ]),
        )
        .all()
    )
    updated = 0
    for r in recips:
        if r.offer_id is None:
            continue
        offer = db.get(Offer, r.offer_id)
        if offer is None:
            continue
        new_status: RecipientStatus | None = None
        if offer.status == OfferStatus.ACCEPTED:
            new_status = RecipientStatus.ACCEPTED
        elif offer.status == OfferStatus.DECLINED:
            new_status = RecipientStatus.DECLINED
        elif offer.status == OfferStatus.EXPIRED:
            new_status = RecipientStatus.EXPIRED
        if new_status and new_status != r.status:
            r.status = new_status
            r.responded_at = _aware(offer.responded_at) or _now()
            updated += 1
    if autocommit:
        db.commit()
    return {"ok": True, "updated_count": updated}


def campaign_stats(db: Session, *, campaign_id: int) -> dict:
    """Funnel istatistikleri — toplam + varyant bazında + owner tipi kırılımı."""
    camp = db.get(Campaign, campaign_id)
    if camp is None:
        return {"ok": False, "error": "not_found"}

    recips = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == campaign_id)
        .all()
    )

    def _counts(items: list[CampaignRecipient]) -> dict:
        out = {s.value: 0 for s in RecipientStatus}
        for r in items:
            out[r.status.value] = out.get(r.status.value, 0) + 1
        out["total"] = len(items)
        sent_eq = (
            out["sent"] + out["accepted"]
            + out["declined"] + out["expired"]
        )
        accepted = out["accepted"]
        out["sent_total"] = sent_eq
        out["accepted_pct"] = (
            round(100 * accepted / sent_eq) if sent_eq > 0 else None
        )
        return out

    overall = _counts(recips)
    variant_a = _counts([r for r in recips if r.variant == "A"])
    variant_b = _counts([r for r in recips if r.variant == "B"])

    inst_count = sum(1 for r in recips if r.owner_type == "institution")
    user_count = sum(1 for r in recips if r.owner_type == "user")

    return {
        "ok": True,
        "campaign_id": camp.id,
        "campaign_name": camp.name,
        "status": camp.status.value,
        "overall": overall,
        "variant_a": variant_a,
        "variant_b": variant_b if camp.has_variant_b else None,
        "has_variant_b": camp.has_variant_b,
        "institution_count": inst_count,
        "user_count": user_count,
    }


__all__ = [
    "campaign_stats",
    "cancel_campaign",
    "complete_campaign",
    "create_campaign",
    "launch_campaign",
    "list_campaigns",
    "pause_campaign",
    "preview_segment",
    "resume_campaign",
    "sync_recipient_statuses",
]
