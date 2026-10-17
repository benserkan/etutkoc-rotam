import { apiServer } from "@/lib/api-server";
import { auditFeedQueryString } from "@/lib/api/admin";
import type { AuditCategory, AuditFeedQuery, AuditFeedResponse } from "@/lib/types/admin";
import { AdminAuditFeedClient } from "@/components/admin/admin-audit-feed-client";

/**
 * /admin/audit — Denetim: kim, ne zaman, ne yaptı (2026-10-17).
 * Veri: GET /api/v2/admin/audit/feed — audit_logs + alan olayları birleşik akış.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Denetim — Süper Admin" };

const CATS: AuditCategory[] = ["security", "admin", "coaching", "student", "commercial", "system"];

interface PageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function AdminAuditPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const days = [1, 7, 30, 90].includes(Number(sp.days)) ? Number(sp.days) : 7;
  const query: AuditFeedQuery = {
    days,
    category: CATS.includes(sp.category as AuditCategory) ? (sp.category as AuditCategory) : "all",
    severity: sp.severity === "critical" || sp.severity === "warn" ? sp.severity : "all",
    // Eski bağlantılar (?actor_id=) aynen çalışır
    actorId: sp.actor_id ? Number(sp.actor_id) || null : null,
    q: sp.q ?? "",
    role: sp.role ?? "",
    page: Math.max(1, Number(sp.page) || 1),
  };
  const data = await apiServer<AuditFeedResponse>(`/api/v2/admin/audit/feed?${auditFeedQueryString(query)}`);
  return <AdminAuditFeedClient initial={data} initialQuery={query} />;
}
