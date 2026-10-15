"use client";

/**
 * Program modu geçişi (gün gün ↔ haftalık havuz) — 2026-10-15.
 * Önce etkiyi gösterir (sunucu önizlemesi, hiçbir şey yazmaz), koç onaylayınca uygular.
 * Havuz → gün gün geçişi açık dönemde yapılamaz: seans ekranındaki “Seansı bitir” penceresinden yapılır.
 */
import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, CheckCircle2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  getModeHistory, getModeSwitchPreview, modeSwitchKeys, useSwitchProgramMode, type ModeSwitchTask,
} from "@/lib/api/pool";

const MODE_LABEL = { gun_gun: "Gün gün program", havuz: "Haftalık havuz" } as const;

function addDays(iso: string, n: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function fmt(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("tr-TR", { day: "numeric", month: "short", weekday: "short" });
}

function TaskList({ rows, tone }: { rows: ModeSwitchTask[]; tone: "del" | "keep" }) {
  if (!rows.length) return null;
  return (
    <ul className="mt-1 space-y-1">
      {rows.map((t) => (
        <li key={t.task_id} className="flex flex-wrap items-baseline gap-x-2 rounded border px-2 py-1 text-xs">
          <span className="font-medium text-foreground">{fmt(t.date)}</span>
          <span className="min-w-0 flex-1 break-words text-foreground">{t.title}</span>
          {t.planned > 0 && (
            <span className="text-muted-foreground">
              {tone === "keep" ? `${t.completed}/${t.planned} test çözüldü` : `${t.planned} test`}
            </span>
          )}
          {t.is_draft && <span className="rounded bg-slate-600 px-1.5 text-[10px] font-semibold text-white">taslak</span>}
          {t.is_cup && <span className="rounded bg-cyan-700 px-1.5 text-[10px] font-semibold text-white">kap</span>}
        </li>
      ))}
    </ul>
  );
}

export function ModeSwitchDialog({
  studentId, toMode, today, open, onOpenChange,
}: {
  studentId: number;
  toMode: "gun_gun" | "havuz";
  today: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [effective, setEffective] = React.useState(today);
  const [openFirst, setOpenFirst] = React.useState(true);
  const [next, setNext] = React.useState(addDays(today, 7));
  const [note, setNote] = React.useState("");
  const sw = useSwitchProgramMode(studentId);
  const pv = useQuery({
    queryKey: modeSwitchKeys.preview(studentId, toMode, effective),
    queryFn: () => getModeSwitchPreview(studentId, toMode, effective),
    enabled: open && effective >= today,
    staleTime: 0,
  });
  const d = pv.data;

  function submit() {
    sw.mutate(
      {
        to_mode: toMode, effective_on: effective, note: note || null,
        open_first_period: toMode === "havuz" ? openFirst : undefined,
        expected_next_on: toMode === "havuz" && openFirst ? next || null : null,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          router.push(toMode === "havuz"
            ? `/teacher/students/${studentId}/pool?mod=duzenle`
            : `/teacher/students/${studentId}/week`);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" data-testid="mode-switch-dialog">
        <DialogHeader>
          <DialogTitle className="flex flex-wrap items-center gap-2">
            {MODE_LABEL[toMode === "havuz" ? "gun_gun" : "havuz"]}
            <ArrowRight className="size-4" aria-hidden />
            {MODE_LABEL[toMode]}
          </DialogTitle>
          <DialogDescription>
            {toMode === "havuz"
              ? "Geçiş genelde program bittiğinde, yeni hafta başlamadan yapılır. Çözülenler müfredatta ve kitap sayacında kalır; yapılmamış kısımların rezervi kitaba iade edilir."
              : "Bundan sonra programı günlere sen yazarsın. Kalan havuz kalemleri havuzdan çıkar, dönem geçmişinde iz olarak kalır."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 text-sm">
          <label className="block">
            <span className="text-xs text-muted-foreground">Geçiş günü (bu gün ve sonrası yeni modda)</span>
            <Input type="date" value={effective} min={today} onChange={(e) => setEffective(e.target.value)}
                   className="mt-1 w-44" aria-label="Geçiş günü" />
          </label>

          {pv.isLoading && <p className="text-xs text-muted-foreground">Etki hesaplanıyor…</p>}
          {d && !d.allowed && (
            <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100"
                 data-section="mode-switch:blocked">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
              <div>
                <p>{d.blocker_message}</p>
                {d.blocker === "open_period" && (
                  <Link href={`/teacher/students/${studentId}/pool/session`} className="mt-1 inline-block font-semibold underline">
                    Seans ekranına git
                  </Link>
                )}
              </div>
            </div>
          )}
          {d && d.allowed && (
            <div className="space-y-3" data-section="mode-switch:effects">
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="rounded-md border p-2">
                  <p className="text-lg font-semibold text-foreground">{d.delete_tasks.length}</p>
                  <p className="text-xs text-muted-foreground">görev silinir (hiç dokunulmamış)</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="text-lg font-semibold text-foreground">{d.keep_partial.length}</p>
                  <p className="text-xs text-muted-foreground">görev kalır (kısmen çözülmüş)</p>
                </div>
                <div className="rounded-md border p-2">
                  <p className="text-lg font-semibold text-foreground">{d.release_tests + d.dead_reserve_tests}</p>
                  <p className="text-xs text-muted-foreground">test rezervi kitaba iade edilir</p>
                </div>
              </div>
              {d.delete_tasks.length > 0 && (
                <div>
                  <p className="flex items-center gap-1 text-xs font-semibold text-foreground"><Trash2 className="size-3.5" aria-hidden /> Silinecek görevler</p>
                  <TaskList rows={d.delete_tasks} tone="del" />
                </div>
              )}
              {d.keep_partial.length > 0 && (
                <div>
                  <p className="flex items-center gap-1 text-xs font-semibold text-foreground"><CheckCircle2 className="size-3.5" aria-hidden /> Kalacak görevler (çözülen kısım korunur, kalan rezervi iade edilir)</p>
                  <TaskList rows={d.keep_partial} tone="keep" />
                </div>
              )}
              {d.dead_reserve_tests > 0 && (
                <p className="text-xs text-muted-foreground">
                  Geçmişte verilip yapılmamış görevlerin {d.dead_reserve_tests} testlik rezervi de serbest bırakılır (görevler geçmişte durur).
                </p>
              )}
              {toMode === "gun_gun" && d.pool_leftover_items > 0 && (
                <p className="text-xs text-muted-foreground">
                  Son dönemde kalanı olan {d.pool_leftover_items} kalem ({d.pool_leftover_units} birim) havuzdan çıkar.
                </p>
              )}
              <ul className="list-disc space-y-0.5 pl-4 text-xs text-muted-foreground">
                {d.notes.map((n) => <li key={n}>{n}</li>)}
              </ul>
              {toMode === "havuz" && (
                <div className="rounded-md border p-3">
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={openFirst} onChange={(e) => setOpenFirst(e.target.checked)} />
                    <span className="font-medium text-foreground">İlk havuz dönemini geçiş günü aç</span>
                  </label>
                  {openFirst && (
                    <label className="mt-2 block">
                      <span className="text-xs text-muted-foreground">Beklenen sonraki seans</span>
                      <Input type="date" value={next} onChange={(e) => setNext(e.target.value)} className="mt-1 w-44" />
                    </label>
                  )}
                </div>
              )}
              <label className="block">
                <span className="text-xs text-muted-foreground">Not (isteğe bağlı, geçiş geçmişinde görünür)</span>
                <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} className="mt-1" />
              </label>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Vazgeç</Button>
          <Button onClick={submit} disabled={!d?.allowed || sw.isPending} data-testid="mode-switch-submit"
                  className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
            {toMode === "havuz" ? "Haftalık havuza geç" : "Gün gün programa geç"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Geçiş geçmişi — kayıt yoksa hiç çizilmez. */
export function ModeHistoryList({ studentId }: { studentId: number }) {
  const q = useQuery({ queryKey: modeSwitchKeys.history(studentId), queryFn: () => getModeHistory(studentId) });
  const items = q.data?.items ?? [];
  if (!items.length) return null;
  return (
    <div className="rounded-lg border bg-card p-4 text-sm" data-section="pool:mode-history">
      <h2 className="font-semibold text-foreground">Program modu geçişleri</h2>
      <ul className="mt-2 space-y-1.5">
        {items.map((c) => (
          <li key={c.id} className="flex flex-wrap items-baseline gap-x-2 text-xs">
            <span className="font-medium text-foreground">{fmt(c.effective_on)}</span>
            <span className="text-foreground">{c.from_label} → {c.to_label}</span>
            <span className="rounded bg-slate-600 px-1.5 text-[10px] font-semibold text-white">{c.trigger_label}</span>
            {c.changed_by_name && <span className="text-muted-foreground">· {c.changed_by_name}</span>}
            {(c.summary.deleted_tasks ?? 0) > 0 && <span className="text-muted-foreground">· {c.summary.deleted_tasks} görev silindi</span>}
            {((c.summary.released_tests ?? 0) + (c.summary.dead_reserve_released ?? 0)) > 0 && (
              <span className="text-muted-foreground">· {(c.summary.released_tests ?? 0) + (c.summary.dead_reserve_released ?? 0)} test iade</span>
            )}
            {(c.summary.pool_leftover_items ?? 0) > 0 && <span className="text-muted-foreground">· {c.summary.pool_leftover_items} kalem havuzdan çıktı</span>}
            {c.note && <span className="w-full break-words text-muted-foreground">“{c.note}”</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
