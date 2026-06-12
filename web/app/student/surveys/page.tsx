import { apiServer } from "@/lib/api-server";
import type { StudentSurveysResponse } from "@/lib/types/survey";
import { StudentSurveysClient } from "@/components/student/surveys-client";

export const metadata = { title: "Anketlerim" };
export const dynamic = "force-dynamic";

export default async function StudentSurveysPage() {
  const data = await apiServer<StudentSurveysResponse>("/api/v2/student/surveys");
  return <StudentSurveysClient initial={data} />;
}
