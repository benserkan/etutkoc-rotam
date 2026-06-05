import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildReportView } from "@/components/parent/child-report-view";
import type { ParentWeekResponse } from "@/lib/parent";

/** UX önizleme — Veli: haftalık rapor (mock). Faz 7'de kaldırılacak. */
function day(weekday: number, date: string, done: number, total: number, tc = 0, tp = 0): ParentWeekResponse["days"][number] {
  return {
    date, weekday, tasks: [], task_count: total, planned_total: tp, completed_total: tc,
    gorev_total: total, gorev_done: done, test_planned: tp, test_completed: tc, deneme_count: 0, etkinlik_count: 0,
  };
}
const MOCK: ParentWeekResponse = {
  student: { id: 1, full_name: "Yiğit Demir" },
  start: "2026-05-25", end: "2026-05-31", prev_start: "2026-05-18", next_start: "2026-06-01",
  days: [
    day(0, "2026-05-25", 5, 6, 40, 48),
    day(1, "2026-05-26", 4, 4, 32, 32),
    day(2, "2026-05-27", 3, 5, 24, 40),
    day(3, "2026-05-28", 6, 6, 48, 48),
    day(4, "2026-05-29", 2, 5, 16, 40),
    day(5, "2026-05-30", 4, 4, 30, 30),
    day(6, "2026-05-31", 0, 2, 0, 16),
  ],
};

export default function ParentReportPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ParentChildReportView week={MOCK} />
    </SafeAreaView>
  );
}
