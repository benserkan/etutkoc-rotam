"use client";

/**
 * "Bugünün mesajları" (2026-11-14, koç kararları): sistemin öğrenci hakkında fark
 * ettiği sorunlar, gelişmeler, hatırlatmalar ve yeni raporlar için hazır WhatsApp
 * mesajı. Sınır yok — koç seçer; bugün kaç mesaj gönderdiği üstte görünür.
 * Veri güvenilirliği uyarıları (toplu işaretleme vb.) listeye girmez.
 */

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, MessageCircle, Send, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import {
  getMessageSuggestions,
  messageSuggestionKeys,
  sendMessageSuggestion,
  skipMessageSuggestion,
  type SuggestionItem,
} from "@/lib/api/message-suggestions";
import { cn } from "@/lib/utils";

const LINK_TOKEN = "[rapor bağlantısı]";

const KIND_STYLE: Record<string, string> = {
  problem: "bg-amber-600 text-white",
  positive: "bg-emerald-700 text-white",
  reminder: "bg-sky-700 text-white",
  report: "bg-cyan-800 text-white",
};

type Filter = "all" | "parent" | "student" | "positive";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "Tümü" },
  { key: "parent", label: "Veliye" },
  { key: "student", label: "Öğrenciye" },
  { key: "positive", label: "Tebrikler" },
];

