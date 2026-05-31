import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { ParentSessionsResponse } from "@/lib/types/parent";
import { ParentSessionsClient } from "@/components/parent/parent-sessions-client";

/**
 * /parent/students/[id]/sessions — M4
 *
 * Seans hareketleri + tahsilat özeti. KVKK: koça-özel notlar (agenda,
 * coach_note, mood vb.) backend tarafında zaten gizli.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Seans Hareketleri — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ParentSessionsPage({ params }: PageProps) {
  const { id } = await params;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();

  let data: ParentSessionsResponse;
  try {
    data = await apiServer<ParentSessionsResponse>(
      `/api/v2/parent/students/${sid}/sessions?months=12`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return <ParentSessionsClient initial={data} studentId={sid} />;
}
