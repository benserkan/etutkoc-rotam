// /api/v2/pricing — public üyelik/fiyat kataloğu (tek kaynak: app/services/pricing.py)

export interface SoloBand {
  max_students: number;
  monthly: number;
}

export interface InstitutionTier {
  code: string;
  label: string;
  min_coaches: number;
  max_coaches: number | null;
  per_coach_monthly: number;
  white_label: boolean;
  short: string;
}

export interface PricingCatalog {
  currency: string;
  annual_paid_months: number;
  solo: {
    trial_days: number;
    free: { students: number; ai_included: boolean };
    bands: SoloBand[];
    over_cap_per_student: number;
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
