import { apiServer } from "@/lib/api-server";
import type { LibraryBookListResponse } from "@/lib/types/library";
import { LibraryListClient } from "@/components/teacher/library-list-client";

/**
 * /teacher/library — kitap kütüphanesi (Paket 8).
 *
 * Filtreler URL search params üzerinden: q, subject_id, type, grade_level.
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Kitap kütüphanesi",
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

export default async function LibraryPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const q = firstStr(sp.q) ?? "";
  const type = firstStr(sp.type) ?? "";
  const subjectId = toInt(firstStr(sp.subject_id));
  const grade = toInt(firstStr(sp.grade_level));

  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  if (type) qs.set("type", type);
  if (subjectId !== undefined) qs.set("subject_id", String(subjectId));
  if (grade !== undefined) qs.set("grade_level", String(grade));
  const queryString = qs.toString();

  const data = await apiServer<LibraryBookListResponse>(
    `/api/v2/teacher/library/books${queryString ? "?" + queryString : ""}`,
  );

  return (
    <LibraryListClient
      initial={data}
      initialFilters={{ q, type, subject_id: subjectId, grade_level: grade }}
    />
  );
}
