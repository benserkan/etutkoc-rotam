import { apiServer } from "@/lib/api-server";
import type { InstitutionListResponse } from "@/lib/types/admin";
import { AdminInstitutionsClient, type LevelFilter } from "@/components/admin/admin-institutions-client";

/**
 * /admin/institutions — Kurumlar (2026-10-17): sağlık çipleri + arama +
 * paket/sıra süzgeci (istemcide). Liste daima sağlık sırasıyla çekilir.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kurumlar — Süper Admin" };

const LEVELS: LevelFilter[] = ["all", "critical", "risk", "watch", "healthy"];

interface PageProps {
  searchParams: Promise<{ level?: string; filter_level?: string }>;
}

export default async function AdminInstitutionsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  // Eski bağlantılar: filter_level=critical → Acil ilgi
  const raw = sp.level ?? (sp.filter_level === "critical" ? "critical" : undefined);
  const level: LevelFilter = LEVELS.includes(raw as LevelFilter) ? (raw as LevelFilter) : "all";
  const data = await apiServer<InstitutionListResponse>("/api/v2/admin/institutions?sort=health");
  return <AdminInstitutionsClient initial={data} initialLevel={level} />;
}
