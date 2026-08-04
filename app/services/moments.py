"""Moment sağlık sistemi (Faz C, 2026-08-04 kullanıcı onaylı).

SORUN: bağlamsal uyarı/kartlar (deneme bitiyor bandı, ödeme duvarı, kredi
azaldı kartı...) her biri kendi koşuluyla dağınık yaşıyor; koşul/uç/render
kırılırsa KİMSE fark etmiyor (e-posta kesintisi dersi: 10 gün sessiz kaldı
çünkü ölçen alarm yoktu).

ÇÖZÜM (iki bacak):
1. GÖSTERİM İZİ — sinyali taşıyan API yanıtı üretilirken `record_moment`
   (best-effort, kullanıcı+moment+gün tekil) MomentEvent yazar.
2. SESSİZLİK TARAMASI — `silent_moment_report`: koşulu ŞU AN sağlayan VE
   panelde gerçekten gezinen (yüzeye göre: son 48s login / ilgili sayfayı
   ziyaret) ama son 48 saatte sinyal ALMAYAN kullanıcıları bulur. Sonuç
   alarm motorundaki `moment_silent` kuralını besler → süper admine
   push+panel+e-posta.

KAYIT (registry) — her moment:
  key       : moment_events.moment_key + alarm mesajındaki ad
  label     : insan-dili ad
  surface   : "global"  → sinyal her koç sayfasında çekilen /teacher/trial-status
              ile taşınır → "panelde gezdi" kanıtı son 48s login yeter.
              "plan_page" → sinyal yalnız /teacher/plan yanıtında taşınır →
              kanıt panel_visit_events'te teacher.plan ziyareti ister
              (sayfayı hiç açmayan koç için yanlış alarm üretmemek İÇİN).
  evaluate  : (db, user, now) -> bool — koşul ŞU AN sağlanıyor mu
              (endpoint'lerin kullandığı gerçek servislerle AYNI kaynaktan).

Yeni bağlamsal kart eklerken: (1) buraya kayıt ekle, (2) sinyali taşıyan
endpoint'e record_moment çağrısı koy, (3) scripts/test_moment_health.py'ye
senaryo ekle. Üçü birden yoksa kart "ölçüsüz" kalır — yasak.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MomentEvent, PanelVisitEvent, User, UserRole

logger = logging.getLogger(__name__)

# Sessizlik taraması penceresi: koşul dünden beri sağlanıyor + kullanıcı
# panelde gezdi ama sinyal yok → şüpheli. 48 saat, "dün gece deploy edildi,
# bugün kimse girmedi" tipi yanlış alarmları yumuşatır.
SILENT_WINDOW_HOURS = 48
# Tarama tavanı — koç sayısı büyürse tam tarama yerine ilk N aktif koç
# (log'a kırpma notu düşülür; sessiz kırpma yasak kuralı).
SCAN_CAP = 500


def _now() -> datetime:
    return datetime.now(timezone.utc)


def record_moment(
    db: Session, *, user_id: int, moment_key: str, now: datetime | None = None,
) -> None:
    """Sinyal sunuldu izi — günde bir kez, ASLA endpoint'i kırmaz.

    Çağıran endpoint'ler try/except'e sarmaz; burada yutulur (best-effort).
    """
    if now is None:
        now = _now()
    day = now.strftime("%Y-%m-%d")
    try:
        exists = (
            db.query(MomentEvent.id)
            .filter(
                MomentEvent.user_id == user_id,
                MomentEvent.moment_key == moment_key,
                MomentEvent.day == day,
            )
            .first()
        )
        if exists:
            return
        db.add(MomentEvent(
            user_id=user_id, moment_key=moment_key, day=day, occurred_at=now,
        ))
        db.flush()
    except Exception:
        # UNIQUE yarışı / geçici DB sorunu — sinyalin kendisi kayıttan önemli.
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("record_moment yutuldu (user=%s key=%s)", user_id, moment_key)


# ---------------------------- Registry ----------------------------


def _trial_status(db: Session, user: User, now: datetime) -> dict:
    from app.services.plans import solo_trial_status
    return solo_trial_status(db, user=user, now=now)


def _eval_trial_critical(db: Session, user: User, now: datetime) -> bool:
    st = _trial_status(db, user, now)
    return bool(st.get("trial_critical"))


def _eval_paywall(db: Session, user: User, now: datetime) -> bool:
    st = _trial_status(db, user, now)
    return bool(st.get("paywall"))


def _eval_payment_pending(db: Session, user: User, now: datetime) -> bool:
    st = _trial_status(db, user, now)
    return bool(st.get("payment_pending")) and not bool(st.get("paywall"))


def _eval_credit_low(db: Session, user: User, now: datetime) -> bool:
    """Aktif ücretli abone + kredi kullanımı >= %80 (CreditPackCard eşiği)."""
    from app.services.credits import CreditOwner, get_or_create_account
    from app.services.plans import is_paid_plan

    if not (
        is_paid_plan(user.plan or "")
        and getattr(user, "subscription_status", None) in ("active", "canceled")
        and getattr(user, "subscription_platform", None) != "app_store"
    ):
        return False
    acc = get_or_create_account(db, owner=CreditOwner.for_user(user))
    total = acc.total_allocated
    return total > 0 and (acc.used_credits or 0) / total >= 0.8


@dataclass(frozen=True)
class MomentSpec:
    key: str
    label: str
    surface: str  # "global" | "plan_page"
    evaluate: Callable[[Session, User, datetime], bool]
    note: str = ""


MOMENTS: list[MomentSpec] = [
    MomentSpec(
        key="trial_critical",
        label="Deneme bitiyor bandı (son 3 gün)",
        surface="global",
        evaluate=_eval_trial_critical,
        note="TrialBanner amber — /teacher/trial-status her koç sayfasında çekilir",
    ),
    MomentSpec(
        key="paywall",
        label="Ödeme duvarı bandı",
        surface="global",
        evaluate=_eval_paywall,
        note="TrialBanner rose — kapatılamaz",
    ),
    MomentSpec(
        key="payment_pending",
        label="Denemen bitti — ödemen bekleniyor bandı",
        surface="global",
        evaluate=_eval_payment_pending,
    ),
    MomentSpec(
        key="credit_low",
        label="Kredi azaldı — ek kredi kartı (/teacher/plan)",
        surface="plan_page",
        evaluate=_eval_credit_low,
        note="CreditPackCard yalnız Paket sayfasında — kanıt: teacher.plan ziyareti",
    ),
]

MOMENT_KEYS = {m.key for m in MOMENTS}


# ---------------------------- Sessizlik taraması ----------------------------


@dataclass
class SilentMomentRow:
    key: str
    label: str
    eligible_active: int          # koşul + panel kanıtı olan kullanıcı sayısı
    served: int                   # pencerede sinyal alan (aynı kümeden)
    silent_user_ids: list[int] = field(default_factory=list)


def _recent_login_user_ids(db: Session, cutoff: datetime) -> set[int]:
    rows = (
        db.query(User.id)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
            User.last_login_at >= cutoff,
        )
        .all()
    )
    return {r[0] for r in rows}


def _plan_page_visitor_ids(db: Session, cutoff: datetime) -> set[int]:
    rows = (
        db.query(PanelVisitEvent.user_id)
        .filter(
            PanelVisitEvent.route_key == "teacher.plan",
            PanelVisitEvent.created_at >= cutoff,
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _served_user_ids(db: Session, key: str, cutoff: datetime) -> set[int]:
    rows = (
        db.query(MomentEvent.user_id)
        .filter(
            MomentEvent.moment_key == key,
            MomentEvent.occurred_at >= cutoff,
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def silent_moment_report(
    db: Session, *, now: datetime | None = None,
) -> list[SilentMomentRow]:
    """Her moment için: koşulu sağlayan + panel kanıtı olan ama sinyal
    ALMAYAN kullanıcılar.

    Panel kanıtı olmadan sayılmaz — giriş yapmayan koç sinyal alamaz, bu
    sistem hatası değildir (yanlış alarm koruması).
    """
    if now is None:
        now = _now()
    cutoff = now - timedelta(hours=SILENT_WINDOW_HOURS)

    coaches = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.last_login_at.desc().nullslast())
        .limit(SCAN_CAP + 1)
        .all()
    )
    if len(coaches) > SCAN_CAP:
        logger.warning(
            "silent_moment_report: koç sayısı %d > tavan %d — en yeni "
            "girişliler tarandı (kırpıldı)", len(coaches), SCAN_CAP,
        )
        coaches = coaches[:SCAN_CAP]

    logged_in = _recent_login_user_ids(db, cutoff)
    plan_visitors = _plan_page_visitor_ids(db, cutoff)

    out: list[SilentMomentRow] = []
    for spec in MOMENTS:
        evidence = logged_in if spec.surface == "global" else plan_visitors
        eligible: set[int] = set()
        for u in coaches:
            if u.id not in evidence:
                continue
            try:
                if spec.evaluate(db, u, now):
                    eligible.add(u.id)
            except Exception:
                logger.exception(
                    "moment evaluate hata (key=%s user=%s)", spec.key, u.id,
                )
        served = _served_user_ids(db, spec.key, cutoff)
        silent = sorted(eligible - served)
        out.append(SilentMomentRow(
            key=spec.key, label=spec.label,
            eligible_active=len(eligible),
            served=len(eligible & served),
            silent_user_ids=silent,
        ))
    return out


def silent_total(db: Session, *, now: datetime | None = None) -> int:
    """Alarm motoru metriği: sessiz kalan (kullanıcı, moment) çifti toplamı."""
    report = silent_moment_report(db, now=now)
    return sum(len(r.silent_user_ids) for r in report)


def silent_summary_text(db: Session, *, now: datetime | None = None) -> str:
    """Alarm mesajı gövdesi — hangi moment kaç kullanıcıda sessiz."""
    rows = [r for r in silent_moment_report(db, now=now) if r.silent_user_ids]
    if not rows:
        return "Sessiz moment yok."
    parts = []
    for r in rows:
        ids = ", ".join(f"#{i}" for i in r.silent_user_ids[:5])
        extra = f" (+{len(r.silent_user_ids) - 5})" if len(r.silent_user_ids) > 5 else ""
        parts.append(f"{r.label}: {len(r.silent_user_ids)} kullanıcı [{ids}{extra}]")
    return " · ".join(parts)


def purge_old_events(db: Session, *, days: int = 90) -> int:
    """90 günden eski gösterim izlerini temizle (alarm değerlendirmesi
    sırasında best-effort çağrılır — ayrı cron gerekmez)."""
    cutoff = _now() - timedelta(days=days)
    n = (
        db.query(MomentEvent)
        .filter(MomentEvent.occurred_at < cutoff)
        .delete(synchronize_session=False)
    )
    if n:
        db.commit()
    return int(n)
