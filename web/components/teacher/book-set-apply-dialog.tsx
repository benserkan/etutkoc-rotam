"use client";

/**
 * Kitap setini birden çok öğrenciye uygula (2026-09-27, kurum toplu kurulumu 2/4).
 *
 * Aktif öğrenciler şubeye göre gruplu listelenir; setin hedef sınıfına uyan ve
 * setteki kitaplardan eksiği olan öğrenciler ön-seçili gelir. Uygula → her
 * öğrenciye setin tüm kitapları (zaten atalı olan atlanır, arşivli olan geri
 * açılır). Sınıf uyumsuzluğu engel değil, uyarı.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, UsersRound } from "lucide-react";

import { getBookSetApplyCandidates, libraryKeys } from "@/lib/api/library";
import { useApplyBookSet } from "@/lib/hooks/use-library-mutations";
import type { BookSetApplyCandidate } from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const NO_GROUP = "Şubesiz";

function defaultSelection(rows: BookSetApplyCandidate[]): Set<number> {
  return new Set(
    rows.filter((r) => r.fits_grade && r.already_count < r.set_book_count).map((r) => r.student_id),
  );
}

export function BookSetApplyDialog({ setId, setBookCount }: { setId: number; setBookCount: number }) {
  const [open, setOpen] = React.useState(false);
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="space-y-0.5">
          <h2 className="inline-flex items-center gap-2 text-base font-medium">
            <UsersRound className="size-4 text-muted-foreground" aria-hidden />
            Öğrencilere uygula
          </h2>
          <p className="text-xs text-muted-foreground">
            Setin {setBookCount} kitabını tek seferde birden çok öğrenciye ata —
            örneğin bir şubenin tamamına. Zaten atalı kitaplar atlanır.
          </p>
        </div>
        <Button
          type="button"
          onClick={() => setOpen(true)}
          disabled={setBookCount === 0}
          data-testid="open-set-apply"
        >
          Öğrenci seç ve uygula
        </Button>
      </CardContent>
      {open ? <ApplyDialog setId={setId} onClose={() => setOpen(false)} /> : null}
    </Card>
  );
}

function ApplyDialog({ setId, onClose }: { setId: number; onClose: () => void }) {
  const q = useQuery({
    queryKey: libraryKeys.bookSetApplyCandidates(setId),
    queryFn: () => getBookSetApplyCandidates(setId),
  });
  const mut = useApplyBookSet(setId);
  const rows = React.useMemo(() => q.data?.students ?? [], [q.data]);
  const [selected, setSelected] = React.useState<Set<number> | null>(null);
  const [group, setGroup] = React.useState<string>("all");
  const sel = selected ?? defaultSelection(rows);

  const groups = React.useMemo(() => {
    const m = new Map<string, BookSetApplyCandidate[]>();
    for (const r of rows) {
      const k = r.class_group || NO_GROUP;
      m.set(k, [...(m.get(k) ?? []), r]);
    }
    return Array.from(m.entries()).sort(([a], [b]) =>
      a === NO_GROUP ? 1 : b === NO_GROUP ? -1 : a.localeCompare(b, "tr", { numeric: true }),
    );
  }, [rows]);
  const visible = group === "all" ? groups : groups.filter(([k]) => k === group);

  function toggle(ids: number[], on: boolean) {
    const next = new Set(sel);
    for (const id of ids) {
      if (on) next.add(id);
      else next.delete(id);
    }
    setSelected(next);
  }

  function submit() {
    mut.mutate({ studentIds: Array.from(sel) }, { onSuccess: () => onClose() });
  }

  return (
    <Dialog open onOpenChange={(o) => (!o ? onClose() : null)}>
      <DialogContent className="flex max-h-[88vh] max-w-3xl flex-col gap-0 p-0">
        <DialogHeader className="border-b border-border p-4">
          <DialogTitle>
            {q.data ? `“${q.data.set_name}” setini uygula` : "Seti uygula"}
          </DialogTitle>
          <DialogDescription>
            Setin hedefi: {q.data?.grade_label ?? "…"}. Sınıfına uyan ve eksik
            kitabı olan öğrenciler seçili geldi; istediğini ekle/çıkar.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {q.isLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="size-4 animate-spin" aria-hidden /> Öğrenciler yükleniyor…
            </p>
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aktif öğrencin yok.</p>
          ) : (
            <>
              {groups.length > 1 ? (
                <label className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Şube:</span>
                  <select
                    value={group}
                    onChange={(e) => setGroup(e.target.value)}
                    className="rounded-md border border-input bg-background px-2 py-1 text-sm"
                    data-testid="set-apply-group"
                  >
                    <option value="all">Tüm şubeler ({rows.length})</option>
                    {groups.map(([k, list]) => (
                      <option key={k} value={k}>
                        {k} ({list.length})
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {visible.map(([k, list]) => {
                const ids = list.map((r) => r.student_id);
                const allOn = ids.every((id) => sel.has(id));
                return (
                  <section key={k} className="space-y-1.5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h3 className="text-sm font-semibold">
                        {k} <span className="font-normal text-muted-foreground">· {list.length} öğrenci</span>
                      </h3>
                      <button
                        type="button"
                        className="text-xs font-medium text-cyan-700 underline-offset-2 hover:underline dark:text-cyan-300"
                        onClick={() => toggle(ids, !allOn)}
                      >
                        {allOn ? "Bu şubeyi bırak" : "Bu şubenin tümünü seç"}
                      </button>
                    </div>
                    <ul className="divide-y divide-border rounded-md border border-border">
                      {list.map((r) => {
                        const full = r.already_count >= r.set_book_count && r.set_book_count > 0;
                        return (
                          <li key={r.student_id}>
                            <label
                              className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2"
                              data-testid="set-apply-row"
                            >
                              <input
                                type="checkbox"
                                checked={sel.has(r.student_id)}
                                onChange={(e) => toggle([r.student_id], e.target.checked)}
                                className="size-4"
                              />
                              <span className="font-medium break-words">{r.full_name}</span>
                              <span className="text-xs text-muted-foreground">{r.grade_label}</span>
                              {r.already_count > 0 ? (
                                <span className="text-xs text-muted-foreground">
                                  {full
                                    ? "setin tüm kitapları zaten atalı"
                                    : `${r.already_count}/${r.set_book_count} kitap zaten atalı`}
                                </span>
                              ) : null}
                              {!r.fits_grade ? (
                                <span className="rounded bg-amber-700 px-1.5 py-0.5 text-[11px] font-medium text-white">
                                  sınıfı setin hedefine uymuyor
                                </span>
                              ) : null}
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border p-4">
          <span className="text-sm text-muted-foreground">{sel.size} öğrenci seçili</span>
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button
              type="button"
              onClick={submit}
              disabled={sel.size === 0 || mut.isPending}
              data-testid="set-apply-submit"
            >
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {sel.size} öğrenciye uygula
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
