import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ExamsTabView } from "@/components/teacher/exams-tab";
import type { TeacherExamsResponse } from "@/lib/teacher";

/** UX önizleme — Koç: öğrenci denemeleri (mock). Faz 7'de kaldırılacak. */
const MOCK: TeacherExamsResponse = {
  summary: { count: 4, avg_net: 78, best_net: 92, last_net: 85, first_net: 64, trend_delta: 21 },
  section_options: [
    { value: "lgs", label: "LGS" },
    { value: "tyt", label: "TYT" },
    { value: "ayt_say", label: "AYT Sayısal" },
    { value: "ayt_ea", label: "AYT EA" },
  ],
  rows: [
    {
      id: 4, title: "TYT Genel Deneme 7", exam_date: "2026-06-01", section: "tyt", section_label: "TYT",
      total_correct: 96, total_wrong: 18, total_blank: 6, total_questions: 120, net: 85,
      subjects: [], note: null, created_at: "2026-06-01", created_by_name: "Koç",
    },
    {
      id: 3, title: "TYT Genel Deneme 6", exam_date: "2026-05-25", section: "tyt", section_label: "TYT",
      total_correct: 100, total_wrong: 12, total_blank: 8, total_questions: 120, net: 92,
      subjects: [], note: null, created_at: "2026-05-25", created_by_name: "Koç",
    },
    {
      id: 2, title: "TYT Genel Deneme 5", exam_date: "2026-05-18", section: "tyt", section_label: "TYT",
      total_correct: 84, total_wrong: 24, total_blank: 12, total_questions: 120, net: 72,
      subjects: [], note: null, created_at: "2026-05-18", created_by_name: "Koç",
    },
  ],
};

export default function TeacherExamsPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView className="flex-1">
        <View className="flex-1">
          <ExamsTabView data={MOCK} addBusy={false} addError={null} onAdd={() => {}} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
