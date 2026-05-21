import { apiServer } from "@/lib/api-server";
import type { AuditListResponse } from "@/lib/types/admin";
import { AdminAuditClient } from "@/components/admin/admin-audit-client";

/**
 * /admin/audit — Audit log (pagination + filter).
 *
 * Jinja kaynağı: admin.py:1298-1399 + audit_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Audit Log — Süper Admin" };

interface PageProps {
  searchParams: Promise<{
    action?: string;
    actor_id?: string;
    start_date?: string;
    end_date?: string;
    page?: string;
  }>;
}

export default async function AdminAuditPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.action) qs.set("action", sp.action);
  if (sp.actor_id) qs.set("actor_id", sp.actor_id);
  if (sp.start_date) qs.set("start_date", sp.start_date);
  if (sp.end_date) qs.set("end_date", sp.end_date);
  if (sp.page) qs.set("page", sp.page);
  const suffix = qs.toString();
  const data = await apiServer<AuditListResponse>(
    `/api/v2/admin/audit${suffix ? `?${suffix}` : ""}`,
  );

  return (
    <AdminAuditClient
      initial={data}
      initialAction={sp.action ?? null}
      initialActorId={sp.actor_id ? Number(sp.actor_id) : null}
      initialStartDate={sp.start_date ?? null}
      initialEndDate={sp.end_date ?? null}
      initialPage={sp.page ? Number(sp.page) : 1}
    />
  );
}
