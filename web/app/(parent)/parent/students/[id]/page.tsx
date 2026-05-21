import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { ParentStudentOverviewResponse } from "@/lib/types/parent";
import { ParentStudentDetailClient } from "@/components/parent/parent-student-detail-client";

/**
 * /parent/students/[id] — Öğrenci detay (read-only).
 *
 * Jinja kaynağı: parent.py:267-282 + student_detail.html (213 satır).
 * KVKK guard: bağ yoksa backend 404 döner → Next.js notFound().
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğrenci Detayı — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ParentStudentDetailPage({ params }: PageProps) {
  const { id } = await params;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();

  let data: ParentStudentOverviewResponse;
  try {
    data = await apiServer<ParentStudentOverviewResponse>(
      `/api/v2/parent/students/${sid}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <ParentStudentDetailClient initial={data} studentId={sid} />;
}
