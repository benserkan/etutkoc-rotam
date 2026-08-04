// /api/v2/pricing — public üyelik/fiyat kataloğu (tek kaynak: app/services/pricing.py)

export interface SoloTier {
  code: string;                 // solo_pro | solo_elite | solo_unlimited
  label: string;
  max_students: number | null;  // null = sınırsız
  monthly: number;
}

export interface InstitutionTier {
  code: string;
  label: string;
  min_coaches: number;
  max_coaches: number | null;
  monthly_total: number | null; // null = özel teklif (price_hidden)
  price_hidden: boolean;
  white_label: boolean;
  short: string;
}

export interface PricingCard {
  key: string;            // free | solo | institution
  audience: string;       // solo | institution
  plan: string;           // plan kodu (signup ?plan=)
  name: string;
  tagline: string;
  monthly: number;        // 0 = ücretsiz; "from" referans aylık
  price_label: string;    // "Ücretsiz" | "2.500 ₺"
  price_unit?: string;    // "/ay"
  price_note?: string;
  tone?: string;          // plain | featured | dark (görsel ton)
  price_hidden?: boolean; // kurum → fiyat gizli, teklif al
  price_caption?: string; // fiyat yerine "Kurumunuza özel teklif"
  cta_href?: string;      // boş ise /signup/teacher?plan=...
  highlight: boolean;
  badge: string | null;   // "En popüler"
  corner: string | null;  // "60 Gün Garanti"
  cta: string;
  features: string[];     // kademeli model: yalnız bu kademenin YENİLERİ
  excluded: string[];
  // Kademeli anlatım + kredi insan-dili (2026-08-04)
  inherits?: string;          // "Keşif'tekilerin hepsi, artı:"
  credit_note?: string;       // "Aylık 1.500 kredi — ... rahat yeter"
  credits_monthly?: number;   // 0 = kredi yok (ücretsiz)
  per_student_note?: string;  // "öğrenci başına ~250 ₺/ay"
}

export interface CreditCostRow {
  label: string;
  credits: number;
}

export interface FeatureGlossaryEntry {
  term: string;                // madde kısa başlığıyla birebir eşleşir
  explanation: string;         // sade, ilk-kez-okuyan dili
  image: string | null;        // KIRPILMIŞ odak görseli (küçükte okunur)
  image_w?: number;            // kırpım boyutları (aspect için)
  image_h?: number;
  image_full?: string | null;  // tam kare — "Ekranın tamamını gör"
}

export interface CreditPack {
  code: string;       // pack_500 | pack_1500 | pack_4000
  credits: number;
  price: number;      // TL, tek seferlik
  per_credit: number; // TL/kredi (bilgi)
}

export interface PricingContact {
  sales_email: string;
  support_email: string;
  whatsapp: string;       // boş → gizli
  phone: string;          // boş → gizli
}

export interface PricingCatalog {
  cards: PricingCard[];
  plan_features: Record<string, string[]>;  // plan kodu → pazarlama bullet'ları (TEK KAYNAK)
  credit_costs: CreditCostRow[];            // "Krediler ne yapar?" tablosu
  credit_packs: CreditPack[];               // kredi ek paketleri (Faz 3)
  feature_glossary: FeatureGlossaryEntry[]; // tıkla-gör balonlar (tek kaynak)
  currency: string;
  annual_paid_months: number;
  contact: PricingContact;
  solo: {
    trial_days: number;
    free: { students: number; ai_included: boolean };
    tiers: SoloTier[];
    ai_included: boolean;
  };
  institution: {
    trial_days: number;
    free: { teachers: number; students: number; ai_included: boolean };
    students_per_coach: number;
    tiers: InstitutionTier[];
    ai_included: boolean;
  };
}
