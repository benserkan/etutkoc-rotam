"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CalendarCheck,
  Camera,
  ChevronDown,
  Lightbulb,
  Loader2,
  Lock,
  Mic,
  Plus,
  Printer,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";
import { DemoHint } from "@/components/demos/demo-hint";

import {
  getTeacherStudentSessions,
  getTeacherSessionPrefill,
  getTeacherAiConsent,
  getTeacherCoachingInsight,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
  useSetAiConsent,
  useParseSessionPhoto,
  useTranscribeAudio,
  useGenerateCoachingInsight,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  AiConsentResponse,
  CoachingInsightCacheResponse,
  CoachingSessionCreateBody,
  CoachingSessionRow,
  SessionChannel,
  SessionPrefillResponse,
  SessionStatus,
  StudentSessionListResponse,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS: { value: SessionStatus; label: string }[] = [
  { value: "done", label: "Yapıldı" },
  { value: "postponed", label: "Ertelendi" },
  { value: "cancelled", label: "İptal" },
  { value: "no_show", label: "Gelmedi" },
];
const STATUS_TONE: Record<SessionStatus, string> = {
  done: "border-emerald-200 bg-emerald-50 text-emerald-700",
  postponed: "border-amber-200 bg-amber-50 text-amber-800",
  cancelled: "border-slate-200 bg-slate-50 text-slate-600",
  no_show: "border-rose-200 bg-rose-50 text-rose-700",
};
const CHANNEL_OPTIONS: { value: SessionChannel; label: string }[] = [
  { value: "in_person", label: "Yüz yüze" },
  { value: "online", label: "Online" },
  { value: "phone", label: "Telefon" },
];

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] ?? "");
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

const AUDIO_MIMES = ["audio/webm", "audio/mp4", "audio/ogg"];
const ALLOWED_AUDIO = ["audio/webm", "audio/mp4", "audio/ogg", "audio/mpeg", "audio/wav"];

function pickAudioMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of AUDIO_MIMES) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

type CaptureSource = "manual" | "photo" | "voice";

interface Props {
  studentId: number;
}

