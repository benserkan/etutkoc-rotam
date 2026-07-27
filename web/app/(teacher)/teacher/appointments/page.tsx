import { apiServer } from "@/lib/api-server";
import type { TeacherAppointmentsResponse } from "@/lib/types/appointment";
import type { TeacherStudentListResponse } from "@/lib/types/teacher";
import { AppointmentsClient } from "@/components/teacher/appointments-client";

/**
 * /teacher/appointments — online görüşme takvimi.
 *
 * Koç randevu atar (tek/haftalık), öğrenci isteklerini onaylar, uygunluk
 * saatlerini tanımlar; Google bağlıysa Meet linki otomatik üretilir.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Görüşmeler" };

export default async function TeacherAppointmentsPage() {
  const [data, students] = await Promise.all([
    apiServer<TeacherAppointmentsResponse>("/api/v2/teacher/appointments"),
    // page_size backend'de en fazla 100 (le=100) — 200 istemek 422 + SSR 500
    // yapıyordu (2026-07-27 canlı bulgusu).
    apiServer<TeacherStudentListResponse>(
      "/api/v2/teacher/students?page_size=100",
    ),
  ]);
  return <AppointmentsClient initial={data} students={students.items} />;
}
