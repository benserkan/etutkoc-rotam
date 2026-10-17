import { apiServer } from "@/lib/api-server";
import { peopleQueryString } from "@/lib/api/admin";
import type { PeopleActivity, PeopleQuery, PeopleResponse, PeopleRole, PeopleSort } from "@/lib/types/admin";
import { AdminPeopleClient } from "@/components/admin/admin-people-client";

/**
 * /admin/users — Kullanıcılar: rol sekmeleri + aktivite kümeleri (2026-10-17).
 * Veri: GET /api/v2/admin/people (role/activity/q/institution_id/sort/page).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kullanıcılar — Süper Admin" };

const ROLES: PeopleRole[] = ["teacher", "student", "parent", "institution_admin", "super_admin"];
const ACTS: PeopleActivity[] = ["all", "today", "week", "silent", "never"];
const SORTS: PeopleSort[] = ["activity", "name", "created"];

interface PageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function AdminUsersPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const query: PeopleQuery = {
    role: ROLES.includes(sp.role as PeopleRole) ? (sp.role as PeopleRole) : "teacher",
    activity: ACTS.includes(sp.activity as PeopleActivity) ? (sp.activity as PeopleActivity) : "all",
    q: sp.q ?? "",
    institutionId: sp.institution_id ? Number(sp.institution_id) : null,
    sort: SORTS.includes(sp.sort as PeopleSort) ? (sp.sort as PeopleSort) : "activity",
    page: Math.max(1, Number(sp.page) || 1),
  };
  const data = await apiServer<PeopleResponse>(`/api/v2/admin/people?${peopleQueryString(query)}`);
  return <AdminPeopleClient initial={data} initialQuery={query} />;
}
