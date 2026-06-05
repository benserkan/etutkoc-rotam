import { SafeAreaView } from "react-native-safe-area-context";
import { GoalsView } from "@/components/student/goals-view";
import type { GoalListResponse } from "@/lib/student";

const DATA: GoalListResponse = {
  items: [
    { id: 1, kind: "weekly", status: "active", title: "Bu hafta 200 test çöz", description: null, target_value: 200, current_value: 140, unit: "test", target_date: "2026-06-08", is_auto_generated: true, progress_pct: 70 },
    { id: 2, kind: "topic", status: "active", title: "Üslü sayıları bitir", description: null, target_value: null, current_value: null, unit: null, target_date: null, is_auto_generated: false, progress_pct: 45 },
    { id: 3, kind: "custom", status: "achieved", title: "Deneme netini 80'e çıkar", description: null, target_value: 80, current_value: 82, unit: "net", target_date: null, is_auto_generated: false, progress_pct: 100 },
  ],
  summary: { total: 5, active: 2, achieved: 3, abandoned: 0, overall_pct: 71, next_target_date: "2026-06-08" },
};
export default function GoalsPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <GoalsView data={DATA} busy={false} onCreate={() => {}} onProgress={() => {}} onAchieve={() => {}} />
    </SafeAreaView>
  );
}
