"use client";

/**
 * Deneme sonuçları penceresi (D2, 2026-10-20) — öğrenci + koç ortak.
 *
 * Bir görevdeki her deneme ayrı satır (1 satır = 1 deneme). Öğrenci doğru/yanlış girer,
 * boş otomatik hesaplanır (soru − D − Y; elle de yazılabilir), net anında görünür.
 * Soru sayısı ESNEK: koçun yazdığı değer başlangıçtır; kaynakta farklıysa öğrenci düzeltir.
 * "Sonucu sonra gireceğim" denemeyi çözüldü sayar, sonuç bekler (2 gün sonra hatırlatma).
 */
import * as React from "react";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export interface DenemeRowInput {
  id: number;
  label: string;
  examSection: string | null | undefined;
  questionCount: number | null | undefined;
  completed: number;
  correct: number | null | undefined;
  wrong: number | null | undefined;
  blank: number | null | undefined;
  durationMinutes: number | null | undefined;
}

export interface DenemeRowOutput {
  item_id: number;
  solved: boolean;
  correct?: number | null;
  wrong?: number | null;
  blank?: number | null;
  question_count?: number | null;
  duration_minutes?: number | null;
}

interface Draft {
  solved: boolean;
  correct: string;
  wrong: string;
  blank: string;
  qn: string;
  dur: string;
}

function toStr(v: number | null | undefined): string {
  return v == null ? "" : String(v);
}

function penaltyFor(sec: string | null | undefined): number {
  return sec === "lgs" ? 3 : 4;
}

