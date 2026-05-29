"""Iyzico Checkout Form servisi (Ödeme Paket Ö1, sandbox-first).

Akış:
  1. `init_checkout(user, plan_code, cycle)`:
     - Fiyat pricing.py'dan hesaplanır (solo_pro/elite/unlimited).
     - PaymentTransaction satırı `pending` olarak yaratılır.
     - Iyzico CheckoutFormInitialize.create() çağrılır.
     - Iyzico `paymentPageUrl` döner → kullanıcı oraya yönlendirilir.
     - Iyzico'da kart girer, 3DS olur, ödenir.
  2. `verify_callback(token)`:
     - Iyzico 3DS sonrası bizim `payment_callback_url`'imize GET/POST yapar
       (form-data ile `token`).
     - `iyzipay.CheckoutForm.retrieve({token})` ile durum çekilir.
     - paymentStatus=SUCCESS → status=succeeded, change_plan tetiklenir.
     - paymentStatus=FAILURE → status=failed, hata mesajı status_reason'a.
     - Idempotent: aynı transaction zaten succeeded ise no-op.

Sandbox vs Prod: settings.iyzico_base_url + key/secret env'den okunur.
Sandbox URL = https://sandbox-api.iyzipay.com (varsayılan).
Prod URL = https://api.iyzipay.com.

Test kartları (sandbox): 5528790000000008 (success), 5406670000000009 (fail),
5526080000000006 (3DS başarısız) — Iyzico dokümantasyon kartları.

Hata kodları (frontend için):
  - payment_provider_unavailable: iyzipay SDK yok veya key eksik
  - payment_plan_invalid: bilinmeyen plan kodu
  - payment_amount_invalid: fiyat hesaplanamadı (özel teklif gerekli)
  - payment_cycle_invalid: cycle monthly|annual değil
  - payment_already_completed: transaction zaten succeeded
  - payment_not_found: token geçersiz
  - payment_3ds_failed: 3DS başarısız (Iyzico FAILURE döndü)
  - payment_card_rejected: kart reddedildi
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AuditAction,
    PROVIDER_IYZICO,
    STATUS_3DS_PENDING,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_SUCCEEDED,
    PaymentTransaction,
    User,
)
from app.services import audit as audit_service
from app.models import LINK_OWNER_INSTITUTION
from app.models.payment_link import PaymentLink
from app.models.plan_history import PlanChangeReason, PlanOwnerType
from app.services import plans as plans_service
from app.services import pricing as pricing_service
from app.services import payment_link_service

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Servis-seviye ödeme hatası — endpoint katmanı uygun HTTP'ye çevirir."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def is_provider_available() -> bool:
    """iyzipay SDK kurulu mu + key konfigüre mi?"""
    try:
        import iyzipay  # noqa: F401
    except ImportError:
        return False
    return bool(settings.iyzico_api_key and settings.iyzico_secret_key)


def _iyzico_options() -> dict[str, str]:
    """iyzipay SDK options. base_url 'https://' prefix'ini KABUL ETMEZ —
    HTTPSConnection doğrudan host bekliyor; biz config'de tam URL tutuyoruz."""
    base = settings.iyzico_base_url
    if base.startswith("https://"):
        base = base[len("https://"):]
    elif base.startswith("http://"):
        base = base[len("http://"):]
    base = base.rstrip("/")
    return {
        "api_key": settings.iyzico_api_key,
        "secret_key": settings.iyzico_secret_key,
        "base_url": base,
    }


# Mock-able SDK çağrı helper'ları — smoke testte monkeypatch'lenir.
def _iyzico_call_create(request: dict) -> dict:
    """Iyzico Checkout Form initialize çağrısı. Smoke'da mock'lanır."""
    import iyzipay  # type: ignore[import-not-found]
    result = iyzipay.CheckoutFormInitialize().create(request, _iyzico_options())
    return json.loads(result.read().decode("utf-8"))


def _iyzico_call_retrieve(token: str) -> dict:
    """Iyzico Checkout Form retrieve (durum sorgu). Smoke'da mock'lanır."""
    import iyzipay  # type: ignore[import-not-found]
    req = {"locale": "tr", "token": token}
    result = iyzipay.CheckoutForm().retrieve(req, _iyzico_options())
    return json.loads(result.read().decode("utf-8"))


