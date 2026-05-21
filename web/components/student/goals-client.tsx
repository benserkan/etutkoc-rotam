"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  CheckCircle2,
  Loader2,
  PlusCircle,
  RotateCcw,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ErrorState } from "@/components/error-state";
import { getStudentGoals, studentKeys } from "@/lib/api/student";
import {
  useGoalCreate,
  useGoalProgress,
  useGoalToggle,
} from "@/lib/hooks/use-student-mutations";
import type {
  GoalItem,
  GoalKind,
  GoalListResponse,
} from "@/lib/types/student";
import { formatDate } from "@/lib/locale";

interface Props {
  initial: GoalListResponse;
}

type CreateKind = "weekly" | "daily" | "custom" | "topic";

const KIND_META: Record<
  GoalKind,
  { emoji: string; label: string }
> = {
  exam_target: { emoji: "🎯", label: "Sınav hedefi" },
  subject: { emoji: "📘", label: "Ders hedefi" },
  topic: { emoji: "📖", label: "Konu hedefi" },
  weekly: { emoji: "📅", label: "Haftalık" },
  daily: { emoji: "⏱️", label: "Günlük" },
  custom: { emoji: "⭐", label: "Özel" },
};

const CREATE_KINDS: { value: CreateKind; label: string }[] = [
  { value: "weekly", label: "Haftalık" },
  { value: "daily", label: "Günlük" },
  { value: "topic", label: "Konu" },
  { value: "custom", label: "Özel" },
];

export function GoalsClient({ initial }: Props) {
  const q = useQuery<GoalListResponse>({
    queryKey: studentKeys.goals(),
    queryFn: () => getStudentGoals(),
    initialData: initial,
    staleTime: 60_000,
  });
  const [createOpen, setCreateOpen] = React.useState(false);

  if (q.isError) {
    return <ErrorState onRetry={() => q.refetch()} />;
  }
  const data = q.data ?? initial;
  const active = data.items.filter((g) => g.status === "active");
  const achieved = data.items.filter((g) => g.status === "achieved");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1.5">
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
            Hedeflerim
          </h1>
          <p className="text-sm text-muted-foreground">
            Kendi hedeflerini koy, ilerleme oranını güncelle. Otomatik üretilmiş
            ders/sınav hedefleri burada gizli — koçunla birlikte yönetilir.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <PlusCircle /> Yeni hedef
        </Button>
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <SummaryPill label="Toplam" value={data.summary.total} />
        <SummaryPill label="Aktif" value={data.summary.active} />
        <SummaryPill label="Tamam" value={data.summary.achieved} accent="yolunda" />
        <SummaryPill
          label="Genel %"
          value={data.summary.overall_pct ?? 0}
          suffix="%"
        />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold">Aktif hedefler</h2>
        {active.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aktif hedefin yok. Üstteki <span className="font-medium">Yeni hedef</span> butonu ile başlayabilirsin.
          </p>
        ) : (
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {active.map((g) => (
              <GoalCard key={g.id} goal={g} />
            ))}
          </ul>
        )}
      </section>

      {achieved.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold">Tamamlanan hedefler</h2>
          <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {achieved.map((g) => (
              <GoalCard key={g.id} goal={g} />
            ))}
          </ul>
        </section>
      ) : null}

      <CreateDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  );
}

// =============================================================================
// GoalCard — progress slider + achieved toggle
// =============================================================================

