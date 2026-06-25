"""Kampanya / genel link servisi — public markalı landing (grup paylaşımı).

Admin link oluşturur → token + public URL → WhatsApp grubuna paylaşır. Tıklayan
herkes markalı teklifi görür, ad+telefon bırakır → SalesProspect (lead, dedup) +
ContactRequest (source="campaign_link") → süper admin "İletişim Talepleri"nde
mevcut onboard akışıyla (Koç/Kurum Aç + Aktive Et) aktive eder.

Plan/tutar/kazanç/kopya membership ile AYNI kaynaktan (pricing/plans). Fark:
hedef yok + 1:çok lead toplama.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import CampaignLink, ContactRequest
from app.models.campaign_link import (
    CAMPAIGN_STATUS_ACTIVE, CAMPAIGN_STATUSES,
)
from app.models.contact_request import CONTACT_STATUS_NEW
from app.services import plans, pricing

_CYCLE_LABELS = {"monthly": "aylık", "annual": "akademik yıl (10 ay peşin)"}


class CampaignLinkError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _gen_token(db: Session) -> str:
    for _ in range(6):
        t = secrets.token_hex(16)
        if not db.query(CampaignLink.id).filter(CampaignLink.token == t).first():
            return t
    raise CampaignLinkError("token_error", "Token üretilemedi.")


def create_link(
    db: Session, *, admin_id: int | None, name: str, plan_code: str,
    cycle: str = "monthly", amount: int | None = None,
    title: str | None = None, message: str | None = None,
    audience: str | None = None, expires_in_days: int | None = None,
) -> CampaignLink:
    name = (name or "").strip()
    if len(name) < 2:
        raise CampaignLinkError("invalid_name", "Kampanya adı en az 2 karakter olmalı.")
    pi = plans.get_plan_info(plan_code)
    if pi is None:
        raise CampaignLinkError("invalid_plan", "Geçersiz plan.")
    if cycle not in ("monthly", "annual"):
        cycle = "monthly"
    # audience verilmezse plan tipinden türet (solo → koç, kurum planı → kurum)
    aud = audience if audience in ("coach", "institution") else (
        "coach" if pi.audience == "solo" else "institution")
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        if expires_in_days else None
    )
    link = CampaignLink(
        token=_gen_token(db), name=name, audience=aud,
        plan_code=plan_code, cycle=cycle, amount=amount,
        title=(title or "").strip() or None,
        message=(message or "").strip() or None,
        status=CAMPAIGN_STATUS_ACTIVE, created_by_admin_id=admin_id,
        expires_at=expires_at,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def list_links(db: Session, *, include_archived: bool = False) -> list[CampaignLink]:
    q = db.query(CampaignLink)
    if not include_archived:
        q = q.filter(CampaignLink.status != "archived")
    return q.order_by(CampaignLink.created_at.desc()).limit(200).all()


def get_by_token(db: Session, token: str) -> CampaignLink | None:
    return db.query(CampaignLink).filter(CampaignLink.token == token).first()


def get_by_id(db: Session, link_id: int) -> CampaignLink | None:
    return db.get(CampaignLink, link_id)


def set_status(db: Session, link: CampaignLink, status: str) -> CampaignLink:
    if status not in CAMPAIGN_STATUSES:
        raise CampaignLinkError("invalid_status", "Geçersiz durum.")
    link.status = status
    db.commit()
    db.refresh(link)
    return link


def _effective_status(link: CampaignLink) -> str:
    if link.status == CAMPAIGN_STATUS_ACTIVE and link.expires_at is not None:
        exp = link.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return "expired"
    return link.status


def _resolve_amount(link: CampaignLink) -> int | None:
    if link.amount is not None:
        return link.amount
    pi = plans.get_plan_info(link.plan_code)
    if pi is None:
        return None
    val = pi.price_yearly_try if link.cycle == "annual" else pi.price_monthly_try
    return val if val and val > 0 else None


def public_view(db: Session, link: CampaignLink, *, mark_viewed: bool = True) -> dict:
    status = _effective_status(link)
    if mark_viewed and status == "active":
        link.view_count = (link.view_count or 0) + 1
        db.commit()
    pi = plans.get_plan_info(link.plan_code)
    amount = _resolve_amount(link)
    list_price = None
    if pi is not None:
        lp = pi.price_yearly_try if link.cycle == "annual" else pi.price_monthly_try
        list_price = lp if lp and lp > 0 else None
    savings = discount_pct = None
    if list_price and amount is not None and amount < list_price:
        savings = list_price - amount
        discount_pct = round(savings * 100 / list_price)
    return {
        "valid": status == "active",
        "status": status,
        "audience": link.audience,
        "title": link.title,
        "message": link.message,
        "plan_code": link.plan_code,
        "plan_label": (pi.label if pi else link.plan_code),
        "plan_short": (pi.short_description if pi else None),
        "plan_features": pricing.features_for_plan(link.plan_code),
        "cycle": link.cycle,
        "cycle_label": _CYCLE_LABELS.get(link.cycle, link.cycle),
        "amount": amount,
        "list_price": list_price,
        "savings": savings,
        "discount_pct": discount_pct,
    }


def _lead_summary(link: CampaignLink) -> str:
    """ContactRequest mesajı — membership ile AYNI etiketler (onboard akışı çözer)."""
    pi = plans.get_plan_info(link.plan_code)
    amount = _resolve_amount(link)
    amount_str = f"{amount} TL" if amount else "size özel / belirtilmedi"
    parts = [
        f"Kampanya linki — {link.name}.",
        f"Plan: {pi.label if pi else link.plan_code} ({_CYCLE_LABELS.get(link.cycle, link.cycle)}).",
        f"Tutar: {amount_str}.",
        f"hedef_tip={'koc' if (pi and pi.audience == 'solo') else 'kurum'}",
        f"hedef_kod={link.plan_code}",
    ]
    if amount:
        parts.append(f"tutar={amount}")
    parts.append(f"kampanya_token={link.token}")
    return " ".join(parts)


def record_lead(
    db: Session, link: CampaignLink, *, name: str, phone: str,
    email: str | None = None, note: str | None = None,
) -> ContactRequest:
    """Ziyaretçi ad+telefon bıraktı → SalesProspect (lead, dedup) + ContactRequest.

    Lead, mevcut onboard akışına akar (İletişim Talepleri'nde Koç/Kurum Aç butonu).
    """
    if _effective_status(link) != "active":
        raise CampaignLinkError("not_active", "Bu kampanya artık geçerli değil.")
    name = (name or "").strip()
    if len(name) < 2:
        raise CampaignLinkError("invalid_name", "Lütfen adını gir.")

    from app.services import prospect_service
    from app.models import SalesProspect
    from app.models.sales_prospect import (
        PROSPECT_KIND_COACH, PROSPECT_KIND_INSTITUTION,
    )
    from app.services.phone_service import normalize_e164_tr

    norm = normalize_e164_tr(phone or "")
    if not norm:
        raise CampaignLinkError("invalid_phone", "Geçerli bir cep telefonu gir (5XX...).")

    kind = PROSPECT_KIND_INSTITUTION if link.audience == "institution" else PROSPECT_KIND_COACH
    prospect_id: int | None = None
    # Lead → prospect (dedup by phone). Var olan adayı yeniden yaratma.
    try:
        pr = prospect_service.create_prospect(
            db, actor_user_id=None, name=name, phone=norm, kind=kind,
            email=email, source="inbound", opt_in=True,
            note=f"Kampanya: {link.name}",
        )
        prospect_id = pr.id
    except prospect_service.ProspectError as exc:
        if exc.code == "duplicate_phone":
            existing = db.query(SalesProspect).filter_by(phone=norm).first()
            if existing is not None:
                prospect_id = existing.id
                existing.opt_in = True
        else:
            raise CampaignLinkError(exc.code, exc.message) from exc

    extra = "[KAMPANYA LİNKİ TALEBİ — manuel aktivasyon bekliyor]"
    if note and note.strip():
        extra += f" Not: {note.strip()[:200]}"
    summary = _lead_summary(link)
    if prospect_id:
        summary += f" aday_id={prospect_id}"
    cr = ContactRequest(
        name=name[:160],
        email=((email or "").strip()[:255] or "kampanya-lead@etutkoc.local"),
        phone=norm[:40],
        source="campaign_link",
        message=f"{summary} {extra}".strip(),
        status=CONTACT_STATUS_NEW,
    )
    db.add(cr)
    link.lead_count = (link.lead_count or 0) + 1
    db.commit()
    db.refresh(cr)
    return cr
