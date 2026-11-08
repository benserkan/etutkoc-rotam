"use client";

/**
 * Deneme sonuçları penceresi (D2, 2026-10-20) — öğrenci + koç ortak.
 *
 * Bir görevdeki her deneme ayrı satır (1 satır = 1 deneme). Öğrenci doğru/yanlış girer,
 * boş otomatik hesaplanır (soru − D − Y; elle de yazılabilir), net anında görünür.
 * Soru sayısı ESNEK: koçun yazdığı değer başlangıçtır; kaynakta farklıysa öğrenci düzeltir.
 * "Sonucu sonra gireceğim" denemeyi çözüldü sayar, sonuç bekler (2 gün sonra hatırlatma).
 *
 * TOPLU GİRİŞ (2026-11-08): öğrenci birden çok denemenin toplamını tek satıra yazarsa
 * (doğru + yanlış [+ boş] deneme başına soru sayısını aşar ya da "Soru"yu katına çıkarır)
 * pencere sorar: "Birden çok denemenin toplamını mı yazdın?" — öneri N = girilen soru ÷
 * deneme başına soru (yukarı yuvarlanır, kalan boş deneme sayısıyla sınırlı). Evet → sonraki
 * boş deneme satırları bu satıra bağlanır, soru sayısı N × deneme başına olur; Hayır → bu
 * denemenin soru sayısı düzeltilir. Toplu satır analize deneme adedi ağırlığıyla girer.
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
  /** Toplu sonuç: sonucu başka satırda (o satırın id'si) */
  combinedIntoId?: number | null;
  /** Bu satırın sonucu kaç denemeyi kapsıyor (toplu girişte >1) */
  combinedCount?: number | null;
}

export interface DenemeRowOutput {
  item_id: number;
  solved: boolean;
  correct?: number | null;
  wrong?: number | null;
  blank?: number | null;
  question_count?: number | null;
  duration_minutes?: number | null;
  combine_with?: number[];
}

