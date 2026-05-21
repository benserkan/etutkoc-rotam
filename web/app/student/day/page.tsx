import { apiServer } from "@/lib/api-server";
import type { StudentDayResponse } from "@/lib/types/student";
import { DayClient } from "@/components/student/day-client";

/**
 * /student/day — interaktif öğrenci günü (Paket 6).
 *
 * Server Component initial fetch yapar; DayClient bu snapshot'ı TanStack Query
 * `initialData` olarak kullanır. Sonrasında tüm tikleme + modal akışları
 * client-side yürür; backend mutation'ları invalidate listesiyle gelir.
 *
 * URL `?date=YYYY-MM-DD` — DayHeader navigasyonu router.push ile bunu değiştirir;
 * Server Component re-fetch eder.
 */
export const metadata = {
  title: "Bugün",
};

export const dynamic = "force-dynamic";

interface StudentDayPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentDayPage({
  searchParams,
}: StudentDayPageProps) {
  const sp = await searchParams;
  const raw = sp.date;
  const date = typeof raw === "string" ? raw : undefined;
  const qs = date ? `?date=${encodeURIComponent(date)}` : "";
  const day = await apiServer<StudentDayResponse>(`/api/v2/student/day${qs}`);
  return <DayClient initial={day} />;
}
