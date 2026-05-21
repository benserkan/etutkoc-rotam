import { apiServer } from "@/lib/api-server";
import type {
  AcademicYearChoicesResponse,
  AcademicYearListResponse,
} from "@/lib/types/academic";
import { AcademicYearsListClient } from "@/components/teacher/academic-years-list-client";

/**
 * /teacher/academic-years — akademik yıl listesi + hızlı yıl ekleme (Paket 10).
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Akademik yıllar",
};

export default async function AcademicYearsPage() {
  const [list, choices] = await Promise.all([
    apiServer<AcademicYearListResponse>("/api/v2/teacher/academic/years"),
    apiServer<AcademicYearChoicesResponse>(
      "/api/v2/teacher/academic/years/choices",
    ),
  ]);
  return <AcademicYearsListClient initialList={list} initialChoices={choices} />;
}
