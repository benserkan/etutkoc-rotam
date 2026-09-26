"use client";

/**
 * Konuyu günlere yay — önizleme penceresi (İskelet F2-3, 2026-09-26).
 *
 * Koç: "dershanede işlenen konunun kalan testlerini programda boşluk nerede ise
 * oraya koyuyorum" → tahmin değil HESAP. Önizleme gün gün kaynak + adet gösterir;
 * koç günü çıkarır, adedi değiştirir, tek tıkla yazar (ileri tarih taslak).
 *
 * Kurallar sunucuda (services/topic_spread): birim KONU (kitap yetmezse aynı
 * konudaki başka kitaptan tamamlanır) · ÇAPAYA ÖNCELİK (günün dershane dersinin
 * payı önceden ayrılır) · bir sonraki aynı dersin çapa gününden önce biter.
 *
 * Pencere sağlayıcıda yaşar: hayalet satırı kabul edilince DOM'dan kalkar,
 * pencere onunla birlikte kaybolmasın.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarRange, Loader2, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  dayLabel,
  getSpreadPreview,
  type SpreadParams,
  type SpreadPreview,
  useApplySpread,
} from "@/lib/api/weekly-skeleton";
import { cn } from "@/lib/utils";

type Ctx = { open: (p: SpreadParams) => void };
const SpreadContext = React.createContext<Ctx | null>(null);

/** Hayalet satırlarından çağrılır; sağlayıcı yoksa (başka sayfa) sessizce yok sayılır. */
export function useTopicSpread(): Ctx {
  return React.useContext(SpreadContext) ?? { open: () => {} };
}

export function TopicSpreadProvider({
  studentId,
  children,
}: {
  studentId: number;
  children: React.ReactNode;
}) {
  const [params, setParams] = React.useState<SpreadParams | null>(null);
  const ctx = React.useMemo<Ctx>(() => ({ open: (p) => setParams(p) }), []);
  return (
    <SpreadContext.Provider value={ctx}>
      {children}
      {params ? (
        <SpreadDialog
          key={`${params.topicId}-${params.sectionId}-${params.start}`}
          studentId={studentId}
          initial={params}
          onClose={() => setParams(null)}
        />
      ) : null}
    </SpreadContext.Provider>
  );
}

type Draft = { include: boolean; counts: Record<number, number> };

