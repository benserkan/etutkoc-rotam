import { SafeAreaView } from "react-native-safe-area-context";

import { ParentChildReportView } from "@/components/parent/child-report-view";
import type { WeeklyReportResponse } from "@/lib/parent";

/** UX önizleme — Veli: haftalık rapor (mock). Faz 7'de kaldırılacak. */
const MOCK: WeeklyReportResponse = {
  student: { id: 1, full_name: "Yiğit Demir" },
  start: "2026-05-25",
  end: "2026-05-31",
  prev_start: "2026-05-18",
  next_start: "2026-06-01",
  gorev_done: 18,
  gorev_total: 24,
  completion_pct: 75,
  test_completed: 142,
  test_planned: 190,
  active_days: 6,
  daily: [
    { date: "2026-05-25", weekday: 0, gorev_done: 5, gorev_total: 6, pct: 83, test_completed: 40, test_planned: 48 },
    { date: "2026-05-26", weekday: 1, gorev_done: 4, gorev_total: 4, pct: 100, test_completed: 32, test_planned: 32 },
    { date: "2026-05-27", weekday: 2, gorev_done: 3, gorev_total: 5, pct: 60, test_completed: 24, test_planned: 40 },
    { date: "2026-05-28", weekday: 3, gorev_done: 6, gorev_total: 6, pct: 100, test_completed: 48, test_planned: 48 },
    { date: "2026-05-29", weekday: 4, gorev_done: 0, gorev_total: 3, pct: 0, test_completed: 0, test_planned: 24 },
    { date: "2026-05-30", weekday: 5, gorev_done: 0, gorev_total: 0, pct: 0, test_completed: 0, test_planned: 0 },
    { date: "2026-05-31", weekday: 6, gorev_done: 0, gorev_total: 0, pct: 0, test_completed: 0, test_planned: 0 },
  ],
  subjects: [
    { subject_name: "Matematik", planned: 60, completed: 58, pct: 97 },
    { subject_name: "Fen Bilimleri", planned: 50, completed: 40, pct: 80 },
    { subject_name: "Türkçe", planned: 40, completed: 12, pct: 30 },
  ],
  most_completed_subject: "Matematik",
  most_neglected_subject: "Türkçe",
  most_neglected_pct: 30,
  comparison: {
    this_completion_pct: 75,
    last_completion_pct: 62,
    completion_delta: 13,
    this_test_completed: 142,
    last_test_completed: 118,
    test_delta: 24,
    this_gorev_done: 18,
    last_gorev_done: 15,
    direction: "up",
  },
  exams: [
    { title: "Hız ve Renk TYT Deneme 7", exam_date: "2026-05-30", section_label: "TYT", net: 78.5, total_correct: 84, total_wrong: 22, total_blank: 14 },
    { title: "Hız ve Renk TYT Deneme 6", exam_date: "2026-05-16", section_label: "TYT", net: 71.25, total_correct: 78, total_wrong: 27, total_blank: 15 },
  ],
  exam_trend_delta: 7.25,
  exam_trend_section: "TYT",
  teacher_notes: [
    { body: "Bu hafta matematikte ciddi ilerleme var. Türkçe paragraf sorularına ağırlık vereceğiz.", teacher_name: "Serkan Hoca", created_at: "2026-05-29" },
  ],
  verdict_level: "good",
  verdict_text: "Harika bir hafta! Geçen haftaya göre belirgin bir yükseliş var.",
};

export default function ParentReportPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ParentChildReportView report={MOCK} />
    </SafeAreaView>
  );
}
