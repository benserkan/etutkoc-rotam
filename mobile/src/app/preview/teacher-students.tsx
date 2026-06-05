import { StudentsListView } from "@/components/teacher/students-list-view";
import type { TeacherStudentListItem } from "@/lib/teacher";

/** UX önizleme — Koç: Öğrencilerim (mock). Faz 7'de kaldırılacak. */
function s(over: Partial<TeacherStudentListItem>): TeacherStudentListItem {
  return {
    id: 1, full_name: "—", email: "ornek@e.com", grade_level: 8, is_active: true,
    last_login_at: null, worst_warning_level: "green", worst_warning_title: null,
    worst_warning_detail: null, today_gorev_total: 0, today_gorev_done: 0,
    week_pct: 0, has_pending_request: false, ...over,
  };
}

const ITEMS: TeacherStudentListItem[] = [
  s({ id: 1, full_name: "Yiğit Demir", grade_level: 8, worst_warning_level: "red",
      worst_warning_title: "3 gündür giriş yok", today_gorev_total: 6, today_gorev_done: 0,
      week_pct: 0.18, has_pending_request: true }),
  s({ id: 2, full_name: "Elif Yıldız", grade_level: 8, worst_warning_level: "amber",
      worst_warning_title: "Haftalık tempo düşük", today_gorev_total: 5, today_gorev_done: 2, week_pct: 0.55 }),
  s({ id: 3, full_name: "Ada Kaya", grade_level: 12, worst_warning_level: "green",
      today_gorev_total: 4, today_gorev_done: 4, week_pct: 0.92 }),
  s({ id: 4, full_name: "Mert Şahin", grade_level: 7, worst_warning_level: "green",
      is_active: false, today_gorev_total: 0, today_gorev_done: 0, week_pct: 0 }),
];

export default function TeacherStudentsPreview() {
  return <StudentsListView items={ITEMS} onOpenStudent={() => {}} />;
}