function num(s: string): number | null {
  if (s.trim() === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function fmtNet(n: number): string {
  return n.toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

export function DenemeResultDialog({
  open,
  onClose,
  title,
  rows,
  saving,
  onSubmit,
  audience = "student",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  rows: DenemeRowInput[];
  saving: boolean;
  onSubmit: (rows: DenemeRowOutput[]) => void;
  audience?: "student" | "coach";
}) {
  // Pencere her açılışta satırlardan taze taslak kurar (kapalıyken bileşen bağlanmaz).
  if (!open) return null;
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <Body
          title={title}
          rows={rows}
          saving={saving}
          onSubmit={onSubmit}
          onClose={onClose}
          audience={audience}
        />
      </DialogContent>
    </Dialog>
  );
}

function Body({
  title, rows, saving, onSubmit, onClose, audience,
}: {
  title: string;
  rows: DenemeRowInput[];
  saving: boolean;
  onSubmit: (rows: DenemeRowOutput[]) => void;
  onClose: () => void;
  audience: "student" | "coach";
}) {
  const [drafts, setDrafts] = React.useState<Record<number, Draft>>(() =>
    Object.fromEntries(
      rows.map((r) => [
        r.id,
        {
          // İlk açılışta çözülmemiş deneme de "çözdüm" gelir (öğrenci işaretlemek için açtı)
          solved: true,
          correct: toStr(r.correct),
          wrong: toStr(r.wrong),
          blank: toStr(r.blank),
          qn: toStr(r.questionCount),
          dur: toStr(r.durationMinutes),
        },
      ]),
    ),
  );

  function set(id: number, patch: Partial<Draft>) {
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));
  }

  const computed = rows.map((r) => {
    const d = drafts[r.id];
    const c = num(d.correct);
    const w = num(d.wrong);
    const qn = num(d.qn);
    const typedBlank = num(d.blank);
    const hasResult = c != null || w != null;
    const autoBlank = hasResult && qn != null ? Math.max(0, qn - (c ?? 0) - (w ?? 0)) : null;
    const blank = typedBlank ?? autoBlank;
    const total = (c ?? 0) + (w ?? 0) + (blank ?? 0);
    const over = hasResult && qn != null && total > qn;
    const bad =
      [c, w, typedBlank].some((v) => v != null && v < 0) ||
      (qn != null && (qn < 1 || qn > 200)) ||
      (num(d.dur) != null && (num(d.dur)! < 1 || num(d.dur)! > 600));
    const net = hasResult ? (c ?? 0) - (w ?? 0) / penaltyFor(r.examSection) : null;
    return { r, d, c, w, qn, typedBlank, autoBlank, hasResult, over, bad, net };
  });

  const invalid = computed.some((x) => x.d.solved && (x.over || x.bad));
  const anyResult = computed.some((x) => x.d.solved && x.hasResult);

  function build(withResults: boolean): DenemeRowOutput[] {
    return computed.map((x) => {
      if (!x.d.solved) return { item_id: x.r.id, solved: false };
      const out: DenemeRowOutput = { item_id: x.r.id, solved: true };
      if (x.qn != null && x.qn !== x.r.questionCount) out.question_count = x.qn;
      const dur = num(x.d.dur);
      if (dur != null) out.duration_minutes = dur;
      if (withResults && x.hasResult) {
        out.correct = x.c ?? 0;
        out.wrong = x.w ?? 0;
        if (x.typedBlank != null) out.blank = x.typedBlank;
      }
      return out;
    });
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle className="break-words">{title}</DialogTitle>
        <DialogDescription>
          {audience === "student"
            ? "Her denemenin doğru ve yanlışını gir; boş kendiliğinden hesaplanır. Kaynağındaki soru sayısı farklıysa düzelt. Süre isteğe bağlı."
            : "Öğrenci adına sonuç gir ya da düzelt. Boş, soru − doğru − yanlış olarak hesaplanır."}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-3" data-section="deneme-results">
        {computed.map(({ r, d, autoBlank, over, net, hasResult }, idx) => (
          <div
            key={r.id}
            data-testid="deneme-row"
            className={cn(
              "rounded-lg border p-3",
              d.solved ? "border-border" : "border-dashed border-border bg-muted/40",
            )}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="min-w-0 break-words text-sm font-medium">
                {rows.length > 1 ? `${idx + 1}. ` : ""}
                {r.label}
              </p>
              <div role="radiogroup" aria-label={`${r.label} durumu`} className="inline-flex rounded-md border border-input p-0.5 text-xs">
                {[true, false].map((v) => (
                  <button
                    key={String(v)}
                    type="button"
                    role="radio"
                    aria-checked={d.solved === v}
                    onClick={() => set(r.id, { solved: v })}
                    className={cn(
                      "rounded px-2.5 py-0.5 font-medium transition",
                      d.solved === v ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {v ? "Çözdüm" : "Çözmedim"}
                  </button>
                ))}
              </div>
            </div>

            {d.solved ? (
              <>
                <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5">
                  <NumField label="Doğru" value={d.correct} onChange={(v) => set(r.id, { correct: v })} tone="emerald" />
                  <NumField label="Yanlış" value={d.wrong} onChange={(v) => set(r.id, { wrong: v })} tone="rose" />
                  <NumField
                    label="Boş"
                    value={d.blank}
                    placeholder={autoBlank != null ? String(autoBlank) : "—"}
                    onChange={(v) => set(r.id, { blank: v })}
                  />
                  <NumField label="Soru" value={d.qn} onChange={(v) => set(r.id, { qn: v })} />
                  <NumField label="Süre (dk)" value={d.dur} placeholder="—" onChange={(v) => set(r.id, { dur: v })} />
                </div>
                <p
                  className={cn(
                    "mt-1.5 text-xs",
                    over ? "text-rose-700 dark:text-rose-300" : "text-muted-foreground",
                  )}
                >
                  {over
                    ? "Doğru + yanlış + boş soru sayısından fazla — kaynağındaki soru sayısı farklıysa “Soru”yu düzelt."
                    : hasResult && net != null
                      ? <>Net <span className="font-semibold text-foreground tabular-nums">{fmtNet(net)}</span>
                        {" "}· {r.examSection === "lgs" ? "3 yanlış 1 doğruyu götürür" : "4 yanlış 1 doğruyu götürür"}</>
                      : "Sonucu şimdi girmezsen deneme çözüldü sayılır, sonuç bekler."}
                </p>
              </>
            ) : (
              <p className="mt-1.5 text-xs text-muted-foreground">Bu deneme çözülmedi olarak kalır.</p>
            )}
          </div>
        ))}
      </div>

      <DialogFooter className="flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={onClose}
          className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          Vazgeç
        </button>
        <div className="flex flex-col gap-2 sm:flex-row">
          {audience === "student" ? (
            <button
              type="button"
              disabled={saving}
              onClick={() => onSubmit(build(false))}
              className="rounded-md border border-input px-3 py-1.5 text-sm font-medium hover:bg-muted disabled:opacity-50"
            >
              Sonucu sonra gireceğim
            </button>
          ) : null}
          <button
            type="button"
            disabled={saving || invalid}
            onClick={() => onSubmit(build(true))}
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-cyan-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-cyan-800 disabled:opacity-50"
          >
            {saving ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
            {anyResult ? "Kaydet" : "Kaydet (sonuçsuz)"}
          </button>
        </div>
      </DialogFooter>
    </>
  );
}

function NumField({
  label, value, onChange, placeholder, tone,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  tone?: "emerald" | "rose";
}) {
  return (
    <label className="min-w-0">
      <span
        className={cn(
          "mb-0.5 block text-[11px] font-medium",
          tone === "emerald"
            ? "text-emerald-700 dark:text-emerald-300"
            : tone === "rose"
              ? "text-rose-700 dark:text-rose-300"
              : "text-muted-foreground",
        )}
      >
        {label}
      </span>
      <input
        type="number"
        inputMode="numeric"
        min={0}
        value={value}
        placeholder={placeholder}
        aria-label={label}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-right text-sm tabular-nums placeholder:text-muted-foreground/70"
      />
    </label>
  );
}

/** Kartlarda tek satır özet: "24D 3Y 3B · net 23,25 · 35 dk" / "sonuç bekliyor" / "çözülmedi". */
export function denemeSummary(r: {
  completed: number;
  correct: number | null | undefined;
  wrong: number | null | undefined;
  blank: number | null | undefined;
  net: number | null | undefined;
  durationMinutes: number | null | undefined;
  resultPending: boolean | undefined;
}): { text: string; tone: "done" | "pending" | "todo" } {
  if (r.completed <= 0) return { text: "çözülmedi", tone: "todo" };
  if (r.resultPending || (r.correct == null && r.wrong == null)) return { text: "sonuç bekliyor", tone: "pending" };
  const parts = [`${r.correct ?? 0}D ${r.wrong ?? 0}Y ${r.blank ?? 0}B`];
  if (r.net != null) parts.push(`net ${fmtNet(r.net)}`);
  if (r.durationMinutes) parts.push(`${r.durationMinutes} dk`);
  return { text: parts.join(" · "), tone: "done" };
}
