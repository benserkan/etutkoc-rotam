import { apiServer } from "@/lib/api-server";
import type {
  InstitutionFilterLevel,
  InstitutionListResponse,
  InstitutionSort,
} from "@/lib/types/admin";
import { AdminInstitutionsClient } from "@/components/admin/admin-institutions-client";

/**
 * /admin/institutions — Kurum listesi (sort + filter + health KPI).
 *
 * Jinja kaynağı: admin.py:217-271 (list_institutions) + institutions_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kurumlar — Süper Admin" };

interface PageProps {
  searchParams: Promise<{
    sort?: string;
    filter_level?: string;
  }>;
}

export default async function AdminInstitutionsPage({
  searchParams,
}: PageProps) {
  const sp = await searchParams;
  const sort: InstitutionSort = (sp.sort === "name" || sp.sort === "created"
    ? sp.sort
    : "health") as InstitutionSort;
  const filterLevel: InstitutionFilterLevel | null =
    sp.filter_level === "unhealthy" || sp.filter_level === "critical"
      ? (sp.filter_level as InstitutionFilterLevel)
      : null;

  const qs = new URLSearchParams();
  qs.set("sort", sort);
  if (filterLevel) qs.set("filter_level", filterLevel);
  const data = await apiServer<InstitutionListResponse>(
    `/api/v2/admin/institutions?${qs.toString()}`,
  );
  return (
    <AdminInstitutionsClient
      initial={data}
      sort={sort}
      filterLevel={filterLevel}
    />
  );
}
