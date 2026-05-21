import { apiServer } from "@/lib/api-server";
import type { InstitutionRosterResponse } from "@/lib/types/institution";
import { RosterClient } from "@/components/institution/roster-client";

/**
 * /institution/roster — Tüm öğrenciler + filtre.
 *
 * Jinja kaynağı: app/templates/institution/roster.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Roster" };

interface PageProps {
  searchParams: Promise<{
    teacher_id?: string;
    grade?: string;
  }>;
}

export default async function InstitutionRosterPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const teacherId =
    sp.teacher_id && /^\d+$/.test(sp.teacher_id)
      ? Number(sp.teacher_id)
      : undefined;
  let grade: number | undefined;
  let isGraduate: boolean | undefined;
  if (sp.grade === "graduate") {
    isGraduate = true;
  } else if (sp.grade && /^\d+$/.test(sp.grade)) {
    grade = Number(sp.grade);
  }

  const qs = new URLSearchParams();
  if (teacherId != null) qs.set("teacher_id", String(teacherId));
  if (grade != null) qs.set("grade", String(grade));
  if (isGraduate != null) qs.set("is_graduate", String(isGraduate));
  const suffix = qs.toString();

  const data = await apiServer<InstitutionRosterResponse>(
    `/api/v2/institution/roster${suffix ? `?${suffix}` : ""}`,
  );
  return (
    <RosterClient
      initial={data}
      params={{
        teacher_id: teacherId ?? null,
        grade: grade ?? null,
        is_graduate: isGraduate ?? null,
      }}
    />
  );
}