function GoalCard({ goal }: { goal: GoalItem }) {
  const progress = useGoalProgress();
  const toggle = useGoalToggle();
  const meta = KIND_META[goal.kind];
  const isAchieved = goal.status === "achieved";
  const isAuto = goal.is_auto_generated;

  const [current, setCurrent] = React.useState<string>(
    goal.current_value !== null && goal.current_value !== undefined
      ? String(goal.current_value)
      : "",
  );

  function saveProgress() {
    const n = Number(current);
    if (!Number.isFinite(n)) return;
    progress.mutate({ goalId: goal.id, current_value: n });
  }

  return (
    <li
      className={cn(
        "rounded-lg border bg-card p-4 space-y-3",
        isAchieved ? "border-emerald-300/40 bg-emerald-50/40 dark:bg-emerald-950/10" : "border-border",
      )}
    >
      <div className="flex items-start gap-2.5">
        <span className="text-xl shrink-0" aria-hidden>
          {meta.emoji}
        </span>
        <div className="flex-1 min-w-0">
          <p
            className={cn(
              "font-medium leading-tight",
              isAchieved ? "line-through text-muted-foreground" : "",
            )}
          >
            {goal.title}
          </p>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground mt-0.5">
            {meta.label}
            {goal.target_date ? (
              <span className="inline-flex items-center gap-1 ml-2">
                <Calendar className="size-3" aria-hidden />
                {formatDate(goal.target_date)}
              </span>
            ) : null}
          </p>
        </div>
        <Button
          type="button"
          variant={isAchieved ? "ghost" : "outline"}
          size="sm"
          onClick={() => toggle.mutate({ goalId: goal.id, achieved: !isAchieved })}
          disabled={toggle.isPending}
          aria-label={isAchieved ? "Aktife al" : "Tamamlandı işaretle"}
        >
          {toggle.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : isAchieved ? (
            <RotateCcw aria-hidden />
          ) : (
            <CheckCircle2 aria-hidden />
          )}
          {isAchieved ? "Aktife al" : "Tamamlandı"}
        </Button>
      </div>

      {goal.description ? (
        <p className="text-sm text-muted-foreground">{goal.description}</p>
      ) : null}

      {goal.target_value !== null && goal.target_value !== undefined ? (
        <div className="space-y-1.5">
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-muted-foreground">İlerleme</span>
            <span className="tabular-nums">
              <span className="font-medium">
                {goal.current_value ?? 0}
              </span>
              {" / "}
              {goal.target_value}
              {goal.unit ? ` ${goal.unit}` : ""}
              {goal.progress_pct !== null && goal.progress_pct !== undefined
                ? ` · %${goal.progress_pct}`
                : ""}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className={cn(
                "h-full transition-all",
                isAchieved ? "bg-emerald-500" : "bg-primary",
              )}
              style={{ width: `${goal.progress_pct ?? 0}%` }}
              aria-hidden
            />
          </div>
          {!isAuto && !isAchieved ? (
            <div className="flex gap-1.5 pt-1">
              <Input
                type="number"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className="h-8 text-sm"
                aria-label="Mevcut değer"
              />
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={saveProgress}
                disabled={progress.isPending}
              >
                {progress.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                ) : null}
                Güncelle
              </Button>
            </div>
          ) : null}
          {isAuto ? (
            <p className="text-[11px] text-muted-foreground">
              Bu hedef sistem tarafından üretildi — elle güncellenemez.
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

// =============================================================================
// CreateDialog
// =============================================================================

function CreateDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useGoalCreate();
  const [title, setTitle] = React.useState("");
  const [kind, setKind] = React.useState<CreateKind>("weekly");
  const [target, setTarget] = React.useState("");
  const [current, setCurrent] = React.useState("");
  const [unit, setUnit] = React.useState("");
  const [targetDate, setTargetDate] = React.useState("");
  const [description, setDescription] = React.useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const t = title.trim();
    if (!t) return;
    create.mutate(
      {
        title: t,
        kind,
        description: description.trim() || null,
        target_value: target.trim() ? Number(target) : null,
        current_value: current.trim() ? Number(current) : null,
        unit: unit.trim() || null,
        target_date: targetDate.trim() || null,
      },
      {
        onSuccess: () => {
          setTitle("");
          setTarget("");
          setCurrent("");
          setUnit("");
          setTargetDate("");
          setDescription("");
          setKind("weekly");
          onClose();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Yeni hedef</DialogTitle>
            <DialogDescription>
              Haftalık ya da günlük somut bir hedef tanımla; ilerlemesini
              kontrol panelinden takip et.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="goal-title">Başlık</Label>
            <Input
              id="goal-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Bu hafta 25 test çöz"
              required
              autoFocus
              maxLength={255}
            />
          </div>

          <div className="space-y-2">
            <Label>Tip</Label>
            <div className="flex flex-wrap gap-2">
              {CREATE_KINDS.map((k) => (
                <button
                  key={k.value}
                  type="button"
                  onClick={() => setKind(k.value)}
                  className={cn(
                    "rounded-full px-3 py-1 text-sm transition-colors",
                    kind === k.value
                      ? "bg-foreground text-background"
                      : "bg-muted hover:bg-muted/70",
                  )}
                >
                  {k.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-2">
              <Label htmlFor="goal-target">Hedef değer</Label>
              <Input
                id="goal-target"
                type="number"
                step="any"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="25"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-current">Şu an</Label>
              <Input
                id="goal-current"
                type="number"
                step="any"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                placeholder="0"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-unit">Birim</Label>
              <Input
                id="goal-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="test"
                maxLength={20}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="goal-date">Hedef tarihi (opsiyonel)</Label>
            <Input
              id="goal-date"
              type="date"
              value={targetDate}
              onChange={(e) => setTargetDate(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="goal-desc">Açıklama (opsiyonel)</Label>
            <textarea
              id="goal-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              maxLength={500}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Vazgeç
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? <Loader2 className="animate-spin" /> : null}
              Hedef oluştur
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function SummaryPill({
  label,
  value,
  accent,
  suffix,
}: {
  label: string;
  value: number;
  accent?: "yolunda";
  suffix?: string;
}) {
  const bg =
    accent === "yolunda"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
      : "bg-muted text-foreground";
  return (
    <div className={cn("rounded-md px-3 py-2 flex items-baseline justify-between", bg)}>
      <span className="text-xs opacity-70">{label}</span>
      <span className="font-display font-bold tabular-nums">
        {value}
        {suffix ?? ""}
      </span>
    </div>
  );
}
