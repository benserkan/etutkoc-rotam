"use client";

/**
 * Haftalık İskelet düzenleyicisi.
 *
 * İskelet TARİHE değil HAFTA GÜNÜNE bağlı: "Pazartesi Matematik" satırı her
 * haftanın Pazartesi'sine hayalet öneri olarak düşer.
 *
 * Düzen (2026-09-27 yeniden tasarım — koç: "bütün günler birbirine girmiş,
 * neyin ne olduğu belli değil"): solda 7 günlük fihrist (her günün derslerini
 * renkli etiketlerle özetler → hafta tek bakışta görünür), sağda YALNIZ seçili
 * gün. Gün içinde satırlar türüne göre üç bölümde: okul/dershane dersi · konu
 * çalışması · rutin. Her satır etiketli alanlar + "bu satır ne yapar" cümlesi.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CalendarRange,
  Copy,
  GraduationCap,
  Loader2,
  Pencil,
  Plus,
  Repeat,
  Trash2,
  Wand2,
} from "lucide-react";

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
import { toneForKey } from "@/components/teacher/weekly-plan/week-grid";
import {
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
  type SkeletonBookOption,
  type SkeletonResponse,
  type SkeletonSlotIn,
  skeletonKeys,
  useDeleteSkeleton,
  useSaveSkeleton,
  useSkeletonFromWeek,
  WEEKDAY_LABELS,
} from "@/lib/api/weekly-skeleton";

type Row = SkeletonSlotIn & { key: string };
type RowKind = "anchor" | "topic" | "routine";

let _seq = 0;
const nextKey = () => `r${++_seq}`;

const KIND_ORDER: Record<RowKind, number> = { anchor: 0, topic: 1, routine: 2 };

function rowKind(r: Row): RowKind {
  if (r.is_anchor) return "anchor";
  if (r.is_routine) return "routine";
  return "topic";
}

function kindPatch(kind: RowKind): Partial<Row> {
  if (kind === "routine") return { is_routine: true, is_anchor: false, second_book_id: null };
  if (kind === "anchor")
    return { is_routine: false, is_anchor: true, routine_mode: null, routine_scope: null };
  return { is_routine: false, is_anchor: false, routine_mode: null, routine_scope: null };
}

const PERIOD_TR: Record<string, string> = { morning: "Sabah", noon: "Öğle", evening: "Akşam" };

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
    is_anchor: !!s.is_anchor,
    routine_scope: s.routine_scope ?? null,
    second_book_id: s.second_book_id ?? null,
  }));
}

function toCapDraft(sk: SkeletonResponse | undefined): Record<number, string> {
  const out: Record<number, string> = {};
  for (const c of sk?.capacity ?? []) out[c.weekday] = c.override == null ? "" : String(c.override);
  return out;
}

/** Kaydedilecek biçim — hem gönderimde hem "kaydedilmemiş değişiklik" karşılaştırmasında. */
function toSlots(list: Row[]): SkeletonSlotIn[] {
  const ordered = list
    .map((r, i) => ({ r, i }))
    .sort(
      (a, b) =>
        a.r.weekday - b.r.weekday ||
        KIND_ORDER[rowKind(a.r)] - KIND_ORDER[rowKind(b.r)] ||
        a.i - b.i,
    )
    .map((x) => x.r);
  return ordered.map((r, i) => ({
    weekday: r.weekday,
    period: r.period,
    subject_id: r.subject_id,
    position: i,
    is_routine: r.is_routine,
    default_count: r.default_count,
    book_id: r.book_id ?? null,
    label: r.book_id ? null : r.label?.trim() || null,
    routine_mode: r.is_routine && r.book_id ? (r.routine_mode ?? "sirali") : null,
    is_anchor: !!r.is_anchor,
    routine_scope: r.is_routine && r.book_id && r.routine_scope === "problems" ? "problems" : null,
    second_book_id:
      !r.is_routine && r.book_id && r.second_book_id && r.second_book_id !== r.book_id
        ? r.second_book_id
        : null,
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
  // Düzenlenen dönem (null = bugün geçerli dönem)
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
    staleTime: 0,
    refetchOnMount: "always",
  });
  const save = useSaveSkeleton(studentId);
  const fromWeek = useSkeletonFromWeek(studentId);
  const del = useDeleteSkeleton(studentId);

  const [rows, setRows] = React.useState<Row[] | null>(null);
  const [baseline, setBaseline] = React.useState<string>("");
  const [capDraft, setCapDraft] = React.useState<Record<number, string>>({});
  const [capBase, setCapBase] = React.useState<string>("");
  // Sunucu verisi değişince taslağı yeniden kur — render sırasında türetme.
  const dataStamp = q.data
    ? `${q.data.id ?? "yok"}:${JSON.stringify(q.data.slots.map((s) => s.id))}`
    : null;
  const [lastStamp, setLastStamp] = React.useState<string | null>(null);
  if (dataStamp !== lastStamp) {
    setLastStamp(dataStamp);
    const r0 = q.data ? toRows(q.data) : null;
    setRows(r0);
    setBaseline(JSON.stringify(toSlots(r0 ?? [])));
    const c0 = toCapDraft(q.data);
    setCapDraft(c0);
    setCapBase(JSON.stringify(c0));
  }

  const todayWd = (new Date().getDay() + 6) % 7;
  const [day, setDay] = React.useState<number>(todayWd);

  const capacity = q.data?.capacity ?? [];
  const subjects = q.data?.subjects ?? [];
  const books = q.data?.books ?? [];
  const list = rows ?? [];
  const dirty =
    rows != null &&
    (JSON.stringify(toSlots(list)) !== baseline || JSON.stringify(capDraft) !== capBase);

  function update(key: string, patch: Partial<Row>) {
    setRows((prev) => (prev ?? []).map((r) => (r.key === key ? { ...r, ...patch } : r)));
  }
  function remove(key: string) {
    setRows((prev) => (prev ?? []).filter((r) => r.key !== key));
  }
  function add(kind: RowKind) {
    const first = subjects[0];
    if (!first) return;
    setRows((prev) => [
      ...(prev ?? []),
      {
        key: nextKey(),
        weekday: day,
        period: null,
        subject_id: first.id,
        position: (prev ?? []).filter((r) => r.weekday === day).length,
        is_routine: false,
        default_count: null,
        book_id: null,
        label: null,
        routine_mode: null,
        is_anchor: false,
        routine_scope: null,
        second_book_id: null,
        ...kindPatch(kind),
      },
    ]);
  }
  function copyDay(targets: number[]) {
    setRows((prev) => {
      const base = prev ?? [];
      const src = base.filter((r) => r.weekday === day);
      const kept = base.filter((r) => !targets.includes(r.weekday));
      const clones = targets.flatMap((wd) =>
        src.map((r) => ({ ...r, key: nextKey(), weekday: wd })),
      );
      return [...kept, ...clones];
    });
  }
  function applySecond(subjectId: number, bookId: number, second: number | null) {
    setRows((prev) =>
      (prev ?? []).map((r) =>
        !r.is_routine && r.subject_id === subjectId && r.book_id === bookId
          ? { ...r, second_book_id: second }
          : r,
      ),
    );
  }

  function submit() {
    const day_capacity: Record<string, number | null> = {};
    for (let wd = 0; wd < 7; wd++) {
      const v = (capDraft[wd] ?? "").trim();
      day_capacity[String(wd)] = v === "" ? null : Math.max(0, Number(v) || 0);
    }
    save.mutate(
      { skeleton_id: q.data?.id ?? null, slots: toSlots(list), day_capacity },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  function close() {
    if (dirty && !window.confirm("Kaydedilmemiş değişiklikler var. Kaydetmeden kapatılsın mı?")) {
      return;
    }
    onOpenChange(false);
  }

  const exists = q.data?.exists ?? false;
  const subjectName = (id: number) => subjects.find((s) => s.id === id)?.name ?? "Ders";

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? onOpenChange(true) : close())}>
      <DialogContent className="flex h-[92vh] flex-col gap-3 sm:max-w-6xl">
        <DialogHeader className="space-y-1">
          <DialogTitle>Haftalık iskelet</DialogTitle>
          <DialogDescription>
            Her hafta tekrar eden ders yerleşimi. Bir günü seç, o günün satırlarını düzenle. Satırlar
            programda kesikli &ldquo;öneri&rdquo; olarak görünür; tıklayıp onaylayınca görev olur.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-2 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            <PeriodStrip
              studentId={studentId}
              periods={q.data?.periods ?? []}
              activeId={q.data?.id ?? null}
              weekStart={weekStart}
              weekEnd={weekEnd}
              onSelect={setSelectedId}
            />
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="shrink-0"
            disabled={fromWeek.isPending}
            title="Görüntülenen haftanın görevlerinden gün + ders + kaynak satırları çıkarılır."
            onClick={() => {
              if (
                exists &&
                !window.confirm(
                  `"${q.data?.name ?? "Bu dönem"}" satırları bu haftanın görevleriyle değiştirilsin mi? (Yeni bir dönem başlatmak için "Yeni dönem"i kullan.)`,
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
        </div>

        {q.isLoading || rows == null ? (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="size-5 animate-spin text-muted-foreground" aria-hidden />
          </div>
        ) : subjects.length === 0 ? (
          <p className="text-[13px] text-amber-800 dark:text-amber-200">
            Öğrencinin ders listesi boş — önce kitap ata.
          </p>
        ) : (
          <div className="grid min-h-0 flex-1 gap-3 md:grid-cols-[230px_1fr]">
            <DayRail
              rows={list}
              books={books}
              selected={day}
              onSelect={setDay}
              subjectName={subjectName}
            />
            <DayPanel
              key={day}
              day={day}
              rows={list.filter((r) => r.weekday === day)}
              allRows={list}
              subjects={subjects}
              books={books}
              capValue={capDraft[day] ?? ""}
              capLearned={capacity[day]?.learned ?? null}
              onCap={(v) => setCapDraft((p) => ({ ...p, [day]: v }))}
              onAdd={add}
              onUpdate={update}
              onRemove={remove}
              onCopy={copyDay}
              onApplySecond={applySecond}
              subjectName={subjectName}
            />
          </div>
        )}

        <DialogFooter className="items-center gap-2 border-t border-border pt-3 sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            {exists ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="text-rose-700 dark:text-rose-300"
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
            <AcceptanceLine report={accQ.data} />
          </div>
          <div className="flex items-center gap-2">
            {dirty ? (
              <span
                className="rounded bg-amber-600 px-2 py-0.5 text-[11.5px] font-semibold text-white"
                data-testid="skeleton-dirty"
              >
                Kaydedilmemiş değişiklik
              </span>
            ) : null}
            <Button type="button" variant="outline" onClick={close}>
              Vazgeç
            </Button>
            <Button type="button" onClick={submit} disabled={save.isPending || rows == null}>
              {save.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
              Kaydet
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/* Sol fihrist: 7 gün, her birinde o günün dersleri renkli etiketle    */
/* ------------------------------------------------------------------ */

function DayRail({
  rows,
  books,
  selected,
  onSelect,
  subjectName,
}: {
  rows: Row[];
  books: SkeletonBookOption[];
  selected: number;
  onSelect: (wd: number) => void;
  subjectName: (id: number) => string;
}) {
  const bookName = (id: number | null | undefined) =>
    id ? (books.find((b) => b.id === id)?.name ?? null) : null;
  return (
    <nav className="min-h-0 space-y-1 overflow-y-auto pr-1" aria-label="Günler">
      {WEEKDAY_LABELS.map((label, wd) => {
        const dayRows = rows
          .filter((r) => r.weekday === wd)
          .sort((a, b) => KIND_ORDER[rowKind(a)] - KIND_ORDER[rowKind(b)]);
        const active = wd === selected;
        return (
          <button
            key={wd}
            type="button"
            onClick={() => onSelect(wd)}
            data-testid="skeleton-day-tab"
            aria-current={active ? "true" : undefined}
            className={cn(
              "w-full rounded-lg border px-2.5 py-2 text-left transition-colors",
              active
                ? "border-cyan-600 bg-cyan-500/10 ring-1 ring-cyan-600"
                : "border-border bg-background hover:bg-muted/60",
            )}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[13.5px] font-semibold text-foreground">{label}</span>
              <span className="text-[11px] text-muted-foreground">
                {dayRows.length === 0 ? "boş" : `${dayRows.length} satır`}
              </span>
            </div>
            {dayRows.length > 0 ? (
              <ul className="mt-1.5 space-y-0.5">
                {dayRows.map((r) => {
                  const nm = subjectName(r.subject_id);
                  const k = rowKind(r);
                  return (
                    <li
                      key={r.key}
                      className="flex items-start gap-1.5 text-[11.5px] leading-snug text-foreground"
                    >
                      <span
                        className={cn(
                          "mt-1 size-2 shrink-0 rounded-full",
                          toneForKey("s", nm).dot,
                        )}
                        aria-hidden
                      />
                      <span className="min-w-0 break-words">
                        {nm}
                        {bookName(r.book_id) || (r.is_routine && r.label?.trim()) ? (
                          <span className="text-muted-foreground">
                            {" "}— {bookName(r.book_id) ?? r.label?.trim()}
                          </span>
                        ) : null}
                        {k === "routine" ? (
                          <span className="text-muted-foreground"> · rutin</span>
                        ) : k === "anchor" ? (
                          <span className="text-muted-foreground"> · okul/dershane</span>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Sağ: seçili günün düzenleyicisi                                    */
/* ------------------------------------------------------------------ */

const SECTION_META: Record<
  RowKind,
  { title: string; hint: string; icon: React.ComponentType<{ className?: string }>; add: string }
> = {
  anchor: {
    title: "Okul / dershane dersleri",
    hint: "O gün okulda ya da dershanede işlenen ders. Öneri \"bugün hangi konu işlendi?\" diye sorar; kalan testler haftaya yayılır.",
    icon: GraduationCap,
    add: "Okul/dershane dersi",
  },
  topic: {
    title: "Konu çalışması",
    hint: "Kitapta kalınan konudan devam eder. Konu bitince 2. kaynak tanımlıysa hangisiyle devam edileceği sana sorulur.",
    icon: BookOpen,
    add: "Konu satırı",
  },
  routine: {
    title: "Rutinler",
    hint: "Her hafta aynı işi tekrarlayan satırlar (paragraf, problem…). Gün kartında tek tuşla onaylanır.",
    icon: Repeat,
    add: "Rutin",
  },
};

function DayPanel({
  day,
  rows,
  allRows,
  subjects,
  books,
  capValue,
  capLearned,
  onCap,
  onAdd,
  onUpdate,
  onRemove,
  onCopy,
  onApplySecond,
  subjectName,
}: {
  day: number;
  rows: Row[];
  allRows: Row[];
  subjects: { id: number; name: string }[];
  books: SkeletonBookOption[];
  capValue: string;
  capLearned: number | null;
  onCap: (v: string) => void;
  onAdd: (kind: RowKind) => void;
  onUpdate: (key: string, patch: Partial<Row>) => void;
  onRemove: (key: string) => void;
  onCopy: (targets: number[]) => void;
  onApplySecond: (subjectId: number, bookId: number, second: number | null) => void;
  subjectName: (id: number) => string;
}) {
  const [copyOpen, setCopyOpen] = React.useState(false);
  const [targets, setTargets] = React.useState<number[]>([]);
  const label = WEEKDAY_LABELS[day];

  return (
    <section
      className="flex min-h-0 flex-col rounded-lg border border-border bg-background"
      data-testid="skeleton-day"
      aria-label={label}
    >
      <header className="space-y-2 border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h3 className="text-[17px] font-semibold text-foreground">{label}</h3>
          <label
            className="inline-flex items-center gap-1.5 text-[12.5px] text-foreground"
            title="Bu güne sığan test sayısı: konu yayılırken boşluk buna göre hesaplanır. Boş bırakırsan geçmişten öğrenilen değer kullanılır."
          >
            Günlük kapasite
            <input
              type="number"
              min={0}
              max={200}
              value={capValue}
              placeholder={capLearned != null ? String(capLearned) : "—"}
              onChange={(e) => onCap(e.target.value)}
              className="w-16 rounded-md border border-border bg-background px-1.5 py-1 text-[12.5px] text-foreground"
              aria-label={`${label} kapasitesi`}
              data-testid="capacity-input"
            />
            test
            {capLearned != null ? (
              <span className="text-muted-foreground">(geçmişe göre {capLearned})</span>
            ) : null}
          </label>
          <button
            type="button"
            onClick={() => {
              setCopyOpen((v) => !v);
              setTargets([]);
            }}
            disabled={rows.length === 0}
            className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-[12.5px] text-cyan-800 hover:bg-cyan-500/10 disabled:opacity-40 dark:text-cyan-300"
          >
            <Copy className="size-3.5" aria-hidden /> Bu günü başka günlere kopyala
          </button>
        </div>
        {copyOpen ? (
          <div
            className="flex flex-wrap items-center gap-1.5 rounded-md border border-cyan-600/40 bg-cyan-500/5 p-2"
            data-testid="copy-day"
          >
            <span className="text-[12px] text-foreground">
              {label} satırları şu günlere kopyalansın (o günlerin mevcut satırları değişir):
            </span>
            {WEEKDAY_LABELS.map((l, wd) =>
              wd === day ? null : (
                <button
                  key={wd}
                  type="button"
                  onClick={() =>
                    setTargets((t) => (t.includes(wd) ? t.filter((x) => x !== wd) : [...t, wd]))
                  }
                  className={cn(
                    "rounded-md border px-2 py-0.5 text-[12px]",
                    targets.includes(wd)
                      ? "border-cyan-700 bg-cyan-700 text-white"
                      : "border-border bg-background text-foreground hover:bg-muted",
                  )}
                >
                  {l}
                </button>
              ),
            )}
            <Button
              type="button"
              size="sm"
              disabled={targets.length === 0}
              onClick={() => {
                onCopy(targets);
                setCopyOpen(false);
              }}
            >
              Kopyala
            </Button>
            <button
              type="button"
              onClick={() => setCopyOpen(false)}
              className="text-[12px] text-muted-foreground hover:underline"
            >
              vazgeç
            </button>
          </div>
        ) : null}
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3">
        {(["anchor", "topic", "routine"] as RowKind[]).map((kind) => {
          const meta = SECTION_META[kind];
          const Icon = meta.icon;
          const sectionRows = rows.filter((r) => rowKind(r) === kind);
          return (
            <div key={kind} data-kind={kind}>
              <div className="mb-1.5 flex items-start gap-2">
                <Icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <div className="text-[13.5px] font-semibold text-foreground">
                    {meta.title}
                    <span className="ml-1.5 text-[11.5px] font-normal text-muted-foreground">
                      {sectionRows.length > 0 ? `${sectionRows.length} satır` : ""}
                    </span>
                  </div>
                  <p className="text-[11.5px] leading-snug text-muted-foreground">{meta.hint}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onAdd(kind)}
                  className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-[12px] text-foreground hover:bg-muted"
                  data-testid={`add-${kind}`}
                >
                  <Plus className="size-3.5" aria-hidden /> {meta.add}
                </button>
              </div>
              {sectionRows.length > 0 ? (
                <ul className="space-y-2">
                  {sectionRows.map((r) => (
                    <RowCard
                      key={r.key}
                      row={r}
                      dayLabel={label}
                      subjects={subjects}
                      books={books.filter((b) => b.subject_id === r.subject_id)}
                      allBooks={books}
                      allRows={allRows}
                      subjectName={subjectName}
                      onChange={(patch) => onUpdate(r.key, patch)}
                      onRemove={() => onRemove(r.key)}
                      onApplySecond={onApplySecond}
                    />
                  ))}
                </ul>
              ) : null}
            </div>
          );
        })}
        {rows.length === 0 ? (
          <p className="rounded-md border border-dashed border-border px-3 py-4 text-center text-[12.5px] text-muted-foreground">
            {label} boş — bu güne öneri düşmez. Yukarıdan satır ekleyebilir ya da dolu bir günü buraya
            kopyalayabilirsin.
          </p>
        ) : null}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Tek satır                                                           */
/* ------------------------------------------------------------------ */

function Field({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("flex min-w-0 flex-col gap-0.5", className)}>
      <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-md border border-border bg-background px-2 py-1.5 text-[13px] text-foreground";

function RowCard({
  row,
  dayLabel,
  subjects,
  books,
  allBooks,
  allRows,
  subjectName,
  onChange,
  onRemove,
  onApplySecond,
}: {
  row: Row;
  dayLabel: string;
  subjects: { id: number; name: string }[];
  books: SkeletonBookOption[];
  allBooks: SkeletonBookOption[];
  allRows: Row[];
  subjectName: (id: number) => string;
  onChange: (patch: Partial<Row>) => void;
  onRemove: () => void;
  onApplySecond: (subjectId: number, bookId: number, second: number | null) => void;
}) {
  const kind = rowKind(row);
  const current = books.find((b) => b.id === row.book_id);
  const banks = books.filter((b) => b.is_bank && b.id !== row.book_id);
  const nm = subjectName(row.subject_id);
  const tone = toneForKey("s", nm);
  // Aynı ders + aynı ana kaynakta 2. kaynağı farklı olan diğer konu satırları
  const siblings =
    kind !== "routine" && row.book_id
      ? allRows.filter(
          (r) =>
            r.key !== row.key &&
            !r.is_routine &&
            r.subject_id === row.subject_id &&
            r.book_id === row.book_id &&
            (r.second_book_id ?? null) !== (row.second_book_id ?? null),
        ).length
      : 0;

  return (
    <li
      className="rounded-lg border border-border bg-card p-3 shadow-sm"
      data-testid="skeleton-row"
    >
      <div className="flex flex-wrap items-end gap-2">
        <span className={cn("mb-2 size-2.5 shrink-0 rounded-full", tone.dot)} aria-hidden />
        <Field label="Ders" className="min-w-44 flex-[2]">
          <select
            value={row.subject_id}
            onChange={(e) => {
              const sid = Number(e.target.value);
              const keep = allBooks.some((b) => b.id === row.book_id && b.subject_id === sid);
              onChange({
                subject_id: sid,
                book_id: keep ? row.book_id : null,
                second_book_id: keep ? row.second_book_id : null,
              });
            }}
            className={cn(inputCls, "font-medium")}
            aria-label="Ders"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        <fieldset className="flex min-w-0 flex-col gap-0.5">
          <legend className="text-[11px] font-medium text-muted-foreground">Satır türü</legend>
          <div className="flex overflow-hidden rounded-md border border-border">
            {(
              [
                ["topic", "Konu"],
                ["routine", "Rutin"],
                ["anchor", "Okul/dershane dersi"],
              ] as [RowKind, string][]
            ).map(([k, l]) => (
              <label
                key={k}
                className={cn(
                  "inline-flex cursor-pointer items-center gap-1 border-r border-border px-2 py-1.5 text-[12px] last:border-r-0",
                  kind === k
                    ? "bg-cyan-700 font-semibold text-white"
                    : "bg-background text-foreground hover:bg-muted",
                )}
              >
                <input
                  type="radio"
                  name={`kind-${row.key}`}
                  checked={kind === k}
                  onChange={() => onChange(kindPatch(k))}
                  aria-label={l}
                  className="size-3 accent-white"
                />
                {l}
              </label>
            ))}
          </div>
        </fieldset>
        <Field label="Gün içinde" className="w-32">
          <select
            value={row.period ?? ""}
            onChange={(e) =>
              onChange({ period: (e.target.value || null) as SkeletonPeriod | null })
            }
            className={inputCls}
            aria-label="Periyot"
          >
            <option value="">Farketmez</option>
            <option value="morning">Sabah</option>
            <option value="noon">Öğle</option>
            <option value="evening">Akşam</option>
          </select>
        </Field>
        <Field label="Test / gün" className="w-24">
          <input
            type="number"
            min={1}
            max={100}
            value={row.default_count ?? ""}
            placeholder="otomatik"
            onChange={(e) =>
              onChange({ default_count: e.target.value ? Number(e.target.value) : null })
            }
            className={inputCls}
            aria-label="Test sayısı"
          />
        </Field>
        <button
          type="button"
          onClick={onRemove}
          className="mb-1 ml-auto rounded-md p-1.5 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-700 dark:hover:text-rose-300"
          aria-label="Satırı sil"
          title="Satırı sil"
        >
          <Trash2 className="size-4" aria-hidden />
        </button>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <Field label={kind === "routine" ? "Rutin kaynağı" : "Ana kaynak"}>
          <select
            value={row.book_id ?? ""}
            onChange={(e) => {
              const bid = e.target.value ? Number(e.target.value) : null;
              onChange({
                book_id: bid,
                second_book_id: row.second_book_id === bid ? null : row.second_book_id,
              });
            }}
            className={inputCls}
            aria-label="Kaynak kitap"
          >
            <option value="">
              {kind === "routine" ? "Kitap yok — serbest metin" : "Belirtme — herhangi bir kaynak"}
            </option>
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
                {b.is_bank ? "" : " (soru bankası değil)"}
              </option>
            ))}
          </select>
        </Field>

        {kind === "routine" && !row.book_id ? (
          <Field label="Etkinlik adı">
            <input
              type="text"
              value={row.label ?? ""}
              maxLength={160}
              placeholder="ör. 345 Sıfır Risk Paragraf 2 Test"
              onChange={(e) => onChange({ label: e.target.value })}
              className={inputCls}
              aria-label="Etkinlik adı"
            />
          </Field>
        ) : null}

        {kind === "routine" && row.book_id ? (
          <Field label="Nasıl ilerlesin">
            <select
              value={row.routine_mode ?? "sirali"}
              onChange={(e) => onChange({ routine_mode: e.target.value as RoutineMode })}
              className={inputCls}
              aria-label="Rutin biçimi"
            >
              <option value="sirali">Sırayla — kaldığı yerden</option>
              <option value="karma">Karışık — her gün farklı bölümlerden birer test</option>
            </select>
          </Field>
        ) : null}

        {kind === "routine" && row.book_id && current?.has_problems ? (
          <Field label="Kapsam" className="sm:col-span-2">
            <select
              value={row.routine_scope ?? "book"}
              onChange={(e) =>
                onChange({ routine_scope: e.target.value === "problems" ? "problems" : null })
              }
              className={inputCls}
              aria-label="Rutin kapsamı"
            >
              <option value="book">Kitabın tamamı</option>
              <option value="problems">
                Yalnız problemler — kitabın problemleri bitince sıradaki soru bankasına geçer
              </option>
            </select>
          </Field>
        ) : null}

        {kind !== "routine" && row.book_id && current?.is_bank ? (
          <Field label="2. kaynak — konu ana kaynakta bitince">
            <div className="flex flex-col gap-1">
              <select
                value={row.second_book_id ?? ""}
                onChange={(e) =>
                  onChange({ second_book_id: e.target.value ? Number(e.target.value) : null })
                }
                className={inputCls}
                aria-label="İkinci kaynak"
              >
                <option value="">Yok — ana kaynakta sıradaki konuya geç</option>
                {banks.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
              {siblings > 0 ? (
                <button
                  type="button"
                  onClick={() =>
                    onApplySecond(row.subject_id, row.book_id!, row.second_book_id ?? null)
                  }
                  className="self-start text-[11.5px] text-cyan-800 hover:underline dark:text-cyan-300"
                  data-testid="apply-second-all"
                >
                  Bu seçimi {nm} için diğer {siblings} konu satırına da uygula
                </button>
              ) : null}
            </div>
          </Field>
        ) : null}
        {kind !== "routine" && row.book_id && current && !current.is_bank ? (
          <p className="self-end text-[11.5px] text-amber-800 dark:text-amber-200">
            Bu kitap soru bankası değil; 2. kaynak yalnız soru bankasıyla tanımlanır.
          </p>
        ) : null}
      </div>

      <p className="mt-2 rounded-md bg-muted/60 px-2.5 py-1.5 text-[12px] leading-snug text-foreground">
        {rowSummary(row, dayLabel, nm, current, allBooks)}
      </p>
    </li>
  );
}

/** "Bu satır ne yapar?" — koçun okuyacağı tek cümle. */
function rowSummary(
  row: Row,
  day: string,
  subject: string,
  book: SkeletonBookOption | undefined,
  allBooks: SkeletonBookOption[],
): string {
  const when = row.period ? `${day} ${PERIOD_TR[row.period].toLocaleLowerCase("tr")}` : day;
  const cnt = row.default_count
    ? `günde ${row.default_count} test`
    : "test sayısı alışkanlığına göre otomatik";
  const kind = rowKind(row);
  if (kind === "routine") {
    if (!book) {
      return row.label?.trim()
        ? `${when}: “${row.label.trim()}” etkinlik olarak yazılır (kitaba bağlı değil, test sayımına girmez).`
        : `${when}: ${subject} rutini — kaynak seçilmedi; kitap seç ya da etkinlik adı yaz.`;
    }
    if (row.routine_scope === "problems") {
      return `${when}: ${book.name} kitabından yalnız problemler, ${
        row.routine_mode === "karma" ? "her gün farklı bölümlerden" : "kaldığı yerden sırayla"
      } · ${cnt}. Problemler bitince sıradaki soru bankasının problemlerine geçer.`;
    }
    return `${when}: ${book.name}, ${
      row.routine_mode === "karma"
        ? "her gün farklı bölümlerden birer test"
        : "kaldığı yerden sırayla"
    } · ${cnt}.`;
  }
  const second = row.second_book_id
    ? allBooks.find((b) => b.id === row.second_book_id)?.name
    : null;
  const src = book
    ? `${book.name} kitabında kalınan konudan devam`
    : "kaynak serbest (öneride tüm kitaplar)";
  const tail = second
    ? ` Konu bitince ${second} ile aynı konu mu, sıradaki konu mu diye sorulur.`
    : book?.is_bank
      ? " Konu bitince kitapta sıradaki konuya geçer."
      : "";
  if (kind === "anchor") {
    return `${when} ${subject} okulda/dershanede işleniyor: öneri “bugün hangi konu işlendi?” diye sorar, ${src} · ${cnt}.${tail}`;
  }
  return `${when}: ${subject} konu çalışması — ${src} · ${cnt}.${tail}`;
}

const KIND_TR: Record<string, string> = {
  thread: "devam",
  next: "sıradaki",
  new: "yeni konu",
  weak: "tekrar",
};

/** Önerilerin isabeti: son 30 günde koçun hayaletlerde ne yaptığı. */
function AcceptanceLine({ report }: { report: GhostAcceptanceReport | undefined }) {
  if (!report || report.actions === 0) return null;
  const top1 = report.by_rank["1"] ?? 0;
  const kinds = Object.entries(report.by_kind)
    .filter(([, n]) => n > 0)
    .map(([k, n]) => `${KIND_TR[k] ?? k} ${n}`)
    .join(" · ");
  return (
    <span
      className="text-[11.5px] text-muted-foreground"
      data-testid="skeleton-acceptance"
      title={`Son 30 gün, tüm öğrencilerin: ${report.actions} öneri işlendi · başka konu ${report.other} · kaldırılan ${report.dismissed}${report.accepted > 0 ? ` — kabullerin ${top1}'i 1. çipten${kinds ? ` · ${kinds}` : ""}` : ""}`}
    >
      Öneri isabeti (30 gün): çipten kabul <b className="text-foreground">%{report.acceptance_pct ?? 0}</b>{" "}
      · {report.actions} öneri
    </span>
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
