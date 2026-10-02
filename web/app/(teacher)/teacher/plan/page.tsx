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

export default async function TeacherPlanPage({
  searchParams,
}: {
  searchParams: Promise<{ plan?: string; checkout?: string }>;
}) {
  const data = await apiServer<TeacherPlanResponse>("/api/v2/teacher/plan");
  // Bağlamsal yükseltme anından gelen ön-seçim (?plan=solo_elite). ?checkout=1
  // → ödeme penceresi doğrudan açık gelir (banner "X paketine geç" tek tık).
  const { plan, checkout } = await searchParams;
  return (
    <TeacherPlanClient
      initial={data}
      initialPlan={plan ?? null}
      autoCheckout={checkout === "1"}
    />
  );
}
