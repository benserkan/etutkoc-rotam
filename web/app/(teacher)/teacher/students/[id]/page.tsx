import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TeacherStudentDetailResponse } from "@/lib/types/teacher";
import { StudentTabs } from "@/components/teacher/student-tabs";

/**
 * /teacher/students/[id] — server initial fetch + client sekmeli görünüm.
 *
 * Sekme kontrolü hash-bazlı (`#summary`, `#books`, `#parents`) — sayfa
 * yenilenmez. Detay verisi 30s stale + window focus refetch.
 */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Öğrenci #${id}` };
}

export default async function TeacherStudentDetailPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) {
    notFound();
  }
  let data: TeacherStudentDetailResponse;
  try {
    data = await apiServer<TeacherStudentDetailResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(String(numericId))}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      notFound();
    }
    throw e;
  }
  return <StudentTabs studentId={numericId} initial={data} />;
}
