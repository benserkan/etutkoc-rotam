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
              ile taşınır → kanıt: pencerede HERHANGİ bir teacher.* sayfa
              ziyareti (panel_visit_events).
              "plan_page" → sinyal yalnız /teacher/plan yanıtında taşınır →
              kanıt: pencerede teacher.plan ziyareti
              (sayfayı hiç açmayan koç için yanlış alarm üretmemek İÇİN).
  evaluate  : (db, user, now) -> bool — koşul ŞU AN sağlanıyor mu
              (endpoint'lerin kullandığı gerçek servislerle AYNI kaynaktan).
  since     : (db, user, now) -> datetime|None — koşul NE ZAMAN doğru oldu.
              Kullanıcının SON ziyareti bu andan ÖNCEYSE sinyali görmesi
              fiziksel olarak mümkün değildi → sessiz sayılmaz.

KANIT KURALI — NEDEN "login" DEĞİL (2026-08-09 saha bulgusu):
İlk sürüm kanıt olarak `last_login_at` son 48 saatte mi diye bakıyordu. Bu
TEK bir damga olduğundan, 7 Ağustos'ta girip çıkan koç 9 Ağustos'a kadar
"panelde aktif" sayıldı; bu aralıkta denemesi kritik eşiğe girdi, koç panelde
olmadığı için banner gösterilemedi ve sistem kendi kendine "gösterilmedi"
alarmı üretti (2 gün boyunca 4 yanlış alarm). Kanıt artık GERÇEK sayfa
ziyaretidir + koşulun doğru olduğu ana göre kesilir.

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


def _since_trial_critical(db: Session, user: User, now: datetime) -> datetime | None:
    """Deneme kritik eşiğine (son 3 gün) girdiği an."""
    end = getattr(user, "trial_ends_at", None)
    return (end - timedelta(days=3)) if end else None


def _since_trial_end(db: Session, user: User, now: datetime) -> datetime | None:
    """Deneme bitişi — paywall/ödeme-bekliyor bantları o an doğar."""
    return getattr(user, "trial_ends_at", None)


@dataclass(frozen=True)
class MomentSpec:
    key: str
    label: str
    surface: str  # "global" | "plan_page"
    evaluate: Callable[[Session, User, datetime], bool]
    note: str = ""
    # Koşulun doğru olduğu an; None → "pencerede ziyaret varsa yeter".
    since: Callable[[Session, User, datetime], datetime | None] | None = None


MOMENTS: list[MomentSpec] = [
    MomentSpec(
        key="trial_critical",
        label="Deneme bitiyor bandı (son 3 gün)",
        surface="global",
        evaluate=_eval_trial_critical,
        since=_since_trial_critical,
        note="TrialBanner amber — /teacher/trial-status her koç sayfasında çekilir",
    ),
    MomentSpec(
        key="paywall",
        label="Ödeme duvarı bandı",
        surface="global",
        evaluate=_eval_paywall,
        since=_since_trial_end,
        note="TrialBanner rose — kapatılamaz",
    ),
    MomentSpec(
        key="payment_pending",
        label="Denemen bitti — ödemen bekleniyor bandı",
        surface="global",
        evaluate=_eval_payment_pending,
        since=_since_trial_end,
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


def _last_visit_map(
    db: Session, cutoff: datetime, *, only_plan_page: bool = False,
) -> dict[int, datetime]:
    """user_id → pencere içindeki EN SON panel ziyareti.

    Kanıt olarak giriş damgası değil gerçek sayfa ziyareti kullanılır; ayrıca
    "en son ne zaman" bilgisi, koşulun doğru olduğu ana göre kesme yapmayı
    (bkz. MomentSpec.since) mümkün kılar.
    """
    q = db.query(
        PanelVisitEvent.user_id, func.max(PanelVisitEvent.created_at),
    ).filter(PanelVisitEvent.created_at >= cutoff)
    if only_plan_page:
        q = q.filter(PanelVisitEvent.route_key == "teacher.plan")
    else:
        q = q.filter(PanelVisitEvent.route_key.like("teacher.%"))
    return {uid: son for uid, son in q.group_by(PanelVisitEvent.user_id).all()}


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

    genel_ziyaret = _last_visit_map(db, cutoff)
    plan_ziyaret = _last_visit_map(db, cutoff, only_plan_page=True)

    out: list[SilentMomentRow] = []
    for spec in MOMENTS:
        ziyaret = genel_ziyaret if spec.surface == "global" else plan_ziyaret
        eligible: set[int] = set()
        for u in coaches:
            son_ziyaret = ziyaret.get(u.id)
            if son_ziyaret is None:
                continue  # panele hiç girmemiş — sinyali göremezdi
            try:
                if not spec.evaluate(db, u, now):
                    continue
                # Koşul, kullanıcının SON ziyaretinden SONRA doğru olduysa
                # sinyali görmesi mümkün değildi → sessiz sayma.
                if spec.since is not None:
                    basladi = spec.since(db, u, now)
                    if basladi is not None:
                        if basladi.tzinfo is None:
                            basladi = basladi.replace(tzinfo=timezone.utc)
                        sz = son_ziyaret
                        if sz.tzinfo is None:
                            sz = sz.replace(tzinfo=timezone.utc)
                        if sz < basladi:
                            continue
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

    # Ham "#87" süper admine hiçbir şey anlatmıyordu — ad + e-posta ile göster.
    tum_ids = {i for r in rows for i in r.silent_user_ids[:5]}
    adlar: dict[int, str] = {}
    if tum_ids:
        for u in db.query(User).filter(User.id.in_(tum_ids)).all():
            ad = (u.full_name or "").strip() or "(adsız)"
            adlar[u.id] = f"{ad} <{u.email}> (#{u.id})" if u.email else f"{ad} (#{u.id})"

    parts = []
    for r in rows:
        kim = ", ".join(adlar.get(i, f"#{i}") for i in r.silent_user_ids[:5])
        extra = f" (+{len(r.silent_user_ids) - 5} kişi daha)" if len(r.silent_user_ids) > 5 else ""
        parts.append(f"{r.label}: {len(r.silent_user_ids)} kullanıcı — {kim}{extra}")
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
