import { apiServer } from "@/lib/api-server";
import type { ActivityStreamResponse } from "@/lib/types/institution";
import { AdminActivityStreamClient } from "./client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Aktivite Akışı — Süper Admin" };

export default async function AdminActivityStreamPageRoute() {
  const initial = await apiServer<ActivityStreamResponse>(
    "/api/v2/admin/activity-stream?days=30",
  );
  return <AdminActivityStreamClient initial={initial} />;
}
