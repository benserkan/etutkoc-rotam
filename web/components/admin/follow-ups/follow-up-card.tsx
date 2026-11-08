"use client";

import * as React from "react";
import {
  AlarmClock,
  CalendarClock,
  Check,
  ChevronDown,
  Gauge,
  Pencil,
  RefreshCw,
  Repeat,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";

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
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  useCancelFollowUp,
  useCheckFollowUp,
  useCompleteFollowUp,
  useDeleteFollowUp,
  useReopenFollowUp,
  useSnoozeFollowUp,
} from "@/lib/hooks/use-follow-up-mutations";
import type { FollowUpItem, FollowUpReport } from "@/lib/types/follow-ups";

import { fmtDate, fmtDelta, fmtValue, isoToday, VerdictBadge } from "./shared";

const STRIPE: Record<string, string> = {
  overdue: "border-l-rose-600",
  today: "border-l-amber-500",
  upcoming: "border-l-cyan-600",
  later: "border-l-slate-300",
  done: "border-l-emerald-600",
  cancelled: "border-l-slate-300",
};

function dueText(it: FollowUpItem): { text: string; cls: string } {
  if (it.status === "done") return { text: `Tamamlandı · ${fmtDate(it.completed_at)}`, cls: "text-emerald-700" };
  if (it.status === "cancelled") return { text: `İptal edildi · ${fmtDate(it.completed_at)}`, cls: "text-slate-600" };
  const d = it.days_left;
  if (d < 0) return { text: `${-d} gün gecikti · vade ${fmtDate(it.effective_due)}`, cls: "text-rose-700 font-semibold" };
  if (d === 0) return { text: "Bugün", cls: "text-amber-700 font-semibold" };
  if (d === 1) return { text: `Yarın · ${fmtDate(it.effective_due)}`, cls: "text-cyan-800" };
  return { text: `${d} gün kaldı · ${fmtDate(it.effective_due)}`, cls: "text-slate-700" };
}

