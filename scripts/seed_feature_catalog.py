"""Katman 1+ — Özellik Kataloğu seed.

Anasayfadaki 5 statik kart + 4 yardımcı kart = 9 başlangıç kartı.
Her kart yapısı bire bir anasayfadaki kart iskeletine uyar:
  category_icon + category_label + title + tagline (HTML) + benefits chipler
  + demo_slug + demo_duration_label + accent_color

Kullanım:
    python -m scripts.seed_feature_catalog
    python -m scripts.seed_feature_catalog --reset   # mevcut seed'leri sil + yeniden

Idempotent (reset değilse): aynı slug varsa atlar, mevcut içeriği EZMEZ.
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import (
    FeatureCard,
    FeatureDomain,
    FeatureStatus,
    FeatureTier,
    UserRole,
)
from app.services import feature_catalog as fc


# 9 seed kartı. İlk 5'i anasayfada birebir karşılık, son 4'ü yardımcı/genişletme.
SEEDS: list[dict] = [
    # ──────────────────────── ANASAYFA ────────────────────────
    {
        "slug": "daily-plan",
        "category_icon": "📅",
        "category_label": "Günlük Rota",
        "accent_color": "#0EA5E9",
        "title": "Saniyeler İçinde Günlük Program Oluşturma",
        "tagline": (
            "AI'ın önerdiği görevleri tek tıkla onaylayın, saatleri ve sıraları "
            "düzenleyin. <strong>Öğrenci her gün açtığında o günün rotasını hazır "
            "bulur</strong> — kitap, bölüm ve hedef soru sayısı dahil."
        ),
        "benefits": [
            "⚡ Tek tıkla AI onayı",
            "🔀 Drag-and-drop sıralama",
            "📚 Kitap & bölüm seçimi",
        ],
        "pain_points": [
            "Her öğrenci için saatlerce plan hazırlama",
            "Hangi konunun ne kadar süreceğini tahmin etme",
        ],
        "demo_slug": "daily-plan",
        "demo_duration_label": "2 dk · 8 sahne",
        "mockup_type": "daily_schedule",
        "target_roles": [UserRole.TEACHER, UserRole.STUDENT],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 5,
    },
    {
        "slug": "aralikli-tekrar",
        "category_icon": "🧠",
        "category_label": "FSRS",
        "accent_color": "#7C3AED",
        "title": "Aralıklı Tekrar ve AI Önerileri",
        "tagline": (
            "Öğrencinin geçmiş performansına göre yapay zeka günlük görevler önerir. "
            "FSRS algoritması ile <strong>unutulmaya yüz tutan konular</strong> "
            "tespit edilerek tam zamanında tekrar planlanır."
        ),
        "benefits": [
            "🎯 Konu bazlı tekrar zamanlaması",
            "🌱 Tekrarda zorlananı yakalar",
            "🤖 AI ile günlük öneriler",
        ],
        "pain_points": [
            "Manuel tekrar planlaması zaman alır",
            "Hangi konunun unutulmaya yüz tuttuğu görünmez",
        ],
        "demo_slug": None,
        "demo_duration_label": None,
        "mockup_type": "fsrs_rating",
        "target_roles": [UserRole.STUDENT, UserRole.TEACHER],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 5,
    },
    {
        "slug": "dna-risk",
        "category_icon": "⚠️",
        "category_label": "Risk Radarı",
        "accent_color": "#E11D48",
        "title": "Çalışma DNA'sı ve Risk Paneli",
        "tagline": (
            "Öğrencinin en verimli saatlerini haritalayın. Streak kırılması veya "
            "yoğunluk artışı gibi <strong>5 farklı sinyal</strong> ile tükenmişliği "
            "düşüş yaşanmadan önce yakalayın."
        ),
        "benefits": [
            "🦉 Verimli saat haritalaması",
            "📊 Burnout skoru",
            "🚨 5 farklı erken sinyal",
        ],
        "pain_points": [
            "Tükenmişlik kriz çıkmadan görünmez",
            "Hangi öğrenci geride kalıyor fark edilmez",
        ],
        "demo_slug": "teacher-dna",
        "demo_duration_label": "2 dk · 8 sahne",
        "mockup_type": "burnout_gauge",
        "target_roles": [UserRole.TEACHER, UserRole.STUDENT],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 4,
    },
    {
        "slug": "soru-bankasi",
        "category_icon": "📚",
        "category_label": "Hedef Ağacı",
        "accent_color": "#117A86",
        "title": "Soru Bankası ve Hedef Takibi",
        "tagline": (
            "MEB müfredatına uygun kitap envanteri ile <strong>hangi kitabın yüzde "
            "kaçının bittiğini</strong> görün. Sınav hedeflerini ders bazlı alt "
            "hedeflere bölerek anlık ilerlemeyi ölçün."
        ),
        "benefits": [
            "📖 MEB uyumlu kitap envanteri",
            "🎯 Ders bazlı alt hedefler",
            "📈 Anlık ilerleme yüzdesi",
        ],
        "pain_points": [
            "Hangi kitabın ne kadarının bittiği takip edilmiyor",
            "Hedefler somut adımlara bölünmüyor",
        ],
        "demo_slug": None,
        "demo_duration_label": None,
        "mockup_type": "books_progress",
        "target_roles": [UserRole.TEACHER, UserRole.STUDENT],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 4,
    },
    {
        "slug": "veli-kanali",
        "category_icon": "💬",
        "category_label": "Veli Kanalı",
        "accent_color": "#E8AC2D",
        "title": "WhatsApp ve Kurumsal Raporlama",
        "tagline": (
            "Veliler bildirim tercihlerini (<strong>sessiz saatler dahil</strong>) "
            "kendi yönetir. Haftalık otomatik karneler ve öğretmen notları ile "
            "güven inşa edin."
        ),
        "benefits": [
            "📱 WhatsApp + e-posta",
            "🔕 Sessiz saatler",
            "📊 Haftalık otomatik karne",
        ],
        "pain_points": [
            "Veli sürekli arıyor, durum soruyor",
            "Riskli öğrenci velisi geç haberdar oluyor",
        ],
        "demo_slug": None,
        "demo_duration_label": None,
        "mockup_type": "whatsapp_chat",
        "target_roles": [UserRole.PARENT, UserRole.TEACHER, UserRole.STUDENT],
        "domain": FeatureDomain.VELI.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 4,
    },

    # ──────────────────────── YARDIMCI (anasayfada şu an yok ama katalogda dursun) ────────────────────────
    {
        "slug": "focus-pomodoro",
        "category_icon": "⏱️",
        "category_label": "Odak Modu",
        "accent_color": "#10b981",
        "title": "Pomodoro Odak Seansları",
        "tagline": (
            "Öğrenci için <strong>dikkati toplayan, ödüllendiren</strong> tam ekran "
            "odak seansları. Streak rozetiyle süreklilik teşvik edilir."
        ),
        "benefits": [
            "🎯 Tam ekran, bildirimsiz",
            "🏆 Streak rozetleri",
            "📊 Öğretmen istatistik takibi",
        ],
        "pain_points": [
            "Telefon ve sosyal medya dikkati bölüyor",
            "Hangi öğrenci ne kadar odaklanıyor görünmez",
        ],
        "demo_slug": "focus-pomodoro",
        "demo_duration_label": "2 dk · 8 sahne",
        "target_roles": [UserRole.STUDENT],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.ENHANCEMENT.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 3,
    },
    {
        "slug": "rotam",
        "category_icon": "🧭",
        "category_label": "Akıllı Plan",
        "accent_color": "#06b6d4",
        "title": "Rotam — Akıllı Haftalık Plan",
        "tagline": (
            "Öğrencinin ritmine uyan, kendiliğinden yenilenen çalışma planı. "
            "Geride kalan konuyu <strong>yeni haftaya yedirir</strong>; Pazartesi "
            "sabahı plan hazır."
        ),
        "benefits": [
            "🔄 Otomatik yeniden dengeleme",
            "📅 Haftalık pencere",
            "🚀 Pazartesi sabahı hazır",
        ],
        "pain_points": [
            "Bozulan planı yeniden yapmak zaman alıyor",
            "Geride kalan konuların biriktiği fark edilmiyor",
        ],
        "demo_slug": "daily-plan",
        "demo_duration_label": "2 dk · 8 sahne",
        "target_roles": [UserRole.STUDENT, UserRole.TEACHER],
        "domain": FeatureDomain.GENEL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 4,
    },
    {
        "slug": "yks-mezun-modu",
        "category_icon": "🎓",
        "category_label": "YKS Mezun",
        "accent_color": "#7c3aed",
        "title": "YKS Mezun Hazırlık Modu",
        "tagline": (
            "Tam zamanlı veya dershane — <strong>mezun öğrenciye özel düzen</strong>. "
            "Yaz kampı, dönem-tipi geçişi ve alan filtresi tek modda."
        ),
        "benefits": [
            "⏰ 8-10 saat/gün modu",
            "🏝️ Yaz kampı geçişi",
            "🎯 Alan filtresi (Sayısal/EA/Sözel/Dil)",
        ],
        "pain_points": [
            "Mezun ve aktif öğrenci aynı planı kullanamıyor",
            "Yaz kampı geçişi manuel ve karmaşık",
        ],
        "demo_slug": None,
        "demo_duration_label": None,
        "target_roles": [UserRole.STUDENT, UserRole.TEACHER],
        "domain": FeatureDomain.YKS.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 3,
    },
    {
        "slug": "kurumsal-panel",
        "category_icon": "🏢",
        "category_label": "Kurumsal",
        "accent_color": "#0ea5e9",
        "title": "Kurumsal Yönetici Paneli",
        "tagline": (
            "Multi-tenant: her kurum kendi izole verisi. Kurum yöneticisi öğretmen "
            "verilerine doğrudan ulaşmaz (<strong>gizlilik</strong>) — sadece agrega "
            "raporlar görür."
        ),
        "benefits": [
            "🔒 Tenant izolasyonu",
            "📊 Agrega raporlar",
            "🎚️ Kuruma özel kuota",
        ],
        "pain_points": [
            "Kurum bazlı raporlama yoktu",
            "Kuruma özel ayarlamalar manuel",
        ],
        "demo_slug": None,
        "demo_duration_label": None,
        "target_roles": [UserRole.INSTITUTION_ADMIN, UserRole.SUPER_ADMIN],
        "domain": FeatureDomain.KURUMSAL.value,
        "tier": FeatureTier.CORE.value,
        "status": FeatureStatus.PUBLISHED.value,
        "strategic_priority": 3,
    },
]


def main() -> int:
    reset = "--reset" in sys.argv

    inserted = 0
    skipped = 0
    deleted = 0
    failed: list[str] = []

    with SessionLocal() as db:
        if reset:
            # Tüm mevcut kartları sil (test/seed için, prod'da kullanılmaz)
            cards = db.query(FeatureCard).all()
            deleted = len(cards)
            for c in cards:
                db.delete(c)
            db.commit()
            print(f"  [RESET] {deleted} mevcut kart silindi")

        for seed in SEEDS:
            slug = seed["slug"]
            existing = fc.get_by_slug(db, slug)
            if existing is not None:
                skipped += 1
                print(f"  [SKIP] {slug} (zaten var)")
                continue
            try:
                fc.create(
                    db,
                    actor_id=None,
                    introduced_at=datetime.now(timezone.utc),
                    **seed,
                )
                inserted += 1
                print(f"  [OK]   {slug}")
            except Exception as e:  # noqa: BLE001
                failed.append(f"{slug}: {e}")
                print(f"  [FAIL] {slug} -- {e}")

    print()
    print(f"Toplam: {inserted} eklendi, {skipped} atlandı, {deleted} silindi, {len(failed)} başarısız")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
