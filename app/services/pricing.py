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
    # Görünen adlar (2026-08-04 yenilemesi, kullanıcı onaylı): koçun yolculuğu —
    # Keşif (ücretsiz) → Patika → Rota (amiral, marka adıyla aynı) → Zirve.
    # KOD adları DB/iyzico/App Store'a gömülü — ASLA değişmez.
    "solo_tiers": [
        {"code": "solo_pro", "label": "Patika", "max_students": 10, "monthly": 2500},
        {"code": "solo_elite", "label": "Rota", "max_students": 25, "monthly": 5000},
        {"code": "solo_unlimited", "label": "Zirve", "max_students": None, "monthly": 7500},
    ],
    "solo_free_label": "Keşif",
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


# ----------------------------------------------------------------------------
# TEK KAYNAK — paket özellik bullet'ları (pazarlama-odaklı, "can alıcı"
# özellikler). /pricing + anasayfa + /teacher/plan + admin kurum + üyelik teklifi
# HEPSİ buradan beslenir (features_for_plan). plans.py features_included artık
# bunu yansıtır. Fiyat/limit İSKELETİNE dokunmaz — yalnız SUNUM (hangi özellik,
# hangi dille). Yeni "can alıcı" özellik çıkınca tek yer güncellenir.
# ----------------------------------------------------------------------------

# --- KADEMELİ İÇERİK (2026-08-04): "Öncekinin hepsi, artı…" modeli ---
# Keşif = çekirdek döngünün tamamı (AI'sız). Her ücretli kademe yalnız
# YENİ kazandırdıklarını listeler; kümülatif liste features_for_plan üretir.

# Keşif (ücretsiz) — çekirdek döngü, AI yok.
# BİÇİM KURALI: her madde "Kısa Başlık — kısa detay". Kart, başlığı kalın,
# detayı soluk basar → sayfa TARANABİLİR kalır (2026-08-04 yoğunluk düzeltmesi:
# 3 satıra sarkan cümle-maddeler kartları okunmaz yapıyordu).
_FREE_FEATURES = [
    "Haftalık program + günlük takip — kitap, görev, işaretleme",
    "Veli raporu — davet + haftalık e-posta",
    "Deneme takibi — elle giriş + net grafiği",
    "Yanlış Soru Arşivi — fotoğrafla, aralıklı tekrar",
    "Mobil uygulama — öğrenci · veli · koç",
    "Sesli rehber turu — kolay kurulum",
]
# Patika — "Keşif'tekilerin hepsi, artı:" (yapay zekâ paketi açılır)
_TIER1_NEW = [
    "AI karne okuma — deneme sonucu PDF'inden konu analizi",
    "Veliye yapay zekâ asistanı — durumu sesli anlatır, soruları yanıtlar",
    "Yanlışına ipucu — cevabı söylemez, çözüm yolunu gösterir",
    "Sesli/fotoğraflı seans notu — kendiliğinden yazılır",
    "Görüşme öncesi özet — \"bugün şunu konuş\" listesi",
    "Erken uyarı — kopan öğrenciyi geç olmadan gör",
    "Randevu + Google Meet",
]
# Rota — "Patika'dakilerin hepsi, artı:"
_TIER2_NEW = [
    "Veli asistanı tam kapasite — her veliye haftalık sesli yorum",
    "Kariyer önerisi — anket + gerçek netlerle hedef bölüm",
    "Öncelikli destek",
]
# Zirve — "Rota'dakilerin hepsi, artı:"
_TIER3_NEW = [
    "Birebir kurulum ve taşıma — kitaplarını, öğrencilerini birlikte kurarız",
    "Erken erişim — yeni özellikler önce sende",
]

# Kademeye göre yeni-özellik listesi (kart kademeli anlatımı için).
_TIER_NEW_BY_IDX = [_TIER1_NEW, _TIER2_NEW, _TIER3_NEW]


def _tier_credits(code: str) -> int:
    """Aylık kredi tahsisi — credits.PLAN_ALLOCATIONS TEK KAYNAK (sayı burada
    tekrarlanmaz; tahsis değişikliği ayrı karardır)."""
    from app.services.credits import PLAN_ALLOCATIONS
    return int(PLAN_ALLOCATIONS.get(code, 0))


def _credit_note(idx: int, code: str) -> str:
    """Kredinin insan dili — '1.500 kredi' tek başına hiçbir şey anlatmıyor."""
    n = _fmt(_tier_credits(code))
    if idx == 0:
        return f"{n} kredi/ay — 10 öğrencilik tam kullanıma rahat yeter"
    if idx == 1:
        return f"{n} kredi/ay — veli asistanı tam kapasitede bile yeter"
    return f"{n} kredi/ay — tavana takılmazsın"


