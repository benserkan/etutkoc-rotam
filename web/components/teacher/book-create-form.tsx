"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronDown, GraduationCap, Loader2, School } from "lucide-react";

import { useCreateBook } from "@/lib/hooks/use-library-mutations";
import type {
  BookTemplateListItem,
  LibraryBookType,
  SubjectRef,
} from "@/lib/types/library";
import {
  groupSubjectsByCurriculum,
  filterSubjectsByGrade,
} from "@/lib/utils/subjects";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const TYPE_OPTIONS: Array<{ value: LibraryBookType; label: string }> = [
  { value: "soru_bankasi", label: "Soru bankası" },
  { value: "fasikul", label: "Fasikül" },
  { value: "konu_anlatimli", label: "Konu anlatımlı" },
  { value: "brans_denemesi", label: "Branş denemesi" },
  { value: "genel_deneme", label: "Genel deneme" },
];

type GradePreset = "any" | "lgs" | "lise" | "graduate" | "custom";

const PRESET_OPTIONS: Array<{
  value: GradePreset;
  label: string;
  description: string;
  icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}> = [
  {
    value: "lgs",
    label: "LGS (5-8)",
    description: "Ortaokul müfredatı",
    icon: School,
  },
  {
    value: "lise",
    label: "Lise (9-12)",
    description: "Maarif veya Klasik Lise",
    icon: School,
  },
  {
    value: "graduate",
    label: "Mezun (YKS)",
    description: "YKS hazırlık",
    icon: GraduationCap,
  },
  {
    value: "any",
    label: "Tüm seviyeler",
    description: "Hedef belirtmeden",
  },
];

interface Props {
  subjects: SubjectRef[];
  templates: BookTemplateListItem[];
}

