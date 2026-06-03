"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Archive,
  Boxes,
  Check,
  ChevronDown,
  Loader2,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { getTeacherWorkBlocks, teacherKeys } from "@/lib/api/teacher";
import {
  useArchiveWorkBlock,
  useCreateWorkBlock,
  useDeleteWorkBlock,
  useUpdateWorkBlock,
} from "@/lib/hooks/use-teacher-mutations";
import type { WorkBlock, WorkBlockListResponse } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const UNITS = ["test", "soru", "deneme"] as const;

/**
 * Serbest İş Blokları (Katman 3) — sistem-DIŞI kaynak sayacı.
 *
 * Koç birbirine bağlı bir iş yığını tanımlar (ör. "Özel Ders Mat — 10 test");
 * günlere görev dağıttıkça "dağıtılan / kalan" burada görünür. Böylece geçmiş
 * günlere dönüp elle saymak gerekmez. Kaynak Durumu'nun (sistem kitapları)
 * üstünde durur.
 */
export function WorkBlockPanel({ studentId }: { studentId: number }) {
  const q = useQuery<WorkBlockListResponse>({
    queryKey: teacherKeys.studentWorkBlocks(studentId),
    queryFn: () => getTeacherWorkBlocks(studentId),
    staleTime: 30_000,
  });
  const [showNew, setShowNew] = React.useState(false);
  const blocks = q.data?.items ?? [];

  return (
    <div className="border-b border-border">
      <div className="px-4 py-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-foreground flex items-center gap-1.5">
            <Boxes className="size-4 text-muted-foreground" aria-hidden />
            Serbest Bloklar
          </p>
          <p className="text-xs text-muted-foreground">
            Sistemde olmayan kaynak (özel ders / ödev) — dağıtılan / kalan
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowNew((v) => !v)}
          className="flex-shrink-0 inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-foreground hover:bg-muted/50 transition"
        >
          {showNew ? <X className="size-3" aria-hidden /> : <Plus className="size-3" aria-hidden />}
          {showNew ? "Vazgeç" : "Yeni"}
        </button>
      </div>

      {showNew ? (
        <NewBlockForm studentId={studentId} onDone={() => setShowNew(false)} />
      ) : null}

      <div className="px-4 pb-3 space-y-2">
        {q.isLoading && !q.data ? (
          <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
            <Loader2 className="size-3.5 animate-spin" aria-hidden /> Yükleniyor…
          </div>
        ) : blocks.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-1">
            Henüz blok yok. Birbirine bağlı testleri (örn. özel ders 10 test) tek
            yerden takip etmek için “Yeni” ile oluştur.
          </p>
        ) : (
          blocks.map((b) => (
            <BlockCard key={b.id} block={b} studentId={studentId} />
          ))
        )}
      </div>
    </div>
  );
}

function NewBlockForm({
  studentId,
  onDone,
}: {
  studentId: number;
  onDone: () => void;
}) {
  const create = useCreateWorkBlock(studentId);
  const [title, setTitle] = React.useState("");
  const [total, setTotal] = React.useState("");
  const [unit, setUnit] = React.useState<string>("test");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const t = title.trim();
    const n = Number(total);
    if (!t || !Number.isFinite(n) || n < 1) return;
    create.mutate(
      { body: { title: t, total_count: n, unit } },
      {
        onSuccess: () => {
          setTitle("");
          setTotal("");
          onDone();
        },
      },
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="mx-4 mb-3 rounded-lg border border-border bg-muted/30 p-3 space-y-2"
    >
      <input
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        maxLength={200}
        placeholder="Blok adı — örn. Özel Ders Mat ödevi"
        className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />
      <div className="flex gap-2">
        <input
          type="number"
          min={1}
          value={total}
          onChange={(e) => setTotal(e.target.value)}
          placeholder="toplam"
          className="w-24 px-2.5 py-1.5 border border-input bg-background rounded-md text-sm text-right tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          className="px-2 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {UNITS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
        <button
          type="submit"
          disabled={create.isPending || !title.trim() || !total}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-40 transition"
        >
          {create.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Plus className="size-3.5" aria-hidden />
          )}
          Oluştur
        </button>
      </div>
    </form>
  );
}

