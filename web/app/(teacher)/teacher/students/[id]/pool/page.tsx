import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { PoolBundleResponse } from "@/lib/api/pool";
import { PoolEditor } from "@/components/teacher/pool/pool-editor";

/**
 * /teacher/students/[id]/pool — haftalık görev havuzu (dershane modu) rehber editörü.
 * Gün-gün programın (/week) ALTERNATİFİ; öğrenci havuz modunda değilse ekran
 * moda geçiş kartı gösterir, gün-gün yapıya dokunmaz.
 */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ mod?: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Haftalık havuz · #${id}` };
}

export default async function TeacherStudentPoolPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const { mod } = await searchParams;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();
  let data: PoolBundleResponse;
  try {
    data = await apiServer<PoolBundleResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(String(numericId))}/pool`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return <PoolEditor studentId={numericId} initial={data}
                     initialView={mod === "duzenle" ? "duzenle" : mod === "izle" ? "izle" : undefined} />;
}
