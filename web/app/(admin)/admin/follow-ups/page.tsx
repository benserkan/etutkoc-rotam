import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { FollowUpListResponse } from "@/lib/types/follow-ups";

import { FollowUpsClient } from "./follow-ups-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Takip Listesi — Süper Admin",
};

export default async function AdminFollowUpsPage() {
  let data: FollowUpListResponse;
  try {
    data = await apiServer<FollowUpListResponse>("/api/v2/admin/follow-ups?status=open");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/admin/follow-ups"));
    }
    throw e;
  }
  return <FollowUpsClient initial={data} />;
}
