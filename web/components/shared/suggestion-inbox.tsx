"use client";

/**
 * Mesaj önerileri gelen kutusu (2026-11-14) — koç "Bugünün mesajları" ve kurum
 * yöneticisi "Koçlara mesajlar" ORTAK bileşeni. Çok öğrenci/koçta sayfa uzamasın
 * diye iki panel: solda aranabilir kısa liste (kendi içinde kayar), sağda seçilenin
 * önerileri (kapalı satırlar; tıklanan açılır, gönder/atla sonrası sıradakine geçer).
 * Telefonda önce liste, dokununca ayrıntı.
 */

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, ChevronRight, Loader2, MessageCircle, Search, Send, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import type { SuggestionItem, SuggestionsResponse } from "@/lib/api/message-suggestions";
import { cn } from "@/lib/utils";

const LINK_TOKEN = "[rapor bağlantısı]";

const KIND_STYLE: Record<string, string> = {
  problem: "bg-amber-600 text-white",
  positive: "bg-emerald-700 text-white",
  reminder: "bg-sky-700 text-white",
  report: "bg-cyan-800 text-white",
};
const KIND_DOT: Record<string, string> = {
  problem: "bg-amber-500",
  positive: "bg-emerald-600",
  reminder: "bg-sky-600",
  report: "bg-cyan-700",
};
const KIND_ORDER = ["problem", "reminder", "report", "positive"];
const AUDIENCE_LABEL: Record<string, string> = { parent: "Veliye", student: "Öğrenciye", coach: "Koça" };

type KindFilter = "all" | "problem" | "positive" | "reminder" | "report";

export interface SuggestionInboxProps {
  title: string;
  description: string;
  groupNoun: string;
  queryKey: readonly unknown[];
  invalidateKey: readonly unknown[];
  fetcher: () => Promise<SuggestionsResponse>;
  send: (it: SuggestionItem, text: string, targetId: number | null) => Promise<{ wa_url: string; target_name: string | null }>;
  skip: (it: SuggestionItem) => Promise<unknown>;
  groupHref?: (groupId: number) => string;
  groupLinkLabel?: string;
  initialGroupId?: number | null;
}

function itemId(it: SuggestionItem) {
  return `${it.group_id}|${it.audience}|${it.key}`;
}

