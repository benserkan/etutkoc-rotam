"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Download,
  FileText,
  Inbox,
  Loader2,
  MessageSquarePlus,
  Paperclip,
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
  useUploadAttachment,
  useWithdrawSupport,
} from "@/lib/hooks/use-support-mutations";
import type {
  SupportCategoryOption,
  SupportListResponse,
  SupportRequestListItem,
  SupportStatus,
} from "@/lib/types/support";

const FIELD =
  "flex w-full rounded-2xl border border-input bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500";

// Durum renkleri (2026-10-03, Paketim diliyle): DOLGULU rozet + beyaz yazı —
// açık ve koyu temada aynı okunur. Camgöbeği açık · kehribar inceleniyor ·
// mor cevap geldi (dikkat) · yeşil çözüldü · gri geri çekildi.
const STATUS_TONE: Record<SupportStatus, { chip: string; bar: string }> = {
  open: { chip: "bg-cyan-700 text-white", bar: "bg-cyan-600" },
  under_review: { chip: "bg-amber-500 text-amber-950", bar: "bg-amber-500" },
  answered: { chip: "bg-violet-600 text-white", bar: "bg-violet-600" },
  resolved: { chip: "bg-emerald-600 text-white", bar: "bg-emerald-600" },
  withdrawn: { chip: "bg-slate-500 text-white", bar: "bg-slate-400" },
};

// Gönderenin rolü küçük dolgulu nokta + etiketle; balon rengi yalnız "ben / karşı taraf".
const ROLE_DOT: Record<string, string> = {
  teacher: "bg-cyan-600",
  institution_admin: "bg-amber-500",
  super_admin: "bg-violet-600",
  parent: "bg-emerald-600",
  student: "bg-sky-500",
};

const ROLE_LABEL: Record<string, string> = {
  teacher: "Koç / Öğretmen",
  institution_admin: "Kurum Yöneticisi",
  super_admin: "Süper Yönetici",
  parent: "Veli",
  student: "Öğrenci",
};

