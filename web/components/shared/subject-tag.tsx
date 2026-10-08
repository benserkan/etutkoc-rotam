import * as React from "react";

import { cn } from "@/lib/utils";
import { subjectHue } from "@/lib/subject-match";

/**
 * Ders renk sistemi — TEK MERKEZ (2026-10-08).
 *
 * Koç gün kartı ve öğrenci hafta ızgarası aynı dersi AYNI renkte gösterir
 * (renk ada göre: `subjectHue`). Koyu temada saydam pastel zemin tüm dersleri
 * aynı lacivert-griye çeviriyordu → opak, doygun koyu ton kullanılır.
 * Ölçüm: scripts/live_day_card_subject_colors.py (komşu farklı ders ΔE ≥ 10).
 */
export function subjectColors(name: string) {
  const hue = subjectHue(name);
  return {
    hue,
    /** Satır/blok zemini — açık tema */
    tintLight: `hsl(${hue}, 65%, 91%)`,
    /** Satır/blok zemini — koyu tema (opak) */
    tintDark: `hsl(${hue}, 40%, 18%)`,
    /** Sol şerit */
    rail: `hsl(${hue}, 75%, 50%)`,
    /** Dolgulu etiket zemini (beyaz yazı) */
    chip: `hsl(${hue}, 60%, 36%)`,
  };
}

/** Blok/satır için CSS değişkenleri: `bg-[var(--subj-tint-l)] dark:bg-[var(--subj-tint-d)]`. */
export function subjectTintVars(name: string): React.CSSProperties {
  const c = subjectColors(name);
  return {
    "--subj-tint-l": c.tintLight,
    "--subj-tint-d": c.tintDark,
    borderLeftColor: c.rail,
  } as React.CSSProperties;
}

/**
 * Ders adı DOLGULU etiket: renkli yazı koyu zeminde soluk okunuyordu; küçük
 * öğede dolgu (koyu ton + beyaz yazı) bir bakışta ayrışır. Sınav öneki
 * (TYT/AYT/LGS) ayrı küçük işaret: aynı derste TYT ve AYT aynı renkte kalır,
 * AYT koyu dolgulu işaretle ayrılır.
 *
 * size="xs": dar sütunlar (hafta ızgarası) — ad kırpılmaz, gerekirse alt satıra
 * iner.
 */
export function SubjectTag({
  name,
  size = "sm",
  className,
}: {
  name: string;
  size?: "sm" | "xs";
  className?: string;
}) {
  const m = /^(TYT|AYT|LGS)\s+(.+)$/i.exec(name);
  const exam = m ? m[1].toUpperCase() : null;
  const plain = m ? m[2] : name;
  const xs = size === "xs";
  return (
    <span
      className={cn("inline-flex items-center gap-1 self-center", xs && "flex-wrap", className)}
      title={name}
      data-testid="subject-tag"
    >
      {exam ? (
        <span
          className={cn(
            "font-bold tracking-wider px-1 py-px rounded border leading-none",
            xs ? "text-[8.5px]" : "text-[9.5px]",
            exam === "AYT"
              ? "bg-slate-900 text-white border-slate-900 dark:bg-white dark:text-slate-900 dark:border-white"
              : "border-slate-400 text-slate-700 dark:border-slate-500 dark:text-slate-200",
          )}
        >
          {exam}
        </span>
      ) : null}
      <span
        className={cn(
          "font-semibold rounded text-white",
          xs
            ? "text-[10px] leading-tight px-1 py-px break-words"
            : "text-[12px] whitespace-nowrap px-1.5 py-px",
        )}
        style={{ backgroundColor: subjectColors(name).chip }}
        data-testid="subject-tag-name"
      >
        {plain}
      </span>
    </span>
  );
}