export function SuggestionInbox(props: SuggestionInboxProps) {
  const { title, description, groupNoun, queryKey, fetcher, groupHref, groupLinkLabel } = props;
  const q = useQuery({ queryKey, queryFn: fetcher, staleTime: 60_000 });
  const [kind, setKind] = React.useState<KindFilter>("all");
  const [audience, setAudience] = React.useState<string>("all");
  const [search, setSearch] = React.useState("");
  const [picked, setPicked] = React.useState<number | null>(props.initialGroupId ?? null);
  const [mobileDetail, setMobileDetail] = React.useState(props.initialGroupId != null);

  const items = React.useMemo(() => q.data?.items ?? [], [q.data]);
  const audiences = React.useMemo(() => [...new Set(items.map((i) => i.audience))], [items]);
  const filtered = items.filter(
    (i) => (kind === "all" || i.kind === kind) && (audience === "all" || i.audience === audience),
  );
  const term = search.trim().toLocaleLowerCase("tr");
  const groups = React.useMemo(() => {
    const m = new Map<number, { id: number; name: string; items: SuggestionItem[] }>();
    for (const it of filtered) {
      const g = m.get(it.group_id) ?? { id: it.group_id, name: it.group_name, items: [] };
      g.items.push(it);
      m.set(it.group_id, g);
    }
    return [...m.values()]
      .filter((g) => !term || (g.name ?? "").toLocaleLowerCase("tr").includes(term))
      .map((g) => ({
        ...g,
        items: [...g.items].sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind)),
      }))
      .sort((a, b) => {
        const pa = a.items.filter((i) => i.kind === "problem").length;
        const pb = b.items.filter((i) => i.kind === "problem").length;
        return pb - pa || b.items.length - a.items.length || (a.name ?? "").localeCompare(b.name ?? "", "tr");
      });
  }, [filtered, term]);
  const current = groups.find((g) => g.id === picked) ?? groups[0] ?? null;
  const sent = q.data?.sent_today ?? 0;
  const count = (k: KindFilter) => (k === "all" ? items.length : items.filter((i) => i.kind === k).length);

  function nextGroup(afterId: number) {
    const idx = groups.findIndex((g) => g.id === afterId);
    const nxt = groups[idx + 1] ?? groups[idx - 1] ?? null;
    setPicked(nxt ? nxt.id : null);
  }

  return (
    <div className="space-y-4" data-section="suggestion-inbox">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-2xl">
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <MessageCircle className="size-5 text-emerald-700" aria-hidden />
            {title}
          </h1>
          <p className="mt-1 text-[15px] leading-relaxed text-muted-foreground">{description}</p>
        </div>
        <p
          className={cn(
            "rounded-full px-3 py-1.5 text-sm font-semibold",
            sent >= 20 ? "bg-amber-600 text-white" : "bg-slate-200 text-slate-900",
          )}
          data-testid="msg-sent-today"
        >
          Bugün {sent} mesaj gönderdin
        </p>
      </div>
      {sent >= 20 ? (
        <p className="rounded-xl border border-amber-400 bg-amber-100 px-4 py-2.5 text-sm text-amber-950">
          Bugün çok sayıda mesaj gönderdin. Aynı kişiye üst üste mesaj gitmesi etkisini azaltabilir; önemli olanları seç.
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Tür süzgeci">
          {(["all", "problem", "reminder", "report", "positive"] as KindFilter[])
            .filter((k) => k === "all" || k === kind || count(k) > 0)
            .map((k) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={kind === k}
              onClick={() => setKind(k)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold",
                kind === k ? "border-cyan-800 bg-cyan-800 text-white" : "border-border bg-card hover:bg-muted",
              )}
            >
              {k !== "all" ? <span className={cn("size-2 rounded-full", KIND_DOT[k])} aria-hidden /> : null}
              {k === "all" ? "Tümü" : k === "problem" ? "Dikkat" : k === "positive" ? "Tebrik" : k === "reminder" ? "Hatırlatma" : "Yeni rapor"}
              <span className="tabular-nums">({count(k)})</span>
            </button>
          ))}
        </div>
        {audiences.length > 1 ? (
          <select
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
            aria-label="Kime"
            className="h-8 rounded-md border border-border bg-card px-2 text-sm"
          >
            <option value="all">Herkese</option>
            {audiences.map((a) => (
              <option key={a} value={a}>
                {AUDIENCE_LABEL[a] ?? a}
              </option>
            ))}
          </select>
        ) : null}
      </div>

      {q.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Durumlar taranıyor…
        </p>
      ) : q.isError ? (
        <p className="text-sm text-rose-800">Öneriler yüklenemedi. Sayfayı yenile.</p>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          Bugün için gönderilecek bir mesaj önerisi yok.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside
            className={cn(
              "rounded-xl border border-border bg-card",
              mobileDetail && "hidden lg:block",
            )}
            aria-label={`${groupNoun} listesi`}
          >
            <div className="border-b border-border p-3">
              <label className="relative block">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={`${groupNoun} ara`}
                  aria-label={`${groupNoun} ara`}
                  className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-2 text-sm"
                />
              </label>
              <p className="mt-2 text-xs text-muted-foreground">
                {groups.length} {groupNoun} · {filtered.length} öneri
              </p>
            </div>
            <ul className="max-h-[calc(100vh-300px)] min-h-40 overflow-y-auto p-1.5" data-testid="inbox-groups">
              {groups.map((g) => {
                const active = current?.id === g.id;
                const byKind = KIND_ORDER.map((k) => [k, g.items.filter((i) => i.kind === k).length] as const).filter(
                  ([, n]) => n > 0,
                );
                return (
                  <li key={g.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setPicked(g.id);
                        setMobileDetail(true);
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left",
                        active ? "bg-cyan-800 text-white" : "hover:bg-muted",
                      )}
                      aria-current={active ? "true" : undefined}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block font-semibold leading-snug">{g.name}</span>
                        <span className="mt-0.5 flex flex-wrap gap-x-2 gap-y-0.5 text-xs">
                          {byKind.map(([k, n]) => (
                            <span key={k} className="inline-flex items-center gap-1">
                              <span className={cn("size-2 rounded-full", KIND_DOT[k])} aria-hidden />
                              {n} {k === "problem" ? "dikkat" : k === "positive" ? "tebrik" : k === "reminder" ? "hatırlatma" : "rapor"}
                            </span>
                          ))}
                        </span>
                      </span>
                      <ChevronRight className="size-4 shrink-0 opacity-60" aria-hidden />
                    </button>
                  </li>
                );
              })}
              {groups.length === 0 ? (
                <li className="p-3 text-sm text-muted-foreground">Aramaya uyan {groupNoun} yok.</li>
              ) : null}
            </ul>
          </aside>

          <section className={cn("min-w-0", !mobileDetail && "hidden lg:block")}>
            {current ? (
              <GroupDetail
                key={current.id}
                group={current}
                {...props}
                onBack={() => setMobileDetail(false)}
                onEmpty={() => nextGroup(current.id)}
                groupHref={groupHref}
                groupLinkLabel={groupLinkLabel}
              />
            ) : (
              <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
                Soldan bir {groupNoun} seç.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function GroupDetail({
  group,
  invalidateKey,
  send,
  skip,
  groupHref,
  groupLinkLabel,
  onBack,
  onEmpty,
}: SuggestionInboxProps & {
  group: { id: number; name: string; items: SuggestionItem[] };
  onBack: () => void;
  onEmpty: () => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = React.useState<string | null>(group.items[0] ? itemId(group.items[0]) : null);

  function done(it: SuggestionItem) {
    const rest = group.items.filter((x) => itemId(x) !== itemId(it));
    if (rest.length === 0) onEmpty();
    else setOpen(itemId(rest[0]));
    qc.invalidateQueries({ queryKey: invalidateKey });
  }

  return (
    <div className="space-y-3" data-testid="inbox-detail">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-sm lg:hidden"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Liste
          </button>
          <h2 className="text-lg font-bold">{group.name}</h2>
          <span className="text-sm text-muted-foreground">{group.items.length} öneri</span>
        </div>
        {groupHref ? (
          <Link href={groupHref(group.id)} className="text-sm font-semibold text-cyan-800 hover:underline">
            {groupLinkLabel ?? "Sayfasını aç"}
          </Link>
        ) : null}
      </div>
      <ul className="space-y-2">
        {group.items.map((it) => (
          <SuggestionRow
            key={itemId(it)}
            item={it}
            open={open === itemId(it)}
            onToggle={() => setOpen(open === itemId(it) ? null : itemId(it))}
            send={send}
            skip={skip}
            onDone={() => done(it)}
          />
        ))}
      </ul>
    </div>
  );
}

/** Metin kutusu içeriğe göre büyür (koç: uzun mesajda kaydırma istemiyor). */
function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight + 2}px`;
}

function SuggestionRow({
  item,
  open,
  onToggle,
  send,
  skip,
  onDone,
}: {
  item: SuggestionItem;
  open: boolean;
  onToggle: () => void;
  send: SuggestionInboxProps["send"];
  skip: SuggestionInboxProps["skip"];
  onDone: () => void;
}) {
  const [text, setText] = React.useState(item.text);
  const firstOk = item.targets.find((t) => t.can_message) ?? item.targets[0] ?? null;
  const [target, setTarget] = React.useState<number | null>(firstOk?.user_id ?? null);
  const selected = item.targets.find((t) => t.user_id === target) ?? null;
  const canPhone = selected?.can_message ?? false;

  // eslint-disable-next-line lgs/missing-invalidate -- liste onDone içinde invalidateQueries ile tazelenir
  const sendM = useMutation({ mutationFn: () => send(item, text, canPhone ? target : null) });
  // eslint-disable-next-line lgs/missing-invalidate -- liste onDone içinde invalidateQueries ile tazelenir
  const skipM = useMutation({
    mutationFn: () => skip(item),
    onSuccess: () => {
      toast.success("Öneri atlandı.");
      onDone();
    },
    onError: () => toast.error("Atlanamadı, tekrar dene."),
  });

  async function onSend() {
    const isTouch = window.matchMedia?.("(pointer: coarse)").matches === true;
    const win = isTouch ? null : window.open("about:blank", "_blank");
    try {
      const res = await sendM.mutateAsync();
      if (win) win.location.href = res.wa_url;
      else window.location.href = res.wa_url;
      toast.success(
        res.target_name ? `${res.target_name} ile sohbet açıldı — gönder tuşuna basman yeterli.` : "WhatsApp açıldı — kişiyi seçip gönder.",
      );
      onDone();
    } catch (e) {
      win?.close();
      toast.error(e instanceof ApiError && e.message ? e.message : "WhatsApp açılamadı.");
    }
  }

  return (
    <li className={cn("rounded-xl border bg-card", open ? "border-cyan-700" : "border-border")} data-testid="msg-suggestion">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-3 text-left"
      >
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className={cn("rounded px-2 py-0.5 text-xs font-bold", KIND_STYLE[item.kind] ?? "bg-slate-600 text-white")}>
              {item.kind_label}
            </span>
            <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-bold text-slate-900">
              {AUDIENCE_LABEL[item.audience] ?? item.audience}
            </span>
            <span className="font-semibold">{item.title}</span>
          </span>
          {item.reason && !open ? <span className="mt-1 block text-sm text-muted-foreground">{item.reason}</span> : null}
        </span>
        <ChevronDown className={cn("mt-1 size-4 shrink-0 transition-transform", open && "rotate-180")} aria-hidden />
      </button>
      {open ? (
        <div className="space-y-3 border-t border-border px-4 pb-4 pt-3">
          {item.reason ? <p className="text-sm text-muted-foreground">{item.reason}</p> : null}
          <textarea
            ref={autoGrow}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              autoGrow(e.target);
            }}
            rows={3}
            maxLength={2000}
            aria-label={`${item.title} mesaj metni`}
            className="w-full resize-none overflow-hidden rounded-md border border-border bg-background px-3 py-2 text-sm leading-relaxed"
          />
          {text.includes(LINK_TOKEN) ? (
            <p className="-mt-1 text-xs text-muted-foreground">
              &quot;{LINK_TOKEN}&quot; gönderirken raporun gerçek bağlantısıyla değiştirilir (60 gün açık, sesli dinlenebilir).
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            {item.targets.length > 1 ? (
              <select
                value={target ?? ""}
                onChange={(e) => setTarget(Number(e.target.value))}
                aria-label="Alıcı"
                className="h-9 rounded-md border border-border bg-background px-2 text-sm"
              >
                {item.targets.map((t) => (
                  <option key={t.user_id} value={t.user_id}>
                    {t.full_name} ({t.relation_label}){t.can_message ? "" : " · numara yok"}
                  </option>
                ))}
              </select>
            ) : selected ? (
              <span className="text-sm text-muted-foreground">
                {selected.full_name} · {selected.relation_label}
                {selected.can_message ? "" : " · numara kayıtlı değil, WhatsApp'ta kişiyi sen seçersin"}
              </span>
            ) : null}
            <div className="ml-auto flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => skipM.mutate()} disabled={skipM.isPending}>
                <X className="size-4" aria-hidden />
                Atla
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={onSend}
                disabled={sendM.isPending || !text.trim()}
                className="bg-emerald-700 text-white hover:bg-emerald-800 hover:text-white"
              >
                {sendM.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
                WhatsApp&apos;ta gönder
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </li>
  );
}
