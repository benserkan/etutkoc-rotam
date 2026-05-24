"""Anasayfa vitrin kartları seed — koç (6) + kurum (5) yayın kartları.

Stratejik analiz çıktısı (2026-05-25): hedef kitlenin (bağımsız koç + kurum)
acılarına dokunan fayda-odaklı kartlar. feature_catalog üzerinden YAYINLANIR
(status=published) → landing /api/v2/landing bunları çeker. Koç-öncelik:
target_roles=['teacher'] (audience=teacher akışı) yüksek priority; kurum kartları
target_roles=['institution_admin'] (kurum bandı).

İdempotent: slug varsa ATLAR (admin'deki sonraki düzenlemeler korunur).
Çalıştır:  python -m scripts.seed_landing_cards   [--delete ile kaldır]
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import FeatureDomain, FeatureStatus, FeatureTier
from app.services import feature_catalog as fc

NOW = datetime.now(timezone.utc)

# Marka aksanları
CYAN = "#0E7490"   # koç çekirdek
AMBER = "#F59E0B"  # yapay zekâ (premium)
TEAL = "#155E75"   # kurum bandı

CARDS: list[dict] = [
    # ---------------- KOÇ (ana akış — audience=teacher) ----------------
    dict(
        slug="kesfet-erken-uyari", title="Kopan öğrenciyi sistem senden önce fark eder",
        category_label="Erken Uyarı", category_icon="🚨", accent_color=CYAN,
        mockup_type="burnout_gauge", target_roles=["teacher"], domain=FeatureDomain.GENEL.value,
        tier=FeatureTier.CORE.value, strategic_priority=10,
        tagline="Geri kalan, programa uymayan, tempo düşüren öğrenci panoda kırmızı yanar — sen müdahale edene kadar.",
        benefits=["Günlük/haftalık uyum + tutarlılık izlenir", "Sınava yetişme projeksiyonu", "Gördüm/Ertele ile alarm körlüğü yok"],
        pain_points=["'Hangi öğrenci kopuyor?' görünmüyordu → sessiz öğrenci kaybı"],
    ),
    dict(
        slug="kesfet-ai-seans-hazirligi", title="Bugün şu öğrenciyle şunu konuş",
        category_label="Yapay Zekâ", category_icon="🤖", accent_color=AMBER,
        mockup_type="daily_schedule", target_roles=["teacher"], domain=FeatureDomain.GENEL.value,
        tier=FeatureTier.ENHANCEMENT.value, strategic_priority=9,
        tagline="Her görüşme öncesi, öğrencinin son durumundan hazırlanmış gündem ve konuşma ipuçları.",
        benefits=["Seans notları + akademik veriden hazırlık", "Hazırlık dakikalara iner", "Ücretli pakette açık"],
        pain_points=["Seansa hazırlıksız girme"],
    ),
    dict(
        slug="kesfet-ai-sesli-foto-not", title="Notunu sesle ya da fotoğrafla bırak",
        category_label="Yapay Zekâ", category_icon="🤖", accent_color=AMBER,
        mockup_type="fsrs_rating", target_roles=["teacher"], domain=FeatureDomain.GENEL.value,
        tier=FeatureTier.ENHANCEMENT.value, strategic_priority=9,
        tagline="Kâğıt formu çek veya konuş; yapay zekâ seans taslağını doldursun.",
        benefits=["El yazısı not fotoğrafı → metin", "Sesli dikte → gündem", "Veri girmek en fazla 3 tık"],
        pain_points=["Not girme zahmeti zaman çalıyor"],
    ),
    dict(
        slug="kesfet-surdurulebilir-plan", title="Sınırsız öğrenci, sürdürülebilir haftalık plan",
        category_label="Program", category_icon="📅", accent_color=CYAN,
        mockup_type="daily_schedule", target_roles=["teacher"], domain=FeatureDomain.GENEL.value,
        tier=FeatureTier.CORE.value, strategic_priority=8,
        tagline="Sürükle-bırak haftalık plan; kaynak durumu anlık güncellenir, tam deneme ve etkinlik dahil.",
        benefits=["Kitap, ünite, soru bazında plan", "Şablonla tek tıkla uygula", "Öğrenci sayısı arttıkça boğulmazsın"],
        pain_points=["Manuel plan çok zaman alıyor"],
    ),
    dict(
        slug="kesfet-veli-bilgilendirme", title="Veliye otomatik bilgilendirme + net grafiği",
        category_label="Veli İletişimi", category_icon="💬", accent_color=CYAN,
        mockup_type="whatsapp_chat", target_roles=["teacher"], domain=FeatureDomain.VELI.value,
        tier=FeatureTier.CORE.value, strategic_priority=8,
        tagline="Her veliye tek tek yazmak yok; sistem bildirir, veli çocuğunun net trendini görür.",
        benefits=["E-posta/WhatsApp otomatik bildirim", "Veli paneli + net trendi", "Veli güveni artar"],
        pain_points=["Veli iletişimi yük"],
    ),
    dict(
        slug="kesfet-tahsilat", title="Ücret takibini sisteme bırak",
        category_label="Tahsilat", category_icon="💰", accent_color=CYAN,
        mockup_type="books_progress", target_roles=["teacher"], domain=FeatureDomain.GENEL.value,
        tier=FeatureTier.CORE.value, strategic_priority=7,
        tagline="Öğrenci başına ücret, yapılan seans, alınan ödeme ve kalan — tek ekranda, 'ayı kapat' ile.",
        benefits=["Öğrenci başına ücret", "Yapılan seans otomatik sayım", "Kalan tutar + ayı kapat"],
        pain_points=["Elden/akılda tahsilat → para kaçağı"],
    ),
    # ---------------- KURUM (band — audience=institution_admin) ----------------
    dict(
        slug="kesfet-program-uyum", title="Koçlarınız plan yapıyor mu, öğrenci uyuyor mu — tek bakışta",
        category_label="Şeffaflık", category_icon="🔍", accent_color=TEAL,
        mockup_type="books_progress", target_roles=["institution_admin"], domain=FeatureDomain.KURUMSAL.value,
        tier=FeatureTier.CORE.value, strategic_priority=10,
        tagline="Program uyumu, doğruluk oranı ve boş program; koç ve sınıf kırılımıyla.",
        benefits=["Koç başına uyum + doğruluk", "Boş program uyarısı", "Sınıf kırılımı"],
        pain_points=["Kara kutu: koç sistemli plan yapıyor mu görünmüyor"],
    ),
    dict(
        slug="kesfet-mudahale-merkezi", title="Sorunu büyümeden yakalayın",
        category_label="Erken Müdahale", category_icon="🎯", accent_color=TEAL,
        mockup_type="burnout_gauge", target_roles=["institution_admin"], domain=FeatureDomain.KURUMSAL.value,
        tier=FeatureTier.CORE.value, strategic_priority=9,
        tagline="Önceliklendirilmiş müdahale listesi: hangi öğrenciye, neden, hangi koç üzerinden.",
        benefits=["Risk büyümeden sıraya düşer", "Tek tıkla ilgili koça ilet", "Gizlilik korunur"],
        pain_points=["Risk geç fark ediliyor"],
    ),
    dict(
        slug="kesfet-akademik-cikti", title="Kurumunuzun başarısını veliye kanıtlayın",
        category_label="Akademik Kanıt", category_icon="📈", accent_color=TEAL,
        mockup_type="daily_schedule", target_roles=["institution_admin"], domain=FeatureDomain.KURUMSAL.value,
        tier=FeatureTier.CORE.value, strategic_priority=9,
        tagline="Deneme net başarı trendleri; koç, sınıf ve öğrenci bazında.",
        benefits=["Net başarı trendi", "Koç/sınıf kırılımı", "Gelişen/gerileyen öğrenci"],
        pain_points=["Kurum değerini kanıtlayamıyor"],
    ),
    dict(
        slug="kesfet-ogretmen-karne", title="Hangi koç sonuç alıyor, görün",
        category_label="Koç Yönetimi", category_icon="🎓", accent_color=TEAL,
        mockup_type="fsrs_rating", target_roles=["institution_admin"], domain=FeatureDomain.KURUMSAL.value,
        tier=FeatureTier.CORE.value, strategic_priority=8,
        tagline="Öğretmen etkililik karnesi: tamamlama, doğruluk, program disiplini, risk — tek skorda.",
        benefits=["Tek skorda etkililik", "Tükenmişlik + etkililik birlikte", "Kimi destekleyeceğinizi bilin"],
        pain_points=["Hangi koç etkili bilinmiyor"],
    ),
    dict(
        slug="kesfet-veli-guveni", title="Veli güvenini ölçün ve koruyun",
        category_label="Veli Güveni", category_icon="🤝", accent_color=TEAL,
        mockup_type="whatsapp_chat", target_roles=["institution_admin"], domain=FeatureDomain.KURUMSAL.value,
        tier=FeatureTier.CORE.value, strategic_priority=8,
        tagline="Veli kapsaması, aktif veli oranı, bildirim teslim başarısı — yenilemenin sigortası.",
        benefits=["Veli kapsama oranı", "Bildirim teslim başarısı", "Yenileme riskini erken gör"],
        pain_points=["Veli iletişimi tutarsız → retention düşük"],
    ),
]


# strategic_priority sistemde 1-5; göreli sıra korunarak eşle (yüksek = önce)
_PRI = {10: 5, 9: 4, 8: 3, 7: 2}

# Eski genel kartlar — yeni stratejik kartlar öne çıksın diye GİZLENİR (silinmez;
# admin'den republish edilebilir, --delete bunları geri PUBLISHED yapar).
_LEGACY_HIDE = [
    "daily-plan", "aralikli-tekrar", "dna-risk", "soru-bankasi", "veli-kanali",
]


def run(delete: bool = False) -> int:
    created, skipped, removed = 0, 0, 0
    with SessionLocal() as db:
        # Legacy kartların görünürlüğü
        from app.models import FeatureStatus as _FS
        for slug in _LEGACY_HIDE:
            c = fc.get_by_slug(db, slug)
            if c is None:
                continue
            c.status = _FS.PUBLISHED.value if delete else _FS.HIDDEN.value
        for spec in CARDS:
            existing = fc.get_by_slug(db, spec["slug"])
            if delete:
                if existing is not None:
                    fc.delete(db, existing)
                    removed += 1
                continue
            if existing is not None:
                skipped += 1
                print(f"  [atla] {spec['slug']} (zaten var)")
                continue
            spec = {**spec, "strategic_priority": _PRI.get(spec["strategic_priority"], spec["strategic_priority"])}
            fc.create(
                db, actor_id=None, status=FeatureStatus.PUBLISHED.value,
                introduced_at=NOW, cta_label="Detayları gör", **spec,
            )
            created += 1
            print(f"  [+] {spec['slug']}  ({spec['category_label']})")
        db.commit()
    if delete:
        print(f"\n=== {removed} kart silindi ===")
    else:
        print(f"\n=== {created} kart yayınlandı, {skipped} atlandı (zaten vardı) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(delete="--delete" in sys.argv))