function SpreadDialog({
  studentId,
  initial,
  onClose,
}: {
  studentId: number;
  initial: SpreadParams;
  onClose: () => void;
}) {
  const [perDay, setPerDay] = React.useState(initial.perDay);
  const q = useQuery<SpreadPreview>({
    queryKey: [
      "teacher", "me", "students", String(studentId), "skeleton", "spread",
      initial.topicId ?? 0, initial.sectionId ?? 0, initial.start, perDay,
    ],
    queryFn: () =>
      getSpreadPreview(studentId, {
        topicId: initial.topicId,
        sectionId: initial.sectionId,
        start: initial.start,
        perDay,
      }),
  });
  const apply = useApplySpread(studentId);

  // Önizleme değişince taslağı yeniden kur (render sırasında türetme)
  const stamp = q.data ? JSON.stringify(q.data.days.map((d) => [d.date, d.items])) : null;
  const [lastStamp, setLastStamp] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState<Record<string, Draft>>({});
  if (stamp !== lastStamp) {
    setLastStamp(stamp);
    const next: Record<string, Draft> = {};
    for (const d of q.data?.days ?? []) {
      next[d.date] = {
        include: true,
        counts: Object.fromEntries(d.items.map((it) => [it.section_id, it.count])),
      };
    }
    setDraft(next);
  }

  const data = q.data;
  const chosen = (data?.days ?? []).filter((d) => draft[d.date]?.include);
  const total = chosen.reduce(
    (a, d) => a + d.items.reduce((b, it) => b + (draft[d.date]?.counts[it.section_id] ?? 0), 0),
    0,
  );

  function submit() {
    apply.mutate(
      {
        days: chosen.map((d) => ({
          date: d.date,
          items: d.items
            .map((it) => ({ section_id: it.section_id, count: draft[d.date]?.counts[it.section_id] ?? 0 }))
            .filter((it) => it.count > 0),
        })).filter((d) => d.items.length > 0),
      },
      { onSuccess: onClose },
    );
  }

  return (
    <Dialog open onOpenChange={(v) => (!v ? onClose() : null)}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="spread-dialog">
        <DialogHeader>
          <DialogTitle>Konuyu yay: {initial.title}</DialogTitle>
          <DialogDescription>
            Kalan testler boş günlere dağıtılır. Önce günün dershane/okul dersinin payı
            ayrılır; aynı konu kitapta yetmezse başka kaynaktan tamamlanır. Günleri
            çıkarabilir, adetleri değiştirebilirsin.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-foreground">
          <label className="inline-flex items-center gap-1.5">
            Günde
            <input
              type="number"
              min={1}
              max={20}
              value={perDay}
              onChange={(e) => setPerDay(Math.max(1, Number(e.target.value) || 1))}
              className="w-16 rounded border border-border bg-background px-1.5 py-1 text-[12.5px] text-foreground"
              aria-label="Günlük adet"
            />
            test
          </label>
          {data ? (
            <span className="text-muted-foreground">
              Kalan {data.total_remaining} test
              {data.stop_reason ? ` · ${data.stop_reason}` : ""}
            </span>
          ) : null}
        </div>

        {q.isLoading || !data ? (
          <div className="py-6 text-center">
            <Loader2 className="mx-auto size-4 animate-spin" aria-hidden />
          </div>
        ) : (
          <div className="space-y-2">
            {data.days.length === 0 ? (
              <p className="rounded-md border border-border px-3 py-2 text-[12.5px] text-muted-foreground">
                {data.total_remaining === 0
                  ? "Bu konunun kalan testi yok."
                  : "Uygun boş gün bulunamadı — adedi düşürmeyi ya da gün kapasitelerini iskelet penceresinden artırmayı dene."}
              </p>
            ) : null}
            <ul className="space-y-1.5">
              {data.days.map((d) => {
                const dr = draft[d.date];
                return (
                  <li
                    key={d.date}
                    data-testid="spread-day"
                    className={cn(
                      "rounded-md border px-2.5 py-2",
                      dr?.include ? "border-cyan-600/50 bg-cyan-500/[0.04]" : "border-border opacity-60",
                    )}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-foreground">
                        <input
                          type="checkbox"
                          checked={!!dr?.include}
                          onChange={(e) =>
                            setDraft((p) => ({ ...p, [d.date]: { ...p[d.date], include: e.target.checked } }))
                          }
                        />
                        {dayLabel(d.date)}
                      </label>
                      <span className="text-[11.5px] text-muted-foreground">
                        {d.capacity == null
                          ? "kapasite bilinmiyor"
                          : `kapasite ${d.capacity} · yazılı ${d.planned}${d.anchor_reserve ? ` · dershane payı ${d.anchor_reserve}` : ""} · boş ${d.free}`}
                      </span>
                    </div>
                    <ul className="mt-1 space-y-1 pl-6">
                      {d.items.map((it) => (
                        <li key={it.section_id} className="flex flex-wrap items-center gap-2 text-[12.5px] text-foreground">
                          <input
                            type="number"
                            min={0}
                            max={50}
                            value={dr?.counts[it.section_id] ?? it.count}
                            disabled={!dr?.include}
                            onChange={(e) =>
                              setDraft((p) => ({
                                ...p,
                                [d.date]: {
                                  ...p[d.date],
                                  counts: { ...p[d.date].counts, [it.section_id]: Math.max(0, Number(e.target.value) || 0) },
                                },
                              }))
                            }
                            className="w-14 rounded border border-border bg-background px-1.5 py-0.5 text-[12.5px] text-foreground"
                            aria-label={`${it.book_name} adet`}
                          />
                          <span>test</span>
                          <span className="font-medium">{it.book_name}</span>
                          <span className="text-muted-foreground">— {it.section_label}</span>
                        </li>
                      ))}
                    </ul>
                  </li>
                );
              })}
            </ul>
            {data.leftover > 0 ? (
              <p className="flex items-start gap-1.5 rounded-md border border-amber-600/50 bg-amber-500/10 px-2.5 py-1.5 text-[12.5px] text-amber-900 dark:text-amber-200" data-testid="spread-leftover">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                {data.leftover} test sığmadı
                {data.window_end ? ` (${dayLabel(data.window_end)} gününe kadar)` : ""} — günlük adedi
                artırabilir ya da kalanı sonra elle verebilirsin.
              </p>
            ) : null}
            {data.skipped.length > 0 ? (
              <details className="text-[12px] text-muted-foreground">
                <summary className="cursor-pointer">Atlanan günler ({data.skipped.length})</summary>
                <ul className="mt-1 space-y-0.5 pl-4">
                  {data.skipped.map((s) => (
                    <li key={s.date}>
                      {dayLabel(s.date)}: {s.reason}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button type="button" onClick={submit} disabled={apply.isPending || total === 0}>
            {apply.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <CalendarRange className="size-3.5" aria-hidden />
            )}
            {chosen.length} güne {total} test yaz
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
