import { apiServer } from "@/lib/api-server";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import { StudentsListClient } from "@/components/teacher/students-list-client";
import type { FilterValues } from "@/components/teacher/students-filter-bar";

/**
 * /teacher/students — server initial fetch + client interaktif filtreler.
 *
 * URL search params filtre kaynağıdır. Client tarafı `useTransition` ile
 * yumuşatılmış `router.replace` kullanır; sayfa yenilenmez, snapshot URL'le
 * paylaşılabilir kalır.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Öğrenciler",
};

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstStr(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

function toInt(v: string | undefined): number | undefined {
  if (!v) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export default async function TeacherStudentsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const q = firstStr(sp.q) ?? "";
  const grade = firstStr(sp.grade_level) ?? "";
  const riskRaw = firstStr(sp.risk) ?? "all";
  const risk: FilterValues["risk"] =
    riskRaw === "ok" ||
    riskRaw === "medium" ||
    riskRaw === "high" ||
    riskRaw === "critical"
      ? riskRaw
      : "all";
  const pageSizeRaw = toInt(firstStr(sp.page_size)) ?? 25;
  const pageSize = (pageSizeRaw === 50 || pageSizeRaw === 100 ? pageSizeRaw : 25) as
    | 25
    | 50
    | 100;
  const page = toInt(firstStr(sp.page)) ?? 1;

  const initialFilters: FilterValues = {
    q,
    grade_level: grade,
    risk,
    page_size: pageSize,
  };

  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  if (risk !== "all") qs.set("risk", risk);
  const gradeNum = toInt(grade);
  if (gradeNum !== undefined) qs.set("grade_level", String(gradeNum));
  if (page > 1) qs.set("page", String(page));
  if (pageSize !== 25) qs.set("page_size", String(pageSize));
  const queryString = qs.toString();

  const data = await apiServer<TeacherStudentListResponse>(
    `/api/v2/teacher/students${queryString ? "?" + queryString : ""}`,
  );

  return (
    <StudentsListClient
      initial={data}
      initialFilters={initialFilters}
      initialPage={page}
    />
  );
}
