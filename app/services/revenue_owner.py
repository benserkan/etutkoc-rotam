"""Sprint F.2 (Ticari Pano 2.0) — Owner-aware revenue abstraction.

Sistemde 2 tip "billing owner" var:
  1) Institution (kurum) — institution_id sahibi
  2) Bağımsız öğretmen — role=TEACHER + institution_id=NULL,
     plan/trial bilgisi User üzerinde

Bu servis ikisini tek bir `Owner` arayüzü altında birleştirir; revenue panel,
plan dağılımı, MRR, forecast vb. fonksiyonların hem kurumu hem bağımsız
öğretmeni saymasını sağlar.

Mevcut Institution-only kodu değiştirmiyoruz — yeni "owner_aware" varyantları
ekliyoruz. Tüketici (route/template) her ikisini de görüntüleyebilir.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import Institution, User, UserRole


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


def _plan_label(plan: str) -> str:
    info = _plan_catalog().get(plan)
    if info is None:
        return plan
    return str(getattr(info, "label", plan))


# ---------------------------- Owner dataclass ----------------------------


@dataclass
class Owner:
    owner_type: Literal["institution", "user"]
    owner_id: int
    name: str
    email: str | None
    plan: str
    is_active: bool
    created_at: datetime
    trial_ends_at: datetime | None
    monthly_price_try: int

    @property
    def url(self) -> str:
        """Detay sayfası URL'i."""
        if self.owner_type == "institution":
            return f"/admin/revenue/institutions/{self.owner_id}"
        return f"/admin/revenue/users/{self.owner_id}"

    @property
    def display_label(self) -> str:
        """UI'da gösterilecek kompakt etiket."""
        suffix = "kurum" if self.owner_type == "institution" else "bağımsız öğretmen"
        return f"{self.name} ({suffix})"


# ---------------------------- Owner enumeration ----------------------------


def iter_owners(
    db: Session, *,
    include_institutions: bool = True,
    include_independent_teachers: bool = True,
    active_only: bool = True,
) -> list[Owner]:
    """Tüm billing owner'ları döndür."""
    owners: list[Owner] = []
    now = _now()

    if include_institutions:
        q = db.query(Institution)
        if active_only:
            q = q.filter(Institution.is_active.is_(True))
        for inst in q.all():
            owners.append(Owner(
                owner_type="institution",
                owner_id=inst.id,
                name=inst.name,
                email=inst.contact_email,
                plan=inst.plan or "free",
                is_active=bool(inst.is_active),
                created_at=_aware(inst.created_at) or now,
                trial_ends_at=_aware(inst.trial_ends_at),
                monthly_price_try=_plan_price(inst.plan),
            ))

    if include_independent_teachers:
        q = (
            db.query(User)
            .filter(
                User.role == UserRole.TEACHER,
                User.institution_id.is_(None),
            )
        )
        if active_only:
            q = q.filter(User.is_active.is_(True))
        for u in q.all():
            owners.append(Owner(
                owner_type="user",
                owner_id=u.id,
                name=u.full_name or u.email,
                email=u.email,
                plan=u.plan or "free",
                is_active=bool(u.is_active),
                created_at=_aware(u.created_at) or now,
                trial_ends_at=_aware(u.trial_ends_at),
                monthly_price_try=_plan_price(u.plan),
            ))

    return owners


# ---------------------------- Aggregations ----------------------------


def _segment_flags(segment: str) -> tuple[bool, bool]:
    """'all' | 'institution' | 'user' → (include_institutions, include_users)."""
    if segment == "institution":
        return True, False
    if segment == "user":
        return False, True
    return True, True  # 'all' veya bilinmeyen → her ikisi


