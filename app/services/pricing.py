"""Üyelik/fiyat yapısı — TEK KAYNAK (single source of truth) + süper admin override.

İki kitle:
- B2C bağımsız koç: öğrenci bandına göre fiyat (1-5/6-15/16-30/30+).
- B2B kurum: koç başına fiyat (koç sayısı tier'ına göre), her koç ≤30 öğrenci.

Kod default + DB override (`app_settings` key="pricing"). Süper admin panelden
düzenler; override yoksa kod varsayılanı geçerli. /pricing sayfası, teacher Paket,
süper admin paneli — hepsi buradan okur (veri tutarlılığı). AI yalnız ücretli.
"""

from __future__ import annotations

from typing import Any

from app.services import app_settings

PRICING_KEY = "pricing"

# Süper adminden düzenlenebilen tüm sayılar — kod varsayılanı.
_DEFAULTS: dict[str, Any] = {
    "currency": "TRY",
    "annual_paid_months": 10,           # yıllık = 10 ay öde (2 ay bedava)
    # --- Solo (B2C) ---
    "solo_trial_days": 14,
    "solo_free_students": 3,
    "solo_bands": [
        {"max_students": 5, "monthly": 2000},
        {"max_students": 15, "monthly": 4000},
        {"max_students": 30, "monthly": 6000},
    ],
    "solo_over_cap_per_student": 200,
    # --- Kurum (B2B) ---
    "institution_trial_days": 30,
    "institution_free_teachers": 2,
    "institution_free_students": 20,
    "institution_students_per_coach": 30,
    "institution_tiers": [
        {"code": "etut_standart", "label": "Etüt Standart", "min_coaches": 2,
         "max_coaches": 10, "per_coach_monthly": 4000, "white_label": False,
         "short": "Etüt merkezleri ve butik dershaneler için."},
        {"code": "dershane_pro", "label": "Dershane Pro", "min_coaches": 11,
         "max_coaches": 50, "per_coach_monthly": 3000, "white_label": False,
         "short": "Büyüyen dershaneler için hacim avantajı + 60 gün garanti."},
        {"code": "enterprise", "label": "Özel Okul / Enterprise", "min_coaches": 51,
         "max_coaches": None, "per_coach_monthly": 2500, "white_label": True,
         "short": "Özel okul, zincir ve kurumlar için özel sözleşme + white-label."},
    ],
}

# Ücretli plan kodları (entitlement — AI premium açık). Düzenlenebilir değil.
PAID_PLAN_CODES = {"solo_pro", "solo_elite", "etut_standart", "dershane_pro", "enterprise"}
TRIAL_PLAN_CODES = {"solo_trial", "institution_trial"}


def defaults() -> dict[str, Any]:
    """Kod varsayılanı (sıfırlama için)."""
    import copy
    return copy.deepcopy(_DEFAULTS)


def _cfg() -> dict[str, Any]:
    """Etkin yapılandırma = kod default + DB override (shallow merge)."""
    override = app_settings.get_json(PRICING_KEY, {}) or {}
    cfg = dict(_DEFAULTS)
    if isinstance(override, dict):
        cfg.update(override)
    return cfg


# ----------------------------- Hesaplayıcılar -----------------------------


def compute_solo_monthly(student_count: int) -> int:
    cfg = _cfg()
    bands = cfg["solo_bands"]
    over = int(cfg["solo_over_cap_per_student"])
    n = max(0, int(student_count))
    if n == 0:
        return 0
    last = bands[-1]
    if n > last["max_students"]:
        return int(last["monthly"]) + (n - last["max_students"]) * over
    for band in bands:
        if n <= band["max_students"]:
            return int(band["monthly"])
    return int(last["monthly"])


def institution_tier_for_coaches(coach_count: int) -> dict[str, Any]:
    tiers = _cfg()["institution_tiers"]
    n = max(1, int(coach_count))
    for tier in tiers:
        mx = tier["max_coaches"]
        if mx is None or n <= mx:
            return tier
    return tiers[-1]


def compute_institution_monthly(coach_count: int) -> int:
    n = max(0, int(coach_count))
    if n == 0:
        return 0
    return n * int(institution_tier_for_coaches(n)["per_coach_monthly"])


def annual_total(monthly: int) -> int:
    return monthly * int(_cfg()["annual_paid_months"])


def is_paid_plan_code(plan_code: str | None) -> bool:
    return (plan_code or "") in PAID_PLAN_CODES


# ----------------------------- Katalog (UI için) -----------------------------


def get_pricing_catalog() -> dict[str, Any]:
    """`/pricing` + süper admin için tam yapı. Tek kaynak (override uygulanmış)."""
    cfg = _cfg()
    return {
        "currency": cfg["currency"],
        "annual_paid_months": int(cfg["annual_paid_months"]),
        "solo": {
            "trial_days": int(cfg["solo_trial_days"]),
            "free": {"students": int(cfg["solo_free_students"]), "ai_included": False},
            "bands": [dict(b) for b in cfg["solo_bands"]],
            "over_cap_per_student": int(cfg["solo_over_cap_per_student"]),
            "ai_included": True,
        },
        "institution": {
            "trial_days": int(cfg["institution_trial_days"]),
            "free": {
                "teachers": int(cfg["institution_free_teachers"]),
                "students": int(cfg["institution_free_students"]),
                "ai_included": False,
            },
            "students_per_coach": int(cfg["institution_students_per_coach"]),
            "tiers": [dict(t) for t in cfg["institution_tiers"]],
            "ai_included": True,
        },
    }


def get_effective_config() -> dict[str, Any]:
    """Süper admin editörü için düzenlenebilir etkin yapı (override dahil)."""
    return _cfg()
