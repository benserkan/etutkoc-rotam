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
    apiServer<TeacherStudentListResponse>(
      "/api/v2/teacher/students?page_size=200",
    ),
  ]);
  return <AppointmentsClient initial={data} students={students.items} />;
}
