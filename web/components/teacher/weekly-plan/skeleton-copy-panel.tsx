"use client";

/**
 * İskeleti başka öğrencilere kopyala (2026-09-27, kurum toplu kurulumu 3/4).
 *
 * Dönem şeridinin içinde açılır. Kaynak = seçili dönemin KAYDEDİLMİŞ hâli.
 * Hedefler şubeye göre gruplu; eksik kitaplar satırda yazılır ("atansın" kutusu
 * açıksa öğrenciye atanır, kapalıysa o satır kitapsız kopyalanır). Gün
 * kapasiteleri kopyalanmaz — her öğrencinin kendi geçmişinden öğrenilir.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import {
  getSkeletonCopyCandidates,
  skeletonCopyKey,
  useCopySkeleton,
  type SkeletonCopyCandidate,
} from "@/lib/api/weekly-skeleton";
import { Button } from "@/components/ui/button";

const NO_GROUP = "Şubesiz";

export function SkeletonCopyPanel({
  studentId,
  skeletonId,
  sourceName,
  defaultStart,
  dirty,
  onDone,
}: {
  studentId: number;
  skeletonId: number;
  sourceName: string;
  defaultStart: string;
  dirty: boolean;
  onDone: () => void;
}) {
  const q = useQuery({
    queryKey: skeletonCopyKey(studentId, skeletonId),
    queryFn: () => getSkeletonCopyCandidates(studentId, skeletonId),
  });
  const copy = useCopySkeleton(studentId);
  const [mode, setMode] = React.useState<"new" | "replace">("new");
  const [start, setStart] = React.useState(defaultStart);
  const [name, setName] = React.useState(sourceName);
  const [assign, setAssign] = React.useState(true);
  const [sel, setSel] = React.useState<Set<number>>(new Set());

  const rows = React.useMemo(() => q.data?.candidates ?? [], [q.data]);
  const groups = React.useMemo(() => {
    const m = new Map<string, SkeletonCopyCandidate[]>();
    for (const r of rows) {
      const k = r.class_group || NO_GROUP;
      m.set(k, [...(m.get(k) ?? []), r]);
    }
    return Array.from(m.entries()).sort(([a], [b]) =>
      a === NO_GROUP ? 1 : b === NO_GROUP ? -1 : a.localeCompare(b, "tr", { numeric: true }),
    );
  }, [rows]);

  function toggle(ids: number[], on: boolean) {
    const next = new Set(sel);
    for (const id of ids) {
      if (on) next.add(id);
      else next.delete(id);
    }
    setSel(next);
  }

  function effect(r: SkeletonCopyCandidate): string {
    if (mode === "new") {
      return r.period_starts.includes(start)
        ? "aynı tarihte başlayan dönemi var — onun satırları değişir"
        : "yeni dönem açılır, eski dönemleri korunur";
    }
    return r.current_period_name
      ? `“${r.current_period_name}” (${r.current_slot_count} satır) değişir`
      : "iskeleti yok — ilk dönemi açılır";
  }

  function submit() {
    copy.mutate(
      {
        skeleton_id: skeletonId,
        target_ids: Array.from(sel),
        mode,
        valid_from: mode === "new" ? start : null,
        name: mode === "new" ? name : null,
        assign_missing_books: assign,
      },
      { onSuccess: () => onDone() },
    );
  }

  return (
    <div className="space-y-3 rounded-md border border-border bg-background p-3" data-testid="skeleton-copy-panel">
      <p className="text-[12.5px] text-muted-foreground">
        <span className="font-semibold text-foreground">“{sourceName}”</span> dönemi
        {q.data ? ` (${q.data.source_slot_count} satır)` : ""} seçtiğin öğrencilere
        kopyalanır. Öneriler her öğrencide kendi ilerlemesinden hesaplanır; gün
        kapasiteleri kopyalanmaz.
      </p>
      {dirty ? (
        <p className="rounded bg-amber-600 px-2 py-1 text-[12px] font-medium text-white">
          Kaydedilmemiş değişiklik var — kopyalanan, dönemin KAYITLI hâlidir. Önce kaydet.
        </p>
      ) : null}

      <div className="flex flex-wrap items-end gap-3 text-[13px]">
        <fieldset className="flex flex-wrap gap-3">
          <label className="inline-flex items-center gap-1.5">
            <input type="radio" checked={mode === "new"} onChange={() => setMode("new")} />
            Yeni dönem olarak
          </label>
          <label className="inline-flex items-center gap-1.5">
            <input type="radio" checked={mode === "replace"} onChange={() => setMode("replace")} />
            Bugünkü dönemlerinin yerine
          </label>
        </fieldset>
        {mode === "new" ? (
          <>
            <label className="flex flex-col gap-0.5">
              <span className="text-[11.5px] text-muted-foreground">Başlangıç</span>
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="rounded-md border border-input bg-background px-2 py-1"
              />
            </label>
            <label className="flex flex-col gap-0.5">
              <span className="text-[11.5px] text-muted-foreground">Dönem adı</span>
              <input
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
                className="rounded-md border border-input bg-background px-2 py-1"
              />
            </label>
          </>
        ) : null}
        <label className="inline-flex items-center gap-1.5">
          <input type="checkbox" checked={assign} onChange={(e) => setAssign(e.target.checked)} />
          Eksik kitapları öğrenciye ata
        </label>
      </div>

      {q.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Öğrenciler yükleniyor…
        </p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Kopyalanacak başka aktif öğrencin yok.</p>
      ) : (
        <div className="max-h-80 space-y-3 overflow-y-auto pr-1">
          {groups.map(([k, list]) => {
            const ids = list.map((r) => r.student_id);
            const allOn = ids.every((id) => sel.has(id));
            return (
              <section key={k} className="space-y-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-[13px] font-semibold">
                    {k} <span className="font-normal text-muted-foreground">· {list.length}</span>
                  </h4>
                  <button
                    type="button"
                    className="text-[12px] font-medium text-cyan-800 hover:underline dark:text-cyan-300"
                    onClick={() => toggle(ids, !allOn)}
                  >
                    {allOn ? "Bu şubeyi bırak" : "Bu şubenin tümünü seç"}
                  </button>
                </div>
                <ul className="divide-y divide-border rounded-md border border-border">
                  {list.map((r) => (
                    <li key={r.student_id}>
                      <label className="flex cursor-pointer items-start gap-2 px-2.5 py-1.5" data-testid="skeleton-copy-row">
                        <input
                          type="checkbox"
                          className="mt-1 size-4"
                          checked={sel.has(r.student_id)}
                          onChange={(e) => toggle([r.student_id], e.target.checked)}
                        />
                        <span className="min-w-0 flex-1 text-[13px]">
                          <span className="font-medium break-words">{r.full_name}</span>{" "}
                          <span className="text-muted-foreground">· {r.grade_label}</span>
                          <span className="block text-[12px] text-muted-foreground">{effect(r)}</span>
                          {r.missing_books.length > 0 ? (
                            <span className="block text-[12px] text-amber-800 dark:text-amber-300 break-words">
                              {assign ? "Atanacak kitap: " : "Kitapsız kopyalanacak: "}
                              {r.missing_books.map((b) => b.name).join(", ")}
                            </span>
                          ) : null}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <span className="mr-auto text-[12.5px] text-muted-foreground">{sel.size} öğrenci seçili</span>
        <Button type="button" variant="ghost" size="sm" onClick={onDone} disabled={copy.isPending}>
          Vazgeç
        </Button>
        <Button
          type="button"
          size="sm"
          onClick={submit}
          disabled={sel.size === 0 || copy.isPending || (mode === "new" && !start)}
          data-testid="skeleton-copy-submit"
        >
          {copy.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
          {sel.size} öğrenciye kopyala
        </Button>
      </div>
    </div>
  );
}
