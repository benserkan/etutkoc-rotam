import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MetricsResponse } from "@/lib/types/follow-ups";

import { MetricsClient } from "./metrics-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Ölçümler — Süper Admin",
};

export default async function AdminMetricsPage() {
  let data: MetricsResponse;
  try {
    data = await apiServer<MetricsResponse>("/api/v2/admin/metrics");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/admin/metrics"));
    }
    throw e;
  }
  return <MetricsClient initial={data} />;
}
