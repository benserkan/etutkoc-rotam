import { apiServer } from "@/lib/api-server";
import type {
  AcademicYearListResponse,
  GradeAdvancePreviewResponse,
} from "@/lib/types/academic";
import { GradeAdvanceClient } from "@/components/teacher/grade-advance-client";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Sınıf yükseltme",
};

export default async function GradeAdvancePage() {
  const [preview, years] = await Promise.all([
    apiServer<GradeAdvancePreviewResponse>(
      "/api/v2/teacher/grade-advance/preview",
    ),
    apiServer<AcademicYearListResponse>("/api/v2/teacher/academic/years"),
  ]);
  return <GradeAdvanceClient initialPreview={preview} years={years.items} />;
}
