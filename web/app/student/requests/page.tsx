import { apiServer } from "@/lib/api-server";
import type { StudentRequestListResponse } from "@/lib/types/student";
import { RequestsClient } from "@/components/student/requests-client";

export const metadata = { title: "Taleplerim" };
export const dynamic = "force-dynamic";

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentRequestsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const raw = sp.status;
  const status = typeof raw === "string" ? raw : "all";
  const valid = ["all", "pending", "answered"].includes(status) ? status : "all";
  const data = await apiServer<StudentRequestListResponse>(
    `/api/v2/student/requests?status=${valid}`,
  );
  return <RequestsClient initial={data} initialFilter={valid as "all" | "pending" | "answered"} />;
}
