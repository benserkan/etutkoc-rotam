"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ChevronDown,
  Loader2,
  Minus,
  Plus,
  TrendingDown,
  TrendingUp,
  Trash2,
  X,
} from "lucide-react";

import { getTeacherStudentExams, teacherKeys } from "@/lib/api/teacher";
import { useCreateExam, useDeleteExam } from "@/lib/hooks/use-teacher-mutations";
import type {
  ExamResultRow,
  ExamSectionValue,
  ExamSubjectInput,
  StudentExamListResponse,
} from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

// Sınav türü → sabit ton (Tailwind purge güvenli)
const SECTION_TONE: Record<ExamSectionValue, string> = {
  lgs: "border-sky-200 bg-sky-50 text-sky-700",
  tyt: "border-indigo-200 bg-indigo-50 text-indigo-700",
  ayt_say: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ayt_ea: "border-amber-200 bg-amber-50 text-amber-800",
  ayt_soz: "border-violet-200 bg-violet-50 text-violet-700",
  ayt_dil: "border-rose-200 bg-rose-50 text-rose-700",
};

function sectionPenalty(section: ExamSectionValue): number {
  return section === "lgs" ? 3 : 4;
}

function computeNet(correct: number, wrong: number, section: ExamSectionValue): number {
  const raw = correct - wrong / sectionPenalty(section);
  return Math.round(Math.max(raw, 0) * 100) / 100;
}

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

interface Props {
  studentId: number;
}

