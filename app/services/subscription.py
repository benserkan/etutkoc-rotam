"""Stage 9 (Faz 2.5) — Akademik yıl + yaz pause + 60g performans garantisi.

Bu modül sadece kurumlar (Institution) için geçerli. Bağımsız öğretmenler
aylık ödeme + add-on modeliyle çalışır; yıllık ya da pause özelliği yok.

Üç ana özellik:

1) **Akademik yıl planı** — Eylül-Haziran 10 ay peşin ödeme, 12 ay erişim
   (yaz dönemi pause olarak veya devam eden erişimle gelir). UI'da yıllık
   ücret üzerinden 2 ay tasarruf vurgusu.

2) **Yaz pause** — Akademik yıl planındaki kurumlar Temmuz-Ağustos için
   pause modu seçebilir. subscription_kind='paused'; %20 saklama ücreti
   alınır (kredi havuzu, feature flag'ler kapalı, cron job'ları o kurumu
   atlıyor — diğer modüllerde uygulanacak).

3) **60 gün performans garantisi** — Dershane Pro / Solo Elite plan'larında
   aktif olabilir. Plana başlangıçtan 60 gün sonra koçluk verim metriği
   eşiğin altındaysa otomatik 1 ay uzatma + CSM iletişimi tetiklenir.
   guarantee_extended_at NULL = hiç uzatma uygulanmamış. Tek seferlik —
   uzatma 1 kez yapılır.

Not: Ödeme entegrasyonu yok; bu modül plan durumu ve audit kayıtlarıyla
sınırlı. Gerçek tahsilat ileride payment provider entegrasyonunda eklenecek.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    PlanOwnerType,
    Task,
    TaskStatus,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# ---------------------------- Sabitler ----------------------------


# Türkiye akademik yılı: Eylül başlar, Haziran biter.
ACADEMIC_YEAR_START_MONTH = 9   # Eylül
ACADEMIC_YEAR_START_DAY = 1
ACADEMIC_YEAR_END_MONTH = 6     # Haziran (sonu)
ACADEMIC_YEAR_END_DAY = 30

# Yaz pause modunda saklama ücretinin orijinal aylık fiyata oranı.
# Plan değiştirmek değil — sadece düşük tarife.
SUMMER_PAUSE_DISCOUNT_RATIO = 0.20    # %20

# 60 gün performans garantisi — değerlendirme süresi
GUARANTEE_PERIOD_DAYS = 60
# Garantinin uzatma süresi (1 ay)
GUARANTEE_EXTENSION_DAYS = 30
# Garantinin tetiklendiği eşik: kurum-genelinde haftalık tamamlama oranı %30 altı
GUARANTEE_COMPLETION_THRESHOLD = 0.30

# Subscription kind değerleri
KIND_MONTHLY = "monthly"
KIND_ACADEMIC_YEAR = "academic_year"
KIND_PAUSED = "paused"
ALL_KINDS = (KIND_MONTHLY, KIND_ACADEMIC_YEAR, KIND_PAUSED)


# ---------------------------- Yardımcılar ----------------------------


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def current_academic_year_bounds(now: datetime | None = None) -> tuple[date, date]:
    """Şu anın ait olduğu akademik yıl başı ve sonu.

    Bugün 1 Ocak ise akademik yıl önceki Eylül'de başladı.
    Bugün 15 Eylül ise yeni akademik yıl başladı.
    Sonu: ertesi yılın 30 Haziran.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    if today.month >= ACADEMIC_YEAR_START_MONTH:
        start = date(today.year, ACADEMIC_YEAR_START_MONTH, ACADEMIC_YEAR_START_DAY)
        end = date(today.year + 1, ACADEMIC_YEAR_END_MONTH, ACADEMIC_YEAR_END_DAY)
    else:
        start = date(today.year - 1, ACADEMIC_YEAR_START_MONTH, ACADEMIC_YEAR_START_DAY)
        end = date(today.year, ACADEMIC_YEAR_END_MONTH, ACADEMIC_YEAR_END_DAY)
    return start, end


