// Sosyal kanıt (testimonials) tipleri — public + süper admin.

export type TestimonialKind = "review" | "institution_ref" | "success_story";
export type TestimonialStatus = "pending" | "published" | "hidden";

export interface TestimonialPublicItem {
  id: number;
  kind: TestimonialKind;
  author_name: string;
  author_role: string | null;
  author_role_label: string | null;
  author_title: string | null;
  institution_name: string | null;
  rating: number | null;
  content: string;
  featured: boolean;
}

export interface TestimonialPublicResponse {
  items: TestimonialPublicItem[];
  counts: Record<string, number>;
}

export interface TestimonialSubmitBody {
  content: string;
  rating?: number | null;
  author_name: string;
  consent_public: boolean;
}

export interface TestimonialSubmitResult {
  ok: boolean;
  message: string;
  already_pending: boolean;
}

export interface TestimonialPromptResponse {
  eligible: boolean;
  default_name: string | null;
}

export interface TestimonialAdminItem {
  id: number;
  kind: TestimonialKind;
  kind_label: string;
  author_name: string;
  author_role: string | null;
  author_role_label: string | null;
  author_title: string | null;
  institution_name: string | null;
  rating: number | null;
  content: string;
  status: TestimonialStatus;
  status_label: string;
  source: string;
  source_label: string;
  submitted_by_id: number | null;
  consent_public: boolean;
  featured: boolean;
  sort_order: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TestimonialAdminListResponse {
  items: TestimonialAdminItem[];
  counts: Record<string, number>;
  kinds: Record<string, string>;
  statuses: Record<string, string>;
  roles: Record<string, string>;
}

export interface TestimonialCreateBody {
  kind: TestimonialKind;
  author_name: string;
  author_role?: string | null;
  author_title?: string | null;
  institution_name?: string | null;
  rating?: number | null;
  content: string;
  status: TestimonialStatus;
  consent_public: boolean;
  featured: boolean;
  sort_order: number;
}

export type TestimonialUpdateBody = Partial<
  Omit<TestimonialCreateBody, "status">
>;
