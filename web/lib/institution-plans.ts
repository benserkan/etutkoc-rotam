// Kurum planı görüntüleme/seçim yardımcıları — /api/v2/pricing kataloğundan
// türetilir (tek kaynak). Admin "Yeni Kurum" + kurum detay düzenleme paylaşır.

import type { PricingCatalog } from "@/lib/types/pricing";

export const INSTITUTION_PLAN_LABELS: Record<string, string> = {
  institution_trial: "30 Günlük Pilot",
  institution_free: "Kurum Tanıma",
  etut_standart: "Etüt Standart",
  dershane_pro: "Dershane Pro",
  enterprise: "Özel Okul / Enterprise",
  // eski/legacy kodlar (geriye uyum)
  free: "Kurum Tanıma",
  starter: "Etüt Standart",
  professional: "Dershane Pro",
};

export function institutionPlanLabel(code: string | null | undefined): string {
  if (!code) return "Kurum Tanıma";
  return INSTITUTION_PLAN_LABELS[code] ?? code;
}

export interface InstitutionPlanOption {
  value: string;
  label: string;
  coaches: string; // koç aralığı (örn. "2–10 koç")
  desc: string;
}

// Free her zaman ilk seçenek; ardından kurum kademeleri (etut/dershane/enterprise).
export function buildInstitutionPlanOptions(
  catalog: PricingCatalog | undefined,
): InstitutionPlanOption[] {
  const free: InstitutionPlanOption = {
    value: "institution_free",
    label: "Kurum Tanıma (Ücretsiz)",
    coaches: catalog
      ? `${catalog.institution.free.teachers} öğretmen · ${catalog.institution.free.students} öğrenci`
      : "2 öğretmen · 20 öğrenci",
    desc: "Pilot sonrası ücretsiz tanıma planı; yapay zekâ kapalı.",
  };
  const tiers = (catalog?.institution.tiers ?? []).map((t) => ({
    value: t.code,
    label: t.label,
    coaches: t.max_coaches == null ? `${t.min_coaches}+ koç` : `${t.min_coaches}–${t.max_coaches} koç`,
    desc:
      (t.short || "") +
      (t.price_hidden || t.monthly_total == null
        ? " · Özel teklif"
        : ` · ${t.monthly_total.toLocaleString("tr-TR")} ₺/ay`),
  }));
  return [free, ...tiers];
}
