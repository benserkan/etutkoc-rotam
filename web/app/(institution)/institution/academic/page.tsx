import { apiServer } from "@/lib/api-server";
import type { InstitutionAcademicResponse } from "@/lib/types/institution";
import { AcademicClient } from "@/components/institution/academic-client";

/**
 * /institution/academic — Kurum Akademik Çıktı Panosu (KP4b).
 *
 * KP4a'da öğretmenlerin girdiği deneme sonuçlarının kurum agregasyonu:
 * kapsama + net başarı oranı (normalize) + sınav türü kırılımı + trend +
 * öğretmen kırılımı + en çok gelişen/gerileyen + deneme girmeyen.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Akademik Çıktı" };

export default async function InstitutionAcademicPage() {
  const data = await apiServer<InstitutionAcademicResponse>(
    "/api/v2/institution/academic?weeks=8",
  );
  return <AcademicClient initial={data} />;
}
