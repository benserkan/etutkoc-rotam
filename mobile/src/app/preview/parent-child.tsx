import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildDetailView } from "@/components/parent/child-detail-view";
import type { ParentStudentOverview } from "@/lib/parent-detail";

/** UX önizleme — Veli: çocuk detayı (mock). Faz 7'de kaldırılacak. */
const MOCK: ParentStudentOverview = {
  student: {
    id: 1, full_name: "Elif Yıldız", grade_level: 8, is_graduate: false,
    display_grade_label: "8. sınıf", academic_year: "2025-2026",
    exam_date: "2027-06-01", exam_label: "LGS", exam_target: "lgs",
  },
  today: { planned: 22, completed: 16, gorev_total: 5, gorev_done: 4 },
  week: { planned: 120, completed: 96, rate: 80, gorev_total: 28, gorev_done: 24, gorev_rate: 88, test_planned: 92, test_completed: 78 },
  rate_7d_pct: 82,
  rate_30d_pct: 75,
  consistency_7d_pct: 90,
  warning_level: "green",
  projection: {
    total_tests: 1200, completed_tests: 540, remaining_tests: 660,
    rate_per_day: 14, days_left_to_exam: 60, expected_completed_by_exam: 1380, gap: 180, status: "green",
  },
  subjects: [
    { subject_id: 1, name: "Matematik", percent_done: 72 },
    { subject_id: 2, name: "Fen Bilimleri", percent_done: 58 },
    { subject_id: 3, name: "Türkçe", percent_done: 81 },
    { subject_id: 4, name: "T.C. İnkılap", percent_done: 35 },
  ],
  teacher_notes: [
    { id: 1, body: "Bu hafta matematikte çok iyi ilerledi, tebrik ederim. İnkılap'a biraz daha ağırlık vermeliyiz.", teacher_name: "Serkan Hoca", created_at: "2026-06-03", delivered_at: null },
  ],
};

export default function ParentChildPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-1">
        <ParentChildDetailView data={MOCK} onOpenWeek={() => {}} />
      </View>
    </SafeAreaView>
  );
}
