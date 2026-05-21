import { apiServer } from "@/lib/api-server";
import type { RevenueInvoicesResponse } from "@/lib/types/admin";
import { AdminRevenueInvoicesClient } from "@/components/admin/admin-revenue-invoices-client";

/**
 * /admin/security-monitor/revenue/invoices — Tüm faturalar.
 *
 * Jinja kaynağı: admin.py:5165-5227 + security_monitor_invoices.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Faturalar — Süper Admin" };

export default async function AdminRevenueInvoicesPage() {
  const data = await apiServer<RevenueInvoicesResponse>(
    "/api/v2/admin/security-monitor/revenue/invoices",
  );
  return <AdminRevenueInvoicesClient initial={data} />;
}