export function StudentSessionsPanel({ studentId }: Props) {
  const q = useQuery<StudentSessionListResponse>({
    queryKey: teacherKeys.studentSessions(studentId),
    queryFn: () => getTeacherStudentSessions(studentId),
    staleTime: 30_000,
  });
  const consentQ = useQuery<AiConsentResponse>({
    queryKey: teacherKeys.aiConsent(),
    queryFn: getTeacherAiConsent,
    staleTime: 300_000,
  });
  const generateInsight = useGenerateCoachingInsight(studentId);
  const setConsent = useSetAiConsent();

  const [formOpen, setFormOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<CoachingSessionRow | null>(null);
  const [consentOpen, setConsentOpen] = React.useState(false);
  const [pendingAction, setPendingAction] = React.useState<(() => void) | null>(null);
  const [insightOpen, setInsightOpen] = React.useState(false);

  // İçgörü cache'i — açılınca okunur, KREDİ DÜŞMEZ (yalnız "Oluştur/Yenile" düşer)
  const insightQ = useQuery<CoachingInsightCacheResponse>({
    queryKey: teacherKeys.coachingInsight(studentId),
    queryFn: () => getTeacherCoachingInsight(studentId),
    enabled: insightOpen,
    staleTime: 60_000,
  });
  const cachedInsight = insightQ.data?.insight ?? null;

  const data = q.data;
  const hasSessions = !!data && data.summary.total > 0;
  // Ücretli paket kapısı: trial/free koçta AI özellikleri kilitli.
  const aiLocked = !!consentQ.data && consentQ.data.ai_premium === false;

  function openNew() {
    setEditing(null);
    setFormOpen(true);
  }
  function openEdit(row: CoachingSessionRow) {
    setEditing(row);
    setFormOpen(true);
  }

  // AI eylemleri (foto/dikte/içgörü) öncesi rıza kapısı — SessionForm'a da geçer.
  function gateConsent(action: () => void) {
    if (!consentQ.data?.consented) {
      setPendingAction(() => action);
      setConsentOpen(true);
      return;
    }
    action();
  }

  function generateNow() {
    gateConsent(() => generateInsight.mutate());
  }

  function acceptConsent() {
    setConsent.mutate(undefined, {
      onSuccess: () => {
        setConsentOpen(false);
        const action = pendingAction;
        setPendingAction(null);
        action?.();
      },
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-medium">Koçluk Seansları</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Görüşme notları + kararlar. Tahsilat yapılan seansları sayar.
          </p>
          <DemoHint contextKey="sessions" role="teacher" className="mt-1.5" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={`/teacher/students/${studentId}/sessions/print`}
            target="_blank"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted"
          >
            <Printer className="size-3.5" aria-hidden /> Boş form
          </Link>
          <Button
            size="sm"
            variant="outline"
            className="border-violet-200 text-violet-700 hover:bg-violet-50 hover:text-violet-800"
            onClick={() => setInsightOpen(true)}
            disabled={!hasSessions || aiLocked}
            title={aiLocked ? "Ücretli pakette kullanılabilir" : hasSessions ? "Seans geçmişinden bir sonraki seans için AI önerisi" : "Önce en az bir seans kaydı gerekir"}
          >
            {aiLocked ? <Lock className="size-4" aria-hidden /> : <Lightbulb className="size-4" aria-hidden />} İçgörü
          </Button>
          <Button size="sm" onClick={openNew}>
            <Plus className="size-4" aria-hidden /> Yeni Seans
          </Button>
        </div>
      </div>

      {aiLocked ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          <Lock className="size-4 shrink-0" aria-hidden />
          Yapay zekâ özellikleri (sesli dikte, fotoğraftan doldurma, koçluk içgörüsü) ücretli
          pakette açıktır.
          <Link href="/teacher/plan" className="ml-auto font-medium text-amber-900 underline">
            Paketi görüntüle
          </Link>
        </div>
      ) : null}

      {q.isLoading && !data ? (
        <p className="text-sm text-muted-foreground">Yükleniyor…</p>
      ) : !data || data.rows.length === 0 ? (
        <Card>
          <CardContent className="space-y-2 p-6 text-center">
            <p className="text-sm text-muted-foreground">Henüz seans kaydı yok.</p>
            <Button size="sm" variant="outline" onClick={openNew}>
              <Plus className="size-4" aria-hidden /> İlk seansı ekle
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Toplam seans" value={String(data.summary.total)} />
            <Stat label="Yapıldı" value={String(data.summary.done_count)} tone="good" />
            <Stat label="Ertelendi" value={String(data.summary.postponed_count)} />
            <Stat label="Son seans" value={data.summary.last_session_date ? formatTRDate(data.summary.last_session_date) : "—"} />
          </section>
          <ul className="space-y-2">
            {data.rows.map((row) => (
              <SessionCard key={row.id} row={row} onEdit={() => openEdit(row)} />
            ))}
          </ul>
        </>
      )}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Seans notları yalnızca size özeldir; öğrenci ve veli görmez.
      </p>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editing ? "Seansı düzenle" : "Yeni seans kaydı"}</DialogTitle>
          </DialogHeader>
          <SessionForm
            studentId={studentId}
            editing={editing}
            aiLocked={aiLocked}
            gateConsent={gateConsent}
            onDone={() => setFormOpen(false)}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={consentOpen} onOpenChange={(o) => { if (!o) { setConsentOpen(false); setPendingAction(null); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-cyan-600" aria-hidden /> Yapay zekâ özellikleri onayı
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm text-muted-foreground">
            <p>
              Fotoğrafınız, ses kaydınız veya seans notlarınız; metne çevrilmek ya da
              içgörü üretilmek üzere yapay zekâ hizmetine (Google Gemini) gönderilir.
              Devam etmek için onayınız gerekir.
            </p>
            <ul className="space-y-1.5 text-xs">
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-emerald-600" aria-hidden /> Fotoğraf / ses <strong>saklanmaz</strong>; yalnızca işlenir, ardından silinir.</li>
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-emerald-600" aria-hidden /> Yalnızca <strong>siz</strong> görürsünüz; öğrenci ve veli erişemez.</li>
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-amber-600" aria-hidden /> İşleme yurt dışındaki bir hizmet (Google) tarafından yapılır.</li>
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-emerald-600" aria-hidden /> Çıkan sonuç bir taslaktır; kaydetmeden önce kontrol edip düzeltebilirsiniz.</li>
            </ul>
            <p className="text-[11px]">Bu onayı dilediğinizde geri çekebilirsiniz; bu özellikleri kullanmadan da seansları elle girebilirsiniz.</p>
          </div>
          <div className="flex items-center justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={() => { setConsentOpen(false); setPendingAction(null); }} disabled={setConsent.isPending}>
              Vazgeç
            </Button>
            <Button onClick={acceptConsent} disabled={setConsent.isPending}>
              {setConsent.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <ShieldCheck className="size-4" aria-hidden />}
              Onaylıyorum, devam et
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={insightOpen} onOpenChange={setInsightOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Lightbulb className="size-5 text-violet-600" aria-hidden /> Koçluk içgörüsü
            </DialogTitle>
          </DialogHeader>

          {insightQ.isLoading ? (
            <p className="py-6 text-center text-sm text-muted-foreground">Yükleniyor…</p>
          ) : !cachedInsight ? (
            <div className="space-y-4 py-2 text-sm">
              <p className="text-muted-foreground">
                Bu öğrenci için henüz içgörü oluşturulmadı. Seans geçmişi + güncel
                akademik durumdan bir sonraki seans için özet, gündem ve yaklaşım
                önerileri üretilir.
              </p>
              <div className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800">
                Bu işlem yapay zekâ kullanır ve <strong>kredi düşer</strong>. Üretilen
                içgörü kaydedilir; sonraki görüntülemeler ücretsizdir.
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button variant="ghost" onClick={() => setInsightOpen(false)}>Kapat</Button>
                <Button onClick={generateNow} disabled={generateInsight.isPending}>
                  {generateInsight.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
                  İçgörü oluştur
                </Button>
              </div>
            </div>
          ) : (
            <div className="max-h-[68vh] space-y-4 overflow-y-auto pr-1 text-sm">
              {insightQ.data?.is_stale ? (
                <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                  <span>
                    Bu içgörü <strong>{cachedInsight.based_on_sessions} seansa</strong> dayanıyor;
                    şu an <strong>{data?.summary.total ?? cachedInsight.based_on_sessions} seans</strong> var.
                    Güncel öneri için <strong>Yenile</strong> (kredi düşer).
                  </span>
                </div>
              ) : null}
              <p className="rounded-md bg-muted/50 px-3 py-2 leading-relaxed">{cachedInsight.summary}</p>

              {cachedInsight.agenda_suggestions.length > 0 ? (
                <InsightList
                  title="Bir sonraki seansta konuş"
                  icon={<CalendarCheck className="size-4 text-cyan-600" aria-hidden />}
                  items={cachedInsight.agenda_suggestions}
                />
              ) : null}
              {cachedInsight.psychological_tips.length > 0 ? (
                <InsightList
                  title="Yaklaşım ipuçları"
                  icon={<Sparkles className="size-4 text-violet-600" aria-hidden />}
                  items={cachedInsight.psychological_tips}
                />
              ) : null}
              {cachedInsight.watch_outs.length > 0 ? (
                <InsightList
                  title="Dikkat"
                  icon={<AlertTriangle className="size-4 text-amber-600" aria-hidden />}
                  items={cachedInsight.watch_outs}
                  tone="warn"
                />
              ) : null}

              <p className="text-[11px] text-muted-foreground">
                {cachedInsight.based_on_sessions} seans + güncel akademik durumdan üretildi
                {cachedInsight.generated_at ? ` (${formatTRDate(cachedInsight.generated_at.slice(0, 10))})` : ""}.
                Bu bir öneridir; klinik teşhis değildir. Yalnızca siz görürsünüz.
              </p>
              <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
                <Button variant="ghost" onClick={() => setInsightOpen(false)}>Kapat</Button>
                <Button variant="outline" onClick={generateNow} disabled={generateInsight.isPending}>
                  {generateInsight.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
                  Yenile
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InsightList({
  title,
  icon,
  items,
  tone,
}: {
  title: string;
  icon: React.ReactNode;
  items: string[];
  tone?: "warn";
}) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 font-medium">{icon} {title}</p>
      <ul className="space-y-1">
        {items.map((it, i) => (
          <li
            key={i}
            className={cn(
              "rounded-md border px-2.5 py-1.5 text-sm",
              tone === "warn" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-border bg-card",
            )}
          >
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" }) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-semibold tabular-nums", tone === "good" && "text-emerald-600")}>{value}</p>
      </CardContent>
    </Card>
  );
}

function SessionCard({ row, onEdit }: { row: CoachingSessionRow; onEdit: () => void }) {
  const [open, setOpen] = React.useState(false);
  const del = useDeleteSession();

  function onDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (!window.confirm(`${formatTRDate(row.session_date)} seansını silmek istiyor musunuz?`)) return;
    del.mutate({ sessionId: row.id });
  }

  const hasDetail = !!(row.coach_note || row.next_change || (row.auto_snapshot));

  return (
    <li>
      <Card>
        <CardContent className="p-3">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-semibold tabular-nums">{formatTRDate(row.session_date)}</span>
                <span className={cn("inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-bold", STATUS_TONE[row.status])}>
                  {row.status_label}
                </span>
                {row.channel_label ? (
                  <span className="text-[11px] text-muted-foreground">{row.channel_label}</span>
                ) : null}
                {row.mood ? (
                  <span className="text-[11px] text-muted-foreground">ruh hali {row.mood}/5</span>
                ) : null}
              </div>
              <p className="mt-1 text-sm">{row.agenda}</p>
              {row.tags.length > 0 ? (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {row.tags.map((t) => (
                    <span key={t} className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">{t}</span>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {hasDetail ? (
                <Button variant="ghost" size="sm" onClick={() => setOpen((v) => !v)} aria-label="Detay" aria-expanded={open}>
                  <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} aria-hidden />
                </Button>
              ) : null}
              <Button variant="ghost" size="sm" onClick={onEdit} className="text-xs">Düzenle</Button>
              <Button variant="ghost" size="sm" onClick={onDelete} disabled={del.isPending} aria-label="Sil">
                {del.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Trash2 className="size-4" aria-hidden />}
              </Button>
            </div>
          </div>

          {open && hasDetail ? (
            <div className="mt-3 space-y-2 border-t border-border pt-2 text-sm">
              {row.coach_note ? (
                <p><span className="font-medium">Görüşme notu: </span><span className="text-muted-foreground">{row.coach_note}</span></p>
              ) : null}
              {row.next_change ? (
                <p><span className="font-medium">Değiştirilecek: </span><span className="text-muted-foreground">{row.next_change}</span></p>
              ) : null}
              {row.auto_snapshot ? <AutoSnapshot snap={row.auto_snapshot} /> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </li>
  );
}

function AutoSnapshot({ snap }: { snap: SessionPrefillResponse }) {
  return (
    <div className="rounded-lg bg-muted/50 p-2.5 text-xs">
      <p className="mb-1 font-medium text-foreground">O haftanın verisi</p>
      <div className="grid grid-cols-2 gap-1 text-muted-foreground">
        <span>Tamamlama: {snap.week_completion_pct != null ? `%${snap.week_completion_pct}` : "—"}</span>
        <span>Hız: {snap.recent_rate.toFixed(1)} test/gün</span>
        {snap.latest_exam ? (
          <span className="col-span-2">Son deneme: {snap.latest_exam.section_label} net {snap.latest_exam.net.toFixed(2)}</span>
        ) : null}
        {snap.behind_subjects.length > 0 ? (
          <span className="col-span-2">Geride: {snap.behind_subjects.map((s) => `${s.name} %${s.percent_done}`).join(" · ")}</span>
        ) : null}
        {snap.recent_units && snap.recent_units.length > 0 ? (
          <span className="col-span-2 text-cyan-700 dark:text-cyan-300">
            Geçen hafta işlenen: {snap.recent_units.slice(0, 6).map((u) => `${u.topic} (${u.tests})`).join(" · ")}
          </span>
        ) : null}
      </div>
    </div>
  );
}

const TODAY = () => new Date().toISOString().slice(0, 10);

function appendText(prev: string, add: string): string {
  const a = add.trim();
  if (!a) return prev;
  return prev.trim() ? `${prev.trim()} ${a}` : a;
}

type DictField = "agenda" | "note";

function DictateButton({
  aiLocked,
  recording,
  processing,
  disabled,
  elapsed,
  onToggle,
}: {
  aiLocked: boolean;
  recording: boolean;
  processing: boolean;
  disabled: boolean;
  elapsed: number;
  onToggle: () => void;
}) {
  if (aiLocked) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground" title="Ücretli pakette kullanılabilir">
        <Lock className="size-3.5" aria-hidden /> dikte
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium transition",
        recording
          ? "border-rose-300 bg-rose-50 text-rose-700"
          : "border-border hover:bg-muted disabled:opacity-50",
      )}
      title="Konuşarak yazdır (sesli dikte)"
    >
      {recording ? (
        <>
          <Square className="size-3 fill-current" aria-hidden />
          {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} · Durdur
        </>
      ) : processing ? (
        <>
          <Loader2 className="size-3 animate-spin" aria-hidden /> çözülüyor…
        </>
      ) : (
        <>
          <Mic className="size-3.5" aria-hidden /> Sesle yaz
        </>
      )}
    </button>
  );
}

function SessionForm({
  studentId,
  editing,
  aiLocked,
  gateConsent,
  onDone,
}: {
  studentId: number;
  editing: CoachingSessionRow | null;
  aiLocked: boolean;
  gateConsent: (action: () => void) => void;
  onDone: () => void;
}) {
  const create = useCreateSession(studentId);
  const update = useUpdateSession();
  const parsePhoto = useParseSessionPhoto(studentId);
  const transcribe = useTranscribeAudio(studentId);
  const isEdit = !!editing;

  const [date, setDate] = React.useState(editing?.session_date ?? TODAY());
  const [stat, setStat] = React.useState<SessionStatus>(editing?.status ?? "done");
  const [channel, setChannel] = React.useState<SessionChannel | "">(editing?.channel ?? "");
  const [duration, setDuration] = React.useState(editing?.duration_min ? String(editing.duration_min) : "");
  const [agenda, setAgenda] = React.useState(editing?.agenda ?? "");
  const [note, setNote] = React.useState(editing?.coach_note ?? "");
  const [nextChange, setNextChange] = React.useState(editing?.next_change ?? "");
  const [mood, setMood] = React.useState<number | null>(editing?.mood ?? null);
  const [tags, setTags] = React.useState((editing?.tags ?? []).join(", "));
  const [error, setError] = React.useState<string | null>(null);
  const [captureSource, setCaptureSource] = React.useState<CaptureSource>("manual");

  // Dikte (alan-bazlı ses → metin)
  const [dictation, setDictation] = React.useState<{ field: DictField; phase: "recording" | "processing" } | null>(null);
  const [elapsed, setElapsed] = React.useState(0);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const streamRef = React.useRef<MediaStream | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const photoRef = React.useRef<HTMLInputElement | null>(null);

  // Otomatik panel — yalnız yeni seansta çekilir
  const prefill = useQuery<SessionPrefillResponse>({
    queryKey: teacherKeys.sessionPrefill(studentId),
    queryFn: () => getTeacherSessionPrefill(studentId),
    enabled: !isEdit,
    staleTime: 60_000,
  });

  const pending = create.isPending || update.isPending;

  function cleanupStream() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }
  React.useEffect(() => cleanupStream, []);

  function fillField(field: DictField, text: string) {
    if (field === "agenda") setAgenda((v) => appendText(v, text));
    else setNote((v) => appendText(v, text));
    setCaptureSource((s) => (s === "photo" ? s : "voice"));
  }

  async function beginRecording(field: DictField) {
    const mime = pickAudioMime();
    if (!mime) {
      toast.error("Tarayıcınız ses kaydını desteklemiyor");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const rec = new MediaRecorder(stream, { mimeType: mime });
      rec.ondataavailable = (ev) => { if (ev.data.size > 0) chunksRef.current.push(ev.data); };
      rec.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mime });
        cleanupStream();
        setElapsed(0);
        if (blob.size === 0) { setDictation(null); toast.error("Kayıt boş"); return; }
        setDictation({ field, phase: "processing" });
        const cleanMime = mime.split(";")[0];
        const mt = ALLOWED_AUDIO.includes(cleanMime) ? cleanMime : "audio/webm";
        const b64 = await blobToBase64(blob);
        transcribe.mutate(
          { audioBase64: b64, mediaType: mt },
          {
            onSuccess: (res) => fillField(field, res.text),
            onSettled: () => setDictation(null),
          },
        );
      };
      recorderRef.current = rec;
      rec.start();
      setDictation({ field, phase: "recording" });
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch {
      toast.error("Mikrofon erişimi reddedildi");
      cleanupStream();
      setDictation(null);
    }
  }

  function toggleDictation(field: DictField) {
    if (dictation?.phase === "recording" && dictation.field === field) {
      recorderRef.current?.stop();
      return;
    }
    gateConsent(() => beginRecording(field));
  }

  async function onPhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      toast.error("JPEG, PNG veya WebP seçin");
      return;
    }
    const b64 = await fileToBase64(file);
    gateConsent(() =>
      parsePhoto.mutate(
        { imageBase64: b64, mediaType: file.type },
        {
          onSuccess: (d) => {
            setAgenda(d.agenda || "");
            setNote(d.coach_note || "");
            setNextChange(d.next_change || "");
            setMood(d.mood ?? null);
            setTags((d.tags || []).join(", "));
            setCaptureSource("photo");
            toast.success("Fotoğraf okundu — alanları kontrol edin");
          },
        },
      ),
    );
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!agenda.trim()) {
      setError("Gündem (konuşulacaklar) zorunlu.");
      return;
    }
    const body: CoachingSessionCreateBody = {
      session_date: date,
      status: stat,
      duration_min: duration ? Number(duration) : null,
      channel: channel || null,
      agenda: agenda.trim(),
      coach_note: note.trim() || null,
      next_change: nextChange.trim() || null,
      mood,
      tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
    };
    if (isEdit && editing) {
      update.mutate({ sessionId: editing.id, body }, { onSuccess: () => onDone() });
    } else {
      const cap = captureSource !== "manual" ? { capture_source: captureSource } : {};
      create.mutate({ body: { ...body, ...cap } }, { onSuccess: () => onDone() });
    }
  }

  const recordingThis = (f: DictField) => dictation?.phase === "recording" && dictation.field === f;
  const processingThis = (f: DictField) => dictation?.phase === "processing" && dictation.field === f;
  const otherBusy = (f: DictField) => !!dictation && dictation.field !== f;

  return (
    <form onSubmit={submit} className="max-h-[72vh] space-y-3 overflow-y-auto pr-1">
      <input
        ref={photoRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        className="hidden"
        onChange={onPhoto}
      />

      {!isEdit ? (
        <div className="rounded-lg border border-cyan-200 bg-cyan-50/50 p-3 text-xs">
          <p className="mb-1.5 font-semibold text-cyan-900">Bu haftanın verisi (otomatik)</p>
          {prefill.isLoading ? (
            <p className="text-muted-foreground">Hesaplanıyor…</p>
          ) : prefill.data ? (
            <div className="grid grid-cols-2 gap-1 text-cyan-900/80">
              <span>Tamamlama: {prefill.data.week_completion_pct != null ? `%${prefill.data.week_completion_pct}` : "—"} ({prefill.data.week_completed}/{prefill.data.week_planned})</span>
              <span>Hız: {prefill.data.recent_rate.toFixed(1)} test/gün</span>
              {prefill.data.latest_exam ? (
                <span className="col-span-2">Son deneme: {prefill.data.latest_exam.section_label} net {prefill.data.latest_exam.net.toFixed(2)}</span>
              ) : <span className="col-span-2">Henüz deneme yok</span>}
              {prefill.data.behind_subjects.length > 0 ? (
                <span className="col-span-2">Geride kalan: {prefill.data.behind_subjects.map((s) => `${s.name} %${s.percent_done}`).join(" · ")}</span>
              ) : null}
            </div>
          ) : (
            <p className="text-muted-foreground">Veri alınamadı (yine de seansı kaydedebilirsiniz).</p>
          )}
        </div>
      ) : null}

      {/* Fotoğraftan doldur — tüm formu okur (kâğıt görüşme formu) */}
      <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-border px-3 py-2">
        <span className="text-xs text-muted-foreground">
          Hızlı doldurma: kâğıt formu fotoğrafla ya da alanlara konuşarak yazdır.
        </span>
        {aiLocked ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground" title="Ücretli pakette kullanılabilir">
            <Lock className="size-3.5" aria-hidden /> Fotoğraf
          </span>
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={() => photoRef.current?.click()} disabled={parsePhoto.isPending || !!dictation}>
            {parsePhoto.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Camera className="size-4" aria-hidden />}
            Fotoğraftan doldur
          </Button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="se-date">Tarih</Label>
          <Input id="se-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </div>
        <div className="space-y-1">
          <Label htmlFor="se-status">Durum</Label>
          <select id="se-status" value={stat} onChange={(e) => setStat(e.target.value as SessionStatus)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="se-channel">Kanal (ops.)</Label>
          <select id="se-channel" value={channel} onChange={(e) => setChannel(e.target.value as SessionChannel | "")}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <option value="">—</option>
            {CHANNEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="se-dur">Süre (dk, ops.)</Label>
          <Input id="se-dur" type="number" min={0} value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="örn. 45" />
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="se-agenda">Gündem / konuşulacaklar <span className="text-rose-500">*</span></Label>
          <DictateButton
            aiLocked={aiLocked}
            recording={recordingThis("agenda")}
            processing={processingThis("agenda")}
            disabled={otherBusy("agenda") || processingThis("agenda")}
            elapsed={elapsed}
            onToggle={() => toggleDictation("agenda")}
          />
        </div>
        <textarea id="se-agenda" value={agenda} onChange={(e) => setAgenda(e.target.value)} rows={2} required
          placeholder="Bu seansta konuşulan / konuşulacak ana konular"
          className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor="se-note">Görüşme notu (ops.)</Label>
          <DictateButton
            aiLocked={aiLocked}
            recording={recordingThis("note")}
            processing={processingThis("note")}
            disabled={otherBusy("note") || processingThis("note")}
            elapsed={elapsed}
            onToggle={() => toggleDictation("note")}
          />
        </div>
        <textarea id="se-note" value={note} onChange={(e) => setNote(e.target.value)} rows={3}
          placeholder="Gözlemler, başarılar, zorluklar…"
          className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
      </div>

      <div className="space-y-1">
        <Label htmlFor="se-next">Gelecek hafta değiştirilecek 1 şey (ops.)</Label>
        <Input id="se-next" value={nextChange} onChange={(e) => setNextChange(e.target.value)} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label>Ruh hali (ops.)</Label>
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" onClick={() => setMood(mood === n ? null : n)}
                className={cn("size-8 rounded-md border text-sm font-semibold transition",
                  mood === n ? "border-cyan-600 bg-cyan-600 text-white" : "border-border hover:bg-muted")}>
                {n}
              </button>
            ))}
          </div>
        </div>
        <div className="space-y-1">
          <Label htmlFor="se-tags">Etiketler (virgülle)</Label>
          <Input id="se-tags" value={tags} onChange={(e) => setTags(e.target.value)} placeholder="kaygı, motivasyon" />
        </div>
      </div>

      {error ? <p className="text-sm text-destructive" role="alert">{error}</p> : null}

      <div className="flex items-center justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onDone} disabled={pending}>İptal</Button>
        <Button type="submit" disabled={pending || !!dictation}>
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <CalendarCheck className="size-4" aria-hidden />}
          {isEdit ? "Güncelle" : "Kaydet"}
        </Button>
      </div>
    </form>
  );
}
