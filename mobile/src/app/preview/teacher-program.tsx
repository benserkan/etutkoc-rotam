import { SafeAreaView } from "react-native-safe-area-context";

import { TeacherWeekView } from "@/components/teacher/week-view";
import type { TeacherWeekResponse, TeacherWeekDay } from "@/lib/teacher";

function day(date: string, dow: string, tasks: TeacherWeekDay["tasks"], today = false): TeacherWeekDay {
  const planned = tasks.reduce((a, t) => a + t.planned_count, 0);
  const completed = tasks.reduce((a, t) => a + t.completed_count, 0);
  return {
    date, dow_label: dow, is_today: today, is_future: false, is_past: false,
    tasks_count: tasks.length, planned, completed, pct: planned > 0 ? completed / planned : 0,
    test_planned: planned, test_completed: completed, deneme_count: 0, etkinlik_count: 0, tasks, draft_count: 0,
  };
}
function task(id: number, book: string, section: string, p: number, c: number): TeacherWeekDay["tasks"][number] {
  return {
    id, date: "", type: "test", status: c >= p ? "completed" : "pending", title: `${book} · ${section}`,
    period: null, is_draft: false,
    items: [{ id, book_id: 1, book_name: book, book_type: "soru_bankasi", subject_name: null, section_label: section, planned_count: p, completed_count: c }],
    planned_count: p, completed_count: c, pct: p > 0 ? c / p : 0, solved_count: null,
  };
}
const MOCK: TeacherWeekResponse = {
  student_id: 1, start_date: "2026-06-01", end_date: "2026-06-07",
  prev_start: "2026-05-25", next_start: "2026-06-08",
  total_planned: 120, total_completed: 78, total_pct: 0.65,
  days: [
    day("2026-06-01", "Pazartesi", [task(1, "Matematik SB", "Üslü Sayılar", 20, 20), task(2, "Fen SB", "Hücre", 15, 10)], true),
    day("2026-06-02", "Salı", [task(3, "Türkçe SB", "Paragraf", 25, 18)]),
    day("2026-06-03", "Çarşamba", []),
    day("2026-06-04", "Perşembe", [task(4, "Matematik SB", "Köklü Sayılar", 20, 5)]),
    day("2026-06-05", "Cuma", [task(5, "Fen SB", "Basınç", 15, 0)]),
    day("2026-06-06", "Cumartesi", []),
    day("2026-06-07", "Pazar", []),
  ],
};

export default function TeacherProgramPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <TeacherWeekView
        week={MOCK}
        onPrev={() => {}} onNext={() => {}} onThisWeek={() => {}}
        onAddTask={() => {}} onDeleteTask={() => {}}
      />
    </SafeAreaView>
  );
}
