"use client";

import * as React from "react";
import { ChevronDown, GraduationCap, School } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Hedef sınıf seviyesi seçici — 3 hızlı radyo (LGS/Lise/Mezun/Tüm) + ince
 * ayar (özel min/max). Book create form'unda ve Book set form'larında ortak.
 *
 * Bir state objesi okur ve setState callback'leri verir; ebeveyn kontrolü
 * elinde tutar.
 */

export type GradePreset = "any" | "lgs" | "lise" | "graduate" | "custom";

export interface TargetGradeValue {
  preset: GradePreset;
  gradeMin: string; // input string (empty = null)
  gradeMax: string;
  targetGraduate: boolean;
}

export const INITIAL_TARGET_GRADE: TargetGradeValue = {
  preset: "any",
  gradeMin: "",
  gradeMax: "",
  targetGraduate: false,
};

/**
 * Backend body için normalleştirme. preset değerlerinden gerçek alanları üret.
 */
export function targetGradeBody(v: TargetGradeValue): {
  target_grade_min: number | null;
  target_grade_max: number | null;
  target_graduate: boolean;
} {
  if (v.preset === "lgs") {
    return { target_grade_min: 5, target_grade_max: 8, target_graduate: false };
  }
  if (v.preset === "lise") {
    return {
      target_grade_min: 9,
      target_grade_max: 12,
      target_graduate: false,
    };
  }
  if (v.preset === "graduate") {
    return {
      target_grade_min: null,
      target_grade_max: null,
      target_graduate: true,
    };
  }
  if (v.preset === "any") {
    return {
      target_grade_min: null,
      target_grade_max: null,
      target_graduate: false,
    };
  }
  // custom
  return {
    target_grade_min: v.gradeMin ? Number(v.gradeMin) : null,
    target_grade_max: v.gradeMax ? Number(v.gradeMax) : null,
    target_graduate: v.targetGraduate,
  };
}

/**
 * Backend'den gelen alanları preset'e çöz (edit form için).
 */
export function targetGradeFromFields(
  min: number | null,
  max: number | null,
  graduate: boolean,
): TargetGradeValue {
  if (min === null && max === null && !graduate) {
    return { preset: "any", gradeMin: "", gradeMax: "", targetGraduate: false };
  }
  if (min === 5 && max === 8 && !graduate) {
    return { preset: "lgs", gradeMin: "5", gradeMax: "8", targetGraduate: false };
  }
  if (min === 9 && max === 12 && !graduate) {
    return {
      preset: "lise",
      gradeMin: "9",
      gradeMax: "12",
      targetGraduate: false,
    };
  }
  if (min === null && max === null && graduate) {
    return {
      preset: "graduate",
      gradeMin: "",
      gradeMax: "",
      targetGraduate: true,
    };
  }
  return {
    preset: "custom",
    gradeMin: min === null ? "" : String(min),
    gradeMax: max === null ? "" : String(max),
    targetGraduate: graduate,
  };
}

const PRESET_OPTIONS: Array<{
  value: GradePreset;
  label: string;
  description: string;
  icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}> = [
  {
    value: "lgs",
    label: "LGS (5-8)",
    description: "Ortaokul",
    icon: School,
  },
  {
    value: "lise",
    label: "Lise (9-12)",
    description: "Maarif / Klasik",
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
  value: TargetGradeValue;
  onChange: (v: TargetGradeValue) => void;
  title?: string;
  description?: string;
  idPrefix?: string;
}

export function TargetGradePicker({
  value,
  onChange,
  title = "Hedef sınıf seviyesi",
  description = "Set'in hangi sınıf seviyesi için olduğunu işaretle. Tüm seviyeler = sınırlandırma yok.",
  idPrefix = "tg",
}: Props) {
  const [showAdvanced, setShowAdvanced] = React.useState(
    value.preset === "custom",
  );

  function applyPreset(p: GradePreset) {
    if (p === "lgs") {
      onChange({
        preset: "lgs",
        gradeMin: "5",
        gradeMax: "8",
        targetGraduate: false,
      });
      setShowAdvanced(false);
    } else if (p === "lise") {
      onChange({
        preset: "lise",
        gradeMin: "9",
        gradeMax: "12",
        targetGraduate: false,
      });
      setShowAdvanced(false);
    } else if (p === "graduate") {
      onChange({
        preset: "graduate",
        gradeMin: "",
        gradeMax: "",
        targetGraduate: true,
      });
      setShowAdvanced(false);
    } else if (p === "any") {
      onChange({
        preset: "any",
        gradeMin: "",
        gradeMax: "",
        targetGraduate: false,
      });
      setShowAdvanced(false);
    }
  }

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{title}</legend>
      <p className="text-xs text-muted-foreground">{description}</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {PRESET_OPTIONS.map((p) => {
          const Icon = p.icon;
          const active = value.preset === p.value;
          return (
            <button
              key={p.value}
              type="button"
              onClick={() => applyPreset(p.value)}
              className={cn(
                "rounded-md border p-2.5 text-left transition-colors",
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
            onChange({ ...value, preset: "custom" });
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
            <Label htmlFor={`${idPrefix}-min`} className="text-xs">
              Min sınıf
            </Label>
            <Input
              id={`${idPrefix}-min`}
              type="number"
              min={4}
              max={12}
              value={value.gradeMin}
              onChange={(e) =>
                onChange({
                  ...value,
                  preset: "custom",
                  gradeMin: e.target.value,
                })
              }
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`${idPrefix}-max`} className="text-xs">
              Maks sınıf
            </Label>
            <Input
              id={`${idPrefix}-max`}
              type="number"
              min={4}
              max={12}
              value={value.gradeMax}
              onChange={(e) =>
                onChange({
                  ...value,
                  preset: "custom",
                  gradeMax: e.target.value,
                })
              }
            />
          </div>
          <label className="flex items-center gap-2 text-xs pt-6">
            <input
              type="checkbox"
              checked={value.targetGraduate}
              onChange={(e) =>
                onChange({
                  ...value,
                  preset: "custom",
                  targetGraduate: e.target.checked,
                })
              }
            />
            Mezun için
          </label>
        </div>
      ) : null}
    </fieldset>
  );
}
