"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarCheck,
  ChevronDown,
  Loader2,
  Plus,
  Printer,
  Trash2,
} from "lucide-react";

import {
  getTeacherStudentSessions,
  getTeacherSessionPrefill,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
} from "@/lib/hooks/use-teacher-mutations";
import type {
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

interface Props {
  studentId: number;
}

export function StudentSessionsPanel({ studentId }: Props) {
  const q = useQuery<StudentSessionListResponse>({
    queryKey: teacherKeys.studentSessions(studentId),
    queryFn: () => getTeacherStudentSessions(studentId),
    staleTime: 30_000,
  });
  const [formOpen, setFormOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<CoachingSessionRow | null>(null);
  const data = q.data;

  function openNew() {
    setEditing(null);
    setFormOpen(true);
  }
  function openEdit(row: CoachingSessionRow) {
    setEditing(row);
    setFormOpen(true);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-medium">Koçluk Seansları</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Görüşme notları + kararlar. Tahsilat (yakında) yapılan seansları sayar.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href={`/teacher/students/${studentId}/sessions/print`}
            target="_blank"
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted"
          >
            <Printer className="size-3.5" aria-hidden /> Boş form
          </Link>
          <Button size="sm" onClick={openNew}>
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
            <DialogTitle>{editing ? "Seansı düzenle" : "Yeni seans kaydı"}</DialogTitle>
          </DialogHeader>
          <SessionForm
            studentId={studentId}
            editing={editing}
            onDone={() => setFormOpen(false)}
          />
        </DialogContent>
      </Dialog>
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
  onDone,
}: {
  studentId: number;
  editing: CoachingSessionRow | null;
  onDone: () => void;
}) {
  const create = useCreateSession(studentId);
  const update = useUpdateSession();
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
      create.mutate({ body }, { onSuccess: () => onDone() });
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