def is_summer_window(now: datetime | None = None) -> bool:
    """Şu an yaz penceresi mi (Tem-Ağu)? Pause yalnız bu pencerede başlatılabilir."""
    if now is None:
        now = datetime.now(timezone.utc)
    m = now.month
    return m in (7, 8)


# ---------------------------- Akademik yıl planı ----------------------------


@dataclass
class SubscriptionStatus:
    """UI'da gösterilecek özet durum."""
    kind: str                       # 'monthly' | 'academic_year' | 'paused'
    kind_label: str
    period_end: datetime | None
    pause_until: datetime | None
    in_summer_window: bool
    can_pause: bool
    can_resume: bool
    can_switch_to_academic_year: bool
    days_until_period_end: int | None
    performance_guarantee: bool
    guarantee_extended_at: datetime | None


KIND_LABELS_TR = {
    KIND_MONTHLY: "Aylık Abonelik",
    KIND_ACADEMIC_YEAR: "Akademik Yıl Planı",
    KIND_PAUSED: "Yaz Pause Modu",
}


def get_status(institution: Institution, now: datetime | None = None) -> SubscriptionStatus:
    """Kurumun mevcut abonelik durumu özeti."""
    if now is None:
        now = datetime.now(timezone.utc)
    pe = _ensure_utc(institution.subscription_period_end)
    pu = _ensure_utc(institution.subscription_pause_until)
    days_until_end = None
    if pe is not None:
        days_until_end = max(0, (pe.date() - now.date()).days)

    summer = is_summer_window(now)
    kind = institution.subscription_kind or KIND_MONTHLY

    return SubscriptionStatus(
        kind=kind,
        kind_label=KIND_LABELS_TR.get(kind, kind),
        period_end=pe,
        pause_until=pu,
        in_summer_window=summer,
        # Pause yalnız akademik yıl planında VE yaz penceresinde mümkün
        can_pause=(kind == KIND_ACADEMIC_YEAR and summer),
        can_resume=(kind == KIND_PAUSED),
        # Aylıktan akademik yıla geçiş — istediği zaman
        can_switch_to_academic_year=(kind == KIND_MONTHLY),
        days_until_period_end=days_until_end,
        performance_guarantee=institution.performance_guarantee,
        guarantee_extended_at=_ensure_utc(institution.guarantee_extended_at),
    )


def switch_to_academic_year(
    db: Session, *, institution: Institution,
    actor_user_id: int | None = None,
    note: str | None = None,
    autocommit: bool = True,
) -> Institution:
    """Aylıktan akademik yıl planına geçir.

    period_end = şu anki akademik yılın sonuna (30 Haziran) set edilir.
    Eğer şu an Eylül-Haziran arası ise mevcut yılın sonu; Tem-Ağu arası ise
    bir sonraki Haziran sonu.
    """
    if institution.subscription_kind == KIND_ACADEMIC_YEAR:
        return institution
    now = datetime.now(timezone.utc)
    _, end_date = current_academic_year_bounds(now)
    period_end = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    institution.subscription_kind = KIND_ACADEMIC_YEAR
    institution.subscription_period_end = period_end
    institution.subscription_pause_until = None

    # Audit
    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,    # plan değişmedi, abonelik tipi değişti
        reason=PlanChangeReason.ACADEMIC_YEAR_RENEWAL,
        actor_user_id=actor_user_id,
        note=note or f"Akademik yıl planına geçildi (bitiş: {end_date.isoformat()})",
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "switch_to_academic_year: inst=%s period_end=%s",
        institution.id, period_end.isoformat(),
    )
    return institution


