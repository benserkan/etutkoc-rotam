"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Compass,
  ChevronDown,
  Loader2,
  Plus,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { getTeacherNextUnits, teacherKeys } from "@/lib/api/teacher";
import { useCreateTask } from "@/lib/hooks/use-teacher-mutations";
import type {
  NextUnitItem,
  NextUnitsResponse,
  TeacherStudentWeekDay,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

function fmtDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return d && m ? `${d}.${m}` : iso;
}

/**
 * Sıradaki üniteler (Faz 2) — program yaparken müfredatta sıradaki atanabilir
 * konular. Her ünite resmi sırada, tamamlanmamış, kaynaklı; tek tıkla göreve
 * dönüşür. "AI önceliklendir" (kredili) → performans+sınav+sıra dengesiyle sırala.
 * Varsayılan kapalı. Aday yoksa görünmez.
 */
export function NextUnitsPanel({
  studentId,
  weekDays,
}: {
  studentId: number;
  weekDays: TeacherStudentWeekDay[];
}) {
  const qc = useQueryClient();
  const q = useQuery<NextUnitsResponse>({
    queryKey: teacherKeys.studentNextUnits(studentId),
    queryFn: () => getTeacherNextUnits(studentId),
    staleTime: 30_000,
  });
  const [expanded, setExpanded] = React.useState(false);
  const [assignFor, setAssignFor] = React.useState<NextUnitItem | null>(null);

  // eslint-disable-next-line lgs/missing-invalidate -- setQueryData ile doğrudan güncellenir (öneri sıralaması, yan etkisiz)
  const aiMut = useMutation<NextUnitsResponse, ApiError, void>({
    mutationFn: () =>
      api<NextUnitsResponse>(
        `/api/v2/teacher/students/${studentId}/next-units/ai-prioritize`,
        { method: "POST", body: "{}" },
      ),
    onError: (err) => {
      const code = err.detail?.code;
      if (code === "plan_upgrade_required") toast.error("AI ücretli pakette — paketinizi yükseltin");
      else if (code === "consent_required") toast.error("AI için önce rıza vermelisiniz (Hesabım)");
      else if (code === "ai_credit_exhausted") toast.error("AI kredin bitti — paketini yükselt");
      else toast.error("AI önceliklendirme yapılamadı");
    },
    onSuccess: (res) => {
      qc.setQueryData(teacherKeys.studentNextUnits(studentId), res);
      toast.success("AI öncelik sırası hazır");
    },
  });

  const data = aiMut.data ?? q.data;
  const units = data?.units ?? [];
  if (q.isLoading || units.length === 0) return null;

  return (
    <div className="border-b border-cyan-200 bg-cyan-50/50">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-left transition hover:bg-cyan-100/50"
        aria-expanded={expanded}
      >
        <Compass className="size-4 shrink-0 text-cyan-700" aria-hidden />
        <span className="min-w-0 flex-1 text-sm font-medium text-cyan-900">
          Sıradaki üniteler ({units.length})
          <span className="ml-1 font-normal text-cyan-700">· müfredatta sırada</span>
        </span>
        <ChevronDown
          className={cn("size-4 shrink-0 text-cyan-600 transition-transform", expanded && "rotate-180")}
          aria-hidden
        />
      </button>

      {!expanded ? null : (
        <>
          <div className="flex items-center justify-between gap-2 px-4 pb-2">
            <p className="text-[11px] text-cyan-800">
              Müfredat sırasındaki atanabilir konular. “Ata” ile göreve çevir.
            </p>
            <button
              type="button"
              onClick={() => aiMut.mutate()}
              disabled={aiMut.isPending}
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-violet-300 px-2 py-1 text-[11px] font-medium text-violet-700 transition hover:bg-violet-50"
            >
              {aiMut.isPending ? (
                <Loader2 className="size-3 animate-spin" aria-hidden />
              ) : (
                <Sparkles className="size-3" aria-hidden />
              )}
              AI önceliklendir
            </button>
          </div>

          {data?.ai_used && data.ai_summary ? (
            <p className="mx-3 mb-2 rounded-md bg-violet-50 px-2.5 py-1.5 text-[11px] text-violet-800">
              <Sparkles className="mr-1 inline size-3" aria-hidden />
              {data.ai_summary}
            </p>
          ) : null}

          <ul className="space-y-1 px-3 pb-3">
            {units.map((u) => (
              <li
                key={u.topic_id}
                className="rounded-md border border-cyan-200 bg-white px-2.5 py-2 text-xs"
              >
                <div className="flex items-start gap-2">
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium text-slate-900">
                      {u.ai_priority ? (
                        <span className="mr-1 rounded bg-violet-100 px-1 text-[10px] font-bold text-violet-700">
                          {u.ai_priority}
                        </span>
                      ) : null}
                      {u.subject_name} · {u.topic_name}
                    </span>
                    <span className="block text-slate-500">
                      {u.status === "devam" ? `devam · ${u.completed}/${u.test_total} test` : "başlanmadı"}
                    </span>
                    {u.ai_reason ? (
                      <span className="mt-0.5 block text-[11px] text-violet-700">↳ {u.ai_reason}</span>
                    ) : null}
                  </span>
                  <button
                    type="button"
                    onClick={() => setAssignFor(u)}
                    disabled={u.sections.every((s) => s.remaining <= 0)}
                    className="inline-flex shrink-0 items-center gap-1 rounded-md bg-cyan-600 px-2 py-1 text-[11px] font-semibold text-white transition hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-cyan-300"
                  >
                    <Plus className="size-3" aria-hidden />
                    Ata
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      <AssignDialog
        unit={assignFor}
        studentId={studentId}
        weekDays={weekDays}
        onClose={() => setAssignFor(null)}
        onDone={() => {
          setAssignFor(null);
          qc.invalidateQueries({ queryKey: teacherKeys.studentNextUnits(studentId) });
        }}
      />
    </div>
  );
}

function AssignDialog({
  unit,
  studentId,
  weekDays,
  onClose,
  onDone,
}: {
  unit: NextUnitItem | null;
  studentId: number;
  weekDays: TeacherStudentWeekDay[];
  onClose: () => void;
  onDone: () => void;
}) {
  const open = unit !== null;
  const create = useCreateTask(studentId);
  const selectableDays = React.useMemo(() => weekDays.filter((d) => !d.is_past), [weekDays]);

  // ilk kapasiteli section
  const firstSection = unit?.sections.find((s) => s.remaining > 0) ?? unit?.sections[0] ?? null;
  const [day, setDay] = React.useState("");
  const [sectionId, setSectionId] = React.useState<number | null>(null);
  const [count, setCount] = React.useState(5);

  const [lastKey, setLastKey] = React.useState<number | null>(null);
  if (unit && unit.topic_id !== lastKey) {
    setLastKey(unit.topic_id);
    const today = selectableDays.find((d) => d.is_today);
    setDay(today?.date ?? selectableDays[0]?.date ?? "");
    setSectionId(firstSection?.section_id ?? null);
    const rem = firstSection?.remaining ?? 5;
    setCount(Math.max(1, Math.min(rem || 5, 5)));
  }

  const sec = unit?.sections.find((s) => s.section_id === sectionId) ?? firstSection;

  function onAssign() {
    if (!unit || !day || !sec) return;
    create.mutate(
      {
        body: {
          date: day,
          type: "test",
          title: "—",
          items: [{ book_id: sec.book_id, section_id: sec.section_id, planned_count: count }],
        },
      },
      {
        onSuccess: () => {
          toast.success(`${unit.topic_name} → ${fmtDate(day)} (${count} test)`);
          onDone();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-base">Üniteyi ata</DialogTitle>
        </DialogHeader>
        {unit ? (
          <p className="-mt-1 text-xs text-muted-foreground">
            {unit.subject_name} · {unit.topic_name}
          </p>
        ) : null}

        <div className="space-y-3">
          {unit && unit.sections.length > 1 ? (
            <label className="block">
              <span className="text-xs font-medium text-foreground">Kaynak</span>
              <select
                value={sectionId ?? ""}
                onChange={(e) => setSectionId(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
              >
                {unit.sections.map((s) => (
                  <option key={s.section_id} value={s.section_id} disabled={s.remaining <= 0}>
                    {s.book_name} ({s.remaining} kalan)
                  </option>
                ))}
              </select>
            </label>
          ) : null}

          <div>
            <p className="mb-1.5 text-xs font-medium text-foreground">Gün</p>
            <div className="grid grid-cols-2 gap-1.5">
              {selectableDays.map((d) => (
                <button
                  key={d.date}
                  type="button"
                  onClick={() => setDay(d.date)}
                  className={cn(
                    "rounded-md border px-2 py-1.5 text-left text-xs transition",
                    day === d.date
                      ? "border-cyan-500 bg-cyan-100 font-semibold text-cyan-900"
                      : "border-border bg-card hover:bg-muted/50",
                  )}
                >
                  {d.dow_label} · {fmtDate(d.date)}
                  {d.is_today ? <span className="ml-1 text-cyan-600">bugün</span> : null}
                </button>
              ))}
            </div>
          </div>

          <label className="block">
            <span className="text-xs font-medium text-foreground">
              Test sayısı{sec ? ` (en çok ${sec.remaining})` : ""}
            </span>
            <input
              type="number"
              min={1}
              max={sec?.remaining ?? 99}
              value={count}
              onChange={(e) => setCount(Math.max(1, Number(e.target.value) || 1))}
              className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
            />
          </label>
        </div>

        <div className="mt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted/50"
          >
            <X className="size-4" aria-hidden /> Vazgeç
          </button>
          <button
            type="button"
            onClick={onAssign}
            disabled={!day || !sec || create.isPending}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-sm font-semibold text-white transition",
              !day || !sec || create.isPending ? "cursor-not-allowed bg-cyan-300" : "bg-cyan-600 hover:bg-cyan-700",
            )}
          >
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Plus className="size-4" aria-hidden />
            )}
            Ata
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
