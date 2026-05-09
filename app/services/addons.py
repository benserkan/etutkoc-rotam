"""Stage 9 (Faz 2.2) — Add-on (ek paket) servis katmanı.

Add-on'lar planın *üzerine* eklenen aylık abonelik birimleridir. Üç tip:
- WhatsApp Veli Paketi → parent_notifications_whatsapp flag'ini kuruma/öğretmene
  açar + 500 mesaj/ay
- AI Plus → CreditAccount.bonus_credits'e aylık +1000 ekler
- Veli Portalı → SOLO planlarında veli paneli erişimini açar

Servis fonksiyonları:
- activate_addon(owner, addon_kind, ...): yeni Addon kaydı + yan etkiler
  (kredi havuzuna bonus, vb.)
- cancel_addon(addon_id, ...): cancelled_at + auto_renew=False; period_end'e
  kadar geçerli kalır, sonraki dönemde yenilenmez
- get_active_addons(owner): şu an aktif olanlar
- is_addon_active(owner, kind): tek tip için boolean
- addon_grants_feature_flag(owner, flag_key): add-on, flag_key'i aktive
  ediyor mu (ör. WHATSAPP_PARENT → parent_notifications_whatsapp)
- monthly_addon_renewal(now): auto_renew=True olan ve dönemi biten add-on'ları
  yeni ay için yeniler (cron her ayın 1'inde)

Owner soyutlaması: User veya Institution objesi alır; içeride ('user'|'institution',
id) çiftine çevirir. AddonOwner dataclass'ı CreditOwner ile uyumlu.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import (
    ADDON_MONTHLY_PRICE_TRY,
    ADDON_MONTHLY_QUOTA,
    Addon,
    AddonKind,
    Institution,
    User,
)


logger = logging.getLogger(__name__)


# ---------------------------- Add-on → feature flag eşleşmesi ----------------------------


# Bir add-on aktif olduğunda hangi feature flag'leri zorla "açık" kabul edeceğiz.
# is_enabled() çağrılırken add-on devrede olup olmadığı kontrol edilir; varsa flag
# global/per-kurum ayarına bakılmaksızın True kabul edilir.
ADDON_FEATURE_FLAGS: dict[AddonKind, frozenset[str]] = {
    AddonKind.WHATSAPP_PARENT: frozenset({"parent_notifications_whatsapp"}),
    AddonKind.AI_PLUS: frozenset(),       # kredi bonusu — feature flag açmaz
    AddonKind.PARENT_PORTAL: frozenset(), # SOLO için ayrı route guard kontrol eder
}


# Bir add-on aktif olduğunda kredi havuzuna eklenen aylık bonus.
# Şu an sadece AI_PLUS kredi veriyor; diğerleri WhatsApp/Portal için ayrı ölçülür.
def _addon_credit_bonus(addon_kind: AddonKind) -> int:
    quota = ADDON_MONTHLY_QUOTA.get(addon_kind, {})
    return int(quota.get("credits", 0))


# ---------------------------- AddonOwner (polymorphic) ----------------------------


# DB'de Addon.owner_type plain string (UNIQUE constraint için), bu yüzden enum
# kullanmıyoruz. CreditAccount/UsageEvent ile aynı string değerlere sadık kalıyoruz.
OWNER_TYPE_USER = "user"
OWNER_TYPE_INSTITUTION = "institution"


@dataclass(frozen=True)
class AddonOwner:
    """Polymorphic add-on sahibi. User veya Institution'dan üretilir."""
    type: str   # 'user' | 'institution'
    id: int

    @classmethod
    def for_user(cls, user: User) -> "AddonOwner":
        return cls(type=OWNER_TYPE_USER, id=user.id)

    @classmethod
    def for_institution(cls, institution: Institution) -> "AddonOwner":
        return cls(type=OWNER_TYPE_INSTITUTION, id=institution.id)

    @classmethod
    def for_owner(cls, owner: User | Institution) -> "AddonOwner":
        if isinstance(owner, Institution):
            return cls.for_institution(owner)
        if isinstance(owner, User):
            return cls.for_user(owner)
        raise TypeError(f"AddonOwner.for_owner: tanınmayan tip {type(owner)}")


