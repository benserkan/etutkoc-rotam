"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, Save, Trash2 } from "lucide-react";

import { academicKeys, getAcademicYear } from "@/lib/api/academic";
import {
  useAssignStudentsToYear,
  useCreatePhase,
  useDeletePhase,
  usePatchAcademicYear,
} from "@/lib/hooks/use-academic-mutations";
import type {
  AcademicYearDetailResponse,
  ExamTarget,
  PhaseItem,
  PhaseKind,
} from "@/lib/types/academic";
import type { TeacherStudentListItem } from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const PHASE_KIND_OPTIONS: Array<{ value: PhaseKind; label: string }> = [
  { value: "regular", label: "📚 Olağan Dönem" },
  { value: "winter_break", label: "❄️ Yarıyıl Tatili" },
  { value: "summer_camp", label: "🌞 Yaz Kampı" },
  { value: "exam_prep", label: "🎯 Sınav Hazırlık" },
];

const EXAM_TARGET_OPTIONS: Array<{ value: ExamTarget; label: string }> = [
  { value: "none", label: "Yıl Sonu / yok" },
  { value: "lgs", label: "LGS" },
  { value: "yks", label: "YKS" },
];

interface Props {
  yearId: number;
  initial: AcademicYearDetailResponse;
  allStudents: TeacherStudentListItem[];
}

export function AcademicYearDetailClient({
  yearId,
  initial,
  allStudents,
}: Props) {
  const q = useQuery<AcademicYearDetailResponse>({
    queryKey: academicKeys.year(yearId),
    queryFn: () => getAcademicYear(yearId),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link
            href="/teacher/academic-years"
            className="hover:underline"
          >
            Akademik yıllar
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          {data.name}
        </h1>
        <p className="text-sm text-muted-foreground">
          {data.phases.length} dönem · {data.assigned_students.length} öğrenci
          {data.exam_label !== "—" ? ` · ${data.exam_label}` : ""}
        </p>
      </header>

      <YearMetaCard data={data} />
      <PhasesCard data={data} />
      <AssignmentsCard
        yearId={data.id}
        assigned={data.assigned_students}
        allStudents={allStudents}
      />
    </div>
  );
}

function YearMetaCard({ data }: { data: AcademicYearDetailResponse }) {
  const patch = usePatchAcademicYear(data.id);
  const [examTarget, setExamTarget] = React.useState<ExamTarget>(data.exam_target);
  const [isActive, setIsActive] = React.useState(data.is_active);

  // Adapt state when data changes (server-driven)
  const dataKey = `${data.exam_target}::${data.is_active}`;
  const [lastKey, setLastKey] = React.useState(dataKey);
  if (lastKey !== dataKey) {
    setLastKey(dataKey);
    setExamTarget(data.exam_target);
    setIsActive(data.is_active);
  }

  function onSave() {
    patch.mutate({
      body: { exam_target: examTarget, is_active: isActive },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Yıl ayarları</CardTitle>
      </CardHeader>
      <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
        <div className="space-y-1">
          <Label htmlFor="exam-target">Hedef sınav</Label>
          <select
            id="exam-target"
            value={examTarget}
            onChange={(e) => setExamTarget(e.target.value as ExamTarget)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {EXAM_TARGET_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 h-9">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Etkin yıl
        </label>
        <Button onClick={onSave} disabled={patch.isPending}>
          {patch.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Save className="size-4" aria-hidden />
          )}
          Kaydet
        </Button>
      </CardContent>
    </Card>
  );
}

function PhasesCard({ data }: { data: AcademicYearDetailResponse }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Dönemler (faz)</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {data.phases.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 pb-3">
            Henüz dönem tanımı yok.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data.phases.map((p) => (
              <PhaseRow key={p.id} yearId={data.id} phase={p} />
            ))}
          </ul>
        )}
        <div className="border-t border-border p-4">
          <NewPhaseForm yearId={data.id} />
        </div>
      </CardContent>
    </Card>
  );
}

function PhaseRow({
  yearId,
  phase,
}: {
  yearId: number;
  phase: PhaseItem;
}) {
  const del = useDeletePhase(yearId);
  function onDelete() {
    if (!window.confirm(`"${phase.name}" dönemini silmek istiyor musunuz?`)) {
      return;
    }
    del.mutate({ phaseId: phase.id });
  }
  return (
    <li className="px-4 py-3 flex items-center gap-3 text-sm">
      <span className="flex-1 min-w-0">
        <span className="font-medium truncate block">
          {phase.kind_badge} {phase.name}
        </span>
        <span className="text-xs text-muted-foreground">
          {phase.start_date} → {phase.end_date}
          {phase.is_no_school ? " · okul yok" : ""}
          {phase.capacity_multiplier !== 1
            ? ` · ×${phase.capacity_multiplier} kapasite`
            : ""}
        </span>
        {phase.notes ? (
          <span className="text-xs text-muted-foreground italic truncate block">
            {phase.notes}
          </span>
        ) : null}
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        disabled={del.isPending}
        aria-label="Dönemi sil"
      >
        {del.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Trash2 className="size-4" aria-hidden />
        )}
      </Button>
    </li>
  );
}

