import { apiServer } from "@/lib/api-server";
import type { BillingMonthResponse } from "@/lib/types/teacher";
import { BillingClient } from "@/components/teacher/billing-client";

/**
 * /teacher/billing — bağımsız koç aylık tahsilat panosu (KS2).
 *
 * Yapılan seans (status=done) × öğrenci ücreti − ödenen = kalan alacak.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Tahsilat" };

function currentMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default async function TeacherBillingPage() {
  const month = currentMonth();
  const data = await apiServer<BillingMonthResponse>(
    `/api/v2/teacher/billing?month=${month}`,
  );
  return <BillingClient initialMonth={month} initial={data} />;
}
