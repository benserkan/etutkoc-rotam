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
SOLO_PRO = "solo_pro"
SOLO_ELITE = "solo_elite"

# Kurumsal yol (B2B sözleşmeli)
INSTITUTION_TRIAL = "institution_trial"
INSTITUTION_FREE = "institution_free"
ETUT_STANDART = "etut_standart"
DERSHANE_PRO = "dershane_pro"
ENTERPRISE = "enterprise"


SOLO_PLANS = (SOLO_TRIAL, SOLO_FREE, SOLO_PRO, SOLO_ELITE)
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
        label="Solo Pro",
        short_description="15 öğrenciye kadar, AI + WhatsApp dahil",
        long_description=(
            "Aktif çalışan koçluk için en popüler plan. 15 aktif öğrenci, "
            "yapay zeka şablon önerisi (300 kredi/ay), WhatsApp veli bildirimi "
            "(500 mesaj/ay dahil), haftalık otomatik raporlar."
        ),
        price_monthly_try=299,
        price_yearly_try=2691,   # 9 × 299 (1 ay bonus)
        audience="solo",
        tier_rank=2,
        features_included=[
            "15 aktif öğrenci",
            "Yapay zeka önerisi (300 kredi/ay)",
            "WhatsApp veli bildirimi (500 mesaj/ay)",
            "Haftalık otomatik raporlar",
            "Tüm temel özellikler",
        ],
        features_excluded=[
            "Sınırsız öğrenci",
            "Veli portalı",
        ],
        cta_label="Solo Pro'ya Geç",
        badge="⭐ En Popüler",
    ),
    SOLO_ELITE: PlanInfo(
        code=SOLO_ELITE,
        label="Solo Elite",
        short_description="Sınırsız öğrenci, tüm özellikler",
        long_description=(
            "Yoğun talep alan, çok öğrencili koçlar için. Sınırsız öğrenci, "
            "yapay zeka 1500 kredi/ay, WhatsApp 1500 mesaj/ay, veli portalı dahil, "
            "60 gün performans garantisi opsiyonu."
        ),
        price_monthly_try=599,
        price_yearly_try=5391,   # 9 × 599
        audience="solo",
        tier_rank=3,
        features_included=[
            "Sınırsız öğrenci",
            "Yapay zeka önerisi (1500 kredi/ay)",
            "WhatsApp veli bildirimi (1500 mesaj/ay)",
            "Veli portalı dahil",
            "Haftalık + günlük raporlar",
            "Öncelikli destek",
            "60 gün performans garantisi",
        ],
        features_excluded=[],
        cta_label="Elite'e Yükselt",
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
        short_description="2-10 koç, 200 öğrenciye kadar",
        long_description=(
            "Etüt merkezleri ve butik dershaneler için en uygun plan. "
            "Koç başına aylık 199 ₺, öğrenci başına aylık 15 ₺. "
            "Yapay zeka, WhatsApp veli bildirimi, haftalık raporlar dahil."
        ),
        price_monthly_try=199,   # koç başı; öğrenci başı +15 ₺
        price_yearly_try=1791,   # 9 × 199
        audience="institution",
        tier_rank=2,
        features_included=[
            "2-10 koç, 200 öğrenciye kadar",
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
        short_description="10-50 koç, 2000 öğrenciye kadar",
        long_description=(
            "Büyük dershane ve eğitim kurumları için. Yıllık plan + akademik yıl "
            "uyumu (Eylül-Haziran 10 ay peşin) + yaz pause seçeneği + "
            "öncelikli destek. Toplu fiyat üzerinden indirim."
        ),
        price_monthly_try=2999,   # tahmini başlangıç
        price_yearly_try=26991,
        audience="institution",
        tier_rank=3,
        features_included=[
            "10-50 koç, 2000 öğrenciye kadar",
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

    KURAL (kullanıcı 2026-05-21): yalnız ÜCRETLİ planlar. trial/free → KAPALI
    (gerçek Anthropic/OpenAI maliyeti — deneme/ücretsiz kullanıcı yakamamalı).
    """
    return is_paid_plan(effective_plan_for_user(db, user))


# ---------------------------- Solo plan kotaları ----------------------------


# Bağımsız öğretmen plan'larında aktif öğrenci limiti.
# -1 = sınırsız, 0 = kapalı.
SOLO_STUDENT_LIMITS: dict[str, int] = {
    SOLO_TRIAL: -1,        # trial sırasında pro deneyim — sınırsız
    SOLO_FREE: 3,          # ücretsiz tier — 3 öğrenci (sert sınır)
    SOLO_PRO: -1,          # ücretli — öğrenci bandına göre fiyatlanır (sert sınır YOK)
    SOLO_ELITE: -1,        # sınırsız
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
    paywall = (plan == SOLO_FREE and over_limit)
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
        "upgrade_target": SOLO_PRO if plan in (SOLO_FREE, SOLO_TRIAL) else None,
    }


# ---------------------------- Plan değişiklik ----------------------------


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
    """Plan değişikliği + audit log."""
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