function NewPhaseForm({ yearId }: { yearId: number }) {
  const create = useCreatePhase(yearId);
  const [name, setName] = React.useState("");
  const [start, setStart] = React.useState("");
  const [end, setEnd] = React.useState("");
  const [kind, setKind] = React.useState<PhaseKind>("regular");
  const [notes, setNotes] = React.useState("");

  function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !start || !end) return;
    create.mutate(
      {
        body: {
          name: name.trim(),
          start_date: start,
          end_date: end,
          kind,
          notes: notes.trim() || undefined,
        },
      },
      {
        onSuccess: () => {
          setName("");
          setStart("");
          setEnd("");
          setNotes("");
          setKind("regular");
        },
      },
    );
  }

  return (
    <form onSubmit={onAdd} className="grid grid-cols-1 sm:grid-cols-6 gap-2 items-end text-sm">
      <div className="space-y-1 sm:col-span-2">
        <Label htmlFor="ph-name">Dönem adı</Label>
        <Input
          id="ph-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="1. Dönem"
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="ph-start">Başlangıç</Label>
        <Input
          id="ph-start"
          type="date"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="ph-end">Bitiş</Label>
        <Input
          id="ph-end"
          type="date"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="ph-kind">Tür</Label>
        <select
          id="ph-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value as PhaseKind)}
          className={cn(
            "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          )}
        >
          {PHASE_KIND_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <Button type="submit" disabled={create.isPending}>
        {create.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Plus className="size-4" aria-hidden />
        )}
        Ekle
      </Button>
      <div className="space-y-1 sm:col-span-6">
        <Label htmlFor="ph-notes">Notlar (opsiyonel)</Label>
        <Input
          id="ph-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
    </form>
  );
}

function AssignmentsCard({
  yearId,
  assigned,
  allStudents,
}: {
  yearId: number;
  assigned: AcademicYearDetailResponse["assigned_students"];
  allStudents: TeacherStudentListItem[];
}) {
  const assign = useAssignStudentsToYear(yearId);
  const initialIds = React.useMemo(
    () => new Set(assigned.map((s) => s.student_id)),
    [assigned],
  );
  const [selected, setSelected] = React.useState<Set<number>>(
    () => new Set(initialIds),
  );

  // Adapt state when server data changes
  const initialKey = React.useMemo(
    () => Array.from(initialIds).sort().join(","),
    [initialIds],
  );
  const [lastKey, setLastKey] = React.useState(initialKey);
  if (lastKey !== initialKey) {
    setLastKey(initialKey);
    setSelected(new Set(initialIds));
  }

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function onSave() {
    assign.mutate({ body: { student_ids: Array.from(selected) } });
  }

  const dirty =
    selected.size !== initialIds.size ||
    Array.from(selected).some((id) => !initialIds.has(id));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Öğrenci atamaları</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {allStudents.length === 0 ? (
          <p className="text-sm text-muted-foreground p-4">
            Henüz öğrenci kaydı yok.
          </p>
        ) : (
          <ul className="divide-y divide-border max-h-[50vh] overflow-y-auto">
            {allStudents.map((s) => {
              const checked = selected.has(s.id);
              return (
                <li
                  key={s.id}
                  className="px-4 py-2 flex items-center gap-3 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(s.id)}
                    aria-label={s.full_name}
                  />
                  <span className="flex-1 min-w-0">
                    <span className="font-medium truncate block">
                      {s.full_name}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {s.email}
                      {s.grade_level !== null
                        ? ` · ${s.grade_level}. sınıf`
                        : ""}
                      {s.is_active ? "" : " · pasif"}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <div className="border-t border-border px-4 py-3 flex items-center justify-end gap-2">
          <p className="text-xs text-muted-foreground flex-1">
            {selected.size} öğrenci seçili.
          </p>
          <Button
            onClick={onSave}
            disabled={!dirty || assign.isPending}
          >
            {assign.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Save className="size-4" aria-hidden />
            )}
            Atamayı kaydet
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
