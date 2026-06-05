import { SafeAreaView } from "react-native-safe-area-context";
import { FocusView } from "@/components/student/focus-view";
import type { FocusResponse } from "@/lib/student";

const DATA: FocusResponse = {
  active_session: { id: 1, kind: "work", planned_minutes: 25, actual_minutes: 0, interrupted: false, label: "Matematik — Üslü Sayılar", is_active: true, elapsed_seconds: 390 },
  today: { work_sessions: 3, work_minutes: 75, break_minutes: 15, total_minutes: 90, interrupted_count: 0 },
  recent_sessions: [], streak_days: 6, points: 1240,
};
export default function FocusPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <FocusView data={DATA} remainingSec={1110} runningLabel="Matematik — Üslü Sayılar" busy={false} onStart={() => {}} onFinish={() => {}} onCancel={() => {}} />
    </SafeAreaView>
  );
}
