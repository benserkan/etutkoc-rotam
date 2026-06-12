import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import type { StudentSurveyFillResponse } from "@/lib/types/survey";
import { SurveyFillClient } from "@/components/student/survey-fill-client";

export const metadata = { title: "Anket" };
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function StudentSurveyFillPage({ params }: PageProps) {
  const { id } = await params;
  const assignmentId = Number(id);
  if (!Number.isInteger(assignmentId) || assignmentId <= 0) notFound();
  let data: StudentSurveyFillResponse;
  try {
    data = await apiServer<StudentSurveyFillResponse>(
      `/api/v2/student/surveys/${assignmentId}`,
    );
  } catch {
    notFound();
  }
  return <SurveyFillClient assignmentId={assignmentId} initial={data} />;
}
