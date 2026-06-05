import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CoachReviewView } from "@/components/teacher/coach-dev-views";
import type { TeacherReviewResponse } from "@/lib/teacher";

const D: TeacherReviewResponse = {
  student_name: "Yiğit", breakdown: { new: 5, learning: 8, review: 22, relearning: 3, due_now: 6, total: 38 },
  struggle_cards: [
    { topic_id: 1, topic_name: "Üslü Sayılar", subject_name: "Matematik", state_label: "Yeniden", lapse_count: 3 },
    { topic_id: 2, topic_name: "Basınç", subject_name: "Fen", state_label: "Öğreniliyor", lapse_count: 2 },
    { topic_id: 3, topic_name: "Cümlede Anlam", subject_name: "Türkçe", state_label: "Yeniden", lapse_count: 4 },
  ],
  subjects: [{ id: 1, name: "Matematik" }, { id: 2, name: "Fen" }, { id: 3, name: "Türkçe" }],
};
export default function P() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView contentContainerClassName="px-4 py-4"><View><CoachReviewView d={D} busy={false} onSeed={() => {}} /></View></ScrollView>
    </SafeAreaView>
  );
}
