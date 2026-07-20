import { apiServer } from "@/lib/api-server";
import type { InstitutionSelfStudyReportResponse } from "@/lib/types/institution";
import { InstitutionSelfStudyClient } from "@/components/institution/self-study-client";

/**
 * /institution/self-study — Bağımsız Çalışma Girişleri raporu (Faz 2).
 *
 * Koçların elle/bağımsız ilerleme girişleri: kim, ne kadar, öğrenci beyanıyla
 * mı / koç tek taraflı mı + "beyansız yüklü giriş" dikkat işareti. Kurum uyum/
 * karne metrikleri görev-bazlıdır — bu girişlerden etkilenmez.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bağımsız Çalışma" };

export default async function InstitutionSelfStudyPage() {
  const data = await apiServer<InstitutionSelfStudyReportResponse>(
    "/api/v2/institution/self-study-report?days=30",
  );
  return <InstitutionSelfStudyClient initial={data} />;
}
