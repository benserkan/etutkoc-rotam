import { apiServer } from "@/lib/api-server";
import type { ActionCenterResponse } from "@/lib/types/institution";
import { ActionCenterClient } from "@/components/institution/action-center-client";

/**
 * /institution/action-center — Müdahale Merkezi.
 *
 * "Bugün kime dokunmalıyım?" — boş program + düşük uyum + riskli öğrenci
 * sinyallerini tek önceliklendirilmiş aksiyon listesinde toplar.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Müdahale Merkezi" };

export default async function InstitutionActionCenterPage() {
  const data = await apiServer<ActionCenterResponse>(
    "/api/v2/institution/action-center",
  );
  return <ActionCenterClient initial={data} />;
}
