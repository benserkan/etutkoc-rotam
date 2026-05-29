"""Stage 6 — kredi servisi.

Tüm AI/email/WhatsApp çağrıları bu modül üzerinden ölçülür:
- Çağrıdan ÖNCE: `check_credit_available(db, owner)` → blok varsa CreditBlocked
- Çağrıdan SONRA (başarılı ise): `record_usage(db, owner, kind)` → kredi düş

Çağrı bağlamı (context manager):
    with consume_credits(db, owner, UsageKind.AI_INSIGHTS, actor=user) as ctx:
        # AI çağrısı yap
        ctx.set_metadata({"tokens": 1234, "model": "claude-haiku"})
    # exit'te success ise record_usage; exception ise atla

Kurum: institution_id sahibi olan tüm kullanıcılar tek institutional pool.
Bağımsız öğretmen (institution_id=NULL teacher): bireysel pool.

Diğer roller (institution_id NULL student/admin) bu sistemde "yok" — onlar
zaten anormal durumdur; defansif olarak çağrı reddedilir.

Period: 'YYYY-MM' string. Refill cron her ayın 1'inde günceller.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterator, Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    CreditAccount,
    Institution,
    UsageEvent,
    UsageKind,
    UsageOwnerType,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# ---------------------------- Sabitler ----------------------------


# Plan başına aylık kredi tahsisatı (TUNABLE — settings'e taşınabilir).
# Tasarım: free trial gibi düşük başlangıç, pro tier'da bol kredi.
PLAN_ALLOCATIONS: dict[str, int] = {
    # ----- DEFANSİF FALLBACK -----
    # "free" PLAN_CATALOG'da DEĞİL ama eski DB satırları (özellikle non-teacher
    # User: öğrenci/veli/admin default plan="free") taşır. Bu satır olmadan
    # credits.py:204 (allocation = PLAN_ALLOCATIONS.get(..., PLAN_ALLOCATIONS["free"]))
    # KeyError. AI özelliği bu kullanıcılarda KAPALI, sadece email/whatsapp gibi
    # düşük maliyetli aksiyonlar için yeterli.
    "free": 100,
    # ----- SOLO (bağımsız koç) — period (ay) başına kredi -----
    # Tahmin: öğrenci başına ~150 kredi/ay (AI yoğun kullanılırsa). 2026-05-26
    # revizyonu: ETUTKOC gerçek tüketim verisinden (8 günde 56 = ay 210 / 1
    # öğrenci) ekstrapolasyon. AI fiyatları: email=1, WA=5, AI insight=6,
    # AI foto=5, AI dikte=3, AI book_template=5.
    "solo_free": 200,        # 3 öğr, AI yok → ~90 email + buffer
    "solo_trial": 50,        # 14 gün deneme — TASARIM AI-tavanı (sembolik)
    "solo_pro": 1500,        # ≤10 öğr × 150 = 1500
    "solo_elite": 4000,      # ≤25 öğr × 160 = 4000
    "solo_unlimited": 8000,  # sınırsız öğrenci
    # ----- KURUM planları -----
    "institution_free": 200,    # ≤2 koç, AI sınırlı
    "institution_trial": 3000,  # kurum deneme
    "etut_standart": 10000,     # ≤10 koç × 5 öğr × 200 ≈ 10K
    "dershane_pro": 40000,      # ≤50 koç × 5 öğr × 160 ≈ 40K
    "enterprise": 150000,       # 50+ koç, özel teklif
}

# Çağrı tipi başına kredi maliyeti (TUNABLE).
# AI çağrıları görece pahalı; email/WA daha az.
KIND_CREDITS: dict[UsageKind, int] = {
    UsageKind.AI_BOOK_TEMPLATE: 5,
    UsageKind.AI_INSIGHTS: 5,
    UsageKind.AI_SESSION_CAPTURE: 5,
    UsageKind.AI_SESSION_VOICE: 8,  # (eski) — kullanılmıyor
    UsageKind.AI_TRANSCRIBE: 3,     # saf ses→metin dikte (alan başına)
    UsageKind.AI_COACHING_INSIGHT: 6,  # Gemini — geniş bağlam (seans geçmişi + akademik)
    UsageKind.EMAIL_SEND: 1,
    UsageKind.WHATSAPP_SEND: 5,
    UsageKind.OTHER: 1,
}

# %80 uyarı eşiği
WARN_THRESHOLD_PCT = 80

# Bağımsız öğretmen %100'e ulaşınca cooldown süresi
INDEPENDENT_COOLDOWN_HOURS = 5


# ---------------------------- Hata sınıfı ----------------------------


class CreditBlocked(Exception):
    """Kredi blokunda — çağrı reddedildi.

    Tipler:
    - 'hard_block': Süper admin manuel hard-block aktif (kurum)
    - 'cooldown': Bağımsız öğretmen 5h soğumada
    - 'no_account': Sahip türü desteklenmiyor (anormal durum)
    """
    def __init__(
        self, reason: Literal["hard_block", "cooldown", "no_account"],
        *, until: datetime | None = None, message: str = "",
    ):
        self.reason = reason
        self.until = until
        self.message = message or f"Kredi blokunda: {reason}"
        super().__init__(self.message)


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class CreditOwner:
    """Polymorphic sahip referansı.

    Bir User verildiğinde bu helper otomatik institution vs independent
    teacher ayrımını yapar.
    """
    type: UsageOwnerType
    id: int
    plan_code: str  # snapshot — hesap oluştururken kullanılır

    @classmethod
    def for_user(cls, user: User) -> "CreditOwner":
        """User'ın hangi havuza ait olduğunu belirle.

        - Kurumlu kullanıcı → kurum havuzu (Institution.plan)
        - Bağımsız öğretmen (TEACHER + institution_id IS NULL) → bireysel (User.plan)
        - Diğer (institution_id NULL admin/student/parent) → bireysel (User.plan),
          ama normalde olmamalı
        """
        if user.institution_id is not None:
            inst = user.institution
            plan = inst.plan if inst else "free"
            return cls(
                type=UsageOwnerType.INSTITUTION,
                id=user.institution_id,
                plan_code=plan,
            )
        return cls(
            type=UsageOwnerType.USER,
            id=user.id,
            plan_code=getattr(user, "plan", "free") or "free",
        )

    @classmethod
    def for_institution(cls, institution: Institution) -> "CreditOwner":
        return cls(
            type=UsageOwnerType.INSTITUTION,
            id=institution.id,
            plan_code=institution.plan or "free",
        )


# ---------------------------- Yardımcılar ----------------------------


def current_period(now: datetime | None = None) -> str:
    """Aktif period 'YYYY-MM' string'i (UTC ay)."""
    if now is None:
        now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_or_create_account(
    db: Session, *, owner: CreditOwner, period: str | None = None,
) -> CreditAccount:
    """Sahip + period için CreditAccount satırı; yoksa plan'a göre oluştur.

    İlk oluşumda allocated_credits = PLAN_ALLOCATIONS[owner.plan_code].
    Plan tanımsızsa 'free' baz alınır (defansif).
    """
    if period is None:
        period = current_period()
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == owner.type,
            CreditAccount.owner_id == owner.id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if acc:
        return acc

    allocation = PLAN_ALLOCATIONS.get(owner.plan_code, PLAN_ALLOCATIONS["free"])
    acc = CreditAccount(
        owner_type=owner.type,
        owner_id=owner.id,
        period_year_month=period,
        allocated_credits=allocation,
        used_credits=0,
        bonus_credits=0,
        plan_code=owner.plan_code,
        hard_block_enabled=False,
    )
    db.add(acc)
    db.flush()
    return acc


