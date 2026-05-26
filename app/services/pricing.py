"""Üyelik/fiyat yapısı — TEK KAYNAK (single source of truth) + süper admin override.

İki kitle:
- B2C bağımsız koç: öğrenci bandına göre fiyat (1-5/6-15/16-30/30+).
- B2B kurum: toplam kademe fiyatı (koç sayısı tier'ına göre), her koç ≤30 öğrenci.

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
    # 3 kapaklı paket: her tier'ın SERT öğrenci tavanı + sabit aylık fiyatı var.
    # free=3 (ücretsiz). Ücretli: ≤10 / ≤25 / sınırsız. max_students=null → sınırsız.
    "solo_trial_days": 14,
    "solo_free_students": 3,
    "solo_tiers": [
        {"code": "solo_pro", "label": "Solo Başlangıç", "max_students": 10, "monthly": 2500},
        {"code": "solo_elite", "label": "Solo", "max_students": 25, "monthly": 5000},
        {"code": "solo_unlimited", "label": "Solo Sınırsız", "max_students": None, "monthly": 7500},
    ],
    # --- Kurum (B2B) ---
    # Toplam kademe fiyatı (koç-başı DEĞİL): ≤10 → 10k, ≤50 → 30k, 50+ → özel teklif.
    # max_coaches → öğretmen limiti; öğrenci limiti = öğretmen × students_per_coach.
    "institution_trial_days": 30,
    "institution_free_teachers": 2,
    "institution_free_students": 20,
    "institution_students_per_coach": 30,
    "institution_tiers": [
        {"code": "etut_standart", "label": "Etüt Standart", "min_coaches": 2,
         "max_coaches": 10, "monthly_total": 10000, "price_hidden": False, "white_label": False,
         "short": "Etüt merkezleri ve butik dershaneler için."},
        {"code": "dershane_pro", "label": "Dershane Pro", "min_coaches": 11,
         "max_coaches": 50, "monthly_total": 30000, "price_hidden": False, "white_label": False,
         "short": "Büyüyen dershaneler için hacim avantajı + 60 gün garanti."},
        {"code": "enterprise", "label": "Özel Okul / Enterprise", "min_coaches": 51,
         "max_coaches": None, "monthly_total": None, "price_hidden": True, "white_label": True,
         "short": "Özel okul, zincir ve kurumlar için özel sözleşme + white-label."},
    ],
    # --- İletişim (kurumsal talep + destek) ---
    "contact": {
        "sales_email": "satis@etutkoc.com",
        "support_email": "destek@etutkoc.com",
        "whatsapp": "",   # boş → gizli. Örn: "+905xxxxxxxxx"
        "phone": "",      # boş → gizli. Örn: "+902xxxxxxxxx"
    },
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


def solo_tier_for_students(student_count: int) -> dict[str, Any]:
    """Öğrenci sayısına denk gelen solo tier (kapaklı). max_students=None → sınırsız."""
    tiers = _cfg()["solo_tiers"]
    n = max(0, int(student_count))
    for tier in tiers:
        if tier["max_students"] is None or n <= tier["max_students"]:
            return tier
    return tiers[-1]


def compute_solo_monthly(student_count: int) -> int:
    """Öğrenci sayısına göre solo tier'ın sabit aylık fiyatı (kapaklı modelde)."""
    n = max(0, int(student_count))
    if n == 0:
        return 0
    return int(solo_tier_for_students(n)["monthly"])


def institution_tier_for_coaches(coach_count: int) -> dict[str, Any]:
    tiers = _cfg()["institution_tiers"]
    n = max(1, int(coach_count))
    for tier in tiers:
        mx = tier["max_coaches"]
        if mx is None or n <= mx:
            return tier
    return tiers[-1]


def compute_institution_monthly(coach_count: int) -> int | None:
    """Koç sayısının düştüğü kademenin TOPLAM aylık fiyatı (koç-başı değil).
    Enterprise (özel teklif) → None."""
    n = max(0, int(coach_count))
    if n == 0:
        return 0
    mt = institution_tier_for_coaches(n).get("monthly_total")
    return int(mt) if mt is not None else None


def annual_total(monthly: int) -> int:
    return monthly * int(_cfg()["annual_paid_months"])


def is_paid_plan_code(plan_code: str | None) -> bool:
    return (plan_code or "") in PAID_PLAN_CODES


# ----------------------------- Katalog (UI için) -----------------------------


