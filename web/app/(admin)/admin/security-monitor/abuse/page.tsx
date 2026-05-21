import { apiServer } from "@/lib/api-server";
import type { AbuseResponse } from "@/lib/types/admin";
import { SecurityAbuseClient } from "@/components/admin/security-abuse-client";

/**
 * /admin/security-monitor/abuse — Kötüye Kullanım Kamerası (G4).
 *
 * Jinja kaynağı: admin.py:5482-5625 + security_monitor_abuse.html (199).
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Suistimal Kamerası — Süper Admin" };

export default async function SecurityAbusePage({
  searchParams,
}: {
  searchParams: Promise<{ only_open?: string; kind?: string }>;
}) {
  const sp = await searchParams;
  const onlyOpen = sp.only_open !== "0";
  const kind = sp.kind || null;
  const qs = new URLSearchParams();
  qs.set("only_open", onlyOpen ? "1" : "0");
  if (kind) qs.set("kind", kind);
  const data = await apiServer<AbuseResponse>(
    `/api/v2/admin/security-monitor/abuse?${qs.toString()}`,
  );
  return <SecurityAbuseClient initial={data} onlyOpen={onlyOpen} kind={kind} />;
}
