"use client";

/**
 * Deneme görevi formu (D1, 2026-10-20).
 *
 * Koç iki tür deneme verir: BRANŞ (tek ders, çoğunlukla kaynaktan; fen gruplarında
 * soru az olduğu için 2-3 adet) ve GENEL (LGS/TYT/AYT/YDT). Kural: 1 kalem = 1 deneme;
 * "×2" verilen görev öğrencide 2 ayrı sonuç satırı olur. Soru sayısı koçun başlangıç
 * değeridir — öğrenci kendi kaynağındaki sayıya göre girişte değiştirebilir.
 *
 * Hızlı yol: koçun sık verdiği kalıplar çip olarak üstte (tek tık → görev).
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Info, Loader2, Plus, Sparkles } from "lucide-react";

import {
  denemeKeys,
  getDenemeOptions,
  templateToBody,
  type DenemeBookOption,
  type DenemeTaskBody,
  type DenemeTemplate,
} from "@/lib/api/deneme";
import { useAddPoolDeneme } from "@/lib/api/pool";
import { useCreateDenemeTask } from "@/lib/hooks/use-teacher-mutations";
import type { TaskPeriod } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

const COUNT_CHIPS = [1, 2, 3, 4];
const NO_SOURCE = "none";

const Q_SOURCE_LABEL: Record<string, string> = {
  label: "deneme adından",
  book: "kitapta kayıtlı",
  standard: "sınavdaki soru sayısı",
};

function sectionLabel(sec: string | null | undefined): string {
  if (!sec) return "";
  if (sec === "lgs") return "LGS";
  if (sec === "tyt") return "TYT";
  if (sec.startsWith("ayt")) return "AYT";
  return "";
}

export function DenemeForm({
  studentId,
  dayDate = "",
  period = null,
  onAfterAdd,
  target = "task",
}: {
  studentId: number;
  dayDate?: string;
  period?: TaskPeriod | null;
  onAfterAdd: () => void;
  /** "task" = programa görev (gün gün) · "pool" = havuza kalem (D1b) */
  target?: "task" | "pool";
}) {
  const q = useQuery({
    queryKey: denemeKeys.options(studentId),
    queryFn: () => getDenemeOptions(studentId),
    staleTime: 30_000,
  });
  const createTask = useCreateDenemeTask(studentId);
  const createPool = useAddPoolDeneme(studentId);
  const create = target === "pool" ? createPool : createTask;

  const [kind, setKind] = React.useState<"brans" | "genel">("brans");
  const [subjectId, setSubjectId] = React.useState<number | null>(null);
  // Birleşik branş (TYT Fen …) seçiliyse anahtarı; ders seçimini geçersiz kılar.
  const [groupKey, setGroupKey] = React.useState<string | null>(null);
  // "none" = kaynaksız; null = ilk uygun kaynak (varsayılan)
  const [source, setSource] = React.useState<string | null>(null);
  const [genelKey, setGenelKey] = React.useState<string | null>(null);
  const [count, setCount] = React.useState(1);
  const [qOverride, setQOverride] = React.useState<string | null>(null);
  const [name, setName] = React.useState("");

  const data = q.data;
  const subjects = data?.subjects ?? [];
  const books = data?.books ?? [];
  const presets = data?.genel_presets ?? [];
  // Havuz kalemi derse bağlı olmak zorunda — birleşik branş yalnız programda.
  const groups = target === "pool" ? [] : data?.brans_groups ?? [];
  const templates = (data?.templates ?? []).filter((t) => target !== "pool" || !t.group_key);
  const group = kind === "brans" ? groups.find((g) => g.key === groupKey) ?? null : null;

  // Kaynağı olan dersler önce
  const sortedSubjects = [...subjects].sort(
    (a, b) => Number(b.deneme_book_count > 0) - Number(a.deneme_book_count > 0),
  );
  const effSubjectId = subjectId ?? sortedSubjects[0]?.id ?? null;
  const subject = subjects.find((s) => s.id === effSubjectId) ?? null;

  const sourceBooks: DenemeBookOption[] =
    kind === "brans"
      ? group
        ? []
        : books.filter((b) => b.type === "brans_denemesi" && b.subject_id === effSubjectId)
      : books.filter((b) => b.type === "genel_deneme");

  const effSource =
    source ?? (sourceBooks[0] ? String(sourceBooks[0].book_id) : NO_SOURCE);
  const book =
    effSource !== NO_SOURCE
      ? sourceBooks.find((b) => String(b.book_id) === effSource) ?? null
      : null;
  const preset =
    presets.find((p) => p.key === genelKey) ?? presets[0] ?? null;

  const defaultQ: { n: number | null; why: string } = book?.question_count
    ? { n: book.question_count, why: Q_SOURCE_LABEL[book.question_source] ?? "" }
    : group
      ? { n: group.question_count, why: "sınav standardı" }
      : kind === "brans"
      ? {
          n: subject?.standard_question_count ?? null,
          why: subject?.standard_question_count ? Q_SOURCE_LABEL.standard : "",
        }
      : { n: preset?.question_count ?? null, why: preset ? "türün soru sayısı" : "" };
  const qValue = qOverride ?? (defaultQ.n ? String(defaultQ.n) : "");
  const qNum = Number(qValue);
  const qValid = Number.isFinite(qNum) && qNum >= 1 && qNum <= 200;

  const base = { date: dayDate, period, scheduled_hour: null };

  function resetAfter() {
    setCount(1);
    setQOverride(null);
    setName("");
    onAfterAdd();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!qValid) return;
    const body: DenemeTaskBody = {
      ...base,
      kind,
      count,
      question_count: qNum,
      name: name.trim() || null,
      book_id: book?.book_id ?? null,
      subject_id: kind === "brans" && !book && !group ? effSubjectId : null,
      group_key: group?.key ?? null,
      genel_key: kind === "genel" ? preset?.key ?? null : null,
    };
    send(body);
  }

  function send(body: DenemeTaskBody) {
    if (target === "pool") {
      const { date: _d, period: _p, scheduled_hour: _h, ...rest } = body;
      void _d; void _p; void _h;
      createPool.mutate(rest, { onSuccess: resetAfter });
    } else {
      createTask.mutate({ body }, { onSuccess: resetAfter });
    }
  }

  function applyTemplate(t: DenemeTemplate) {
    send(templateToBody(t, base, presets));
  }

  if (q.isLoading) {
    return (
      <p className="inline-flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" aria-hidden /> Deneme seçenekleri yükleniyor…
      </p>
    );
  }

  const canSubmit =
    qValid &&
    (kind === "brans" ? effSubjectId != null || group != null : preset != null) &&
    !create.isPending;

  const previewTitle =
    kind === "brans"
      ? `${book ? book.name : `${group?.label ?? subject?.name ?? "Ders"} branş denemesi`}${count > 1 ? ` ×${count}` : ""}`
      : `${name.trim() || book?.name || preset?.label || "Genel deneme"}${count > 1 ? ` ×${count}` : ""}`;

  return (
    <form method="post" onSubmit={submit} className="space-y-3" aria-label="Deneme ekleme">
      {templates.length > 0 ? (
        <div className="space-y-1.5">
          <p className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
            <Sparkles className="size-3" aria-hidden /> Sık verdiklerin — tek tıkla ekle
          </p>
          <div className="flex flex-wrap gap-1.5">
            {templates.map((t, i) => (
              <button
                key={`${t.kind}-${t.subject_id}-${t.book_id}-${t.count}-${t.question_count}-${i}`}
                type="button"
                disabled={create.isPending}
                onClick={() => applyTemplate(t)}
                className="inline-flex items-center gap-1 rounded-full border border-violet-300 bg-violet-50 px-2.5 py-1 text-xs text-violet-900 hover:bg-violet-100 disabled:opacity-50 dark:border-violet-500/40 dark:bg-violet-500/15 dark:text-violet-100 dark:hover:bg-violet-500/25"
              >
                <Plus className="size-3" aria-hidden />
                {t.label}
                {t.kind === "brans" ? " branş" : ""} ×{t.count}
                <span className="text-violet-700 dark:text-violet-300">· {t.question_count} soru</span>
                {t.book_id ? <BookOpen className="size-3" aria-label="kaynaktan" /> : null}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div role="radiogroup" aria-label="Deneme türü" className="inline-flex rounded-md border border-input p-0.5">
        {(["brans", "genel"] as const).map((k) => (
          <button
            key={k}
            type="button"
            role="radio"
            aria-checked={kind === k}
            onClick={() => {
              setKind(k);
              setSource(null);
              setQOverride(null);
            }}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition",
              kind === k
                ? "bg-cyan-700 text-white"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {k === "brans" ? "Branş denemesi" : "Genel deneme"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-3">
        {kind === "brans" ? (
          <Field label="Ders">
            <select
              aria-label="Ders"
              value={group ? `g:${group.key}` : effSubjectId ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                if (v.startsWith("g:")) {
                  setGroupKey(v.slice(2));
                } else {
                  setGroupKey(null);
                  setSubjectId(Number(v));
                }
                setSource(null);
                setQOverride(null);
              }}
              className={SELECT_CLS}
            >
              {groups.length > 0 ? (
                <optgroup label="Birleşik branş denemeleri">
                  {groups.map((g) => (
                    <option key={g.key} value={`g:${g.key}`}>
                      {g.label} · {g.question_count} soru
                    </option>
                  ))}
                </optgroup>
              ) : null}
              <optgroup label="Tek ders">
                {sortedSubjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.deneme_book_count > 0 ? ` · ${s.deneme_book_count} kitap` : ""}
                  </option>
                ))}
              </optgroup>
            </select>
            {group ? (
              <p className="mt-1 text-[11px] text-muted-foreground">{group.covers}</p>
            ) : null}
          </Field>
        ) : (
          <Field label="Tür">
            <select
              aria-label="Genel deneme türü"
              value={preset?.key ?? ""}
              onChange={(e) => {
                setGenelKey(e.target.value);
                setQOverride(null);
              }}
              className={SELECT_CLS}
            >
              {presets.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label} · {p.question_count} soru
                </option>
              ))}
            </select>
          </Field>
        )}

      </div>

      <Field label="Kaynak">
        <div role="radiogroup" aria-label="Kaynak" className="grid grid-cols-1 @md:grid-cols-2 gap-1.5">
          {sourceBooks.map((b) => {
            const on = effSource === String(b.book_id);
            return (
              <button
                key={b.book_id}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => {
                  setSource(String(b.book_id));
                  setQOverride(null);
                }}
                className={cn(
                  "rounded-md border px-2.5 py-1.5 text-left text-sm transition",
                  on
                    ? "border-cyan-700 bg-cyan-700/10 ring-1 ring-cyan-700"
                    : "border-input hover:bg-muted",
                )}
              >
                <span className="block break-words font-medium">{b.name}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {b.next_sections[0]
                    ? `sıradaki: ${b.next_sections[0].label} · ${b.remaining_total} kaldı`
                    : "boş deneme kalmadı"}
                </span>
              </button>
            );
          })}
          <button
            type="button"
            role="radio"
            aria-checked={effSource === NO_SOURCE}
            onClick={() => {
              setSource(NO_SOURCE);
              setQOverride(null);
            }}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-left text-sm transition",
              effSource === NO_SOURCE
                ? "border-cyan-700 bg-cyan-700/10 ring-1 ring-cyan-700"
                : "border-input hover:bg-muted",
            )}
          >
            <span className="block font-medium">Kaynaksız</span>
            <span className="block text-[11px] text-muted-foreground">
              {kind === "brans" ? "özel ders, öğretmen denemesi" : "yayınevi, kurum denemesi"}
            </span>
          </button>
        </div>
      </Field>

      {book ? (
        <p className="break-words text-[11px] text-muted-foreground">
          {book.next_sections.length > 0 ? (
            <>
              Verilecek:{" "}
              <span className="font-medium text-foreground">
                {book.next_sections.slice(0, count).map((s) => s.label).join(", ")}
              </span>
              {count > book.remaining_total
                ? ` · kitapta ${book.remaining_total} deneme kaldı, fazlası kayıtlı sayının üstünde atanır`
                : ` · kitapta ${book.remaining_total} deneme kaldı`}
            </>
          ) : (
            "Bu kitapta boş deneme kalmadı — yine de atanabilir (kayıtlı sayının üstünde)."
          )}
        </p>
      ) : null}

      <div className="grid grid-cols-1 @md:grid-cols-2 gap-3 items-end">
        <Field label="Adet">
          <div className="flex flex-wrap items-center gap-1.5">
            {COUNT_CHIPS.map((n) => (
              <button
                key={n}
                type="button"
                aria-pressed={count === n}
                onClick={() => setCount(n)}
                className={cn(
                  "min-w-9 rounded-md border px-2.5 py-1 text-sm tabular-nums transition",
                  count === n
                    ? "border-cyan-700 bg-cyan-700 text-white"
                    : "border-input hover:bg-muted",
                )}
              >
                {n}
              </button>
            ))}
            <input
              type="number"
              min={1}
              max={data?.max_count ?? 10}
              aria-label="Adet (başka)"
              value={COUNT_CHIPS.includes(count) ? "" : count}
              placeholder="başka"
              onChange={(e) => {
                const n = Number(e.target.value);
                if (Number.isFinite(n) && n >= 1) setCount(Math.min(n, data?.max_count ?? 10));
              }}
              className="w-20 rounded-md border border-input bg-background px-2 py-1 text-sm tabular-nums"
            />
          </div>
        </Field>
        <Field label="Deneme başına soru">
          <input
            type="number"
            min={1}
            max={200}
            aria-label="Deneme başına soru"
            value={qValue}
            onChange={(e) => setQOverride(e.target.value)}
            placeholder="örn. 20"
            className={cn(
              "w-28 rounded-md border bg-background px-2 py-1 text-sm text-right tabular-nums",
              qValue && !qValid ? "border-rose-500" : "border-input",
            )}
          />
          {qOverride == null && defaultQ.why ? (
            <span className="ml-2 text-[11px] text-muted-foreground">{defaultQ.why}</span>
          ) : null}
        </Field>
      </div>

      {!book ? (
        <Field label="Ad (isteğe bağlı)">
          <input
            type="text"
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={kind === "brans" ? "örn. Özel ders matematik denemesi" : "örn. Özdebir TG-4"}
            className="w-full rounded-md border border-input bg-background px-2 py-1 text-sm"
          />
        </Field>
      ) : null}

      <div className="flex flex-col @md:flex-row @md:items-center gap-2 @md:justify-between">
        <p className="inline-flex items-start gap-1.5 text-[11px] text-muted-foreground">
          <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
          <span>
            <span className="font-medium text-foreground">{previewTitle}</span>
            {qValid ? ` (${qNum} soru)` : ""}
            {sectionLabel(kind === "brans" ? (group?.exam_section ?? subject?.exam_section) : preset?.exam_section)
              ? ` · ${sectionLabel(kind === "brans" ? (group?.exam_section ?? subject?.exam_section) : preset?.exam_section)}`
              : ""}
            {target === "pool"
              ? count > 1
                ? ` — havuza ${count} deneme; öğrenci kabına aldıkça her denemeyi ayrı girer.`
                : " — havuza 1 deneme."
              : count > 1
                ? ` — öğrenci ${count} denemenin sonucunu ayrı ayrı girer.`
                : " — öğrenci sonucunu doğru/yanlış olarak girer."}
          </span>
        </p>
        <button
          type="submit"
          disabled={!canSubmit}
          className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md bg-cyan-700 px-4 py-1.5 text-sm font-medium text-white hover:bg-cyan-800 disabled:opacity-40"
        >
          {create.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <Plus className="size-3.5" aria-hidden />
          )}
          {target === "pool" ? "Havuza ekle" : "Ekle"} · {count} deneme
        </button>
      </div>
    </form>
  );
}

const SELECT_CLS =
  "w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-xs font-medium text-muted-foreground">{label}</p>
      {children}
    </div>
  );
}
