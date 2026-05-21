import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TeacherStudentDayResponse } from "@/lib/types/teacher";
import { DayBoard } from "@/components/teacher/day-board";

/**
 * /teacher/students/[id]/day — server initial fetch + interaktif day board.
 *
 * Görev ekle/sil + kalem PATCH akışları gün cache'i üzerinde optimistic
 * update yapar; backend `MutationResponse.invalidate` ile gün/hafta/dashboard
 * sayaçları bayatlatılır (R-006).
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
  return { title: `Günlük plan · #${id}` };
}

export default async function TeacherStudentDayPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  const date = firstStr(sp.date);
  const qs = date ? `?date=${encodeURIComponent(date)}` : "";

  let data: TeacherStudentDayResponse;
  try {
    data = await apiServer<TeacherStudentDayResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(String(numericId))}/day${qs}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <DayBoard
      studentId={numericId}
      initial={data}
      initialDate={date ?? data.date}
    />
  );
}
