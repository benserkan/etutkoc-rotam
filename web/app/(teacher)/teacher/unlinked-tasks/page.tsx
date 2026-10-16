import { UnlinkedTasksClient } from "@/components/teacher/unlinked-tasks-client";

/**
 * /teacher/unlinked-tasks — Konusuz test görevleri (2026-10-16).
 *
 * "Diğer" etkinliği olarak, test sayısı serbest metne yazılarak verilmiş
 * görevler hiçbir tabloya giremiyordu. Koç burada önerilen konuyu onaylayıp
 * görevleri konuya bağlı teste çevirir; tablolar geriye dönük dolar.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Konusuz test görevleri" };

export default function UnlinkedTasksPage() {
  return <UnlinkedTasksClient />;
}
