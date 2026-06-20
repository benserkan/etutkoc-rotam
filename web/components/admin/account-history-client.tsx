"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Archive,
  ArrowLeft,
  CalendarRange,
  ChevronDown,
  Info,
  Loader2,
  PackageOpen,
  Undo2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminAccountHistory } from "@/lib/api/admin";
import {
  useAccountHistoryArchive,
  useAccountHistoryBulkArchive,
  useAccountHistoryUnarchive,
} from "@/lib/hooks/use-admin-mutations";
import type {
  AccountHistoryEvent,
  AccountHistoryResponse,
  AccountOwnerType,
  AccountRecordType,
} from "@/lib/types/admin";

interface Props {
  initial: AccountHistoryResponse;
  ownerType: AccountOwnerType;
  ownerId: number;
  years: number;
  includeArchived: boolean;
  backHref: string;
  backLabel: string;
}

const YEARS_OPTIONS = [1, 2, 3, 5, 10];

/**
 * Account history timeline — Jinja `account_history.html` feature parity.
 *
 * Hem institution hem user için ortak (Owner-pattern). User için Invoice
 * eventleri olmaz (backend filter).
 *
 * 4 KPI + filter form (years + include_archived) + bulk archive + event list
 * (her event archive/unarchive button).
 */
export function AccountHistoryClient({
  initial,
  ownerType,
  ownerId,
  years,
  includeArchived,
  backHref,
  backLabel,
}: Props) {
  const router = useRouter();
  const q = useQuery<AccountHistoryResponse>({
    queryKey: adminKeys.accountHistory(
      ownerType,
      ownerId,
      years,
      includeArchived,
    ),
    queryFn: () =>
      getAdminAccountHistory(ownerType, ownerId, years, includeArchived),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href={backHref}
          className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          {backLabel}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <CalendarRange className="size-6 text-indigo-700" aria-hidden />
          Hesap Hareketleri — {data.owner_name ?? "Bilinmiyor"}
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Plan değişimleri ve faturalar tek zaman akışında. Varsayılan pencere
          son <strong className="tabular-nums">{data.years}</strong> yıl — daha
          eski kayıtlar otomatik gizli, arşivlemeden silinmez.
        </p>
      </header>

      <HelpDetails olderCount={data.older_count} years={data.years} />

      {/* 4 KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi
          label="Gösterilen"
          value={data.total_count}
          tone="default"
          sub={`son ${data.years} yıl`}
        />
        <Kpi
          label="Arşivli (pencere içinde)"
          value={data.archived_count}
          tone="amber"
          sub="&quot;Arşivi göster&quot; ile görünür"
        />
        <Kpi
          label="3 yıldan eski"
          value={data.older_count}
          tone="slate"
          sub="arşivlemeye uygun"
        />
        <Kpi
          label="Pencere başı"
          value={formatDate(data.window_start)}
          tone="indigo"
          sub={`${data.years} yıl önce`}
        />
      </div>

      {/* Filter + Bulk archive */}
      <FilterBar
        ownerType={ownerType}
        ownerId={ownerId}
        years={years}
        includeArchived={includeArchived}
        olderCount={data.older_count}
        onChange={(newYears, newIncludeArchived) => {
          const params = new URLSearchParams();
          params.set("years", String(newYears));
          if (newIncludeArchived) params.set("include_archived", "1");
          const url =
            ownerType === "institution"
              ? `/admin/institutions/${ownerId}/account-history?${params.toString()}`
              : `/admin/users/${ownerId}/account-history?${params.toString()}`;
          router.push(url);
        }}
      />

      {/* Timeline */}
      {data.events.length === 0 ? (
        <EmptyState
          includeArchived={includeArchived}
          archivedCount={data.archived_count}
          years={data.years}
          ownerType={ownerType}
          ownerId={ownerId}
        />
      ) : (
        <Card>
          <ul className="divide-y divide-border">
            {data.events.map((e) => (
              <EventRow
                key={`${e.record_type}-${e.record_id}`}
                event={e}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

// ============================================================================
// Help details (collapsible explanation)
// ============================================================================

function HelpDetails({
  olderCount,
  years,
}: {
  olderCount: number;
  years: number;
}) {
  return (
    <details className="rounded-md border border-sky-200 bg-sky-50/40 dark:bg-sky-500/10 dark:border-sky-500/30">
      <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-sky-900 hover:bg-sky-100/60 inline-flex items-center gap-1.5 w-full">
        <Info className="size-4" aria-hidden />
        Bu sayfada ne yazıyor? (terim açıklamaları)
        <ChevronDown className="size-3 ml-auto" aria-hidden />
      </summary>
      <div className="px-4 py-3 text-sm text-sky-900 space-y-2 border-t border-sky-200">
        <div>
          <strong>Hesap hareketi</strong> — bu kurum / kullanıcı için yapılan
          plan değişikliği veya kesilen fatura. Her satır bir olay.
        </div>
        <div>
          <strong>{years} yıl penceresi</strong> — varsayılan olarak son {years}{" "}
          yıl gösterilir. Daha eski kayıtlar sistemde duruyor ama görünmez.
          &ldquo;Pencereyi büyüt&rdquo; ile değiştirilebilir.
        </div>
        <div>
          <strong>Arşive ekle</strong> — bir kaydı listeden gizler (silmez).
          Sayfa kalabalıklığını azaltır. &ldquo;Arşivi göster&rdquo; ile geri
          görünür hale gelir. &ldquo;Arşivden çıkar&rdquo; ile aktife döner.
        </div>
        <div>
          <strong>Toplu arşivleme</strong> — {years} yıldan eski TÜM kayıtları
          tek tıkla arşive ekle. Pencere dışında kalan{" "}
          <strong>{olderCount}</strong> kayıt varsa düğme aktif olur.
        </div>
      </div>
    </details>
  );
}

// ============================================================================
// KPI
// ============================================================================

function Kpi({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: number | string;
  tone: "default" | "amber" | "slate" | "indigo";
  sub?: string;
}) {
  const map = {
    default: "border-border bg-card",
    amber: "border-amber-200 bg-amber-50/40 dark:bg-amber-500/10 dark:border-amber-500/30",
    slate: "border-slate-200 bg-slate-50/40 dark:bg-slate-500/10 dark:border-slate-500/30",
    indigo: "border-indigo-200 bg-indigo-50/40 dark:bg-indigo-500/10 dark:border-indigo-500/30",
  };
  const valueColor = {
    default: "text-foreground",
    amber: "text-amber-900",
    slate: "text-slate-900",
    indigo: "text-indigo-900",
  }[tone];
  return (
    <Card className={cn("border", map[tone])}>
      <CardContent className="p-3">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div
          className={cn(
            "text-2xl font-semibold tabular-nums mt-0.5",
            valueColor,
          )}
        >
          {value}
        </div>
        {sub && (
          <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Filter bar
// ============================================================================

function FilterBar({
  ownerType,
  ownerId,
  years,
  includeArchived,
  olderCount,
  onChange,
}: {
  ownerType: AccountOwnerType;
  ownerId: number;
  years: number;
  includeArchived: boolean;
  olderCount: number;
  onChange: (years: number, includeArchived: boolean) => void;
}) {
  const [yearsLocal, setYearsLocal] = React.useState(years);
  const [inclLocal, setInclLocal] = React.useState(includeArchived);

  function apply(e: React.FormEvent) {
    e.preventDefault();
    onChange(yearsLocal, inclLocal);
  }

  return (
    <Card>
      <CardContent className="p-3 flex items-center justify-between flex-wrap gap-3">
        <form
          onSubmit={apply}
          className="flex items-center gap-2 text-sm flex-wrap"
        >
          <label className="text-muted-foreground">Pencere:</label>
          <select
            value={yearsLocal}
            onChange={(e) => setYearsLocal(Number(e.target.value))}
            className="px-2 py-1 border border-input rounded text-sm bg-card"
          >
            {YEARS_OPTIONS.map((y) => (
              <option key={y} value={y}>
                {y} yıl
              </option>
            ))}
          </select>
          <label className="inline-flex items-center gap-1 text-muted-foreground ml-3 cursor-pointer">
            <input
              type="checkbox"
              checked={inclLocal}
              onChange={(e) => setInclLocal(e.target.checked)}
              className="accent-indigo-600"
            />
            Arşivi göster
          </label>
          <Button type="submit" size="sm" variant="outline">
            Uygula
          </Button>
        </form>

        {olderCount > 0 ? (
          <BulkArchiveAction
            ownerType={ownerType}
            ownerId={ownerId}
            olderCount={olderCount}
          />
        ) : (
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1.5">
            <PackageOpen className="size-3.5" aria-hidden />
            3 yıldan eski arşivlenecek kayıt yok
          </span>
        )}
      </CardContent>
    </Card>
  );
}

function BulkArchiveAction({
  ownerType,
  ownerId,
  olderCount,
}: {
  ownerType: AccountOwnerType;
  ownerId: number;
  olderCount: number;
}) {
  const router = useRouter();
  const mut = useAccountHistoryBulkArchive();
  const [open, setOpen] = React.useState(false);

  function onConfirm() {
    mut.mutate(
      {
        owner_type: ownerType,
        owner_id: ownerId,
        years: 3,
        note: "Toplu arşiv (3 yıldan eski)",
      },
      {
        onSuccess: () => {
          setOpen(false);
          router.refresh();
        },
      },
    );
  }

  return (
    <>
      <Button
        size="sm"
        onClick={() => setOpen(true)}
        className="bg-amber-600 hover:bg-amber-700 text-white"
      >
        <Archive className="size-3.5" aria-hidden />
        3 yıldan eski {olderCount} kaydı arşivle
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Toplu Arşivleme</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <strong className="tabular-nums">{olderCount}</strong> adet 3 yıldan
            eski kayıt arşive eklenecek. Onaylıyor musun?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={onConfirm}
              disabled={mut.isPending}
              className="bg-amber-600 hover:bg-amber-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Archive className="size-4" aria-hidden />
              )}
              Arşivle
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================================
// Event row
// ============================================================================

function EventRow({ event }: { event: AccountHistoryEvent }) {
  return (
    <li
      className={cn(
        "px-4 py-3 hover:bg-muted/40",
        event.archived && "bg-muted/30 opacity-75",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground whitespace-nowrap tabular-nums">
              {formatDateTime(event.when)}
            </span>
            <span
              className={cn(
                "inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium",
                badgeColorClass(event.badge_color),
              )}
            >
              {event.badge_label}
            </span>
            <span className="text-[10px] text-muted-foreground/70 font-mono">
              {event.record_type}#{event.record_id}
            </span>
            {event.archived && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-amber-100 text-amber-800 border border-amber-200">
                <Archive className="size-2.5 mr-0.5" aria-hidden />
                arşivli
              </span>
            )}
          </div>
          <div className="text-sm font-medium mt-1">{event.title}</div>
          {event.subtitle && (
            <div className="text-xs text-muted-foreground mt-0.5">
              {event.subtitle}
            </div>
          )}
          {event.archived && event.archive_note && (
            <div className="text-[11px] text-amber-700 mt-1 italic">
              Arşiv notu: {event.archive_note}
              {event.archived_at &&
                ` · ${formatDateTime(event.archived_at)}`}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-1.5 whitespace-nowrap shrink-0">
          {event.archived ? (
            <UnarchiveButton
              recordType={event.record_type}
              recordId={event.record_id}
            />
          ) : (
            <ArchiveButton
              recordType={event.record_type}
              recordId={event.record_id}
            />
          )}
        </div>
      </div>
    </li>
  );
}

function ArchiveButton({
  recordType,
  recordId,
}: {
  recordType: AccountRecordType;
  recordId: number;
}) {
  const router = useRouter();
  const mut = useAccountHistoryArchive();
  return (
    <button
      type="button"
      onClick={() => {
        mut.mutate(
          { record_type: recordType, record_id: recordId },
          { onSuccess: () => router.refresh() },
        );
      }}
      disabled={mut.isPending}
      className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-0.5"
      title="Bu kaydı arşive ekle (silmez)"
    >
      {mut.isPending ? (
        <Loader2 className="size-3 animate-spin" aria-hidden />
      ) : (
        <Archive className="size-3" aria-hidden />
      )}
      Arşive ekle
    </button>
  );
}

function UnarchiveButton({
  recordType,
  recordId,
}: {
  recordType: AccountRecordType;
  recordId: number;
}) {
  const router = useRouter();
  const mut = useAccountHistoryUnarchive();
  return (
    <button
      type="button"
      onClick={() => {
        mut.mutate(
          { record_type: recordType, record_id: recordId },
          { onSuccess: () => router.refresh() },
        );
      }}
      disabled={mut.isPending}
      className="text-xs text-emerald-700 hover:text-emerald-900 underline underline-offset-2 inline-flex items-center gap-0.5"
    >
      {mut.isPending ? (
        <Loader2 className="size-3 animate-spin" aria-hidden />
      ) : (
        <Undo2 className="size-3" aria-hidden />
      )}
      Arşivden çıkar
    </button>
  );
}

// ============================================================================
// Empty state
// ============================================================================

function EmptyState({
  includeArchived,
  archivedCount,
  years,
  ownerType,
  ownerId,
}: {
  includeArchived: boolean;
  archivedCount: number;
  years: number;
  ownerType: AccountOwnerType;
  ownerId: number;
}) {
  const showArchivedUrl =
    ownerType === "institution"
      ? `/admin/institutions/${ownerId}/account-history?years=${years}&include_archived=1`
      : `/admin/users/${ownerId}/account-history?years=${years}&include_archived=1`;
  return (
    <Card>
      <CardContent className="p-12 text-center text-sm text-muted-foreground">
        {includeArchived ? (
          "Bu pencerede hiç hesap hareketi yok (arşivli dahil)."
        ) : (
          <>
            Bu pencerede aktif hesap hareketi yok.
            {archivedCount > 0 && (
              <>
                <br />
                <Link
                  href={showArchivedUrl}
                  className="text-indigo-700 hover:underline mt-2 inline-block"
                >
                  Arşivli {archivedCount} kaydı göster →
                </Link>
              </>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function badgeColorClass(color: string): string {
  const map: Record<string, string> = {
    emerald: "bg-emerald-100 text-emerald-800",
    rose: "bg-rose-100 text-rose-800",
    amber: "bg-amber-100 text-amber-800",
    violet: "bg-violet-100 text-violet-800",
    indigo: "bg-indigo-100 text-indigo-800",
    slate: "bg-slate-100 text-slate-800",
  };
  return map[color] ?? "bg-slate-100 text-slate-800";
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
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
