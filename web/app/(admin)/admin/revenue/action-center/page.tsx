import { apiServer } from "@/lib/api-server";
import type { ActionCenterResponse } from "@/lib/types/admin";
import { AdminActionCenterClient } from "@/components/admin/admin-action-center-client";

/**
 * /admin/revenue/action-center — Aksiyon Merkezi (Bugün Ne Yapmalıyım?).
 *
 * Jinja kaynağı: admin.py:3456-3472 + action_center.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Aksiyon Merkezi — Süper Admin" };

export default async function AdminActionCenterPage() {
  const data = await apiServer<ActionCenterResponse>(
    "/api/v2/admin/revenue/action-center",
  );
  return <AdminActionCenterClient initial={data} />;
}
