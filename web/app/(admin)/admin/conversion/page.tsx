import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { ConversionResponse } from "@/lib/types/conversion";

import { ConversionClient } from "./conversion-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Dönüşüm Hunisi — Süper Admin",
};

export default async function AdminConversionPage() {
  let data: ConversionResponse;
  try {
    data = await apiServer<ConversionResponse>("/api/v2/admin/conversion?days=30");
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect("/login?returnUrl=" + encodeURIComponent("/admin/conversion"));
    }
    throw e;
  }

  return <ConversionClient initial={data} />;
}
