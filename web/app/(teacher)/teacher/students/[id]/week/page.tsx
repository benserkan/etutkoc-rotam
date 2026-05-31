import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TeacherStudentWeekResponse } from "@/lib/types/teacher";
import { WeekBoard } from "@/components/teacher/week-board";

/**
 * /teacher/students/[id]/week — server initial fetch + interaktif week board.
 *
 * "Haftaya yay" akışı (bulk-tasks) atomik: tüm görevler başarılıysa kaydedilir
 * veya tek hata varsa hiçbiri kaydedilmez (SAVEPOINT, backend).
 */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function firstStr(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Haftalık plan · #${id}` };
}

export default async function TeacherStudentWeekPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  const start = firstStr(sp.start);
  const programId = firstStr(sp.program_id);
  const qsParts: string[] = [];
  if (start) qsParts.push(`start=${encodeURIComponent(start)}`);
  if (programId) qsParts.push(`program_id=${encodeURIComponent(programId)}`);
  const qs = qsParts.length ? `?${qsParts.join("&")}` : "";

  let data: TeacherStudentWeekResponse;
  try {
    data = await apiServer<TeacherStudentWeekResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(String(numericId))}/week${qs}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <WeekBoard
      studentId={numericId}
      initial={data}
      initialStart={start ?? data.start_date}
    />
  );
}
