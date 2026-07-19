"""Apple IAP entitlement köprüsü — RevenueCat webhook + REST sync.

App Store 3.1.1 çözümü (2026-07-19): solo koç abonelikleri iOS'ta Apple'ın
otomatik yenilenen aboneliği (StoreKit) olarak satılır; RevenueCat makbuz
doğrulama + olay (webhook) katmanıdır. Bu servis RevenueCat olaylarını
sistemin mevcut plan/abonelik modeline çevirir:

- INITIAL_PURCHASE / RENEWAL / UNCANCELLATION / PRODUCT_CHANGE →
  `change_plan` (UPGRADE) + subscription_status='active' +
  subscription_period_end=Apple bitiş tarihi + subscription_platform='app_store'
- CANCELLATION (otomatik yenileme kapatıldı) → status='canceled'
  (erişim dönem sonuna kadar sürer — iyzico iptal semantiğiyle aynı)
- EXPIRATION → solo_free'ye düş + abonelik alanları temizlenir
- BILLING_ISSUE → yalnız log (Apple kendi yeniden-deneme/grace süresini işletir;
  gerçekten biterse EXPIRATION gelir)

Kimlik eşleme: mobil uygulama RevenueCat'i `appUserID=str(user.id)` ile
yapılandırır → webhook'taki app_user_id doğrudan bizim User.id'mizdir.

GÜVENLİK: webhook plan aktive ettiği için Authorization secret'i ZORUNLUDUR
(boş/eşleşmeyen → 403; zeptomail'in "boşsa kabul" deseni burada BİLİNÇLİ
uygulanmaz). Kanal koruması: iyzico'dan satın almış kullanıcıyı App Store
EXPIRATION olayı düşüremez (subscription_platform kontrolü).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PlanChangeReason, PlanOwnerType, User, UserRole

logger = logging.getLogger(__name__)


PLATFORM_APP_STORE = "app_store"
PLATFORM_IYZICO = "iyzico"
PLATFORM_MANUAL = "manual"


# App Store Connect ürün kimliği → (plan_code, cycle).
# Yıllık ürünler henüz ASC'de tanımlı değil; tanımlanırsa deploy'suz çalışır
# (cycle 'academic_year' = sistem standardı, Apple 1 yıl yeniler).
PRODUCT_PLANS: dict[str, tuple[str, str]] = {
    "rotam_solo_pro_monthly": ("solo_pro", "monthly"),
    "rotam_solo_elite_monthly": ("solo_elite", "monthly"),
    "rotam_solo_unlimited_monthly": ("solo_unlimited", "monthly"),
    "rotam_solo_pro_yearly": ("solo_pro", "academic_year"),
    "rotam_solo_elite_yearly": ("solo_elite", "academic_year"),
    "rotam_solo_unlimited_yearly": ("solo_unlimited", "academic_year"),
}

# RevenueCat olay türleri → aboneliği aktifleştirir
_ACTIVE_EVENT_TYPES = {
    "INITIAL_PURCHASE",
    "RENEWAL",
    "UNCANCELLATION",
    "PRODUCT_CHANGE",
    "SUBSCRIPTION_EXTENDED",
}


class IapError(Exception):
    """IAP akışı hatası (yapılandırma / RevenueCat API / doğrulama)."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def is_configured() -> bool:
    """RevenueCat REST sync kullanılabilir mi (secret key girildi mi)."""
    return bool(settings.revenuecat_secret_key)


def plan_for_product(product_id: str | None) -> tuple[str, str] | None:
    """Ürün kimliği → (plan_code, cycle). Bilinmeyen ürün → None.

    Google Play tarafında RevenueCat product_id'yi 'urun:base_plan' biçiminde
    gönderebilir — iki taraf da çalışsın diye ':' öncesi de denenir.
    """
    if not product_id:
        return None
    hit = PRODUCT_PLANS.get(product_id)
    if hit is None and ":" in product_id:
        hit = PRODUCT_PLANS.get(product_id.split(":", 1)[0])
    return hit


def _resolve_user(db: Session, event: dict) -> User | None:
    """Webhook olayındaki app_user_id / alias'lardan User çöz (int id bekler)."""
    candidates: list[str] = []
    for key in ("app_user_id", "original_app_user_id"):
        v = event.get(key)
        if isinstance(v, str):
            candidates.append(v)
    aliases = event.get("aliases")
    if isinstance(aliases, list):
        candidates.extend(a for a in aliases if isinstance(a, str))
    for c in candidates:
        c = c.strip()
        if not c or c.startswith("$RCAnonymousID"):
            continue
        try:
            uid = int(c)
        except ValueError:
            continue
        user = db.get(User, uid)
        if user is not None:
            return user
    return None


