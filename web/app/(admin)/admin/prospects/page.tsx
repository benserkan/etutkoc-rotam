import { apiServer } from "@/lib/api-server";
import type { ProspectListResponse } from "@/lib/types/admin";
import { AdminProspectsClient } from "@/components/admin/admin-prospects-client";

/**
 * /admin/prospects — Hedef Havuzu (K1a).
 * Sisteme üye olmayan kurum/koç adayları; üyelik teklifi + WhatsApp tanıtım hedefi.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Hedef Havuzu — Süper Admin" };

export default async function ProspectsPage() {
  const initial = await apiServer<ProspectListResponse>("/api/v2/admin/prospects");
  return <AdminProspectsClient initial={initial} />;
}
