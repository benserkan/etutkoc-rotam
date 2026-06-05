import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DevHubView } from "@/components/student/dev-hub-view";
import type { DnaResponse, FocusResponse, GoalListResponse, ReviewResponse } from "@/lib/student";

const DNA: DnaResponse = {
  window_days: 30, has_enough_data: true, gorev_total: 120, gorev_done: 92, test_planned: 400,
  test_completed: 318, completion_rate: 0.77, chronotype: "evening", peak_hour: 20, peak_day_idx: 2,
  peak_day_name: "Çarşamba", heatmap: [], morning_count: 12, afternoon_count: 24, evening_count: 38,
  night_count: 9, weekend_count: 21, weekday_count: 62,
};
const FOCUS: FocusResponse = {
  active_session: null,
  today: { work_sessions: 3, work_minutes: 75, break_minutes: 15, total_minutes: 90, interrupted_count: 0 },
  recent_sessions: [], streak_days: 6, points: 1240,
};
const REVIEW: ReviewResponse = {
  due_cards: [
    { id: 1, topic_id: 1, topic_name: "Üslü Sayılar", subject_name: "Matematik", state: "review", review_count: 4 },
    { id: 2, topic_id: 2, topic_name: "Hücre", subject_name: "Fen", state: "learning", review_count: 2 },
    { id: 3, topic_id: 3, topic_name: "Paragraf", subject_name: "Türkçe", state: "review", review_count: 6 },
  ],
  breakdown: { new: 5, learning: 8, review: 22, relearning: 2, due_now: 3, total: 37 },
};
const GOALS: GoalListResponse = {
  items: [
    { id: 1, kind: "exam_target", status: "active", title: "LGS'de 450+ puan", description: null, target_value: 450, current_value: 412, unit: "puan", target_date: "2026-06-15", is_auto_generated: false, progress_pct: 78 },
    { id: 2, kind: "weekly", status: "active", title: "Bu hafta 200 test", description: null, target_value: 200, current_value: 140, unit: "test", target_date: null, is_auto_generated: true, progress_pct: 70 },
    { id: 3, kind: "subject", status: "active", title: "Matematik konularını bitir", description: null, target_value: null, current_value: null, unit: null, target_date: null, is_auto_generated: false, progress_pct: 55 },
  ],
  summary: { total: 5, active: 3, achieved: 2, abandoned: 0, overall_pct: 68, next_target_date: "2026-06-15" },
};

export default function StudentGelisimPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-1">
        <DevHubView dna={DNA} focus={FOCUS} review={REVIEW} goals={GOALS} onOpenBooks={() => {}} onOpenFocus={() => {}} onOpenReview={() => {}} onOpenGoals={() => {}} />
      </View>
    </SafeAreaView>
  );
}
