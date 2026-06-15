"""Anasayfa kartlarındaki sağ-yan mockup şablon kütüphanesi.

Her mockup ayrı bir Jinja template fragment'ı (`app/templates/landing/mockups/`).
Bu modül, admin formundaki "Görsel şablon seç" dropdown'u + Katman 2'de
catalog-bazlı render için tek doğruluk kaynağı.

Yeni mockup eklemek için:
1. `app/templates/landing/mockups/<key>.html` dosyasını oluştur
2. Aşağıdaki MOCKUP_TEMPLATES sözlüğüne kaydet (key, label, sample title)
3. Migration GEREKMEZ — sadece text alanı (FeatureCard.mockup_type)

Admin formunda dropdown bu kayıtlardan beslenir.
Katman 2 render time'da: `{% include 'landing/mockups/' + key + '.html' %}`.

NOT: Mockup içerikleri ŞU AN HARDCODED. Gelecekte mockup_data_json ile
dinamikleştirilebilir (örn. öğrenci adı, tarih, görev satırları). Şimdiki
versiyon mevcut anasayfa görüntüsünü birebir korumak için statik.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MockupTemplate:
    """Bir mockup şablonunun kayıt bilgisi."""
    key: str                 # FeatureCard.mockup_type değeri (örn. "daily_schedule")
    label: str               # Admin dropdown'da görünen TR ad
    description: str         # Kısa açıklama — koç hangi karta uygun
    template_path: str       # "landing/mockups/<key>.html"
    feature_card_slug: str   # Hangi anasayfa kartından çıkarıldı


# Mevcut anasayfadaki 5 mockup'ın kayıtları.
# Sıralama → admin dropdown sırası.
MOCKUP_TEMPLATES: dict[str, MockupTemplate] = {
    "daily_schedule": MockupTemplate(
        key="daily_schedule",
        label="Günlük Program Tablosu",
        description="Saat + ders + görev satırlı tablo (Saniyeler İçinde Günlük Program kartının görseli)",
        template_path="landing/mockups/daily_schedule.html",
        feature_card_slug="daily-plan",
    ),
    "fsrs_rating": MockupTemplate(
        key="fsrs_rating",
        label="FSRS Rating Kartı",
        description="Bugünkü kart + 4 rating butonu (Tekrar/Zor/İyi/Kolay)",
        template_path="landing/mockups/fsrs_rating.html",
        feature_card_slug="aralikli-tekrar",
    ),
    "burnout_gauge": MockupTemplate(
        key="burnout_gauge",
        label="Burnout Risk Gauge",
        description="Yüzde gauge + bar + sinyal chipleri (Risk Radarı kartının görseli)",
        template_path="landing/mockups/burnout_gauge.html",
        feature_card_slug="dna-risk",
    ),
    "books_progress": MockupTemplate(
        key="books_progress",
        label="Kitap İlerleme Barları",
        description="Ders bazında ilerleme yüzdeleri (Soru Bankası kartının görseli)",
        template_path="landing/mockups/books_progress.html",
        feature_card_slug="soru-bankasi",
    ),
    "whatsapp_chat": MockupTemplate(
        key="whatsapp_chat",
        label="WhatsApp Sohbet",
        description="Veli mesaj balonu + haftalık karne (Veli Kanalı kartının görseli)",
        template_path="landing/mockups/whatsapp_chat.html",
        feature_card_slug="veli-kanali",
    ),
    # Temalı/AI kartlar için inandırıcı mini-UI'lar (özelliği canlandırır). AI
    # gruplama her temaya en uygun olanı seçer; admin formdan değiştirebilir.
    "gamification": MockupTemplate(
        key="gamification",
        label="Motivasyon / Oyunlaştırma",
        description="Seri + seviye barı + rozetler + puan (motivasyon/odaklanma temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "ai_assistant": MockupTemplate(
        key="ai_assistant",
        label="Yapay Zeka Asistanı",
        description="AI öneri kartı / 'bugün şunu konuş' baloncuğu (yapay zekâ temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "exam_trend": MockupTemplate(
        key="exam_trend",
        label="Deneme / Net Gelişimi",
        description="Net trend grafiği + son deneme skoru (deneme/akademik takip temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "security": MockupTemplate(
        key="security",
        label="Güvenlik / KVKK",
        description="Kalkan + kilit + KVKK/şifreli rozetleri (kurumsal güvenlik / veri gizliliği temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "billing": MockupTemplate(
        key="billing",
        label="Ödeme / Üyelik / Tahsilat",
        description="Plan kartı + ödeme özeti + 'ödendi' rozeti (ödeme/üyelik/tahsilat/finans temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "analytics": MockupTemplate(
        key="analytics",
        label="Veri Analizi / Panel",
        description="KPI kartları + çizgi grafik (veri analizi / optimizasyon / içgörü temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "crm": MockupTemplate(
        key="crm",
        label="CRM / Müşteri İlişkileri",
        description="Kişi listesi + not + aşama rozetleri (CRM / satış / müşteri ilişkileri temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "branding": MockupTemplate(
        key="branding",
        label="Kurumsal Kimlik / Logo",
        description="Logolu panel başlığı önizlemesi (markalaşma / kurumsal kimlik / co-branding temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "support": MockupTemplate(
        key="support",
        label="Destek / Sistem Sağlığı",
        description="Destek talebi + sistem durum göstergeleri (destek / yardım / sistem sağlığı temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "curriculum": MockupTemplate(
        key="curriculum",
        label="Akademik Yapı / Müfredat",
        description="Sınıf seviyesi + müfredat modeli rozetleri (LGS/YKS akademik yapı / müfredat temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    # Demo konularından eklenen (2026-06-15): odak / hedef / konu performansı
    "focus_timer": MockupTemplate(
        key="focus_timer",
        label="Odak / Pomodoro",
        description="Geri sayım halkası + seri + oturum (odaklı çalışma / Pomodoro temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "goals": MockupTemplate(
        key="goals",
        label="Hedefler",
        description="Ana hedef + alt hedef ağacı + ilerleme (hedef belirleme / motivasyon temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    "topic_performance": MockupTemplate(
        key="topic_performance",
        label="Konu Performansı",
        description="Ders/konu bazında doğruluk barları (konu analizi / eksik tespit temaları)",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
    # Genel/şablonsuz kart — bespoke görsel gerektirmeden landing'e çıkar. AI hiçbir
    # özel mockup'a karar veremezse fallback. Next.js GenericShowcase render eder.
    "generic": MockupTemplate(
        key="generic",
        label="Genel Vitrin Kartı (şablonsuz)",
        description="Marka temalı genel görsel — uygun özel mockup yoksa fallback",
        template_path="landing/mockups/generic.html",
        feature_card_slug="",
    ),
}


def get_mockup(key: str | None) -> MockupTemplate | None:
    """Verilen key için mockup bilgisini döndür; yoksa None."""
    if not key:
        return None
    return MOCKUP_TEMPLATES.get(key)


def list_mockups() -> list[MockupTemplate]:
    """Admin dropdown için kayıt sırasında liste."""
    return list(MOCKUP_TEMPLATES.values())


def is_valid_key(key: str | None) -> bool:
    """Mockup key'i geçerli mi (None veya "none" da kabul)."""
    if not key or key == "none":
        return True
    return key in MOCKUP_TEMPLATES


def template_path_for(key: str | None) -> str | None:
    """Render için template path döndür; geçersiz/boş key None döner."""
    tpl = get_mockup(key)
    return tpl.template_path if tpl else None
