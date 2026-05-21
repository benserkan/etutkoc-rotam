"use client";

import * as React from "react";
import {
  CheckCircle2,
  CircleDashed,
  Clock,
  Hourglass,
  Lock,
  Minus,
  MoreHorizontal,
  Plus,
  Replace,
  Trash2,
  MessageCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { StudentTask, StudentTaskItem } from "@/lib/types/student";
import {
  useCompleteTask,
  useDebouncedSetItem,
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

  function toggleAll() {
    if (blocked) return;
    if (isCompleted) {
      uncomplete.mutate({ task });
    } else {
      complete.mutate({ task });
    }
  }

  return (
    <article
      className={cn(
        "rounded-lg border bg-card transition-opacity",
        isCompleted ? "border-emerald-200 bg-emerald-50/40 dark:bg-emerald-950/10" : "border-border",
        blocked ? "opacity-70" : "",
      )}
    >
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
            <TypeBadge type={task.type} />
            {task.scheduled_hour ? (
              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="size-3" aria-hidden="true" />
                {task.scheduled_hour}
              </span>
            ) : null}
            {task.has_pending_request ? <PendingBadge /> : null}
            {blocked ? <FutureLockedBadge /> : null}
          </div>
          <p className="text-xs text-muted-foreground mt-1 tabular-nums">
            {task.completed_count} / {task.planned_count} tamam ·{" "}
            {Math.round(task.pct * 100)}%
          </p>
        </div>

        <ActionsMenu
          task={task}
          blocked={blocked}
          isCompleted={isCompleted}
          onOpenComm={onOpenComm}
        />
      </header>

      <div className="border-t border-border/70 px-4 py-3 space-y-2">
        {task.items.map((item) => (
          <ItemRow
            key={item.id}
            task={task}
            item={item}
            dateIso={dateIso}
            blocked={blocked}
          />
        ))}
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
      ? "text-emerald-600"
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
// ItemRow — tek kalem +/− kontrolleri
// =============================================================================

function ItemRow({
  task,
  item,
  dateIso,
  blocked,
}: {
  task: StudentTask;
  item: StudentTaskItem;
  dateIso: string;
  blocked: boolean;
}) {
  const debounced = useDebouncedSetItem(dateIso);
  const max = item.planned;
  const min = 0;

  function inc() {
    if (blocked || item.completed >= max) return;
    debounced.apply({ task, itemId: item.id, completed: item.completed + 1 });
  }
  function dec() {
    if (blocked || item.completed <= min) return;
    debounced.apply({ task, itemId: item.id, completed: item.completed - 1 });
  }

  return (
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
      </div>
    </div>
  );
}

// =============================================================================
// Type rozeti + Pending rozeti + Future lock rozeti
// =============================================================================

function TypeBadge({ type }: { type: StudentTask["type"] }) {
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide">
      {TASK_TYPE_LABEL[type] ?? "Görev"}
    </span>
  );
}

const TASK_TYPE_LABEL: Record<StudentTask["type"], string> = {
  test: "Test",
  video: "Video",
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
          <MenuItem
            label="Kaynağı değiştir"
            icon={<Replace className="size-3.5" />}
            disabled={!canChangeOrReplaceOrRemove || blocked}
            onClick={() => {
              setOpen(false);
              onOpenComm("replace", task);
            }}
          />
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
          <div className="my-1 h-px bg-border" aria-hidden="true" />
          <MenuItem
            label="Koçuna sor"
            icon={<MessageCircle className="size-3.5" />}
            onClick={() => {
              setOpen(false);
              onOpenComm("question", task);
            }}
          />
        </div>
      ) : null}
    </div>
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
