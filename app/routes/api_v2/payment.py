"""Ödeme endpoint'leri (Ödeme Paket Ö1) — Iyzico Checkout Form akışı.

4 endpoint:
  - GET  /payment/provider-status   → frontend "ödeme açık mı" check
  - POST /payment/init              → checkout başlat (auth: koç) → paymentPageUrl
  - POST /payment/iyzico/callback   → Iyzico 3DS sonrası form-POST eder (auth YOK,
                                       Iyzico'nun token'ı doğrulanır) → 303 redirect
  - GET  /payment/transactions/{id} → Next.js sonuç sayfası için durum (auth: sahibi)
  - GET  /payment/history           → kullanıcının son ödemeleri

Akış:
  1. Koç /teacher/plan'da paket seç → POST /payment/init → paymentPageUrl döner
  2. Frontend window.location.href = paymentPageUrl
  3. Iyzico'da kart girilir, 3DS olur, ödenir
  4. Iyzico bizim callback URL'imize form-POST eder (token ile)
  5. Backend verify + plan aktive + 303 redirect → /payment/result?tx={id}
  6. Frontend /payment/result sayfası GET /payment/transactions/{id} ile durumu çeker
  7. Başarılıysa "Plan aktif, panele dön" / başarısızsa "Tekrar dene"

Webhook (async event) Paket Ö1.5'e bırakıldı — one-time için callback yeterli.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings as app_settings
from app.database import get_db
from app.models import (
    LINK_OWNER_INSTITUTION,
    LINK_OWNER_USER,
    LINK_STATUS_LABELS_TR,
    STATUS_LABELS_TR,
    Institution,
    PaymentLink,
    PaymentTransaction,
    User,
    UserRole,
)
from app.routes.api_v2.dependencies import (
    _auth_error,
    get_current_user_v2,
)
from app.routes.api_v2.schemas.payment import (
    PaymentHistoryItem,
    PaymentHistoryResponse,
    PaymentInitBody,
    PaymentInitResponse,
    PaymentLinkCreateBody,
    PaymentLinkItem,
    PaymentLinkListResponse,
    PaymentLinkPublicInfo,
    PaymentProviderStatus,
    PaymentResultResponse,
)
from app.services import iyzico_service, payment_link_service
from app.services.pricing import get_pricing_catalog


def _payment_error(message: str, code: str, http_status: int) -> HTTPException:
    """Ödeme akışı için standart hata zarfı."""
    return HTTPException(
        status_code=http_status,
        detail={"error": "payment_error", "code": code, "message": message},
    )


router = APIRouter(prefix="/payment", tags=["payment"])


def _require_teacher_or_admin(user: User = Depends(get_current_user_v2)) -> User:
    """Ödeme akışına dahil olabilen roller: koç + kurum yöneticisi + süper admin.

    SUPER_ADMIN: test/destek için (örneğin onboarding sırasında kendi adına
    link akışı testi). /payment/history yine kendi user_id'sine filtreli kalır;
    süper admin başkasının geçmişini göremez (servis katmanı).
    """
    if user.role not in (UserRole.TEACHER, UserRole.INSTITUTION_ADMIN, UserRole.SUPER_ADMIN):
        raise _auth_error(
            "Ödeme yalnız öğretmen, kurum yöneticisi ve süper admin rolleri için açıktır",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/provider-status", response_model=PaymentProviderStatus)
def get_provider_status() -> PaymentProviderStatus:
    available = iyzico_service.is_provider_available()
    sandbox = "sandbox" in app_settings.iyzico_base_url
    return PaymentProviderStatus(available=available, sandbox=sandbox)


@router.post("/init", response_model=PaymentInitResponse)
def post_init_checkout(
    body: PaymentInitBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(_require_teacher_or_admin),
) -> PaymentInitResponse:
    """Iyzico Checkout Form başlat — paymentPageUrl döner.

    Frontend `window.location.href = response.payment_page_url` ile yönlendirir.
    """
    try:
        result = iyzico_service.init_checkout(
            db,
            user=user,
            plan_code=body.plan_code,
            cycle=body.cycle,
            ip_address=_client_ip(request),
        )
    except iyzico_service.PaymentError as exc:
        http_code = {
            "payment_provider_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
            "payment_plan_invalid": status.HTTP_400_BAD_REQUEST,
            "payment_amount_invalid": status.HTTP_400_BAD_REQUEST,
            "payment_cycle_invalid": status.HTTP_400_BAD_REQUEST,
        }.get(exc.code, status.HTTP_400_BAD_REQUEST)
        raise _payment_error(exc.message, exc.code, http_status=http_code) from exc

    return PaymentInitResponse(**result)


@router.post("/iyzico/callback")
async def post_iyzico_callback(
    request: Request,
    token: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Iyzico 3DS sonrası form-POST eder. Auth GEREKMEZ — Iyzico tarafından
    çağrılır, kullanıcı cookie'sini taşımaz. Güvenlik: token Iyzico'nun
    ürettiği imzalı string; verify_callback Iyzico'ya geri sorduğu için
    sahte token geçemez.

    Sonuç:
      - Başarılı/başarısız: 303 → {frontend}/payment/result?tx={id}
      - Token geçersiz/Iyzico erişim hatası: 303 → /payment/result?error=...
    """
    try:
        tx = iyzico_service.verify_callback(
            db,
            iyzico_token=token,
            ip_address=_client_ip(request),
        )
        redirect_url = f"{app_settings.app_base_url}/payment/result?tx={tx.id}"
    except iyzico_service.PaymentError as exc:
        redirect_url = (
            f"{app_settings.app_base_url}/payment/result?error={exc.code}"
        )

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/transactions/{tx_id}", response_model=PaymentResultResponse)
def get_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_require_teacher_or_admin),
) -> PaymentResultResponse:
    """Tek transaction'ı getir. Yalnız sahibi görebilir (cross-user 404)."""
    tx = db.get(PaymentTransaction, tx_id)
    if tx is None or tx.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Ödeme bulunamadı"},
        )
    return PaymentResultResponse(
        transaction_id=tx.id,
        status=tx.status,
        status_label=STATUS_LABELS_TR.get(tx.status, tx.status),
        status_reason=tx.status_reason,
        plan_code=tx.plan_code,
        cycle=tx.cycle,
        amount=float(tx.amount),
        currency=tx.currency,
        created_at=tx.created_at,
        completed_at=tx.completed_at,
    )