function fmtSize(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

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
        "inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
        STATUS_TONE[status].chip,
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
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-2xl font-bold text-foreground">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
        {canCreate ? (
          <Button onClick={() => setCreateOpen(true)} className="h-11 bg-cyan-700 px-5 text-white hover:bg-cyan-800">
            <MessageSquarePlus className="size-4" aria-hidden />
            Yeni Talep
          </Button>
        ) : null}
      </div>

      {/* Durum filtreleri */}
      <div className="flex flex-wrap gap-1 rounded-2xl border border-border bg-muted/50 p-1 sm:inline-flex sm:rounded-full" role="radiogroup" aria-label="Durum">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            type="button"
            role="radio"
            aria-checked={statusFilter === f.value}
            onClick={() => setStatusFilter(f.value)}
            className={cn(
              "rounded-full px-3.5 py-1.5 text-sm font-semibold transition",
              statusFilter === f.value
                ? "bg-cyan-700 text-white"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)]">
        {/* Liste */}
        <div className={cn(selectedId != null ? "hidden lg:block" : "block")}>
          {listQuery.isLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              <Loader2 className="size-5 animate-spin" aria-hidden />
            </div>
          ) : items.length === 0 ? (
            <EmptyList view={view} />
          ) : (
            <ul className="space-y-2.5">
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
            <div className="hidden h-full min-h-[280px] flex-col items-center justify-center gap-2 rounded-3xl border border-dashed border-border text-sm text-muted-foreground lg:flex">
              <Inbox className="size-8" aria-hidden />
              Görüntülemek için soldan bir talep seç.
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
    <div className="rounded-3xl border border-dashed border-border p-10 text-center">
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
        "relative w-full overflow-hidden rounded-2xl border-2 bg-card py-3.5 pl-5 pr-4 text-left transition",
        active ? "border-cyan-600 shadow-md" : "border-border hover:border-cyan-600/50",
      )}
    >
      <span className={cn("absolute inset-y-0 left-0 w-1.5", STATUS_TONE[item.status].bar)} aria-hidden />
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 break-words text-sm font-semibold text-foreground">{item.subject}</p>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-1">
          {item.escalated ? (
            <span className="inline-flex items-center rounded-full bg-violet-600 px-2 py-0.5 text-[11px] font-semibold text-white">
              Yönlendirildi
            </span>
          ) : null}
          <StatusBadge status={item.status} label={item.status_label} />
        </div>
      </div>
      <p className="mt-1.5 line-clamp-2 break-words text-sm text-muted-foreground">
        {item.last_message_preview ?? "—"}
      </p>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
        <span className="rounded-full bg-muted px-2 py-0.5 font-medium text-foreground">{item.category_label}</span>
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
  const upload = useUploadAttachment(requestId);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const [replyBody, setReplyBody] = React.useState("");
  const [escalateOpen, setEscalateOpen] = React.useState(false);
  const [escalateNote, setEscalateNote] = React.useState("");

  function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) upload.mutate({ file: f });
    e.target.value = "";
  }

  const data = q.data;
  const terminal = data ? data.status === "resolved" || data.status === "withdrawn" : false;
  const isMine = data?.is_mine ?? false;
  const canManage = data?.can_manage ?? false;
  const isEscalator = data?.is_escalator ?? false;

  function submitReply() {
    const body = replyBody.trim();
    if (!body) return;
    reply.mutate({ body }, { onSuccess: () => setReplyBody("") });
  }

  return (
    <div className="overflow-hidden rounded-3xl border border-border bg-card">
      <div className="flex items-start gap-2 border-b border-border px-5 py-4">
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
                <h2 className="break-words font-display text-lg font-semibold text-foreground">{data.subject}</h2>
                <StatusBadge status={data.status} label={data.status_label} />
                {data.escalated ? (
                  <span className="inline-flex items-center rounded-full bg-violet-600 px-2.5 py-0.5 text-xs font-semibold text-white">
                    Süper yöneticiye yönlendirildi
                  </span>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {data.category_label} · {data.requester_name}
                {data.institution_name ? ` · ${data.institution_name}` : ""} ·{" "}
                {fmt(data.created_at)}
                {data.handled_by_name ? ` · İlgilenen: ${data.handled_by_name}` : ""}
                {data.escalated && data.escalated_by_name
                  ? ` · Yönlendiren: ${data.escalated_by_name}`
                  : ""}
              </p>
            </>
          )}
        </div>
      </div>

      {/* Thread — balon rengi GÖNDEREN ROLÜNE göre */}
      <div className="max-h-[520px] space-y-4 overflow-y-auto px-5 py-5">
        {(data?.messages ?? []).map((m) => {
          const roleLabel = m.sender_role ? ROLE_LABEL[m.sender_role] ?? "" : "";
          const dot = (m.sender_role && ROLE_DOT[m.sender_role]) || "bg-slate-400";
          return (
            <div key={m.id} className={cn("flex flex-col gap-1", m.is_me ? "items-end" : "items-start")}>
              <div className={cn("flex flex-wrap items-center gap-1.5 px-1 text-xs", m.is_me && "justify-end")}>
                <span className={cn("size-2 rounded-full", dot)} aria-hidden />
                {m.sender_profile_url ? (
                  <Link href={m.sender_profile_url} className="font-semibold text-foreground underline-offset-2 hover:underline">
                    {m.sender_name}
                  </Link>
                ) : (
                  <span className="font-semibold text-foreground">{m.sender_name}</span>
                )}
                {roleLabel ? <span className="text-muted-foreground">· {roleLabel}</span> : null}
                <span className="text-muted-foreground">· {fmt(m.created_at)}</span>
              </div>
              <p
                className={cn(
                  "max-w-[88%] whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-sm leading-relaxed",
                  m.is_me ? "rounded-tr-md bg-cyan-700 text-white" : "rounded-tl-md bg-muted text-foreground",
                )}
              >
                {m.body}
              </p>
            </div>
          );
        })}
      </div>

      {/* Ekler */}
      {data && (data.attachments?.length ?? 0) > 0 ? (
        <div className="border-t border-border px-5 py-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Ekler ({data.attachments.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {data.attachments.map((a) => (
              <a
                key={a.id}
                href={a.download_url}
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-2 text-xs transition hover:bg-muted"
                title={`${a.filename} · ${fmtSize(a.size_bytes)} · ${a.uploaded_by_name}`}
              >
                {a.is_image ? (
                  // eslint-disable-next-line @next/next/no-img-element -- küçük önizleme, auth'lu BFF ucu
                  <img
                    src={a.download_url}
                    alt={a.filename}
                    className="size-9 rounded object-cover"
                  />
                ) : (
                  <span className="flex size-9 items-center justify-center rounded bg-rose-100 dark:bg-rose-500/15 text-rose-700 dark:text-rose-300">
                    <FileText className="size-4" aria-hidden />
                  </span>
                )}
                <span className="max-w-[140px]">
                  <span className="block truncate font-medium">{a.filename}</span>
                  <span className="block text-[10px] text-muted-foreground">
                    {fmtSize(a.size_bytes)} · {a.uploaded_by_name}
                  </span>
                </span>
                <Download className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition group-hover:opacity-100" aria-hidden />
              </a>
            ))}
          </div>
        </div>
      ) : null}

      {/* Aksiyonlar + yanıt */}
      <div className="space-y-3 border-t border-border bg-muted/30 px-5 py-4">
        {data && !terminal ? (
          <>
            <textarea
              className={cn(FIELD, "min-h-[88px] resize-y")}
              placeholder="Mesajını yaz…"
              value={replyBody}
              onChange={(e) => setReplyBody(e.target.value)}
              maxLength={5000}
            />
            {isEscalator && !canManage ? (
              <p className="rounded-xl bg-violet-600 px-3 py-2 text-sm text-white">
                Bu talebi süper yöneticiye yönlendirdiniz; süper yönetici yanıtladığında
                cevap burada görünür.
              </p>
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap gap-2">
                {canManage ? (
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
                ) : isMine ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => withdraw.mutate()}
                    disabled={withdraw.isPending}
                  >
                    Geri çek
                  </Button>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif,application/pdf"
                  className="hidden"
                  onChange={onPickFile}
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={upload.isPending}
                  title="Dosya ekle (görsel / PDF, en fazla 10 MB)"
                >
                  {upload.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <Paperclip className="size-4" aria-hidden />
                  )}
                  Dosya
                </Button>
                <Button onClick={submitReply} disabled={reply.isPending || !replyBody.trim()} className="bg-cyan-700 text-white hover:bg-cyan-800">
                  {reply.isPending ? (
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                  ) : (
                    <Send className="size-4" aria-hidden />
                  )}
                  Gönder
                </Button>
              </div>
            </div>
          </>
        ) : data ? (
          <p className="text-center text-sm text-muted-foreground">
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
                  { onSuccess: () => setEscalateOpen(false) },
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
