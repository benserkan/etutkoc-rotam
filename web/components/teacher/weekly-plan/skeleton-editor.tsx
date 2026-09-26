"use client";

/**
 * Haftalık İskelet düzenleyicisi (F1b).
 *
 * İskelet TARİHE değil HAFTA GÜNÜNE bağlı: "Pazartesi sabah Matematik"
 * satırı her haftanın Pazartesi'sine hayalet olarak düşer (Perşembe–Çarşamba
 * programında da sorunsuz). "Bu haftayı iskelet yap" mevcut haftanın
 * görevlerinden satırları çıkarır; koç burada düzeltir.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarRange, Copy, Loader2, Pencil, Plus, Trash2, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  ROUTINE_MODE_LABELS,
  type RoutineMode,
  getSkeleton,
  getSkeletonAcceptance,
  fmtDay,
  periodRange,
  type SkeletonTerm,
  useCreatePeriod,
  useUpdatePeriod,
  type GhostAcceptanceReport,
  type SkeletonPeriod,
  type SkeletonResponse,
  type SkeletonSlotIn,
  skeletonKeys,
  useDeleteSkeleton,
  useSaveSkeleton,
  useSkeletonFromWeek,
  WEEKDAY_LABELS,
} from "@/lib/api/weekly-skeleton";

type Row = SkeletonSlotIn & { key: string };

let _seq = 0;
const nextKey = () => `r${++_seq}`;

function toRows(sk: SkeletonResponse | undefined): Row[] {
  return (sk?.slots ?? []).map((s) => ({
    key: nextKey(),
    weekday: s.weekday,
    period: s.period,
    subject_id: s.subject_id,
    position: s.position,
    is_routine: s.is_routine,
    default_count: s.default_count,
    book_id: s.book_id ?? null,
    label: s.label ?? null,
    routine_mode: s.routine_mode ?? null,
  }));
}

export function SkeletonEditorDialog({
  studentId,
  open,
  onOpenChange,
  weekStart,
  weekEnd,
}: {
  studentId: number;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  weekStart: string;
  weekEnd: string;
}) {
  // F2-2: düzenlenen dönem (null = bugün geçerli dönem)
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const q = useQuery<SkeletonResponse>({
    queryKey: skeletonKeys.skeleton(studentId, selectedId),
    queryFn: () => getSkeleton(studentId, selectedId),
    enabled: open,
  });
  const accQ = useQuery<GhostAcceptanceReport>({
    queryKey: skeletonKeys.acceptance(30),
    queryFn: () => getSkeletonAcceptance(30),
    enabled: open,
    // Pencere her açılışta taze: hayalet kabul/kaldırma bu anahtarı bayatlatmaz
    staleTime: 0,
    refetchOnMount: "always",
  });
  const save = useSaveSkeleton(studentId);
  const fromWeek = useSkeletonFromWeek(studentId);
  const del = useDeleteSkeleton(studentId);

  const [rows, setRows] = React.useState<Row[] | null>(null);
  // Sunucu verisi değişince (ilk yükleme / "bu haftadan" sonrası) taslağı
  // yeniden kur — render sırasında türetme (effect'te setState yok).
  const dataStamp = q.data
    ? `${q.data.id ?? "yok"}:${JSON.stringify(q.data.slots.map((s) => s.id))}`
    : null;
  const [lastStamp, setLastStamp] = React.useState<string | null>(null);
  if (dataStamp !== lastStamp) {
    setLastStamp(dataStamp);
    setRows(q.data ? toRows(q.data) : null);
  }

  const subjects = q.data?.subjects ?? [];
  const books = q.data?.books ?? [];
  const list = rows ?? [];

  function update(key: string, patch: Partial<Row>) {
    setRows((prev) => (prev ?? []).map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }
  function remove(key: string) {
    setRows((prev) => (prev ?? []).filter((r) => r.key !== key));
  }
  function add(weekday: number) {
    const first = subjects[0];
    if (!first) return;
    setRows((prev) => [
      ...(prev ?? []),
      {
        key: nextKey(),
        weekday,
        period: null,
        subject_id: first.id,
        position: (prev ?? []).filter((r) => r.weekday === weekday).length,
        is_routine: false,
        default_count: null,
        book_id: null,
        label: null,
        routine_mode: null,
      },
    ]);
  }

  function submit() {
    const slots: SkeletonSlotIn[] = list.map((r, i) => ({
      weekday: r.weekday,
      period: r.period,
      subject_id: r.subject_id,
      position: i,
      is_routine: r.is_routine,
      default_count: r.default_count,
      book_id: r.book_id ?? null,
      label: r.book_id ? null : (r.label?.trim() || null),
      routine_mode: r.is_routine && r.book_id ? (r.routine_mode ?? "sirali") : null,
    }));
    save.mutate(
      { skeleton_id: q.data?.id ?? null, slots },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  const exists = q.data?.exists ?? false;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Haftalık iskelet</DialogTitle>
          <DialogDescription>
            Her hafta tekrar eden ders yerleşimi. Satırı dolmamış güne kesikli
            &ldquo;öneri&rdquo; düşer; öneri görev değildir, kaynak ayırmaz — tıklayıp konusunu
            seçince görev olur. Rutin satırlar (paragraf, problem) gün kartında tek
            tuşla onaylanabilir.
          </DialogDescription>
        </DialogHeader>

        <PeriodStrip
          studentId={studentId}
          periods={q.data?.periods ?? []}
          activeId={q.data?.id ?? null}
          weekStart={weekStart}
          weekEnd={weekEnd}
          onSelect={setSelectedId}
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={fromWeek.isPending}
            onClick={() => {
              if (
                exists &&
                !window.confirm(
                  `"${q.data?.name ?? "Bu dönem"}" satırları bu haftanın görevleriyle değiştirilsin mi? (Yeni bir dönem başlatmak için yukarıdaki "Yeni dönem"i kullan.)`,
                )
              ) {
                return;
              }
              fromWeek.mutate({
                start: weekStart,
                end: weekEnd,
                mode: "replace",
                skeleton_id: q.data?.id ?? null,
              });
            }}
          >
            {fromWeek.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Wand2 className="size-3.5" aria-hidden />
            )}
            Bu haftayı iskelet yap
          </Button>
          <span className="text-[12px] text-muted-foreground">
            Görüntülenen haftanın görevlerinden gün + periyot + ders satırları çıkarılır.
          </span>
        </div>

        <AcceptanceLine report={accQ.data} />

        {q.isLoading || rows == null ? (
          <div className="py-6 text-center text-sm text-muted-foreground">
            <Loader2 className="mx-auto size-4 animate-spin" aria-hidden />
          </div>
        ) : (
          <div className="space-y-3">
            {WEEKDAY_LABELS.map((label, wd) => {
              const dayRows = list.filter((r) => r.weekday === wd);
              return (
                <div key={wd} className="rounded-md border border-border" data-testid="skeleton-day">
                  <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-3 py-1.5">
                    <span className="text-[13px] font-semibold text-foreground">{label}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {dayRows.length} satır
                    </span>
                    <button
                      type="button"
                      onClick={() => add(wd)}
                      disabled={subjects.length === 0}
                      className="ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] text-cyan-800 hover:bg-cyan-500/10 dark:text-cyan-300"
                    >
                      <Plus className="size-3" aria-hidden /> Satır ekle
                    </button>
                  </div>
                  {dayRows.length === 0 ? (
                    <p className="px-3 py-2 text-[12px] italic text-muted-foreground">boş gün</p>
                  ) : (
                    <ul className="divide-y divide-border">
                      {dayRows.map((r) => (
                        <li
                          key={r.key}
                          className="space-y-1.5 px-3 py-1.5"
                          data-testid="skeleton-row"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                          <select
                            value={r.subject_id}
                            onChange={(e) => {
                              const sid = Number(e.target.value);
                              const keep = books.some(
                                (b) => b.id === r.book_id && b.subject_id === sid,
                              );
                              update(r.key, { subject_id: sid, book_id: keep ? r.book_id : null });
                            }}
                            className="min-w-40 flex-1 rounded border border-border bg-background px-2 py-1 text-[13px] text-foreground"
                            aria-label="Ders"
                          >
                            {subjects.map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.name}
                              </option>
                            ))}
                          </select>
                          <select
                            value={r.period ?? ""}
                            onChange={(e) =>
                              update(r.key, {
                                period: (e.target.value || null) as SkeletonPeriod | null,
                              })
                            }
                            className="rounded border border-border bg-background px-2 py-1 text-[13px] text-foreground"
                            aria-label="Periyot"
                          >
                            <option value="">Periyotsuz</option>
                            <option value="morning">Sabah</option>
                            <option value="noon">Öğle</option>
                            <option value="evening">Akşam</option>
                          </select>
                          <label className="inline-flex items-center gap-1 text-[12px] text-foreground">
                            <input
                              type="checkbox"
                              checked={r.is_routine}
                              onChange={(e) => update(r.key, { is_routine: e.target.checked })}
                            />
                            rutin
                          </label>
                          <label className="inline-flex items-center gap-1 text-[12px] text-foreground">
                            adet
                            <input
                              type="number"
                              min={1}
                              max={100}
                              value={r.default_count ?? ""}
                              placeholder="oto"
                              onChange={(e) =>
                                update(r.key, {
                                  default_count: e.target.value ? Number(e.target.value) : null,
                                })
                              }
                              className="w-16 rounded border border-border bg-background px-1.5 py-1 text-[13px] text-foreground"
                            />
                          </label>
                          <button
                            type="button"
                            onClick={() => remove(r.key)}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            aria-label="Satırı sil"
                          >
                            <Trash2 className="size-3.5" aria-hidden />
                          </button>
                          </div>
                          <SourceLine
                            row={r}
                            books={books.filter((b) => b.subject_id === r.subject_id)}
                            onChange={(patch) => update(r.key, patch)}
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
            {subjects.length === 0 ? (
              <p className="text-[12px] text-amber-800 dark:text-amber-200">
                Öğrencinin ders listesi boş — önce kitap ata.
              </p>
            ) : null}
          </div>
        )}

        <DialogFooter className="gap-2">
          {exists ? (
            <Button
              type="button"
              variant="outline"
              className="sm:mr-auto text-rose-700 dark:text-rose-300"
              disabled={del.isPending}
              onClick={() => {
                if (
                  window.confirm(
                    `"${q.data?.name ?? "Bu dönem"}" dönemi silinsin mi? Görevlere dokunulmaz; bu dönemin günleri önceki döneme döner.`,
                  )
                ) {
                  del.mutate(
                    { skeleton_id: q.data?.id ?? null },
                    { onSuccess: () => setSelectedId(null) },
                  );
                }
              }}
            >
              Dönemi sil
            </Button>
          ) : null}
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Vazgeç
          </Button>
          <Button type="button" onClick={submit} disabled={save.isPending || rows == null}>
            {save.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
            Kaydet
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const KIND_TR: Record<string, string> = {
  thread: "devam",
  next: "sıradaki",
  new: "yeni konu",
  weak: "tekrar",
};

/**
 * Önerilerin işe yarıyor mu? Son 30 günde koçun (tüm öğrencileri) hayaletlerde
 * ne yaptığı: çipten kabul · başka konu · kaldırma. Hedef: çiplerin ≥%60'ı kabul.
 */
