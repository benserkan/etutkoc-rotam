import { apiServer } from "@/lib/api-server";
import type { InvitationListResponse } from "@/lib/types/institution";
import { InvitationsClient } from "@/components/institution/invitations-client";

/**
 * /institution/invitations — Öğretmen davetiye yönetimi.
 *
 * Jinja kaynağı: app/templates/institution/invitations.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Davetiyeler" };

export default async function InstitutionInvitationsPage() {
  const data = await apiServer<InvitationListResponse>(
    "/api/v2/institution/invitations",
  );
  return <InvitationsClient initial={data} />;
}
