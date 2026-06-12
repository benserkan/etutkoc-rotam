"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  Clock,
  Compass,
  Loader2,
  RefreshCw,
  Send,
  Sparkles,
  XCircle,
} from "lucide-react";

import {
  getCareerSynthesis,
  getSurveyAssignment,
  getTeacherStudentSurveys,
  surveyKeys,
} from "@/lib/api/surveys";
import {
  useAssignSurvey,
  useCancelSurveyAssignment,
  useGenerateCareerSynthesis,
} from "@/lib/hooks/use-survey-mutations";
import { useSetAiConsent } from "@/lib/hooks/use-teacher-mutations";
import { ApiError } from "@/lib/api";
import type {
  CareerSynthesisModel,
  SurveyAssignmentRow,
  SurveyTemplateBrief,
} from "@/lib/types/survey";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SurveyResultView } from "@/components/shared/survey-result-view";
import { cn } from "@/lib/utils";

/**
 * Koç — öğrenci "Anketler" sekmesi.
 *
 * Üstte atamalar (durum + sonuç görüntüleme), altta kategori gruplu katalog
 * ("Gönder" → not'lu onay dialogu). Tamamlanan atamaya tıklayınca sonuç
 * dialogu (radar/bar/kadran — SurveyResultView).
 */

const STATUS_TONE: Record<string, string> = {
  pending: "border-amber-300 bg-amber-50 text-amber-900",
  in_progress: "border-sky-300 bg-sky-50 text-sky-900",
  completed: "border-emerald-300 bg-emerald-50 text-emerald-900",
  cancelled: "border-border bg-muted text-muted-foreground",
};

