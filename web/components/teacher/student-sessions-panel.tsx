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
  Mic,
  Plus,
  Printer,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
} from "lucide-react";

import {
  getTeacherStudentSessions,
  getTeacherSessionPrefill,
  getTeacherAiConsent,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
  useSetAiConsent,
  useParseSessionPhoto,
  useParseSessionVoice,
  useCoachingInsight,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  AiConsentResponse,
  CoachingInsightResponse,
  CoachingSessionCreateBody,
  CoachingSessionRow,
  SessionChannel,
  SessionDraftResponse,
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

interface Props {
  studentId: number;
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

type CaptureSource = "photo" | "voice";
type DraftSource = CaptureSource | "insight";
type PendingCapture = { b64: string; mt: string; source: CaptureSource };

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
  const parsePhoto = useParseSessionPhoto(studentId);
  const parseVoice = useParseSessionVoice(studentId);
  const insight = useCoachingInsight(studentId);
  const setConsent = useSetAiConsent();
  const fileRef = React.useRef<HTMLInputElement | null>(null);

  const [formOpen, setFormOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<CoachingSessionRow | null>(null);
  const [draft, setDraft] = React.useState<SessionDraftResponse | null>(null);
  const [draftSource, setDraftSource] = React.useState<DraftSource | null>(null);
  const [consentOpen, setConsentOpen] = React.useState(false);
  const [pendingAction, setPendingAction] = React.useState<(() => void) | null>(null);
  const [insightData, setInsightData] = React.useState<CoachingInsightResponse | null>(null);
  const [insightOpen, setInsightOpen] = React.useState(false);

  // Ses kaydı durumu
  const [recording, setRecording] = React.useState(false);
  const [elapsed, setElapsed] = React.useState(0);
  const recorderRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const streamRef = React.useRef<MediaStream | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  const data = q.data;
  const parsing = parsePhoto.isPending || parseVoice.isPending;
  const busy = parsing || insight.isPending || recording;
  const hasSessions = !!data && data.summary.total > 0;

  function openNew() {
    setEditing(null);
    setDraft(null);
    setDraftSource(null);
    setFormOpen(true);
  }
  function openEdit(row: CoachingSessionRow) {
    setEditing(row);
    setDraft(null);
    setDraftSource(null);
    setFormOpen(true);
  }

  function gateConsent(action: () => void) {
    if (!consentQ.data?.consented) {
      setPendingAction(() => action);
      setConsentOpen(true);
      return;
    }
    action();
  }

  function runParse(payload: PendingCapture) {
    const onSuccess = (d: SessionDraftResponse) => {
      setEditing(null);
      setDraft(d);
      setDraftSource(payload.source);
      setFormOpen(true);
    };
    if (payload.source === "photo") {
      parsePhoto.mutate({ imageBase64: payload.b64, mediaType: payload.mt }, { onSuccess });
    } else {
      parseVoice.mutate({ audioBase64: payload.b64, mediaType: payload.mt }, { onSuccess });
    }
  }

  function runInsight() {
    insight.mutate(undefined, {
      onSuccess: (d) => { setInsightData(d); setInsightOpen(true); },
    });
  }

  function startSessionFromInsight() {
    if (!insightData) return;
    setEditing(null);
    setDraft({
      agenda: insightData.agenda_suggestions.map((a) => `• ${a}`).join("\n"),
      coach_note: "",
      next_change: "",
      mood: null,
      tags: [],
    });
    setDraftSource("insight");
    setInsightOpen(false);
    setFormOpen(true);
  }

  function dispatch(payload: PendingCapture) {
    gateConsent(() => runParse(payload));
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      toast.error("JPEG, PNG veya WebP seçin");
      return;
    }
    const b64 = await fileToBase64(file);
    dispatch({ b64, mt: file.type, source: "photo" });
  }

  function cleanupStream() {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }

  React.useEffect(() => cleanupStream, []);

  async function startRecording() {
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
        setRecording(false);
        setElapsed(0);
        if (blob.size === 0) { toast.error("Kayıt boş"); return; }
        const cleanMime = mime.split(";")[0];
        const mt = ALLOWED_AUDIO.includes(cleanMime) ? cleanMime : "audio/webm";
        const b64 = await blobToBase64(blob);
        dispatch({ b64, mt, source: "voice" });
      };
      recorderRef.current = rec;
      rec.start();
      setRecording(true);
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    } catch {
      toast.error("Mikrofon erişimi reddedildi");
      cleanupStream();
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
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
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        className="hidden"
        onChange={onFile}
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-medium">Koçluk Seansları</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Görüşme notları + kararlar. Tahsilat yapılan seansları sayar.
          </p>
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
            onClick={() => gateConsent(runInsight)}
            disabled={busy || !hasSessions}
            title={hasSessions ? "Seans geçmişinden bir sonraki seans için AI önerisi" : "Önce en az bir seans kaydı gerekir"}
          >
            {insight.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Lightbulb className="size-4" aria-hidden />}
            İçgörü al
          </Button>
          {recording ? (
            <Button size="sm" variant="destructive" onClick={stopRecording}>
              <Square className="size-3.5 fill-current" aria-hidden />
              Durdur · {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={startRecording} disabled={busy}>
              {parseVoice.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Mic className="size-4" aria-hidden />}
              Sesle doldur
            </Button>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            {parsePhoto.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Camera className="size-4" aria-hidden />}
            Fotoğraftan doldur
          </Button>
          <Button size="sm" onClick={openNew} disabled={recording}>
            <Plus className="size-4" aria-hidden /> Yeni Seans
          </Button>
        </div>
      </div>

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
            <DialogTitle>
              {editing
                ? "Seansı düzenle"
                : draft
                  ? draftSource === "insight" ? "İçgörüden seans" : draftSource === "voice" ? "Sesten taslak" : "Fotoğraftan taslak"
                  : "Yeni seans kaydı"}
            </DialogTitle>
          </DialogHeader>
          {draft ? (
            <div className="-mt-1 mb-1 flex items-center gap-2 rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-xs text-violet-800">
              <Sparkles className="size-4 shrink-0" aria-hidden />
              {draftSource === "insight"
                ? "Yapay zekâ önerisinden bir gündem taslağı hazırlandı. Düzenleyip kaydedin."
                : `Yapay zekâ ${draftSource === "voice" ? "sesinizi" : "fotoğrafı"} okudu. Lütfen kontrol edip düzeltin — kaydetmeden hiçbir şey saklanmaz.`}
            </div>
          ) : null}
          <SessionForm
            studentId={studentId}
            editing={editing}
            draft={draft}
            draftSource={draftSource}
            onDone={() => {
              setFormOpen(false);
              setDraft(null);
              setDraftSource(null);
            }}
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
              içgörü üretilmek üzere yapay zekâ hizmetlerine (Anthropic, OpenAI)
              gönderilir. Devam etmek için onayınız gerekir.
            </p>
            <ul className="space-y-1.5 text-xs">
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-emerald-600" aria-hidden /> Fotoğraf / ses <strong>saklanmaz</strong>; yalnızca işlenir, ardından silinir.</li>
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-emerald-600" aria-hidden /> Yalnızca <strong>siz</strong> görürsünüz; öğrenci ve veli erişemez.</li>
              <li className="flex gap-2"><ShieldCheck className="size-4 shrink-0 text-amber-600" aria-hidden /> İşleme yurt dışındaki hizmetler (Anthropic, OpenAI) tarafından yapılır.</li>
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
          {insightData ? (
            <div className="max-h-[68vh] space-y-4 overflow-y-auto pr-1 text-sm">
              <p className="rounded-md bg-muted/50 px-3 py-2 leading-relaxed">{insightData.summary}</p>

              {insightData.agenda_suggestions.length > 0 ? (
                <InsightList
                  title="Bir sonraki seansta konuş"
                  icon={<CalendarCheck className="size-4 text-cyan-600" aria-hidden />}
                  items={insightData.agenda_suggestions}
                />
              ) : null}
              {insightData.psychological_tips.length > 0 ? (
                <InsightList
                  title="Yaklaşım ipuçları"
                  icon={<Sparkles className="size-4 text-violet-600" aria-hidden />}
                  items={insightData.psychological_tips}
                />
              ) : null}
              {insightData.watch_outs.length > 0 ? (
                <InsightList
                  title="Dikkat"
                  icon={<AlertTriangle className="size-4 text-amber-600" aria-hidden />}
                  items={insightData.watch_outs}
                  tone="warn"
                />
              ) : null}

              <p className="text-[11px] text-muted-foreground">
                {insightData.based_on_sessions} seans + güncel akademik durumdan üretildi.
                Bu bir öneridir; klinik teşhis değildir. Yalnızca siz görürsünüz.
              </p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <Button variant="ghost" onClick={() => setInsightOpen(false)}>Kapat</Button>
                {insightData.agenda_suggestions.length > 0 ? (
                  <Button onClick={startSessionFromInsight}>
                    <Plus className="size-4" aria-hidden /> Bu gündemle seans aç
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}
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
      </div>
    </div>
  );
}

const TODAY = () => new Date().toISOString().slice(0, 10);

function SessionForm({
  studentId,
  editing,
  draft,
  draftSource,
  onDone,
}: {
  studentId: number;
  editing: CoachingSessionRow | null;
  draft?: SessionDraftResponse | null;
  draftSource?: DraftSource | null;
  onDone: () => void;
}) {
  const create = useCreateSession(studentId);
  const update = useUpdateSession();
  const isEdit = !!editing;

  const [date, setDate] = React.useState(editing?.session_date ?? TODAY());
  const [stat, setStat] = React.useState<SessionStatus>(editing?.status ?? "done");
  const [channel, setChannel] = React.useState<SessionChannel | "">(editing?.channel ?? "");
  const [duration, setDuration] = React.useState(editing?.duration_min ? String(editing.duration_min) : "");
  const [agenda, setAgenda] = React.useState(editing?.agenda ?? draft?.agenda ?? "");
  const [note, setNote] = React.useState(editing?.coach_note ?? draft?.coach_note ?? "");
  const [nextChange, setNextChange] = React.useState(editing?.next_change ?? draft?.next_change ?? "");
  const [mood, setMood] = React.useState<number | null>(editing?.mood ?? draft?.mood ?? null);
  const [tags, setTags] = React.useState((editing?.tags ?? draft?.tags ?? []).join(", "));
  const [error, setError] = React.useState<string | null>(null);

  // Otomatik panel — yalnız yeni seansta çekilir
  const prefill = useQuery<SessionPrefillResponse>({
    queryKey: teacherKeys.sessionPrefill(studentId),
    queryFn: () => getTeacherSessionPrefill(studentId),
    enabled: !isEdit,
    staleTime: 60_000,
  });

  const pending = create.isPending || update.isPending;

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
      const captureSource = draftSource === "photo" || draftSource === "voice" ? { capture_source: draftSource } : {};
      create.mutate({ body: { ...body, ...captureSource } }, { onSuccess: () => onDone() });
    }
  }

  return (
    <form onSubmit={submit} className="max-h-[72vh] space-y-3 overflow-y-auto pr-1">
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
        <Label htmlFor="se-agenda">Gündem / konuşulacaklar <span className="text-rose-500">*</span></Label>
        <textarea id="se-agenda" value={agenda} onChange={(e) => setAgenda(e.target.value)} rows={2} required
          placeholder="Bu seansta konuşulan / konuşulacak ana konular"
          className="w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/30" />
      </div>

      <div className="space-y-1">
        <Label htmlFor="se-note">Görüşme notu (ops.)</Label>
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
        <Button type="submit" disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <CalendarCheck className="size-4" aria-hidden />}
          {isEdit ? "Güncelle" : "Kaydet"}
        </Button>
      </div>
    </form>
  );
}
