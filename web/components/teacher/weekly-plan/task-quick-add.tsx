"use client";

/**
 * Görev ekleme kutusu — 3 tık (P4, 2026-09-07).
 *
 * KOÇ GERİ BİLDİRİMİ: eski form ders → kitap → ünite → adet → Ekle zinciriyle
 * ~9 etkileşim istiyordu; kapasitesi dolan ünite de yolu tıkıyordu.
 *
 * TASARIM: koç "türev çalışsın" diye düşünür, "345'in 12. ünitesi" diye değil.
 * Bu yüzden arama birimi KONU, kaynaklar konunun altında. Her konunun altında
 * sabit "Kaynak belirtmeden ver" seçeneği var (P2) ve kapasitesi dolu bölüm
 * gizlenmez, işaretlenir (P1). Adet koçun kendi alışkanlığından gelir (P3).
 *
 * Tık sayımı: kutu (1) → satır (2) → Ekle (3).
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Loader2,
  Search,
  Sparkles,
  TriangleAlert,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getTaskPicker, teacherKeys } from "@/lib/api/teacher";
import { useCreateTask } from "@/lib/hooks/use-teacher-mutations";
import type {
  PickerSourceItem,
  PickerTopicItem,
  TaskPeriod,
  TaskPickerResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

/** Seçilen satır: konu + (varsa) kaynak. Kaynak yoksa kaynaksız görev. */
type Picked = {
  topic: PickerTopicItem;
  source: PickerSourceItem | null;
};

const BADGE_TONE: Record<string, string> = {
  sıradaki:
    "bg-cyan-50 text-cyan-800 border-cyan-200 dark:bg-cyan-500/10 dark:text-cyan-200 dark:border-cyan-500/30",
  zayıf:
    "bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-500/10 dark:text-amber-200 dark:border-amber-500/30",
  "son çalışılan":
    "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-500/10 dark:text-slate-300 dark:border-slate-500/30",
};

function Badge({ label }: { label: string }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-px text-[10px] font-medium whitespace-nowrap",
        BADGE_TONE[label] ??
          "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-500/10 dark:text-slate-300 dark:border-slate-500/30",
      )}
    >
      {label}
    </span>
  );
}