def renew_academic_year(
    db: Session, *, institution: Institution,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> Institution:
    """Akademik yıl bitince bir sonraki akademik yıla yenileme.

    Cron'dan çağrılabilir veya manuel UI ile.
    """
    if institution.subscription_kind != KIND_ACADEMIC_YEAR:
        raise ValueError(
            f"renew_academic_year: kurum #{institution.id} akademik yılda değil"
        )
    pe = _ensure_utc(institution.subscription_period_end)
    if pe is None:
        # Hiç yoktan bir akademik yıl set et
        return switch_to_academic_year(
            db, institution=institution, actor_user_id=actor_user_id,
            note="Akademik yıl planı yenilendi (önceki dönem yok)",
            autocommit=autocommit,
        )
    # Sonraki akademik yıl sonu — period_end + 1 yıl
    next_end_date = pe.date().replace(year=pe.year + 1)
    next_period_end = datetime.combine(
        next_end_date, datetime.max.time(), tzinfo=timezone.utc,
    )
    institution.subscription_period_end = next_period_end
    institution.subscription_pause_until = None
    if institution.subscription_kind == KIND_PAUSED:
        institution.subscription_kind = KIND_ACADEMIC_YEAR

    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,
        reason=PlanChangeReason.ACADEMIC_YEAR_RENEWAL,
        actor_user_id=actor_user_id,
        note=f"Akademik yıl yenilendi (yeni bitiş: {next_end_date.isoformat()})",
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "renew_academic_year: inst=%s next_period_end=%s",
        institution.id, next_period_end.isoformat(),
    )
    return institution


# ---------------------------- Yaz pause ----------------------------


def pause_for_summer(
    db: Session, *, institution: Institution,
    until: datetime | None = None,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> Institution:
    """Akademik yıl planındaki kurumu yaz boyunca pause moduna al.

    Varsayılan: 31 Ağustos sonuna kadar. Bu süre boyunca subscription_kind=
    'paused'; Eylül'de manuel veya cron ile resume.

    Sadece akademik yıl planında olan kurumlar pause olabilir; aylık plan
    için pause anlamsız (zaten istediğinde iptal edebilir).
    """
    if institution.subscription_kind not in (KIND_ACADEMIC_YEAR, KIND_PAUSED):
        raise ValueError(
            f"pause_for_summer: kurum #{institution.id} akademik yıl planında değil"
        )
    now = datetime.now(timezone.utc)
    if until is None:
        # Varsayılan: o yılın 31 Ağustos 23:59
        year = now.year if now.month <= 8 else now.year + 1
        until = datetime(year, 8, 31, 23, 59, 59, tzinfo=timezone.utc)
    until = _ensure_utc(until)

    prev_kind = institution.subscription_kind
    institution.subscription_kind = KIND_PAUSED
    institution.subscription_pause_until = until

    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,
        reason=PlanChangeReason.PAUSE,
        actor_user_id=actor_user_id,
        note=(
            f"Yaz pause moduna geçildi (önceki: {prev_kind}, "
            f"dönüş: {until.date().isoformat()})"
        ),
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "pause_for_summer: inst=%s until=%s",
        institution.id, until.isoformat(),
    )
    return institution


