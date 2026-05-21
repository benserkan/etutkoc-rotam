import { apiServer } from "@/lib/api-server";
import type { SubscriptionResponse } from "@/lib/types/institution";
import { SubscriptionClient } from "@/components/institution/subscription-client";

/**
 * /institution/subscription — Abonelik yönetimi (Dalga 4 Paket 7).
 *
 * Jinja kaynağı: app/templates/institution/subscription.html (255 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Abonelik Yönetimi" };

export default async function InstitutionSubscriptionPage() {
  const data = await apiServer<SubscriptionResponse>(
    "/api/v2/institution/subscription",
  );
  return <SubscriptionClient initial={data} />;
}
