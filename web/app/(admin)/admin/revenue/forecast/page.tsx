import { apiServer } from "@/lib/api-server";
import type { RevenueForecastResponse } from "@/lib/types/admin";
import { AdminRevenueForecastClient } from "@/components/admin/admin-revenue-forecast-client";

/**
 * /admin/revenue/forecast — MRR Tahmin & Senaryo.
 *
 * Jinja kaynağı: admin.py:3901-3937 + revenue_forecast.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Tahmin & Senaryo — Süper Admin" };

export default async function AdminRevenueForecastPage() {
  const data = await apiServer<RevenueForecastResponse>(
    "/api/v2/admin/revenue/forecast?save_rate=0.5",
  );
  return <AdminRevenueForecastClient initial={data} />;
}