@router.get("/history", response_model=PaymentHistoryResponse)
def get_history(
    db: Session = Depends(get_db),
    user: User = Depends(_require_teacher_or_admin),
) -> PaymentHistoryResponse:
    items = iyzico_service.list_user_payments(db, user_id=user.id, limit=20)
    return PaymentHistoryResponse(
        items=[
            PaymentHistoryItem(
                id=tx.id,
                provider=tx.provider,
                plan_code=tx.plan_code,
                cycle=tx.cycle,
                amount=float(tx.amount),
                currency=tx.currency,
                status=tx.status,
                status_label=STATUS_LABELS_TR.get(tx.status, tx.status),
                created_at=tx.created_at,
                completed_at=tx.completed_at,
            )
            for tx in items
        ],
        total=len(items),
    )


# =============================================================================
# PAYMENT LINKS — süper admin oluşturur, kurum/koç linkten öder (Paket Ö2a)
# =============================================================================


_PLAN_LABELS_TR: dict[str, str] = {
    "solo_free": "Solo Ücretsiz",
    "solo_trial": "Solo Deneme",
    "solo_pro": "Solo Başlangıç",
    "solo_elite": "Solo",
    "solo_unlimited": "Solo Sınırsız",
    "institution_free": "Kurum Tanıma",
    "institution_trial": "Kurum Deneme",
    "etut_standart": "Etüt Standart",
    "dershane_pro": "Dershane Pro",
    "enterprise": "Özel Okul / Enterprise",
}

_CYCLE_LABELS_TR: dict[str, str] = {
    "monthly": "Aylık",
    "annual": "Yıllık (10 ay peşin)",
    "one_time": "Tek seferlik",
}


def _plan_label(code: str) -> str:
    return _PLAN_LABELS_TR.get(code, code)


def _cycle_label(code: str) -> str:
    return _CYCLE_LABELS_TR.get(code, code)


def _require_super_admin(user: User = Depends(get_current_user_v2)) -> User:
    if user.role != UserRole.SUPER_ADMIN:
        raise _auth_error(
            "Yalnız süper admin erişebilir",
            "role_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def _resolve_target_name(db: Session, owner_type: str, owner_id: int) -> str | None:
    if owner_type == LINK_OWNER_INSTITUTION:
        inst = db.get(Institution, owner_id)
        return inst.name if inst else None
    if owner_type == LINK_OWNER_USER:
        u = db.get(User, owner_id)
        return u.full_name if u else None
    return None


def _public_url_for(token: str) -> str:
    return f"{app_settings.app_base_url.rstrip('/')}/payment/link/{token}"


def _link_to_item(db: Session, link: PaymentLink) -> PaymentLinkItem:
    target_name = _resolve_target_name(db, link.target_owner_type, link.target_owner_id)
    consumer_name = None
    if link.consumed_by_user_id:
        u = db.get(User, link.consumed_by_user_id)
        consumer_name = u.full_name if u else None
    resolved = link.status_resolved
    return PaymentLinkItem(
        id=link.id,
        token=link.token,
        public_url=_public_url_for(link.token),
        target_owner_type=link.target_owner_type,
        target_owner_id=link.target_owner_id,
        target_owner_name=target_name,
        plan_code=link.plan_code,
        cycle=link.cycle,
        amount=float(link.amount),
        currency=link.currency,
        description=link.description,
        status=resolved,
        status_label=LINK_STATUS_LABELS_TR.get(resolved, resolved),
        expires_at=link.expires_at,
        consumed_at=link.consumed_at,
        consumed_by_user_id=link.consumed_by_user_id,
        consumed_by_user_name=consumer_name,
        consumed_transaction_id=link.consumed_transaction_id,
        created_by_admin_id=link.created_by_admin_id,
        created_at=link.created_at,
    )


@router.post("/admin/links", response_model=PaymentLinkItem)
def admin_create_link(
    body: PaymentLinkCreateBody,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_super_admin),
) -> PaymentLinkItem:
    try:
        link = payment_link_service.create_link(
            db,
            admin=admin,
            target_owner_type=body.target_owner_type,
            target_owner_id=body.target_owner_id,
            plan_code=body.plan_code,
            cycle=body.cycle,
            amount=body.amount,
            description=body.description,
            expires_in_days=body.expires_in_days,
        )
    except payment_link_service.PaymentLinkError as exc:
        raise _payment_error(exc.message, exc.code, status.HTTP_400_BAD_REQUEST) from exc
    return _link_to_item(db, link)


