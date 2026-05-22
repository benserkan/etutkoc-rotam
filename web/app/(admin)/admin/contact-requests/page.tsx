import { apiServer } from "@/lib/api-server";
import type { ContactRequestListResponse } from "@/lib/types/admin";
import { AdminContactRequestsClient } from "@/components/admin/admin-contact-requests-client";

/**
 * /admin/contact-requests — kurumsal/genel iletişim talepleri.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "İletişim Talepleri — Süper Admin" };

export default async function AdminContactRequestsPage() {
  const data = await apiServer<ContactRequestListResponse>("/api/v2/admin/contact-requests");
  return <AdminContactRequestsClient initial={data} />;
}
