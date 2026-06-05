import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildWeekView } from "@/components/parent/child-week-view";
import type { ParentWeekDay, ParentWeekResponse } from "@/lib/parent";

/** UX önizleme — Veli: çocuk haftası (mock). Faz 7'de kaldırılacak. */
function day(
  weekday: number,
  date: string,
  done: number,
  total: number,
  testC: number,
  testP: number,
  subjects: string[],
): ParentWeekDay {
  return {
    date, weekday, task_count: total, planned_total: testP, completed_total: testC,
    gorev_total: total, gorev_done: done, test_planned: testP, test_completed: testC,
    deneme_count: 0, etkinlik_count: 0,
    tasks: subjects.map((s, i) => ({
      id: i + 1, title: "", type: "test", status: "pending",
      book_items: [{ book_name: "Kitap", subject_name: s, subject_id: i, section_label: null, topic_name: null, planned_count: 1, completed_count: 0 }],
    })),
  };
}

const MOCK: ParentWeekResponse = {
  student: { id: 1, full_name: "Elif Yıldız" },
  start: "2026-06-01", end: "2026-06-07", prev_start: "2026-05-25", next_start: "2026-06-08",
  days: [
    day(0, "2026-06-01", 5, 5, 22, 22, ["Matematik", "Fen Bilimleri", "Türkçe"]),
    day(1, "2026-06-02", 3, 4, 12, 18, ["Matematik", "T.C. İnkılap"]),
    day(2, "2026-06-03", 1, 6, 4, 24, ["Fen Bilimleri", "Din Kültürü", "Matematik"]),
    day(3, "2026-06-04", 0, 3, 0, 12, ["Türkçe", "Matematik"]),
    day(4, "2026-06-05", 0, 4, 0, 16, ["Fen Bilimleri"]),
    day(5, "2026-06-06", 0, 2, 0, 0, ["Matematik"]),
    day(6, "2026-06-07", 0, 0, 0, 0, []),
  ],
};

export default function ParentChildWeekPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ParentChildWeekView week={MOCK} onPrev={() => {}} onNext={() => {}} onThisWeek={() => {}} />
    </SafeAreaView>
  );
}
