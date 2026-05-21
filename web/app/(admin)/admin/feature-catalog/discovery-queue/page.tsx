import { apiServer } from "@/lib/api-server";
import type { DiscoveryQueueResponse } from "@/lib/types/admin";
import { AdminFeatureCatalogDiscoveryClient } from "@/components/admin/admin-feature-catalog-discovery-client";

/**
 * /admin/feature-catalog/discovery-queue — Otomatik keşif onay kuyruğu.
 *
 * Jinja kaynağı: admin.py:2094-2174 + feature_catalog_discovery_queue.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Onay Kuyruğu — Süper Admin" };

export default async function AdminDiscoveryQueuePage() {
  const data = await apiServer<DiscoveryQueueResponse>(
    "/api/v2/admin/feature-catalog/discovery-queue",
  );
  return <AdminFeatureCatalogDiscoveryClient initial={data} />;
}
