import { apiServer } from "@/lib/api-server";
import type { TeacherPlanResponse } from "@/lib/types/teacher";
import { TeacherPlanClient } from "@/components/teacher/teacher-plan-client";

/**
 * /teacher/plan — bağımsız koç paket görüntüleme + yükseltme.
 *
 * AI özellikleri (foto/ses yakalama, koçluk içgörüsü) yalnız ücretli pakette açık.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Paket" };

export default async function TeacherPlanPage() {
  const data = await apiServer<TeacherPlanResponse>("/api/v2/teacher/plan");
  return <TeacherPlanClient initial={data} />;
}
