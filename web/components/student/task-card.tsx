"use client";

import * as React from "react";
import Link from "next/link";
import {
  BookX,
  CheckCircle2,
  CircleDashed,
  Clock,
  Hourglass,
  Lock,
  Minus,
  MoreHorizontal,
  Plus,
  Replace,
  SlidersHorizontal,
  Trash2,
  MessageCircle,
  ExternalLink,
  Trophy,
  Undo2,
} from "lucide-react";
import { linkButtonLabel } from "@/lib/task-links";
import { TaskVideoLinks } from "@/components/shared/task-video-links";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useCupResize, useCupReturn } from "@/lib/api/pool-student";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DenemeResultDialog,
  denemeSummary,
} from "@/components/shared/deneme-result-dialog";
import {
  CompleteSheet,
  type CompleteSheetResult,
} from "@/components/shared/complete-sheet";
import type { StudentTask, StudentTaskItem } from "@/lib/types/student";
import {
  useCompleteTask,
  useDebouncedSetItem,
  useSetItemCompleted,
  useSetDenemeResults,
  useUncompleteTask,
} from "@/lib/hooks/use-student-mutations";
import type { CommMode } from "./comm-modal";

/** Task-card içinden açılan modallar; "add" hep sayfa header'ından gelir. */
type TaskCommMode = Exclude<CommMode, "add">;

interface Props {
  task: StudentTask;
  dateIso: string;
  /** Talep modalını açmak için parent callback'i. */
  onOpenComm: (mode: TaskCommMode, task: StudentTask) => void;
}

/**
 * Tek görev kartı — başlık + tip rozeti + saat + kalem listesi + 3 aksiyon.
 *
 * Davranış:
 *   - `is_future_blocked` → tüm tikleme aksiyonları disable + lock ikonu
 *   - `is_past` → tikleme açık (geç işaretleme izni)
 *   - `has_pending_request` → sarı "Bekliyor" rozeti
 *   - status COMPLETED → kart hafif soluk
 */
