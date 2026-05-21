"""Üyelik/fiyat yapısı — TEK KAYNAK (single source of truth).

İki kitle:
- B2C bağımsız koç: öğrenci bandına göre fiyat (1-5/6-15/16-30/30+).
- B2B kurum: koç başına fiyat (koç sayısı tier'ına göre), her koç ≤30 öğrenci.

Bu modül `/pricing` sayfası + teacher Paket + süper admin ücret paneli + entitlement
tarafından okunur. Sayılar süper adminden düzenlenebilir olacak (M2 DB override);
şimdilik kod default + `_override` kancası. **Veri tutarlılığı: her yer buradan okur.**

KURAL: AI özellikleri yalnız ücretli planlarda; free → kapalı.
"""

from __future__ import annotations

from typing import Any

CURRENCY = "TRY"
# Yıllık abonelik: 10 ay öde, 12 ay kullan (2 ay bedava — akademik yıl ritmi).
ANNUAL_PAID_MONTHS = 10

SOLO_TRIAL_DAYS = 14
INSTITUTION_TRIAL_DAYS = 30

# ----------------------------- Solo (B2C) -----------------------------

SOLO_FREE_STUDENTS = 3

# Öğrenci bantları — üst sınıra kadar düz aylık ücret (₺/ay). Sıralı artan.
SOLO_BANDS: list[dict[str, int]] = [
    {"max_students": 5, "monthly": 2000},
    {"max_students": 15, "monthly": 4000},
    {"max_students": 30, "monthly": 6000},
]
# 30 üstü her öğrenci için son bandın üstüne eklenen ücret (₺/ay).
SOLO_OVER_CAP_PER_STUDENT = 200

# ----------------------------- Kurum (B2B) -----------------------------

INSTITUTION_FREE_TEACHERS = 2
INSTITUTION_FREE_STUDENTS = 20
INSTITUTION_STUDENTS_PER_COACH = 30

# Koç sayısı tier'ları — koç başına aylık ücret (₺). max_coaches None = sınırsız.
INSTITUTION_TIERS: list[dict[str, Any]] = [
    {
        "code": "etut_standart", "label": "Etüt Standart",
        "min_coaches": 2, "max_coaches": 10, "per_coach_monthly": 4000,
        "white_label": False,
        "short": "Etüt merkezleri ve butik dershaneler için.",
    },
    {
        "code": "dershane_pro", "label": "Dershane Pro",
        "min_coaches": 11, "max_coaches": 50, "per_coach_monthly": 3000,
        "white_label": False,
        "short": "Büyüyen dershaneler için hacim avantajı + 60 gün garanti.",
    },
    {
        "code": "enterprise", "label": "Özel Okul / Enterprise",
        "min_coaches": 51, "max_coaches": None, "per_coach_monthly": 2500,
        "white_label": True,
        "short": "Özel okul, zincir ve kurumlar için özel sözleşme + white-label.",
    },
]

# Ücretli plan kodları (entitlement — AI premium açık).
PAID_PLAN_CODES = {"solo_pro", "solo_elite", "etut_standart", "dershane_pro", "enterprise"}
TRIAL_PLAN_CODES = {"solo_trial", "institution_trial"}


# ----------------------------- Hesaplayıcılar -----------------------------


def compute_solo_monthly(student_count: int) -> int:
    """Aktif öğrenci sayısına göre solo aylık ücret (₺). 0/negatif → 0."""
    n = max(0, int(student_count))
    if n == 0:
        return 0
    last = SOLO_BANDS[-1]
    if n > last["max_students"]:
        return last["monthly"] + (n - last["max_students"]) * SOLO_OVER_CAP_PER_STUDENT
    for band in SOLO_BANDS:
        if n <= band["max_students"]:
            return band["monthly"]
    return last["monthly"]


def institution_tier_for_coaches(coach_count: int) -> dict[str, Any]:
    """Koç sayısına uyan kurum tier'ı (en küçük min altı → ilk tier)."""
    n = max(1, int(coach_count))
    for tier in INSTITUTION_TIERS:
        mx = tier["max_coaches"]
        if mx is None or n <= mx:
            return tier
    return INSTITUTION_TIERS[-1]


def compute_institution_monthly(coach_count: int) -> int:
    """Koç sayısına göre kurum aylık ücret (₺) = koç × tier koç-başı ücret."""
    n = max(0, int(coach_count))
    if n == 0:
        return 0
    tier = institution_tier_for_coaches(n)
    return n * int(tier["per_coach_monthly"])


def annual_total(monthly: int) -> int:
    """Yıllık peşin tutar (10 ay öde)."""
    return monthly * ANNUAL_PAID_MONTHS


# ----------------------------- Katalog (UI için) -----------------------------


def get_pricing_catalog() -> dict[str, Any]:
    """`/pricing` + süper admin için tam yapı. Tek kaynak."""
    return {
        "currency": CURRENCY,
        "annual_paid_months": ANNUAL_PAID_MONTHS,
        "solo": {
            "trial_days": SOLO_TRIAL_DAYS,
            "free": {"students": SOLO_FREE_STUDENTS, "ai_included": False},
            "bands": [dict(b) for b in SOLO_BANDS],
            "over_cap_per_student": SOLO_OVER_CAP_PER_STUDENT,
            "ai_included": True,
        },
        "institution": {
            "trial_days": INSTITUTION_TRIAL_DAYS,
            "free": {
                "teachers": INSTITUTION_FREE_TEACHERS,
                "students": INSTITUTION_FREE_STUDENTS,
                "ai_included": False,
            },
            "students_per_coach": INSTITUTION_STUDENTS_PER_COACH,
            "tiers": [dict(t) for t in INSTITUTION_TIERS],
            "ai_included": True,
        },
    }


def is_paid_plan_code(plan_code: str | None) -> bool:
    return (plan_code or "") in PAID_PLAN_CODES
