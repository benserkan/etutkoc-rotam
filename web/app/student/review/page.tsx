import { apiServer } from "@/lib/api-server";
import type { ReviewResponse } from "@/lib/types/student";
import { ReviewClient } from "@/components/student/review-client";

export const metadata = { title: "Tekrar" };
export const dynamic = "force-dynamic";

export default async function StudentReviewPage() {
  const data = await apiServer<ReviewResponse>("/api/v2/student/review");
  return <ReviewClient initial={data} />;
}