# ----------------------------------------------------------------------------
# ÖZELLİK SÖZLÜĞÜ — tıkla-gör balonlar (2026-08-04, kullanıcı onaylı mekanizma).
# Kart maddesindeki KISA BAŞLIK ("term") buradaki anahtara birebir eşleşirse
# arayüz noktalı altçizgi basar; dokununca sade açıklama + (varsa) GERÇEK ürün
# ekranı açılır. Görseller rehber çekimlerinden (demo veri — kişisel veri yok).
# KURAL: yeni özellik maddesi eklerken başlığı buraya da tanımla; görsel yoksa
# image=None (yalnız metin balonu).
# ----------------------------------------------------------------------------
_SHOTS = "/static/guide/shots"

FEATURE_GLOSSARY: list[dict[str, Any]] = [
    {
        "term": "AI karne okuma",
        "explanation": (
            "Denemeden sonra eline geçen sonuç karnesini (PDF dosyası) sisteme "
            "yüklersin. Yapay zekâ belgeyi iki kez okur, her sorunun konusunu ve "
            "doğru/yanlışını çıkarır; netler ve konu boşlukları kendiliğinden "
            "işlenir — elle giriş yok."
        ),
        "image": f"{_SHOTS}/aktar-onizleme.png",
    },
    {
        "term": "Veliye yapay zekâ asistanı",
        "explanation": (
            "Sistemin yapay zekâ asistanı (adı Rota), veliye çocuğunun haftasını "
            "ve deneme gelişimini SESLİ anlatır; veli yazarak ya da konuşarak "
            "soru sorar. Kimse velinle görüşmez — veli uygulamadan dinler ve "
            "sorar. Kullanım senin kredinden düşer; istediğin veliye kapatabilirsin."
        ),
        "image": f"{_SHOTS}/veli-rota-dinle.png",
    },
    {
        "term": "Yanlışına ipucu",
        "explanation": (
            "Öğrenci yanlış yaptığı sorunun fotoğrafını arşive atar. Yapay zekâ "
            "çözümü SÖYLEMEZ; 'hangi kavramı hatırla, ilk adım ne' diye yol "
            "gösterir — cevabı öğrenci kendisi bulur."
        ),
        "image": f"{_SHOTS}/ogr-ai-ipucu.png",
    },
    {
        "term": "Yanlış Soru Arşivi",
        "explanation": (
            "Öğrenci yanlışının fotoğrafını çeker, arşive atar. Sistem soruyu "
            "unutma eğrisine göre doğru zamanda yeniden sorar; aralıklı iki "
            "doğru çözüm soruyu 'öğrenildi' olarak kapatır."
        ),
        "image": f"{_SHOTS}/ogr-yanlislar.png",
    },
    {
        "term": "Görüşme öncesi özet",
        "explanation": (
            "Öğrenciyle görüşmeden önce yapay zekâ; son seans notlarını, "
            "programa uyumu ve deneme verisini okuyup sana 'bugün şunu konuş' "
            "gündem listesi hazırlar. Görüşmeye hazırlıklı girersin."
        ),
        "image": None,
    },
    {
        "term": "Sesli/fotoğraflı seans notu",
        "explanation": (
            "Görüşme bitince ya sesle anlatırsın ya da elindeki formun "
            "fotoğrafını çekersin — seans kaydı kendiliğinden yazılır. "
            "Not tutmakla vakit kaybetmezsin."
        ),
        "image": None,
    },
    {
        "term": "Erken uyarı",
        "explanation": (
            "Tempo düşüşü, üst üste boş günler ve tükenmişlik sinyalleri "
            "panelde erken görünür; öğrenci kopmadan müdahale edersin."
        ),
        "image": None,
    },
    {
        "term": "Randevu + Google Meet",
        "explanation": (
            "Öğrenci ya da veli, senin boş saatlerinden randevu ister; sen "
            "onaylarsın. Görüşme bağlantısı (Google Meet) ve hatırlatmalar "
            "otomatik gider."
        ),
        "image": None,
    },
    {
        "term": "Veli asistanı tam kapasite",
        "explanation": (
            "4.000 kredi, 25 öğrencinin HER velisine haftalık sesli yorum + "
            "sohbet için rahatça yeter — veli 'bu hafta ne yaptı?' diye seni "
            "aramaz, asistana sorar."
        ),
        "image": f"{_SHOTS}/veli-rota-yorum.png",
    },
    {
        "term": "Kariyer önerisi",
        "explanation": (
            "Meslek ilgisi ve beceri anketleri, öğrencinin GERÇEK deneme "
            "netleriyle birleştirilir; yapay zekâ hedef bölüm/alan önerir ve "
            "sana hedef görüşmesi gündemi çıkarır."
        ),
        "image": None,
    },
    {
        "term": "Birebir kurulum ve taşıma",
        "explanation": (
            "Kitaplarını, öğrencilerini ve mevcut Excel/WhatsApp düzenini "
            "birlikte sisteme taşırız — ekranı paylaşır, kurulumu beraber "
            "bitiririz. Tek başına uğraşmazsın."
        ),
        "image": None,
    },
]


