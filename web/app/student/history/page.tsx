import { apiServer } from "@/lib/api-server";
import type { ProgramHistoryResponse } from "@/lib/api/program-history";
import { StudentHistoryClient } from "@/components/student/history-client";

export const metadata = { title: "Program geçmişim" };
export const dynamic = "force-dynamic";

export default async function StudentHistoryPage() {
  const data = await apiServer<ProgramHistoryResponse>("/api/v2/student/program-history");
  return <StudentHistoryClient initial={data} />;
}