# ---------------------------- Yardımcılar ----------------------------


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _month_period(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Şu anın ait olduğu aylık dönem (period_start, period_end).

    period_start = ayın 1'i 00:00 UTC; period_end = sonraki ayın 1'i 00:00 UTC.
    Tüm add-on'lar takvim ayına hizalı — fatura/hesaplama tutarlılığı için.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _next_month_period(period_end: datetime) -> tuple[datetime, datetime]:
    """Bir önceki dönemin period_end'ini sonraki dönemin period_start'ı olarak al."""
    start = _normalize_dt(period_end) or _month_period()[1]
    if start.month == 12:
        end = datetime(start.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(start.year, start.month + 1, 1, tzinfo=timezone.utc)
    return start, end


# ---------------------------- Aktif add-on sorguları ----------------------------


def get_active_addons(
    db: Session, *, owner: AddonOwner | User | Institution,
    now: datetime | None = None,
) -> list[Addon]:
    """Sahibin şu an aktif olan tüm add-on'ları (period_end > now)."""
    if not isinstance(owner, AddonOwner):
        owner = AddonOwner.for_owner(owner)
    if now is None:
        now = datetime.now(timezone.utc)
    rows = (
        db.query(Addon)
        .filter(
            Addon.owner_type == owner.type,
            Addon.owner_id == owner.id,
            Addon.period_end > now,
        )
        .order_by(Addon.period_start.desc())
        .all()
    )
    return rows


def is_addon_active(
    db: Session, *, owner: AddonOwner | User | Institution,
    addon_kind: AddonKind, now: datetime | None = None,
) -> bool:
    """Belirli bir add-on tipi şu an aktif mi?"""
    if not isinstance(owner, AddonOwner):
        owner = AddonOwner.for_owner(owner)
    if now is None:
        now = datetime.now(timezone.utc)
    return (
        db.query(Addon.id)
        .filter(
            Addon.owner_type == owner.type,
            Addon.owner_id == owner.id,
            Addon.addon_kind == addon_kind,
            Addon.period_end > now,
        )
        .first()
        is not None
    )


def addon_grants_feature_flag(
    db: Session, *, owner: AddonOwner | User | Institution,
    flag_key: str, now: datetime | None = None,
) -> bool:
    """Bu sahip için, aktif bir add-on `flag_key` özelliğini açıyor mu?

    is_enabled() çağrısının üzerine bir katman: "kuruma override yok, global
    kapalı — ama add-on satın alınmış, o zaman aç" mantığını sağlar.

    Çağıran taraf:
        if (
            feature_flags.is_enabled(db, key, institution=...)
            or addons.addon_grants_feature_flag(db, owner=..., flag_key=key)
        ):
            ...
    """
    if not isinstance(owner, AddonOwner):
        owner = AddonOwner.for_owner(owner)
    actives = get_active_addons(db, owner=owner, now=now)
    for addon in actives:
        if flag_key in ADDON_FEATURE_FLAGS.get(addon.addon_kind, frozenset()):
            return True
    return False


# ---------------------------- Activate ----------------------------


def activate_addon(
    db: Session, *,
    owner: AddonOwner | User | Institution,
    addon_kind: AddonKind,
    period_start: datetime | None = None,
    auto_renew: bool = True,
    note: str | None = None,
    actor_user_id: int | None = None,
    autocommit: bool = True,
) -> Addon:
    """Add-on'u aktive et.

    period_start verilmezse mevcut takvim ayının 1'i alınır; period_end =
    sonraki ayın 1'i. Aynı dönem için aynı add-on yoksa yeni satır açılır;
    varsa idempotent — mevcut satır geri döner (UNIQUE constraint korur).

    AI_PLUS aktivasyonunda CreditAccount.bonus_credits'e +1000 eklenir
    (mevcut period için tek seferlik). Yenilenme aylık_renewal cron'u tarafından.
    """
    if not isinstance(owner, AddonOwner):
        owner = AddonOwner.for_owner(owner)

    # Period — mevcut takvim ayı
    if period_start is None:
        period_start, period_end = _month_period()
    else:
        period_start = _normalize_dt(period_start)  # type: ignore[assignment]
        # period_start'ın ait olduğu ay
        ps = period_start
        if ps.month == 12:
            period_end = datetime(ps.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            period_end = datetime(ps.year, ps.month + 1, 1, tzinfo=timezone.utc)

    # Idempotent: aynı (owner, kind, period_start) varsa onu döndür
    existing = (
        db.query(Addon)
        .filter(
            Addon.owner_type == owner.type,
            Addon.owner_id == owner.id,
            Addon.addon_kind == addon_kind,
            Addon.period_start == period_start,
        )
        .first()
    )
    if existing is not None:
        # İptalden geri çevrilme — aktif tut
        if existing.cancelled_at is not None:
            existing.cancelled_at = None
            existing.cancelled_by_user_id = None
            existing.auto_renew = bool(auto_renew)
            if note:
                existing.note = note
        if autocommit:
            db.commit()
        else:
            db.flush()
        return existing

    addon = Addon(
        owner_type=owner.type,
        owner_id=owner.id,
        addon_kind=addon_kind,
        period_start=period_start,
        period_end=period_end,
        auto_renew=bool(auto_renew),
        price_try=int(ADDON_MONTHLY_PRICE_TRY.get(addon_kind, 0)),
        note=note,
    )
    db.add(addon)
    db.flush()

    # Yan etki: AI_PLUS aktivasyonunda kredi bonusu
    bonus = _addon_credit_bonus(addon_kind)
    if bonus > 0:
        _grant_credit_bonus(
            db, owner=owner, amount=bonus,
            note=f"Add-on '{addon_kind.value}' aktif",
            actor_user_id=actor_user_id,
        )

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "activate_addon: %s#%s %s period=%s..%s",
        owner.type, owner.id, addon_kind.value,
        period_start.isoformat(), period_end.isoformat(),
    )
    return addon


def _grant_credit_bonus(
    db: Session, *, owner: AddonOwner, amount: int,
    note: str | None = None, actor_user_id: int | None = None,
) -> None:
    """Mevcut dönem CreditAccount'a bonus_credits ekle.

    Add-on aktivasyonunda çağrılır. CreditAccount yoksa create edilir.
    Bonus tek seferlik; aylık yenilemeyi monthly_addon_renewal yapar.
    """
    if amount <= 0:
        return
    # Lazy import — credits modülü plans'tan bağımsız
    from app.services.credits import CreditOwner, get_or_create_account

    if owner.type == OWNER_TYPE_INSTITUTION:
        inst = db.get(Institution, owner.id)
        if inst is None:
            return
        co = CreditOwner.for_institution(inst)
    else:
        u = db.get(User, owner.id)
        if u is None:
            return
        co = CreditOwner.for_user(u)

    account = get_or_create_account(db, owner=co)
    account.bonus_credits = (account.bonus_credits or 0) + amount
    db.flush()
    logger.info(
        "_grant_credit_bonus: %s#%s +%d credits (%s)",
        owner.type, owner.id, amount, note or "addon",
    )


# ---------------------------- Cancel ----------------------------


def cancel_addon(
    db: Session, *, addon_id: int, by_user_id: int | None = None,
    autocommit: bool = True,
) -> Addon | None:
    """Add-on'u iptal et — mevcut dönem sonuna kadar geçerli kalır, yenilenmez.

    cancelled_at set edilir + auto_renew=False. Para iadesi yok (bu Faz'da).
    Hesap kayıtlarındaki kredi bonusu da geri alınmaz.
    """
    addon = db.get(Addon, addon_id)
    if addon is None:
        return None
    if addon.cancelled_at is not None:
        return addon  # zaten iptal — idempotent

    addon.cancelled_at = datetime.now(timezone.utc)
    addon.cancelled_by_user_id = by_user_id
    addon.auto_renew = False
    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "cancel_addon: addon=%d (%s#%s %s) cancelled_by=%s",
        addon.id, addon.owner_type, addon.owner_id,
        addon.addon_kind.value, by_user_id,
    )
    return addon


# ---------------------------- Aylık yenileme (cron) ----------------------------


def monthly_addon_renewal(
    db: Session, *, now: datetime | None = None,
) -> dict:
    """Cron: dönemi biten ve auto_renew=True olan add-on'ları yenile.

    Her ayın 1'inde 00:30 UTC çalışır (credits_monthly_refill ile aynı saat
    bandı). İdempotent: yeni dönem için aynı (owner, kind, period_start)
    satırı varsa atlanır (UNIQUE constraint).

    Yenileme akışı:
    - Eski Addon.period_end <= now ve cancelled_at IS NULL ve auto_renew=True
    - Yeni Addon: period_start = eski period_end, period_end = +1 ay
    - AI_PLUS için CreditAccount.bonus_credits += 1000 (yeni dönem)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    now = _normalize_dt(now) or now

    # Bu ayın takvim sınırları — yenilemenin "yeni dönemi" buradan
    period_start, period_end = _month_period(now)

    counts = {
        "renewed": 0, "skipped_cancelled": 0, "skipped_no_renew": 0,
        "skipped_already_renewed": 0, "credit_bonus_granted": 0,
    }

    # Yenilenmeye aday add-on'lar: dönemi *bu ay başlangıcından önce* veya
    # *tam başlangıcında* biten ve auto_renew aktif. Pencere geniş — geç
    # tetiklenirse (job birkaç gün gecikse) hâlâ yakalansın.
    candidates = (
        db.query(Addon)
        .filter(
            Addon.period_end <= period_start,
            Addon.auto_renew.is_(True),
            Addon.cancelled_at.is_(None),
        )
        .all()
    )

    for old in candidates:
        # Bu (owner, kind) için zaten yeni dönem satırı açıldı mı?
        already = (
            db.query(Addon.id)
            .filter(
                Addon.owner_type == old.owner_type,
                Addon.owner_id == old.owner_id,
                Addon.addon_kind == old.addon_kind,
                Addon.period_start == period_start,
            )
            .first()
        )
        if already is not None:
            counts["skipped_already_renewed"] += 1
            continue

        new_addon = Addon(
            owner_type=old.owner_type,
            owner_id=old.owner_id,
            addon_kind=old.addon_kind,
            period_start=period_start,
            period_end=period_end,
            auto_renew=True,
            price_try=int(ADDON_MONTHLY_PRICE_TRY.get(old.addon_kind, 0)),
            note=f"Otomatik yenileme (önceki: addon#{old.id})",
        )
        db.add(new_addon)
        db.flush()
        counts["renewed"] += 1

        # AI_PLUS için yeni dönem kredi bonusu
        bonus = _addon_credit_bonus(old.addon_kind)
        if bonus > 0:
            owner_obj = AddonOwner(type=old.owner_type, id=old.owner_id)
            _grant_credit_bonus(
                db, owner=owner_obj, amount=bonus,
                note=f"Add-on '{old.addon_kind.value}' aylık yenileme",
            )
            counts["credit_bonus_granted"] += 1

    db.commit()
    logger.info("monthly_addon_renewal: %s", counts)
    return counts


# ---------------------------- Toplu sorgular (UI) ----------------------------


def list_addon_history(
    db: Session, *, owner: AddonOwner | User | Institution,
    limit: int = 50,
) -> list[Addon]:
    """Sahibin tüm add-on geçmişi (aktif + iptal + bitmiş) — yeni → eski."""
    if not isinstance(owner, AddonOwner):
        owner = AddonOwner.for_owner(owner)
    return (
        db.query(Addon)
        .filter(
            Addon.owner_type == owner.type,
            Addon.owner_id == owner.id,
        )
        .order_by(Addon.period_start.desc(), Addon.id.desc())
        .limit(limit)
        .all()
    )


def active_addon_kinds(
    db: Session, *, owner: AddonOwner | User | Institution,
    now: datetime | None = None,
) -> set[AddonKind]:
    """Sahibin aktif add-on türleri set'i — UI condition'ları için kısa yol."""
    return {a.addon_kind for a in get_active_addons(db, owner=owner, now=now)}
