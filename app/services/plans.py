"""Stage 9 (Faz 2) — Plan kataloğu + plan değişiklik servisi.

Tek sözlük: ETÜTKOÇ Plan Yapısı.

İki ayrı yol:
- Bireysel (B2C) bağımsız öğretmen için: 14 gün reverse trial → 'solo_free'
- Kurumsal (B2B) için: 30 gün pilot → 'institution_free' veya kurumsal plan

Plan kodları (User.plan veya Institution.plan değeri):
  Bireysel:    solo_trial · solo_free · solo_pro · solo_elite
  Kurumsal:    institution_trial · institution_free · etut_standart ·
               dershane_pro · enterprise

Add-on'lar plan'ın üzerine eklenir, planı değiştirmez.

Servis fonksiyonları:
- start_trial(user_or_institution): trial_ends_at set + post_trial_plan set
- expire_trials() cron: süresi dolmuş trial'ları post_trial_plan'a düşürür
- change_plan(...): manuel veya otomatik plan değişikliği + audit log
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models import (
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    PlanOwnerType,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# ---------------------------- Plan kataloğu ----------------------------


# Bireysel bağımsız öğretmen yolu (B2C self-serve)
SOLO_TRIAL = "solo_trial"
SOLO_FREE = "solo_free"
SOLO_PRO = "solo_pro"          # ≤10 öğrenci (Solo Başlangıç)
SOLO_ELITE = "solo_elite"     # ≤25 öğrenci (Solo)
SOLO_UNLIMITED = "solo_unlimited"  # 25+ sınırsız (Solo Sınırsız)

# Kurumsal yol (B2B sözleşmeli)
INSTITUTION_TRIAL = "institution_trial"
INSTITUTION_FREE = "institution_free"
ETUT_STANDART = "etut_standart"
DERSHANE_PRO = "dershane_pro"
ENTERPRISE = "enterprise"


SOLO_PLANS = (SOLO_TRIAL, SOLO_FREE, SOLO_PRO, SOLO_ELITE, SOLO_UNLIMITED)
INSTITUTION_PLANS = (
    INSTITUTION_TRIAL, INSTITUTION_FREE, ETUT_STANDART,
    DERSHANE_PRO, ENTERPRISE,
)
ALL_PLANS = SOLO_PLANS + INSTITUTION_PLANS


# Trial süreleri (gün)
SOLO_TRIAL_DAYS = 14
INSTITUTION_TRIAL_DAYS = 30


@dataclass(frozen=True)
class PlanInfo:
    code: str
    label: str
    short_description: str
    long_description: str
    price_monthly_try: int          # 0 = ücretsiz; -1 = "Görüşme" (enterprise)
    price_yearly_try: int            # akademik yıl peşin (10 ay) — 0 yoksa
    audience: Literal["solo", "institution"]
    tier_rank: int                   # düşük = düşük tier
    features_included: list[str]
    features_excluded: list[str]
    cta_label: str                   # call-to-action butonu
    badge: str | None = None         # "🏆 En Popüler" gibi


PLAN_CATALOG: dict[str, PlanInfo] = {
    # ---------- BİREYSEL ----------
    SOLO_TRIAL: PlanInfo(
        code=SOLO_TRIAL,
        label="14 Günlük Pro Deneme",
        short_description="Tüm pro özellikler 14 gün ücretsiz",
        long_description=(
            "Yeni kayıtlarda otomatik aktive olur. 14 gün boyunca Solo Pro'nun "
            "tüm özellikleri sınırsızca açıktır. Süre sonunda otomatik olarak "
            "Solo Ücretsiz'e geçilir; eski raporların korunur."
        ),
        price_monthly_try=0,
        price_yearly_try=0,
        audience="solo",
        tier_rank=0,
        features_included=[
            "Tüm Solo Pro özellikleri",
            "Sınırsız öğrenci",
            "Yapay zeka şablon önerisi",
            "WhatsApp veli bildirim",
            "Haftalık raporlar",
        ],
        features_excluded=[],
        cta_label="14 Gün Ücretsiz Dene",
        badge="🎁 Hoş Geldin",
    ),
    SOLO_FREE: PlanInfo(
        code=SOLO_FREE,
        label="Solo Ücretsiz",
        short_description="3 öğrenciye kadar, manuel raporlama",
        long_description=(
            "Trial bittikten sonra varsayılan plan. En fazla 3 aktif öğrenci. "
            "Yapay zeka önerileri, WhatsApp veli bildirim ve veli portalı kapalı. "
            "Görev oluşturma, plan takibi, temel analiz açık. Asla bitmeyen ücretsiz tier."
        ),
        price_monthly_try=0,
        price_yearly_try=0,
        audience="solo",
        tier_rank=1,
        features_included=[
            "3 aktif öğrenci",
            "Görev planlama",
            "Temel analiz",
            "E-posta ile manuel rapor",
        ],
        features_excluded=[
            "Yapay zeka önerisi",
            "WhatsApp veli bildirimi",
            "Veli portalı",
            "Haftalık otomatik rapor",
        ],
        cta_label="Ücretsiz Devam Et",
    ),
    SOLO_PRO: PlanInfo(
        code=SOLO_PRO,
        label="Solo Başlangıç",
        short_description="10 öğrenciye kadar, AI dahil",
        long_description=(
            "Küçük ama düzenli büyüyen koçluk için. 10 aktif öğrenciye kadar, "
            "yapay zeka özellikleri + veli bildirimi + haftalık raporlar dahil."
        ),
        price_monthly_try=2500,
        price_yearly_try=25000,  # 10 ay (2 ay bedava)
        audience="solo",
        tier_rank=2,
        features_included=[
            "10 öğrenciye kadar",
            "Yapay zeka özellikleri",
            "Veli bildirimi + deneme/net grafiği",
            "Haftalık otomatik raporlar",
            "Tüm temel özellikler",
        ],
        features_excluded=[
            "Sınırsız öğrenci",
            "Veli portalı",
        ],
        cta_label="Solo Başlangıç'a Geç",
    ),
    SOLO_ELITE: PlanInfo(
        code=SOLO_ELITE,
        label="Solo",
        short_description="25 öğrenciye kadar, AI dahil",
        long_description=(
            "Yoğun, yapay zekâ kullanan koç için en popüler plan. 25 aktif "
            "öğrenciye kadar, tüm yapay zeka özellikleri + veli bildirimi + "
            "haftalık/günlük raporlar + öncelikli destek."
        ),
        price_monthly_try=5000,
        price_yearly_try=50000,  # 10 ay
        audience="solo",
        tier_rank=3,
        features_included=[
            "25 öğrenciye kadar",
            "Tüm yapay zeka özellikleri",
            "Veli bildirimi + deneme/net grafiği",
            "Haftalık + günlük raporlar",
            "Öncelikli destek",
        ],
        features_excluded=["Sınırsız öğrenci"],
        cta_label="Solo'ya Yükselt",
        badge="⭐ En Popüler",
    ),
    SOLO_UNLIMITED: PlanInfo(
        code=SOLO_UNLIMITED,
        label="Solo Sınırsız",
        short_description="Sınırsız öğrenci, tüm özellikler",
        long_description=(
            "Mini-kurum ölçeğindeki güç koçu için. Sınırsız öğrenci, tüm yapay "
            "zeka özellikleri, veli bildirimi, haftalık/günlük raporlar, öncelikli destek."
        ),
        price_monthly_try=7500,
        price_yearly_try=75000,  # 10 ay
        audience="solo",
        tier_rank=4,
        features_included=[
            "Sınırsız öğrenci",
            "Tüm yapay zeka özellikleri",
            "Veli bildirimi + deneme/net grafiği",
            "Haftalık + günlük raporlar",
            "Öncelikli destek",
        ],
        features_excluded=[],
        cta_label="Sınırsız'a Yükselt",
    ),

    # ---------- KURUMSAL ----------
    INSTITUTION_TRIAL: PlanInfo(
        code=INSTITUTION_TRIAL,
        label="30 Günlük Pilot",
        short_description="CSM destekli kurumsal deneme",
        long_description=(
            "Kurum başvurularda tam özellik açık 30 gün pilot süreç. ETÜTKOÇ ekibi "
            "kurulum + öğretmen eğitimi + kuruma özel raporlama desteği sağlar. "
            "Pilot sonunda kurum kararına göre Etüt Standart veya yukarı plana geçilir."
        ),
        price_monthly_try=0,
        price_yearly_try=0,
        audience="institution",
        tier_rank=0,
        features_included=[
            "30 gün full pro deneyim",
            "CSM destekli onboarding",
            "Sınırsız öğretmen+öğrenci",
            "Tüm yapay zeka + WhatsApp",
            "Pilot sonu özel rapor",
        ],
        features_excluded=[],
        cta_label="Pilot Başvurusu",
        badge="🚀 30 Gün Ücretsiz",
    ),
    INSTITUTION_FREE: PlanInfo(
        code=INSTITUTION_FREE,
        label="Kurum Tanıma",
        short_description="Pilot bittikten sonra ücretsiz tanıma planı",
        long_description=(
            "Pilot bittikten sonra varsayılan plan. 2 öğretmen, 20 öğrenciye kadar. "
            "Tanıma amaçlı; kurumsal alış kararı vermeden önce kullanıcılarınızı "
            "sisteme alıştırmak için ideal."
        ),
        price_monthly_try=0,
        price_yearly_try=0,
        audience="institution",
        tier_rank=1,
        features_included=[
            "2 öğretmen + 20 öğrenci",
            "Görev planlama + temel analiz",
            "Manuel raporlama",
        ],
        features_excluded=[
            "Yapay zeka önerisi",
            "WhatsApp veli bildirimi",
            "Haftalık otomatik raporlar",
        ],
        cta_label="Kurum Tanıma'da Devam",
    ),
    ETUT_STANDART: PlanInfo(
        code=ETUT_STANDART,
        label="Etüt Standart",
        short_description="2-10 koç, 300 öğrenciye kadar",
        long_description=(
            "Etüt merkezleri ve butik dershaneler için en uygun plan. "
            "Toplam aylık 10.000 ₺ (≤10 koç). "
            "Yapay zeka, WhatsApp veli bildirimi, haftalık raporlar dahil."
        ),
        price_monthly_try=10000,   # toplam kademe (≤10 koç)
        price_yearly_try=100000,   # 10 ay (2 ay bedava)
        audience="institution",
        tier_rank=2,
        features_included=[
            "2-10 koç, 300 öğrenciye kadar",
            "Yapay zeka önerisi",
            "WhatsApp veli bildirimi",
            "Haftalık + aylık raporlar",
            "Risk paneli + kohort karşılaştırma",
            "Öğrenci ortak havuz krediler",
        ],
        features_excluded=[
            "Çok şube yönetimi",
            "Özel sözleşme",
        ],
        cta_label="Etüt Standart'a Geç",
        badge="🏫 En Popüler",
    ),
    DERSHANE_PRO: PlanInfo(
        code=DERSHANE_PRO,
        label="Dershane Pro",
        short_description="11-50 koç, 1500 öğrenciye kadar",
        long_description=(
            "Büyük dershane ve eğitim kurumları için. Toplam aylık 30.000 ₺ "
            "(≤50 koç). Akademik yıl uyumu (Eylül-Haziran 10 ay peşin) + yaz "
            "pause seçeneği + öncelikli destek. Hacim avantajı + 60 gün garanti."
        ),
        price_monthly_try=30000,   # toplam kademe (≤50 koç)
        price_yearly_try=300000,   # 10 ay (2 ay bedava)
        audience="institution",
        tier_rank=3,
        features_included=[
            "11-50 koç, 1500 öğrenciye kadar",
            "Akademik yıl planı (10 ay peşin)",
            "Yaz pause seçeneği",
            "Tüm Etüt Standart özellikleri",
            "60 gün performans garantisi",
            "Öncelikli destek (4 saat içinde dönüş)",
            "Aylık özel raporlama",
        ],
        features_excluded=[
            "White-label markalama",
        ],
        cta_label="Görüşme Talep Et",
    ),
    ENTERPRISE: PlanInfo(
        code=ENTERPRISE,
        label="Kurumsal",
        short_description="50+ koç veya zincir kurumlar — özel teklif",
        long_description=(
            "Çok şube, franchise, anlaşmalı okul gibi yapılar için özel sözleşme. "
            "White-label markalama, kuruma özel entegrasyon, sınırsız kapasite, "
            "atanmış müşteri başarı yöneticisi."
        ),
        price_monthly_try=-1,   # "Görüşme"
        price_yearly_try=-1,
        audience="institution",
        tier_rank=4,
        features_included=[
            "Sınırsız her şey",
            "White-label markalama",
            "Çok şube yönetimi",
            "Özel sözleşme + SLA",
            "Atanmış müşteri başarı yöneticisi",
            "Kuruma özel entegrasyon (ödeme, MEB, vs.)",
        ],
        features_excluded=[],
        cta_label="Bizimle Görüşün",
    ),
}


def get_plan_info(plan_code: str) -> PlanInfo | None:
    return PLAN_CATALOG.get(plan_code)


def is_solo_plan(plan_code: str) -> bool:
    return plan_code in SOLO_PLANS


def is_institution_plan(plan_code: str) -> bool:
    return plan_code in INSTITUTION_PLANS


def is_paid_plan(plan_code: str) -> bool:
    """Bu plan ücretli mi (trial hariç)."""
    info = get_plan_info(plan_code)
    if info is None:
        return False
    return info.price_monthly_try != 0


def is_trial_plan(plan_code: str) -> bool:
    return plan_code in (SOLO_TRIAL, INSTITUTION_TRIAL)


def effective_plan_for_user(db: Session, user: User) -> str:
    """Kullanıcının geçerli plan kodu. Kurumlu → Institution.plan; bağımsız → user.plan."""
    if user.institution_id is not None:
        inst = db.get(Institution, user.institution_id)
        return inst.plan if inst else INSTITUTION_FREE
    return user.plan or SOLO_FREE


def ai_premium_allowed(db: Session, user: User) -> bool:
    """Pahalı AI özellikleri (foto/ses yakalama + koçluk içgörüsü) bu kullanıcıya açık mı.

    KURAL (kullanıcı 2026-05-22): ÜCRETLİ planlar + AKTİF solo deneme.
    - Ücretli plan → açık.
    - Solo deneme (solo_trial, trial aktif) → açık ama 50 kredi tavanıyla sınırlı
      (PLAN_ALLOCATIONS["solo_trial"]); tükenince consume_credits 402 verir →
      kullanıcı ücretliye yönlendirilir. Deneme bitince (solo_free) → KAPALI.
    - Ücretsiz (solo_free) / kurum ücretsiz → KAPALI.
    """
    plan = effective_plan_for_user(db, user)
    if is_paid_plan(plan):
        return True
    if plan == SOLO_TRIAL and is_trial_active(user):
        return True
    return False


# ---------------------------- Solo plan kotaları ----------------------------


# Bağımsız öğretmen plan'larında aktif öğrenci limiti.
# -1 = sınırsız, 0 = kapalı.
SOLO_STUDENT_LIMITS: dict[str, int] = {
    SOLO_TRIAL: -1,        # trial sırasında pro deneyim — sınırsız (kredi tavanlı)
    SOLO_FREE: 3,          # ücretsiz tier — 3 öğrenci (sert sınır)
    SOLO_PRO: 10,          # Solo Başlangıç — ≤10 öğrenci (sert sınır)
    SOLO_ELITE: 25,        # Solo — ≤25 öğrenci (sert sınır)
    SOLO_UNLIMITED: -1,    # Solo Sınırsız — sınırsız
}


def solo_student_limit(plan_code: str) -> int:
    """Solo plana göre aktif öğrenci limiti. Tanımsız plan → SOLO_FREE."""
    return SOLO_STUDENT_LIMITS.get(plan_code, SOLO_STUDENT_LIMITS[SOLO_FREE])


def count_solo_students(db: Session, *, teacher_id: int) -> int:
    """Bağımsız öğretmenin aktif öğrencileri (institution_id IS NULL ve
    teacher_id eşleşen kayıt sayısı)."""
    return (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.institution_id.is_(None),
            User.teacher_id == teacher_id,
        )
        .count()
    )


def reactivate_solo_students(db: Session, coach: User, *, autocommit: bool = False) -> int:
    """Bağımsız koçun TÜM pasif öğrencilerini yeniden aktif yapar.

    Paket yükseltme / abonelik aktivasyonunda çağrılır: ödeme duvarındayken
    (ücretsiz + limit aşımı / past_due) koç limite inmek için öğrencilerini
    pasifleştirmiş olabilir; ücretli/aktif duruma geçince banner'da verilen söz
    gereği bunlar OTOMATİK geri açılır. Ücretli planda öğrenci limiti yok
    (band-fiyatlı) → kota engeli oluşmaz. Aktif öğrenciye dokunmaz (idempotent).
    Kaç öğrencinin yeniden aktifleştiğini döndürür.
    """
    if coach.role != UserRole.TEACHER or coach.institution_id is not None:
        return 0
    passive = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.is_active.is_(False),
            User.institution_id.is_(None),
            User.teacher_id == coach.id,
        )
        .all()
    )
    for s in passive:
        s.is_active = True
    if autocommit and passive:
        db.commit()
    return len(passive)


@dataclass
class SoloQuotaCheckResult:
    """Solo öğrenci kotası kontrolünün ayrıntılı sonucu — UI için."""
    ok: bool
    plan_code: str
    plan_label: str
    current: int
    limit: int                  # -1 = sınırsız
    requested: int              # 1 yeni veya CSV import ise toplu
    upgrade_target_code: str | None     # Önerilen yükseltme planı


def check_solo_student_quota(
    db: Session, *, teacher: User, extra_count: int = 1,
) -> SoloQuotaCheckResult:
    """Bağımsız öğretmenin yeni öğrenci ekleyebileceğini kontrol et.

    Bu kontrol exception fırlatmaz — UI'a SoloQuotaCheckResult döner. Çağıran
    taraf .ok False ise upgrade prompt'ü render eder (raise yerine).
    """
    plan_code = teacher.plan or SOLO_FREE
    limit = solo_student_limit(plan_code)
    info = get_plan_info(plan_code)
    plan_label = info.label if info else plan_code

    current = count_solo_students(db, teacher_id=teacher.id)
    if limit == -1:
        return SoloQuotaCheckResult(
            ok=True, plan_code=plan_code, plan_label=plan_label,
            current=current, limit=-1, requested=extra_count,
            upgrade_target_code=None,
        )

    after = current + extra_count
    target = None
    if plan_code == SOLO_FREE:
        target = SOLO_PRO
    elif plan_code == SOLO_PRO:
        target = SOLO_ELITE
    return SoloQuotaCheckResult(
        ok=(after <= limit),
        plan_code=plan_code, plan_label=plan_label,
        current=current, limit=limit, requested=extra_count,
        upgrade_target_code=target,
    )


# ---------------------------- Trial yönetimi ----------------------------


def start_solo_trial(
    db: Session, *, user: User, days: int = SOLO_TRIAL_DAYS,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> User:
    """Bağımsız öğretmen için 14 günlük reverse trial başlat.

    plan='solo_trial' set edilir, trial_ends_at=now+14d, post_trial_plan='solo_free'.
    """
    if user.institution_id is not None:
        raise ValueError(
            f"start_solo_trial: kurumlu kullanıcı (#{user.id}) — bireysel trial uygun değil"
        )
    now = datetime.now(timezone.utc)
    from_plan = user.plan
    user.plan = SOLO_TRIAL
    user.trial_ends_at = now + timedelta(days=days)
    user.post_trial_plan = SOLO_FREE

    _log_change(
        db, owner_type=PlanOwnerType.USER, owner_id=user.id,
        from_plan=from_plan, to_plan=SOLO_TRIAL,
        reason=PlanChangeReason.SIGNUP,
        actor_user_id=actor_user_id or user.id,
        note=f"{days} günlük reverse trial başlatıldı (Solo Pro özellikleri)",
    )
    if autocommit:
        db.commit()
    else:
        db.flush()
    return user


def start_institution_trial(
    db: Session, *, institution: Institution, days: int = INSTITUTION_TRIAL_DAYS,
    actor_user_id: int | None = None, autocommit: bool = True,
) -> Institution:
    """Kurum için 30 günlük pilot başlat."""
    now = datetime.now(timezone.utc)
    from_plan = institution.plan
    institution.plan = INSTITUTION_TRIAL
    institution.trial_ends_at = now + timedelta(days=days)
    institution.post_trial_plan = INSTITUTION_FREE

    _log_change(
        db, owner_type=PlanOwnerType.INSTITUTION, owner_id=institution.id,
        from_plan=from_plan, to_plan=INSTITUTION_TRIAL,
        reason=PlanChangeReason.SIGNUP,
        actor_user_id=actor_user_id,
        note=f"{days} günlük pilot süreci başlatıldı",
    )
    if autocommit:
        db.commit()
    else:
        db.flush()
    return institution


def trial_days_left(*, owner: User | Institution, now: datetime | None = None) -> int | None:
    """Kalan trial gün sayısı. None = trial yok / bitmiş."""
    if now is None:
        now = datetime.now(timezone.utc)
    ends = owner.trial_ends_at
    if ends is None:
        return None
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    if ends <= now:
        return 0
    return max(0, (ends - now).days + (1 if (ends - now).seconds > 0 else 0))


def is_trial_active(owner: User | Institution, now: datetime | None = None) -> bool:
    """Trial şu an aktif mi?"""
    if now is None:
        now = datetime.now(timezone.utc)
    ends = owner.trial_ends_at
    if ends is None:
        return False
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    return ends > now


def compute_trial_banner(
    db: Session, *, user: User, now: datetime | None = None,
) -> dict | None:
    """Global trial countdown banner için context.

    Sahip belirleme:
    - Kurumlu kullanıcı (institution_id NOT NULL) → kurum trial'ı görünür
      (kurum üyeleri pilot süresinden haberdar olsun)
    - Bağımsız öğretmen (TEACHER + institution_id NULL) → kendi trial'ı
    - Diğer (super_admin, public sayfa öğrenci) → None

    Dönüş:
        {
            "kind": "user" | "institution",
            "days_left": int,        # 0..30
            "plan_code": "solo_trial" | "institution_trial",
            "plan_label": "14 Günlük Pro Deneme" | "30 Günlük Pilot",
            "post_trial_label": "Solo Ücretsiz" | "Kurum Tanıma",
            "is_critical": bool,     # son 3 günde mi? (kırmızı uyarı)
        }
    None döndüğünde banner gösterilmez.
    """
    if user is None or not user.is_active:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    if user.institution_id is not None:
        inst = db.get(Institution, user.institution_id)
        if inst is None or not is_trial_active(inst, now):
            return None
        days = trial_days_left(owner=inst, now=now) or 0
        info = get_plan_info(inst.plan)
        post_info = get_plan_info(inst.post_trial_plan or INSTITUTION_FREE)
        return {
            "kind": "institution",
            "days_left": days,
            "plan_code": inst.plan,
            "plan_label": info.label if info else inst.plan,
            "post_trial_label": post_info.label if post_info else "Kurum Tanıma",
            "is_critical": days <= 3,
        }

    # Bağımsız öğretmen
    if user.role == UserRole.TEACHER and user.institution_id is None:
        if not is_trial_active(user, now):
            return None
        days = trial_days_left(owner=user, now=now) or 0
        info = get_plan_info(user.plan)
        post_info = get_plan_info(user.post_trial_plan or SOLO_FREE)
        return {
            "kind": "user",
            "days_left": days,
            "plan_code": user.plan,
            "plan_label": info.label if info else user.plan,
            "post_trial_label": post_info.label if post_info else "Solo Ücretsiz",
            "is_critical": days <= 3,
        }

    return None


def expire_trials(db: Session, *, now: datetime | None = None) -> dict:
    """Cron: süresi dolmuş trial'ları post_trial_plan'a düşürür.

    Hem User (bağımsız öğretmen) hem Institution (kurum pilot) için çalışır.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    counts: dict = {"users_expired": 0, "institutions_expired": 0, "expired_user_ids": []}

    # Bağımsız öğretmen trial'ları
    expired_users = (
        db.query(User)
        .filter(
            User.plan == SOLO_TRIAL,
            User.trial_ends_at.isnot(None),
            User.trial_ends_at <= now,
        )
        .all()
    )
    for u in expired_users:
        target = u.post_trial_plan or SOLO_FREE
        from_plan = u.plan
        u.plan = target
        # trial_ends_at'i siliyoruz; post_trial_plan referans için kalsın
        u.trial_ends_at = None
        _log_change(
            db, owner_type=PlanOwnerType.USER, owner_id=u.id,
            from_plan=from_plan, to_plan=target,
            reason=PlanChangeReason.TRIAL_EXPIRED,
            note="14 günlük trial bitti — Solo Ücretsiz'e geçildi",
        )
        counts["users_expired"] += 1
        counts["expired_user_ids"].append(u.id)

    # Kurum trial'ları
    expired_insts = (
        db.query(Institution)
        .filter(
            Institution.plan == INSTITUTION_TRIAL,
            Institution.trial_ends_at.isnot(None),
            Institution.trial_ends_at <= now,
        )
        .all()
    )
    for i in expired_insts:
        target = i.post_trial_plan or INSTITUTION_FREE
        from_plan = i.plan
        i.plan = target
        i.trial_ends_at = None
        _log_change(
            db, owner_type=PlanOwnerType.INSTITUTION, owner_id=i.id,
            from_plan=from_plan, to_plan=target,
            reason=PlanChangeReason.TRIAL_EXPIRED,
            note="30 günlük pilot bitti — Kurum Tanıma'ya geçildi",
        )
        counts["institutions_expired"] += 1

    db.commit()
    logger.info("expire_trials: %s", counts)
    return counts


