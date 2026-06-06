import { apiServer } from "@/lib/api-server";
import type { SupportListResponse } from "@/lib/types/support";
import type { ParentDashboardResponse } from "@/lib/types/parent";
import { ParentSupportClient } from "@/components/parent/parent-support-client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Koça Talep" };

export default async function ParentSupportPage() {
  const [initial, dash] = await Promise.all([
    apiServer<SupportListResponse>("/api/v2/support/requests"),
    apiServer<ParentDashboardResponse>("/api/v2/parent/dashboard"),
  ]);
  const children = dash.children.map((c) => ({ id: c.student_id, name: c.full_name }));
  return <ParentSupportClient initial={initial} childList={children} />;
}
