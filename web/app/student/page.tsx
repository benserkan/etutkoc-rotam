import { redirect } from "next/navigation";

/**
 * /student — öğrenci ana sayfası.
 *
 * Jinja parite (app/routes/student.py:135 `student_home`): /student →
 * /student/day (303). Öğrencinin varsayılan görünümü bugünün planı.
 * Auth kontrolü `app/student/layout.tsx` içinde yapılır.
 */
export default function StudentHomePage() {
  redirect("/student/day");
}
