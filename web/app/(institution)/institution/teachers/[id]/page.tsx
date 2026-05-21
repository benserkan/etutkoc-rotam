import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { TeacherCardResponse } from "@/lib/types/institution";
import { TeacherCardClient } from "@/components/institution/teacher-card-client";

/**
 * /institution/teachers/[id] — Öğretmen kartı (privacy korumalı).
 *
 * Jinja kaynağı: app/templates/institution/teacher_card.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmen kartı" };

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function InstitutionTeacherCardPage({ params }: PageProps) {
  const { id } = await params;
  const parsed = Number(id);
  if (!Number.isFinite(parsed) || parsed <= 0) notFound();

  let data: TeacherCardResponse;
  try {
    data = await apiServer<TeacherCardResponse>(
      `/api/v2/institution/teachers/${parsed}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
  return <TeacherCardClient initial={data} teacherId={parsed} />;
}