def plan_distribution_owner_aware(
    db: Session, *, segment: str = "all",
) -> list[dict]:
    """Plan kodu → aktif owner sayısı. segment ile kurum/bağımsız filtre."""
    inc_inst, inc_user = _segment_flags(segment)
    owners = iter_owners(
        db,
        include_institutions=inc_inst,
        include_independent_teachers=inc_user,
    )
    by_plan: dict[str, dict] = defaultdict(lambda: {
        "count": 0,
        "institution_count": 0,
        "user_count": 0,
        "monthly_price_try": 0,
        "estimated_mrr": 0,
    })
    for o in owners:
        bucket = by_plan[o.plan]
        bucket["count"] += 1
        if o.owner_type == "institution":
            bucket["institution_count"] += 1
        else:
            bucket["user_count"] += 1
        bucket["monthly_price_try"] = o.monthly_price_try
        bucket["estimated_mrr"] += o.monthly_price_try

    out: list[dict] = []
    for plan, data in by_plan.items():
        out.append({
            "plan": plan,
            "label": _plan_label(plan),
            **data,
        })
    out.sort(key=lambda r: (-r["estimated_mrr"], -r["count"]))
    return out


def mrr_owner_aware(db: Session, *, segment: str = "all") -> dict:
    """MRR — kurum + bağımsız öğretmen ayrı + toplam. segment ile filtre."""
    inc_inst, inc_user = _segment_flags(segment)
    owners = iter_owners(
        db,
        include_institutions=inc_inst,
        include_independent_teachers=inc_user,
    )
    inst_mrr = sum(o.monthly_price_try for o in owners if o.owner_type == "institution")
    user_mrr = sum(o.monthly_price_try for o in owners if o.owner_type == "user")
    inst_paying = sum(1 for o in owners
                       if o.owner_type == "institution" and o.monthly_price_try > 0)
    user_paying = sum(1 for o in owners
                       if o.owner_type == "user" and o.monthly_price_try > 0)
    total_owners = len(owners)
    inst_total = sum(1 for o in owners if o.owner_type == "institution")
    user_total = sum(1 for o in owners if o.owner_type == "user")
    total_mrr = inst_mrr + user_mrr
    total_paying = inst_paying + user_paying
    return {
        "total_try": total_mrr,
        "institution_mrr_try": inst_mrr,
        "user_mrr_try": user_mrr,
        "total_owners": total_owners,
        "institution_count": inst_total,
        "user_count": user_total,
        "paying_count": total_paying,
        "institution_paying_count": inst_paying,
        "user_paying_count": user_paying,
        "avg_per_paying": (
            round(total_mrr / total_paying, 2) if total_paying > 0 else 0
        ),
    }


def trial_ending_soon_owner_aware(
    db: Session, *, days_horizon: int = 7, segment: str = "all",
) -> list[Owner]:
    """Trial önümüzdeki N günde biten owner'lar. segment ile filtre."""
    now = _now()
    horizon = now + timedelta(days=days_horizon)
    inc_inst, inc_user = _segment_flags(segment)
    owners = iter_owners(
        db,
        include_institutions=inc_inst,
        include_independent_teachers=inc_user,
    )
    out: list[Owner] = []
    for o in owners:
        te = o.trial_ends_at
        if te is None:
            continue
        if now <= te <= horizon:
            out.append(o)
    out.sort(key=lambda o: o.trial_ends_at or now)
    return out


def get_owner(
    db: Session, *, owner_type: str, owner_id: int,
) -> Owner | None:
    """Tek bir owner'ı çek."""
    if owner_type == "institution":
        inst = db.get(Institution, owner_id)
        if inst is None:
            return None
        return Owner(
            owner_type="institution",
            owner_id=inst.id,
            name=inst.name,
            email=inst.contact_email,
            plan=inst.plan or "free",
            is_active=bool(inst.is_active),
            created_at=_aware(inst.created_at) or _now(),
            trial_ends_at=_aware(inst.trial_ends_at),
            monthly_price_try=_plan_price(inst.plan),
        )
    elif owner_type == "user":
        u = db.get(User, owner_id)
        if u is None or u.role != UserRole.TEACHER or u.institution_id is not None:
            return None
        return Owner(
            owner_type="user",
            owner_id=u.id,
            name=u.full_name or u.email,
            email=u.email,
            plan=u.plan or "free",
            is_active=bool(u.is_active),
            created_at=_aware(u.created_at) or _now(),
            trial_ends_at=_aware(u.trial_ends_at),
            monthly_price_try=_plan_price(u.plan),
        )
    return None


__all__ = [
    "Owner",
    "get_owner",
    "iter_owners",
    "mrr_owner_aware",
    "plan_distribution_owner_aware",
    "trial_ending_soon_owner_aware",
]
