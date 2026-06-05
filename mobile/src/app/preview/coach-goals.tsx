import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CoachGoalsView } from "@/components/teacher/coach-dev-views";
import type { TeacherGoalsResponse } from "@/lib/teacher";

const D: TeacherGoalsResponse = {
  student_name: "Yiğit", overall_pct: 64,
  summary: { total: 6, active: 4, achieved: 2, overall_pct: 64 },
  roots: [
    { id: 1, kind: "exam_target", kind_label: "Sınav", status: "active", title: "LGS 450+ puan", target_value: 450, current_value: 412, unit: "puan", progress_pct: 78, aggregated_pct: 78, children: [] },
    { id: 2, kind: "subject", kind_label: "Ders", status: "active", title: "Matematik", target_value: null, current_value: null, unit: null, progress_pct: null, aggregated_pct: 55, children: [
      { id: 3, kind: "topic", kind_label: "Konu", status: "achieved", title: "Üslü Sayılar", target_value: null, current_value: null, unit: null, progress_pct: 100, aggregated_pct: 100, children: [] },
      { id: 4, kind: "topic", kind_label: "Konu", status: "active", title: "Köklü Sayılar", target_value: null, current_value: null, unit: null, progress_pct: 40, aggregated_pct: 40, children: [] },
    ] },
  ],
};
export default function P() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView contentContainerClassName="px-4 py-4"><View><CoachGoalsView d={D} busy={false} onCreate={() => {}} /></View></ScrollView>
    </SafeAreaView>
  );
}
