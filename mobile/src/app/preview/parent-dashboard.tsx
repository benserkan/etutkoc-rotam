import { ParentDashboardView } from "@/components/parent/dashboard-view";
import type { ParentChildSummary, WarningLevel } from "@/lib/parent";

/** UX önizleme — Veli: Çocuklarım (mock). Faz 7'de kaldırılacak. */
function child(over: Partial<ParentChildSummary>): ParentChildSummary {
  return {
    student_id: 1, full_name: "—", grade_level: 8, is_graduate: false,
    display_grade_label: "8. sınıf", academic_year: null, exam_label: "LGS",
    exam_target: "lgs", relation: "anne", is_primary: true,
    today_gorev_total: 0, today_gorev_done: 0, week_gorev_total: 0, week_gorev_done: 0,
    week_gorev_rate: null, week_test_planned: 0, week_test_completed: 0,
    rate_7d: null, consistency_7d: null, warning_level: "green",
    latest_exam_title: null, latest_exam_date: null, latest_exam_net: null,
    latest_exam_section: null, latest_exam_count: 0, ...over,
  };
}

const CHILDREN: ParentChildSummary[] = [
  child({
    student_id: 1, full_name: "Elif Yıldız", warning_level: "green",
    today_gorev_total: 5, today_gorev_done: 4, week_gorev_rate: 88, consistency_7d: 90,
    latest_exam_title: "Hız ve Renk LGS 4", latest_exam_net: 76, latest_exam_section: "lgs", latest_exam_count: 4,
  }),
  child({
    student_id: 2, full_name: "Yiğit Demir", grade_level: 12, display_grade_label: "12. sınıf",
    exam_label: "YKS", exam_target: "yks", relation: "baba", warning_level: "red",
    today_gorev_total: 6, today_gorev_done: 1, week_gorev_rate: 34, consistency_7d: 42,
    latest_exam_title: "TYT Genel Deneme 2", latest_exam_net: 61, latest_exam_section: "tyt", latest_exam_count: 3,
  }),
];

export default function ParentDashboardPreview() {
  return <ParentDashboardView children={CHILDREN} onOpenChild={() => {}} />;
}