export function TaskCard({ task, dateIso, onOpenComm }: Props) {
  const complete = useCompleteTask(dateIso);
  const uncomplete = useUncompleteTask(dateIso);
  const blocked = task.is_future_blocked;
  const isCompleted = task.status === "completed";
  const isPartial = task.status === "partial";
  // Tamamlayınca sonuç sor (2026-10-14): test birimli, sonucu girilmemiş ilk kalemin
  // doğru/yanlış/boş penceresi kendiliğinden açılır — "Sonucu girmeden geç" ile atlanabilir.
  // Sonuç girilmeyen test konu performansına doğruluk olarak yansımaz.
  const [askItemId, setAskItemId] = React.useState<number | null>(null);
  // Deneme görevi (D2): her deneme ayrı satır; işaretlerken sonuç penceresi açılır.
  const examItems = task.items.filter((it) => it.exam_kind);
  const isExamTask = examItems.length > 0;
  const [examOpen, setExamOpen] = React.useState(false);
  // Deneme görevi programda öne çıkar (2026-10-21): eski kayıtlar exam_kind taşımayabilir —
  // deneme kitabı / kitapsız tam deneme de "deneme" sayılır (görsel vurgu için).
  const denemeKind = examTaskKind(task);

  function toggleAll() {
    if (blocked) return;
    if (isCompleted) {
      uncomplete.mutate({ task });
    } else if (isExamTask) {
      setExamOpen(true);
    } else {
      const target = task.items.find(
        (it) =>
          ((it.is_test_unit ?? it.book_id != null) || it.unit === "soru") &&
          it.planned > 0 &&
          it.correct == null && it.wrong == null && it.blank == null,
      );
      complete.mutate({ task }, { onSuccess: () => { if (target) setAskItemId(target.id); } });
    }
  }

  return (
    <article
      data-deneme={denemeKind ?? undefined}
      className={cn(
        "rounded-lg border bg-card transition-opacity",
        isCompleted ? "border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/10" : "border-border",
        denemeKind && !isCompleted
          ? "border-indigo-300 border-l-4 border-l-indigo-600 bg-indigo-500/[0.06] shadow-sm dark:border-indigo-500/40 dark:border-l-indigo-400"
          : "",
        blocked ? "opacity-70" : "",
      )}
    >
      {denemeKind ? (
        <div className="flex items-center gap-2 rounded-t-lg bg-indigo-700 px-4 py-1.5 text-white">
          <Trophy className="size-3.5" aria-hidden />
          <span className="text-[11px] font-bold uppercase tracking-wider">
            {denemeKind === "genel" ? "Genel deneme" : "Branş denemesi"}
          </span>
          {examItems[0]?.question_count ? (
            <span className="text-[11px] text-indigo-100">
              · {examItems.length > 1 ? `${examItems.length} deneme × ` : ""}
              {examItems[0].question_count} soru
            </span>
          ) : null}
          <span className="ml-auto text-[11px] text-indigo-100">Sınav provası — süre tutarak çöz</span>
        </div>
      ) : null}
      <header className="flex items-start gap-3 px-4 py-3">
        <ToggleButton
          status={task.status}
          blocked={blocked}
          loading={complete.isPending || uncomplete.isPending}
          onClick={toggleAll}
        />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <h3
              className={cn(
                "font-medium leading-tight",
                isCompleted ? "line-through text-muted-foreground" : "",
              )}
            >
              {task.title || "—"}
            </h3>
            {denemeKind ? null : <TypeBadge type={task.type} unit={itemUnitOf(task)} />}
            {task.link_url && (task.videos?.length ?? 0) < 2 ? (
              <a
                href={task.link_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-full bg-cyan-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-cyan-700"
                title={task.link_url}
              >
                <ExternalLink className="size-3" aria-hidden="true" />
                {linkButtonLabel(task.type)}
              </a>
            ) : null}
            {task.scheduled_hour ? (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="size-3" aria-hidden="true" />
                {task.scheduled_hour}
              </span>
            ) : null}
            {task.has_pending_request ? <PendingBadge /> : null}
            {blocked ? <FutureLockedBadge /> : null}
          </div>
          <TaskVideoLinks videos={task.videos ?? []} />
          <p className="text-xs text-muted-foreground mt-1 tabular-nums">
            {task.completed_count} / {task.planned_count} {denemeKind ? "deneme çözüldü" : "tamam"} ·{" "}
            {Math.round(task.pct * 100)}%
          </p>
        </div>

        {/* Yanlış soru arşivi — menüde saklı kalmasın diye görünür kısayol
            (kullanıcı geri bildirimi: "görev kartında göremedim") */}
        <ArchiveWrongButton task={task} />

        <ActionsMenu
          task={task}
          blocked={blocked}
          isCompleted={isCompleted}
          onOpenComm={onOpenComm}
        />
      </header>

      <div className="border-t border-border/70 px-4 py-3 space-y-2">
        {isExamTask ? (
          <DenemeTaskRows
            task={task}
            dateIso={dateIso}
            blocked={blocked}
            open={examOpen}
            setOpen={setExamOpen}
          />
        ) : task.items.length > 0 ? (
          task.items.map((item) => (
            <ItemRow
              key={item.id}
              task={task}
              item={item}
              dateIso={dateIso}
              blocked={blocked}
              askResult={askItemId === item.id}
              onAskDone={() => setAskItemId(null)}
            />
          ))
        ) : (
          <ItemlessSolvedRow task={task} dateIso={dateIso} blocked={blocked} />
        )}
      </div>

      {/* Progress bar — alt şerit */}
      <div className="h-1 w-full bg-muted/50 rounded-b-lg overflow-hidden">
        <div
          className={cn(
            "h-full transition-all",
            isCompleted ? "bg-emerald-500" : isPartial ? "bg-amber-400" : "bg-primary/30",
          )}
          style={{ width: `${Math.round(task.pct * 100)}%` }}
          aria-hidden="true"
        />
      </div>
    </article>
  );
}

/** Görev bir deneme mi? branş/genel ya da null (vurgu için; eski kayıtlar da tanınır). */
function examTaskKind(task: StudentTask): "brans" | "genel" | null {
  const ex = task.items.find((it) => it.exam_kind);
  if (ex) return ex.exam_kind === "genel" ? "genel" : "brans";
  const b = task.items.find((it) => it.book_type === "brans_denemesi" || it.book_type === "genel_deneme");
  if (b) return b.book_type === "genel_deneme" ? "genel" : "brans";
  // Soru/sayfa birimli kaynaksız konu kalemi (topic_id dolu) deneme DEĞİL (2026-10-22).
  if (task.items.length > 0 && task.items.every((it) => it.book_id == null && it.is_test_unit === false && it.topic_id == null)) {
    return "genel";
  }
  return null;
}

// =============================================================================
// ToggleButton — sol baştaki büyük tikleme dairesi
// =============================================================================

function ToggleButton({
  status,
  blocked,
  loading,
  onClick,
}: {
  status: StudentTask["status"];
  blocked: boolean;
  loading: boolean;
  onClick: () => void;
}) {
  const label =
    status === "completed" ? "Geri al" : status === "partial" ? "Tamamla" : "Tamamla";
  const Icon =
    status === "completed" ? CheckCircle2 : status === "partial" ? Hourglass : CircleDashed;
  const color =
    status === "completed"
      ? "text-emerald-600 dark:text-emerald-300"
      : status === "partial"
        ? "text-amber-500"
        : "text-muted-foreground";

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onClick}
            disabled={blocked || loading}
            aria-label={label}
            className={cn(
              "shrink-0 size-7 grid place-items-center rounded-full border border-transparent hover:border-border hover:bg-muted transition-colors",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              color,
            )}
          >
            <Icon className={cn("size-6", loading ? "animate-pulse" : "")} aria-hidden="true" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="bottom">
          {blocked ? "O gün gelince tıklayabilirsin" : label}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// =============================================================================
// ItemlessSolvedRow — kalemsiz (etkinlik/diğer) görevde "çözdüğüm soru" girişi
// "olmayan kitaptan test" gibi durumda öğrenci çözdüğü soruyu kaydeder.
// =============================================================================

function ItemlessSolvedRow({
  task,
  dateIso,
  blocked,
}: {
  task: StudentTask;
  dateIso: string;
  blocked: boolean;
}) {
  const complete = useCompleteTask(dateIso);
  const current = task.solved_count ?? 0;
  const [editing, setEditing] = React.useState(false);
  const [val, setVal] = React.useState<number>(current);

  function save() {
    complete.mutate(
      { task, solvedCount: val > 0 ? val : null },
      { onSuccess: () => setEditing(false) },
    );
  }

  if (editing) {
    return (
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted-foreground">Çözdüğüm soru:</span>
        <input
          type="number"
          min={0}
          value={val}
          autoFocus
          onChange={(e) => setVal(Math.max(0, Number(e.target.value) || 0))}
          onKeyDown={(e) => { if (e.key === "Enter") save(); }}
          className="h-8 w-20 rounded-md border border-input bg-background px-2 text-sm tabular-nums focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button size="sm" className="h-8" onClick={save} disabled={complete.isPending}>
          Kaydet
        </Button>
        <button
          type="button"
          onClick={() => { setVal(current); setEditing(false); }}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Vazgeç
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      {current > 0 ? (
        <>
          <span className="text-muted-foreground">Çözülen soru:</span>
          <span className="font-medium tabular-nums text-emerald-700 dark:text-emerald-400">
            {current}
          </span>
          {!blocked ? (
            <button
              type="button"
              onClick={() => { setVal(current); setEditing(true); }}
              className="text-xs text-cyan-700 hover:underline dark:text-cyan-400"
            >
              düzenle
            </button>
          ) : null}
        </>
      ) : (
        <button
          type="button"
          onClick={() => { setVal(0); setEditing(true); }}
          disabled={blocked}
          className="text-xs text-cyan-700 hover:underline disabled:opacity-50 disabled:no-underline dark:text-cyan-400"
        >
          + Çözdüğüm soru sayısını gir
        </button>
      )}
    </div>
  );
}

// =============================================================================
// ItemRow — tek kalem +/− kontrolleri
// =============================================================================

function ItemRow({
  task,
  item,
  dateIso,
  blocked,
  askResult = false,
  onAskDone,
}: {
  task: StudentTask;
  item: StudentTaskItem;
  dateIso: string;
  blocked: boolean;
  /** Görev az önce tamamlandı → sonuç penceresini kendiliğinden aç */
  askResult?: boolean;
  onAskDone?: () => void;
}) {
  const debounced = useDebouncedSetItem(dateIso);
  const setItem = useSetItemCompleted(dateIso);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const max = item.planned;
  const min = 0;

  // Kitapsız deneme kaleminde de D/Y mantıklı (TYT branş denemesi → 40 soru/35 D/5 Y).
  // Kaynaksız KONULU kalem (kitapsız ama konusu var) denemedir değil, test birimidir.
  const isDeneme = item.is_test_unit === false || (item.is_test_unit == null && item.book_id == null);
  const hasResult =
    item.correct != null || item.wrong != null || item.blank != null;
  // Kaynaksız konulu kalemin birimi (2026-10-22): sayfada D/Y yok, aralık gösterilir.
  const unit = item.book_id == null && item.unit ? item.unit : "test";
  const pageRange =
    unit === "sayfa" && item.page_from && item.page_to ? `s. ${item.page_from}–${item.page_to}` : null;

  function inc() {
    if (blocked || item.completed >= max) return;
    debounced.apply({ task, itemId: item.id, completed: item.completed + 1 });
  }
  function dec() {
    if (blocked || item.completed <= min) return;
    debounced.apply({ task, itemId: item.id, completed: item.completed - 1 });
  }

  function handleSheetSubmit(r: CompleteSheetResult) {
    setItem.mutate(
      {
        task,
        itemId: item.id,
        completed: r.completed,
        correct: r.correct,
        wrong: r.wrong,
        blank: r.blank,
      },
      {
        onSuccess: () => {
          setSheetOpen(false);
          onAskDone?.();
        },
      },
    );
  }

  return (
    <>
      <div className="flex items-center gap-3 text-sm">
        <div className="flex-1 min-w-0">
          <p className="truncate">
            <span className="font-medium">{item.book_name}</span>
            {item.section_label ? (
              <span className="text-muted-foreground"> · {item.section_label}</span>
            ) : null}
          </p>
          {item.topic_name ? (
            <p className="text-xs text-muted-foreground truncate">{item.topic_name}</p>
          ) : null}
          {pageRange ? (
            <p className="text-xs font-semibold tabular-nums text-foreground">{pageRange}</p>
          ) : null}
          {/* D/Y rozeti veya "+ doğru/yanlış" linki — yalnız completed > 0 ise göster */}
          {item.completed > 0 && unit !== "sayfa" ? (
            <ResultBadge
              correct={item.correct}
              wrong={item.wrong}
              blank={item.blank}
              completed={item.completed}
              onEdit={() => setSheetOpen(true)}
              blocked={blocked}
            />
          ) : null}
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="size-7"
            disabled={blocked || item.completed <= min}
            onClick={dec}
            aria-label="Bir azalt"
          >
            <Minus className="size-3.5" aria-hidden="true" />
          </Button>
          <span className="tabular-nums text-sm font-medium min-w-[3.5rem] text-center">
            {item.completed} / {item.planned}
            {unit !== "test" ? <span className="ml-0.5 text-[11px] text-muted-foreground">{unit}</span> : null}
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            className="size-7"
            disabled={blocked || item.completed >= max}
            onClick={inc}
            aria-label="Bir arttır"
          >
            <Plus className="size-3.5" aria-hidden="true" />
          </Button>
          {/* Sheet trigger — "Sayıyla tamamla" / "Sonucu düzenle" */}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-7"
            disabled={blocked}
            onClick={() => setSheetOpen(true)}
            aria-label={hasResult ? "Sonucu düzelt" : "Çözdüğüm sayı ve sonuç"}
            title={hasResult ? "Sonucu düzelt" : "Sayıyla tamamla"}
          >
            <SlidersHorizontal
              className={cn(
                "size-3.5",
                hasResult ? "text-emerald-600 dark:text-emerald-300" : "text-muted-foreground",
              )}
              aria-hidden="true"
            />
          </Button>
        </div>
      </div>

      <CompleteSheet
        open={sheetOpen || askResult}
        onClose={() => {
          setSheetOpen(false);
          onAskDone?.();
        }}
        onSubmit={handleSheetSubmit}
        taskTitle={task.title}
        itemLabel={
          item.book_name +
          (item.section_label ? ` · ${item.section_label}` : "")
        }
        planned={item.planned}
        initialCompleted={item.completed > 0 ? item.completed : item.planned}
        initialCorrect={item.correct}
        initialWrong={item.wrong}
        initialBlank={item.blank}
        isDeneme={isDeneme}
        unit={unit}
        pageRange={pageRange}
        saving={setItem.isPending}
      />
    </>
  );
}

/**
 * D/Y rozeti — completed > 0 ise gösterilir.
 * - D/Y girilmişse: yeşil rozet "8 ✓ / 2 ✗" + "düzelt" linki
 * - Girilmemişse: küçük "+ doğru/yanlış" linki (sonradan düzeltme)
 */
function ResultBadge({
  correct,
  wrong,
  blank,
  completed,
  onEdit,
  blocked,
}: {
  correct: number | null;
  wrong: number | null;
  blank: number | null;
  completed: number;
  onEdit: () => void;
  blocked: boolean;
}) {
  const hasResult = correct != null || wrong != null || blank != null;
  void completed;
  if (!hasResult) {
    return (
      <button
        type="button"
        onClick={onEdit}
        disabled={blocked}
        className="mt-1 inline-flex items-center gap-1 rounded-full bg-amber-500 px-2 py-0.5 text-[11px] font-semibold text-amber-950 transition hover:bg-amber-400 disabled:opacity-40"
        title="Sonuç girilmeyen test konu performansına doğruluk olarak yansımaz"
      >
        <Plus className="size-2.5" aria-hidden />
        doğru/yanlış/boş gir
      </button>
    );
  }
  const c = correct ?? 0;
  const w = wrong ?? 0;
  const b = blank ?? 0;
  return (
    <button
      type="button"
      onClick={onEdit}
      disabled={blocked}
      className="inline-flex items-center gap-1.5 mt-0.5 text-[11px] tabular-nums hover:underline disabled:opacity-40"
      title="Sonucu düzelt"
    >
      <span className="text-emerald-700 dark:text-emerald-300 font-medium">{c} doğru</span>
      <span className="text-muted-foreground/60">·</span>
      <span className="text-rose-700 dark:text-rose-300 font-medium">{w} yanlış</span>
      {b > 0 ? (
        <>
          <span className="text-muted-foreground/60">·</span>
          <span className="text-muted-foreground">{b} boş</span>
        </>
      ) : null}
    </button>
  );
}

// =============================================================================
// Type rozeti + Pending rozeti + Future lock rozeti
// =============================================================================

function TypeBadge({ type, unit }: { type: StudentTask["type"]; unit?: "soru" | "sayfa" | null }) {
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
      {unit === "sayfa" ? "Sayfa" : unit === "soru" ? "Soru" : (TASK_TYPE_LABEL[type] ?? "Görev")}
    </span>
  );
}

/** Kaynaksız konulu görev soru/sayfa birimliyse rozet birimi gösterir (2026-10-22). */
function itemUnitOf(task: StudentTask): "soru" | "sayfa" | null {
  const it = task.items.find((x) => x.book_id == null && x.topic_id != null);
  return it && (it.unit === "soru" || it.unit === "sayfa") ? it.unit : null;
}

const TASK_TYPE_LABEL: Record<StudentTask["type"], string> = {
  test: "Test",
  video: "Video dersi",
  ozet: "Özet",
  tekrar: "Tekrar",
  other: "Diğer",
};

function PendingBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200 px-2 py-0.5 text-[10px] font-medium">
      <Clock className="size-3" aria-hidden="true" />
      Bekliyor
    </span>
  );
}

function FutureLockedBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 px-2 py-0.5 text-[10px] font-medium">
      <Lock className="size-3" aria-hidden="true" />
      Gelecek
    </span>
  );
}

// =============================================================================
// ActionsMenu — change/replace/remove/question için kullanıcı dostu mini popup
//
// Radix dropdown-menu yerine basit toggle button + popover yapısı: küçük yüzey,
// erişilebilir, mobil-dostu. Dropdown primitive'i Paket 7'de book grid satır
// menülerinde de kullanılacak; o dalgada ortak hale getirilecek.
// =============================================================================

function ActionsMenu({
  task,
  blocked,
  isCompleted,
  onOpenComm,
}: {
  task: StudentTask;
  blocked: boolean;
  isCompleted: boolean;
  onOpenComm: (mode: TaskCommMode, task: StudentTask) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const canChangeOrReplaceOrRemove = !isCompleted && !task.has_pending_request;
  const [resizeOpen, setResizeOpen] = React.useState(false);
  const cupReturn = useCupReturn();

  // Haftalık havuz: kap görevini öğrenci kendisi kurdu → sayı/çıkar REHBERE TALEP değildir,
  // öğrenci doğrudan düzeltir (talep menüsü yerine kendi eylemleri).
  if (task.pool_item_id != null) {
    const done = task.items.reduce((a, it) => a + it.completed, 0);
    const resizable = task.items.length === 1 && task.pool_max_count != null;
    return (
      <div className="relative" ref={ref}>
        <Button type="button" variant="ghost" size="icon" className="size-7" aria-label="Görev eylemleri"
                onClick={() => setOpen((o) => !o)}>
          <MoreHorizontal className="size-4" aria-hidden="true" />
        </Button>
        {open ? (
          <div role="menu" className="absolute right-0 z-20 mt-1 w-56 rounded-md border border-border bg-popover p-1 shadow-md">
            {resizable ? (
              <MenuItem
                label="Bugünkü sayıyı değiştir"
                icon={<CircleDashed className="size-3.5" />}
                disabled={isCompleted || blocked}
                disabledReason={isCompleted ? "Tamamlanmış görev — işaretlediğin sayıyı düzeltmek için − düğmesini kullan" : blocked ? "Gelecek tarihli görev" : undefined}
                onClick={() => { setOpen(false); setResizeOpen(true); }}
              />
            ) : null}
            <MenuItem
              label="Havuza geri al"
              icon={<Undo2 className="size-3.5" />}
              disabled={done > 0 || isCompleted || cupReturn.isPending}
              disabledReason={done > 0 ? "İşaretlediğin kısım var; kalan gün sonunda havuza kendiliğinden döner" : undefined}
              onClick={() => { setOpen(false); cupReturn.mutate({ task_id: task.id }); }}
            />
            <div className="my-1 h-px bg-border" aria-hidden="true" />
            <MenuItem
              label="Koçuna sor"
              icon={<MessageCircle className="size-3.5" />}
              onClick={() => { setOpen(false); onOpenComm("question", task); }}
            />
            <MenuItem
              label="Yanlışı arşivle"
              icon={<BookX className="size-3.5" />}
              onClick={() => { setOpen(false); window.location.href = wrongArchiveHref(task); }}
            />
          </div>
        ) : null}
        {resizeOpen ? (
          <CupResizeDialog task={task} done={done} onClose={() => setResizeOpen(false)} />
        ) : null}
      </div>
    );
  }

  // Tip-aware menü görünürlüğü:
  // - "Sayıyı değiştir" → görevde **en az bir sayı kalemi** olmalı (Test, Deneme).
  //   Video/Özet/Tekrar/Diğer items=[] → bu seçenek gizli.
  // - "Kaynağı değiştir" → görevde **en az bir kitaplı kalem** olmalı (Test).
  //   Deneme (kitapsız etiket) + Video/Özet/Tekrar/Diğer → bu seçenek gizli.
  const hasItems = task.items.length > 0;
  const hasBookItem = task.items.some((it) => it.book_id != null);
  const showChange = hasItems;
  const showReplace = hasBookItem;

  return (
    <div className="relative" ref={ref}>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="size-7"
        aria-label="Görev eylemleri"
        onClick={() => setOpen((o) => !o)}
      >
        <MoreHorizontal className="size-4" aria-hidden="true" />
      </Button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-border bg-popover p-1 shadow-md"
        >
          {showChange ? (
            <MenuItem
              label="Sayıyı değiştir"
              icon={<CircleDashed className="size-3.5" />}
              disabled={!canChangeOrReplaceOrRemove || blocked}
              onClick={() => {
                setOpen(false);
                onOpenComm("change", task);
              }}
              disabledReason={
                task.has_pending_request
                  ? "Bu görev için zaten bekleyen talep var"
                  : isCompleted
                    ? "Tamamlanmış görevde değişiklik yok"
                    : blocked
                      ? "Gelecek tarihli görev"
                      : undefined
              }
            />
          ) : null}
          {showReplace ? (
            <MenuItem
              label="Kaynağı değiştir"
              icon={<Replace className="size-3.5" />}
              disabled={!canChangeOrReplaceOrRemove || blocked}
              onClick={() => {
                setOpen(false);
                onOpenComm("replace", task);
              }}
            />
          ) : null}
          <MenuItem
            label="Çıkar"
            icon={<Trash2 className="size-3.5" />}
            destructive
            disabled={!canChangeOrReplaceOrRemove || blocked}
            onClick={() => {
              setOpen(false);
              onOpenComm("remove", task);
            }}
          />
          {(showChange || showReplace) ? (
            <div className="my-1 h-px bg-border" aria-hidden="true" />
          ) : null}
          <MenuItem
            label="Koçuna sor"
            icon={<MessageCircle className="size-3.5" />}
            onClick={() => {
              setOpen(false);
              onOpenComm("question", task);
            }}
          />
          <MenuItem
            label="Yanlışı arşivle"
            icon={<BookX className="size-3.5" />}
            onClick={() => {
              setOpen(false);
              window.location.href = wrongArchiveHref(task);
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

/** Kap görevinin bugünkü sayısını düzelt — alt sınır işaretlenen, üst sınır havuzdaki kalan. */
function CupResizeDialog({ task, done, onClose }: { task: StudentTask; done: number; onClose: () => void }) {
  const resize = useCupResize();
  const planned = task.items[0]?.planned ?? 1;
  const max = Math.max(planned, task.pool_max_count ?? planned);
  const min = Math.max(1, done);
  const [val, setVal] = React.useState(planned);
  const opts = Array.from({ length: Math.min(max, 12) - min + 1 }, (_, i) => min + i);
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Bugün kaç tane?</DialogTitle>
          <DialogDescription>
            {task.title} — kaba {planned} almıştın. Bugün yapacağın sayıyı seç; kalan havuzda bekler.
            {done > 0 ? ` ${done} tanesini işaretledin, daha aza inemez.` : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Bugünkü sayı">
          {opts.map((n) => (
            <button key={n} type="button" role="radio" aria-checked={val === n} onClick={() => setVal(n)}
                    className={cn("min-w-10 rounded-md border px-3 py-1.5 text-sm font-semibold tabular-nums",
                      val === n ? "border-transparent bg-cyan-700 text-white" : "bg-background text-foreground hover:bg-muted")}>
              {n}
            </button>
          ))}
          {max > 12 ? (
            <Input type="number" min={min} max={max} value={val} aria-label="Başka sayı" className="h-9 w-20"
                   onChange={(e) => { const n = Number(e.target.value); if (Number.isInteger(n)) setVal(n); }} />
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">En az {min}, en fazla {max} (havuzdaki kalan).</p>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
          <Button disabled={resize.isPending || val === planned || val < min || val > max}
                  className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
                  onClick={() => resize.mutate({ task_id: task.id, count: val }, { onSuccess: onClose })}>
            {val} yap
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Görev bağlamıyla Yanlış Soru Arşivi'ne gidiş URL'i.
 * İlk kitaplı kalemden ders+konu otomatik etiketlenir; kitapsız görevde
 * (video/deneme/etkinlik) yalnız görev bağı taşınır.
 */
function wrongArchiveHref(task: StudentTask): string {
  const first = task.items.find((it) => it.section_id != null);
  const sp = new URLSearchParams({ add: "1", task_id: String(task.id) });
  if (first?.book_id) sp.set("book_id", String(first.book_id));
  if (first?.section_id) sp.set("section_id", String(first.section_id));
  return `/student/wrong-questions?${sp.toString()}`;
}

/** Görev kartındaki görünür "yanlışı arşivle" kısayolu. */
function ArchiveWrongButton({ task }: { task: StudentTask }) {
  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            asChild
            variant="ghost"
            size="icon"
            className="size-7 text-muted-foreground hover:bg-rose-500/10 hover:text-rose-600"
          >
            <Link
              href={wrongArchiveHref(task)}
              aria-label="Bu görevden yanlış soru arşivle"
            >
              <BookX className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          Yanlış soruyu arşivle — fotoğrafını çek, sistem tekrar sorsun
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function MenuItem({
  label,
  icon,
  onClick,
  disabled,
  destructive,
  disabledReason,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  destructive?: boolean;
  disabledReason?: string;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      title={disabled ? disabledReason : undefined}
      className={cn(
        "flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-left transition-colors",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        destructive
          ? "text-destructive hover:bg-destructive/10"
          : "hover:bg-muted",
      )}
    >
      <span className="text-muted-foreground" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );
}


// =============================================================================
// Deneme görevi (D2) — her deneme bir satır + ortak sonuç penceresi
// =============================================================================

function DenemeTaskRows({
  task,
  dateIso,
  blocked,
  open,
  setOpen,
}: {
  task: StudentTask;
  dateIso: string;
  blocked: boolean;
  open: boolean;
  setOpen: (v: boolean) => void;
}) {
  const save = useSetDenemeResults(dateIso);
  const items = task.items.filter((it) => it.exam_kind);
  const pending = items.filter((it) => it.result_pending).length;
  const q = items[0]?.question_count;

  function rowLabel(it: StudentTaskItem): string {
    return it.section_label || it.book_name || "Deneme";
  }

  return (
    <>
      <ul className="space-y-1.5" aria-label="Denemeler">
        {items.map((it) => {
          const sm = denemeSummary({
            completed: it.completed, correct: it.correct, wrong: it.wrong, blank: it.blank,
            net: it.net, durationMinutes: it.duration_minutes, resultPending: it.result_pending,
          });
          return (
            <li key={it.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="min-w-0 break-words">{rowLabel(it)}</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium tabular-nums",
                  sm.tone === "done"
                    ? "bg-emerald-600 text-white"
                    : sm.tone === "pending"
                      ? "bg-amber-500 text-amber-950"
                      : "bg-muted text-muted-foreground",
                )}
              >
                {sm.text}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        <p className="text-xs text-muted-foreground">
          {q ? `Deneme başına ${q} soru` : "Deneme"}
          {pending > 0 ? ` · ${pending} denemenin sonucu bekleniyor` : ""}
        </p>
        <Button
          type="button"
          size="sm"
          disabled={blocked}
          onClick={() => setOpen(true)}
          className="bg-cyan-700 text-white hover:bg-cyan-800"
        >
          {items.some((it) => it.completed > 0) ? "Sonuçları düzenle" : "Sonuçları gir"}
        </Button>
      </div>
      <DenemeResultDialog
        open={open}
        onClose={() => setOpen(false)}
        title={task.title || "Deneme sonuçları"}
        saving={save.isPending}
        rows={items.map((it) => ({
          id: it.id,
          label: rowLabel(it),
          examSection: it.exam_section,
          questionCount: it.question_count,
          completed: it.completed,
          correct: it.correct,
          wrong: it.wrong,
          blank: it.blank,
          durationMinutes: it.duration_minutes,
        }))}
        onSubmit={(rows) => save.mutate({ task, rows }, { onSuccess: () => setOpen(false) })}
      />
    </>
  );
}
