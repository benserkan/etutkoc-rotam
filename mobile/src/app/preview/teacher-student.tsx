import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { StudentDetailView } from "@/components/teacher/student-detail-view";
import type { GorevBreakdown, TeacherStudentDetail } from "@/lib/teacher";

/** UX önizleme — Koç: öğrenci detayı (mock). Faz 7'de kaldırılacak. */
function g(over: Partial<GorevBreakdown>): GorevBreakdown {
  return {
    gorev_total: 0, gorev_done: 0, gorev_pct: 0, test_planned: 0, test_completed: 0,
    deneme_planned: 0, deneme_completed: 0, deneme_count: 0, deneme_done: 0,
    etkinlik_count: 0, etkinlik_done: 0, ...over,
  };
}

const MOCK: TeacherStudentDetail = {
  student: {
    id: 1, full_name: "Yiğit Demir", email: "yigit@e.com", grade_level: 8,
    is_active: true, display_grade_label: "8. sınıf", track_label: null, last_login_at: null,
  },
  worst_warning_level: "red",
  warning_items: [
    { level: "red", code: "no_login_5d", title: "3 gündür giriş yapmadı", detail: "Son giriş 3 gün önce. İletişime geç.", link: "", link_label: "" },
    { level: "amber", code: "low_completion", title: "Haftalık tempo düşük", detail: "Bu hafta görevlerin %18'i tamam.", link: "", link_label: "" },
  ],
  pending_request_count: 1,
  has_active_program: true,
  gorev_today: g({ gorev_total: 6, gorev_done: 0, gorev_pct: 0, test_planned: 24, test_completed: 0 }),
  gorev_week: g({ gorev_total: 28, gorev_done: 5, gorev_pct: 18, test_planned: 92, test_completed: 16, deneme_count: 2, deneme_done: 0 }),
};

export default function TeacherStudentPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-1">
        <StudentDetailView data={MOCK} />
      </View>
    </SafeAreaView>
  );
}
