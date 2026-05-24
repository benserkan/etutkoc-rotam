"""Stage 8 — Kurum kuotaları servisi.

Plan başına default + per-kurum override mantığı.

Tipik kullanım:
    from app.services.quotas import check_quota_for_create, QuotaExceeded
    try:
        check_quota_for_create(db, institution=inst, quota_key="students")
    except QuotaExceeded as e:
        return error_response(e.message)
    # ... yeni kayıt oluştur

Anlık sayım: kurum scope'unda aktif (is_active=True) kullanıcı sayısı
sayılır. Pasif kullanıcı kotaya dahil değil — kullanıcıyı silmek yerine
deaktive eden müşteriler yer açabilsin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    InstitutionQuotaOverride,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# ---------------------------- Plan default'ları ----------------------------


# Plan başına anlık entity limitleri.
# -1 = sınırsız, 0 = kapalı (oluşturulamaz)
# Kurum plan kotaları — pricing.py institution_tiers ile UYUMLU (tek model):
#   teachers = tier max_coaches · students = max_coaches × students_per_coach(30)
#   institution_free: 2 öğretmen / 20 öğrenci (pricing free) · enterprise: sınırsız.
# NOT: anahtarlar GERÇEK plan kodlarıdır (eski free/starter/professional STALE idi
# → ücretli kurumlar yanlışlıkla free'ye düşüyordu; düzeltildi).
PLAN_QUOTAS: dict[str, dict[str, int]] = {
    "institution_free": {"teachers": 2, "students": 20, "institution_admins": 1},
    "institution_trial": {"teachers": 10, "students": 300, "institution_admins": 3},
    "etut_standart": {"teachers": 10, "students": 300, "institution_admins": 3},
    "dershane_pro": {"teachers": 50, "students": 1500, "institution_admins": 5},
    "enterprise": {"teachers": -1, "students": -1, "institution_admins": -1},
    # Geriye uyum (eski anahtar) — institution_free ile aynı.
    "free": {"teachers": 2, "students": 20, "institution_admins": 1},
}

QUOTA_KEYS: tuple[str, ...] = ("teachers", "students", "institution_admins")

QUOTA_LABELS_TR = {
    "teachers": "Öğretmen",
    "students": "Öğrenci",
    "institution_admins": "Kurum Yöneticisi",
}

# Kullanıcının %80'inde uyarı eşiği (UI için)
WARN_PCT = 80


# ---------------------------- Hata sınıfı ----------------------------


class QuotaExceeded(Exception):
    """Kurum kuotası aşıldı — yeni kayıt oluşturulamaz."""
    def __init__(
        self, *, quota_key: str, limit: int, current: int,
        institution_name: str = "",
    ):
        self.quota_key = quota_key
        self.limit = limit
        self.current = current
        label = QUOTA_LABELS_TR.get(quota_key, quota_key)
        if limit == 0:
            self.message = (
                f"{label} eklemek için kuota kapalı (sıfır limit). "
                "Süper admin'den izin isteyin."
            )
        else:
            self.message = (
                f"{label} kotası ({limit}) doldu — şu an {current} kayıt mevcut. "
                "Pasif kayıtları silebilir veya plan yükseltebilirsiniz."
            )
        if institution_name:
            self.message = f"[{institution_name}] {self.message}"
        super().__init__(self.message)


# ---------------------------- Veri yapıları ----------------------------


@dataclass
class QuotaInfo:
    key: str
    label: str
    limit: int               # -1 = sınırsız, 0 = kapalı, N = sayı
    current: int
    pct: int                 # 0-100; sınırsızsa 0
    is_unlimited: bool
    is_at_limit: bool        # current >= limit (sınırsız ise False)
    is_warn: bool            # %80+ ama henüz dolmamış
    has_override: bool       # default değil, override aktif
    override_note: str | None = None


# ---------------------------- Limit + sayım ----------------------------


def _normalize_plan(plan: str | None) -> str:
    """Bilinmeyen plan → 'institution_free' fallback (defansif)."""
    if plan and plan in PLAN_QUOTAS:
        return plan
    return "institution_free"


def get_default_limit(plan: str, quota_key: str) -> int:
    """Plan için default kuota (override yokken)."""
    plan_norm = _normalize_plan(plan)
    return PLAN_QUOTAS.get(plan_norm, PLAN_QUOTAS["free"]).get(quota_key, 0)


def get_quota_limit(
    db: Session, *, institution: Institution, quota_key: str,
) -> tuple[int, bool, str | None]:
    """Etkin limit + override var mı + note döner.

    Returns: (limit_value, has_override, note)
    """
    override = (
        db.query(InstitutionQuotaOverride)
        .filter(
            InstitutionQuotaOverride.institution_id == institution.id,
            InstitutionQuotaOverride.quota_key == quota_key,
        )
        .first()
    )
    if override is not None:
        return (override.override_value, True, override.note)
    return (get_default_limit(institution.plan, quota_key), False, None)


def count_current_usage(
    db: Session, *, institution_id: int, quota_key: str,
) -> int:
    """Aktif kullanıcı sayısı — quota_key'e göre rol filtresi."""
    role_map = {
        "teachers": UserRole.TEACHER,
        "students": UserRole.STUDENT,
        "institution_admins": UserRole.INSTITUTION_ADMIN,
    }
    role = role_map.get(quota_key)
    if role is None:
        return 0
    n = (
        db.query(func.count(User.id))
        .filter(
            User.institution_id == institution_id,
            User.role == role,
            User.is_active.is_(True),
        )
        .scalar() or 0
    )
    return int(n)


