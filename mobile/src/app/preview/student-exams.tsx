import { ExamsView } from "@/components/student/exams-view";
import type { ExamRow, StudentExamsResponse } from "@/lib/student";

/** UX önizleme — Denemeler (mock). Faz 7'de kaldırılacak. */
function exam(id: number, title: string, date: string, section: string, label: string, c: number, w: number, b: number, net: number): ExamRow {
  return {
    id, title, exam_date: date, section, section_label: label,
    total_correct: c, total_wrong: w, total_blank: b, total_questions: c + w + b,
    net, subjects: [], note: null, created_at: date + "T10:00:00Z", created_by_name: null,
  };
}

// DESC (en yeni ilk)
const ROWS: ExamRow[] = [
  exam(5, "Hız ve Renk LGS 4", "2026-05-28", "lgs", "LGS", 78, 6, 6, 76),
  exam(4, "Hız ve Renk LGS 3", "2026-05-21", "lgs", "LGS", 72, 9, 9, 69),
  exam(3, "TYT Genel Deneme 1", "2026-05-18", "tyt", "TYT", 88, 16, 16, 84),
  exam(2, "Hız ve Renk LGS 2", "2026-05-14", "lgs", "LGS", 64, 12, 14, 60),
  exam(1, "Hız ve Renk LGS 1", "2026-05-07", "lgs", "LGS", 58, 15, 17, 53),
];

const MOCK: StudentExamsResponse = {
  summary: { count: 5, avg_net: 68.4, best_net: 84, last_net: 76, first_net: 53, trend_delta: 23 },
  rows: ROWS,
};

export default function StudentExamsPreview() {
  return <ExamsView data={MOCK} />;
}