export function StudentExamsPanel({ studentId }: Props) {
  const q = useQuery<StudentExamListResponse>({
    queryKey: teacherKeys.studentExams(studentId),
    queryFn: () => getTeacherStudentExams(studentId),
    staleTime: 30_000,
  });
  const [addOpen, setAddOpen] = React.useState(false);
  const data = q.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-medium">Deneme Sonuçları</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Net, sınav türüne göre hesaplanır (LGS: doğru − yanlış/3 · YKS:
            doğru − yanlış/4).
          </p>
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="size-4" aria-hidden />
          Deneme Ekle
        </Button>
      </div>

      {q.isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : !data || data.rows.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center space-y-2">
            <p className="text-sm text-muted-foreground">
              Henüz deneme sonucu girilmemiş.
            </p>
            <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
              <Plus className="size-4" aria-hidden />
              İlk denemeyi ekle
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <SummaryStrip data={data} />
          {data.rows.length >= 2 ? <NetTrendChart rows={data.rows} /> : null}
          <ul className="space-y-2">
            {data.rows.map((row) => (
              <ExamRow key={row.id} row={row} />
            ))}
          </ul>
        </>
      )}

      <p className="text-[11px] text-muted-foreground leading-relaxed">
        Deneme net sonuçları yalnızca öğretmen ve kurum yöneticisi tarafından
        görülür; veliyle paylaşılmaz.
      </p>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Deneme sonucu ekle</DialogTitle>
          </DialogHeader>
          <ExamForm
            studentId={studentId}
            sectionOptions={data?.section_options ?? []}
            onDone={() => setAddOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SummaryStrip({ data }: { data: StudentExamListResponse }) {
  const s = data.summary;
  return (
    <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard label="Deneme Sayısı" value={String(s.count)} />
      <StatCard label="Ortalama Net" value={s.avg_net.toFixed(2)} />
      <StatCard label="En İyi Net" value={s.best_net.toFixed(2)} emphasize="good" />
      <StatCard
        label="Son Net"
        value={s.last_net != null ? s.last_net.toFixed(2) : "—"}
        delta={s.trend_delta}
      />
    </section>
  );
}

function StatCard({
  label,
  value,
  emphasize,
  delta,
}: {
  label: string;
  value: string;
  emphasize?: "good";
  delta?: number | null;
}) {
  return (
    <Card>
      <CardContent className="p-4 space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p
          className={cn(
            "text-2xl font-semibold tabular-nums",
            emphasize === "good" && "text-emerald-600",
          )}
        >
          {value}
        </p>
        {delta != null && Math.abs(delta) > 0.001 ? (
          <p
            className={cn(
              "text-xs inline-flex items-center gap-1 tabular-nums",
              delta > 0 ? "text-emerald-600" : "text-rose-600",
            )}
          >
            {delta > 0 ? (
              <TrendingUp className="size-3.5" aria-hidden />
            ) : (
              <TrendingDown className="size-3.5" aria-hidden />
            )}
            {delta > 0 ? "+" : ""}
            {delta.toFixed(2)} (ilk denemeye göre)
          </p>
        ) : delta != null ? (
          <p className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <Minus className="size-3.5" aria-hidden />
            değişim yok
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function NetTrendChart({ rows }: { rows: ExamResultRow[] }) {
  // rows DESC (en yeni ilk) → kronolojik için ters çevir
  const points = React.useMemo(
    () =>
      [...rows].reverse().map((r) => ({
        date: formatTRDate(r.exam_date).slice(0, 5),
        net: r.net,
        title: r.title,
      })),
    [rows],
  );
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm font-medium mb-3">Net Gelişimi</p>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 5, right: 8, bottom: 0, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                formatter={(v) => [Number(v).toFixed(2), "Net"]}
                labelFormatter={(_l, p) => p?.[0]?.payload?.title ?? ""}
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
              />
              <Line
                type="monotone"
                dataKey="net"
                stroke="#4f46e5"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function ExamRow({ row }: { row: ExamResultRow }) {
  const [open, setOpen] = React.useState(false);
  const del = useDeleteExam();
  const hasSubjects = row.subjects.length > 0;

  function onDelete() {
    if (
      !window.confirm(
        `"${row.title}" (${formatTRDate(row.exam_date)}) denemesini silmek istiyor musunuz?`,
      )
    ) {
      return;
    }
    del.mutate({ examId: row.id });
  }

  return (
    <li>
      <Card>
        <CardContent className="p-3">
          <div className="flex items-center gap-3">
            <div className="text-center shrink-0 w-16">
              <p className="text-2xl font-semibold tabular-nums leading-none">
                {row.net.toFixed(2)}
              </p>
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                net
              </p>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-medium truncate">{row.title}</span>
                <span
                  className={cn(
                    "inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border",
                    SECTION_TONE[row.section],
                  )}
                >
                  {row.section_label}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatTRDate(row.exam_date)} ·{" "}
                <span className="text-emerald-600">{row.total_correct}D</span>{" "}
                <span className="text-rose-600">{row.total_wrong}Y</span>{" "}
                <span className="text-muted-foreground">{row.total_blank}B</span>
                {" · "}
                {row.total_questions} soru
              </p>
              {row.note ? (
                <p className="text-xs text-muted-foreground mt-1 italic">
                  {row.note}
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {hasSubjects ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setOpen((v) => !v)}
                  aria-label={open ? "Ders kırılımını gizle" : "Ders kırılımını göster"}
                  aria-expanded={open}
                >
                  <ChevronDown
                    className={cn("size-4 transition-transform", open && "rotate-180")}
                    aria-hidden
                  />
                </Button>
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                onClick={onDelete}
                disabled={del.isPending}
                aria-label="Denemeyi sil"
              >
                {del.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Trash2 className="size-4" aria-hidden />
                )}
              </Button>
            </div>
          </div>

          {open && hasSubjects ? (
            <div className="mt-3 border-t border-border pt-2">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground text-left">
                    <th className="font-medium py-1">Ders</th>
                    <th className="font-medium py-1 text-right">D</th>
                    <th className="font-medium py-1 text-right">Y</th>
                    <th className="font-medium py-1 text-right">B</th>
                    <th className="font-medium py-1 text-right">Net</th>
                  </tr>
                </thead>
                <tbody>
                  {row.subjects.map((s, i) => (
                    <tr key={i} className="border-t border-border/50">
                      <td className="py-1">{s.name}</td>
                      <td className="py-1 text-right tabular-nums text-emerald-600">
                        {s.correct}
                      </td>
                      <td className="py-1 text-right tabular-nums text-rose-600">
                        {s.wrong}
                      </td>
                      <td className="py-1 text-right tabular-nums text-muted-foreground">
                        {s.blank}
                      </td>
                      <td className="py-1 text-right tabular-nums font-medium">
                        {s.net.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </li>
  );
}

type FormMode = "total" | "subjects";

function ExamForm({
  studentId,
  sectionOptions,
  onDone,
}: {
  studentId: number;
  sectionOptions: StudentExamListResponse["section_options"];
  onDone: () => void;
}) {
  const create = useCreateExam(studentId);
  const today = new Date().toISOString().slice(0, 10);

  const [title, setTitle] = React.useState("");
  const [examDate, setExamDate] = React.useState(today);
  const [section, setSection] = React.useState<ExamSectionValue>(
    sectionOptions[0]?.value ?? "lgs",
  );
  const [mode, setMode] = React.useState<FormMode>("total");
  const [correct, setCorrect] = React.useState("");
  const [wrong, setWrong] = React.useState("");
  const [blank, setBlank] = React.useState("");
  const [subjects, setSubjects] = React.useState<ExamSubjectInput[]>([
    { name: "", correct: 0, wrong: 0, blank: 0 },
  ]);
  const [note, setNote] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);

  // Canlı net önizlemesi
  const previewNet = React.useMemo(() => {
    if (mode === "total") {
      return computeNet(Number(correct) || 0, Number(wrong) || 0, section);
    }
    const tc = subjects.reduce((a, s) => a + (Number(s.correct) || 0), 0);
    const tw = subjects.reduce((a, s) => a + (Number(s.wrong) || 0), 0);
    return computeNet(tc, tw, section);
  }, [mode, correct, wrong, subjects, section]);

  function updateSubject(idx: number, patch: Partial<ExamSubjectInput>) {
    setSubjects((prev) =>
      prev.map((s, i) => (i === idx ? { ...s, ...patch } : s)),
    );
  }
  function addSubjectRow() {
    setSubjects((prev) => [...prev, { name: "", correct: 0, wrong: 0, blank: 0 }]);
  }
  function removeSubjectRow(idx: number) {
    setSubjects((prev) => prev.filter((_, i) => i !== idx));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const t = title.trim();
    if (!t) {
      setError("Deneme adı zorunlu.");
      return;
    }
    if (mode === "total") {
      const c = Number(correct) || 0;
      const w = Number(wrong) || 0;
      const b = Number(blank) || 0;
      if (c + w + b <= 0) {
        setError("En az bir doğru/yanlış/boş değeri girin.");
        return;
      }
      create.mutate(
        {
          body: {
            title: t,
            exam_date: examDate,
            section,
            total_correct: c,
            total_wrong: w,
            total_blank: b,
            note: note.trim() || null,
          },
        },
        { onSuccess: () => onDone() },
      );
    } else {
      const cleaned = subjects
        .map((s) => ({
          name: s.name.trim(),
          correct: Number(s.correct) || 0,
          wrong: Number(s.wrong) || 0,
          blank: Number(s.blank) || 0,
        }))
        .filter((s) => s.name.length > 0);
      if (cleaned.length === 0) {
        setError("En az bir ders satırı girin.");
        return;
      }
      const total = cleaned.reduce(
        (a, s) => a + s.correct + s.wrong + s.blank,
        0,
      );
      if (total <= 0) {
        setError("Ders satırlarında en az bir değer girin.");
        return;
      }
      create.mutate(
        {
          body: {
            title: t,
            exam_date: examDate,
            section,
            subjects: cleaned,
            note: note.trim() || null,
          },
        },
        { onSuccess: () => onDone() },
      );
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 max-h-[70vh] overflow-y-auto pr-1">
      <div className="space-y-1">
        <Label htmlFor="ex-title">Deneme adı</Label>
        <Input
          id="ex-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="örn. 3D Yayınları LGS Deneme 5"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="ex-date">Tarih</Label>
          <Input
            id="ex-date"
            type="date"
            value={examDate}
            onChange={(e) => setExamDate(e.target.value)}
            required
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="ex-section">Sınav türü</Label>
          <select
            id="ex-section"
            value={section}
            onChange={(e) => setSection(e.target.value as ExamSectionValue)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {sectionOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Mod seçici */}
      <div className="inline-flex rounded-md border border-border p-0.5 text-xs">
        <button
          type="button"
          onClick={() => setMode("total")}
          className={cn(
            "px-3 py-1 rounded transition-colors",
            mode === "total"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Toplam
        </button>
        <button
          type="button"
          onClick={() => setMode("subjects")}
          className={cn(
            "px-3 py-1 rounded transition-colors",
            mode === "subjects"
              ? "bg-foreground text-background"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Ders kırılımı
        </button>
      </div>

      {mode === "total" ? (
        <div className="grid grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label htmlFor="ex-c" className="text-emerald-700">Doğru</Label>
            <Input
              id="ex-c"
              type="number"
              min={0}
              value={correct}
              onChange={(e) => setCorrect(e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ex-w" className="text-rose-700">Yanlış</Label>
            <Input
              id="ex-w"
              type="number"
              min={0}
              value={wrong}
              onChange={(e) => setWrong(e.target.value)}
              placeholder="0"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="ex-b">Boş</Label>
            <Input
              id="ex-b"
              type="number"
              min={0}
              value={blank}
              onChange={(e) => setBlank(e.target.value)}
              placeholder="0"
            />
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_3rem_3rem_3rem_1.75rem] gap-1.5 text-[10px] uppercase tracking-wide text-muted-foreground px-0.5">
            <span>Ders</span>
            <span className="text-center">D</span>
            <span className="text-center">Y</span>
            <span className="text-center">B</span>
            <span />
          </div>
          {subjects.map((s, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_3rem_3rem_3rem_1.75rem] gap-1.5 items-center"
            >
              <Input
                value={s.name}
                onChange={(e) => updateSubject(i, { name: e.target.value })}
                placeholder="Matematik"
                className="h-8"
              />
              <Input
                type="number"
                min={0}
                value={s.correct || ""}
                onChange={(e) => updateSubject(i, { correct: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <Input
                type="number"
                min={0}
                value={s.wrong || ""}
                onChange={(e) => updateSubject(i, { wrong: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <Input
                type="number"
                min={0}
                value={s.blank || ""}
                onChange={(e) => updateSubject(i, { blank: Number(e.target.value) })}
                className="h-8 px-1 text-center"
              />
              <button
                type="button"
                onClick={() => removeSubjectRow(i)}
                disabled={subjects.length <= 1}
                className="text-muted-foreground hover:text-rose-600 disabled:opacity-30"
                aria-label="Ders satırını kaldır"
              >
                <X className="size-4" aria-hidden />
              </button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={addSubjectRow}>
            <Plus className="size-4" aria-hidden />
            Ders ekle
          </Button>
        </div>
      )}

      <div className="space-y-1">
        <Label htmlFor="ex-note">Not (opsiyonel)</Label>
        <textarea
          id="ex-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={500}
          rows={2}
          placeholder="Deneme hakkında kısa not..."
          className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring/30 resize-y"
        />
      </div>

      <div className="rounded-md bg-muted px-3 py-2 text-sm flex items-center justify-between">
        <span className="text-muted-foreground">Hesaplanan net</span>
        <span className="text-lg font-semibold tabular-nums">
          {previewNet.toFixed(2)}
        </span>
      </div>

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onDone} disabled={create.isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Kaydet
        </Button>
      </div>
    </form>
  );
}