def _compute_price(user: User, plan_code: str, cycle: str) -> Decimal:
    """Plan + döngüye göre tutar (₺). Yıllık = aylık × 10 (CLAUDE.md kuralı).

    Bağımsız koç planları sabit fiyat (solo_pro/elite/unlimited).
    Kurum planları için 'compute_institution_monthly' coach_count gerektirir;
    şimdilik kurum self-serve ödeme akışı KAPSAM DIŞI (manuel aktivasyon kalır).
    """
    if cycle not in ("monthly", "annual"):
        raise PaymentError("payment_cycle_invalid", "Geçersiz dönem (monthly|annual)")

    catalog = pricing_service.get_pricing_catalog()
    solo_tiers = catalog.get("solo", {}).get("tiers", [])
    tier = next((t for t in solo_tiers if t["code"] == plan_code), None)

    if tier is None:
        raise PaymentError(
            "payment_plan_invalid",
            "Bu plan self-serve ödemeye uygun değil. Kurum planları için iletişime geçin.",
            details={"plan_code": plan_code},
        )

    monthly = tier.get("monthly")
    if not monthly:
        raise PaymentError(
            "payment_amount_invalid",
            "Bu paket için fiyat tanımlı değil",
        )

    if cycle == "monthly":
        total = Decimal(str(monthly))
    else:  # annual = 10 ay peşin
        total = Decimal(str(pricing_service.annual_total(monthly)))

    return total


