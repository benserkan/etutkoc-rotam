import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { WeeklyReportResponse } from "@/lib/types/parent";
import { ParentWeeklyReportClient } from "@/components/parent/parent-weekly-report-client";

/**
 * /parent/students/[id]/report — Veliye doyurucu haftalık rapor.
 *
 * Bu hafta özeti + geçen haftaya kıyas + ders kırılımı (en çok çözülen /
 * aksatılan) + deneme net trendi + gün gün + koç notu + genel değerlendirme.
 * KVKK guard: bağ yoksa backend 404 → notFound().
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Haftalık Rapor — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ week_start?: string }>;
}

export default async function ParentWeeklyReportPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const { week_start } = await searchParams;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();

  const qs = week_start
    ? `?week_start=${encodeURIComponent(week_start)}`
    : "";
  let data: WeeklyReportResponse;
  try {
    data = await apiServer<WeeklyReportResponse>(
      `/api/v2/parent/students/${sid}/weekly-report${qs}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <ParentWeeklyReportClient
      initial={data}
      studentId={sid}
      weekStartParam={week_start ?? null}
    />
  );
}
