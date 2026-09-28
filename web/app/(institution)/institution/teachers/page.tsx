import { apiServer } from "@/lib/api-server";
import type {
  InstitutionTeacherListResponse,
  InvitationListResponse,
} from "@/lib/types/institution";
import { TeachersListClient } from "@/components/institution/teachers-list-client";

/**
 * /institution/teachers — Öğretmen yönetimi. İki sekme (2026-09-28):
 *   - Öğretmenler (varsayılan) — "Öğretmen ekle" hesabı hemen açar
 *   - Davet bağlantıları (?tab=davet) — öğretmen kendi kaydolur
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Öğretmenler" };

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function InstitutionTeachersPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const tab = sp.tab === "davet" ? "davet" : "liste";
  const [data, invitations] = await Promise.all([
    apiServer<InstitutionTeacherListResponse>("/api/v2/institution/teachers"),
    apiServer<InvitationListResponse>("/api/v2/institution/invitations"),
  ]);
  return <TeachersListClient initial={data} invitations={invitations} tab={tab} />;
}