def _parse_ms(value) -> datetime | None:
    """Epoch milisaniye → aware datetime (RevenueCat *_at_ms alanları)."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def _parse_iso(value) -> datetime | None:
    """RevenueCat REST ISO tarihi ('...Z') → aware datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def apply_active_subscription(
    db: Session, *, user: User, plan_code: str, cycle: str,
    expires_at: datetime | None, note: str,
    status: str = "active", autocommit: bool = False,
) -> bool:
    """App Store aboneliğini kullanıcıya uygula (change_plan + abonelik alanları).

    Yalnız bağımsız koça uygulanır (kurum üyesi / diğer roller → False + log).
    Ödeme duvarında pasifleştirilmiş öğrenciler aktivasyonla geri açılır
    (iyzico/admin akışıyla aynı kural).
    """
    from app.services.plans import (
        change_plan, is_paid_plan, reactivate_solo_students,
    )

    if user.role != UserRole.TEACHER or user.institution_id is not None:
        logger.warning(
            "iap apply skipped: user=%s solo koç değil (role=%s inst=%s)",
            user.id, user.role, user.institution_id,
        )
        return False

    was_paid_active = (
        is_paid_plan(user.plan or "") and user.subscription_status == "active"
    )
    change_plan(
        db, owner_type=PlanOwnerType.USER, owner_id=user.id, new_plan=plan_code,
        reason=PlanChangeReason.UPGRADE, actor_user_id=user.id,
        note=note, autocommit=False,
    )
    user.subscription_status = status
    user.subscription_cycle = cycle
    user.subscription_period_end = (
        expires_at or datetime.now(timezone.utc) + timedelta(days=30)
    )
    user.subscription_platform = PLATFORM_APP_STORE
    user.trial_ends_at = None
    if not was_paid_active:
        reactivate_solo_students(db, user, autocommit=False)
    if autocommit:
        db.commit()
    return True


def _expire_app_store_subscription(db: Session, user: User, *, note: str) -> None:
    """App Store aboneliği bitti → solo_free + abonelik alanlarını temizle."""
    from app.services.plans import SOLO_FREE, change_plan

    change_plan(
        db, owner_type=PlanOwnerType.USER, owner_id=user.id, new_plan=SOLO_FREE,
        reason=PlanChangeReason.DOWNGRADE, note=note, autocommit=False,
    )
    user.subscription_status = None
    user.subscription_period_end = None
    user.subscription_cycle = None
    user.subscription_platform = None


def handle_webhook_event(db: Session, payload: dict) -> dict:
    """RevenueCat webhook gövdesini işle. Dönüş: {action, user_id?} özeti.

    Bilinmeyen kullanıcı/ürün 200 ile yutulur (RevenueCat sonsuz retry
    yapmasın) ama log'lanır.
    """
    event = payload.get("event") if isinstance(payload.get("event"), dict) else payload
    etype = str(event.get("type") or "").upper()

    if etype == "TEST":
        return {"action": "test"}

    user = _resolve_user(db, event)
    if user is None:
        logger.warning(
            "revenuecat webhook: kullanıcı çözülemedi app_user_id=%s type=%s",
            event.get("app_user_id"), etype,
        )
        return {"action": "user_not_found"}

    product_id = event.get("new_product_id") or event.get("product_id")
    environment = str(event.get("environment") or "")
    expires_at = _parse_ms(event.get("expiration_at_ms"))

    if etype in _ACTIVE_EVENT_TYPES:
        mapping = plan_for_product(product_id)
        if mapping is None:
            logger.warning(
                "revenuecat webhook: bilinmeyen ürün %s (user=%s type=%s)",
                product_id, user.id, etype,
            )
            return {"action": "unknown_product", "user_id": user.id}
        plan_code, cycle = mapping
        applied = apply_active_subscription(
            db, user=user, plan_code=plan_code, cycle=cycle,
            expires_at=expires_at,
            note=f"App Store IAP ({etype} · {product_id}"
                 + (f" · {environment}" if environment else "") + ")",
            autocommit=False,
        )
        db.commit()
        return {
            "action": "activated" if applied else "skipped_not_solo",
            "user_id": user.id,
        }

    if etype == "CANCELLATION":
        # Otomatik yenileme kapatıldı — erişim dönem sonuna kadar sürer.
        if (
            user.subscription_platform == PLATFORM_APP_STORE
            and user.subscription_status == "active"
        ):
            user.subscription_status = "canceled"
            db.commit()
            return {"action": "canceled", "user_id": user.id}
        return {"action": "cancellation_ignored", "user_id": user.id}

    if etype == "EXPIRATION":
        # Kanal koruması: iyzico/manuel aboneliği App Store olayı düşüremez.
        if user.subscription_platform == PLATFORM_APP_STORE:
            _expire_app_store_subscription(
                db, user, note="App Store aboneliği sona erdi (EXPIRATION)",
            )
            db.commit()
            return {"action": "expired", "user_id": user.id}
        return {"action": "expiration_ignored", "user_id": user.id}

    if etype == "BILLING_ISSUE":
        logger.info("revenuecat billing issue user=%s (Apple grace/retry sürecinde)", user.id)
        return {"action": "billing_issue_logged", "user_id": user.id}

    logger.info("revenuecat webhook: işlenmeyen olay türü %s user=%s", etype, user.id)
    return {"action": "ignored", "user_id": user.id}


