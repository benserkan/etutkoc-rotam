import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { PoolSessionResponse } from "@/lib/api/pool";
import { PoolSession } from "@/components/teacher/pool/pool-session";

/** /teacher/students/[id]/pool/session — seans ekranı (K19–K22): geçen dönemin değerlendirmesi. */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Seans · havuz #${id}` };
}

export default async function TeacherPoolSessionPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  let data: PoolSessionResponse;
  try {
    data = await apiServer<PoolSessionResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(String(numericId))}/pool/session`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return <PoolSession studentId={numericId} initial={data} />;
}