def resume_from_pause(
    db: Session, *, institution: Institution,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> Institution:
    """Pause modundaki kurumu akademik yıl planına geri al."""
    if institution.subscription_kind != KIND_PAUSED:
        return institution
    institution.subscription_kind = KIND_ACADEMIC_YEAR
    institution.subscription_pause_until = None

    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,
        reason=PlanChangeReason.RESUME,
        actor_user_id=actor_user_id,
        note="Pause modundan akademik yıl planına geri dönüldü",
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info("resume_from_pause: inst=%s", institution.id)
    return institution


def is_paused(institution: Institution, now: datetime | None = None) -> bool:
    """Kurum şu an pause modunda mı?

    subscription_kind='paused' VE pause_until > now (veya pause_until None
    ise sonsuz pause varsayılır).
    """
    if institution.subscription_kind != KIND_PAUSED:
        return False
    pu = _ensure_utc(institution.subscription_pause_until)
    if pu is None:
        return True
    if now is None:
        now = datetime.now(timezone.utc)
    return pu > now


# ---------------------------- 60 gün performans garantisi ----------------------------


@dataclass
class GuaranteeEvaluation:
    """60g performans garantisi sonucu."""
    eligible: bool                  # plana göre garanti geçerli mi
    period_started_at: datetime | None
    days_into_period: int | None    # bugün periyot başından kaç gün sonra
    average_completion_rate: float | None    # 0..1 — kurum geneli haftalık ort
    threshold: float
    triggered: bool                 # eşiğin altında mı (uzatma şart)
    already_extended: bool
    can_extend: bool                # uzatmak şu an mümkün mü
    note: str


def enable_guarantee(
    db: Session, *, institution: Institution,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> Institution:
    """60g performans garantisini aktive et (Dershane Pro / Solo Elite plan'da)."""
    if institution.performance_guarantee:
        return institution
    institution.performance_guarantee = True
    institution.guarantee_extended_at = None    # eski uzatmaları sıfırla — yeni periyot

    # Audit (PlanChangeHistory üzerinden)
    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,
        reason=PlanChangeReason.GUARANTEE_EXTEND,    # tracking için yakın anlam
        actor_user_id=actor_user_id,
        note="60g performans garantisi aktive edildi",
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info("enable_guarantee: inst=%s", institution.id)
    return institution


def evaluate_guarantee(
    db: Session, *, institution: Institution,
    now: datetime | None = None,
) -> GuaranteeEvaluation:
    """Kurumun 60g garantisi tetiklenecek durumda mı? Salt-okunur değerlendirme.

    Periyot başlangıcı: institution.created_at (veya garanti ilk aktive edilme).
    Eşik: kurum genelinde son 60 gündeki haftalık tamamlama ortalaması
    GUARANTEE_COMPLETION_THRESHOLD altındaysa.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if not institution.performance_guarantee:
        return GuaranteeEvaluation(
            eligible=False, period_started_at=None, days_into_period=None,
            average_completion_rate=None, threshold=GUARANTEE_COMPLETION_THRESHOLD,
            triggered=False, already_extended=False, can_extend=False,
            note="Garanti seçili değil (performance_guarantee=False)",
        )

    period_start = _ensure_utc(institution.created_at) or now
    days_in = (now.date() - period_start.date()).days
    already = institution.guarantee_extended_at is not None

    # 60 günden az ise henüz değerlendirme zamanı değil
    if days_in < GUARANTEE_PERIOD_DAYS:
        return GuaranteeEvaluation(
            eligible=True, period_started_at=period_start, days_into_period=days_in,
            average_completion_rate=None, threshold=GUARANTEE_COMPLETION_THRESHOLD,
            triggered=False, already_extended=already, can_extend=False,
            note=f"Henüz {days_in}/60 gün — değerlendirme zamanı gelmedi",
        )

    # 60 gün geçmiş — kurum geneli tamamlama oranını hesapla
    cutoff = now - timedelta(days=GUARANTEE_PERIOD_DAYS)
    student_ids = [
        u.id for u in db.query(User).filter(
            User.institution_id == institution.id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
        ).all()
    ]
    if not student_ids:
        return GuaranteeEvaluation(
            eligible=True, period_started_at=period_start, days_into_period=days_in,
            average_completion_rate=None, threshold=GUARANTEE_COMPLETION_THRESHOLD,
            triggered=False, already_extended=already, can_extend=False,
            note="Kurum altında öğrenci yok — değerlendirme yapılamaz",
        )

    # Görev sayım: planlanan / tamamlanan
    planned = (
        db.query(Task)
        .filter(
            Task.student_id.in_(student_ids),
            Task.date >= cutoff.date(),
            Task.date <= now.date(),
        )
        .count()
    )
    completed = (
        db.query(Task)
        .filter(
            Task.student_id.in_(student_ids),
            Task.date >= cutoff.date(),
            Task.date <= now.date(),
            Task.status == TaskStatus.COMPLETED,
        )
        .count()
    )
    rate = (completed / planned) if planned > 0 else None

    triggered = rate is not None and rate < GUARANTEE_COMPLETION_THRESHOLD
    can_extend = triggered and not already

    return GuaranteeEvaluation(
        eligible=True, period_started_at=period_start, days_into_period=days_in,
        average_completion_rate=rate, threshold=GUARANTEE_COMPLETION_THRESHOLD,
        triggered=triggered, already_extended=already, can_extend=can_extend,
        note=(
            f"Tamamlama oranı %{(rate or 0)*100:.0f} "
            f"(eşik %{GUARANTEE_COMPLETION_THRESHOLD*100:.0f})"
        ) if rate is not None else "Yeterli veri yok",
    )


def apply_guarantee_extension(
    db: Session, *, institution: Institution,
    actor_user_id: int | None = None,
    note: str | None = None,
    autocommit: bool = True,
) -> Institution:
    """60g garantisini tetikleyen kuruma 1 ay uzatma uygula.

    period_end +30 gün, guarantee_extended_at=now (tek seferlik flag).
    """
    if institution.guarantee_extended_at is not None:
        # zaten uzatma yapılmış
        return institution

    now = datetime.now(timezone.utc)
    pe = _ensure_utc(institution.subscription_period_end)
    if pe is None:
        # Period_end yoksa şimdiden 30 gün set et
        new_pe = now + timedelta(days=GUARANTEE_EXTENSION_DAYS)
    else:
        new_pe = pe + timedelta(days=GUARANTEE_EXTENSION_DAYS)
    institution.subscription_period_end = new_pe
    institution.guarantee_extended_at = now

    entry = PlanChangeHistory(
        owner_type=PlanOwnerType.INSTITUTION,
        owner_id=institution.id,
        from_plan=institution.plan,
        to_plan=institution.plan,
        reason=PlanChangeReason.GUARANTEE_EXTEND,
        actor_user_id=actor_user_id,
        note=note or (
            f"60 gün performans garantisi tetiklendi — "
            f"period_end {GUARANTEE_EXTENSION_DAYS} gün uzatıldı"
        ),
    )
    db.add(entry)

    if autocommit:
        db.commit()
    else:
        db.flush()
    logger.info(
        "apply_guarantee_extension: inst=%s new_pe=%s",
        institution.id, new_pe.isoformat(),
    )
    return institution


# ---------------------------- Cron job'lar ----------------------------


def cron_resume_paused_subscriptions(
    db: Session, *, now: datetime | None = None,
) -> dict:
    """Cron: pause_until geçmiş kurumları otomatik resume et.

    Her gün 01:00 UTC tick — pause_until'i geçmiş kurumlar akademik yıla
    geri döner. İdempotent.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    counts = {"resumed": 0, "skipped_still_paused": 0}

    candidates = (
        db.query(Institution)
        .filter(
            Institution.subscription_kind == KIND_PAUSED,
            Institution.subscription_pause_until.isnot(None),
        )
        .all()
    )
    for inst in candidates:
        pu = _ensure_utc(inst.subscription_pause_until)
        if pu is None or pu > now:
            counts["skipped_still_paused"] += 1
            continue
        resume_from_pause(db, institution=inst, autocommit=False)
        counts["resumed"] += 1

    db.commit()
    logger.info("cron_resume_paused_subscriptions: %s", counts)
    return counts


def cron_evaluate_guarantees(
    db: Session, *, now: datetime | None = None,
) -> dict:
    """Cron: garanti aktif olan kurumları haftalık değerlendir, tetikleyenlere
    uzatma uygula.

    Haftada 1 kez (Pazartesi 06:00 UTC) — daha sık çalıştırmak boş sayım.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    counts = {"evaluated": 0, "extended": 0, "not_yet": 0, "skipped_already": 0}

    insts = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            Institution.performance_guarantee.is_(True),
        )
        .all()
    )
    for inst in insts:
        ev = evaluate_guarantee(db, institution=inst, now=now)
        counts["evaluated"] += 1
        if ev.already_extended:
            counts["skipped_already"] += 1
            continue
        if ev.can_extend:
            apply_guarantee_extension(
                db, institution=inst,
                note=ev.note + " — otomatik uzatma cron'u",
                autocommit=False,
            )
            counts["extended"] += 1
        else:
            counts["not_yet"] += 1

    db.commit()
    logger.info("cron_evaluate_guarantees: %s", counts)
    return counts
