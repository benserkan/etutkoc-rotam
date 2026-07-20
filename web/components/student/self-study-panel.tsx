"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, TentTree } from "lucide-react";

import {
  getStudentSelfStudy,
  getStudentSelfStudyOptions,
  selfStudyKeys,
} from "@/lib/api/self-study";
import {
  useDeclareSelfStudy,
  useWithdrawSelfStudy,
} from "@/lib/hooks/use-self-study-mutations";
import type {
  SelfStudyListResponse,
  SelfStudyOptionsResponse,
} from "@/lib/types/self-study";
import {
  SelfStudyEntryDialog,
  SelfStudyEntryRow,
} from "@/components/shared/self-study";
import { Button } from "@/components/ui/button";

/**
 * Öğrenci "Bağımsız çalışma" paneli (Kitaplarım sayfası).
 * Tatilde/program dışında çözülen testler beyan edilir; koç onaylayınca
 * kitap ilerlemesine işlenir.
 */
export function StudentSelfStudyPanel() {
  const listQ = useQuery<SelfStudyListResponse>({
    queryKey: selfStudyKeys.studentList(),
    queryFn: getStudentSelfStudy,
    staleTime: 30_000,
  });
  const [dialogOpen, setDialogOpen] = React.useState(false);
  const optionsQ = useQuery<SelfStudyOptionsResponse>({
    queryKey: selfStudyKeys.studentOptions(),
    queryFn: getStudentSelfStudyOptions,
    enabled: dialogOpen,
    staleTime: 15_000,
  });
  const declare = useDeclareSelfStudy();
  const withdraw = useWithdrawSelfStudy();

  const items = listQ.data?.items ?? [];
  const pendingCount = listQ.data?.pending_count ?? 0;

  return (
    <section className="rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2.5 min-w-0">
          <TentTree
            className="size-5 text-cyan-600 dark:text-cyan-400 shrink-0 mt-0.5"
            aria-hidden
          />
          <div className="space-y-0.5 min-w-0">
            <p className="font-medium">
              Kendi başına mı çalıştın?
              {pendingCount > 0 ? (
                <span className="ml-2 inline-flex items-center rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:text-amber-200">
                  {pendingCount} bildirim onay bekliyor
                </span>
              ) : null}
            </p>
            <p className="text-xs text-muted-foreground">
              Tatilde, kursta ya da programında olmadan çözdüğün testleri
              bildir — koçun onaylayınca ilerlemene işlenir.
            </p>
          </div>
        </div>
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          Bağımsız çalışma bildir
        </Button>
      </div>

      {items.length > 0 ? (
        <details className="group" open={pendingCount > 0}>
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground inline-flex items-center gap-1 list-none [&::-webkit-details-marker]:hidden">
            <ChevronRight
              className="size-3 transition-transform group-open:rotate-90"
              aria-hidden
            />
            Bildirimlerim ({items.length})
          </summary>
          <ul className="mt-1 divide-y divide-border">
            {items.slice(0, 15).map((it) => (
              <SelfStudyEntryRow
                key={it.id}
                item={it}
                isBusy={withdraw.isPending}
                onWithdraw={
                  it.status === "pending"
                    ? () => withdraw.mutate({ entryId: it.id })
                    : undefined
                }
              />
            ))}
          </ul>
        </details>
      ) : null}

      <SelfStudyEntryDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        books={optionsQ.data?.books ?? []}
        mode="student"
        isPending={declare.isPending}
        onSubmit={(body) =>
          declare.mutate(body, { onSuccess: () => setDialogOpen(false) })
        }
      />
    </section>
  );
}
