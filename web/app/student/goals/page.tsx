import { apiServer } from "@/lib/api-server";
import type { GoalListResponse } from "@/lib/types/student";
import { GoalsClient } from "@/components/student/goals-client";

export const metadata = { title: "Hedefler" };
export const dynamic = "force-dynamic";

export default async function StudentGoalsPage() {
  const data = await apiServer<GoalListResponse>("/api/v2/student/goals");
  return <GoalsClient initial={data} />;
}
