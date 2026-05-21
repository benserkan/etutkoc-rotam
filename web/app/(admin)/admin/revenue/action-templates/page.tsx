import { apiServer } from "@/lib/api-server";
import type { ActionTemplatesResponse } from "@/lib/types/admin";
import { AdminActionTemplatesClient } from "@/components/admin/admin-action-templates-client";

/**
 * /admin/revenue/action-templates — CRM aksiyon şablonları.
 *
 * Jinja kaynağı: admin.py:4813-4936 + action_templates.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Aksiyon Şablonları — Süper Admin" };

export default async function AdminActionTemplatesPage() {
  const data = await apiServer<ActionTemplatesResponse>(
    "/api/v2/admin/revenue/action-templates",
  );
  return <AdminActionTemplatesClient initial={data} />;
}
