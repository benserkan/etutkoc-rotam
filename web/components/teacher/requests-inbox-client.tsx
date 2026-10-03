"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CalendarClock,
  Check,
  CheckCheck,
  Hash,
  Loader2,
  MessageCircle,
  RefreshCw,
  Reply,
  Trash2,
  X,
} from "lucide-react";

import {
  useAcknowledgeRequest,
  useApproveRequest,
  useRejectRequest,
  useRespondRequest,
} from "@/lib/hooks/use-teacher-mutations";
import type { RequestType, TeacherRequestListItem } from "@/lib/types/teacher";
import {
  REQUEST_STATUS_LABELS_TR,
  REQUEST_TYPE_LABELS_TR,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TYPE_ICON: Record<RequestType, React.ComponentType<{ className?: string }>> = {
  change: Hash,
  replace: RefreshCw,
  remove: Trash2,
  question: MessageCircle,
  add: CalendarClock,
};

const STATUS_TONE: Record<string, string> = {
  pending: "bg-amber-500 text-amber-950",
  approved: "bg-emerald-600 text-white",
  rejected: "bg-rose-600 text-white",
  withdrawn: "bg-slate-500 text-white",
  resolved: "bg-sky-600 text-white",
};

function relTime(iso: string): string {
  // Saat dilimi taşımayan değer (dev SQLite) UTC kabul edilir.
  const d = new Date(/(?:[zZ]|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`);
  const diff = Date.now() - d.getTime();
  const min = Math.round(diff / 60000);
  if (min < 1) return "az önce";
  if (min < 60) return `${min} dk önce`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} saat önce`;
  const days = Math.round(h / 24);
  if (days < 7) return `${days} gün önce`;
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
}

function fmtDay(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  return d.toLocaleDateString("tr-TR", { weekday: "long", day: "numeric", month: "long" });
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toLocaleUpperCase("tr-TR"))
    .join("");
}

function proposalText(r: TeacherRequestListItem): string | null {
  switch (r.type) {
    case "change":
      return r.proposed_count != null ? `Test sayısını ${r.proposed_count} yapmak istiyor` : "Test sayısını değiştirmek istiyor";
    case "replace":
      return "Görevin kaynağını değiştirmek istiyor";
    case "remove":
      return "Görevi programdan çıkarmak istiyor";
    case "add":
      return r.proposed_date ? `${fmtDay(r.proposed_date)} için görev eklemek istiyor` : "Yeni görev eklemek istiyor";
    default:
      return null;
  }
}

interface Props {
  items: TeacherRequestListItem[];
  status: string;
}

export function RequestsInbox({ items, status }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-10 text-center">
        <CheckCheck className="mx-auto size-8 text-emerald-600 dark:text-emerald-300" aria-hidden />
        <p className="mt-2 text-sm font-medium">Bu filtrede talep yok.</p>
        {status === "pending" ? (
          <p className="text-xs text-muted-foreground">Bekleyen işin kalmadı.</p>
        ) : null}
      </div>
    );
  }

  if (status !== "pending") {
    return (
      <ul className="space-y-2">
        {items.map((r) => (
          <HistoryCard key={r.id} r={r} />
        ))}
      </ul>
    );
  }

  const approvals = items.filter((r) => r.type !== "question");
  const questions = items.filter((r) => r.type === "question");

  return (
    <div className="space-y-8">
      <section aria-labelledby="req-approvals">
        <SectionHeader
          id="req-approvals"
          title="Onayını bekleyenler"
          count={approvals.length}
          hint="Öğrenci programında değişiklik istiyor. Onaylarsan değişiklik programa hemen uygulanır; reddedersen gerekçen öğrenciye gider."
        />
        {approvals.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Onay bekleyen değişiklik talebi yok.
          </p>
        ) : (
          <ul className="space-y-3">
            {approvals.map((r) => (
              <ApprovalCard key={r.id} r={r} />
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="req-questions">
        <SectionHeader
          id="req-questions"
          title="Soru ve not mesajları"
          count={questions.length}
          hint="Onay gerektirmez — öğrencinin sana yazdığı soru ya da bilgi notu. İstersen cevapla, cevap gerekmiyorsa “Gördüm” ile kapat; görev kilitlenmez."
        />
        {questions.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Yeni mesaj yok.
          </p>
        ) : (
          <ul className="space-y-3">
            {questions.map((r) => (
              <QuestionCard key={r.id} r={r} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function SectionHeader({ id, title, count, hint }: { id: string; title: string; count: number; hint: string }) {
  return (
    <div className="mb-3">
      <h2 id={id} className="flex items-center gap-2 text-base font-semibold">
        {title}
        <span className="rounded-full bg-foreground px-2 py-0.5 text-xs font-semibold text-background tabular-nums">
          {count}
        </span>
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}

function CardShell({ r, accent, children }: { r: TeacherRequestListItem; accent: string; children: React.ReactNode }) {
  const Icon = TYPE_ICON[r.type];
  const day = fmtDay(r.task_date);
  return (
    <li
      className={cn("rounded-xl border border-border bg-card p-4 shadow-sm border-l-4", accent)}
      data-request-id={r.id}
    >
      <div className="flex items-start gap-3">
        <span
          className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold"
          aria-hidden
        >
          {initials(r.student_name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              href={`/teacher/students/${r.student_id}`}
              className="text-sm font-semibold hover:underline break-words"
            >
              {r.student_name}
            </Link>
            <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium">
              <Icon className="size-3" aria-hidden />
              {REQUEST_TYPE_LABELS_TR[r.type]}
            </span>
            <span className="text-[11px] text-muted-foreground" title={new Date(r.created_at).toLocaleString("tr-TR")}>
              {relTime(r.created_at)}
            </span>
          </div>
          {r.task_title ? (
            <p className="mt-1 text-xs text-muted-foreground break-words">
              Görev: <span className="text-foreground">{r.task_title}</span>
              {day ? <> · {day}</> : null}
            </p>
          ) : null}
          {children}
        </div>
      </div>
    </li>
  );
}

function MessageBlock({ text }: { text: string | null }) {
  if (!text) return null;
  return (
    <blockquote className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-muted/60 px-3 py-2 text-sm">
      {text}
    </blockquote>
  );
}

function ApprovalCard({ r }: { r: TeacherRequestListItem }) {
  const router = useRouter();
  const approve = useApproveRequest(r.id);
  const reject = useRejectRequest(r.id);
  const [rejecting, setRejecting] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const proposal = proposalText(r);
  const busy = approve.isPending || reject.isPending;

  return (
    <CardShell r={r} accent="border-l-amber-500">
      {proposal ? (
        <p className="mt-2 flex items-center gap-1.5 text-sm font-medium">
          <ArrowRight className="size-4 text-amber-600 dark:text-amber-300" aria-hidden />
          {proposal}
        </p>
      ) : null}
      <MessageBlock text={r.message} />

      {rejecting ? (
        <div className="mt-3 space-y-2">
          <label htmlFor={`reason-${r.id}`} className="text-xs font-medium">
            Red gerekçesi (öğrenciye gider)
          </label>
          <textarea
            id={`reason-${r.id}`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Şu an program değişikliği yapamayız çünkü…"
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setRejecting(false)} disabled={busy}>
              Vazgeç
            </Button>
            <Button
              size="sm"
              className="bg-rose-600 text-white hover:bg-rose-700"
              disabled={busy || !reason.trim()}
              onClick={() =>
                reject.mutate(
                  { body: { reason: reason.trim() } },
                  { onSuccess: () => router.refresh() },
                )
              }
            >
              {reject.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <X className="size-4" aria-hidden />}
              Reddet
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              approve.mutate({ body: { response: null } }, { onSuccess: () => router.refresh() })
            }
          >
            {approve.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Check className="size-4" aria-hidden />}
            Onayla
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => setRejecting(true)}>
            <X className="size-4" aria-hidden />
            Reddet
          </Button>
          <Link
            href={`/teacher/requests/${r.id}`}
            className="ml-auto text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
          >
            Ayrıntı →
          </Link>
        </div>
      )}
    </CardShell>
  );
}

function QuestionCard({ r }: { r: TeacherRequestListItem }) {
  const router = useRouter();
  const ack = useAcknowledgeRequest(r.id);
  const respond = useRespondRequest(r.id);
  const [replying, setReplying] = React.useState(false);
  const [answer, setAnswer] = React.useState("");
  const busy = ack.isPending || respond.isPending;

  return (
    <CardShell r={r} accent="border-l-sky-500">
      <MessageBlock text={r.message} />
      {replying ? (
        <div className="mt-3 space-y-2">
          <label htmlFor={`answer-${r.id}`} className="text-xs font-medium">
            Cevabın
          </label>
          <textarea
            id={`answer-${r.id}`}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            placeholder="Tamam, yarının videolarını da izleyebilirsin."
            className="w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setReplying(false)} disabled={busy}>
              Vazgeç
            </Button>
            <Button
              size="sm"
              disabled={busy || !answer.trim()}
              onClick={() =>
                respond.mutate(
                  { body: { response: answer.trim() } },
                  { onSuccess: () => router.refresh() },
                )
              }
            >
              {respond.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Reply className="size-4" aria-hidden />}
              Gönder
            </Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={busy} onClick={() => setReplying(true)}>
            <Reply className="size-4" aria-hidden />
            Cevapla
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            title="Cevap yazmadan kapat — öğrenciye 'koçun mesajını gördü' bildirimi gider"
            onClick={() => ack.mutate(undefined, { onSuccess: () => router.refresh() })}
          >
            {ack.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <CheckCheck className="size-4" aria-hidden />}
            Gördüm
          </Button>
          <Link
            href={`/teacher/requests/${r.id}`}
            className="ml-auto text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
          >
            Ayrıntı →
          </Link>
        </div>
      )}
    </CardShell>
  );
}

function HistoryCard({ r }: { r: TeacherRequestListItem }) {
  return (
    <CardShell r={r} accent="border-l-slate-300 dark:border-l-slate-600">
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className={cn("rounded-md px-1.5 py-0.5 text-[11px] font-semibold", STATUS_TONE[r.status])}>
          {REQUEST_STATUS_LABELS_TR[r.status]}
        </span>
        {r.responded_at ? (
          <span className="text-[11px] text-muted-foreground">yanıt: {relTime(r.responded_at)}</span>
        ) : null}
        <Link
          href={`/teacher/requests/${r.id}`}
          className="ml-auto text-xs font-medium text-muted-foreground hover:text-foreground hover:underline"
        >
          Ayrıntı →
        </Link>
      </div>
      <MessageBlock text={r.message} />
      {r.teacher_response ? (
        <p className="mt-2 whitespace-pre-wrap break-words text-xs">
          <span className="font-semibold">Senin yanıtın:</span> {r.teacher_response}
        </p>
      ) : null}
    </CardShell>
  );
}