export function FollowUpCard({ item, onEdit }: { item: FollowUpItem; onEdit: (it: FollowUpItem) => void }) {
  const snooze = useSnoozeFollowUp();
  const check = useCheckFollowUp();
  const reopen = useReopenFollowUp();
  const del = useDeleteFollowUp();
  const [completeOpen, setCompleteOpen] = React.useState(false);
  const [cancelOpen, setCancelOpen] = React.useState(false);
  const [dateOpen, setDateOpen] = React.useState(false);
  const isOpen = item.status === "open";
  const due = dueText(item);

  return (
    <article
      className={cn("rounded-xl border border-border border-l-4 bg-card p-4", STRIPE[item.bucket])}
      data-follow-up-id={item.id}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="break-words text-[15px] font-semibold leading-snug">{item.title}</h3>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs">
            <span className={cn("inline-flex items-center gap-1", due.cls)}>
              <CalendarClock className="size-3.5" aria-hidden />
              {due.text}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-700">{item.category_label}</span>
            {item.priority === "high" ? (
              <span className="rounded-full bg-amber-500 px-2 py-0.5 font-semibold text-slate-900">Önemli</span>
            ) : null}
            {item.recurrence_days ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-2 py-0.5 text-violet-800">
                <Repeat className="size-3" aria-hidden />
                {item.recurrence_days} günde bir
              </span>
            ) : null}
            {item.check ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-cyan-100 px-2 py-0.5 text-cyan-900">
                <Gauge className="size-3" aria-hidden />
                {item.check.metric_label} · {item.check.owner_type === "coach" ? "koç bazında" : "sistem geneli"}
              </span>
            ) : null}
            {item.snoozed_until && isOpen ? (
              <span className="text-slate-600">(ilk vade {fmtDate(item.due_on)}, ertelendi)</span>
            ) : null}
          </div>
        </div>

        {isOpen ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <Button size="sm" onClick={() => setCompleteOpen(true)} className="bg-emerald-700 text-white hover:bg-emerald-800">
              <Check className="mr-1 size-4" aria-hidden />
              Tamamla
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" disabled={snooze.isPending}>
                  <AlarmClock className="mr-1 size-4" aria-hidden />
                  Ertele
                  <ChevronDown className="ml-1 size-3.5" aria-hidden />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {[1, 3, 7, 14].map((d) => (
                  <DropdownMenuItem key={d} onSelect={() => snooze.mutate({ id: item.id, days: d })}>
                    {d === 1 ? "Yarına" : d === 7 ? "1 hafta" : d === 14 ? "2 hafta" : `${d} gün`}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => setDateOpen(true)}>Tarih seç…</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" variant="ghost" onClick={() => onEdit(item)} aria-label="Düzenle">
              <Pencil className="size-4" aria-hidden />
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setCancelOpen(true)} aria-label="İptal et">
              <X className="size-4" aria-hidden />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <Button size="sm" variant="outline" disabled={reopen.isPending}
              onClick={() => reopen.mutate({ id: item.id, due_on: isoToday(7) })}>
              <RotateCcw className="mr-1 size-4" aria-hidden />
              Yeniden aç
            </Button>
            <Button size="sm" variant="ghost" aria-label="Sil" disabled={del.isPending}
              onClick={() => {
                if (window.confirm("Bu kayıt kalıcı olarak silinsin mi?")) del.mutate(item.id);
              }}>
              <Trash2 className="size-4" aria-hidden />
            </Button>
          </div>
        )}
      </div>

      {item.description ? (
        <p className="mt-3 whitespace-pre-wrap break-words text-sm text-slate-700">{item.description}</p>
      ) : null}

      {item.report ? (
        <ReportBlock
          report={item.report}
          onRefresh={isOpen ? () => check.mutate(item.id) : undefined}
          refreshing={check.isPending}
        />
      ) : item.check && isOpen ? (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          Ölçüm sonucu henüz hesaplanmadı.
          <Button size="sm" variant="outline" onClick={() => check.mutate(item.id)} disabled={check.isPending}>
            <RefreshCw className="mr-1 size-3.5" aria-hidden />
            Şimdi hesapla
          </Button>
        </div>
      ) : null}

      {!isOpen && item.result_note ? (
        <div className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">
          <span className="font-semibold">Sonuç: </span>
          <span className="whitespace-pre-wrap">{item.result_note}</span>
          {item.completed_by_name ? (
            <span className="text-emerald-800"> — {item.completed_by_name}</span>
          ) : null}
        </div>
      ) : null}

      {completeOpen ? (
        <CompleteDialog item={item} onClose={() => setCompleteOpen(false)} />
      ) : null}
      {cancelOpen ? <CancelDialog item={item} onClose={() => setCancelOpen(false)} /> : null}
      {dateOpen ? <SnoozeDateDialog item={item} onClose={() => setDateOpen(false)} /> : null}
    </article>
  );
}

