import { apiServer } from "@/lib/api-server";
import type { WrongQuestionListResponse } from "@/lib/types/wrong-question";
import { StudentWrongQuestionsClient } from "@/components/student/wrong-questions-client";

export const metadata = { title: "Yanlışlarım" };
export const dynamic = "force-dynamic";

export default async function StudentWrongQuestionsPage() {
  const data = await apiServer<WrongQuestionListResponse>(
    "/api/v2/student/wrong-questions",
  );
  return <StudentWrongQuestionsClient initial={data} />;
}
