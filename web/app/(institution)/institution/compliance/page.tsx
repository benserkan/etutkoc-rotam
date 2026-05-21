import { apiServer } from "@/lib/api-server";
import type { InstitutionComplianceResponse } from "@/lib/types/institution";
import { ComplianceClient } from "@/components/institution/compliance-client";

/**
 * /institution/compliance — Program Uyum Panosu.
 *
 * Öğretmenlerin hazırladığı programlara öğrenci uyumu: kurum geneli + öğretmen/
 * öğrenci kırılımı + haftalık trend + boş program + doğruluk.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Program Uyumu" };

export default async function InstitutionCompliancePage() {
  const data = await apiServer<InstitutionComplianceResponse>(
    "/api/v2/institution/compliance?weeks=8",
  );
  return <ComplianceClient initial={data} />;
}
