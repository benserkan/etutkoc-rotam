import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { WaTemplateListResponse } from "@/lib/types/whatsapp-template";

import { WhatsAppTemplatesClient } from "./whatsapp-templates-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "WhatsApp Şablonları — Süper Admin",
};

export default async function AdminWhatsAppTemplatesPage() {
  let data: WaTemplateListResponse;
  try {
    data = await apiServer<WaTemplateListResponse>(
      "/api/v2/admin/whatsapp-templates?include_inactive=true",
    );
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      redirect(
        "/login?returnUrl=" +
          encodeURIComponent("/admin/whatsapp-templates"),
      );
    }
    throw e;
  }

  return <WhatsAppTemplatesClient initial={data} />;
}
