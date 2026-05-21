import { apiServer } from "@/lib/api-server";
import type { WeekPrintResponse } from "@/lib/types/student";
import { WeekPrintSheet } from "@/components/student/week-print-sheet";

/**
 * /student/week/print — Next.js A4 yatay yazdırma sayfası.
 *
 * Route group `(print)` sayesinde `app/student/layout.tsx` (SiteHeader içeren)
 * bu sayfaya uygulanmaz. Sadece root `app/layout.tsx` zinciri çalışır.
 * `@media print` kuralları client tarafında bütün ekstra UI'yi gizler.
 *
 * Veri kaynağı: /api/v2/student/week-print?start=YYYY-MM-DD
 */
export const metadata = { title: "Haftalık Program — Yazdır" };
export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentWeekPrintPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const raw = sp.start;
  const start = typeof raw === "string" ? raw : undefined;
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  const data = await apiServer<WeekPrintResponse>(`/api/v2/student/week-print${qs}`);
  return <WeekPrintSheet data={data} />;
}
