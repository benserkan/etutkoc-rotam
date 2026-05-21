import { notFound } from "next/navigation";

import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import type { AcademicYearDetailResponse } from "@/lib/types/academic";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import { AcademicYearDetailClient } from "@/components/teacher/academic-year-detail-client";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Akademik yıl #${id}` };
}

export default async function AcademicYearDetailPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  let year: AcademicYearDetailResponse;
  try {
    year = await apiServer<AcademicYearDetailResponse>(
      `/api/v2/teacher/academic/years/${encodeURIComponent(String(numericId))}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  const students = await apiServer<TeacherStudentListResponse>(
    "/api/v2/teacher/students",
  );
  return (
    <AcademicYearDetailClient
      yearId={numericId}
      initial={year}
      allStudents={students.items}
    />
  );
}
