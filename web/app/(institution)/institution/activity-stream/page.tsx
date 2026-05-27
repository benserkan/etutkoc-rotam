import { apiServer } from "@/lib/api-server";
import type { ActivityStreamResponse } from "@/lib/types/institution";
import { InstitutionActivityStreamClient } from "./client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Aktivite Akışı — Kurum" };

export default async function InstitutionActivityStreamPageRoute() {
  const initial = await apiServer<ActivityStreamResponse>(
    "/api/v2/institution/activity-stream?days=30",
  );
  return <InstitutionActivityStreamClient initial={initial} />;
}
