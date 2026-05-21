import { apiServer } from "@/lib/api-server";
import type { FocusResponse } from "@/lib/types/student";
import { FocusClient } from "@/components/student/focus-client";

export const metadata = { title: "Odak" };
export const dynamic = "force-dynamic";

export default async function StudentFocusPage() {
  const data = await apiServer<FocusResponse>("/api/v2/student/focus");
  return <FocusClient initial={data} />;
}
