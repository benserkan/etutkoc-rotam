import { apiServer } from "@/lib/api-server";
import type { AdminIndependentTeachersResponse } from "@/lib/types/admin";
import { AdminIndependentTeachersClient } from "@/components/admin/admin-independent-teachers-client";

/**
 * /admin/independent-teachers — Bağımsız öğretmenler aktivite listesi.
 *
 * Jinja kaynağı: admin.py:131-147 + 4-band heuristik (P1'de aynı).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bağımsız Öğretmenler — Süper Admin" };

export default async function AdminIndependentTeachersPage() {
  const data = await apiServer<AdminIndependentTeachersResponse>(
    "/api/v2/admin/independent-teachers",
  );
  return <AdminIndependentTeachersClient initial={data} />;
}