# ---------------------------- REST sync (fallback) ----------------------------


def _rc_get_subscriber(app_user_id: str) -> dict:
    """RevenueCat REST — subscriber durumu. Testlerde monkeypatch edilir."""
    url = f"{settings.revenuecat_api_base}/subscribers/{app_user_id}"
    try:
        resp = httpx.get(
            url,
            headers={
                "Authorization": f"Bearer {settings.revenuecat_secret_key}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise IapError("rc_unreachable", f"RevenueCat erişilemedi: {exc}") from exc
    if resp.status_code != 200:
        raise IapError(
            "rc_error",
            f"RevenueCat {resp.status_code}: {resp.text[:300]}",
        )
    return resp.json()


def sync_user_from_revenuecat(
    db: Session, user: User, *, autocommit: bool = True,
) -> dict:
    """Kullanıcının App Store abonelik durumunu RevenueCat'ten çekip uygula.

    Mobil, satın alma tamamlanır tamamlanmaz bu yolu çağırır (webhook'u
    beklemeden anında aktivasyon); yenileme cron'u da app_store platformlu
    kullanıcılar için dönem sonunda gerçeği buradan doğrular.

    Dönüş: {"active": bool, "plan_code": str|None, "expired": bool}
    """
    if not is_configured():
        raise IapError("not_configured", "RevenueCat secret key tanımlı değil")

    data = _rc_get_subscriber(str(user.id))
    subs = ((data.get("subscriber") or {}).get("subscriptions") or {})
    now = datetime.now(timezone.utc)

    best: tuple[datetime, str, dict] | None = None  # (expires, product_id, sub)
    for pid, sub in subs.items():
        if not isinstance(sub, dict) or plan_for_product(pid) is None:
            continue
        exp = _parse_iso(sub.get("expires_date"))
        if exp is None or exp <= now:
            continue
        if best is None or exp > best[0]:
            best = (exp, pid, sub)

    if best is not None:
        exp, pid, sub = best
        plan_code, cycle = plan_for_product(pid)  # type: ignore[misc]
        status = "canceled" if sub.get("unsubscribe_detected_at") else "active"
        applied = apply_active_subscription(
            db, user=user, plan_code=plan_code, cycle=cycle,
            expires_at=exp, status=status,
            note=f"App Store IAP (sync · {pid})",
            autocommit=False,
        )
        if autocommit:
            db.commit()
        return {
            "active": applied, "plan_code": plan_code if applied else None,
            "expired": False,
        }

    # Aktif App Store aboneliği yok — daha önce App Store'dan aktive olduysa düşür.
    if (
        user.subscription_platform == PLATFORM_APP_STORE
        and user.subscription_status in ("active", "canceled", "past_due")
    ):
        _expire_app_store_subscription(
            db, user, note="App Store aboneliği sona erdi (sync)",
        )
        if autocommit:
            db.commit()
        return {"active": False, "plan_code": None, "expired": True}

    return {"active": False, "plan_code": None, "expired": False}
