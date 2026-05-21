import { apiServer } from "@/lib/api-server";
import type { AdminUserListResponse } from "@/lib/types/admin";
import { AdminUsersClient } from "@/components/admin/admin-users-client";

/**
 * /admin/users — Kullanıcı listesi (filter + table + Yeni Kullanıcı).
 *
 * Jinja kaynağı: admin.py:708-754 + users_list.html
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Kullanıcılar — Süper Admin" };

interface PageProps {
  searchParams: Promise<{
    role?: string;
    institution_id?: string;
    q?: string;
  }>;
}

export default async function AdminUsersPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const qs = new URLSearchParams();
  if (sp.role) qs.set("role", sp.role);
  if (sp.institution_id) qs.set("institution_id", sp.institution_id);
  if (sp.q) qs.set("q", sp.q);
  const suffix = qs.toString();
  const data = await apiServer<AdminUserListResponse>(
    `/api/v2/admin/users${suffix ? `?${suffix}` : ""}`,
  );
  return (
    <AdminUsersClient
      initial={data}
      initialRole={sp.role ?? null}
      initialInstitutionId={
        sp.institution_id ? Number(sp.institution_id) : null
      }
      initialQ={sp.q ?? null}
    />
  );
}