export function StudentSurveysPanel({ studentId }: { studentId: number }) {
  const q = useQuery({
    queryKey: surveyKeys.studentSurveys(studentId),
    queryFn: () => getTeacherStudentSurveys(studentId),
  });
  const [assignTarget, setAssignTarget] =
    React.useState<SurveyTemplateBrief | null>(null);
  const [resultId, setResultId] = React.useState<number | null>(null);

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-8">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Anketler yükleniyor…
      </div>
    );
  }
  const data = q.data;
  if (!data) {
    return (
      <p className="text-sm text-muted-foreground py-8">
        Anketler yüklenemedi — sayfayı yenileyin.
      </p>
    );
  }

  const visible = data.assignments.filter((a) => a.status !== "cancelled");
  // Bekleyen/devam eden atamalar — katalogda "gönderildi" işaretlemek için
  const openTemplateIds = new Set(
    data.assignments
      .filter((a) => a.status === "pending" || a.status === "in_progress")
      .map((a) => a.template.id),
  );

  // Kategori gruplu katalog
  const byCategory = new Map<string, SurveyTemplateBrief[]>();
  for (const t of data.catalog) {
    const list = byCategory.get(t.category) ?? [];
    list.push(t);
    byCategory.set(t.category, list);
  }

  return (
    <div className="space-y-6">
      {/* AI Kariyer Sentezi — beceri × ilgi × akademik gerçeklik */}
      <CareerSynthesisCard studentId={studentId} />

      {/* Atamalar */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base inline-flex items-center gap-2">
            <ClipboardList className="size-4 text-muted-foreground" aria-hidden />
            Uygulanan Anketler
          </CardTitle>
        </CardHeader>
        <CardContent>
          {visible.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              Henüz anket gönderilmedi — aşağıdaki katalogdan seçip gönderin.
            </p>
          ) : (
            <ul className="space-y-2">
              {visible.map((a) => (
                <AssignmentRow
                  key={a.id}
                  row={a}
                  onOpenResult={() => setResultId(a.id)}
                />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Katalog */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Anket Kataloğu</CardTitle>
          <p className="text-xs text-muted-foreground">
            Bunlar psikolojik test değil, koçluk amaçlı tanıma anketleridir —
            sonuçlar görüşme ve program tasarımı için ipucu sağlar.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...byCategory.entries()].map(([cat, items]) => (
            <div key={cat}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {data.categories[cat] ?? cat}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                {items.map((t) => {
                  const open = openTemplateIds.has(t.id);
                  return (
                    <div
                      key={t.id}
                      className="rounded-lg border border-border p-3 flex flex-col gap-2"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{t.title}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                          {t.description}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {t.question_count} soru · ~{t.estimated_minutes} dk
                        </p>
                      </div>
                      <div className="mt-auto">
                        {open ? (
                          <span className="inline-flex items-center gap-1.5 text-xs text-amber-800">
                            <Clock className="size-3.5" aria-hidden />
                            Öğrencide bekliyor
                          </span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => setAssignTarget(t)}
                            className="inline-flex items-center gap-1.5 rounded-md bg-[#117A86] text-white px-3 py-1.5 text-xs font-medium hover:bg-[#0d626c] transition"
                          >
                            <Send className="size-3.5" aria-hidden />
                            Öğrenciye Gönder
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {assignTarget ? (
        <AssignDialog
          studentId={studentId}
          template={assignTarget}
          onClose={() => setAssignTarget(null)}
        />
      ) : null}
      {resultId != null ? (
        <ResultDialog assignmentId={resultId} onClose={() => setResultId(null)} />
      ) : null}
    </div>
  );
}

// =============================================================================
// AI Kariyer Sentezi kartı — GET ücretsiz cache, POST kredili üret/yenile
// =============================================================================

const CONSENT_TEXT =
  "Yapay zekâ özellikleri için açık rıza gerekir: anket sonuçları ve akademik " +
  "veriler işlenmek üzere yurt dışındaki yapay zekâ sağlayıcısına (Google " +
  "Gemini) gönderilir; veri saklanmaz, yalnız siz görürsünüz. Onaylıyor musunuz?";

function CareerSynthesisCard({ studentId }: { studentId: number }) {
  const q = useQuery({
    queryKey: surveyKeys.careerSynthesis(studentId),
    queryFn: () => getCareerSynthesis(studentId),
  });
  const genMut = useGenerateCareerSynthesis(studentId);
  const consentMut = useSetAiConsent();

  function generate() {
    genMut.mutate(undefined, {
      onError: (e) => {
        // Rıza eksikse: onay al → rızayı kaydet → yeniden üret (dead-end yok)
        if (e instanceof ApiError && e.detail?.code === "consent_required") {
          if (window.confirm(CONSENT_TEXT)) {
            consentMut.mutate(undefined, {
              onSuccess: () => genMut.mutate(),
            });
          }
        }
      },
    });
  }

  const data = q.data;
  const busy = genMut.isPending || consentMut.isPending;

  return (
    <Card className="border-cyan-200">
      <CardHeader>
        <CardTitle className="text-base inline-flex items-center gap-2">
          <Compass className="size-4 text-cyan-700" aria-hidden />
          Kariyer Keşif — AI Sentezi
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Mesleki ilgi + beceri seti anket sonuçlarını öğrencinin gerçek
          akademik verisiyle (deneme netleri, program tamamlama) birleştirir;
          meslek/bölüm önerileri ve hedef belirleme seansı gündemi üretir.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {q.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-2">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
          </div>
        ) : !data ? (
          <p className="text-sm text-muted-foreground">Yüklenemedi — sayfayı yenileyin.</p>
        ) : !data.ready && !data.insight ? (
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
            <p className="text-sm font-semibold text-amber-900 inline-flex items-center gap-1.5">
              <AlertTriangle className="size-4" aria-hidden />
              Önce şu anketler tamamlanmalı
            </p>
            <ul className="mt-1.5 list-disc pl-5 text-xs text-amber-800 space-y-0.5">
              {data.missing_surveys.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
            <p className="mt-1.5 text-xs text-amber-800">
              Aşağıdaki katalogdan gönderin; öğrenci tamamlayınca sentez
              oluşturulabilir.
            </p>
          </div>
        ) : !data.insight ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cyan-200 bg-cyan-50 p-3">
            <p className="text-sm text-cyan-900">
              Anketler hazır — öğrencinin beceri × ilgi × akademik profili
              sentezlenebilir.
            </p>
            <button
              type="button"
              onClick={generate}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md bg-[#117A86] text-white px-3 py-1.5 text-xs font-medium hover:bg-[#0d626c] disabled:opacity-50 transition"
            >
              {busy ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Sparkles className="size-3.5" aria-hidden />
              )}
              Kariyer Sentezi oluştur (kredi)
            </button>
          </div>
        ) : (
          <CareerSynthesisResult
            insight={data.insight}
            isStale={data.is_stale}
            disclaimer={data.disclaimer}
            busy={busy}
            onRefresh={generate}
          />
        )}
      </CardContent>
    </Card>
  );
}

function CareerSynthesisResult({
  insight: ins,
  isStale,
  disclaimer,
  busy,
  onRefresh,
}: {
  insight: CareerSynthesisModel;
  isStale: boolean;
  disclaimer: string;
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-3">
      {isStale ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 p-2.5">
          <p className="text-xs text-amber-900 inline-flex items-center gap-1.5">
            <AlertTriangle className="size-3.5" aria-hidden />
            Yeni anket sonucu var — sentez güncel değil.
          </p>
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-400 bg-white px-2.5 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 disabled:opacity-50 transition"
          >
            {busy ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="size-3.5" aria-hidden />
            )}
            Yenile (kredi)
          </button>
        </div>
      ) : null}

      <p className="text-sm leading-relaxed">{ins.summary}</p>

      <div className="grid gap-2 sm:grid-cols-2">
        {ins.career_suggestions.map((s, i) => (
          <div key={i} className="rounded-lg border border-cyan-200 bg-cyan-50/50 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-semibold text-cyan-950">{s.title}</p>
              {s.field ? (
                <span className="shrink-0 text-[10px] px-1.5 py-0.5 rounded border border-cyan-300 bg-white text-cyan-900">
                  {s.field}
                </span>
              ) : null}
            </div>
            {s.why ? (
              <p className="mt-1 text-xs leading-relaxed text-cyan-900">{s.why}</p>
            ) : null}
            {s.example_departments.length > 0 ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {s.example_departments.map((d) => (
                  <span
                    key={d}
                    className="text-[10px] px-1.5 py-0.5 rounded-full border border-cyan-200 bg-white text-cyan-800"
                  >
                    {d}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {ins.strengths.length > 0 ? (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Öne çıkan güçlü yönler
          </p>
          <div className="flex flex-wrap gap-1.5">
            {ins.strengths.map((s) => (
              <span
                key={s}
                className="text-xs px-2 py-0.5 rounded-full border border-emerald-300 bg-emerald-50 text-emerald-900"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {ins.agenda.length > 0 ? (
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Hedef belirleme seansı için gündem
          </p>
          <ul className="mt-1.5 list-disc pl-5 text-sm space-y-1">
            {ins.agenda.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {ins.watch_outs.length > 0 ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-900">Dikkat noktaları</p>
          <ul className="mt-1 list-disc pl-5 text-xs text-amber-800 space-y-0.5">
            {ins.watch_outs.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-2">
        <p className="text-[11px] text-muted-foreground">
          {ins.based_on_surveys.length > 0
            ? `Dayanak: ${ins.based_on_surveys.join(", ")}`
            : ""}
          {ins.exam_count > 0 ? ` · ${ins.exam_count} deneme` : ""}
          {ins.generated_at ? ` · ${fmtDate(ins.generated_at)}` : ""}
        </p>
        {!isStale ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50 transition"
          >
            {busy ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="size-3.5" aria-hidden />
            )}
            Yenile (kredi)
          </button>
        ) : null}
      </div>
      <p className="text-[11px] text-muted-foreground">{disclaimer}</p>
    </div>
  );
}

function AssignmentRow({
  row,
  onOpenResult,
}: {
  row: SurveyAssignmentRow;
  onOpenResult: () => void;
}) {
  const cancelMut = useCancelSurveyAssignment();
  const done = row.status === "completed";
  return (
    <li className="rounded-lg border border-border p-3 flex flex-wrap items-center gap-2">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium truncate">{row.template.title}</p>
        <p className="text-[11px] text-muted-foreground">
          Gönderildi: {fmtDate(row.assigned_at)}
          {done && row.completed_at
            ? ` · Tamamlandı: ${fmtDate(row.completed_at)}`
            : row.answered_count > 0
              ? ` · ${row.answered_count}/${row.template.question_count} soru cevaplandı`
              : ""}
        </p>
      </div>
      <span
        className={cn(
          "shrink-0 text-[11px] px-2 py-0.5 rounded-full border inline-flex items-center gap-1",
          STATUS_TONE[row.status] ?? STATUS_TONE.pending,
        )}
      >
        {done ? (
          <CheckCircle2 className="size-3" aria-hidden />
        ) : (
          <Clock className="size-3" aria-hidden />
        )}
        {row.status_label}
      </span>
      {done ? (
        <button
          type="button"
          onClick={onOpenResult}
          className="shrink-0 rounded-md border border-emerald-300 bg-emerald-50 text-emerald-800 px-2.5 py-1 text-xs font-medium hover:bg-emerald-100 transition"
        >
          Sonucu Gör
        </button>
      ) : (
        <button
          type="button"
          onClick={() => {
            if (window.confirm("Bu anket ataması iptal edilsin mi?")) {
              cancelMut.mutate({ assignmentId: row.id });
            }
          }}
          disabled={cancelMut.isPending}
          className="shrink-0 inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted disabled:opacity-50 transition"
        >
          <XCircle className="size-3.5" aria-hidden />
          İptal
        </button>
      )}
    </li>
  );
}

function AssignDialog({
  studentId,
  template,
  onClose,
}: {
  studentId: number;
  template: SurveyTemplateBrief;
  onClose: () => void;
}) {
  const [note, setNote] = React.useState("");
  const mut = useAssignSurvey(studentId);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      { body: { template_id: template.id, note: note.trim() } },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{template.title} — öğrenciye gönder</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <p className="text-sm text-muted-foreground leading-relaxed">
            {template.description}
          </p>
          <p className="text-xs text-muted-foreground">
            {template.question_count} soru · yaklaşık {template.estimated_minutes}{" "}
            dakika sürer. Öğrenci panelinden veya telefonundan doldurur; bitince
            sonuç anında bu sekmeye düşer.
          </p>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-medium mb-1.5">
              Öğrenciye not (opsiyonel)
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              maxLength={500}
              placeholder="Örn. İlk görüşmemizden önce doldurursan harika olur."
              className="w-full px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted transition"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={mut.isPending}
              className="px-4 py-2 text-sm rounded-md bg-[#117A86] text-white font-medium hover:bg-[#0d626c] disabled:opacity-40 transition inline-flex items-center gap-2"
            >
              {mut.isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Send className="size-3.5" aria-hidden />
              )}
              Gönder
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResultDialog({
  assignmentId,
  onClose,
}: {
  assignmentId: number;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: surveyKeys.assignment(assignmentId),
    queryFn: () => getSurveyAssignment(assignmentId),
  });
  const det = q.data;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {det
              ? `${det.assignment.template.title} — Sonuç`
              : "Sonuç yükleniyor…"}
          </DialogTitle>
        </DialogHeader>
        {q.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
          </div>
        ) : det?.result ? (
          <>
            {det.assignment.completed_at ? (
              <p className="text-xs text-muted-foreground -mt-2">
                {det.assignment.student_name} · {fmtDate(det.assignment.completed_at)}{" "}
                tarihinde tamamladı
              </p>
            ) : null}
            <SurveyResultView result={det.result} />
          </>
        ) : (
          <p className="text-sm text-muted-foreground py-4">
            Sonuç henüz hazır değil.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}