export function BookCreateForm({ subjects, templates }: Props) {
  const router = useRouter();
  const createMut = useCreateBook();

  const [name, setName] = React.useState("");
  const [publisher, setPublisher] = React.useState("");
  const [type, setType] = React.useState<LibraryBookType>("soru_bankasi");
  const [avgQ, setAvgQ] = React.useState("");
  const [preset, setPreset] = React.useState<GradePreset>("any");
  const [gradeMin, setGradeMin] = React.useState("");
  const [gradeMax, setGradeMax] = React.useState("");
  const [targetGraduate, setTargetGraduate] = React.useState(false);
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [templateId, setTemplateId] = React.useState<number | "">("");
  const [error, setError] = React.useState<string | null>(null);

  function applyPreset(p: GradePreset) {
    setPreset(p);
    setShowAdvanced(p === "custom");
    if (p === "lgs") {
      setGradeMin("5");
      setGradeMax("8");
      setTargetGraduate(false);
    } else if (p === "lise") {
      setGradeMin("9");
      setGradeMax("12");
      setTargetGraduate(false);
    } else if (p === "graduate") {
      setGradeMin("");
      setGradeMax("");
      setTargetGraduate(true);
    } else if (p === "any") {
      setGradeMin("");
      setGradeMax("");
      setTargetGraduate(false);
    }
    // custom → kullanıcı kendisi düzenler
    // Hedef değişince seçili ders artık kapsam dışında kalmışsa sıfırla
    setSubjectId((prev) => {
      if (prev === "") return prev;
      const s = subjects.find((x) => x.id === prev);
      if (!s) return "";
      const inFilter = computeFilteredSubjects(subjects, p, {
        gradeMin,
        gradeMax,
        targetGraduate,
      }).some((x) => x.id === prev);
      return inFilter ? prev : "";
    });
  }

  const filtered = React.useMemo(
    () =>
      computeFilteredSubjects(subjects, preset, {
        gradeMin,
        gradeMax,
        targetGraduate,
      }),
    [subjects, preset, gradeMin, gradeMax, targetGraduate],
  );

  const groups = React.useMemo(
    () => groupSubjectsByCurriculum(filtered),
    [filtered],
  );

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Kitap adı zorunlu.");
      return;
    }
    if (!subjectId) {
      setError("Ders seçin.");
      return;
    }
    const gMin = gradeMin ? Number(gradeMin) : null;
    const gMax = gradeMax ? Number(gradeMax) : null;
    if (gMin !== null && (gMin < 4 || gMin > 12)) {
      setError("Min sınıf 4-12 aralığında olmalı.");
      return;
    }
    if (gMax !== null && (gMax < 4 || gMax > 12)) {
      setError("Maks sınıf 4-12 aralığında olmalı.");
      return;
    }
    createMut.mutate(
      {
        body: {
          name: name.trim(),
          publisher: publisher.trim() || null,
          subject_id: Number(subjectId),
          type,
          avg_questions_per_test: avgQ ? Number(avgQ) : null,
          target_grade_min: gMin,
          target_grade_max: gMax,
          target_graduate: targetGraduate,
          template_id: templateId ? Number(templateId) : null,
        },
      },
      {
        onSuccess: (res) => {
          router.push(`/teacher/library/books/${res.data.id}`);
        },
      },
    );
  }

  return (
    <Card>
      <CardContent className="p-6">
        <form onSubmit={submit} className="space-y-5">
          <div className="space-y-1">
            <Label htmlFor="cb-name">Kitap adı</Label>
            <Input
              id="cb-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
            />
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Hedef sınıf seviyesi</legend>
            <p className="text-xs text-muted-foreground">
              Seçim, alttaki ders listesini bu seviyeye uygun derslerle
              kısıtlar. Karma kitap için &quot;Tüm seviyeler&quot;.
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {PRESET_OPTIONS.map((p) => {
                const Icon = p.icon;
                const active = preset === p.value;
                return (
                  <button
                    key={p.value}
                    type="button"
                    onClick={() => applyPreset(p.value)}
                    className={cn(
                      "rounded-md border p-3 text-left transition-colors",
                      active
                        ? "border-foreground bg-muted"
                        : "border-border hover:bg-muted/50",
                    )}
                    aria-pressed={active}
                  >
                    <div className="flex items-center gap-1.5">
                      {Icon ? (
                        <Icon
                          className={cn(
                            "size-4",
                            active ? "text-foreground" : "text-muted-foreground",
                          )}
                          aria-hidden
                        />
                      ) : null}
                      <span className="text-sm font-medium">{p.label}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      {p.description}
                    </p>
                  </button>
                );
              })}
            </div>
            <button
              type="button"
              onClick={() => {
                if (showAdvanced) {
                  setShowAdvanced(false);
                } else {
                  setShowAdvanced(true);
                  setPreset("custom");
                }
              }}
              className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1 mt-1"
            >
              <ChevronDown
                className={cn(
                  "size-3 transition-transform",
                  showAdvanced && "rotate-180",
                )}
                aria-hidden
              />
              {showAdvanced ? "İnce ayarı gizle" : "İnce ayar (özel aralık)"}
            </button>
            {showAdvanced ? (
              <div className="grid grid-cols-3 gap-3 pt-2 border-t border-border">
                <div className="space-y-1">
                  <Label htmlFor="cb-gmin" className="text-xs">
                    Min sınıf
                  </Label>
                  <Input
                    id="cb-gmin"
                    type="number"
                    min={4}
                    max={12}
                    value={gradeMin}
                    onChange={(e) => {
                      setGradeMin(e.target.value);
                      setPreset("custom");
                    }}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="cb-gmax" className="text-xs">
                    Maks sınıf
                  </Label>
                  <Input
                    id="cb-gmax"
                    type="number"
                    min={4}
                    max={12}
                    value={gradeMax}
                    onChange={(e) => {
                      setGradeMax(e.target.value);
                      setPreset("custom");
                    }}
                  />
                </div>
                <label className="flex items-center gap-2 text-xs pt-6">
                  <input
                    type="checkbox"
                    checked={targetGraduate}
                    onChange={(e) => {
                      setTargetGraduate(e.target.checked);
                      setPreset("custom");
                    }}
                  />
                  Mezun için
                </label>
              </div>
            ) : null}
          </fieldset>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="cb-subject">
                Ders{" "}
                <span className="text-xs text-muted-foreground font-normal">
                  · {filtered.length} ders eşleşti
                </span>
              </Label>
              <select
                id="cb-subject"
                value={subjectId === "" ? "" : String(subjectId)}
                onChange={(e) =>
                  setSubjectId(e.target.value ? Number(e.target.value) : "")
                }
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
                required
              >
                <option value="">— Seç —</option>
                {groups.length === 0 ? (
                  <option value="" disabled>
                    Bu hedef seviyeye uyan ders yok
                  </option>
                ) : (
                  groups.map((g) => (
                    <optgroup key={g.label} label={g.label}>
                      {g.subjects.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </optgroup>
                  ))
                )}
              </select>
            </div>
            <div className="space-y-1">
              <Label htmlFor="cb-type">Tip</Label>
              <select
                id="cb-type"
                value={type}
                onChange={(e) => setType(e.target.value as LibraryBookType)}
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                {TYPE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="cb-publisher">Yayınevi (opsiyonel)</Label>
              <Input
                id="cb-publisher"
                value={publisher}
                onChange={(e) => setPublisher(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="cb-avg">Test başına ort. soru (opsiyonel)</Label>
              <Input
                id="cb-avg"
                type="number"
                min={1}
                value={avgQ}
                onChange={(e) => setAvgQ(e.target.value)}
              />
            </div>
          </div>

          {templates.length > 0 ? (
            <div className="space-y-1">
              <Label htmlFor="cb-template">Şablondan başla (opsiyonel)</Label>
              <select
                id="cb-template"
                value={templateId === "" ? "" : String(templateId)}
                onChange={(e) =>
                  setTemplateId(e.target.value ? Number(e.target.value) : "")
                }
                className={cn(
                  "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              >
                <option value="">Sıfırdan başla</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name} ({t.section_count} bölüm)
                    {t.is_ai_generated && !t.is_verified ? " · AI taslak" : ""}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
            <Button asChild type="button" variant="ghost">
              <Link href="/teacher/library">İptal</Link>
            </Button>
            <Button type="submit" disabled={createMut.isPending}>
              {createMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Oluştur
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Helper
// =============================================================================

function computeFilteredSubjects(
  subjects: readonly SubjectRef[],
  preset: GradePreset,
  custom: { gradeMin: string; gradeMax: string; targetGraduate: boolean },
): SubjectRef[] {
  if (preset === "lgs")
    return filterSubjectsByGrade(subjects, 5, 8, false);
  if (preset === "lise")
    return filterSubjectsByGrade(subjects, 9, 12, false);
  if (preset === "graduate")
    return filterSubjectsByGrade(subjects, null, null, true);
  if (preset === "any") return [...subjects];
  // custom
  const gMin = custom.gradeMin ? Number(custom.gradeMin) : null;
  const gMax = custom.gradeMax ? Number(custom.gradeMax) : null;
  if (gMin === null && gMax === null && !custom.targetGraduate)
    return [...subjects];
  return filterSubjectsByGrade(
    subjects,
    gMin,
    gMax,
    custom.targetGraduate && gMin === null && gMax === null,
  );
}
