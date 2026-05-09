"""Stage 9 (Faz 2.3) — Plan + Add-on UI route'ları.

Public:
- GET /pricing                → B2C (bireysel) + B2B (kurum) plan kartları

Auth (logged-in user):
- GET  /plans/me              → Mevcut plan + trial durumu + plan geçmişi
- GET  /addons                → Aktif add-on'lar + katalog
- POST /addons/{kind}/activate → Add-on aktive et
- POST /addons/{addon_id}/cancel → Add-on iptal

Plan değiştirme (yükseltme/alçaltma) bu Faz'da self-serve değil — kullanıcı
"İletişime geç" CTA'sıyla yönlendirilir; payment entegrasyonu ileride. Fakat
bu router add-on aktivasyonu için minimal bir self-serve akış sunuyor (ödeme
mock'lu — payment provider eklendiğinde bu fonksiyon güncellenecek).

Sahip belirleme: kullanıcı kurumlu ise Institution sahibi, bağımsız öğretmen
ise User sahibi. SUPER_ADMIN için /plans/me anlamsız — kendi kurumu yok;
admin kurum yönetimi /admin/institutions üzerinden yapılır.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import (
    ADDON_DESCRIPTIONS_TR,
    ADDON_LABELS_TR,
    ADDON_MONTHLY_PRICE_TRY,
    ADDON_MONTHLY_QUOTA,
    AddonKind,
    Institution,
    PlanOwnerType,
    User,
    UserRole,
)
from app.services.addons import (
    AddonOwner,
    activate_addon,
    cancel_addon,
    get_active_addons,
    is_addon_active,
    list_addon_history,
)
from app.services.plans import (
    INSTITUTION_PLANS,
    PLAN_CATALOG,
    SOLO_PLANS,
    get_plan_history,
    get_plan_info,
    is_solo_plan,
    is_trial_active,
    trial_days_left,
)
from app.templating import templates


router = APIRouter()


# ---------------------------- Yardımcılar ----------------------------


def _resolve_plan_owner(
    db: Session, user: User,
) -> tuple[User | Institution | None, AddonOwner | None]:
    """Kullanıcının ait olduğu plan sahibini ve add-on owner'ını döndür.

    - Kurumlu kullanıcı (institution_id IS NOT NULL) → Institution sahibi
    - Bağımsız öğretmen (TEACHER + institution_id IS NULL) → User sahibi
    - Diğer roller (super_admin, kurumlu olmayan student/parent) → (None, None)
      (Bu kullanıcılar için /plans/me anlamsız — yönlendir.)
    """
    if user.institution_id is not None:
        inst = db.get(Institution, user.institution_id)
        if inst is None:
            return None, None
        return inst, AddonOwner.for_institution(inst)
    if user.role == UserRole.TEACHER:
        return user, AddonOwner.for_user(user)
    return None, None


def _format_price(plan_code: str) -> str:
    """Plan fiyatını UI'ya uygun string'e çevir."""
    info = get_plan_info(plan_code)
    if info is None:
        return ""
    if info.price_monthly_try == 0:
        return "Ücretsiz"
    if info.price_monthly_try == -1:
        return "Görüşme"
    return f"₺{info.price_monthly_try:,}".replace(",", ".") + " /ay"


# ---------------------------- Public: /pricing ----------------------------


@router.get("/pricing")
def pricing_page(
    request: Request,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Public pricing page — B2C + B2B sekmeli plan kartları + kampanya banner'ları.

    Auth ZORUNLU DEĞİL. Logged-in kullanıcılar da görebilir; kendi planları
    'Mevcut planınız' rozetiyle vurgulanır.
    """
    # Plan kartları için katalog detayı
    solo_cards = [PLAN_CATALOG[code] for code in SOLO_PLANS]
    institution_cards = [PLAN_CATALOG[code] for code in INSTITUTION_PLANS]

    # Add-on katalog
    addon_catalog = [
        {
            "kind": kind.value,
            "label": ADDON_LABELS_TR[kind],
            "description": ADDON_DESCRIPTIONS_TR[kind],
            "price_try": ADDON_MONTHLY_PRICE_TRY[kind],
            "quota": ADDON_MONTHLY_QUOTA[kind],
        }
        for kind in (
            AddonKind.WHATSAPP_PARENT,
            AddonKind.AI_PLUS,
            AddonKind.PARENT_PORTAL,
        )
    ]

    # Kullanıcının mevcut planı (logged-in ise)
    current_plan_code: str | None = None
    if user is not None:
        owner, _ = _resolve_plan_owner(db, user)
        if owner is not None:
            current_plan_code = owner.plan

    return templates.TemplateResponse(
        "plans/pricing.html",
        {
            "request": request,
            "user": user,
            "solo_cards": solo_cards,
            "institution_cards": institution_cards,
            "addon_catalog": addon_catalog,
            "current_plan_code": current_plan_code,
            "format_price": _format_price,
        },
    )


# ---------------------------- Auth: /plans/me ----------------------------


