import { apiServer } from "@/lib/api-server";
import type { InstitutionTeacherListResponse } from "@/lib/types/institution";
import { TeachersListClient } from "@/components/institution/teachers-list-client";

/**
 * /institution/teachers — Öğretmen yönetimi.
 *
 * Jinja kaynağı: app/templates/institution/teachers_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmenler" };

export default async function InstitutionTeachersPage() {
  const data = await apiServer<InstitutionTeacherListResponse>(
    "/api/v2/institution/teachers",
  );
  return <TeachersListClient initial={data} />;
}
