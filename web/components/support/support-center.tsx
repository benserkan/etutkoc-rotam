"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Inbox,
  Loader2,
  MessageSquarePlus,
  Send,
} from "lucide-react";

import { cn } from "@/lib/utils";
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
  getMySupportRequests,
  getSupportInbox,
  getSupportRequest,
  supportKeys,
} from "@/lib/api/support";
import {
  useCreateSupportRequest,
  useEscalateSupport,
  useReplySupport,
  useResolveSupport,
  useReviewSupport,
  useWithdrawSupport,
} from "@/lib/hooks/use-support-mutations";
import type {
  SupportCategoryOption,
  SupportListResponse,
  SupportRequestListItem,
  SupportStatus,
} from "@/lib/types/support";

const FIELD =
  "flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

// Durum tonları — açık zemin + koyu metin (koyu temada da okunur, purge-safe)
const STATUS_TONE: Record<SupportStatus, string> = {
  open: "border-sky-300 bg-sky-50 text-sky-900",
  under_review: "border-amber-300 bg-amber-50 text-amber-900",
  answered: "border-violet-300 bg-violet-50 text-violet-900",
  resolved: "border-emerald-300 bg-emerald-50 text-emerald-900",
  withdrawn: "border-slate-300 bg-slate-100 text-slate-700",
};

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: "", label: "Tümü" },
  { value: "open", label: "Açık" },
  { value: "under_review", label: "Değerlendiriliyor" },
  { value: "answered", label: "Cevaplandı" },
  { value: "resolved", label: "Çözümlendi" },
  { value: "withdrawn", label: "Geri çekildi" },
];

function fmt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function StatusBadge({ status, label }: { status: SupportStatus; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold",
        STATUS_TONE[status],
      )}
    >
      {label}
    </span>
  );
}

interface Props {
  view: "mine" | "inbox";
  initial: SupportListResponse;
  title: string;
  description: string;
  /** "mine" görünümünde yeni talep oluşturma açık. */
  canCreate?: boolean;
}

