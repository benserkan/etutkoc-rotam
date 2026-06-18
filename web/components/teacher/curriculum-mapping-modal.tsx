"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles, Check, Wand2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { getBookMappingSuggestions, libraryKeys } from "@/lib/api/library";
import { useApplyMapping } from "@/lib/hooks/use-library-mutations";
import type { MappingSuggestionsResponse } from "@/lib/types/library";
import { cn } from "@/lib/utils";

/**
 * Müfredata eşleştir (Faz 0) — kitabın ünitelerini resmi konulara bağlar.
 *
 * Deterministik auto-map (anlık) + "Yapay zekâ ile öner" (Gemini semantik,
 * ücretsiz). Koç her satırda konuyu seçer/onaylar → uygula. Müfredat ilerleme
 * omurgasının ön şartı (eşleşmemiş üniteler haritada görünmez).
 */
export function CurriculumMappingModal({
  open,
  onOpenChange,
  bookId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  bookId: number;
}) {
  const [ai, setAi] = React.useState(false);
  const q = useQuery<MappingSuggestionsResponse>({
    queryKey: libraryKeys.mappingSuggestions(bookId, ai),
    queryFn: () => getBookMappingSuggestions(bookId, ai),
    enabled: open,
    staleTime: 30_000,
  });
  const applyMut = useApplyMapping(bookId);

  // section_id → seçili topic_id ("" = eşleme yok). Veri gelince/değişince türet.
  const [sel, setSel] = React.useState<Record<number, number | "">>({});
  const [seedKey, setSeedKey] = React.useState<string>("");
  const data = q.data;
  if (data) {
    const key = `${ai}:${data.rows.map((r) => r.section_id).join(",")}`;
    if (key !== seedKey) {
      setSeedKey(key);
      const next: Record<number, number | ""> = {};
      for (const r of data.rows) {
        next[r.section_id] = r.current_topic_id ?? r.suggested_topic_id ?? "";
      }
      setSel(next);
    }
  }

  const topics = data?.candidate_topics ?? [];

  function onApply() {
    if (!data) return;
    const items = data.rows
      .map((r) => ({ section_id: r.section_id, topic_id: sel[r.section_id] === "" ? null : Number(sel[r.section_id]) }))
      // yalnız değişenleri gönder
      .filter((it) => {
        const r = data.rows.find((x) => x.section_id === it.section_id)!;
        return it.topic_id !== (r.current_topic_id ?? null);
      });
    if (items.length === 0) {
      onOpenChange(false);
      return;
    }
    applyMut.mutate({ items }, { onSuccess: () => onOpenChange(false) });
  }

  const mapped = data ? data.mapped_count : 0;
  const total = data ? data.total_sections : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Müfredata eşleştir</DialogTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Kitap ünitelerini resmi müfredat konularına bağla. Eşleşmeyen üniteler
            müfredat ilerleme haritasında görünmez. Otomatik öneriler hazır; emin
            olmadıklarında <strong>“Yapay zekâ ile öner”</strong> dene.
          </p>
        </DialogHeader>

        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {q.isLoading ? "Yükleniyor…" : `${mapped}/${total} ünite eşli`}
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setAi(true)}
            disabled={ai && q.isFetching}
          >
            {ai && q.isFetching ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Wand2 className="size-3.5" aria-hidden />
            )}
            Yapay zekâ ile öner
          </Button>
        </div>

        <div className="max-h-[55vh] overflow-y-auto rounded-md border border-border">
          {q.isLoading ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
            </div>
          ) : !data || data.rows.length === 0 ? (
            <div className="p-6 text-center text-sm text-muted-foreground">
              Ünite yok.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Kitap ünitesi</th>
                  <th className="px-3 py-2 text-left font-medium">Resmi konu</th>
                  <th className="px-3 py-2 text-left font-medium">Kaynak</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows.map((r) => {
                  const suggested = r.source === "auto" || r.source === "ai";
                  return (
                    <tr key={r.section_id}>
                      <td className="px-3 py-2 align-top">
                        <span className="font-medium text-foreground">{r.label}</span>
                      </td>
                      <td className="px-3 py-2 align-top">
                        <select
                          value={sel[r.section_id] === undefined ? "" : String(sel[r.section_id])}
                          onChange={(e) =>
                            setSel((p) => ({
                              ...p,
                              [r.section_id]: e.target.value === "" ? "" : Number(e.target.value),
                            }))
                          }
                          className={cn(
                            "w-full rounded-md border border-input bg-background px-2 py-1 text-sm",
                            suggested && sel[r.section_id] === r.suggested_topic_id &&
                              "border-amber-400 bg-amber-50",
                          )}
                        >
                          <option value="">— eşleşmemiş —</option>
                          {topics.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.name}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-2 align-top">
                        {r.source === "mapped" ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700">
                            <Check className="size-3" aria-hidden /> eşli
                          </span>
                        ) : r.source === "auto" ? (
                          <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-medium text-sky-800">
                            otomatik
                          </span>
                        ) : r.source === "ai" ? (
                          <span className="inline-flex items-center gap-1 rounded bg-violet-100 px-1.5 py-0.5 text-[10px] font-medium text-violet-800">
                            <Sparkles className="size-2.5" aria-hidden /> AI
                            {r.confidence ? ` · ${r.confidence}` : ""}
                          </span>
                        ) : (
                          <span className="text-[10px] text-muted-foreground">öneri yok</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Vazgeç
          </Button>
          <Button
            onClick={onApply}
            disabled={applyMut.isPending || q.isLoading}
            className="bg-indigo-600 text-white hover:bg-indigo-700"
          >
            {applyMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Check className="size-4" aria-hidden />
            )}
            Uygula
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
