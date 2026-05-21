import { apiServer } from "@/lib/api-server";
import type { BurnoutResponse } from "@/lib/types/institution";
import { BurnoutClient } from "@/components/institution/burnout-client";

/**
 * /institution/burnout — Kurum geneli tükenmişlik panosu.
 *
 * Jinja kaynağı: app/templates/institution/burnout.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Tükenmişlik Panosu" };

export default async function InstitutionBurnoutPage() {
  const data = await apiServer<BurnoutResponse>(
    "/api/v2/institution/burnout",
  );
  return <BurnoutClient initial={data} />;
}
