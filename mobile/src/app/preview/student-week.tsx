import { WeekView } from "@/components/student/week-view";
import type { StudentTask, StudentWeekDay, StudentWeekResponse } from "@/lib/student";

/** UX önizleme — Hafta görünümü (mock). Faz 7'de kaldırılacak. */
function task(id: number, subject: string): StudentTask {
  return {
    id,
    title: "",
    type: "test",
    status: "pending",
    date: "2026-06-05",
    period: null,
    planned_count: 1,
    completed_count: 0,
    pct: 0,
    is_future_blocked: false,
    is_past: false,
    has_pending_request: false,
    items: [
      {
        id,
        book_id: 1,
        book_name: "Kitap",
        book_type: "soru_bankasi",
        subject_id: id,
        subject_name: subject,
        section_id: 1,
        section_label: null,
        topic_name: null,
        planned: 1,
        completed: 0,
        is_full: false,
        correct: null,
        wrong: null,
      },
    ],
  };
}

function day(
  dow: string,
  date: string,
  done: number,
  total: number,
  testC: number,
  testP: number,
  subjects: string[],
  isToday = false,
): StudentWeekDay {
  return {
    date,
    dow_label: dow,
    is_today: isToday,
    is_future: false,
    is_past: false,
    gorev_total: total,
    gorev_done: done,
    test_planned: testP,
    test_completed: testC,
    deneme_count: 0,
    etkinlik_count: 0,
    tasks: subjects.map((s, i) => task(i + 1, s)),
  };
}

const MOCK_WEEK: StudentWeekResponse = {
  start_date: "2026-06-01",
  end_date: "2026-06-07",
  prev_start: "2026-05-25",
  next_start: "2026-06-08",
  total_gorev: 24,
  total_gorev_done: 9,
  total_test_planned: 92,
  total_test_completed: 38,
  total_pct: 0.375,
  days: [
    day("Pazartesi", "2026-06-01", 5, 5, 22, 22, ["Matematik", "Fen Bilimleri", "Türkçe"]),
    day("Salı", "2026-06-02", 3, 4, 12, 18, ["Matematik", "T.C. İnkılap"]),
    day("Çarşamba", "2026-06-03", 1, 6, 4, 24, ["Fen Bilimleri", "Din Kültürü", "Matematik", "Türkçe", "İngilizce"], true),
    day("Perşembe", "2026-06-04", 0, 3, 0, 12, ["Türkçe", "Matematik"]),
    day("Cuma", "2026-06-05", 0, 4, 0, 16, ["Fen Bilimleri"]),
    day("Cumartesi", "2026-06-06", 0, 2, 0, 0, ["Matematik"]),
    day("Pazar", "2026-06-07", 0, 0, 0, 0, []),
  ],
};

export default function StudentWeekPreview() {
  return (
    <WeekView
      week={MOCK_WEEK}
      onPrev={() => {}}
      onNext={() => {}}
      onThisWeek={() => {}}
      onOpenDay={() => {}}
    />
  );
}
