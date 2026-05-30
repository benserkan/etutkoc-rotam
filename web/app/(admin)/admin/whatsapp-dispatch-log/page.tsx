import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { DispatchLogResponse } from "@/lib/types/messaging";

import { DispatchLogClient } from "./dispatch-log-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "WhatsApp Dispatch Log — Süper Admin",
};

export default async function AdminWhatsAppDispatchLogPage() {
  let data: DispatchLogResponse;
  try {
    data = await apiServer<DispatchLogResponse>(
      "/api/v2/admin/whatsapp-dispatch-log?days=7&limit=50",
    );
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect(
        "/login?returnUrl=" +
          encodeURIComponent("/admin/whatsapp-dispatch-log"),
      );
    }
    throw e;
  }

  return <DispatchLogClient initial={data} />;
}
