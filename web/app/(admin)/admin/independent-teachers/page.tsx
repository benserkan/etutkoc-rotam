import { apiServer } from "@/lib/api-server";
import { peopleQueryString } from "@/lib/api/admin";
import type { PeopleActivity, PeoplePlan, PeopleQuery, PeopleResponse, PeopleSort } from "@/lib/types/admin";
import { AdminPeopleClient } from "@/components/admin/admin-people-client";

/**
 * /admin/independent-teachers — Bağımsız koçlar (2026-10-17): Kullanıcılar
 * sayfasıyla aynı dil; rol sekmesi yerine paket durumu çipleri.
 * Veri: GET /api/v2/admin/people?role=teacher&independent=true
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bağımsız Koçlar — Süper Admin" };

const ACTS: PeopleActivity[] = ["all", "today", "week", "silent", "never"];
const PLANS: PeoplePlan[] = ["all", "trial", "active", "payment_pending", "past_due", "free"];
const SORTS: PeopleSort[] = ["activity", "name", "created"];

interface PageProps {
  searchParams: Promise<Record<string, string | undefined>>;
}

export default async function AdminIndependentTeachersPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const query: PeopleQuery = {
    independent: true,
    role: "teacher",
    plan: PLANS.includes(sp.plan as PeoplePlan) ? (sp.plan as PeoplePlan) : "all",
    activity: ACTS.includes(sp.activity as PeopleActivity) ? (sp.activity as PeopleActivity) : "all",
    q: sp.q ?? "",
    institutionId: null,
    sort: SORTS.includes(sp.sort as PeopleSort) ? (sp.sort as PeopleSort) : "activity",
    page: Math.max(1, Number(sp.page) || 1),
  };
  const data = await apiServer<PeopleResponse>(`/api/v2/admin/people?${peopleQueryString(query)}`);
  return <AdminPeopleClient initial={data} initialQuery={query} />;
}
