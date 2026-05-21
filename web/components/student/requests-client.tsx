"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarDays,
  CheckCircle2,
  Clock,
  Loader2,
  MessageCircle,
  Replace,
  RotateCcw,
  Trash2,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/error-state";
import { getStudentRequests, studentKeys } from "@/lib/api/student";
import { useWithdrawRequest } from "@/lib/hooks/use-student-mutations";
import type {
  RequestType,
  StudentRequestItem,
  StudentRequestListResponse,
} from "@/lib/types/student";
import { formatDateShort } from "@/lib/locale";

type Filter = "all" | "pending" | "answered";

interface Props {
  initial: StudentRequestListResponse;
  initialFilter: Filter;
}

/**
 * Taleplerim sayfası — backend filtre (status=all|pending|answered) + withdraw.
 *
 * Filtre değişimi URL'i günceller (server re-fetch). useQuery initial veriyi
 * seed eder.
 */
export function RequestsClient({ initial, initialFilter }: Props) {
  const router = useRouter();
  const [filter, setFilter] = React.useState<Filter>(initialFilter);
  const q = useQuery<StudentRequestListResponse>({
    queryKey: studentKeys.requests(filter),
    queryFn: () => getStudentRequests(filter),
    initialData: filter === initialFilter ? initial : undefined,
    staleTime: 30_000,
  });
  const withdraw = useWithdrawRequest();

  function applyFilter(next: Filter) {
    setFilter(next);
    router.push(`/student/requests?status=${next}`);
  }

  if (q.isError) {
    return <ErrorState onRetry={() => q.refetch()} />;
  }

  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header className="space-y-2">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          Taleplerim
        </h1>
        <p className="text-sm text-muted-foreground">
          Koçuna gönderdiğin değişiklik, çıkar, ekle ve soru talepleri. Bekleyen
          talepler geri çekilebilir.
        </p>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <FilterButton active={filter === "all"} onClick={() => applyFilter("all")}>
            Tümü ({data.total})
          </FilterButton>
          <FilterButton active={filter === "pending"} onClick={() => applyFilter("pending")}>
            Bekleyen ({data.pending_count})
          </FilterButton>
          <FilterButton active={filter === "answered"} onClick={() => applyFilter("answered")}>
            Yanıtlanan
          </FilterButton>
        </div>
      </header>

      {data.items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
          {filter === "pending"
            ? "Bekleyen talep yok."
            : filter === "answered"
              ? "Yanıtlanmış talep yok."
              : "Henüz talep oluşturmamışsın."}
        </div>
      ) : (
        <ul className="space-y-3">
          {data.items.map((r) => (
            <RequestRow
              key={r.id}
              req={r}
              onWithdraw={() => withdraw.mutate({ requestId: r.id })}
              pending={withdraw.isPending && withdraw.variables?.requestId === r.id}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm transition-colors",
        active
          ? "bg-foreground text-background"
          : "bg-muted text-muted-foreground hover:bg-muted/70 hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function RequestRow({
  req,
  onWithdraw,
  pending,
}: {
  req: StudentRequestItem;
  onWithdraw: () => void;
  pending: boolean;
}) {
  const typeMeta = TYPE_META[req.type];
  const statusMeta = STATUS_META[req.status];
  const canWithdraw = req.status === "pending";

  return (
    <li className="rounded-lg border border-border bg-card p-4 space-y-2">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "inline-flex items-center justify-center size-8 rounded-md shrink-0",
            typeMeta.bg,
          )}
          aria-hidden
        >
          <typeMeta.Icon className={cn("size-4", typeMeta.fg)} />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-2">
            <p className="font-medium text-sm">{typeMeta.label}</p>
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
                statusMeta.bg,
              )}
            >
              <statusMeta.Icon className="size-3" aria-hidden />
              {statusMeta.label}
            </span>
            <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
              <CalendarDays className="size-3" aria-hidden />
              {formatDateShort(req.created_at)}
            </span>
          </div>

          {req.task_title ? (
            <p className="text-sm text-muted-foreground mt-1">
              {req.task_date ? (
                <Link
                  href={`/student/day?date=${req.task_date}`}
                  className="hover:underline"
                >
                  {req.task_title}
                </Link>
              ) : (
                req.task_title
              )}
            </p>
          ) : null}

          {req.proposed_count !== null || req.proposed_book_name ? (
            <p className="text-xs text-muted-foreground mt-0.5">
              {req.proposed_book_name ? (
                <span>{req.proposed_book_name}</span>
              ) : null}
              {req.proposed_section_label ? (
                <span> · {req.proposed_section_label}</span>
              ) : null}
              {req.proposed_count !== null ? (
                <span> · {req.proposed_count} test</span>
              ) : null}
              {req.proposed_date ? (
                <span> · {req.proposed_date}</span>
              ) : null}
            </p>
          ) : null}

          {req.message ? (
            <blockquote className="mt-2 border-l-2 border-border pl-3 text-sm text-muted-foreground italic">
              {req.message}
            </blockquote>
          ) : null}
          {req.teacher_response ? (
            <div className="mt-2 rounded-md bg-muted/60 p-2.5 text-sm">
              <p className="text-[11px] font-medium text-muted-foreground uppercase tracking-wide">
                Koç yanıtı
              </p>
              <p className="mt-0.5">{req.teacher_response}</p>
            </div>
          ) : null}
        </div>

        {canWithdraw ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={pending}
            onClick={onWithdraw}
          >
            {pending ? (
              <Loader2 className="animate-spin" aria-hidden />
            ) : (
              <XCircle aria-hidden />
            )}
            Geri çek
          </Button>
        ) : null}
      </div>
    </li>
  );
}

const TYPE_META: Record<
  RequestType,
  { label: string; Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>; bg: string; fg: string }
> = {
  change: {
    label: "Sayı değiştir",
    Icon: RotateCcw,
    bg: "bg-blue-100 dark:bg-blue-900/40",
    fg: "text-blue-700 dark:text-blue-300",
  },
  replace: {
    label: "Kaynağı değiştir",
    Icon: Replace,
    bg: "bg-purple-100 dark:bg-purple-900/40",
    fg: "text-purple-700 dark:text-purple-300",
  },
  remove: {
    label: "Görev çıkar",
    Icon: Trash2,
    bg: "bg-rose-100 dark:bg-rose-900/40",
    fg: "text-rose-700 dark:text-rose-300",
  },
  question: {
    label: "Soru",
    Icon: MessageCircle,
    bg: "bg-amber-100 dark:bg-amber-900/40",
    fg: "text-amber-700 dark:text-amber-300",
  },
  add: {
    label: "Yeni görev iste",
    Icon: CalendarDays,
    bg: "bg-emerald-100 dark:bg-emerald-900/40",
    fg: "text-emerald-700 dark:text-emerald-300",
  },
};

const STATUS_META = {
  pending: {
    label: "Bekliyor",
    Icon: Clock,
    bg: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  },
  approved: {
    label: "Onaylandı",
    Icon: CheckCircle2,
    bg: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200",
  },
  rejected: {
    label: "Reddedildi",
    Icon: XCircle,
    bg: "bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200",
  },
  withdrawn: {
    label: "Geri çekildi",
    Icon: RotateCcw,
    bg: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  },
  resolved: {
    label: "Yanıtlandı",
    Icon: MessageCircle,
    bg: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200",
  },
} as const;