def credit_costs_public() -> list[dict[str, Any]]:
    """'Krediler ne yapar?' tablosu — işlem başına maliyet (KIND_CREDITS tek
    kaynağından, sunum etiketiyle)."""
    from app.models import UsageKind
    from app.services.credits import KIND_CREDITS

    rows = [
        ("AI karne okuma (deneme sonucu PDF)", UsageKind.AI_EXAM_IMPORT),
        ("Veli sesli yorumu (metin + ses)", None),  # yorum 6 + ses 2 — birleşik
        ("Veli sohbet sorusu", UsageKind.AI_PARENT_CHAT),
        ("Yanlış soru AI ipucu", UsageKind.AI_WRONG_TAG),
        ("Görüşme öncesi AI hazırlık", UsageKind.AI_COACHING_INSIGHT),
        ("Sesli dikte (seans notu)", UsageKind.AI_TRANSCRIBE),
        ("Fotoğraftan seans notu", UsageKind.AI_SESSION_CAPTURE),
        ("AI kariyer sentezi", UsageKind.AI_CAREER_SYNTHESIS),
    ]
    out: list[dict[str, Any]] = []
    for label, kind in rows:
        if kind is None:
            credits = (KIND_CREDITS[UsageKind.AI_PARENT_COMMENTARY]
                       + KIND_CREDITS[UsageKind.AI_PARENT_COMMENTARY_VOICE])
        else:
            credits = KIND_CREDITS[kind]
        out.append({"label": label, "credits": int(credits)})
    return out
# Kurum — kurum gözü + erken müdahale + veli güveni.
_INSTITUTION_FEATURES = [
    "Koçların tüm araçları + kurum gözü",
    "Hangi koç aktif, hangi öğrenci ihmal ediliyor — tek bakışta",
    "Risk altındaki öğrenci ve sınıfı erken gör (kıyaslamalı)",
    "Veliyle güçlü iletişim → kayıt yenileme ve memnuniyet",
    "60 gün performans garantisi",
]


def _cap_note(t: dict[str, Any]) -> str:
    return "sınırsız öğrenci" if t["max_students"] is None else f"{t['max_students']} öğrenciye kadar"


def features_for_plan(plan_code: str | None) -> list[str]:
    """Bir plan kodu için pazarlama-odaklı özellik bullet'ları (TEK KAYNAK).

    Ücretli solo: '{N} öğrenciye kadar tam takip' + yapay zekâ özellikleri
    (+ üst tier'larda öncelikli destek). Free: temel takip. Kurum: kurum gözü.
    Tanınmayan/trial kod → en yakın eşlenik.
    """
    if not plan_code:
        return []
    cfg = _cfg()
    solo_tiers = cfg["solo_tiers"]
    by_code = {t["code"]: (i, t) for i, t in enumerate(solo_tiers)}
    inst_codes = {t["code"] for t in cfg["institution_tiers"]}

    is_trial = plan_code in ("solo_trial",)
    if is_trial:
        plan_code = solo_tiers[1]["code"]  # deneme = Rota deneyimi
    if plan_code in by_code:
        idx, t = by_code[plan_code]
        out = [f"{_cap_note(t).capitalize()} tam takip"]
        if not is_trial:
            # Denemede kredi tavanı 50 — Rota'nın 4.000'lik satırı YALAN olurdu.
            out.append(_credit_note(idx, t["code"]))
        for i in range(idx + 1):
            out.extend(_TIER_NEW_BY_IDX[i])
        return out
    if plan_code in ("solo_free", "free"):
        fs = int(cfg["solo_free_students"])
        return [f"{fs} öğrenciye kadar tam takip", *_FREE_FEATURES]
    if plan_code in inst_codes or plan_code in (
        "institution_free", "institution_trial", "etut_standart", "dershane_pro", "enterprise"
    ):
        if plan_code in ("institution_free",):
            return [
                f"{int(cfg['institution_free_teachers'])} öğretmen / "
                f"{int(cfg['institution_free_students'])} öğrenciye kadar tanıma",
                "Koçların tüm araçları + kurum gözü",
                "Temel kurum panosu",
            ]
        return list(_INSTITUTION_FEATURES)
    return []


def _per_student_note(t: dict[str, Any]) -> str:
    """ROI mikro-satırı (CoachAccountable deseni): öğrenci başına aylık maliyet."""
    mx = t.get("max_students")
    if not mx:
        return ""
    per = int(round(int(t["monthly"]) / int(mx)))
    return f"öğrenci başına ~{_fmt(per)} ₺/ay"


