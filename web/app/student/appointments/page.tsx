import { apiServer } from "@/lib/api-server";
import type { StudentAppointmentsResponse } from "@/lib/types/appointment";
import { StudentAppointmentsClient } from "@/components/student/student-appointments-client";

export const metadata = { title: "Görüşmelerim" };
export const dynamic = "force-dynamic";

export default async function StudentAppointmentsPage() {
  const data = await apiServer<StudentAppointmentsResponse>(
    "/api/v2/student/appointments",
  );
  return <StudentAppointmentsClient initial={data} />;
}
