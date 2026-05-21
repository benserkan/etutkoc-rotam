import { apiServer } from "@/lib/api-server";
import type { TeacherDashboardResponse } from "@/lib/types/teacher";
import { DashboardClient } from "@/components/teacher/dashboard-client";

/**
 * /teacher/dashboard — Server Component initial fetch + Client interaktif.
 *
 * R-007: cache "no-store" + dynamic = "force-dynamic" — App Router cache yok.
 * DashboardClient `initialData` ile hydrate olur; 30s stale + window focus refetch.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Öğretmen panosu",
};

export default async function TeacherDashboardPage() {
  const data = await apiServer<TeacherDashboardResponse>(
    "/api/v2/teacher/dashboard",
  );
  return <DashboardClient initial={data} />;
}
