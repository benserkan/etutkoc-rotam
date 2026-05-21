import { notFound } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { AccountHistoryResponse } from "@/lib/types/admin";
import { AccountHistoryClient } from "@/components/admin/account-history-client";

/**
 * /admin/institutions/[id]/account-history — Kurum hesap hareketleri.
 *
 * Jinja kaynağı: admin.py:432-463 (institution_account_history)
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Hesap Hareketleri — Kurum" };

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ years?: string; include_archived?: string }>;
}

export default async function InstitutionAccountHistoryPage({
  params,
  searchParams,
}: PageProps) {
  const { id } = await params;
  const sp = await searchParams;
  const iid = Number(id);
  if (!Number.isFinite(iid) || iid <= 0) notFound();

  const years = clampYears(sp.years);
  const includeArchived = sp.include_archived === "1";

  const qs = new URLSearchParams();
  qs.set("years", String(years));
  if (includeArchived) qs.set("include_archived", "1");

  let data: AccountHistoryResponse;
  try {
    data = await apiServer<AccountHistoryResponse>(
      `/api/v2/admin/account-history/institution/${iid}?${qs.toString()}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <AccountHistoryClient
      initial={data}
      ownerType="institution"
      ownerId={iid}
      years={years}
      includeArchived={includeArchived}
      backHref={`/admin/institutions/${iid}`}
      backLabel="Kurum detayı"
    />
  );
}

function clampYears(raw: string | undefined): number {
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return 3;
  return Math.min(10, Math.max(1, Math.floor(n)));
}