# ---------------------------- Bakiye kontrolü ----------------------------


@dataclass
class CreditCheckResult:
    ok: bool
    account: CreditAccount
    reason: str | None = None       # 'hard_block' | 'cooldown' | None
    blocked_until: datetime | None = None
    remaining: int = 0


def check_credit_available(
    db: Session, *, owner: CreditOwner, kind: UsageKind | None = None,
    now: datetime | None = None,
) -> CreditCheckResult:
    """Kredi mevcut mu, blok aktif mi?

    Kontrol sırası:
    1) Hard-block → reddet (kurum, super admin manuel)
    2) Cooldown (blocked_until > now) — eğer süresi dolduysa otomatik unblock
    3) Yeterli kredi (kind verildiyse o tipin maliyeti kadar; yoksa >= 1)

    Kurumlar için kredi yetersizse (used >= allocated): ok=False ama
    cooldown SET EDİLMEZ — kurum manuel hard-block ile yönetilir.
    Bağımsız öğretmen için aynı durumda blocked_until otomatik set edilir.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    period = current_period(now)
    acc = get_or_create_account(db, owner=owner, period=period)

    cost = KIND_CREDITS.get(kind, 1) if kind else 1

    # 1) Hard-block
    if acc.hard_block_enabled:
        return CreditCheckResult(
            ok=False, account=acc, reason="hard_block",
            remaining=acc.remaining_credits,
        )

    # 2) Cooldown — süresi dolmuşsa temizle
    if acc.blocked_until is not None:
        bu = _normalize_dt(acc.blocked_until)
        if bu and bu > now:
            return CreditCheckResult(
                ok=False, account=acc, reason="cooldown", blocked_until=bu,
                remaining=acc.remaining_credits,
            )
        # Süresi dolmuş → temizle (record_usage'da olabilir ama burada kibarca)
        acc.blocked_until = None
        db.flush()

    # 3) Yeterli kredi var mı
    if acc.remaining_credits < cost:
        # Bağımsız öğretmen: krediler tükendiğinde 'exhausted' reason döner.
        # ÇÖZÜM YENİDEN-DENE DEĞİL → çözüm paket yükseltme veya ay başını bekleme.
        # (Cooldown saati 'X saat sonra tekrar deneyin' mesajı YANLIŞ — krediler
        # ay başında yenilenir. UI 'paketi yükselt' yönlendirir.)
        if owner.type == UsageOwnerType.USER:
            return CreditCheckResult(
                ok=False, account=acc, reason="exhausted",
                remaining=acc.remaining_credits,
            )
        # Kurum: krediyi tüketmiş ama hard-block manuel — fonksiyonel davranış
        # kullanıcı tarafına bırakılır (warn ama çalışmaya devam et).
        # check_credit_available ok=True döner; gerçek "blok" yalnız hard_block.
        return CreditCheckResult(
            ok=True, account=acc, reason=None,
            remaining=acc.remaining_credits,
        )

    return CreditCheckResult(ok=True, account=acc, remaining=acc.remaining_credits)


# ---------------------------- Kayıt ----------------------------


def record_usage(
    db: Session, *, owner: CreditOwner, kind: UsageKind,
    credits: int | None = None, actor_user_id: int | None = None,
    metadata: dict | None = None, now: datetime | None = None,
    autocommit: bool = True,
) -> UsageEvent:
    """Bir kullanım eventi kaydet + CreditAccount.used_credits artır.

    credits None ise KIND_CREDITS.get(kind, 1) varsayılır. Defensive: 0/negatif
    değerler 1'e clamp.

    %80 eşiği bu kullanımla geçildiyse ilgili flag set edilir (ayrı bir
    notify_warning_if_threshold_crossed çağrısıyla e-posta + banner tetiklenir).
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if credits is None:
        credits = KIND_CREDITS.get(kind, 1)
    if credits < 1:
        credits = 1

    period = current_period(now)
    acc = get_or_create_account(db, owner=owner, period=period)

    event = UsageEvent(
        owner_type=owner.type,
        owner_id=owner.id,
        kind=kind,
        credits=credits,
        period_year_month=period,
        actor_user_id=actor_user_id,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    db.add(event)

    acc.used_credits = (acc.used_credits or 0) + credits

    # NOT: Bağımsız öğretmen için 'cooldown' mantığı KALDIRILDI (2026-05-29).
    # Krediler ay başında otomatik yenilenir; '5 saat sonra tekrar deneyin'
    # mesajı yanıltıcıydı. Bunun yerine check_credit_available 'exhausted'
    # reason döner ve endpoint koçu /teacher/plan'a yönlendirir
    # (`ai_credit_exhausted` 402 + details.upgrade_url).

    # %80 eşiği bu kullanımla geçildi mi → uyarı tetikle
    if threshold_just_crossed(acc):
        try:
            _send_warning_email(db, account=acc, owner=owner)
        except Exception as we:
            logger.warning("usage warning email failed (non-fatal): %s", we)
        mark_warning_sent(db, acc, now=now)

    if autocommit:
        db.commit()
    else:
        db.flush()
    return event


def _send_warning_email(
    db: Session, *, account: CreditAccount, owner: CreditOwner,
) -> None:
    """%80 eşiğinde tek seferlik uyarı e-postası — kuruma admin'lere veya
    bağımsız öğretmene.
    """
    from app.services.email_service import send_email

    if owner.type == UsageOwnerType.INSTITUTION:
        from app.models import Institution
        inst = db.get(Institution, owner.id)
        if not inst:
            return
        # Kurum yöneticilerine
        admins = (
            db.query(User)
            .filter(
                User.institution_id == owner.id,
                User.role == UserRole.INSTITUTION_ADMIN,
                User.is_active.is_(True),
            )
            .all()
        )
        emails = [a.email for a in admins if a.email]
        for email in emails:
            send_email(
                to=email, template="credit_warning",
                ctx={
                    "owner_name": inst.name,
                    "owner_kind": "kurum",
                    "used": account.used_credits,
                    "allocated": account.total_allocated,
                    "pct": account.usage_pct,
                    "plan_code": account.plan_code,
                    "period": account.period_year_month,
                    "is_institution": True,
                },
            )
    else:
        u = db.get(User, owner.id)
        if not u or not u.email:
            return
        send_email(
            to=u.email, template="credit_warning",
            ctx={
                "owner_name": u.full_name or u.email,
                "owner_kind": "öğretmen",
                "used": account.used_credits,
                "allocated": account.total_allocated,
                "pct": account.usage_pct,
                "plan_code": account.plan_code,
                "period": account.period_year_month,
                "is_institution": False,
            },
        )


# ---------------------------- %80 uyarı ----------------------------


def threshold_just_crossed(
    account: CreditAccount, *, threshold_pct: int = WARN_THRESHOLD_PCT,
) -> bool:
    """Bu period'da %80'i ilk kez geçti mi (warn_80_sent_at NULL ve usage >= eşik)?

    Çağıran taraf (record_usage sonrası) flag'i set + uyarıyı tetikler.
    """
    if account.warn_80_sent_at is not None:
        return False
    if account.total_allocated <= 0:
        return False
    return account.usage_pct >= threshold_pct


def mark_warning_sent(
    db: Session, account: CreditAccount, *, now: datetime | None = None,
) -> None:
    if now is None:
        now = datetime.now(timezone.utc)
    account.warn_80_sent_at = now
    db.flush()


# ---------------------------- Context manager ----------------------------


@dataclass
class _UsageContext:
    """consume_credits ile döndürülen handle.

    .set_metadata(dict) ile çağrı detayını ekle (token sayısı, model adı vb.).
    """
    metadata: dict | None = None

    def set_metadata(self, m: dict) -> None:
        self.metadata = m


@contextmanager
def consume_credits(
    db: Session, *, owner: CreditOwner, kind: UsageKind,
    actor_user_id: int | None = None, credits: int | None = None,
    autocommit: bool = True,
) -> Iterator[_UsageContext]:
    """Pre-check + post-record bir arada.

    Kullanım:
        try:
            with consume_credits(db, owner=..., kind=UsageKind.AI_INSIGHTS) as ctx:
                # AI çağrısı yap, sonuç al
                ctx.set_metadata({"tokens": 1234})
            # ctx exit'inde record_usage çağrılır
        except CreditBlocked as e:
            # block aktif — UI'da kibar mesaj
            ...

    Hata oluşursa (with bloğu içinde exception), kredi DÜŞÜLMEZ. Yarım kalan
    çağrılar için fatura çıkarmamak iyi pratik.
    """
    check = check_credit_available(db, owner=owner, kind=kind)
    if not check.ok:
        # Cooldown / hard-block / exhausted — exception fırlat
        reason_messages = {
            "hard_block": "Yapay zekâ kullanımı manuel olarak kapatıldı (süper admin)",
            "cooldown": (
                f"Kullanım sınırına ulaşıldı, "
                f"{INDEPENDENT_COOLDOWN_HOURS} saat sonra tekrar deneyin"
            ),
            "exhausted": (
                "Bu ay için yapay zekâ kredin bitti. Paketini yükselterek "
                "kesintisiz devam edebilirsin."
            ),
        }
        raise CreditBlocked(
            reason=check.reason or "no_account",  # type: ignore[arg-type]
            until=check.blocked_until,
            message=reason_messages.get(check.reason or "", "Kredi hesabı bulunamadı"),
        )

    ctx = _UsageContext()
    yield ctx
    # with bloğu hatasız bitti — kaydet
    record_usage(
        db, owner=owner, kind=kind, credits=credits,
        actor_user_id=actor_user_id, metadata=ctx.metadata,
        autocommit=autocommit,
    )


# ---------------------------- Aylık refill ----------------------------


def monthly_refill(db: Session, *, now: datetime | None = None) -> dict:
    """Cron: her ayın 1'inde tüm aktif sahipler için yeni period satırı oluştur.

    İdempotent: bu period için satır varsa atlanır.

    Sahipler:
    - Tüm aktif Institution
    - Tüm aktif bağımsız teacher (institution_id IS NULL, role=TEACHER)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    period = current_period(now)

    counts = {"institutions": 0, "independent_teachers": 0, "skipped": 0}

    # Kurumlar
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    for inst in insts:
        owner = CreditOwner.for_institution(inst)
        existing = (
            db.query(CreditAccount)
            .filter(
                CreditAccount.owner_type == owner.type,
                CreditAccount.owner_id == owner.id,
                CreditAccount.period_year_month == period,
            )
            .first()
        )
        if existing:
            counts["skipped"] += 1
            continue
        get_or_create_account(db, owner=owner, period=period)
        counts["institutions"] += 1

    # Bağımsız öğretmenler
    indeps = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .all()
    )
    for u in indeps:
        owner = CreditOwner.for_user(u)
        existing = (
            db.query(CreditAccount)
            .filter(
                CreditAccount.owner_type == owner.type,
                CreditAccount.owner_id == owner.id,
                CreditAccount.period_year_month == period,
            )
            .first()
        )
        if existing:
            counts["skipped"] += 1
            continue
        get_or_create_account(db, owner=owner, period=period)
        counts["independent_teachers"] += 1

    db.commit()
    counts["period"] = period
    counts["total_created"] = counts["institutions"] + counts["independent_teachers"]
    logger.info("monthly_refill: %s", counts)
    return counts


# ---------------------------- Toplu sorgular (UI için) ----------------------------


def usage_breakdown_by_kind(
    db: Session, *, owner: CreditOwner, period: str | None = None,
) -> dict[str, int]:
    """Period için tip kırılımı: {kind_value: total_credits}."""
    if period is None:
        period = current_period()
    rows = (
        db.query(
            UsageEvent.kind,
            func.coalesce(func.sum(UsageEvent.credits), 0),
        )
        .filter(
            UsageEvent.owner_type == owner.type,
            UsageEvent.owner_id == owner.id,
            UsageEvent.period_year_month == period,
        )
        .group_by(UsageEvent.kind)
        .all()
    )
    return {kind.value: int(total or 0) for kind, total in rows}


def daily_usage_series(
    db: Session, *, owner: CreditOwner, days: int = 30,
    today: date | None = None,
) -> list[tuple[date, int]]:
    """Son N gün günlük tüketim serisi — UI grafiği için."""
    if today is None:
        today = date.today()
    if days < 1:
        days = 1
    if days > 90:
        days = 90
    start = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = (
        db.query(
            func.date(UsageEvent.occurred_at).label("d"),
            func.coalesce(func.sum(UsageEvent.credits), 0).label("c"),
        )
        .filter(
            UsageEvent.owner_type == owner.type,
            UsageEvent.owner_id == owner.id,
            UsageEvent.occurred_at >= start_dt,
            UsageEvent.occurred_at < end_dt,
        )
        .group_by(func.date(UsageEvent.occurred_at))
        .all()
    )
    by_day = {}
    for d, c in rows:
        if isinstance(d, str):
            d = date.fromisoformat(d[:10])
        by_day[d] = int(c or 0)

    out = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        out.append((day, by_day.get(day, 0)))
    return out


def recent_events(
    db: Session, *, owner: CreditOwner, limit: int = 50,
) -> list[UsageEvent]:
    """Son N event — UI için (en yeni önce)."""
    return (
        db.query(UsageEvent)
        .filter(
            UsageEvent.owner_type == owner.type,
            UsageEvent.owner_id == owner.id,
        )
        .order_by(UsageEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )
