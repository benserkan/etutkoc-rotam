import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { AccountHistoryResponse } from "@/lib/types/admin";
import { AccountHistoryClient } from "@/components/admin/account-history-client";

/**
 * /admin/users/[id]/account-history — Kullanıcı (bağımsız öğretmen)
 * hesap hareketleri. Owner-pattern: User için Invoice yoktur (backend filter).
 *
 * Jinja kaynağı: admin.py:466-496 (user_account_history)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Hesap Hareketleri — Kullanıcı" };

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ years?: string; include_archived?: string }>;
}

export default async function UserAccountHistoryPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const uid = Number(id);
  if (!Number.isFinite(uid) || uid <= 0) notFound();

  const years = clampYears(sp.years);
  const includeArchived = sp.include_archived === "1";

  const qs = new URLSearchParams();
  qs.set("years", String(years));
  if (includeArchived) qs.set("include_archived", "1");

  let data: AccountHistoryResponse;
  try {
    data = await apiServer<AccountHistoryResponse>(
      `/api/v2/admin/account-history/user/${uid}?${qs.toString()}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <AccountHistoryClient
      initial={data}
      ownerType="user"
      ownerId={uid}
      years={years}
      includeArchived={includeArchived}
      backHref={`/admin/users/${uid}`}
      backLabel="Kullanıcı detayı"
    />
  );
}

function clampYears(raw: string | undefined): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 3;
  return Math.min(10, Math.max(1, Math.floor(n)));
}
