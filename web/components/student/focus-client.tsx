"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Award,
  CheckCircle2,
  Flame,
  Loader2,
  Square,
  StopCircle,
  Timer,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/error-state";
import { DemoHint } from "@/components/demos/demo-hint";
import { getStudentFocus, studentKeys } from "@/lib/api/student";
import {
  useFocusCancel,
  useFocusStart,
  useFocusStop,
} from "@/lib/hooks/use-student-mutations";
import type {
  FocusResponse,
  FocusSession,
  PomodoroKind,
} from "@/lib/types/student";

interface Props {
  initial: FocusResponse;
}

const PLAN_CHIPS = [15, 25, 50, 90];

/**
 * Pomodoro paneli — aktif seans yoksa başlatma formu; varsa büyük sayaç +
 * bitir/iptal aksiyonları.
 *
 * Sayaç stratejisi (kullanıcı kararı): setInterval throttle riskini engellemek
 * için her tick'te `now - started_at` farkı hesaplanır. Tab arka planda iken
 * dönünce zamanı kaybetmez.
 */
export function FocusClient({ initial }: Props) {
  const q = useQuery<FocusResponse>({
    queryKey: studentKeys.focus(),
    queryFn: () => getStudentFocus(),
    initialData: initial,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
  const data = q.data ?? initial;

  if (q.isError) {
    return <ErrorState onRetry={() => q.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          Odak (Pomodoro)
        </h1>
        <p className="text-sm text-muted-foreground">
          Çalışma seanslarını başlat, mola ver, akışın aksamasın. Bitirmeyi
          unuttuğun seansları sistem 3 saatte otomatik kapatır.
        </p>
        <DemoHint contextKey="focus" role="student" />
      </header>

      {data.active_session ? (
        <ActiveSessionCard session={data.active_session} />
      ) : (
        <StartCard />
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Stat label="Bugün odak (dk)" value={data.today.work_minutes} icon={<Timer className="size-4" aria-hidden />} />
        <Stat label="Üst üste gün" value={data.streak_days} icon={<Flame className="size-4 text-orange-500" aria-hidden />} />
        <Stat label="Puan" value={data.points} icon={<Award className="size-4 text-amber-500" aria-hidden />} />
      </div>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Son seanslar</h2>
        {data.recent_sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Henüz seans yok.</p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border bg-card">
            {data.recent_sessions.map((s) => (
              <RecentRow key={s.id} session={s} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

// =============================================================================
// ActiveSessionCard — büyük sayaç + bitir/iptal
// =============================================================================

function ActiveSessionCard({ session }: { session: FocusSession }) {
  const stop = useFocusStop();
  const cancel = useFocusCancel();

  // Sayaç — her saniye now - started farkını hesapla (setInterval throttle güvenli)
  const startedAt = React.useMemo(
    () => new Date(session.started_at).getTime(),
    [session.started_at],
  );
  const [elapsed, setElapsed] = React.useState(() =>
    Math.max(0, Math.floor((Date.now() - startedAt) / 1000)),
  );
  React.useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  const min = Math.floor(elapsed / 60);
  const sec = elapsed % 60;
  const plannedSec = session.planned_minutes * 60;
  const pct = plannedSec > 0 ? Math.min(100, Math.round((elapsed / plannedSec) * 100)) : 0;
  const overdue = elapsed >= plannedSec && plannedSec > 0;

  return (
    <div className="rounded-xl border border-primary/30 bg-card p-6 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="space-y-0.5">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            {KIND_LABELS[session.kind]} · {session.planned_minutes} dakika planlı
          </p>
          {session.label ? (
            <p className="text-sm font-medium">{session.label}</p>
          ) : null}
        </div>
        {overdue ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200 px-2 py-0.5 text-xs">
            <AlertTriangle className="size-3.5" aria-hidden /> Süre doldu
          </span>
        ) : null}
      </div>

      <div className="text-center">
        <p
          className="font-display tabular-nums text-7xl font-bold tracking-tight"
          aria-label={`Geçen süre ${min} dakika ${sec} saniye`}
        >
          {String(min).padStart(2, "0")}:{String(sec).padStart(2, "0")}
        </p>
      </div>

      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "h-full transition-all",
            overdue ? "bg-amber-400" : "bg-primary",
          )}
          style={{ width: `${pct}%` }}
          aria-hidden
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 justify-center">
        <Button
          onClick={() =>
            stop.mutate({
              sessionId: session.id,
              actual_minutes: Math.max(1, Math.floor(elapsed / 60)),
              interrupted: false,
            })
          }
          disabled={stop.isPending || cancel.isPending}
        >
          {stop.isPending ? <Loader2 className="animate-spin" /> : <CheckCircle2 />}
          Bitir
        </Button>
        <Button
          variant="outline"
          onClick={() => cancel.mutate({ sessionId: session.id })}
          disabled={stop.isPending || cancel.isPending}
        >
          {cancel.isPending ? <Loader2 className="animate-spin" /> : <StopCircle />}
          Yarıda terk et
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// StartCard — yeni seans başlat
// =============================================================================

function StartCard() {
  const start = useFocusStart();
  const [planned, setPlanned] = React.useState<number>(25);
  const [label, setLabel] = React.useState("");
  const [kind, setKind] = React.useState<PomodoroKind>("work");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    start.mutate({
      planned_minutes: planned,
      kind,
      label: label.trim() || null,
    });
  }

  return (
    <form
      onSubmit={submit}
      className="rounded-xl border border-border bg-card p-5 space-y-4"
    >
      <div className="space-y-2">
        <Label>Süre</Label>
        <div className="flex flex-wrap gap-2">
          {PLAN_CHIPS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setPlanned(m)}
              className={cn(
                "rounded-full px-3 py-1 text-sm transition-colors",
                planned === m
                  ? "bg-foreground text-background"
                  : "bg-muted hover:bg-muted/70",
              )}
            >
              {m} dk
            </button>
          ))}
          <Input
            type="number"
            min={5}
            max={120}
            value={planned}
            onChange={(e) => setPlanned(Number(e.target.value) || 25)}
            className="w-20"
            aria-label="Dakika"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label>Tür</Label>
        <div className="flex flex-wrap gap-2">
          {(["work", "short_break", "long_break"] as PomodoroKind[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm transition-colors",
                kind === k
                  ? "bg-foreground text-background"
                  : "bg-muted hover:bg-muted/70",
              )}
            >
              {KIND_LABELS[k]}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="focus-label">Etiket (opsiyonel)</Label>
        <Input
          id="focus-label"
          placeholder="Matematik · paragraf · vb."
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          maxLength={120}
        />
      </div>

      <Button type="submit" disabled={start.isPending}>
        {start.isPending ? <Loader2 className="animate-spin" /> : <Timer />}
        Seansı başlat
      </Button>
    </form>
  );
}

// =============================================================================
// Yardımcı parçalar
// =============================================================================

function Stat({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-1.5">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="font-display text-3xl font-bold tabular-nums">{value}</p>
    </div>
  );
}

function RecentRow({ session }: { session: FocusSession }) {
  const started = new Date(session.started_at).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <li className="flex items-center gap-3 px-4 py-2.5 text-sm">
      <Square
        className={cn(
          "size-3 shrink-0",
          session.interrupted ? "text-amber-500 fill-amber-500" : "text-emerald-500 fill-emerald-500",
        )}
        aria-hidden
      />
      <div className="flex-1 min-w-0">
        <p className="truncate">
          <span className="font-medium">{KIND_LABELS[session.kind]}</span>
          {session.label ? (
            <span className="text-muted-foreground"> · {session.label}</span>
          ) : null}
        </p>
        <p className="text-xs text-muted-foreground">{started}</p>
      </div>
      <p className="tabular-nums text-sm text-muted-foreground">
        {session.actual_minutes}/{session.planned_minutes} dk
        {session.interrupted ? " · yarıda" : ""}
      </p>
    </li>
  );
}

const KIND_LABELS: Record<PomodoroKind, string> = {
  work: "Odak",
  short_break: "Kısa mola",
  long_break: "Uzun mola",
};
