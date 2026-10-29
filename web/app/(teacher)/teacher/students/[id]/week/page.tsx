import Link from "next/link";
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
  // Koltuk ızgarasından "o günün programında göster" → görevi ızgarada vurgula
  const taskParam = Number(firstStr(sp.task));
  const focusTaskId =
    Number.isInteger(taskParam) && taskParam > 0 ? taskParam : null;
  const qsParts: string[] = [];
  if (start) qsParts.push(`start=${encodeURIComponent(start)}`);
  if (programId) qsParts.push(`program_id=${encodeURIComponent(programId)}`);
  const qs = qsParts.length ? `?${qsParts.join("&")}` : "";

  // Havuz modundaki öğrencide gün-gün editör AÇILMAZ (Basamak 9 türeyen kural):
  // iki editör aynı öğrencide karışmasın. Gün-gün öğrencisi için hiçbir şey değişmez.
  let detail: { student?: { program_mode?: string; full_name?: string } } | null = null;
  try {
    detail = await apiServer(`/api/v2/teacher/students/${encodeURIComponent(String(numericId))}`);
  } catch {
    detail = null;
  }
  if (detail?.student?.program_mode === "havuz") {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-5 text-cyan-900">
          <h1 className="text-lg font-semibold">Bu öğrenci haftalık havuz modunda</h1>
          <p className="mt-1 text-sm">
            {detail.student.full_name ?? "Öğrenci"} için program gün gün değil, haftalık görev havuzuyla
            yazılır. Gün gün editör bu öğrencide kapalıdır; önceki gün gün haftaları Program geçmişinden
            salt okunur açılır.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href={`/teacher/students/${numericId}/pool`}
              className="inline-flex items-center rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-800"
            >
              Haftalık havuzu aç
            </Link>
            <Link
              href={`/teacher/students/${numericId}#history`}
              className="inline-flex items-center rounded-md border border-cyan-700 bg-white px-3 py-2 text-sm font-medium text-cyan-900 hover:bg-cyan-50"
            >
              Program geçmişi (önceki haftalar)
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
      key={`${start ?? ""}:${programId ?? ""}:${focusTaskId ?? ""}`}
      focusTaskId={focusTaskId}
      studentId={numericId}
      initial={data}
      initialStart={start ?? data.start_date}
    />
  );
}