def solo_trial_status(
    db: Session, *, user: User, now: datetime | None = None,
) -> dict:
    """Bağımsız koç trial/ödeme-duvarı durumu — Next.js banner için.

    Kurumlu öğretmen / diğer roller → is_solo=False (banner gösterilmez).
    paywall = ücretsiz plana düşmüş + öğrenci limiti aşılmış (deneme bitti,
    fazla öğrenci) → aktif koçluk salt-okunur olmalı.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    is_solo = user.role == UserRole.TEACHER and user.institution_id is None
    if not is_solo:
        return {
            "is_solo": False, "plan_code": effective_plan_for_user(db, user),
            "plan_label": "", "trial_active": False, "days_left": None,
            "trial_critical": False, "student_count": 0, "student_limit": -1,
            "over_limit": False, "paywall": False, "upgrade_target": None,
        }
    plan = user.plan or SOLO_FREE
    info = get_plan_info(plan)
    active = is_trial_active(user, now)
    days_left = trial_days_left(owner=user, now=now)
    count = count_solo_students(db, teacher_id=user.id)
    limit = solo_student_limit(plan)
    over_limit = (limit != -1 and count > limit)
    sub_status = getattr(user, "subscription_status", None)
    past_due = (sub_status == "past_due")
    # Ödeme duvarı: ücretsiz + limit aşıldı VEYA abonelik yenilenmedi (past_due).
    paywall = (plan == SOLO_FREE and over_limit) or past_due
    trial_critical = (active and days_left is not None and days_left <= 3)
    return {
        "is_solo": True,
        "plan_code": plan,
        "plan_label": info.label if info else plan,
        "trial_active": active,
        "days_left": days_left,
        "trial_critical": trial_critical,
        "student_count": count,
        "student_limit": limit,
        "over_limit": over_limit,
        "paywall": paywall,
        "subscription_status": sub_status,
        "past_due": past_due,
        "upgrade_target": SOLO_PRO if plan in (SOLO_FREE, SOLO_TRIAL) else None,
    }


# ---------------------------- Plan değişiklik ----------------------------


def _refresh_current_period_allocation(
    db: Session, *,
    owner_type: PlanOwnerType,
    owner_id: int,
    new_plan: str,
) -> None:
    """Plan değişikliğinden sonra MEVCUT periyodun CreditAccount'unu yeni plana çek.

    BUG (2026-05-26 kullanıcı bildirdi): ETUTKOC plan=free → etut_standart
    yapıldı; PLAN_ALLOCATIONS["etut_standart"] = 10000. AMA mevcut Mayıs
    period'un CreditAccount.allocated_credits=50 olarak donmuş kaldı (eski
    plan_code='free'). Kullanıcı "kalan -6" gördü (eskisinin aşımı), yeni
    plan değerinden faydalanamadı.

    Çözüm: change_plan sonrası mevcut period varsa plan_code + allocated_credits
    güncellenir. Yoksa (henüz get_or_create_account çağrılmamış) atlanır —
    bir sonraki çağrı yeni plana göre yaratır.

    Davranış:
      - Upgrade: allocated yükselir, used korunur, remaining artar. ✓
      - Downgrade: allocated düşer; eğer used > new_alloc, remaining negatife
        düşer (kullanıcı zaten daha az kotaya geçti — kabul).
    """
    from app.services.credits import current_period, PLAN_ALLOCATIONS
    from app.models import CreditAccount, UsageOwnerType

    new_alloc = PLAN_ALLOCATIONS.get(new_plan)
    if new_alloc is None:
        return  # bilinmeyen plan kodu — defensif atla

    usage_owner_type = (
        UsageOwnerType.INSTITUTION
        if owner_type == PlanOwnerType.INSTITUTION
        else UsageOwnerType.USER
    )
    period = current_period()
    acc = (
        db.query(CreditAccount)
        .filter(
            CreditAccount.owner_type == usage_owner_type,
            CreditAccount.owner_id == owner_id,
            CreditAccount.period_year_month == period,
        )
        .first()
    )
    if acc is None:
        return  # mevcut period kaydı yok; sıradaki get_or_create yeni plan'la oluşturur
    acc.plan_code = new_plan
    acc.allocated_credits = new_alloc
    db.flush()


def change_plan(
    db: Session, *,
    owner_type: PlanOwnerType,
    owner_id: int,
    new_plan: str,
    reason: PlanChangeReason,
    actor_user_id: int | None = None,
    note: str | None = None,
    autocommit: bool = True,
) -> User | Institution | None:
    """Plan değişikliği + audit log + mevcut periyodun kredisini yeni plana çek."""
    if new_plan not in ALL_PLANS:
        raise ValueError(f"Bilinmeyen plan: {new_plan}")

    if owner_type == PlanOwnerType.USER:
        owner = db.get(User, owner_id)
    else:
        owner = db.get(Institution, owner_id)
    if owner is None:
        return None

    from_plan = owner.plan
    if from_plan == new_plan:
        return owner   # değişiklik yok

    owner.plan = new_plan
    # Bağımsız koç ücretli plana geçince deneme biter — trial_ends_at temizlenir
    # (yoksa is_trial_active True kalır → /teacher/plan + banner "deneme" sanır).
    if owner_type == PlanOwnerType.USER and is_paid_plan(new_plan):
        owner.trial_ends_at = None

    # MEVCUT periyodun CreditAccount'unu yeni plan kotasına senkronla.
    # Aksi halde plan yükseltilse bile bu ayın allocated_credits eski plan'da
    # kalır (bug 2026-05-26 ETUTKOC vakası).
    _refresh_current_period_allocation(
        db, owner_type=owner_type, owner_id=owner_id, new_plan=new_plan,
    )

    _log_change(
        db, owner_type=owner_type, owner_id=owner_id,
        from_plan=from_plan, to_plan=new_plan, reason=reason,
        actor_user_id=actor_user_id, note=note,
    )
    if autocommit:
        db.commit()
    else:
        db.flush()
    return owner


def _log_change(
    db: Session, *,
    owner_type: PlanOwnerType, owner_id: int,
    from_plan: str | None, to_plan: str,
    reason: PlanChangeReason,
    actor_user_id: int | None = None,
    note: str | None = None,
) -> PlanChangeHistory:
    entry = PlanChangeHistory(
        owner_type=owner_type,
        owner_id=owner_id,
        from_plan=from_plan,
        to_plan=to_plan,
        reason=reason,
        actor_user_id=actor_user_id,
        note=note,
    )
    db.add(entry)
    db.flush()
    return entry


def get_plan_history(
    db: Session, *, owner_type: PlanOwnerType, owner_id: int, limit: int = 50,
) -> list[PlanChangeHistory]:
    return (
        db.query(PlanChangeHistory)
        .filter(
            PlanChangeHistory.owner_type == owner_type,
            PlanChangeHistory.owner_id == owner_id,
        )
        .order_by(PlanChangeHistory.occurred_at.desc())
        .limit(limit)
        .all()
    )