@router.get("/admin/links", response_model=PaymentLinkListResponse)
def admin_list_links(
    status_filter: str | None = None,
    target_owner_type: str | None = None,
    target_owner_id: int | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_super_admin),
) -> PaymentLinkListResponse:
    links = payment_link_service.list_links(
        db,
        status_filter=status_filter,
        target_owner_type=target_owner_type,
        target_owner_id=target_owner_id,
        limit=200,
    )
    items = [_link_to_item(db, link) for link in links]
    return PaymentLinkListResponse(items=items, total=len(items))


@router.post("/admin/links/{link_id}/cancel", response_model=PaymentLinkItem)
def admin_cancel_link(
    link_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(_require_super_admin),
) -> PaymentLinkItem:
    try:
        link = payment_link_service.cancel_link(db, admin=admin, link_id=link_id)
    except payment_link_service.PaymentLinkError as exc:
        http_code = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "link_not_found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise _payment_error(exc.message, exc.code, http_code) from exc
    return _link_to_item(db, link)


@router.get("/link/{token}", response_model=PaymentLinkPublicInfo)
def get_link_info(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> PaymentLinkPublicInfo:
    """Link bilgisi — kurum yöneticisi (veya süper admin) görür.

    Auth zorunlu (link bilgisi public DEĞİL — kurum adı/tutar sızmasın).
    Frontend proxy login yoksa zaten /login'e yönlendirir.
    """
    link = payment_link_service.get_by_token(db, token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Link bulunamadı"},
        )

    target_name = _resolve_target_name(
        db, link.target_owner_type, link.target_owner_id,
    ) or "—"

    can_pay = payment_link_service.can_user_pay_link(user, link)

    resolved_status = link.status_resolved
    return PaymentLinkPublicInfo(
        token=link.token,
        target_owner_type=link.target_owner_type,
        target_owner_name=target_name,
        plan_code=link.plan_code,
        plan_label=_plan_label(link.plan_code),
        cycle=link.cycle,
        cycle_label=_cycle_label(link.cycle),
        amount=float(link.amount),
        currency=link.currency,
        description=link.description,
        status=resolved_status,
        status_label=LINK_STATUS_LABELS_TR.get(resolved_status, resolved_status),
        expires_at=link.expires_at,
        is_usable=link.is_usable,
        can_pay=can_pay,
        requires_login=True,
        provider_available=iyzico_service.is_provider_available(),
    )


@router.post("/link/{token}/checkout", response_model=PaymentInitResponse)
def post_link_checkout(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_v2),
) -> PaymentInitResponse:
    """Linkten Iyzico checkout başlat.

    Yetki: süper admin VEYA link sahibi (kurum yön. veya hedef koç).
    """
    link = payment_link_service.get_by_token(db, token)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Link bulunamadı"},
        )

    if not link.is_usable:
        raise _payment_error(
            "Bu link artık geçerli değil",
            "payment_link_unusable",
            status.HTTP_400_BAD_REQUEST,
        )

    if not payment_link_service.can_user_pay_link(user, link):
        raise _auth_error(
            "Bu linki ödemeye yetkili değilsiniz",
            "link_payment_forbidden",
            http_status=status.HTTP_403_FORBIDDEN,
        )

    try:
        result = iyzico_service.init_checkout(
            db,
            user=user,
            payment_link=link,
            ip_address=_client_ip(request),
        )
    except iyzico_service.PaymentError as exc:
        http_code = {
            "payment_provider_unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
            "payment_link_unusable": status.HTTP_400_BAD_REQUEST,
        }.get(exc.code, status.HTTP_400_BAD_REQUEST)
        raise _payment_error(exc.message, exc.code, http_code) from exc

    return PaymentInitResponse(**result)
