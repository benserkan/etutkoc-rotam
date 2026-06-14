// Sosyal kanıt (testimonials) fetcher'ları — public (anasayfa) + süper admin.
import { api } from "@/lib/api";
import type {
  TestimonialAdminListResponse,
  TestimonialPromptResponse,
  TestimonialPublicResponse,
  TestimonialSubmitBody,
  TestimonialSubmitResult,
} from "@/lib/types/testimonial";

export const testimonialKeys = {
  public: (kind: string | null) => ["testimonials", "public", kind ?? ""] as const,
  admin: (status: string | null, kind: string | null) =>
    ["admin", "testimonials", status ?? "", kind ?? ""] as const,
  prompt: () => ["testimonials", "prompt"] as const,
};

/** Uygulama-içi: 'Deneyimini paylaş' kartı bu kullanıcıya gösterilsin mi. */
export function getTestimonialPrompt(): Promise<TestimonialPromptResponse> {
  return api<TestimonialPromptResponse>("/api/v2/testimonials/prompt");
}

/** Uygulama-içi: kullanıcı kendi deneyimini gönderir → moderasyon (pending). */
export function submitTestimonial(
  body: TestimonialSubmitBody,
): Promise<TestimonialSubmitResult> {
  return api<TestimonialSubmitResult>("/api/v2/testimonials/submit", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Anasayfa — yayınlanmış sosyal kanıt + sayımlar (login'siz). */
export function getPublicTestimonials(
  kind: string | null = null,
  limit = 24,
): Promise<TestimonialPublicResponse> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (kind) q.set("kind", kind);
  return api<TestimonialPublicResponse>(`/api/v2/testimonials?${q.toString()}`);
}

/** Süper admin — tüm kayıtlar (moderasyon). */
export function getAdminTestimonials(
  status: string | null = null,
  kind: string | null = null,
): Promise<TestimonialAdminListResponse> {
  const q = new URLSearchParams();
  if (status) q.set("status", status);
  if (kind) q.set("kind", kind);
  const qs = q.toString();
  return api<TestimonialAdminListResponse>(
    `/api/v2/admin/testimonials${qs ? `?${qs}` : ""}`,
  );
}
