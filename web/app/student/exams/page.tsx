import { apiServer } from "@/lib/api-server";
import type { StudentExamsResponse } from "@/lib/types/student";
import { StudentExamsClient } from "@/components/student/student-exams-client";

export const metadata = { title: "Denemelerim" };
export const dynamic = "force-dynamic";

export default async function StudentExamsPage() {
  const data = await apiServer<StudentExamsResponse>("/api/v2/student/exams");
  return <StudentExamsClient initial={data} />;
}
