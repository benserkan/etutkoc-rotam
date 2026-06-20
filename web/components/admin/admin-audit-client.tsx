"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Drama,
  Filter,
  FileText,
  Info,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminKeys, getAdminAudit } from "@/lib/api/admin";
import type { AuditListItem, AuditListResponse } from "@/lib/types/admin";

interface Props {
  initial: AuditListResponse;
  initialAction: string | null;
  initialActorId: number | null;
  initialStartDate: string | null;
  initialEndDate: string | null;
  initialPage: number;
}

/**
 * Audit log listesi — Jinja `audit_list.html` feature parity.
 *
 * 4 filter + pagination (50/sayfa) + before/after diff + via_admin marker.
 */
export function AdminAuditClient({
  initial,
  initialAction,
  initialActorId,
  initialStartDate,
  initialEndDate,
  initialPage,
}: Props) {
  const router = useRouter();
  const q = useQuery<AuditListResponse>({
    queryKey: adminKeys.audit(
      initialAction,
      initialActorId,
      initialStartDate,
      initialEndDate,
      initialPage,
    ),
    queryFn: () =>
      getAdminAudit(
        initialAction,
        initialActorId,
        initialStartDate,
        initialEndDate,
        initialPage,
      ),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  // Filter form state
  const [filterAction, setFilterAction] = React.useState(initialAction ?? "");
  const [filterActorId, setFilterActorId] = React.useState(
    initialActorId != null ? String(initialActorId) : "",
  );
  const [filterStart, setFilterStart] = React.useState(initialStartDate ?? "");
  const [filterEnd, setFilterEnd] = React.useState(initialEndDate ?? "");

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (filterAction) params.set("action", filterAction);
    if (filterActorId) params.set("actor_id", filterActorId);
    if (filterStart) params.set("start_date", filterStart);
    if (filterEnd) params.set("end_date", filterEnd);
    router.push(
      `/admin/audit${params.toString() ? "?" + params.toString() : ""}`,
    );
  }

  function quickRange(daysBack: number) {
    const d = new Date();
    d.setDate(d.getDate() + daysBack);
    const sd = d.toISOString().slice(0, 10);
    const params = new URLSearchParams();
    params.set("start_date", sd);
    if (filterAction) params.set("action", filterAction);
    if (filterActorId) params.set("actor_id", filterActorId);
    router.push(`/admin/audit?${params.toString()}`);
  }

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <FileText className="size-6 text-violet-700" aria-hidden />
          Denetim Kaydı (Audit Log)
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Sistemde kim ne yaptı izleyen kalıcı kayıt. Toplam{" "}
          <strong className="tabular-nums">{data.total}</strong> kayıt — sayfa{" "}
          {data.page}/{data.total_pages}
        </p>
      </header>

      {/* Help collapse */}
      <details className="rounded-md border border-sky-200 bg-sky-50/40 dark:bg-sky-500/10 dark:border-sky-500/30">
        <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-sky-900 hover:bg-sky-100/60 inline-flex items-center gap-1.5 w-full">
          <Info className="size-4" aria-hidden />
          Bu sayfada ne yazıyor? (terim açıklamaları)
        </summary>
        <div className="px-4 py-3 text-sm text-sky-900 space-y-2 border-t border-sky-200">
          <div>
            <strong>Denetim kaydı</strong> — sistemde kim ne yaptı, ne zaman
            yaptı izleyen kalıcı log. Silinemez, sadece eklenir.
          </div>
          <div>
            <strong>Aktör</strong> — eylemi yapan kullanıcı. Başarısız girişte
            yanlış e-posta girildiyse boş olabilir.
          </div>
          <div>
            <strong>Sahte oturum</strong> — süper adminin başka kullanıcı
            olarak sistemde dolaştığı zaman dilimi. O sırada yapılan tüm
            aksiyonlar mor şeritle işaretlenir.
          </div>
          <div>
            <strong>Detay</strong> — eylemin teknik ek bilgileri. Değişiklik
            yapıldıysa &ldquo;önce → sonra&rdquo; diff&apos;i yan yana
            gösterilir.
          </div>
        </div>
      </details>

      {/* Filter form */}
      <Card>
        <CardContent className="p-3">
          <form
            onSubmit={applyFilters}
            className="flex items-end gap-3 flex-wrap"
          >
            <div>
              <Label
                htmlFor="action"
                className="text-[11px] uppercase tracking-wide"
              >
                Olay tipi
              </Label>
              <select
                id="action"
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
                className="mt-1 px-3 py-2 border border-input rounded text-sm bg-card max-w-[200px]"
              >
                <option value="">— Tümü —</option>
                {data.all_actions.map((a) => (
                  <option key={a.value} value={a.value}>
                    {a.value}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label
                htmlFor="actor"
                className="text-[11px] uppercase tracking-wide"
              >
                Aktör ID
              </Label>
              <Input
                id="actor"
                type="number"
                value={filterActorId}
                onChange={(e) => setFilterActorId(e.target.value)}
                placeholder="user.id"
                className="mt-1 w-28"
              />
            </div>
            <div>
              <Label
                htmlFor="sd"
                className="text-[11px] uppercase tracking-wide"
              >
                Başlangıç
              </Label>
              <Input
                id="sd"
                type="date"
                value={filterStart}
                onChange={(e) => setFilterStart(e.target.value)}
                className="mt-1"
              />
            </div>
            <div>
              <Label
                htmlFor="ed"
                className="text-[11px] uppercase tracking-wide"
              >
                Bitiş
              </Label>
              <Input
                id="ed"
                type="date"
                value={filterEnd}
                onChange={(e) => setFilterEnd(e.target.value)}
                className="mt-1"
              />
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="submit"
                className="bg-slate-700 hover:bg-slate-800 text-white"
              >
                <Filter className="size-4" aria-hidden />
                Filtrele
              </Button>
              <Link
                href="/admin/audit"
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Temizle
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Hızlı kısayollar */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="text-muted-foreground/70">Hızlı:</span>
        <button
          type="button"
          onClick={() => quickRange(-1)}
          className="px-2 py-1 border border-border rounded hover:bg-muted/60"
        >
          Son 24 saat
        </button>
        <button
          type="button"
          onClick={() => quickRange(-7)}
          className="px-2 py-1 border border-border rounded hover:bg-muted/60"
        >
          Son 7 gün
        </button>
        <button
          type="button"
          onClick={() => quickRange(-30)}
          className="px-2 py-1 border border-border rounded hover:bg-muted/60"
        >
          Son 30 gün
        </button>
      </div>

      {/* Table */}
      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Filtreyle eşleşen kayıt yok.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Zaman</th>
                  <th className="text-left px-3 py-2 font-medium">Olay</th>
                  <th className="text-left px-3 py-2 font-medium">Aktör</th>
                  <th className="text-left px-3 py-2 font-medium">E-posta</th>
                  <th className="text-left px-3 py-2 font-medium">Hedef</th>
                  <th className="text-left px-3 py-2 font-medium">IP</th>
                  <th className="text-left px-3 py-2 font-medium">Detay</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((item) => (
                  <AuditRow key={item.id} item={item} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Pagination */}
      {data.total_pages > 1 && (
        <Pagination
          page={data.page}
          totalPages={data.total_pages}
          action={initialAction}
          actorId={initialActorId}
          startDate={initialStartDate}
          endDate={initialEndDate}
        />
      )}
    </div>
  );
}

function AuditRow({ item }: { item: AuditListItem }) {
  const actionClass = actionToneClass(item.action);
  return (
    <tr
      className={cn(
        item.via_admin_id != null &&
          "bg-violet-50 border-l-4 border-violet-400",
      )}
      title={
        item.via_admin_id != null ? "Sahte oturum sırasında yapıldı" : undefined
      }
    >
      <td className="px-3 py-2 text-muted-foreground whitespace-nowrap tabular-nums">
        {formatDateTime(item.created_at)}
      </td>
      <td className="px-3 py-2">
        <span className={actionClass}>{item.action_label}</span>
        <div className="text-[10px] text-muted-foreground/70 font-mono">
          {item.action}
        </div>
      </td>
      <td className="px-3 py-2">
        {item.actor ? (
          <Link
            href={`/admin/users/${item.actor.id}`}
            className="text-indigo-600 hover:text-indigo-800"
          >
            {item.actor.full_name}
          </Link>
        ) : item.actor_id ? (
          `#${item.actor_id}`
        ) : (
          "—"
        )}
        {item.via_admin && (
          <div className="text-[10px] text-violet-700 mt-0.5 inline-flex items-center gap-1">
            <Drama className="size-3" aria-hidden />
            sahte oturum:{" "}
            <Link
              href={`/admin/users/${item.via_admin.id}`}
              className="font-medium hover:underline"
            >
              {item.via_admin.full_name}
            </Link>
          </div>
        )}
      </td>
      <td className="px-3 py-2 text-muted-foreground font-mono">
        {item.email_attempted ?? "—"}
      </td>
      <td className="px-3 py-2 text-muted-foreground">
        {item.target_type ? (
          item.target_type === "user" && item.target_id ? (
            <Link
              href={`/admin/users/${item.target_id}`}
              className="hover:text-indigo-600"
            >
              user #{item.target_id}
            </Link>
          ) : item.target_type === "institution" && item.target_id ? (
            <Link
              href={`/admin/institutions/${item.target_id}`}
              className="hover:text-indigo-600"
            >
              inst #{item.target_id}
            </Link>
          ) : (
            <>
              {item.target_type}
              {item.target_id != null ? ` #${item.target_id}` : ""}
            </>
          )
        ) : (
          "—"
        )}
      </td>
      <td className="px-3 py-2 text-muted-foreground font-mono">
        {item.ip_address ?? "—"}
      </td>
      <td className="px-3 py-2 text-muted-foreground max-w-md">
        <DetailCell item={item} />
      </td>
    </tr>
  );
}

function DetailCell({ item }: { item: AuditListItem }) {
  if (!item.details_parsed) return <span>—</span>;
  const parsed = item.details_parsed;
  const hasDiff = "before" in parsed || "after" in parsed;
  if (hasDiff) {
    return (
      <details className="group">
        <summary className="cursor-pointer text-indigo-600 hover:text-indigo-800 text-xs font-medium">
          ↳ Değişim diff&apos;i (önce / sonra)
        </summary>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
          <div className="bg-rose-50 border border-rose-200 rounded p-2 dark:bg-rose-500/10 dark:border-rose-500/30">
            <div className="text-rose-700 font-semibold mb-1">ÖNCE</div>
            <pre className="text-rose-900 whitespace-pre-wrap break-words font-mono">
              {"before" in parsed ? JSON.stringify(parsed.before, null, 2) : "—"}
            </pre>
          </div>
          <div className="bg-emerald-50 border border-emerald-200 rounded p-2 dark:bg-emerald-500/10 dark:border-emerald-500/30">
            <div className="text-emerald-700 font-semibold mb-1">SONRA</div>
            <pre className="text-emerald-900 whitespace-pre-wrap break-words font-mono">
              {"after" in parsed ? JSON.stringify(parsed.after, null, 2) : "—"}
            </pre>
          </div>
        </div>
      </details>
    );
  }
  return (
    <details>
      <summary className="cursor-pointer text-muted-foreground hover:text-foreground text-xs">
        ↳ Detay
      </summary>
      <pre className="mt-1 text-[11px] font-mono whitespace-pre-wrap break-words">
        {JSON.stringify(parsed, null, 2)}
      </pre>
    </details>
  );
}

function Pagination({
  page,
  totalPages,
  action,
  actorId,
  startDate,
  endDate,
}: {
  page: number;
  totalPages: number;
  action: string | null;
  actorId: number | null;
  startDate: string | null;
  endDate: string | null;
}) {
  function buildHref(p: number): string {
    const params = new URLSearchParams();
    if (action) params.set("action", action);
    if (actorId != null) params.set("actor_id", String(actorId));
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    if (p > 1) params.set("page", String(p));
    return `/admin/audit${params.toString() ? "?" + params.toString() : ""}`;
  }
  return (
    <div className="flex items-center justify-center gap-2 text-sm">
      {page > 1 && (
        <Button asChild variant="outline" size="sm">
          <Link href={buildHref(page - 1)}>
            <ChevronLeft className="size-4" aria-hidden />
            Önceki
          </Link>
        </Button>
      )}
      <span className="text-muted-foreground tabular-nums">
        {page} / {totalPages}
      </span>
      {page < totalPages && (
        <Button asChild variant="outline" size="sm">
          <Link href={buildHref(page + 1)}>
            Sonraki
            <ChevronRight className="size-4" aria-hidden />
          </Link>
        </Button>
      )}
    </div>
  );
}

function actionToneClass(action: string): string {
  if (
    [
      "login_failed",
      "login_locked",
      "permission_denied",
      "user_delete",
      "institution_delete",
    ].includes(action)
  ) {
    return "text-rose-700 font-medium";
  }
  if (["login_success", "logout"].includes(action)) {
    return "text-emerald-700";
  }
  if (action.startsWith("impersonate")) {
    return "text-violet-700 font-semibold";
  }
  if (
    action.startsWith("user_") ||
    action.startsWith("institution_") ||
    action === "role_change"
  ) {
    return "text-indigo-700";
  }
  return "text-foreground/80";
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}
