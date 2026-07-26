"use client";

/**
 * Rota'ya Sor (P2) — veli yazılı sohbeti (Rota kartının sekmesi).
 *
 * Kredisiz kural-tabanlı karşılama + duruma göre hazır çipler; soru başına
 * 3 kredi (koç havuzundan, günde 10 soru). "Yorumla" çipleri P1 önbelleğine
 * köprü: kartın ilgili sekmesini açar — taze yorum varsa kredisiz.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Send } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  type ChatMessage,
  type CommentaryKind,
  type ParentChatResponse,
  askParentChat,
  getParentChat,
  parentChatKeys,
} from "@/lib/api/parent";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { cn } from "@/lib/utils";

function errMessage(e: unknown): string {
  const code = e instanceof ApiError ? (e.detail?.code ?? null) : null;
  if (code === "daily_limit_reached")
    return "Bugünlük soru hakkın doldu — yarın yeniden sorabilirsin.";
  if (code === "ai_credit_exhausted")
    return "Rota bu ay için dinlenmede — koçun yapay zekâ kotası doldu.";
  if (code === "ai_unavailable")
    return "Yapay zekâ servisi şu an kullanılamıyor, birkaç dakika sonra deneyin.";
  return e instanceof ApiError ? e.message : "Cevap alınamadı, tekrar deneyin.";
}

export function RotaChat({
  studentId,
  onOpenCommentary,
}: {
  studentId: number;
  /** "Yorumla" çipi → kartın Program/Denemeler sekmesine köprü (kredisiz). */
  onOpenCommentary: (kind: CommentaryKind) => void;
}) {
  const qc = useQueryClient();
  const [text, setText] = React.useState("");
  const [err, setErr] = React.useState<string | null>(null);
  const endRef = React.useRef<HTMLDivElement | null>(null);

  const q = useQuery({
    queryKey: parentChatKeys.thread(studentId),
    queryFn: () => getParentChat(studentId),
    staleTime: 15_000,
  });
  const data = q.data;

  // Yanıt yeni mesajları içerir → cache doğrudan güncellenir
  const askMut = useMutation({
    mutationFn: (message: string) => askParentChat(studentId, message),
    onMutate: () => setErr(null),
    onSuccess: (res) => {
      qc.setQueryData(
        parentChatKeys.thread(studentId),
        (prev: ParentChatResponse | undefined) =>
          prev
            ? {
                ...prev,
                messages: [...prev.messages, ...res.messages],
                daily_left: res.daily_left,
              }
            : prev,
      );
      setText("");
    },
    onError: (e) => {
      setErr(errMessage(e));
      // Sunucu kaydetmiş olabilir (dev proxy zaman aşımı: istemci hata görür,
      // backend geç bitirir) — anında + gecikmeli yeniden eşitle
      const inv = () =>
        void qc.invalidateQueries({ queryKey: parentChatKeys.thread(studentId) });
      inv();
      setTimeout(inv, 8000);
      setTimeout(inv, 20000);
    },
  });

  const messages: ChatMessage[] = data?.messages ?? [];

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length, askMut.isPending]);

  function send(message: string) {
    const m = message.trim();
    if (m.length < 2 || askMut.isPending) return;
    askMut.mutate(m);
  }

  function onChip(action: "ask" | "commentary", payload: string) {
    if (action === "commentary") {
      onOpenCommentary(payload as CommentaryKind);
      return;
    }
    send(payload);
  }

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground">Yükleniyor…</p>;
  }
  if (data && !data.ai_available) {
    return (
      <p className="text-sm text-slate-700 dark:text-slate-300">
        {data.unavailable_reason ?? "Rota sohbeti şu an kullanılamıyor."}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Mesajlar + karşılama */}
      <div className="max-h-80 space-y-2.5 overflow-y-auto pr-1">
        {data?.greeting ? (
          <div className="flex items-start gap-2">
            <GuideAvatar size={28} speaking={false} />
            <div className="rounded-2xl rounded-tl-sm border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-800 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-200">
              {data.greeting.text}
            </div>
          </div>
        ) : null}
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex items-start gap-2",
              m.role === "veli" && "justify-end",
            )}
          >
            {m.role === "rota" ? <GuideAvatar size={28} speaking={false} /> : null}
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
                m.role === "veli"
                  ? "rounded-tr-sm bg-cyan-600 text-white"
                  : "rounded-tl-sm border border-cyan-200 bg-white text-slate-800 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-200",
              )}
            >
              {m.body}
            </div>
          </div>
        ))}
        {askMut.isPending ? (
          <div className="flex items-start gap-2">
            <GuideAvatar size={28} speaking />
            <div className="rounded-2xl rounded-tl-sm border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-500 dark:border-cyan-500/30 dark:bg-slate-900">
              <RefreshCw className="mr-1.5 inline size-3.5 animate-spin" aria-hidden />
              Rota düşünüyor…
            </div>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      {/* Hazır çipler */}
      {data?.greeting?.chips?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {data.greeting.chips.map((c) => (
            <button
              key={c.id}
              type="button"
              disabled={askMut.isPending}
              onClick={() => onChip(c.action, c.payload)}
              className="rounded-full border border-cyan-300 bg-white px-3 py-1 text-xs font-medium text-cyan-800 hover:bg-cyan-50 disabled:opacity-50 dark:border-cyan-500/40 dark:bg-slate-900 dark:text-cyan-200"
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : null}

      {/* Giriş */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
        className="flex items-center gap-2"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Rota'ya sor… (örn. Programa uyuyor mu?)"
          maxLength={500}
          disabled={askMut.isPending || (data?.daily_left ?? 0) <= 0}
          className="h-10 flex-1 rounded-xl border border-cyan-200 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-100"
        />
        <button
          type="submit"
          disabled={askMut.isPending || text.trim().length < 2}
          className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-cyan-600 px-4 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
        >
          <Send className="size-4" aria-hidden />
          Sor
        </button>
      </form>

      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground">
          Rota yalnız çocuğunun verilerine dayanır; koçun özel notları görülmez.
        </p>
        <p className="text-[11px] tabular-nums text-muted-foreground">
          Bugün kalan soru: {data?.daily_left ?? 0}
        </p>
      </div>

      {err ? (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
          {err}
        </p>
      ) : null}
    </div>
  );
}
