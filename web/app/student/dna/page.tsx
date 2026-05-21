import { apiServer } from "@/lib/api-server";
import type { DnaResponse } from "@/lib/types/student";
import { DnaView } from "@/components/student/dna-view";

export const metadata = { title: "Çalışma DNA" };
export const dynamic = "force-dynamic";

export default async function StudentDnaPage() {
  const data = await apiServer<DnaResponse>("/api/v2/student/dna");
  return <DnaView data={data} />;
}
