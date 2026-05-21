/**
 * Public landing (anasayfa vitrin) tipleri — `/api/v2/landing` ile birebir.
 */
export interface LandingCard {
  slug: string;
  title: string;
  tagline: string;
  category_icon: string;
  category_label: string;
  accent_color: string;
  benefits: string[];
  demo_slug: string | null;
  demo_duration_label: string | null;
  mockup_type: string | null;
}

export interface LandingResponse {
  cards: LandingCard[];
  variant_slug: string | null;
}
