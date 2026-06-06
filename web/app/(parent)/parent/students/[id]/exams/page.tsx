import { notFound } from "next/navigation";

import { ParentExamsInsightClient } from "@/components/parent/parent-exams-insight-client";

export const dynamic = "force-dynamic";
export const metadata = { title: "Denemeler & Analiz — Veli Paneli" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function ParentExamsPage({ params }: PageProps) {
  const { id } = await params;
  const sid = Number(id);
  if (!Number.isFinite(sid) || sid <= 0) notFound();
  return <ParentExamsInsightClient studentId={sid} />;
}
