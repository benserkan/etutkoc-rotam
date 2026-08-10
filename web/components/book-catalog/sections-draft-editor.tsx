"use client";

/**
 * Bölüm taslağı editörü — okuma motoru önizlemesi + elle düzenleme (ORTAK).
 *
 * Kullanım yerleri: süper admin katalog dialogu + koç sihirbazı "Fotoğraftan
 * oku" önizlemesi. Kurallar:
 *  - suspect satır AMBER (çift okuma çelişkisi — kitapla karşılaştır)
 *  - test_count null satır KIRMIZI çerçeve ("içindekilerde yazmıyor — doldur")
 *  - "tümüne uygula" toplu aracı: sabit-sayı düzeltme acısını tek hamleye indirir
 *
 * Kontrast kuralı: beyaz karta explicit slate; tonlu kutulara dark: metin varyantı.
 */
import * as React from "react";
import { AlertTriangle, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface DraftSection {
  label: string;
  test_count: number | null;
  suspect?: boolean;
}

interface Props {
  sections: DraftSection[];
  onChange: (next: DraftSection[]) => void;
  disabled?: boolean;
}

export function sectionsValid(sections: DraftSection[]): boolean {
  return (
    sections.length > 0 &&
    sections.every((s) => s.label.trim().length > 0 && (s.test_count ?? 0) >= 1)
  );
}

export function SectionsDraftEditor({ sections, onChange, disabled }: Props) {
  const [bulkCount, setBulkCount] = React.useState("");

  const update = (i: number, patch: Partial<DraftSection>) => {
    onChange(sections.map((s, idx) => (idx === i ? { ...s, ...patch, suspect: patch.test_count !== undefined ? false : s.suspect } : s)));
  };
  const remove = (i: number) => onChange(sections.filter((_, idx) => idx !== i));
  const add = () =>
    onChange([...sections, { label: "", test_count: 10, suspect: false }]);
  const applyAll = () => {
    const n = Number(bulkCount);
    if (!Number.isFinite(n) || n < 1) return;
    onChange(sections.map((s) => ({ ...s, test_count: Math.min(Math.round(n), 500), suspect: false })));
  };

  const suspectCount = sections.filter((s) => s.suspect).length;
  const missingCount = sections.filter((s) => (s.test_count ?? 0) < 1).length;

  return (
    <div className="space-y-2">
      {(suspectCount > 0 || missingCount > 0) && (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
          <AlertTriangle className="mr-1 inline size-3.5" aria-hidden />
          {suspectCount > 0 && (
            <span>
              {suspectCount} satırda iki okuma uyuşmadı — sarı satırları kitapla karşılaştır.{" "}
            </span>
          )}
          {missingCount > 0 && (
            <span>{missingCount} satırda test sayısı eksik — kaydetmeden önce doldur.</span>
          )}
        </div>
      )}

      <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
        {sections.map((s, i) => (
          <div
            key={i}
            className={cn(
              "flex items-center gap-2 rounded-md border px-2 py-1.5",
              s.suspect
                ? "border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30"
                : "border-border bg-card",
            )}
          >
            <span className="w-6 shrink-0 text-right text-xs text-muted-foreground">
              {i + 1}.
            </span>
            <Input
              value={s.label}
              disabled={disabled}
              onChange={(e) => update(i, { label: e.target.value })}
              placeholder="Bölüm / ünite adı"
              className="h-8 flex-1 text-sm"
            />
            <Input
              value={s.test_count == null ? "" : String(s.test_count)}
              disabled={disabled}
              onChange={(e) => {
                const v = e.target.value.trim();
                const n = Number(v);
                update(i, {
                  test_count: v === "" || !Number.isFinite(n) ? null : Math.max(0, Math.round(n)),
                });
              }}
              inputMode="numeric"
              placeholder="?"
              aria-label="Test sayısı"
              className={cn(
                "h-8 w-16 text-center text-sm",
                (s.test_count ?? 0) < 1 &&
                  "border-rose-400 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/40",
              )}
            />
            <span className="w-8 shrink-0 text-xs text-muted-foreground">test</span>
            <button
              type="button"
              onClick={() => remove(i)}
              disabled={disabled}
              className="shrink-0 rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10"
              aria-label="Bölümü kaldır"
            >
              <Trash2 className="size-4" aria-hidden />
            </button>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Button type="button" variant="outline" size="sm" onClick={add} disabled={disabled}>
          <Plus className="size-4" aria-hidden /> Bölüm ekle
        </Button>
        <div className="ml-auto flex items-center gap-1.5">
          <Input
            value={bulkCount}
            onChange={(e) => setBulkCount(e.target.value)}
            inputMode="numeric"
            placeholder="örn. 12"
            aria-label="Tümüne uygulanacak test sayısı"
            className="h-8 w-20 text-center text-sm"
            disabled={disabled}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={applyAll}
            disabled={disabled || !bulkCount}
            title="Tüm bölümlerin test sayısını bu değere eşitle"
          >
            Tümüne uygula
          </Button>
        </div>
      </div>
    </div>
  );
}