# Pazarlama kopyası (fayda-odaklı, sade dil) — kod kaynaklı (fiyat sayıları
# override'dan gelir, metin buradan). Hem anasayfa hem /pricing aynısını gösterir.
def _fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _marketing_cards(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    free_students = int(cfg["solo_free_students"])
    tiers = cfg["solo_tiers"]
    t1, t2, t3 = tiers[0], tiers[1], tiers[2]

    def cap_note(t: dict[str, Any]) -> str:
        return "sınırsız öğrenci" if t["max_students"] is None else f"{t['max_students']} öğrenciye kadar"

    ai_features = [
        "Her görüşme öncesi yapay zekâ 'bugün şunu konuş' özetini hazırlar",
        "Görüşmeyi sesle anlat ya da formu fotoğrafla — notlar kendiliğinden yazılır",
        "Tükenen veya uzaklaşan öğrenciyi geç olmadan gör",
        "Veliye otomatik ilerleme bildirimi + deneme/net gelişim grafiği",
    ]
    cards: list[dict[str, Any]] = [
        {
            "key": "free", "audience": "solo", "plan": "solo_free",
            "name": "Ücretsiz", "tagline": "Yeni başlayan koç için",
            "monthly": 0, "price_label": "Ücretsiz", "price_unit": "", "tone": "plain",
            "price_hidden": False, "price_caption": "",
            "price_note": f"{free_students} öğrenciye kadar, süresiz",
            "highlight": False, "badge": None, "corner": None,
            "cta": "Ücretsiz başla", "cta_href": "/signup/teacher",
            "features": [
                f"{free_students} öğrenciye kadar tam takip",
                "Haftalık plan + günlük görev yönetimi",
                "Veliye e-posta ile ilerleme bildirimi",
                "Aralıklı tekrar ile kalıcı öğrenme",
            ],
            "excluded": ["Yapay zekâ özellikleri", "Sınırsız öğrenci"],
        },
        {
            "key": "solo_pro", "audience": "solo", "plan": t1["code"],
            "name": t1["label"], "tagline": "Küçük ama düzenli büyüyen koç için",
            "monthly": int(t1["monthly"]), "price_label": _fmt(t1["monthly"]) + " ₺",
            "price_unit": "/ay", "tone": "plain",
            "price_hidden": False, "price_caption": "",
            "price_note": f"{cap_note(t1)} · 14 gün ücretsiz dene",
            "highlight": False, "badge": None, "corner": None,
            "cta": "14 gün ücretsiz dene", "cta_href": "/signup/teacher?plan=" + t1["code"],
            "features": [f"{cap_note(t1).capitalize()}", *ai_features],
            "excluded": [],
        },
        {
            "key": "solo_elite", "audience": "solo", "plan": t2["code"],
            "name": t2["label"], "tagline": "Yoğun, yapay zekâ kullanan koç için",
            "monthly": int(t2["monthly"]), "price_label": _fmt(t2["monthly"]) + " ₺",
            "price_unit": "/ay", "tone": "featured",
            "price_hidden": False, "price_caption": "",
            "price_note": f"{cap_note(t2)} · 14 gün ücretsiz dene",
            "highlight": True, "badge": "En popüler", "corner": None,
            "cta": "14 gün ücretsiz dene", "cta_href": "/signup/teacher?plan=" + t2["code"],
            "features": [f"{cap_note(t2).capitalize()}", *ai_features, "Öncelikli destek"],
            "excluded": [],
        },
        {
            "key": "solo_unlimited", "audience": "solo", "plan": t3["code"],
            "name": t3["label"], "tagline": "Mini-kurum ölçeğindeki güç koçu için",
            "monthly": int(t3["monthly"]), "price_label": _fmt(t3["monthly"]) + " ₺",
            "price_unit": "/ay", "tone": "plain",
            "price_hidden": False, "price_caption": "",
            "price_note": f"{cap_note(t3)} · 14 gün ücretsiz dene",
            "highlight": False, "badge": None, "corner": None,
            "cta": "14 gün ücretsiz dene", "cta_href": "/signup/teacher?plan=" + t3["code"],
            "features": [f"{cap_note(t3).capitalize()}", *ai_features, "Öncelikli destek"],
            "excluded": [],
        },
        {
            "key": "institution", "audience": "institution", "plan": "etut_standart",
            "name": "Kurum", "tagline": "Etüt, dershane ve özel okullar için",
            "monthly": 0, "price_label": "", "tone": "dark",
            "price_hidden": True, "price_caption": "Kurumunuza özel teklif",
            "price_unit": "", "price_note": "30 gün ücretsiz pilot · birkaç saatte kurulum",
            "highlight": False, "badge": None, "corner": "60 Gün Garanti",
            "cta": "Kurumsal teklif al", "cta_href": "/pricing?type=kurum#kurumsal",
            "features": [
                "Koçların tüm araçları + kurum gözü",
                "Hangi koç aktif, hangi öğrenci ihmal ediliyor — tek bakışta",
                "Risk altındaki öğrenci ve sınıfı erken gör (kıyaslamalı)",
                "Veliyle güçlü iletişim → kayıt yenileme ve memnuniyet",
                "60 gün performans garantisi",
            ],
            "excluded": [],
        },
    ]
    return cards


def get_pricing_catalog() -> dict[str, Any]:
    """`/pricing` + anasayfa + süper admin için tam yapı. Tek kaynak (override uygulanmış)."""
    cfg = _cfg()
    contact = cfg.get("contact") or _DEFAULTS["contact"]
    return {
        "cards": _marketing_cards(cfg),
        "currency": cfg["currency"],
        "annual_paid_months": int(cfg["annual_paid_months"]),
        "contact": {
            "sales_email": str(contact.get("sales_email") or _DEFAULTS["contact"]["sales_email"]),
            "support_email": str(contact.get("support_email") or _DEFAULTS["contact"]["support_email"]),
            "whatsapp": str(contact.get("whatsapp") or ""),
            "phone": str(contact.get("phone") or ""),
        },
        "solo": {
            "trial_days": int(cfg["solo_trial_days"]),
            "free": {"students": int(cfg["solo_free_students"]), "ai_included": False},
            "tiers": [dict(t) for t in cfg["solo_tiers"]],
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
