import { apiServer } from "@/lib/api-server";
import type { TeacherUsageResponse } from "@/lib/types/settings";
import { UsageClient } from "@/components/teacher/usage-client";

/**
 * /teacher/usage — aylık kredi paneli (Paket 9).
 *
 * Kurumlu öğretmen için kurum havuzunu işaret eder; bağımsız öğretmen için
 * kendi havuzunun period özetini, breakdown'unu ve son event'leri gösterir.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Kullanım",
};

export default async function TeacherUsagePage() {
  const data = await apiServer<TeacherUsageResponse>(
    "/api/v2/teacher/usage/current",
  );
  return <UsageClient initial={data} />;
}
