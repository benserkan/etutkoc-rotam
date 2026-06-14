import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TestimonialAdminListResponse } from "@/lib/types/testimonial";

import { TestimonialsClient } from "./testimonials-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Sosyal Kanıt — Süper Admin",
};

export default async function AdminTestimonialsPage() {
  let data: TestimonialAdminListResponse;
  try {
    data = await apiServer<TestimonialAdminListResponse>("/api/v2/admin/testimonials");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/admin/testimonials"));
    }
    throw e;
  }

  return <TestimonialsClient initial={data} />;
}