function ReportBlock({
  report,
  onRefresh,
  refreshing,
}: {
  report: FollowUpReport;
  onRefresh?: () => void;
  refreshing: boolean;
}) {
  const [open, setOpen] = React.useState(report.verdict === "declined");
  const hasRows = report.rows.length > 0;
  return (
    <div className="mt-3 rounded-lg border border-cyan-200 bg-cyan-50 p-3 text-sm text-slate-900">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold text-cyan-900">Ölçüm sonucu</span>
        <VerdictBadge verdict={report.verdict} />
        <span className="text-xs text-slate-600">
          {fmtDate(report.baseline_on)} → {fmtDate(report.evaluated_on)}
        </span>
        {onRefresh ? (
          <button type="button" onClick={onRefresh} disabled={refreshing}
            className="ml-auto inline-flex items-center gap-1 text-xs font-medium text-cyan-800 hover:underline">
            <RefreshCw className={cn("size-3.5", refreshing && "animate-spin")} aria-hidden />
            Yeniden hesapla
          </button>
        ) : null}
      </div>
      <p className="mt-1.5 break-words">{report.summary}</p>
      {hasRows ? (
        <>
          <button type="button" onClick={() => setOpen((v) => !v)}
            className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-cyan-800 hover:underline">
            <ChevronDown className={cn("size-3.5 transition-transform", open && "rotate-180")} aria-hidden />
            {open ? "Ayrıntıyı gizle" : `Ayrıntı (${report.rows.length} satır)`}
          </button>
          {open ? (
            <div className="relative mt-2 overflow-x-auto">
              <table className="w-full min-w-[520px] text-xs">
                <thead>
                  <tr className="text-left text-slate-600">
                    <th className="py-1 pr-2 font-medium">Kim</th>
                    <th className="py-1 pr-2 font-medium">Başlangıç</th>
                    <th className="py-1 pr-2 font-medium">Son</th>
                    <th className="py-1 pr-2 font-medium">Değişim</th>
                    <th className="py-1 pr-2 font-medium">Örnek</th>
                    <th className="py-1 font-medium">Durum</th>
                  </tr>
                </thead>
                <tbody>
                  {report.rows.map((r) => (
                    <tr key={`${r.owner_type}-${r.owner_id}`} className="border-t border-cyan-200">
                      <td className={cn("py-1.5 pr-2", r.owner_type === "system" && "font-semibold")}>{r.owner_label}</td>
                      <td className="py-1.5 pr-2 tabular-nums">{fmtValue(r.base_value, report.unit)}</td>
                      <td className="py-1.5 pr-2 tabular-nums">{fmtValue(r.latest_value, report.unit)}</td>
                      <td className={cn("py-1.5 pr-2 tabular-nums font-medium",
                        r.verdict === "declined" ? "text-rose-700" : r.verdict === "improved" ? "text-emerald-700" : "text-slate-700")}>
                        {fmtDelta(r.delta, report.unit)}
                      </td>
                      <td className="py-1.5 pr-2 tabular-nums text-slate-600">{r.sample_n ?? "—"}</td>
                      <td className="py-1.5"><VerdictBadge verdict={r.verdict} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

function CompleteDialog({ item, onClose }: { item: FollowUpItem; onClose: () => void }) {
  const complete = useCompleteFollowUp();
  const [note, setNote] = React.useState("");
  const [nextDue, setNextDue] = React.useState(
    item.recurrence_days ? isoToday(item.recurrence_days) : "",
  );
  const [scheduleNext, setScheduleNext] = React.useState(!!item.recurrence_days);
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Tamamla</DialogTitle>
          <DialogDescription className="break-words">{item.title}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium" htmlFor="fu-note">Ne sonuç çıktı? (karar / yapılan)</label>
            <textarea id="fu-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder="örn. Düşen iki koçla görüşüldü; ağırlıklar varsayılanda kalacak." />
            <p className="text-xs text-muted-foreground">Not, kapalı işlerde kalır — 3 ay sonra &quot;ne karar vermiştik?&quot; sorusunun cevabı.</p>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={scheduleNext} onChange={(e) => setScheduleNext(e.target.checked)} />
            Sıradaki kontrolü de planla
          </label>
          {scheduleNext ? (
            <Input type="date" value={nextDue} min={isoToday(1)} onChange={(e) => setNextDue(e.target.value)} className="w-44" />
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
          <Button className="bg-emerald-700 text-white hover:bg-emerald-800"
            disabled={complete.isPending || (scheduleNext && !nextDue)}
            onClick={() =>
              complete.mutate(
                { id: item.id, note, next_due: scheduleNext ? nextDue : null },
                { onSuccess: onClose },
              )
            }>
            Tamamla
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CancelDialog({ item, onClose }: { item: FollowUpItem; onClose: () => void }) {
  const cancel = useCancelFollowUp();
  const [note, setNote] = React.useState("");
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>İptal et</DialogTitle>
          <DialogDescription className="break-words">
            {item.title} — artık gerekmiyorsa iptal et. Kayıt kapalı işlerde durur.
          </DialogDescription>
        </DialogHeader>
        <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Neden? (isteğe bağlı)" />
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
          <Button variant="destructive" disabled={cancel.isPending}
            onClick={() => cancel.mutate({ id: item.id, note }, { onSuccess: onClose })}>
            İptal et
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SnoozeDateDialog({ item, onClose }: { item: FollowUpItem; onClose: () => void }) {
  const snooze = useSnoozeFollowUp();
  const [until, setUntil] = React.useState(isoToday(7));
  return (
    <Dialog open onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Ertele</DialogTitle>
          <DialogDescription className="break-words">{item.title}</DialogDescription>
        </DialogHeader>
        <Input type="date" value={until} min={isoToday(1)} onChange={(e) => setUntil(e.target.value)} />
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
          <Button className="bg-cyan-700 text-white hover:bg-cyan-800" disabled={!until || snooze.isPending}
            onClick={() => snooze.mutate({ id: item.id, until }, { onSuccess: onClose })}>
            Ertele
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