def init_checkout(
    db: Session, *,
    user: User,
    plan_code: str | None = None,
    cycle: str | None = None,
    payment_link: PaymentLink | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Iyzico Checkout Form başlat → paymentPageUrl + transaction_id döner.

    İki mod:
      - Self-serve (koç): plan_code + cycle verilir → pricing.py'dan fiyat
      - Link (kurum): payment_link verilir → fiyat/plan/cycle linkten

    Frontend `paymentPageUrl`'a yönlendirir. 3DS sonrası Iyzico bizim
    payment_callback_url'imize form-POST eder.
    """
    if not is_provider_available():
        raise PaymentError(
            "payment_provider_unavailable",
            "Ödeme sağlayıcı şu an kullanılamıyor (sandbox key tanımlı değil).",
        )

    if payment_link is not None:
        if not payment_link.is_usable:
            raise PaymentError(
                "payment_link_unusable",
                "Bu ödeme linki artık geçerli değil",
            )
        plan_code = payment_link.plan_code
        cycle = payment_link.cycle
        amount = payment_link.amount
    else:
        if not plan_code or not cycle:
            raise PaymentError(
                "payment_input_invalid",
                "plan_code + cycle zorunlu (self-serve akış)",
            )
        amount = _compute_price(user, plan_code, cycle)

    conversation_id = uuid.uuid4().hex  # bizim taraftan referans
    basket_id = f"PLAN-{plan_code}-{cycle}-{user.id}"

    # Transaction satırını ÖNCE yarat — Iyzico çağrısı başarısız olsa bile iz kalır
    tx = PaymentTransaction(
        user_id=user.id,
        provider=PROVIDER_IYZICO,
        provider_reference=conversation_id,
        amount=amount,
        currency="TRY",
        plan_code=plan_code,
        cycle=cycle,
        status=STATUS_PENDING,
        payment_link_id=payment_link.id if payment_link else None,
    )
    db.add(tx)
    db.flush()

    # Iyzico request body
    buyer_name = user.full_name or "Müşteri"
    parts = buyer_name.strip().split(maxsplit=1)
    first_name = parts[0] if parts else "Müşteri"
    last_name = parts[1] if len(parts) > 1 else "—"

    # Iyzico email format'i sandbox'ta bile sıkı kontrol ediyor (.local kabul
    # etmez). Geçersiz / dev formatı olanlarda generic fallback kullan.
    buyer_email = (user.email or "").strip()
    if (
        not buyer_email
        or "@" not in buyer_email
        or buyer_email.lower().endswith((".local", ".test", ".example"))
    ):
        buyer_email = "noreply@etutkoc.com"

    request = {
        "locale": "tr",
        "conversationId": conversation_id,
        "price": f"{amount:.2f}",
        "paidPrice": f"{amount:.2f}",
        "currency": "TRY",
        "basketId": basket_id,
        "paymentGroup": "PRODUCT",  # tek seferlik (Subscription değil)
        "callbackUrl": settings.payment_callback_url,
        "enabledInstallments": [1],  # sadece tek çekim
        "buyer": {
            "id": f"USER-{user.id}",
            "name": first_name,
            "surname": last_name,
            "gsmNumber": "+905350000000",  # zorunlu — kullanıcıdan alınmıyor, dummy
            "email": buyer_email,
            "identityNumber": "11111111111",  # zorunlu (TC) — dummy; KVKK için gerçek istenmez
            "registrationAddress": "Türkiye",
            "ip": ip_address or "85.34.78.112",
            "city": "Istanbul",
            "country": "Turkey",
        },
        "shippingAddress": {
            "contactName": buyer_name,
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Dijital hizmet — fiziksel adres yok",
        },
        "billingAddress": {
            "contactName": buyer_name,
            "city": "Istanbul",
            "country": "Turkey",
            "address": "Dijital hizmet — fiziksel adres yok",
        },
        "basketItems": [
            {
                "id": basket_id,
                "name": f"ETÜTKOÇ Rotam — {plan_code} ({cycle})",
                "category1": "Eğitim",
                "category2": "SaaS Abonelik",
                "itemType": "VIRTUAL",
                "price": f"{amount:.2f}",
            }
        ],
    }

    tx.raw_request = request

    # SDK çağrısı (smoke'da _iyzico_call_create monkeypatch'lenebilir)
    try:
        response_data = _iyzico_call_create(request)
    except Exception as exc:  # noqa: BLE001 — Iyzico'nun hata türleri çeşitli
        tx.status = STATUS_FAILED
        tx.status_reason = f"SDK error: {exc!s}"[:500]
        tx.raw_response = {"error": str(exc)}
        db.commit()
        logger.exception("Iyzico init_checkout SDK error")
        raise PaymentError(
            "payment_provider_unavailable",
            "Ödeme sağlayıcıya ulaşılamadı.",
            details={"error": str(exc)},
        ) from exc

    tx.raw_response = response_data

    if response_data.get("status") != "success":
        tx.status = STATUS_FAILED
        tx.status_reason = response_data.get("errorMessage", "Iyzico reddi")[:500]
        db.commit()
        raise PaymentError(
            "payment_provider_unavailable",
            tx.status_reason or "Ödeme başlatılamadı",
            details={"iyzico_code": response_data.get("errorCode")},
        )

    payment_page_url = response_data.get("paymentPageUrl")
    iyzico_token = response_data.get("token")

    if not payment_page_url or not iyzico_token:
        tx.status = STATUS_FAILED
        tx.status_reason = "Iyzico'dan paymentPageUrl/token alınamadı"
        db.commit()
        raise PaymentError(
            "payment_provider_unavailable",
            "Ödeme sayfası açılamadı.",
        )

    tx.status = STATUS_3DS_PENDING
    # provider_reference'i Iyzico'nun token'ına çevir — callback'te bize geri
    # dönen aynı string; conversationId bağımlılığı yok, direkt eşleşir.
    # Bizim conversationId raw_response'da kalır (debug için).
    tx.provider_reference = iyzico_token
    tx.raw_response = {**response_data, "_our_conversation_id": conversation_id}

    # Audit
    audit_service.log_action(
        db,
        action=AuditAction.PAYMENT_INITIATED,
        actor_id=user.id,
        target_type="payment_transaction",
        target_id=tx.id,
        details={
            "plan": plan_code, "cycle": cycle, "amount": str(amount),
            "ip": ip_address,
        },
        autocommit=False,
    )
    db.commit()

    return {
        "transaction_id": tx.id,
        "payment_page_url": payment_page_url,
        "iyzico_token": iyzico_token,
        "amount": float(amount),
        "currency": "TRY",
        "plan_code": plan_code,
        "cycle": cycle,
    }


def verify_callback(
    db: Session, *,
    iyzico_token: str,
    ip_address: str | None = None,
) -> PaymentTransaction:
    """Iyzico 3DS sonrası callback — token ile ödeme durumunu sorgular,
    PaymentTransaction'ı günceller. Başarılıysa plan'ı aktive eder.

    Idempotent: aynı token ile birden çok çağrı = ilk işleyen kazanır,
    sonrakiler no-op (zaten succeeded/failed olanı tekrar işlemez).
    """
    if not is_provider_available():
        raise PaymentError(
            "payment_provider_unavailable",
            "Ödeme sağlayıcı kullanılamıyor.",
        )

    if not iyzico_token:
        raise PaymentError("payment_not_found", "Geçersiz ödeme tokeni")

    # Transaction'ı önce token ile bul (provider_reference = Iyzico token)
    tx = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.provider_reference == iyzico_token)
        .order_by(PaymentTransaction.id.desc())
        .first()
    )

    if tx is None:
        raise PaymentError(
            "payment_not_found",
            "Ödeme kaydı bulunamadı (token uyuşmadı).",
            details={"token_prefix": iyzico_token[:16]},
        )

    # Iyzico'dan durumu çek (smoke'da _iyzico_call_retrieve monkeypatch)
    try:
        response_data = _iyzico_call_retrieve(iyzico_token)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Iyzico verify_callback SDK error")
        raise PaymentError(
            "payment_provider_unavailable",
            "Ödeme durumu doğrulanamadı.",
            details={"error": str(exc)},
        ) from exc

    # Idempotency — zaten sonuçlandıysa mevcut satırı döndür
    if tx.is_terminal:
        return tx

    iyzico_status = response_data.get("status")
    payment_status = response_data.get("paymentStatus")

    # Raw response güncelle (debug için)
    tx.raw_response = response_data

    if iyzico_status == "success" and payment_status == "SUCCESS":
        tx.status = STATUS_SUCCEEDED
        tx.status_reason = None
        tx.completed_at = datetime.utcnow()

        # Plan target'ı belirle: link varsa link'ten (kurum olabilir), yoksa user (self-serve)
        link: PaymentLink | None = None
        if tx.payment_link_id:
            link = db.get(PaymentLink, tx.payment_link_id)

        if link and link.target_owner_type == LINK_OWNER_INSTITUTION:
            target_owner_type = PlanOwnerType.INSTITUTION
            target_owner_id = link.target_owner_id
        else:
            target_owner_type = PlanOwnerType.USER
            target_owner_id = tx.user_id

        # Plan'ı aktive et — change_plan reuse (admin activate-plan ile aynı yol)
        try:
            plans_service.change_plan(
                db,
                owner_type=target_owner_type,
                owner_id=target_owner_id,
                new_plan=tx.plan_code,
                reason=PlanChangeReason.UPGRADE,
                actor_user_id=tx.user_id,
                note=f"Iyzico ödemesi #{tx.id} ({tx.cycle}, {tx.amount} TRY)",
                autocommit=False,
            )
        except Exception as exc:  # noqa: BLE001
            # Plan değişimi başarısız — para alındı ama hizmet açılmadı (kritik).
            tx.status_reason = f"PLAN_ACTIVATION_FAILED: {exc!s}"[:500]
            logger.exception("Payment succeeded but plan activation failed tx=%s", tx.id)

        # Abonelik durumu + dönem sonu — yalnız User akışında (institution'da
        # subscription_status alanları User'da, kurum kendi plan/sözleşme alanlarını
        # kullanır; change_plan yeterli)
        if target_owner_type == PlanOwnerType.USER:
            from app.models import User as UserModel
            owner = db.get(UserModel, target_owner_id)
            if owner is not None:
                owner.subscription_status = "active"
                # Sistem genelinde subscription_cycle 'academic_year' standartını
                # kullanır (manuel akış, process_renewals cron, frontend gösterim).
                # Iyzico'dan gelen 'annual' bu standarda normalize edilir.
                owner.subscription_cycle = (
                    "academic_year" if tx.cycle == "annual" else "monthly"
                )
                days = 365 if tx.cycle == "annual" else 30
                from datetime import timedelta
                owner.subscription_period_end = datetime.utcnow() + timedelta(days=days)

        # Link varsa consumed işaretle
        if link is not None:
            owner_user = db.get(User, tx.user_id)
            payment_link_service.mark_consumed(
                db, link=link, transaction=tx, consumer_user=owner_user,
                autocommit=False,
            )

        audit_service.log_action(
            db,
            action=AuditAction.PAYMENT_SUCCEEDED,
            actor_id=tx.user_id,
            target_type="payment_transaction",
            target_id=tx.id,
            details={
                "plan": tx.plan_code,
                "cycle": tx.cycle,
                "amount": str(tx.amount),
                "ip": ip_address,
            },
            autocommit=False,
        )
        db.commit()
    else:
        tx.status = STATUS_FAILED
        tx.status_reason = (
            response_data.get("errorMessage")
            or response_data.get("mdStatus")
            or "Ödeme başarısız"
        )[:500]
        tx.completed_at = datetime.utcnow()

        audit_service.log_action(
            db,
            action=AuditAction.PAYMENT_FAILED,
            actor_id=tx.user_id,
            target_type="payment_transaction",
            target_id=tx.id,
            details={"reason": tx.status_reason, "ip": ip_address},
            autocommit=False,
        )
        db.commit()

    return tx


def list_user_payments(
    db: Session, *, user_id: int, limit: int = 20,
) -> list[PaymentTransaction]:
    """Kullanıcının son ödemeleri — /teacher/plan geçmiş tablosu için."""
    return (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.user_id == user_id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
