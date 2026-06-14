// Dönüşüm (conversion) hunisi tipleri — süper admin.

export interface ConversionFunnel {
  visitors: number;
  engaged: number;
  clicked: number;
  demo: number;
  signups_landing: number;
  signups_direct: number;
  signups_total: number;
  paid_total: number;
  paid_landing: number;
  rate_visitor_engaged: number;
  rate_engaged_demo: number;
  rate_visitor_signup: number;
  rate_signup_paid: number;
  rate_visitor_paid: number;
}

export interface ConversionVariantRow {
  slug: string;
  sessions: number;
  signups: number;
  conversion_pct: number;
  paid: number;
  paid_pct: number;
}

export interface ConversionResponse {
  days: number;
  funnel: ConversionFunnel;
  variants: ConversionVariantRow[];
  has_experiment: boolean;
  experiment_name: string | null;
}
