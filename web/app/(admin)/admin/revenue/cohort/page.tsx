import { apiServer } from "@/lib/api-server";
import type { RevenueCohortResponse } from "@/lib/types/admin";
import { AdminRevenueCohortClient } from "@/components/admin/admin-revenue-cohort-client";

/**
 * /admin/revenue/cohort — Kohort & Müşteri Yaşam Değeri (LTV).
 *
 * Jinja kaynağı: admin.py:3940-3978 + revenue_cohort.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kohort & LTV — Süper Admin" };

export default async function AdminRevenueCohortPage() {
  const data = await apiServer<RevenueCohortResponse>(
    "/api/v2/admin/revenue/cohort?months_back=12&horizon=12&churn_days=90",
  );
  return <AdminRevenueCohortClient initial={data} />;
}