# ---------------------------- Public API ----------------------------


def check_quota_for_create(
    db: Session, *, institution: Institution, quota_key: str,
    extra_count: int = 1,
) -> None:
    """Yeni N kayıt eklenebilir mi? Aşımsa QuotaExceeded fırlatır.

    extra_count: bu çağrıda kaç yeni kayıt oluşturulacak (toplu import için).
    """
    limit, _, _ = get_quota_limit(db, institution=institution, quota_key=quota_key)
    if limit == -1:
        return  # Sınırsız
    current = count_current_usage(
        db, institution_id=institution.id, quota_key=quota_key,
    )
    if current + extra_count > limit:
        raise QuotaExceeded(
            quota_key=quota_key,
            limit=limit,
            current=current,
            institution_name=institution.name,
        )


def get_quota_summary(
    db: Session, *, institution: Institution,
) -> list[QuotaInfo]:
    """Tüm kuotaların özeti — UI tablosu için."""
    out: list[QuotaInfo] = []
    for key in QUOTA_KEYS:
        limit, has_override, note = get_quota_limit(
            db, institution=institution, quota_key=key,
        )
        current = count_current_usage(
            db, institution_id=institution.id, quota_key=key,
        )
        is_unlimited = limit == -1
        if is_unlimited:
            pct = 0
            is_at = False
            is_warn = False
        elif limit == 0:
            pct = 100 if current == 0 else 999  # gösterim için
            is_at = current >= 0  # zaten kapalı
            is_warn = False
        else:
            pct = int(round(100 * current / limit)) if limit > 0 else 0
            is_at = current >= limit
            is_warn = (not is_at) and pct >= WARN_PCT

        out.append(QuotaInfo(
            key=key,
            label=QUOTA_LABELS_TR.get(key, key),
            limit=limit,
            current=current,
            pct=pct,
            is_unlimited=is_unlimited,
            is_at_limit=is_at,
            is_warn=is_warn,
            has_override=has_override,
            override_note=note,
        ))
    return out


def set_override(
    db: Session, *, institution_id: int, quota_key: str, override_value: int,
    note: str | None = None,
) -> InstitutionQuotaOverride:
    """Per-kurum override ekle veya güncelle."""
    if quota_key not in QUOTA_KEYS:
        raise ValueError(f"Bilinmeyen quota_key: {quota_key}")
    if override_value < -1:
        raise ValueError("override_value -1 (sınırsız), 0 (kapalı) veya pozitif olmalı")

    existing = (
        db.query(InstitutionQuotaOverride)
        .filter(
            InstitutionQuotaOverride.institution_id == institution_id,
            InstitutionQuotaOverride.quota_key == quota_key,
        )
        .first()
    )
    if existing:
        existing.override_value = override_value
        if note is not None:
            existing.note = note
        db.commit()
        return existing
    o = InstitutionQuotaOverride(
        institution_id=institution_id,
        quota_key=quota_key,
        override_value=override_value,
        note=note,
    )
    db.add(o)
    db.commit()
    return o


def remove_override(db: Session, override_id: int) -> bool:
    o = db.get(InstitutionQuotaOverride, override_id)
    if o is None:
        return False
    db.delete(o)
    db.commit()
    return True