export function SupportCenter({ view, initial, title, description, canCreate }: Props) {
  const [statusFilter, setStatusFilter] = React.useState("");
  const [selectedId, setSelectedId] = React.useState<number | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);

  const listQuery = useQuery<SupportListResponse>({
    queryKey: view === "mine" ? supportKeys.mine(statusFilter) : supportKeys.inbox(statusFilter),
    queryFn: () =>
      view === "mine"
        ? getMySupportRequests(statusFilter || undefined)
        : getSupportInbox(statusFilter || undefined),
    initialData: statusFilter === "" ? initial : undefined,
  });

  const items = listQuery.data?.items ?? [];
  const categories = listQuery.data?.categories ?? initial.categories;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {canCreate ? (
          <Button onClick={() => setCreateOpen(true)}>
            <MessageSquarePlus className="size-4" aria-hidden />
            Yeni Talep
          </Button>
        ) : null}
      </div>

      {/* Durum filtreleri */}
      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            onClick={() => setStatusFilter(f.value)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition",
              statusFilter === f.value
                ? "border-foreground bg-foreground text-background"
                : "border-border bg-card text-muted-foreground hover:bg-muted",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        {/* Liste */}
        <div className={cn(selectedId != null ? "hidden lg:block" : "block")}>
          {listQuery.isLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" aria-hidden />
            </div>
          ) : items.length === 0 ? (
            <EmptyList view={view} />
          ) : (
            <ul className="space-y-2">
              {items.map((it) => (
                <li key={it.id}>
                  <RequestRow
                    item={it}
                    view={view}
                    active={selectedId === it.id}
                    onSelect={() => setSelectedId(it.id)}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Detay */}
        <div className={cn(selectedId == null ? "hidden lg:block" : "block")}>
          {selectedId == null ? (
            <div className="hidden h-full min-h-[200px] items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted-foreground lg:flex">
              Görüntülemek için bir talep seçin.
            </div>
          ) : (
            <RequestDetail
              key={selectedId}
              requestId={selectedId}
              onBack={() => setSelectedId(null)}
            />
          )}
        </div>
      </div>

      {canCreate && createOpen ? (
        <CreateDialog
          onOpenChange={setCreateOpen}
          categories={categories}
          onCreated={(id) => {
            setCreateOpen(false);
            setSelectedId(id);
          }}
        />
      ) : null}
    </div>
  );
}

function EmptyList({ view }: { view: "mine" | "inbox" }) {
  return (
    <div className="rounded-lg border border-dashed border-border p-8 text-center">
      <Inbox className="mx-auto size-8 text-muted-foreground" aria-hidden />
      <p className="mt-2 text-sm text-muted-foreground">
        {view === "mine"
          ? "Henüz bir talebiniz yok."
          : "Gelen kutusunda talep yok."}
      </p>
    </div>
  );
}

function RequestRow({
  item,
  view,
  active,
  onSelect,
}: {
  item: SupportRequestListItem;
  view: "mine" | "inbox";
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-lg border p-3 text-left transition",
        active ? "border-foreground bg-muted" : "border-border bg-card hover:bg-muted/60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="line-clamp-1 text-sm font-semibold">{item.subject}</p>
        <StatusBadge status={item.status} label={item.status_label} />
      </div>
      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
        {item.last_message_preview ?? "—"}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
        <span className="rounded bg-muted px-1.5 py-0.5">{item.category_label}</span>
        {view === "inbox" ? (
          <span className="truncate">
            {item.requester_name}
            {item.institution_name ? ` · ${item.institution_name}` : ""}
          </span>
        ) : (
          <span>→ {item.audience_label}</span>
        )}
        <span className="ml-auto">{fmt(item.last_activity_at)}</span>
      </div>
    </button>
  );
}

function RequestDetail({
  requestId,
  onBack,
}: {
  requestId: number;
  onBack: () => void;
}) {
  const q = useQuery({
    queryKey: supportKeys.detail(requestId),
    queryFn: () => getSupportRequest(requestId),
  });
  const reply = useReplySupport(requestId);
  const withdraw = useWithdrawSupport(requestId);
  const review = useReviewSupport(requestId);
  const resolve = useResolveSupport(requestId);
  const escalate = useEscalateSupport(requestId);
  const [replyBody, setReplyBody] = React.useState("");
  const [escalateOpen, setEscalateOpen] = React.useState(false);
  const [escalateNote, setEscalateNote] = React.useState("");

  const data = q.data;
  const terminal = data ? data.status === "resolved" || data.status === "withdrawn" : false;
  const isMine = data?.is_mine ?? false;

  function submitReply() {
    const body = replyBody.trim();
    if (!body) return;
    reply.mutate({ body }, { onSuccess: () => setReplyBody("") });
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-start gap-2 border-b border-border p-3">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden shrink-0"
          onClick={onBack}
          aria-label="Geri"
        >
          <ArrowLeft className="size-4" aria-hidden />
        </Button>
        <div className="min-w-0 flex-1">
          {q.isLoading || !data ? (
            <p className="text-sm text-muted-foreground">Yükleniyor…</p>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold">{data.subject}</h2>
                <StatusBadge status={data.status} label={data.status_label} />
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {data.category_label} · {data.requester_name}
                {data.institution_name ? ` · ${data.institution_name}` : ""} ·{" "}
                {fmt(data.created_at)}
                {data.handled_by_name ? ` · İlgilenen: ${data.handled_by_name}` : ""}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Thread */}
      <div className="max-h-[420px] space-y-3 overflow-y-auto p-3">
        {(data?.messages ?? []).map((m) => (
          <div
            key={m.id}
            className={cn("flex", m.is_me ? "justify-end" : "justify-start")}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2 text-sm",
                m.is_me
                  ? "bg-foreground text-background"
                  : "bg-muted text-foreground",
              )}
            >
              {!m.is_me ? (
                <p className="mb-0.5 text-[11px] font-semibold opacity-70">
                  {m.sender_name}
                </p>
              ) : null}
              <p className="whitespace-pre-wrap break-words">{m.body}</p>
              <p
                className={cn(
                  "mt-1 text-[10px]",
                  m.is_me ? "text-background/60" : "text-muted-foreground",
                )}
              >
                {fmt(m.created_at)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Aksiyonlar + yanıt */}
      <div className="space-y-2 border-t border-border p-3">
        {data && !terminal ? (
          <>
            <textarea
              className={cn(FIELD, "min-h-[64px] resize-y")}
              placeholder="Mesaj yazın…"
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              maxLength={5000}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                {!isMine ? (
                  <>
                    {(data.status === "open" || data.status === "answered") ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => review.mutate()}
                        disabled={review.isPending}
                      >
                        İncelemeye al
                      </Button>
                    ) : null}
                    {data.can_escalate ? (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEscalateOpen(true)}
                        disabled={escalate.isPending}
                      >
                        <ArrowUpRight className="size-4" aria-hidden />
                        Süper yöneticiye yönlendir
                      </Button>
                    ) : null}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => resolve.mutate()}
                      disabled={resolve.isPending}
                    >
                      <CheckCircle2 className="size-4" aria-hidden />
                      Çözümle
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => withdraw.mutate()}
                    disabled={withdraw.isPending}
                  >
                    Geri çek
                  </Button>
                )}
              </div>
              <Button size="sm" onClick={submitReply} disabled={reply.isPending || !replyBody.trim()}>
                {reply.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Send className="size-4" aria-hidden />
                )}
                Gönder
              </Button>
            </div>
          </>
        ) : data ? (
          <p className="text-center text-xs text-muted-foreground">
            Bu talep {data.status_label.toLowerCase()}; yeni mesaj eklenemez.
          </p>
        ) : null}
      </div>

      <Dialog open={escalateOpen} onOpenChange={setEscalateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Süper yöneticiye yönlendir</DialogTitle>
            <DialogDescription>
              Çözemediğiniz (teknik / şifre vb.) talebi süper yöneticiye iletin.
              Talep gelen kutunuzdan çıkar ve süper yönetici tarafından ele alınır.
            </DialogDescription>
          </DialogHeader>
          <textarea
            className={cn(FIELD, "min-h-[90px] resize-y")}
            placeholder="Yönlendirme notu (opsiyonel) — süper yöneticiye kısa açıklama"
            value={escalateNote}
            onChange={(e) => setEscalateNote(e.target.value)}
            maxLength={5000}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEscalateOpen(false)}>
              Vazgeç
            </Button>
            <Button
              onClick={() =>
                escalate.mutate(
                  { note: escalateNote.trim() || undefined },
                  {
                    onSuccess: () => {
                      setEscalateOpen(false);
                      onBack();
                    },
                  },
                )
              }
              disabled={escalate.isPending}
            >
              {escalate.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ArrowUpRight className="size-4" aria-hidden />
              )}
              Yönlendir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CreateDialog({
  onOpenChange,
  categories,
  onCreated,
}: {
  onOpenChange: (v: boolean) => void;
  categories: SupportCategoryOption[];
  onCreated: (id: number) => void;
}) {
  // Yalnız açıkken mount edilir → state her açılışta taze (effect ile reset yok).
  const create = useCreateSupportRequest();
  const [category, setCategory] = React.useState(categories[0]?.value ?? "other");
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");

  function submit() {
    if (!subject.trim() || !body.trim()) return;
    create.mutate(
      { body: { category, subject: subject.trim(), body: body.trim() } },
      { onSuccess: (res) => onCreated(res.data.id) },
    );
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni Talep</DialogTitle>
          <DialogDescription>
            Konunuzu açık yazın; muhatap inceleyip yanıtlayacak.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium">Kategori</label>
            <select
              className={cn(FIELD, "h-10")}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categories.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Konu</label>
            <input
              className={cn(FIELD, "h-10")}
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              maxLength={200}
              placeholder="Kısa bir başlık"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium">Mesaj</label>
            <textarea
              className={cn(FIELD, "min-h-[120px] resize-y")}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              maxLength={5000}
              placeholder="Talebinizi ayrıntılı yazın…"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Vazgeç
          </Button>
          <Button onClick={submit} disabled={create.isPending || !subject.trim() || !body.trim()}>
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Send className="size-4" aria-hidden />
            )}
            Gönder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