@router.get("/plans/me")
def my_plan_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mevcut plan + trial durumu + plan değişim geçmişi."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == UserRole.SUPER_ADMIN:
        # Super admin'in kendi planı yok; admin paneline yönlendir
        return RedirectResponse(url="/admin", status_code=303)
    if user.role == UserRole.STUDENT or user.role == UserRole.PARENT:
        # Öğrenci/veli planı görmez — öğretmen/kurum planı yönetir
        return RedirectResponse(url="/", status_code=303)

    owner, addon_owner = _resolve_plan_owner(db, user)
    if owner is None:
        # Anormal — nereye? Login.
        return RedirectResponse(url="/login", status_code=303)

    plan_code = owner.plan
    plan_info = get_plan_info(plan_code)

    # Trial durumu
    trial_active = is_trial_active(owner)
    trial_days = trial_days_left(owner=owner) if trial_active else None

    # Plan geçmişi
    if isinstance(owner, Institution):
        owner_type = PlanOwnerType.INSTITUTION
    else:
        owner_type = PlanOwnerType.USER
    history = get_plan_history(
        db, owner_type=owner_type, owner_id=owner.id, limit=20,
    )

    # Aktif add-on'lar
    active_addons = (
        get_active_addons(db, owner=addon_owner) if addon_owner else []
    )

    # Yükseltme adayları (mevcut tier'dan yüksek olanlar)
    upgrade_candidates = []
    if plan_info:
        family = SOLO_PLANS if is_solo_plan(plan_code) else INSTITUTION_PLANS
        for code in family:
            cand = PLAN_CATALOG[code]
            if cand.tier_rank > plan_info.tier_rank:
                upgrade_candidates.append(cand)

    return templates.TemplateResponse(
        "plans/my_plan.html",
        {
            "request": request,
            "user": user,
            "owner": owner,
            "is_institution_owner": isinstance(owner, Institution),
            "plan_info": plan_info,
            "plan_code": plan_code,
            "trial_active": trial_active,
            "trial_days_left": trial_days,
            "history": history,
            "active_addons": active_addons,
            "upgrade_candidates": upgrade_candidates,
            "addon_labels": ADDON_LABELS_TR,
            "format_price": _format_price,
        },
    )


# ---------------------------- Auth: /addons ----------------------------


@router.get("/addons")
def addons_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add-on katalog + aktif olanlar + iptal butonları."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role in (UserRole.STUDENT, UserRole.PARENT):
        return RedirectResponse(url="/", status_code=303)

    owner, addon_owner = _resolve_plan_owner(db, user)
    if owner is None or addon_owner is None:
        return RedirectResponse(url="/", status_code=303)

    actives = get_active_addons(db, owner=addon_owner)
    history = list_addon_history(db, owner=addon_owner, limit=30)
    active_kinds = {a.addon_kind for a in actives}

    catalog = []
    for kind in (
        AddonKind.WHATSAPP_PARENT,
        AddonKind.AI_PLUS,
        AddonKind.PARENT_PORTAL,
    ):
        catalog.append({
            "kind": kind,
            "kind_value": kind.value,
            "label": ADDON_LABELS_TR[kind],
            "description": ADDON_DESCRIPTIONS_TR[kind],
            "price_try": ADDON_MONTHLY_PRICE_TRY[kind],
            "quota": ADDON_MONTHLY_QUOTA[kind],
            "is_active": kind in active_kinds,
        })

    return templates.TemplateResponse(
        "plans/addons.html",
        {
            "request": request,
            "user": user,
            "owner": owner,
            "is_institution_owner": isinstance(owner, Institution),
            "catalog": catalog,
            "active_addons": actives,
            "history": history,
            "addon_labels": ADDON_LABELS_TR,
        },
    )


@router.post("/addons/{kind_value}/activate")
def activate_addon_action(
    kind_value: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add-on aktive et — ödeme entegrasyonu eklenene kadar mock akış.

    İlerideki adım: önce `/checkout/{kind}` route'una yönlendirip ödeme alındıktan
    sonra `activate_addon` çağrılacak. Şimdilik free tier için doğrudan aktivasyon.
    """
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role in (UserRole.STUDENT, UserRole.PARENT, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    try:
        kind = AddonKind(kind_value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Bilinmeyen add-on")

    owner, addon_owner = _resolve_plan_owner(db, user)
    if owner is None or addon_owner is None:
        raise HTTPException(status_code=400, detail="Plan sahibi bulunamadı")

    # Yetki: kurumlu öğretmen kurum adına add-on aktive edemez — sadece kurum admini
    if isinstance(owner, Institution) and user.role != UserRole.INSTITUTION_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Kurum ek paketi yalnızca kurum yöneticisi tarafından aktive edilebilir",
        )

    activate_addon(
        db, owner=addon_owner, addon_kind=kind,
        actor_user_id=user.id,
        note="UI üzerinden self-serve aktivasyon",
    )

    return RedirectResponse(url="/addons?activated=1", status_code=303)


@router.post("/addons/{addon_id}/cancel")
def cancel_addon_action(
    addon_id: int,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add-on iptal et — period sonuna kadar geçerli kalır."""
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role in (UserRole.STUDENT, UserRole.PARENT, UserRole.SUPER_ADMIN):
        raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz yok")

    from app.models import Addon
    addon = db.get(Addon, addon_id)
    if addon is None:
        raise HTTPException(status_code=404)

    # Yetki: sadece kendi sahibinin add-on'unu iptal edebilir
    owner, addon_owner = _resolve_plan_owner(db, user)
    if (
        addon_owner is None
        or addon.owner_type != addon_owner.type
        or addon.owner_id != addon_owner.id
    ):
        raise HTTPException(status_code=403, detail="Bu ek paket sizin değil")
    if isinstance(owner, Institution) and user.role != UserRole.INSTITUTION_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Kurum ek paketi yalnızca kurum yöneticisi tarafından iptal edilebilir",
        )

    cancel_addon(db, addon_id=addon_id, by_user_id=user.id)

    return RedirectResponse(url="/addons?cancelled=1", status_code=303)