def _marketing_cards(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    free_students = int(cfg["solo_free_students"])
    free_label = str(cfg.get("solo_free_label") or "Keşif")
    tiers = cfg["solo_tiers"]
    t1, t2, t3 = tiers[0], tiers[1], tiers[2]

    def cap_note(t: dict[str, Any]) -> str:
        return _cap_note(t)

    def tier_card(idx: int, t: dict[str, Any], *, tagline: str, tone: str,
                  highlight: bool, badge: str | None,
                  inherits: str) -> dict[str, Any]:
        return {
            "key": t["code"], "audience": "solo", "plan": t["code"],
            "name": t["label"], "tagline": tagline,
            "monthly": int(t["monthly"]), "price_label": _fmt(t["monthly"]) + " ₺",
            "price_unit": "/ay", "tone": tone,
            "price_hidden": False, "price_caption": "",
            "price_note": f"{cap_note(t)} · 14 gün ücretsiz dene",
            "per_student_note": _per_student_note(t),
            "highlight": highlight, "badge": badge, "corner": None,
            "cta": "14 gün ücretsiz dene", "cta_href": "/signup/teacher?plan=" + t["code"],
            # Kademeli anlatım: inherits satırı + yalnız bu kademenin YENİLERİ.
            "inherits": inherits,
            "features": list(_TIER_NEW_BY_IDX[idx]),
            "credit_note": _credit_note(idx, t["code"]),
            "credits_monthly": _tier_credits(t["code"]),
            "excluded": [],
        }

    cards: list[dict[str, Any]] = [
        {
            "key": "free", "audience": "solo", "plan": "solo_free",
            "name": free_label, "tagline": "Sistemi keşfet — süresiz ücretsiz",
            "monthly": 0, "price_label": "Ücretsiz", "price_unit": "", "tone": "plain",
            "price_hidden": False, "price_caption": "",
            "price_note": f"{free_students} öğrenciye kadar, süresiz",
            "per_student_note": "",
            "highlight": False, "badge": None, "corner": None,
            "cta": "Ücretsiz başla", "cta_href": "/signup/teacher",
            "inherits": "",
            "features": [f"{free_students} öğrenciye kadar tam takip", *_FREE_FEATURES],
            "credit_note": "", "credits_monthly": 0,
            "excluded": [f"Yapay zekâ özellikleri ({t1['label']} ve üzeri)"],
        },
        tier_card(0, t1, tagline="Yola çıktın — ilk 10 öğrencin",
                  tone="plain", highlight=False, badge=None,
                  inherits=f"{free_label}'tekilerin hepsi, artı:"),
        tier_card(1, t2, tagline="Tam kapasite koçluk",
                  tone="featured", highlight=True, badge="En popüler",
                  inherits=f"{t1['label']}'dakilerin hepsi, artı:"),
        tier_card(2, t3, tagline="Tavan yok — mini kurum ölçeği",
                  tone="plain", highlight=False, badge=None,
                  inherits=f"{t2['label']}'dakilerin hepsi, artı:"),
        {
            "key": "institution", "audience": "institution", "plan": "etut_standart",
            "name": "Kurum", "tagline": "Etüt, dershane ve özel okullar için",
            "monthly": 0, "price_label": "", "tone": "dark",
            "price_hidden": True, "price_caption": "Kurumunuza özel teklif",
            "price_unit": "", "price_note": "30 gün ücretsiz pilot · birkaç saatte kurulum",
            "highlight": False, "badge": None, "corner": "60 Gün Garanti",
            "cta": "Kurumsal teklif al", "cta_href": "/pricing?type=kurum#kurumsal",
            "features": features_for_plan("etut_standart"),
            "excluded": [],
        },
    ]
    return cards


def get_pricing_catalog() -> dict[str, Any]:
    """`/pricing` + anasayfa + süper admin için tam yapı. Tek kaynak (override uygulanmış)."""
    cfg = _cfg()
    contact = cfg.get("contact") or _DEFAULTS["contact"]
    # Plan kodu → pazarlama bullet'ları (TEK KAYNAK). /teacher/plan + admin kurum +
    # üyelik teklifi aynı kopyayı buradan tüketir (hardcoded liste yok).
    _codes = (
        ["solo_free"]
        + [t["code"] for t in cfg["solo_tiers"]]
        + ["institution_free"]
        + [t["code"] for t in cfg["institution_tiers"]]
    )
    plan_features = {c: features_for_plan(c) for c in _codes}
    return {
        "cards": _marketing_cards(cfg),
        "plan_features": plan_features,
        # "Krediler ne yapar?" tablosu (işlem başına maliyet, sunum etiketiyle)
        "credit_costs": credit_costs_public(),
        # Tıkla-gör balonlar: kısa başlık → sade açıklama + gerçek ekran karesi
        "feature_glossary": FEATURE_GLOSSARY,
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
