"""WhatsApp üyelik teklifi servisi (Paket 1).

Süper admin teklif oluşturur → token + public link. Kullanıcı markalı sayfada
"Üye ol/Yenile" talebi bırakır VEYA havale/EFT ile ödediğini bildirir → her iki
durumda da bir ContactRequest (source="membership_offer") üretilir → süper admin
"İletişim Talepleri"nde görüp manuel aktive eder (mevcut activate-plan akışı).

İleride: Iyzico kart ödemesi + WhatsApp Cloud API (B fazı) bu servise eklenir;
public sayfa + akış değişmez.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import ContactRequest, MembershipOffer, User
from app.models.contact_request import CONTACT_STATUS_NEW
from app.services import app_settings, plans, pricing

# Havale/EFT bilgisi app_settings'te tutulur (süper admin doldurur).
_HAVALE_KEY = "membership_havale"

_TYPE_LABELS = {"new": "Yeni Üyelik", "renewal": "Üyelik Yenileme"}
_CYCLE_LABELS = {"monthly": "aylık", "annual": "akademik yıl (10 ay peşin)"}


class MembershipOfferError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _gen_token(db: Session) -> str:
    for _ in range(6):
        t = secrets.token_hex(16)  # 32 hex char
        if not db.query(MembershipOffer.id).filter(MembershipOffer.token == t).first():
            return t
    raise MembershipOfferError("token_error", "Token üretilemedi.")


def get_havale_info() -> dict:
    """Süper adminin tanımladığı havale/EFT bilgisi. Boşsa enabled=False."""
    raw = app_settings.get_json(_HAVALE_KEY, None) or {}
    iban = str(raw.get("iban") or "").strip()
    return {
        "enabled": bool(iban),
        "iban": iban,
        "name": str(raw.get("name") or "").strip(),
        "note": str(raw.get("note") or "").strip(),
    }


def set_havale_info(db: Session, *, iban: str, name: str, note: str, actor_user_id: int | None) -> dict:
    app_settings.set_json(
        db,
        _HAVALE_KEY,
        {"iban": iban.strip(), "name": name.strip(), "note": note.strip()},
        actor_user_id=actor_user_id,
    )
    return get_havale_info()


def create_offer(
    db: Session,
    *,
    admin: User,
    target_user_id: int | None,
    offer_type: str,
    plan_code: str,
    cycle: str,
    amount: int | None,
    title: str | None,
    message: str | None,
    expires_in_days: int | None = 30,
    target_prospect_id: int | None = None,
) -> MembershipOffer:
    if offer_type not in ("new", "renewal"):
        offer_type = "new"
    if cycle not in ("monthly", "annual"):
        cycle = "monthly"
    if plans.get_plan_info(plan_code) is None:
        raise MembershipOfferError("invalid_plan", "Geçersiz plan.")
    if target_user_id is not None:
        if db.get(User, target_user_id) is None:
            raise MembershipOfferError("target_not_found", "Hedef kullanıcı bulunamadı.")
    if target_prospect_id is not None:
        from app.models import SalesProspect
        if db.get(SalesProspect, target_prospect_id) is None:
            raise MembershipOfferError("target_not_found", "Hedef aday bulunamadı.")
    token = _gen_token(db)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        if expires_in_days
        else None
    )
    offer = MembershipOffer(
        token=token,
        created_by_admin_id=admin.id,
        target_user_id=target_user_id,
        target_prospect_id=target_prospect_id,
        offer_type=offer_type,
        plan_code=plan_code,
        cycle=cycle,
        amount=amount,
        title=(title or "").strip() or None,
        message=(message or "").strip() or None,
        status="active",
        expires_at=expires_at,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer


def get_by_token(db: Session, token: str) -> MembershipOffer | None:
    return (
        db.query(MembershipOffer)
        .filter(MembershipOffer.token == token)
        .first()
    )


def _resolve_amount(offer: MembershipOffer) -> int | None:
    if offer.amount is not None:
        return offer.amount
    pi = plans.get_plan_info(offer.plan_code)
    if pi is None:
        return None
    val = pi.price_yearly_try if offer.cycle == "annual" else pi.price_monthly_try
    return val if val and val > 0 else None


def _effective_status(offer: MembershipOffer) -> str:
    if offer.status == "active" and offer.expires_at is not None:
        now = datetime.now(timezone.utc)
        exp = offer.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return "expired"
    return offer.status


def public_view(db: Session, offer: MembershipOffer, *, mark_viewed: bool = True) -> dict:
    status = _effective_status(offer)
    if mark_viewed and offer.viewed_at is None and status == "active":
        offer.viewed_at = datetime.now(timezone.utc)
        db.commit()
    pi = plans.get_plan_info(offer.plan_code)
    amount = _resolve_amount(offer)
    # Liste fiyatı (indirimsiz plan) — kazanç hesabı için
    list_price = None
    if pi is not None:
        lp = pi.price_yearly_try if offer.cycle == "annual" else pi.price_monthly_try
        list_price = lp if lp and lp > 0 else None
    savings = None
    discount_pct = None
    if list_price and amount is not None and amount < list_price:
        savings = list_price - amount
        discount_pct = round(savings * 100 / list_price)
    target = offer.target_user
    target_name = target.full_name if target else None
    if target_name is None and offer.target_prospect_id:
        from app.models import SalesProspect
        pr = db.get(SalesProspect, offer.target_prospect_id)
        if pr:
            target_name = pr.name
    return {
        "valid": status in ("active", "accepted"),
        "status": status,
        "completion": offer.completion,
        "offer_type": offer.offer_type,
        "offer_type_label": _TYPE_LABELS.get(offer.offer_type, "Üyelik"),
        "title": offer.title,
        "message": offer.message,
        "target_name": target_name,
        "plan_code": offer.plan_code,
        "plan_label": (pi.label if pi else offer.plan_code),
        "plan_short": (pi.short_description if pi else None),
        # Tek kaynak: pazarlama-odaklı bullet'lar (pricing.features_for_plan).
        "plan_features": pricing.features_for_plan(offer.plan_code),
        "cycle": offer.cycle,
        "cycle_label": _CYCLE_LABELS.get(offer.cycle, offer.cycle),
        "amount": amount,
        # Kazanç: liste fiyatı (indirimsiz) vs teklif tutarı → çizik fiyat + tasarruf.
        "list_price": list_price,
        "savings": savings,
        "discount_pct": discount_pct,
        "havale": get_havale_info(),
    }


def _prospect_of(offer: MembershipOffer):
    if not offer.target_prospect_id:
        return None
    from app.database import SessionLocal
    from app.models import SalesProspect
    # offer'a bağlı session yoksa kısa session — caller genelde session'lı çağırır
    try:
        from sqlalchemy import inspect as _sa_inspect
        sess = _sa_inspect(offer).session
    except Exception:
        sess = None
    if sess is not None:
        return sess.get(SalesProspect, offer.target_prospect_id)
    with SessionLocal() as s:
        return s.get(SalesProspect, offer.target_prospect_id)


def _contact_identity(offer: MembershipOffer, name: str | None, email: str | None, phone: str | None):
    target = offer.target_user
    pr = _prospect_of(offer)
    return (
        (name or "").strip() or (target.full_name if target else None)
            or (pr.name if pr else None) or "WhatsApp Üyelik Teklifi",
        (email or "").strip() or (target.email if target else None)
            or (pr.email if (pr and pr.email) else None) or "whatsapp-offer@etutkoc.local",
        (phone or "").strip() or (target.phone if (target and target.phone) else None)
            or (pr.phone if (pr and pr.phone) else None),
    )


def _offer_summary(offer: MembershipOffer) -> str:
    pi = plans.get_plan_info(offer.plan_code)
    amount = _resolve_amount(offer)
    amount_str = f"{amount} TL" if amount else "size özel / belirtilmedi"
    parts = [
        f"WhatsApp üyelik teklifi — {_TYPE_LABELS.get(offer.offer_type, 'Üyelik')}.",
        f"Plan: {pi.label if pi else offer.plan_code} ({_CYCLE_LABELS.get(offer.cycle, offer.cycle)}).",
        f"Tutar: {amount_str}.",
    ]
    if offer.target_user_id:
        parts.append(f"koç_id={offer.target_user_id}")
    if offer.target_prospect_id:
        parts.append(f"aday_id={offer.target_prospect_id}")
    # Hedef tipi: solo plan → koç onboard, kurum planı → kurum onboard (dinamik buton)
    parts.append(f"hedef_tip={'koc' if (pi and pi.audience == 'solo') else 'kurum'}")
    parts.append(f"hedef_kod={offer.plan_code}")
    if amount:
        parts.append(f"tutar={amount}")
    parts.append(f"teklif_token={offer.token}")
    return " ".join(parts)


def _create_contact(
    db: Session, offer: MembershipOffer, *, name, email, phone, extra: str
) -> ContactRequest:
    nm, em, ph = _contact_identity(offer, name, email, phone)
    cr = ContactRequest(
        name=nm[:160],
        email=em[:255],
        phone=(ph[:40] if ph else None),
        source="membership_offer",
        message=f"{_offer_summary(offer)} {extra}".strip(),
        status=CONTACT_STATUS_NEW,
    )
    db.add(cr)
    db.flush()
    return cr


def record_request(
    db: Session, offer: MembershipOffer, *, name=None, email=None, phone=None
) -> MembershipOffer:
    """Kullanıcı "Üye ol/Yenile" talebi bıraktı → ContactRequest + manuel aktive bekler."""
    if _effective_status(offer) not in ("active", "accepted"):
        raise MembershipOfferError("not_active", "Bu teklif artık geçerli değil.")
    cr = _create_contact(db, offer, name=name, email=email, phone=phone,
                         extra="[ÜYELİK TALEBİ — manuel aktivasyon bekliyor]")
    offer.status = "accepted"
    offer.completion = "requested"
    offer.accepted_at = datetime.now(timezone.utc)
    offer.contact_request_id = cr.id
    db.commit()
    db.refresh(offer)
    return offer


def send_via_whatsapp(db: Session, offer: MembershipOffer) -> MembershipOffer:
    """K2 — Cloud API ile branded üyelik teklifi şablonunu prospect/koça GÖNDER.

    Manuel wa.me'den (Faz 1) AYRI: doğrudan onaylı `uyelik_teklifi` şablonu
    (görsel başlık + ad/plan/tutar + "Teklifi Gör" buton → /membership/{token}).
    Gönderim comm_log'a (whatsapp kanalı) yazılır; teslim/okundu webhook'tan gelir.
    """
    from app.config import settings
    from app.services import comm_log, whatsapp
    from app.models.communication_log import STATUS_SENT, STATUS_FAILED

    if _effective_status(offer) not in ("active", "accepted"):
        raise MembershipOfferError("not_active", "Bu teklif artık geçerli değil.")

    name, _email, phone = _contact_identity(offer, None, None, None)
    if not phone:
        raise MembershipOfferError("no_phone",
                                   "Hedefin telefon numarası yok — WhatsApp gönderilemez.")

    pi = plans.get_plan_info(offer.plan_code)
    plan_label = pi.label if pi else offer.plan_code
    amount = _resolve_amount(offer)
    amount_str = (f"{amount:,} ₺/{_CYCLE_LABELS.get(offer.cycle, offer.cycle)}".replace(",", ".")
                  if amount else "Size özel")

    components = [
        {"type": "header", "parameters": [
            {"type": "image", "image": {"link": settings.whatsapp_offer_image_url}}]},
        {"type": "body", "parameters": [
            {"type": "text", "text": name},
            {"type": "text", "text": plan_label},
            {"type": "text", "text": amount_str},
        ]},
    ]
    # Buton parametresi YALNIZ şablonun butonu dinamik URL (.../membership/{{1}})
    # ise gönderilir. Statik butonlu şablonda parametre yollamak → Meta #132018.
    if settings.whatsapp_offer_button_dynamic:
        components.append({
            "type": "button", "sub_type": "url", "index": "0",
            "parameters": [{"type": "text", "text": offer.token}],
        })

    res = whatsapp.send_template(
        to_phone=phone,
        template_name=settings.whatsapp_offer_template,
        components=components,
        language_code="tr",
    )

    if not res.success:
        comm_log.log_whatsapp(
            db=db, status=STATUS_FAILED, to_address=phone, to_user_id=offer.target_user_id,
            category="membership_offer", subject=f"{plan_label} teklifi",
            provider="whatsapp_cloud", error=res.error or "send_failed",
        )
        db.commit()
        raise MembershipOfferError("wa_send_failed",
                                   f"WhatsApp gönderilemedi: {res.error or 'bilinmeyen hata'}")

    now = datetime.now(timezone.utc)
    offer.wa_sent_at = now
    offer.wa_message_id = res.external_id
    comm_log.log_whatsapp(
        db=db, status=STATUS_SENT, to_address=phone, to_user_id=offer.target_user_id,
        category="membership_offer", subject=f"{plan_label} teklifi",
        provider="whatsapp_cloud", provider_message_id=res.external_id, sent_at=now,
    )
    # Aday'ı "iletişime geçildi" işaretle (varsa)
    pr = _prospect_of(offer)
    if pr is not None and pr.status == "new":
        pr.status = "contacted"
        pr.last_contacted_at = now
    db.commit()
    db.refresh(offer)
    return offer


def record_havale_claim(
    db: Session, offer: MembershipOffer, *, name=None, email=None, phone=None
) -> MembershipOffer:
    """Kullanıcı havale/EFT ile ödediğini bildirdi → ContactRequest (dekont kontrolü)."""
    if _effective_status(offer) not in ("active", "accepted"):
        raise MembershipOfferError("not_active", "Bu teklif artık geçerli değil.")
    cr = _create_contact(db, offer, name=name, email=email, phone=phone,
                         extra="[HAVALE/EFT İLE ÖDEDİĞİNİ BİLDİRDİ — dekont/havale kontrol et, sonra aktive et]")
    offer.status = "accepted"
    offer.completion = "havale_claimed"
    offer.accepted_at = datetime.now(timezone.utc)
    offer.contact_request_id = cr.id
    db.commit()
    db.refresh(offer)
    return offer
