"use client";

/**
 * Deneme analizi Faz 2 — "Gelişim Raporu" sekmesi (koç + öğrenci ortak).
 *
 * Hedef net · gelişim özeti · otomatik yorum (kural tabanlı, kredisiz) ·
 * aksiyon planı (koç: seçilenleri seans gündemine ekler) · ders gidişatı.
 * Veri tek kaynaktan: /exam-progress (app/services/exam_progress.py).
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarClock,
  CheckCircle2,
  ClipboardCopy,
  ClipboardList,
  Flag,
  Lightbulb,
  ListChecks,
  MessageCircle,
  Pencil,
  Printer,
  Share2,
  Target,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";
import { toast } from "sonner";

import { ExamSection } from "@/components/teacher/exams/exam-analytics";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  examProgressKeys,
  getExamProgress,
  progressReportPrintUrl,
  type ProgressSource,
} from "@/lib/api/exam-progress";
import { fmtNet, fmtSigned, fmtTRDate } from "@/lib/exam-format";
import { useAddAgendaItems, useSetExamTarget } from "@/lib/hooks/use-exam-progress-mutations";
import type {
  ExamProgressResponse,
  ProgressAction,
  ProgressSubject,
  ProgressTone,
} from "@/lib/types/exam-progress";
import { cn } from "@/lib/utils";

const TONE: Record<ProgressTone, { box: string; icon: React.ComponentType<{ className?: string }> }> = {
  good: {
    box: "border-emerald-200 bg-emerald-50 text-emerald-950 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100",
    icon: TrendingUp,
  },
  warn: {
    box: "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100",
    icon: TriangleAlert,
  },
  info: {
    box: "border-sky-200 bg-sky-50 text-sky-950 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100",
    icon: Lightbulb,
  },
};

const PRIORITY: Record<number, { label: string; cls: string }> = {
  1: { label: "Öncelikli", cls: "bg-rose-600 text-white" },
  2: { label: "Önemli", cls: "bg-amber-600 text-white" },
  3: { label: "Takip", cls: "bg-slate-600 text-white" },
};

export function ExamProgressReport({
  source,
  section,
  period,
  studentName,
}: {
  source: ProgressSource;
  section: string | null;
  period?: string;
  studentName?: string | null;
}) {
  const isTeacher = source.kind === "teacher";
  const q = useQuery({
    queryKey: examProgressKeys.progress(source, section, period),
    queryFn: () => getExamProgress(source, section, period),
    staleTime: 30_000,
  });
  const [targetOpen, setTargetOpen] = React.useState(false);

  if (q.isLoading) return <p className="text-sm text-muted-foreground">Gelişim raporu hazırlanıyor…</p>;
  if (q.isError || !q.data) {
    return <p className="text-sm text-rose-700 dark:text-rose-400">Gelişim raporu yüklenemedi.</p>;
  }
  const d = q.data;
  if (!d.stats) {
    return <p className="text-sm text-muted-foreground">Bu sınav türünde deneme yok.</p>;
  }
  const studentId = source.kind === "teacher" ? source.studentId : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {d.section_label} · {d.stats.count} deneme · son deneme {fmtTRDate(d.stats.last_date)}
        </p>
        <ReportShare data={d} studentName={studentName ?? d.student_name} studentId={studentId} />
      </div>

      {d.target_allowed === false ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
          Bu bir branş denemesi serisi: netler yalnız aynı dersin branş denemeleriyle
          kıyaslanır. Hedef net ve puan tahmini genel denemelere göre tutulur.
        </p>
      ) : (
        <TargetSection
          data={d}
          isTeacher={isTeacher}
          isParent={source.kind === "parent"}
          onEdit={() => setTargetOpen(true)}
        />
      )}

      <ExamSection
        icon={TrendingUp}
        title="Gelişim özeti"
        description="Bu türdeki tüm denemelerden; eğim = son 5 denemede deneme başına ortalama net değişimi."
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="İlk → son net" value={`${fmtNet(d.stats.first_net)} → ${fmtNet(d.stats.last_net)}`}
            sub={`${fmtSigned(d.stats.change)} net`} tone={d.stats.change >= 1 ? "good" : d.stats.change <= -1 ? "bad" : null} />
          <Stat label="Son 3 deneme ortalaması" value={fmtNet(d.stats.avg_last3)}
            sub={`Genel ortalama ${fmtNet(d.stats.avg_net)}`} />
          <Stat label="En iyi net" value={fmtNet(d.stats.best_net)} sub={`${d.stats.count} deneme içinde`} />
          <Stat label="Eğim (deneme başına)"
            value={d.stats.slope == null ? "—" : `${fmtSigned(d.stats.slope)}`}
            sub={d.stats.slope == null ? "En az 3 deneme gerekir" : "net / deneme"}
            tone={d.stats.slope == null ? null : d.stats.slope >= 0.5 ? "good" : d.stats.slope <= -0.5 ? "bad" : null} />
        </div>
      </ExamSection>

      {d.commentary.length ? (
        <ExamSection
          icon={Lightbulb}
          title="Otomatik yorum"
          description="Kayıtlı netlerden kural tabanlı çıkarımlar — yapay zekâ kullanılmaz, sayı uydurulmaz."
        >
          <ul className="space-y-2">
            {d.commentary.map((c) => {
              const t = TONE[c.tone] ?? TONE.info;
              const Icon = t.icon;
              return (
                <li key={c.text} className={cn("flex gap-2 rounded-lg border px-3 py-2 text-sm", t.box)}>
                  <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>{c.text}</span>
                </li>
              );
            })}
          </ul>
        </ExamSection>
      ) : null}

      <ActionPlan data={d} isTeacher={isTeacher} isParent={source.kind === "parent"} studentId={studentId} />

      {d.subjects.length ? <SubjectTrend subjects={d.subjects} hasTarget={!!d.target} /> : null}

      {isTeacher && studentId != null ? (
        <TargetDialog
          open={targetOpen}
          onOpenChange={setTargetOpen}
          studentId={studentId}
          data={d}
        />
      ) : null}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "good" | "bad" | null;
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-xl font-semibold tabular-nums",
          tone === "good" && "text-emerald-700 dark:text-emerald-400",
          tone === "bad" && "text-rose-700 dark:text-rose-400",
        )}
      >
        {value}
      </p>
      {sub ? <p className="mt-0.5 text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

// ---------------------------------------------------------------- hedef

function TargetSection({
  data,
  isTeacher,
  isParent = false,
  onEdit,
}: {
  data: ExamProgressResponse;
  isTeacher: boolean;
  isParent?: boolean;
  onEdit: () => void;
}) {
  const t = data.target;
  return (
    <ExamSection
      icon={Target}
      title="Hedef net"
      description={
        isTeacher
          ? "Koçun belirlediği hedef; fark son 3 denemenin ortalamasıyla ölçülür. Öğrenci de görür."
          : isParent
            ? "Koçun çocuğunuz için belirlediği hedef; fark son 3 denemenin ortalamasıyla ölçülür."
            : "Koçunun senin için belirlediği hedef; fark son 3 denemenin ortalamasıyla ölçülür."
      }
      actions={
        isTeacher ? (
          <Button size="sm" variant={t ? "outline" : "default"} onClick={onEdit}>
            {t ? <Pencil className="size-4" aria-hidden /> : <Flag className="size-4" aria-hidden />}
            {t ? "Hedefi düzenle" : "Hedef belirle"}
          </Button>
        ) : null
      }
    >
      {!t ? (
        <p className="text-sm text-muted-foreground">
          {isTeacher
            ? `${data.section_label} için hedef net belirlenmedi. Hedef girilince fark, gereken tempo ve ders hedefleri bu rapora eklenir.`
            : isParent
              ? "Koç henüz bu deneme türü için hedef belirlemedi."
              : "Koçun henüz bu deneme türü için hedef belirlemedi."}
        </p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
            <div>
              <p className="text-xs text-muted-foreground">Hedef</p>
              <p className="text-3xl font-semibold tabular-nums">{fmtNet(t.target_net)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Şu an ({t.basis})</p>
              <p className="text-xl font-semibold tabular-nums">{fmtNet(t.basis_net)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Kalan</p>
              <p
                className={cn(
                  "text-xl font-semibold tabular-nums",
                  (t.gap ?? 0) <= 0 ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400",
                )}
              >
                {(t.gap ?? 0) <= 0 ? "Hedef tuttu" : `${fmtNet(t.gap)} net`}
              </p>
            </div>
            {t.target_date ? (
              <div>
                <p className="text-xs text-muted-foreground">Hedef tarih</p>
                <p className="flex items-center gap-1 text-sm font-medium">
                  <CalendarClock className="size-4" aria-hidden />
                  {fmtTRDate(t.target_date)}
                  {t.weeks_left != null ? ` · ${t.weeks_left} hafta` : ""}
                </p>
              </div>
            ) : null}
          </div>
          {t.progress_pct != null ? (
            <div>
              <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full rounded-full",
                    t.progress_pct >= 100 ? "bg-emerald-600" : t.progress_pct >= 80 ? "bg-cyan-600" : "bg-amber-500",
                  )}
                  style={{ width: `${Math.min(100, t.progress_pct)}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                Hedefin %{String(t.progress_pct).replace(".", ",")}&apos;i
                {t.per_week_needed ? ` · hedef tarihe kadar haftada ${fmtNet(t.per_week_needed)} net artış gerekir` : ""}
                {t.exams_needed_at_pace ? ` · bu tempoyla ~${t.exams_needed_at_pace} deneme sonra` : ""}
              </p>
            </div>
          ) : null}
          {t.note ? (
            <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
              <span className="font-medium">Koç notu: </span>
              {t.note}
            </p>
          ) : null}
        </div>
      )}
    </ExamSection>
  );
}

function TargetDialog({
  open,
  onOpenChange,
  studentId,
  data,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  studentId: number;
  data: ExamProgressResponse;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        {open ? <TargetForm studentId={studentId} data={data} onDone={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}

function TargetForm({
  studentId,
  data,
  onDone,
}: {
  studentId: number;
  data: ExamProgressResponse;
  onDone: () => void;
}) {
  const t = data.target;
  const [net, setNet] = React.useState(t ? String(t.target_net).replace(".", ",") : "");
  const [dateV, setDateV] = React.useState(t?.target_date ?? "");
  const [note, setNote] = React.useState(t?.note ?? "");
  const [subj, setSubj] = React.useState<Record<string, string>>(() => {
    const o: Record<string, string> = {};
    for (const s of data.subjects) {
      const v = t?.subjects?.[s.name];
      o[s.name] = v != null ? String(v).replace(".", ",") : "";
    }
    return o;
  });
  const mut = useSetExamTarget(studentId);
  const parse = (v: string) => {
    const n = Number(v.replace(",", "."));
    return v.trim() === "" || Number.isNaN(n) ? null : n;
  };
  const save = () => {
    const tn = parse(net);
    if (tn == null) {
      toast.error("Hedef net girin");
      return;
    }
    const subjects: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(subj)) subjects[k] = parse(v);
    mut.mutate(
      { section: data.section ?? "", target_net: tn, target_date: dateV || null, subjects, note: note || null },
      { onSuccess: onDone },
    );
  };
  return (
    <>
      <DialogHeader>
        <DialogTitle>{data.section_label} hedef neti</DialogTitle>
        <DialogDescription>
          Son 3 denemenin ortalaması {fmtNet(data.stats?.avg_last3)} · en iyi {fmtNet(data.stats?.best_net)}.
          Ders hedefleri isteğe bağlı.
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Toplam hedef net</span>
            <input
              inputMode="decimal"
              value={net}
              onChange={(e) => setNet(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Toplam hedef net"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Hedef tarih (isteğe bağlı)</span>
            <input
              type="date"
              value={dateV}
              onChange={(e) => setDateV(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Hedef tarih"
            />
          </label>
        </div>
        {data.subjects.length ? (
          <div>
            <p className="mb-1 text-xs text-muted-foreground">Ders hedefleri (net)</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {data.subjects.map((s) => (
                <label key={s.name} className="flex items-center justify-between gap-2 text-sm">
                  <span className="min-w-0 break-words">
                    {s.name}
                    <span className="ml-1 text-[11px] text-muted-foreground">(son {fmtNet(s.last)})</span>
                  </span>
                  <input
                    inputMode="decimal"
                    value={subj[s.name] ?? ""}
                    onChange={(e) => setSubj((o) => ({ ...o, [s.name]: e.target.value }))}
                    className="h-8 w-20 shrink-0 rounded-md border border-input bg-background px-2 text-sm"
                    aria-label={`${s.name} hedef net`}
                  />
                </label>
              ))}
            </div>
          </div>
        ) : null}
        <label className="block text-sm">
          <span className="mb-1 block text-xs text-muted-foreground">Hedef notu (öğrenci de görür)</span>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={300}
            rows={2}
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm"
          />
        </label>
      </div>
      <DialogFooter className="gap-2">
        {data.target ? (
          <Button
            variant="outline"
            onClick={() =>
              mut.mutate({ section: data.section ?? "", target_net: null }, { onSuccess: onDone })
            }
            disabled={mut.isPending}
          >
            Hedefi kaldır
          </Button>
        ) : null}
        <Button onClick={save} disabled={mut.isPending}>
          Kaydet
        </Button>
      </DialogFooter>
    </>
  );
}

// ---------------------------------------------------------------- aksiyon planı

function ActionPlan({
  data,
  isTeacher,
  isParent = false,
  studentId,
}: {
  data: ExamProgressResponse;
  isTeacher: boolean;
  isParent?: boolean;
  studentId: number | null;
}) {
  const [picked, setPicked] = React.useState<Set<string>>(() => new Set());
  const add = useAddAgendaItems(studentId ?? 0);
  if (!data.actions.length) return null;
  const selectable = data.actions.filter((a) => !a.queued);
  const toggle = (k: string) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  const addPicked = () => {
    const items = data.actions
      .filter((a) => picked.has(a.key))
      .map((a) => ({ text: `${a.title} — ${a.detail}`, key: a.key, exam_id: a.exam_id, source: "exam" }));
    if (!items.length) return;
    add.mutate(items, { onSuccess: () => setPicked(new Set()) });
  };
  return (
    <ExamSection
      icon={ListChecks}
      title={isTeacher ? "Aksiyon planı" : isParent ? "Çalışma öncelikleri" : "Çalışma önceliklerin"}
      description={
        isTeacher
          ? "Net fırsatı, unutulan konular, ders düşüşleri, boş/yanlış davranışı ve hedef farkından türetilir. Seçtiklerini sıradaki seansın gündemine ekleyebilirsin."
          : isParent
            ? "Deneme sonuçlarından çıkan, öncelik sırasına göre çalışma önerileri — koçunuz programı buna göre şekillendirir."
            : "Deneme sonuçlarından çıkan, öncelik sırasına göre çalışma önerileri."
      }
      actions={
        isTeacher && selectable.length ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setPicked((s) =>
                  s.size === selectable.length ? new Set() : new Set(selectable.map((a) => a.key)),
                )
              }
            >
              {picked.size === selectable.length ? "Seçimi temizle" : "Tümünü seç"}
            </Button>
            <Button size="sm" onClick={addPicked} disabled={!picked.size || add.isPending}>
              <ClipboardList className="size-4" aria-hidden />
              Seansa ekle{picked.size ? ` (${picked.size})` : ""}
            </Button>
          </>
        ) : null
      }
    >
      <ul className="space-y-2">
        {data.actions.map((a) => (
          <ActionRow
            key={a.key}
            a={a}
            isTeacher={isTeacher}
            checked={picked.has(a.key)}
            onToggle={() => toggle(a.key)}
          />
        ))}
      </ul>
    </ExamSection>
  );
}

function ActionRow({
  a,
  isTeacher,
  checked,
  onToggle,
}: {
  a: ProgressAction;
  isTeacher: boolean;
  checked: boolean;
  onToggle: () => void;
}) {
  const p = PRIORITY[a.priority] ?? PRIORITY[3];
  const body = (
    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{a.title}</span>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-semibold", p.cls)}>{p.label}</span>
        {isTeacher && a.queued ? (
          <span className="inline-flex items-center gap-1 rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">
            <CheckCircle2 className="size-3" aria-hidden />
            Seans gündeminde
          </span>
        ) : null}
      </div>
      <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{a.detail}</p>
    </div>
  );
  if (!isTeacher || a.queued) {
    return <li className="flex gap-3 rounded-lg border border-border px-3 py-2 text-sm">{body}</li>;
  }
  return (
    <li>
      <label
        className={cn(
          "flex cursor-pointer gap-3 rounded-lg border px-3 py-2 text-sm transition-colors",
          checked ? "border-cyan-600 bg-cyan-500/5" : "border-border hover:bg-muted/40",
        )}
      >
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="mt-1 size-4 shrink-0 accent-cyan-700"
          aria-label={`${a.title} seansa eklenecek`}
        />
        {body}
      </label>
    </li>
  );
}

// ---------------------------------------------------------------- ders gidişatı

function SubjectTrend({ subjects, hasTarget }: { subjects: ProgressSubject[]; hasTarget: boolean }) {
  const withTarget = hasTarget && subjects.some((s) => s.target != null);
  return (
    <ExamSection
      title="Ders gidişatı"
      description="Her dersin ilk ve son denemedeki neti, değişimi ve deneme başına eğimi."
    >
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Ders</th>
              <th className="py-2 pr-3 text-right font-medium">İlk</th>
              <th className="py-2 pr-3 text-right font-medium">Son</th>
              <th className="py-2 pr-3 text-right font-medium">Değişim</th>
              <th className="py-2 pr-3 text-right font-medium">Eğim</th>
              {withTarget ? (
                <>
                  <th className="py-2 pr-3 text-right font-medium">Hedef</th>
                  <th className="py-2 text-right font-medium">Kalan</th>
                </>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {subjects.map((s) => (
              <tr key={s.name} className="border-b border-border/60 last:border-0">
                <td className="py-2 pr-3">{s.name}</td>
                <td className="py-2 pr-3 text-right tabular-nums">{fmtNet(s.first)}</td>
                <td className="py-2 pr-3 text-right font-medium tabular-nums">{fmtNet(s.last)}</td>
                <td
                  className={cn(
                    "py-2 pr-3 text-right tabular-nums",
                    (s.change ?? 0) >= 1 && "text-emerald-700 dark:text-emerald-400",
                    (s.change ?? 0) <= -1 && "text-rose-700 dark:text-rose-400",
                  )}
                >
                  {s.change == null ? "—" : fmtSigned(s.change)}
                </td>
                <td className="py-2 pr-3 text-right tabular-nums">{s.slope == null ? "—" : fmtSigned(s.slope)}</td>
                {withTarget ? (
                  <>
                    <td className="py-2 pr-3 text-right tabular-nums">{s.target == null ? "—" : fmtNet(s.target)}</td>
                    <td
                      className={cn(
                        "py-2 text-right tabular-nums",
                        s.gap != null && s.gap <= 0 && "text-emerald-700 dark:text-emerald-400",
                        s.gap != null && s.gap > 0 && "text-amber-700 dark:text-amber-400",
                      )}
                    >
                      {s.gap == null ? "—" : s.gap <= 0 ? "tuttu" : fmtNet(s.gap)}
                    </td>
                  </>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </ExamSection>
  );
}

// ---------------------------------------------------------------- paylaşım

export function buildProgressShareText(d: ExamProgressResponse, studentName?: string | null): string {
  const s = d.stats;
  if (!s) return "";
  const lines: string[] = [];
  lines.push(`*${studentName ? `${studentName} — ` : ""}${d.section_label} gelişim raporu*`);
  lines.push(`${s.count} deneme · son deneme ${fmtTRDate(s.last_date)}`);
  lines.push("");
  lines.push(`Net: ${fmtNet(s.first_net)} → ${fmtNet(s.last_net)} (${fmtSigned(s.change)})`);
  lines.push(`Son 3 deneme ortalaması: ${fmtNet(s.avg_last3)} · en iyi: ${fmtNet(s.best_net)}`);
  if (d.target) {
    lines.push(
      `Hedef: ${fmtNet(d.target.target_net)} net · ${
        (d.target.gap ?? 0) <= 0 ? "hedef tuttu" : `kalan ${fmtNet(d.target.gap)} net`
      }`,
    );
  }
  if (d.commentary.length) {
    lines.push("");
    for (const c of d.commentary.slice(0, 4)) lines.push(`• ${c.text}`);
  }
  if (d.actions.length) {
    lines.push("");
    lines.push("Öncelikler:");
    for (const a of d.actions.slice(0, 5)) lines.push(`• ${a.title}`);
  }
  return lines.join("\n");
}

function ReportShare({
  data,
  studentName,
  studentId,
}: {
  data: ExamProgressResponse;
  studentName?: string | null;
  studentId: number | null;
}) {
  const text = () => buildProgressShareText(data, studentName);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {studentId != null ? (
        <Button
          size="sm"
          variant="outline"
          onClick={() => window.open(progressReportPrintUrl(studentId, data.section), "_blank", "noopener")}
          title="A4 gelişim raporu — yazdır ya da PDF olarak kaydet"
        >
          <Printer className="size-4" aria-hidden />
          Raporu yazdır / PDF
        </Button>
      ) : null}
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button size="sm" variant="outline">
            <Share2 className="size-4" aria-hidden />
            Raporu paylaş
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          <DropdownMenuItem
            onSelect={() => window.open(`https://wa.me/?text=${encodeURIComponent(text())}`, "_blank", "noopener")}
          >
            <MessageCircle className="size-4 text-emerald-600 dark:text-emerald-300" aria-hidden />
            WhatsApp ile gönder
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={async () => {
              try {
                await navigator.clipboard.writeText(text());
                toast.success("Rapor özeti kopyalandı");
              } catch {
                toast.error("Kopyalanamadı");
              }
            }}
          >
            <ClipboardCopy className="size-4" aria-hidden />
            Özeti kopyala
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