export function MessageSuggestionsClient({ studentId }: { studentId: number | null }) {
  const q = useQuery({
    queryKey: messageSuggestionKeys.list(studentId),
    queryFn: () => getMessageSuggestions(studentId),
    staleTime: 60_000,
  });
  const [filter, setFilter] = React.useState<Filter>("all");

  const items = React.useMemo(() => q.data?.items ?? [], [q.data]);
  const shown = items.filter((i) =>
    filter === "all" ? true : filter === "positive" ? i.kind === "positive" : i.audience === filter,
  );
  const groups = React.useMemo(() => {
    const m = new Map<number, { name: string; items: SuggestionItem[] }>();
    for (const it of shown) {
      const g = m.get(it.student_id) ?? { name: it.student_name, items: [] };
      g.items.push(it);
      m.set(it.student_id, g);
    }
    return [...m.entries()];
  }, [shown]);
  const sent = q.data?.sent_today ?? 0;

  return (
    <div className="space-y-5" data-section="message-suggestions">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 max-w-2xl">
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <MessageCircle className="size-5 text-emerald-700" aria-hidden />
            Bugünün mesajları
          </h1>
          <p className="mt-1 text-[15px] leading-relaxed text-muted-foreground">
            Sistemin fark ettiği sorunlar, gelişmeler ve yeni raporlar için hazır WhatsApp mesajları. Metni
            düzeltip kendi WhatsApp&apos;ından gönderirsin; gönderdiğin ya da atladığın öneri listeden düşer.
          </p>
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

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Mesaj süzgeci">
        {FILTERS.map((f) => {
          const n = f.key === "all" ? items.length : f.key === "positive"
            ? items.filter((i) => i.kind === "positive").length
            : items.filter((i) => i.audience === f.key).length;
          return (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm font-semibold",
                filter === f.key ? "border-cyan-800 bg-cyan-800 text-white" : "border-border bg-card hover:bg-muted",
              )}
            >
              {f.label} <span className="tabular-nums">({n})</span>
            </button>
          );
        })}
      </div>

      {q.isLoading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Öğrencilerin durumu taranıyor…
        </p>
      ) : q.isError ? (
        <p className="text-sm text-rose-800">Öneriler yüklenemedi. Sayfayı yenile.</p>
      ) : groups.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          {items.length ? "Bu süzgeçte öneri yok." : "Bugün için gönderilecek bir mesaj önerisi yok."}
        </p>
      ) : (
        <div className="space-y-6">
          {groups.map(([sid, g]) => (
            <section key={sid} className="space-y-3">
              <h2 className="flex flex-wrap items-baseline gap-2 text-base font-bold">
                <Link href={`/teacher/students/${sid}`} className="hover:underline">
                  {g.name}
                </Link>
                <span className="text-sm font-normal text-muted-foreground">{g.items.length} öneri</span>
              </h2>
              <div className="grid gap-3 lg:grid-cols-2">
                {g.items.map((it) => (
                  <SuggestionCard key={`${it.audience}:${it.key}`} item={it} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

/** Metin kutusu içeriğe göre büyür (2026-11-14, koç: uzun mesajda kaydırma istemiyor). */
function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight + 2}px`;
}

function SuggestionCard({ item }: { item: SuggestionItem }) {
  const qc = useQueryClient();
  const [text, setText] = React.useState(item.text);
  const firstOk = item.targets.find((t) => t.can_message) ?? item.targets[0] ?? null;
  const [target, setTarget] = React.useState<number | null>(firstOk?.user_id ?? null);
  const selected = item.targets.find((t) => t.user_id === target) ?? null;
  const canPhone = selected?.can_message ?? false;

  const refresh = () => qc.invalidateQueries({ queryKey: messageSuggestionKeys.all });

  // eslint-disable-next-line lgs/missing-invalidate -- öneri listesi qc.invalidateQueries ile tazelenir
  const send = useMutation({
    mutationFn: () =>
      sendMessageSuggestion({
        student_id: item.student_id,
        audience: item.audience,
        key: item.key,
        text,
        target_user_id: canPhone ? target : null,
      }),
    onSuccess: refresh,
  });
  // eslint-disable-next-line lgs/missing-invalidate -- öneri listesi qc.invalidateQueries ile tazelenir
  const skip = useMutation({
    mutationFn: () => skipMessageSuggestion({ student_id: item.student_id, audience: item.audience, key: item.key }),
    onSuccess: () => {
      refresh();
      toast.success("Öneri atlandı.");
    },
    onError: () => toast.error("Atlanamadı, tekrar dene."),
  });

  async function onSend() {
    const isTouch = window.matchMedia?.("(pointer: coarse)").matches === true;
    const win = isTouch ? null : window.open("about:blank", "_blank");
    try {
      const res = await send.mutateAsync();
      if (win) win.location.href = res.wa_url;
      else window.location.href = res.wa_url;
      toast.success(
        res.target_name ? `${res.target_name} ile sohbet açıldı — gönder tuşuna basman yeterli.` : "WhatsApp açıldı — kişiyi seçip gönder.",
      );
    } catch (e) {
      win?.close();
      toast.error(e instanceof ApiError && e.message ? e.message : "WhatsApp açılamadı.");
    }
  }

  const who = item.audience === "parent" ? "Veliye" : "Öğrenciye";
  return (
    <article className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4" data-testid="msg-suggestion">
      <div className="flex flex-wrap items-center gap-2">
        <span className={cn("rounded px-2 py-0.5 text-xs font-bold", KIND_STYLE[item.kind] ?? "bg-slate-600 text-white")}>
          {item.kind_label}
        </span>
        <span className="rounded bg-slate-200 px-2 py-0.5 text-xs font-bold text-slate-900">{who}</span>
      </div>
      <div>
        <p className="font-semibold">{item.title}</p>
        {item.reason ? <p className="mt-0.5 text-sm text-muted-foreground">{item.reason}</p> : null}
      </div>
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
          <Button type="button" variant="outline" size="sm" onClick={() => skip.mutate()} disabled={skip.isPending}>
            <X className="size-4" aria-hidden />
            Atla
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={onSend}
            disabled={send.isPending || !text.trim()}
            className="bg-emerald-700 text-white hover:bg-emerald-800 hover:text-white"
          >
            {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
            WhatsApp&apos;ta gönder
          </Button>
        </div>
      </div>
    </article>
  );
}
