import { apiServer } from "@/lib/api-server";
import type { ParentTrustResponse } from "@/lib/types/institution";
import { ParentTrustClient } from "@/components/institution/parent-trust-client";

/**
 * /institution/parent-trust — Veli Güveni Görünürlüğü.
 *
 * Veli kapsaması + aktif veli + bekleyen davet + bildirim teslimat sağlığı.
 * Kurumun veli nezdindeki değeri (kayıt yenileme/tavsiye buradan beslenir).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Veli Güveni" };

export default async function InstitutionParentTrustPage() {
  const data = await apiServer<ParentTrustResponse>(
    "/api/v2/institution/parent-trust?days=30",
  );
  return <ParentTrustClient initial={data} />;
}