export function TaskQuickAdd({
  studentId,
  dayDate,
  period,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  period: TaskPeriod | null;
  onAfterAdd: () => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");
  const [debounced, setDebounced] = React.useState("");
  const [picked, setPicked] = React.useState<Picked | null>(null);
  const [count, setCount] = React.useState("");
  const create = useCreateTask(studentId);
  const boxRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  // Dışarı tıklama VE Escape ile kapanmalı. Escape'siz sürümde liste açık
  // kalıp altındaki kontrolleri örtüyordu (canlı tarayıcı testinde yakalandı):
  // koç klavyeyle çıkamıyordu.
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pickerQ = useQuery<TaskPickerResponse>({
    queryKey: teacherKeys.studentTaskPicker(studentId, debounced),
    queryFn: () => getTaskPicker(studentId, debounced),
    enabled: open,
    staleTime: 30_000,
  });

  function choose(topic: PickerTopicItem, source: PickerSourceItem | null) {
    setPicked({ topic, source });
    setCount(String(topic.quantity));
    setOpen(false);
    setQ("");
  }

  const overflow =
    picked?.source && Number(count) > 0
      ? Math.max(0, Number(count) - picked.source.remaining)
      : 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!picked) return;
    const n = Number(count);
    if (!Number.isFinite(n) || n < 1) return;
    const { topic, source } = picked;
    const title = source
      ? `${source.book_name} — ${source.section_label}: ${n} test`
      : `${topic.topic_name} — ${n} test`;
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "test",
          title,
          scheduled_hour: null,
          period,
          items: [
            source
              ? {
                  book_id: source.book_id,
                  section_id: source.section_id,
                  planned_count: n,
                  // Kapasite yetmiyorsa engel değil — koç uyarıyı görüyor (P1)
                  allow_over_capacity: overflow > 0,
                }
              : {
                  // Kaynaksız görev: kitap yok, konu var (P2)
                  book_id: null,
                  section_id: null,
                  topic_id: topic.topic_id,
                  label: topic.topic_name,
                  planned_count: n,
                },
          ],
        },
      },
      {
        onSuccess: () => {
          setPicked(null);
          setCount("");
          onAfterAdd();
        },
      },
    );
  }

  const groups = pickerQ.data?.groups ?? [];
  const empty = !pickerQ.isLoading && groups.length === 0;

  return (
    <div ref={boxRef} className="relative space-y-2">
      <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={picked && !open ? "" : q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            placeholder={
              picked ? "Başka bir şey ekle…" : "Ne çalışsın?  konu · kaynak"
            }
            className="pl-8"
            aria-label="Görev ara"
          />
        </div>
        <Input
          type="number"
          min={1}
          value={count}
          onChange={(e) => setCount(e.target.value)}
          disabled={!picked}
          className="w-16 text-right tabular-nums"
          aria-label="Adet"
        />
        <Button type="submit" size="sm" disabled={!picked || !count || create.isPending}>
          {create.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            "Ekle"
          )}
        </Button>
      </form>

      {/* Seçim özeti — koç ne eklediğini görsün */}
      {picked ? (
        <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-cyan-200 bg-cyan-50 px-2.5 py-1.5 text-[12px] text-cyan-900 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-100">
          <span className="font-medium">{picked.topic.topic_name}</span>
          <span className="text-cyan-700 dark:text-cyan-300">
            · {picked.topic.subject_name}
          </span>
          {picked.source ? (
            <span className="text-cyan-700 dark:text-cyan-300">
              · {picked.source.book_name}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-cyan-700 dark:text-cyan-300">
              <Zap className="h-3 w-3" /> kaynak belirtilmedi
            </span>
          )}
          <span className="ml-auto text-[11px] text-cyan-700 dark:text-cyan-300">
            {picked.topic.quantity_reason}
          </span>
        </div>
      ) : null}

      {overflow > 0 && picked?.source ? (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[12px] leading-snug text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Bu bölümde kayıtlı kapasite{" "}
            {picked.source.remaining === 0
              ? "kalmadı"
              : `${picked.source.remaining} test`}{" "}
            — <b>{overflow} test</b> aşılacak. Görev yine de oluşturulur.
          </span>
        </p>
      ) : null}

      {/* Aday listesi */}
      {open ? (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 max-h-[22rem] overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-lg">
          {pickerQ.isLoading ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
              yükleniyor…
            </p>
          ) : empty ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              Eşleşen konu yok. Farklı bir kelime deneyin.
            </p>
          ) : (
            groups.map((g) => (
              <div key={g.key} className="mb-1 last:mb-0">
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.label}
                </p>
                {g.items.map((it) => (
                  <div key={it.topic_id} className="mb-0.5">
                    <div className="flex items-center gap-1.5 px-2 py-1">
                      <span className="truncate text-[13px] font-medium text-foreground">
                        {it.topic_name}
                      </span>
                      <span className="truncate text-[11px] text-muted-foreground">
                        {it.subject_name}
                      </span>
                      {it.badge ? <Badge label={it.badge} /> : null}
                    </div>
                    {it.sources.map((s) => (
                      <button
                        key={s.section_id}
                        type="button"
                        onClick={() => choose(it, s)}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 pl-5 text-left text-[12px] hover:bg-accent"
                      >
                        <BookOpen className="h-3 w-3 shrink-0 text-muted-foreground" />
                        <span className="truncate text-foreground">
                          {s.book_name}
                          <span className="text-muted-foreground">
                            {" "}
                            · {s.section_label}
                          </span>
                        </span>
                        <span
                          className={cn(
                            "ml-auto whitespace-nowrap text-[11px] tabular-nums",
                            s.full
                              ? "text-amber-700 dark:text-amber-300"
                              : "text-muted-foreground",
                          )}
                        >
                          {s.full ? "kapasite doldu" : `${s.remaining} test kaldı`}
                        </span>
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => choose(it, null)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 pl-5 text-left text-[12px] text-muted-foreground hover:bg-accent"
                    >
                      <Zap className="h-3 w-3 shrink-0" />
                      Kaynak belirtmeden ver
                    </button>
                  </div>
                ))}
              </div>
            ))
          )}
          <p className="flex items-center gap-1.5 border-t border-border px-2 py-1.5 text-[10.5px] text-muted-foreground">
            <Sparkles className="h-3 w-3" />
            Adet, bu derste genelde verdiğin sayıdan gelir — değiştirebilirsin.
          </p>
        </div>
      ) : null}
    </div>
  );
}
