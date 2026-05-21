import { apiServer } from "@/lib/api-server";
import type { CohortsResponse } from "@/lib/types/institution";
import { CohortsPrintSheet } from "@/components/institution/cohorts-print-sheet";

/**
 * /institution/cohorts/print — A4 landscape, 4 sekme bir arada.
 *
 * Jinja kaynağı: app/templates/institution/cohorts_print.html (2x2 grid)
 */
export const metadata = { title: "Kohort Raporu — Yazdır" };
export const dynamic = "force-dynamic";

export default async function InstitutionCohortsPrintPage() {
  // 4 sekmeyi paralel çek
  const [grade, track, curriculum, exam] = await Promise.all([
    apiServer<CohortsResponse>("/api/v2/institution/cohorts?tab=grade"),
    apiServer<CohortsResponse>("/api/v2/institution/cohorts?tab=track"),
    apiServer<CohortsResponse>("/api/v2/institution/cohorts?tab=curriculum"),
    apiServer<CohortsResponse>(
      "/api/v2/institution/cohorts?tab=exam_target",
    ),
  ]);
  return (
    <CohortsPrintSheet
      institution={grade.institution}
      wow={grade.wow}
      sections={[
        { label: "Sınıf seviyesi", cohorts: grade.cohorts },
        { label: "Alan (11+/Mezun)", cohorts: track.cohorts },
        { label: "Müfredat modeli", cohorts: curriculum.cohorts },
        { label: "Hedef sınav", cohorts: exam.cohorts },
      ]}
    />
  );
}
