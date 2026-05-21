import { apiServer } from "@/lib/api-server";
import type { AdminUsageResponse } from "@/lib/types/admin";
import { AdminUsageClient } from "@/components/admin/admin-usage-client";

/**
 * /admin/usage — Sistem geneli kredi kullanımı (kurumlar + bağımsız öğretmenler).
 *
 * Jinja kaynağı: admin.py:1405-1495 + usage_dashboard.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kredi Kullanımı — Süper Admin" };

interface PageProps {
  searchParams: Promise<{ tab?: string }>;
}

export default async function AdminUsagePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const tab = sp.tab === "independents" ? "independents" : "institutions";
  const data = await apiServer<AdminUsageResponse>("/api/v2/admin/usage");
  return <AdminUsageClient initial={data} initialTab={tab} />;
}
