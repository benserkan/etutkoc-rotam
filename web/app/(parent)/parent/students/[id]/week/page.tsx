import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { ParentWeekResponse } from "@/lib/types/parent";
import { ParentWeekClient } from "@/components/parent/parent-week-client";

/**
 * /parent/students/[id]/week — 7 gün read-only program.
 *
 * Jinja kaynağı: parent.py:285-309 + student_week.html (117 satır)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Haftalık Program — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ start?: string }>;
}

export default async function ParentStudentWeekPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const { start } = await searchParams;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();

  const qs = start ? `?start=${encodeURIComponent(start)}` : "";
  let data: ParentWeekResponse;
  try {
    data = await apiServer<ParentWeekResponse>(
      `/api/v2/parent/students/${sid}/week${qs}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <ParentWeekClient initial={data} studentId={sid} startParam={start ?? null} />
  );
}
