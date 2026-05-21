import { apiServer } from "@/lib/api-server";
import type { TeacherScorecardResponse } from "@/lib/types/institution";
import { TeacherScorecardClient } from "@/components/institution/teacher-scorecard-client";

/**
 * /institution/teacher-scorecard — Öğretmen Etkililik Karnesi.
 *
 * "Kim sonuç alıyor?" — tamamlama + doğruluk + program disiplini + risk birleşik
 * etkililik skoru. burnout (kim yoruldu) tamamlayıcısı.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmen Karnesi" };

export default async function InstitutionTeacherScorecardPage() {
  const data = await apiServer<TeacherScorecardResponse>(
    "/api/v2/institution/teacher-scorecard?weeks=4",
  );
  return <TeacherScorecardClient initial={data} />;
}