function AcceptanceLine({ report }: { report: GhostAcceptanceReport | undefined }) {
  if (!report || report.actions === 0) return null;
  const top1 = report.by_rank["1"] ?? 0;
  const kinds = Object.entries(report.by_kind)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${KIND_TR[k] ?? k} ${n}`)
    .join(" · ");
  return (
    <div
      className="rounded-md border border-border bg-muted/40 px-3 py-2 text-[12px] text-foreground"
      data-testid="skeleton-acceptance"
    >
      <span className="font-semibold">Son 30 gün, tüm öğrencilerin: </span>
      {report.actions} öneri işlendi · çipten kabul{" "}
      <b>%{report.acceptance_pct ?? 0}</b> ({report.accepted}) · başka konu {report.other} ·
      kaldırılan {report.dismissed}
      {report.accepted > 0 ? (
        <span className="text-muted-foreground">
          {" "}
          — kabullerin {top1}&apos;i 1. çipten{kinds ? ` · ${kinds}` : ""}
        </span>
      ) : null}
    </div>
  );
}

/**
 * Satırın KAYNAĞI (F2-1): aynı derste birden çok satır varken hangisinin
 * hangi iş olduğu buradan okunur. Kitap seçilirse rutin o kitapta ilerler
 * (sırayla / karışık); konu satırında çiplerde önce o kitap gelir. Kitap
 * yoksa serbest metin adı — rutinse "etkinlik olarak" aynen yazılır.
 */
function SourceLine({
  row,
  books,
  onChange,
}: {
  row: Row;
  books: { id: number; name: string }[];
  onChange: (patch: Partial<Row>) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 pl-1 text-[12px] text-foreground">
      <span className="text-muted-foreground">Kaynak:</span>
      <select
        value={row.book_id ?? ""}
        onChange={(e) =>
          onChange({ book_id: e.target.value ? Number(e.target.value) : null })
        }
        className="min-w-48 flex-1 rounded border border-border bg-background px-2 py-1 text-[12.5px] text-foreground"
        aria-label="Kaynak kitap"
      >
        <option value="">Kitap yok{row.label ? "" : " (herhangi bir kaynak)"}</option>
        {books.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>
      {row.book_id ? null : (
        <input
          type="text"
          value={row.label ?? ""}
          maxLength={160}
          placeholder="ya da serbest metin (ör. 345 Sıfır Risk Paragraf 2 Test)"
          onChange={(e) => onChange({ label: e.target.value })}
          className="min-w-56 flex-1 rounded border border-border bg-background px-2 py-1 text-[12.5px] text-foreground"
          aria-label="Etkinlik adı"
        />
      )}
      {row.is_routine && row.book_id ? (
        <select
          value={row.routine_mode ?? "sirali"}
          onChange={(e) => onChange({ routine_mode: e.target.value as RoutineMode })}
          className="rounded border border-border bg-background px-2 py-1 text-[12.5px] text-foreground"
          aria-label="Rutin biçimi"
          title="Sırayla: kitapta kalınan yerden devam. Karışık: her gün farklı bölümlerden birer test."
        >
          {(Object.keys(ROUTINE_MODE_LABELS) as RoutineMode[]).map((m) => (
            <option key={m} value={m}>
              {m === "karma" ? "karışık — her gün farklı bölümlerden birer test" : "sırayla — kaldığı yerden"}
            </option>
          ))}
        </select>
      ) : null}
    </div>
  );
}

/**
 * F2-2 dönem şeridi: her dönem yalnız başlangıç taşır, bir sonraki dönem
 * başlayana kadar geçerli (Yaz · Okul dönemi · Yarıyıl tatili). Seçilen dönem
 * düzenlenir; "bugün" rozeti o gün geçerli olanı gösterir.
 */
function PeriodStrip({
  studentId,
  periods,
  activeId,
  weekStart,
  weekEnd,
  onSelect,
}: {
  studentId: number;
  periods: SkeletonTerm[];
  activeId: number | null;
  weekStart: string;
  weekEnd: string;
  onSelect: (id: number | null) => void;
}) {
  const [mode, setMode] = React.useState<null | "new" | "edit">(null);
  const active = periods.find((p) => p.id === activeId) ?? null;

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/30 p-2.5" data-testid="period-strip">
      <div className="flex flex-wrap items-center gap-1.5">
        <CalendarRange className="size-3.5 text-muted-foreground" aria-hidden />
        <span className="text-[12px] font-semibold text-foreground">Dönemler</span>
        {periods.length === 0 ? (
          <span className="text-[12px] text-muted-foreground">henüz yok — ilk kaydettiğin iskelet ilk dönem olur</span>
        ) : null}
        {periods.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => {
              onSelect(p.id);
              setMode(null);
            }}
            data-testid="period-chip"
            className={cn(
              "rounded-md border px-2 py-1 text-left text-[12px]",
              p.id === activeId
                ? "border-cyan-700 bg-cyan-700 text-white"
                : "border-border bg-background text-foreground hover:bg-muted",
            )}
          >
            <span className="font-semibold">{p.name}</span>
            <span className={p.id === activeId ? "text-white/85" : "text-muted-foreground"}>
              {" "}· {periodRange(p)} · {p.slot_count} satır
            </span>
            {p.is_current ? (
              <span
                className={cn(
                  "ml-1 rounded px-1 text-[10px] font-semibold",
                  p.id === activeId ? "bg-white text-cyan-900" : "bg-emerald-700 text-white",
                )}
              >
                bugün
              </span>
            ) : null}
          </button>
        ))}
        <span className="ml-auto flex gap-1">
          {active ? (
            <button
              type="button"
              onClick={() => setMode(mode === "edit" ? null : "edit")}
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] text-cyan-800 hover:bg-cyan-500/10 dark:text-cyan-300"
            >
              <Pencil className="size-3" aria-hidden /> Dönemi düzenle
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setMode(mode === "new" ? null : "new")}
            className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[12px] text-cyan-800 hover:bg-cyan-500/10 dark:text-cyan-300"
          >
            <Plus className="size-3" aria-hidden /> Yeni dönem
          </button>
        </span>
      </div>
      {mode === "new" ? (
        <NewPeriodForm
          studentId={studentId}
          source={active}
          weekStart={weekStart}
          weekEnd={weekEnd}
          onDone={(id) => {
            setMode(null);
            onSelect(id);
          }}
        />
      ) : null}
      {mode === "edit" && active ? (
        <EditPeriodForm
          key={active.id}
          studentId={studentId}
          period={active}
          onDone={() => setMode(null)}
        />
      ) : null}
    </div>
  );
}

type NewSource = "week" | "copy" | "empty";

function NewPeriodForm({
  studentId,
  source,
  weekStart,
  weekEnd,
  onDone,
}: {
  studentId: number;
  source: SkeletonTerm | null;
  weekStart: string;
  weekEnd: string;
  onDone: (id: number | null) => void;
}) {
  const [name, setName] = React.useState("");
  const [kind, setKind] = React.useState<NewSource>("week");
  const [start, setStart] = React.useState(weekStart);
  const create = useCreatePeriod(studentId);
  const fromWeek = useSkeletonFromWeek(studentId);
  const busy = create.isPending || fromWeek.isPending;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const nm = name.trim() || null;
    if (kind === "week") {
      fromWeek.mutate(
        { start: weekStart, end: weekEnd, mode: "new", name: nm },
        { onSuccess: (res) => onDone(res.data.id) },
      );
    } else {
      create.mutate(
        { valid_from: start, name: nm, copy_from_id: kind === "copy" ? source?.id ?? null : null },
        { onSuccess: (res) => onDone(res.data.id) },
      );
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 rounded-md border border-border bg-background p-2.5" data-testid="new-period-form">
      <div className="flex flex-wrap items-center gap-2 text-[12.5px] text-foreground">
        <input
          type="text"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          placeholder="Dönem adı (ör. Okul dönemi, Yarıyıl tatili)"
          className="min-w-56 flex-1 rounded border border-border bg-background px-2 py-1 text-[12.5px] text-foreground"
          aria-label="Dönem adı"
        />
      </div>
      <div className="flex flex-col gap-1 text-[12.5px] text-foreground">
        <label className="inline-flex items-center gap-2">
          <input type="radio" checked={kind === "week"} onChange={() => setKind("week")} />
          Bu haftanın görevlerinden — {fmtDay(weekStart)} tarihinden başlar
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="radio"
            checked={kind === "copy"}
            onChange={() => setKind("copy")}
            disabled={!source}
          />
          {source ? `"${source.name}" döneminin kopyası` : "Kopya (önce bir dönem seç)"}
        </label>
        <label className="inline-flex items-center gap-2">
          <input type="radio" checked={kind === "empty"} onChange={() => setKind("empty")} />
          Boş dönem
        </label>
        {kind !== "week" ? (
          <label className="inline-flex items-center gap-2 pl-6">
            Başlangıç
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="rounded border border-border bg-background px-1.5 py-0.5 text-[12.5px] text-foreground"
              aria-label="Dönem başlangıcı"
            />
          </label>
        ) : null}
      </div>
      <p className="text-[11.5px] text-muted-foreground">
        Önceki dönem silinmez; yeni dönem başlayınca bir gün önce biter.
      </p>
      <Button type="submit" size="sm" disabled={busy || (kind !== "week" && !start)}>
        {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
        Dönemi başlat
      </Button>
    </form>
  );
}

function EditPeriodForm({
  studentId,
  period,
  onDone,
}: {
  studentId: number;
  period: SkeletonTerm;
  onDone: () => void;
}) {
  const [name, setName] = React.useState(period.name);
  const [start, setStart] = React.useState(period.valid_from ?? "");
  const upd = useUpdatePeriod(studentId);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        upd.mutate(
          {
            skeleton_id: period.id,
            name: name.trim() || null,
            valid_from: start || null,
            clear_start: !start,
          },
          { onSuccess: onDone },
        );
      }}
      className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-background p-2.5 text-[12.5px] text-foreground"
      data-testid="edit-period-form"
    >
      <input
        type="text"
        value={name}
        maxLength={120}
        onChange={(e) => setName(e.target.value)}
        className="min-w-48 flex-1 rounded border border-border bg-background px-2 py-1 text-[12.5px] text-foreground"
        aria-label="Dönem adı"
      />
      <label className="inline-flex items-center gap-1">
        Başlangıç
        <input
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          className="rounded border border-border bg-background px-1.5 py-0.5 text-[12.5px] text-foreground"
          aria-label="Dönem başlangıcı"
        />
      </label>
      <span className="text-[11.5px] text-muted-foreground">boş = en baştan beri</span>
      <Button type="submit" size="sm" disabled={upd.isPending}>
        Kaydet
      </Button>
    </form>
  );
}
