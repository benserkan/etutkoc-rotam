"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Loader2, RotateCcw, Trash2 } from "lucide-react";

import { academicKeys, getGradeAdvancePreview } from "@/lib/api/academic";
import {
  useGradeAdvanceApply,
  useResetProgram,
} from "@/lib/hooks/use-academic-mutations";
import type {
  AcademicYearListItem,
  GradeAdvanceApplyItem,
  GradeAdvancePreviewItem,
  GradeAdvancePreviewResponse,
  GraduateMode,
  Track,
} from "@/lib/types/academic";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface Props {
  initialPreview: GradeAdvancePreviewResponse;
  years: AcademicYearListItem[];
}

interface PlannedChange {
  studentId: number;
  new_grade_level: number | null;
  new_is_graduate: boolean;
  new_track: Track | null;
  new_graduate_mode: GraduateMode | null;
}

export function GradeAdvanceClient({ initialPreview, years }: Props) {
  const q = useQuery<GradeAdvancePreviewResponse>({
    queryKey: academicKeys.gradeAdvancePreview(),
    queryFn: () => getGradeAdvancePreview(),
    initialData: initialPreview,
    staleTime: 30_000,
  });
  const preview = q.data ?? initialPreview;
  const apply = useGradeAdvanceApply();

  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [overrides, setOverrides] = React.useState<Record<number, PlannedChange>>({});
  const [targetYearId, setTargetYearId] = React.useState<string>(
    preview.suggested_year_id !== null ? String(preview.suggested_year_id) : "",
  );

  // sync target year when server preview changes
  const suggestedKey = preview.suggested_year_id !== null
    ? String(preview.suggested_year_id) : "";
  const [lastSuggested, setLastSuggested] = React.useState(suggestedKey);
  if (lastSuggested !== suggestedKey) {
    setLastSuggested(suggestedKey);
    setTargetYearId(suggestedKey);
  }

  function defaultPlanFor(s: GradeAdvancePreviewItem): PlannedChange {
    const existing = overrides[s.student_id];
    if (existing) return existing;
    return {
      studentId: s.student_id,
      new_grade_level: s.suggested_grade_level,
      new_is_graduate: s.suggested_is_graduate,
      new_track: null,
      new_graduate_mode: null,
    };
  }

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setPlan(id: number, change: Partial<PlannedChange>) {
    setOverrides((prev) => {
      const base = prev[id] ?? defaultPlanFor(
        preview.students.find((s) => s.student_id === id)!,
      );
      return { ...prev, [id]: { ...base, ...change } };
    });
  }

  function onApply() {
    const items: GradeAdvanceApplyItem[] = Array.from(selected).map((id) => {
      const plan =
        overrides[id] ??
        defaultPlanFor(preview.students.find((s) => s.student_id === id)!);
      return {
        student_id: id,
        new_grade_level: plan.new_grade_level,
        new_is_graduate: plan.new_is_graduate,
        new_track: plan.new_track,
        new_graduate_mode: plan.new_graduate_mode,
      };
    });
    apply.mutate(
      {
        body: {
          items,
          target_academic_year_id: targetYearId ? Number(targetYearId) : null,
        },
      },
      {
        onSuccess: () => {
          setSelected(new Set());
          setOverrides({});
        },
      },
    );
  }

  const selectableCount = preview.students.length;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Yıllık geçiş
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Sınıf yükseltme
        </h1>
        <p className="text-sm text-muted-foreground">
          Görev, rezerv ve ilerleme kayıtlarına dokunulmaz — yalnızca öğrenci
          profili (sınıf, alan, akademik yıl) güncellenir. Tarihçeyi silmek için
          sağdaki &quot;Programı sıfırla&quot; butonunu kullanın (geri alınamaz).
        </p>
      </header>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="ga-year">Hedef akademik yıl</Label>
            <select
              id="ga-year"
              value={targetYearId}
              onChange={(e) => setTargetYearId(e.target.value)}
              className={cn(
                "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <option value="">Yıl değiştirme (mevcut korunsun)</option>
              {years.map((y) => (
                <option key={y.id} value={y.id}>
                  {y.name}
                </option>
              ))}
            </select>
            {preview.suggested_year_name ? (
              <p className="text-xs text-muted-foreground">
                Önerilen: <span className="font-medium">{preview.suggested_year_name}</span>
              </p>
            ) : null}
          </div>
          <Button
            onClick={onApply}
            disabled={selected.size === 0 || apply.isPending}
          >
            {apply.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <ArrowUpRight className="size-4" aria-hidden />
            )}
            {selected.size} öğrenciyi yükselt
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Öğrenciler ({selectableCount})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {preview.students.length === 0 ? (
            <p className="text-sm text-muted-foreground p-4">
              Atanmış öğrenci yok.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {preview.students.map((s) => (
                <StudentRow
                  key={s.student_id}
                  student={s}
                  checked={selected.has(s.student_id)}
                  plan={defaultPlanFor(s)}
                  onToggle={() => toggle(s.student_id)}
                  onPlanChange={(c) => setPlan(s.student_id, c)}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StudentRow({
  student,
  checked,
  plan,
  onToggle,
  onPlanChange,
}: {
  student: GradeAdvancePreviewItem;
  checked: boolean;
  plan: PlannedChange;
  onToggle: () => void;
  onPlanChange: (change: Partial<PlannedChange>) => void;
}) {
  const [resetOpen, setResetOpen] = React.useState(false);
  const currentLabel = student.current_is_graduate
    ? "Mezun"
    : student.current_grade_level
      ? `${student.current_grade_level}. sınıf`
      : "—";
  const newLabel = plan.new_is_graduate
    ? "Mezun"
    : plan.new_grade_level
      ? `${plan.new_grade_level}. sınıf`
      : "—";

  function onGradeChange(value: string) {
    if (value === "graduate") {
      onPlanChange({ new_is_graduate: true, new_grade_level: null });
    } else if (value === "") {
      onPlanChange({ new_is_graduate: false, new_grade_level: null });
    } else {
      const n = Number(value);
      onPlanChange({ new_is_graduate: false, new_grade_level: n });
    }
  }

  return (
    <li className="px-4 py-3 text-sm">
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          aria-label={student.full_name}
        />
        <span className="flex-1 min-w-0">
          <span className="font-medium truncate block">{student.full_name}</span>
          <span className="text-xs text-muted-foreground">
            {currentLabel}
            {" → "}
            <span className="font-medium text-foreground">{newLabel}</span>
            {student.current_academic_year_name
              ? ` · ${student.current_academic_year_name}`
              : ""}
            {student.has_reservations ? " · rezerv var" : ""}
          </span>
          {student.blocker_notes.length > 0 ? (
            <ul className="mt-1 space-y-0.5">
              {student.blocker_notes.map((n, i) => (
                <li
                  key={i}
                  className="text-[11px] text-amber-700 dark:text-amber-300"
                >
                  ⚠ {n}
                </li>
              ))}
            </ul>
          ) : null}
        </span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setResetOpen(true)}
          aria-label="Programı sıfırla"
        >
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>

      {checked ? (
        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
          <div className="space-y-1">
            <Label className="text-xs">Yeni sınıf</Label>
            <select
              value={
                plan.new_is_graduate
                  ? "graduate"
                  : plan.new_grade_level !== null
                    ? String(plan.new_grade_level)
                    : ""
              }
              onChange={(e) => onGradeChange(e.target.value)}
              className={cn(
                "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <option value="">—</option>
              {[5, 6, 7, 8, 9, 10, 11, 12].map((g) => (
                <option key={g} value={g}>
                  {g}. sınıf
                </option>
              ))}
              <option value="graduate">Mezun (YKS)</option>
            </select>
          </div>
          {plan.new_is_graduate ||
          (plan.new_grade_level !== null && plan.new_grade_level >= 11) ? (
            <div className="space-y-1">
              <Label className="text-xs">Alan</Label>
              <select
                value={plan.new_track ?? ""}
                onChange={(e) =>
                  onPlanChange({
                    new_track:
                      e.target.value === ""
                        ? null
                        : (e.target.value as Track),
                  })
                }
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <option value="">(değişmesin)</option>
                <option value="sayisal">Sayısal</option>
                <option value="ea">Eşit Ağırlık</option>
                <option value="sozel">Sözel</option>
                <option value="dil">Dil</option>
              </select>
            </div>
          ) : null}
          {plan.new_is_graduate ? (
            <div className="space-y-1">
              <Label className="text-xs">Çalışma şekli</Label>
              <select
                value={plan.new_graduate_mode ?? ""}
                onChange={(e) =>
                  onPlanChange({
                    new_graduate_mode:
                      e.target.value === ""
                        ? null
                        : (e.target.value as GraduateMode),
                  })
                }
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <option value="">(değişmesin)</option>
                <option value="full_time">Tam zamanlı</option>
                <option value="dershane">Dershane / etüt</option>
              </select>
            </div>
          ) : null}
        </div>
      ) : null}

      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Programı sıfırla</DialogTitle>
          </DialogHeader>
          <ResetProgramForm
            studentId={student.student_id}
            studentFullName={student.full_name}
            onDone={() => setResetOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </li>
  );
}

function ResetProgramForm({
  studentId,
  studentFullName,
  onDone,
}: {
  studentId: number;
  studentFullName: string;
  onDone: () => void;
}) {
  const mut = useResetProgram(studentId);
  const [confirm, setConfirm] = React.useState("");
  const match = confirm.trim() === studentFullName;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!match) return;
    mut.mutate(
      { body: { confirm_full_name: confirm.trim() } },
      { onSuccess: () => onDone() },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
        <p className="font-medium">Bu işlem geri alınamaz.</p>
        <p className="text-xs mt-1">
          <strong>{studentFullName}</strong> için tüm görevler, görev kalemleri,
          öneri red/kabul geçmişi silinir ve rezervasyon sayaçları sıfırlanır.
          Kitap atamaları korunur, sadece sayaçlar sıfırlanır.
        </p>
      </div>
      <div className="space-y-1">
        <Label htmlFor="rp-confirm">
          Onay için öğrencinin adını birebir yazın:
        </Label>
        <Input
          id="rp-confirm"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder={studentFullName}
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Hedef ad: <strong>{studentFullName}</strong>
        </p>
      </div>
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="ghost"
          onClick={onDone}
          disabled={mut.isPending}
        >
          İptal
        </Button>
        <Button
          type="submit"
          variant="destructive"
          disabled={!match || mut.isPending}
        >
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <RotateCcw className="size-4" aria-hidden />
          )}
          Programı sıfırla
        </Button>
      </div>
    </form>
  );
}