function BlockCard({
  block,
  studentId,
}: {
  block: WorkBlock;
  studentId: number;
}) {
  const update = useUpdateWorkBlock(studentId);
  const archive = useArchiveWorkBlock(studentId);
  const del = useDeleteWorkBlock(studentId);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [editTotal, setEditTotal] = React.useState(false);
  const [totalDraft, setTotalDraft] = React.useState(String(block.total_count));

  const pctDist =
    block.total_count > 0
      ? Math.min(100, Math.round((100 * block.distributed) / block.total_count))
      : 0;
  const full = block.remaining <= 0;

  function saveTotal() {
    const n = Number(totalDraft);
    if (!Number.isFinite(n) || n < 1) {
      setTotalDraft(String(block.total_count));
      setEditTotal(false);
      return;
    }
    update.mutate(
      { blockId: block.id, body: { total_count: n } },
      { onSettled: () => setEditTotal(false) },
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card p-2.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-foreground leading-tight truncate">
            {block.title}
          </p>
          {block.subject_name ? (
            <span className="text-[10px] text-muted-foreground">
              {block.subject_name}
            </span>
          ) : null}
        </div>
        <div className="relative flex-shrink-0">
          <button
            type="button"
            onClick={() => setMenuOpen((v) => !v)}
            className="text-muted-foreground hover:text-foreground p-0.5"
            aria-label="Blok işlemleri"
          >
            <ChevronDown className="size-4" aria-hidden />
          </button>
          {menuOpen ? (
            <div className="absolute right-0 top-6 z-20 w-36 rounded-md border border-border bg-popover shadow-md py-1 text-sm">
              <button
                type="button"
                onClick={() => {
                  setEditTotal(true);
                  setMenuOpen(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-muted/60 text-foreground"
              >
                Toplamı düzelt
              </button>
              <button
                type="button"
                onClick={() => {
                  archive.mutate({ blockId: block.id });
                  setMenuOpen(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-muted/60 text-foreground inline-flex items-center gap-2"
              >
                <Archive className="size-3.5" aria-hidden /> Arşivle
              </button>
              <button
                type="button"
                onClick={() => {
                  if (
                    window.confirm(
                      `"${block.title}" bloğu silinsin mi? Bağlı görevler kalır, sadece blok bağı kopar.`,
                    )
                  ) {
                    del.mutate({ blockId: block.id });
                  }
                  setMenuOpen(false);
                }}
                className="w-full text-left px-3 py-1.5 hover:bg-rose-50 dark:hover:bg-rose-950/30 text-rose-700 dark:text-rose-300 inline-flex items-center gap-2"
              >
                <Trash2 className="size-3.5" aria-hidden /> Sil
              </button>
            </div>
          ) : null}
        </div>
      </div>

      {/* İlerleme: dağıtılan / toplam */}
      <div className="mt-2 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn("h-full", full ? "bg-emerald-500" : "bg-indigo-500")}
          style={{ width: `${pctDist}%` }}
        />
      </div>
      <div className="mt-1 flex items-center justify-between text-[11px] tabular-nums">
        <span className="text-muted-foreground">
          Dağıtılan <b className="text-foreground">{block.distributed}</b> /{" "}
          {editTotal ? (
            <input
              type="number"
              min={1}
              value={totalDraft}
              autoFocus
              onChange={(e) => setTotalDraft(e.target.value)}
              onBlur={saveTotal}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveTotal();
                if (e.key === "Escape") {
                  setTotalDraft(String(block.total_count));
                  setEditTotal(false);
                }
              }}
              className="w-12 px-1 py-0.5 border border-input bg-background rounded text-right"
            />
          ) : (
            <b className="text-foreground">{block.total_count}</b>
          )}{" "}
          {block.unit}
        </span>
        {full ? (
          <span className="inline-flex items-center gap-0.5 text-emerald-600 dark:text-emerald-400 font-medium">
            <Check className="size-3" aria-hidden /> tamamı dağıtıldı
          </span>
        ) : (
          <span className="font-medium text-foreground">
            kalan {block.remaining} {block.unit}
          </span>
        )}
      </div>
      {block.task_count > 0 ? (
        <p className="mt-0.5 text-[10px] text-muted-foreground">
          {block.task_count} göreve dağıtıldı · çözülen {block.completed}
        </p>
      ) : null}
    </div>
  );
}