interface Draft {
  solved: boolean;
  /** Bu satıra bağlanan (toplu girilen) diğer deneme satırları */
  combine: number[];
  /** "Hayır, toplu değil" dendi — öneri bu satırda bir daha sorulmaz */
  noCombine: boolean;
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
  // Deneme başına soru (toplu satırda kayıtlı soru = toplam → deneme adedine bölünür)
  const perQ = React.useMemo(
    () => Object.fromEntries(rows.map((r) => {
      const k = Math.max(1, r.combinedCount ?? 1);
      return [r.id, r.questionCount != null ? Math.max(1, Math.round(r.questionCount / k)) : null];
    })) as Record<number, number | null>,
    [rows],
  );
  const [drafts, setDrafts] = React.useState<Record<number, Draft>>(() =>
    Object.fromEntries(
      rows.map((r) => [
        r.id,
        {
          // İlk açılışta çözülmemiş deneme de "çözdüm" gelir (öğrenci işaretlemek için açtı)
          solved: true,
          combine: rows.filter((o) => o.combinedIntoId === r.id).map((o) => o.id),
          noCombine: false,
          correct: toStr(r.correct),
          wrong: toStr(r.wrong),
          blank: toStr(r.blank),
          qn: toStr(r.questionCount),
          dur: toStr(r.durationMinutes),
        },
      ]),
    ),
  );
  const coveredBy: Record<number, number> = {};
  for (const r of rows) for (const o of drafts[r.id].combine) coveredBy[o] = r.id;

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
    // Toplu giriş sinyali: girilen soru (D+Y[+B]) ya da yazılan "Soru" deneme başına sayıyı aşıyor.
    const pq = perQ[r.id];
    const entered = (c ?? 0) + (w ?? 0) + (typedBlank ?? 0);
    const signal = Math.max(hasResult ? entered : 0, qn != null && pq != null && qn > pq ? qn : 0);
    // Bağlanabilecek satırlar: bu satırdan sonra (sonra önce) gelen, sonucu girilmemiş ve
    // başka toplu sonuca bağlı olmayan denemeler.
    const idx = rows.indexOf(r);
    const free = [...rows.slice(idx + 1), ...rows.slice(0, idx)].filter((o) => {
      const od = drafts[o.id];
      return coveredBy[o.id] == null && od.combine.length === 0
        && num(od.correct) == null && num(od.wrong) == null;
    });
    const suggestK = pq != null && signal > pq && d.combine.length === 0 && !d.noCombine && free.length > 0
      ? Math.min(Math.ceil(signal / pq), free.length + 1)
      : 0;
    return { r, d, c, w, qn, typedBlank, autoBlank, hasResult, over, bad, net, pq, signal, free, suggestK };
  });

  function combine(id: number, k: number) {
    const x = computed.find((y) => y.r.id === id)!;
    const ids = x.free.slice(0, k - 1).map((o) => o.id);
    const q = x.pq != null ? x.pq * k : num(x.d.qn);
    setDrafts((d) => {
      const nd = { ...d, [id]: { ...d[id], combine: ids, qn: q != null ? String(q) : d[id].qn } };
      for (const o of ids) nd[o] = { ...nd[o], solved: true };
      return nd;
    });
  }

  function split(id: number) {
    const pq = perQ[id];
    setDrafts((d) => ({
      ...d,
      [id]: { ...d[id], combine: [], noCombine: true, qn: pq != null ? String(pq) : d[id].qn },
    }));
  }

  const invalid = computed.some((x) => x.d.solved && (x.over || x.bad));
  const anyResult = computed.some((x) => x.d.solved && x.hasResult);

  function build(withResults: boolean): DenemeRowOutput[] {
    const out: DenemeRowOutput[] = [];
    for (const x of computed) {
      if (coveredBy[x.r.id] != null) continue; // toplu satırla birlikte yazılır
      if (!x.d.solved) {
        out.push({ item_id: x.r.id, solved: false });
        continue;
      }
      const o: DenemeRowOutput = { item_id: x.r.id, solved: true };
      const grouped = withResults && x.hasResult && x.d.combine.length > 0;
      if (x.qn != null && (x.qn !== x.r.questionCount || grouped)) o.question_count = x.qn;
      const dur = num(x.d.dur);
      if (dur != null) o.duration_minutes = dur;
      if (withResults && x.hasResult) {
        o.correct = x.c ?? 0;
        o.wrong = x.w ?? 0;
        if (x.typedBlank != null) o.blank = x.typedBlank;
      }
      if (grouped) o.combine_with = x.d.combine;
      out.push(o);
    }
    // Toplu satır sonuçsuz kaydedilirse bağlı denemeler ayrı (çözüldü, sonuç bekler) yazılır.
    for (const x of computed) {
      const host = coveredBy[x.r.id];
      if (host == null) continue;
      const hx = computed.find((y) => y.r.id === host)!;
      if (!(withResults && hx.hasResult && hx.d.solved)) out.push({ item_id: x.r.id, solved: hx.d.solved });
    }
    return out;
  }

  const numberOf = (id: number) => rows.findIndex((r) => r.id === id) + 1;

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
        {computed.map(({ r, d, autoBlank, over, net, hasResult, pq, signal, suggestK, free }, idx) => {
          const host = coveredBy[r.id];
          if (host != null) {
            return (
              <div
                key={r.id}
                data-testid="deneme-row-covered"
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed border-cyan-600/50 bg-cyan-500/10 px-3 py-2 text-sm"
              >
                <span className="min-w-0 break-words">
                  {rows.length > 1 ? `${idx + 1}. ` : ""}{r.label}
                </span>
                <span className="text-xs font-medium text-cyan-900">
                  {numberOf(host)}. satırla birlikte toplu girildi
                </span>
              </div>
            );
          }
          const k = 1 + d.combine.length;
          const nums = [idx + 1, ...d.combine.map(numberOf)].sort((a, b) => a - b);
          return (
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
                  {k > 1 ? (
                    <span className="ml-2 inline-flex rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-medium text-white">
                      Toplu · {k} deneme
                    </span>
                  ) : null}
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
                    <NumField label={k > 1 ? "Soru (toplam)" : "Soru"} value={d.qn} onChange={(v) => set(r.id, { qn: v })} />
                    <NumField label="Süre (dk)" value={d.dur} placeholder="—" onChange={(v) => set(r.id, { dur: v })} />
                  </div>
                  {suggestK > 1 ? (
                    <div
                      data-testid="deneme-combine-ask"
                      className="mt-2 rounded-md border border-amber-500/60 bg-amber-500/10 p-2.5 text-xs text-amber-950"
                    >
                      <p className="font-medium">
                        {signal} soru girdin; bu denemede {pq} soru var. Birden çok denemenin toplamını mı yazdın?
                      </p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {Array.from({ length: free.length }, (_, i) => i + 2).map((n) => (
                          <button
                            key={n}
                            type="button"
                            onClick={() => combine(r.id, n)}
                            className={cn(
                              "rounded-md px-2.5 py-1 font-medium",
                              n === suggestK
                                ? "bg-cyan-700 text-white hover:bg-cyan-800"
                                : "border border-cyan-700/50 text-cyan-900 hover:bg-cyan-500/15",
                            )}
                          >
                            Evet, {n} deneme ({(pq ?? 0) * n} soru)
                          </button>
                        ))}
                        <button
                          type="button"
                          onClick={() => set(r.id, { noCombine: true, qn: String(signal) })}
                          className="rounded-md border border-input bg-background px-2.5 py-1 font-medium text-foreground hover:bg-muted"
                        >
                          Hayır, bu denemede {signal} soru var
                        </button>
                      </div>
                      <p className="mt-1.5 text-amber-900">
                        Denemeleri ayrı ayrı biliyorsan her birini kendi satırına yazman en doğrusu.
                      </p>
                    </div>
                  ) : null}
                  {k > 1 ? (
                    <p className="mt-1.5 text-xs text-cyan-900">
                      {nums.map((n) => `${n}.`).join(", ")} denemenin toplamı · analizde deneme başına
                      {" "}{k}&apos;ye bölünür.{" "}
                      <button type="button" onClick={() => split(r.id)} className="font-medium underline">
                        Ayrı gir
                      </button>
                    </p>
                  ) : null}
                  <p
                    className={cn(
                      "mt-1.5 text-xs",
                      over ? "text-rose-700" : "text-muted-foreground",
                    )}
                  >
                    {over
                      ? suggestK > 1
                        ? "Toplu girdiysen yukarıdan deneme sayısını seç; değilse “Soru”yu düzelt."
                        : "Doğru + yanlış + boş soru sayısından fazla — kaynağındaki soru sayısı farklıysa “Soru”yu düzelt."
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
          );
        })}
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
            ? "text-emerald-700"
            : tone === "rose"
              ? "text-rose-700"
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
  combinedIntoId?: number | null;
  combinedCount?: number | null;
}): { text: string; tone: "done" | "pending" | "todo" } {
  if (r.completed <= 0) return { text: "çözülmedi", tone: "todo" };
  if (r.combinedIntoId != null) return { text: "toplu sonuçta", tone: "done" };
  if (r.resultPending || (r.correct == null && r.wrong == null)) return { text: "sonuç bekliyor", tone: "pending" };
  const parts = [`${r.correct ?? 0}D ${r.wrong ?? 0}Y ${r.blank ?? 0}B`];
  if (r.net != null) parts.push(`net ${fmtNet(r.net)}`);
  if (r.durationMinutes) parts.push(`${r.durationMinutes} dk`);
  if ((r.combinedCount ?? 1) > 1) parts.push(`${r.combinedCount} deneme toplu`);
  return { text: parts.join(" · "), tone: "done" };
}
