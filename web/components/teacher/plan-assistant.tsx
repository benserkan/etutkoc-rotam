"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, MessageCircleQuestion, Send, Sparkles, UserRound, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  askPlanAssistant,
  getPlanAssistant,
  handoffPlanAssistant,
  planAssistantKeys,
  type PlanAssistantAction,
  type PlanAssistantMessage,
} from "@/lib/api/plan-assistant";
import { cn } from "@/lib/utils";

/**
 * Paket asistanı (2026-10-03) — /teacher/plan canlı yardım.
 * Hazır sorular hesabın gerçek durumundan ANINDA cevaplanır (yapay zekâsız);
 * serbest soru yapay zekâya gider; "Bize yaz" konuşmayı destek ekibine aktarır.
 * Mobilde alttan tam yükseklik sayfa, masaüstünde sağ altta panel.
 */

type Msg = PlanAssistantMessage & { action?: PlanAssistantAction | null; pending?: boolean };

export function PlanAssistant({
  open,
  onOpenChange,
  onSelectPlan,
  onOpenSection,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onSelectPlan: (code: string) => void;
  onOpenSection: (section: "ai" | "cancel") => void;
}) {
  return (
    <>
      {!open ? (
        <button
          type="button"
          onClick={() => onOpenChange(true)}
          className="fixed bottom-5 right-4 z-40 flex size-14 items-center justify-center gap-2 rounded-full bg-cyan-700 text-sm font-semibold text-white shadow-lg ring-4 ring-background transition hover:bg-cyan-800 focus-visible:outline-none focus-visible:ring-cyan-400 sm:bottom-6 sm:right-6 sm:size-auto sm:px-5 sm:py-3"
          aria-label="Paket asistanını aç"
        >
          <MessageCircleQuestion className="size-6 sm:size-5" aria-hidden />
          <span className="hidden sm:inline">Yardım</span>
        </button>
      ) : null}
      {open ? (
        <Panel
          onClose={() => onOpenChange(false)}
          onSelectPlan={(c) => {
            onSelectPlan(c);
            onOpenChange(false);
          }}
          onOpenSection={(s) => {
            onOpenSection(s);
            onOpenChange(false);
          }}
        />
      ) : null}
    </>
  );
}

function Panel({
  onClose,
  onSelectPlan,
  onOpenSection,
}: {
  onClose: () => void;
  onSelectPlan: (code: string) => void;
  onOpenSection: (section: "ai" | "cancel") => void;
}) {
  const stateQ = useQuery({
    queryKey: planAssistantKeys.state(),
    queryFn: getPlanAssistant,
    staleTime: 30_000,
  });
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [usedChips, setUsedChips] = React.useState<Set<string>>(() => new Set());
  const [handoff, setHandoff] = React.useState(false);
  const [handoffText, setHandoffText] = React.useState("");
  const [handoffDone, setHandoffDone] = React.useState<string | null>(null);
  const [left, setLeft] = React.useState<number | null>(null);
  const endRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, handoff, handoffDone]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const history = (): PlanAssistantMessage[] =>
    msgs.filter((m) => !m.pending).map((m) => ({ role: m.role, text: m.text }));

  // eslint-disable-next-line lgs/missing-invalidate -- salt soru-cevap; sunucu durumu değişmez
  const ask = useMutation({
    mutationFn: (b: { chip?: string; question?: string; label: string }) =>
      askPlanAssistant({ chip: b.chip, question: b.question, history: history() }),
    onMutate: (b) => {
      setMsgs((m) => [...m, { role: "user", text: b.label }, { role: "assistant", text: "", pending: true }]);
    },
    onSuccess: (res) => {
      setLeft(res.daily_left);
      setMsgs((m) => [
        ...m.filter((x) => !x.pending),
        { role: "assistant", text: res.answer, action: res.action },
      ]);
    },
    onError: () => {
      setMsgs((m) => [
        ...m.filter((x) => !x.pending),
        {
          role: "assistant",
          text: "Bağlantıda bir sorun oldu. Tekrar dene ya da 'Bize yaz' ile ekibimize ilet.",
          action: { type: "handoff", label: "Bize yaz" },
        },
      ]);
    },
  });

  // eslint-disable-next-line lgs/missing-invalidate -- destek talebi; plan durumu değişmez
  const send = useMutation({
    mutationFn: () => handoffPlanAssistant({ message: handoffText.trim(), transcript: history() }),
    onSuccess: (res) => {
      setHandoffDone(res.message);
      setHandoff(false);
      setHandoffText("");
    },
  });

  const chips = (stateQ.data?.chips ?? []).filter((c) => !usedChips.has(c.id));
  const busy = ask.isPending;
  const dailyLeft = left ?? stateQ.data?.daily_left ?? null;

  function onAction(a: PlanAssistantAction) {
    if (a.type === "select_plan" && a.plan) onSelectPlan(a.plan);
    else if (a.type === "open" && a.section) onOpenSection(a.section);
    else if (a.type === "handoff") setHandoff(true);
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    ask.mutate({ question: q, label: q });
  }

  return (
    <div
      role="dialog"
      aria-label="Paket asistanı"
      className={cn(
        "fixed z-50 flex flex-col overflow-hidden border border-border bg-background shadow-2xl",
        "inset-x-0 bottom-0 h-[88dvh] rounded-t-2xl",
        "sm:inset-x-auto sm:bottom-5 sm:right-5 sm:h-[600px] sm:max-h-[85dvh] sm:w-[400px] sm:rounded-2xl",
      )}
    >
      <header className="flex items-center gap-3 border-b border-border bg-cyan-700 px-4 py-3 text-white">
        <span className="flex size-9 items-center justify-center rounded-full bg-white/15">
          <Sparkles className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Paket asistanı</p>
          <p className="flex items-center gap-1.5 text-xs text-cyan-100">
            <span className="size-2 rounded-full bg-emerald-400" aria-hidden />
            Hazır sorulara anında cevap
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full p-1.5 hover:bg-white/15"
          aria-label="Asistanı kapat"
        >
          <X className="size-5" aria-hidden />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {stateQ.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Hazırlanıyor…
          </p>
        ) : stateQ.data ? (
          <Bubble role="assistant" text={stateQ.data.greeting} />
        ) : (
          <Bubble role="assistant" text="Merhaba! Paket, ödeme ya da kredi hakkında ne sormak istersin?" />
        )}

        {msgs.map((m, i) => (
          <div key={i} className="space-y-2">
            {m.pending ? (
              <div className="flex w-fit items-center gap-2 rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Düşünüyor…
              </div>
            ) : (
              <Bubble role={m.role} text={m.text} />
            )}
            {m.action && m.action.label ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="ml-0 border-cyan-600 text-cyan-800 hover:bg-cyan-50 dark:text-cyan-200 dark:hover:bg-cyan-500/10"
                onClick={() => onAction(m.action!)}
              >
                {m.action.label}
              </Button>
            ) : null}
          </div>
        ))}

        {handoffDone ? (
          <div className="rounded-xl bg-emerald-600 px-3.5 py-3 text-sm text-white">{handoffDone}</div>
        ) : null}

        {handoff ? (
          <div className="space-y-2 rounded-xl border border-border bg-card p-3">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
              <UserRound className="size-4" aria-hidden /> Ekibimize yaz
            </p>
            <p className="text-xs text-muted-foreground">
              Bu konuşma da mesajınla birlikte iletilir. Cevabı Destek sayfandan takip edersin.
            </p>
            <textarea
              value={handoffText}
              onChange={(e) => setHandoffText(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Sorununu kısaca anlat…"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
            />
            {send.isError ? (
              <p className="text-xs text-rose-700 dark:text-rose-300">Gönderilemedi, tekrar dene.</p>
            ) : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => setHandoff(false)}>
                Vazgeç
              </Button>
              <Button
                type="button"
                size="sm"
                className="bg-cyan-700 text-white hover:bg-cyan-800"
                disabled={handoffText.trim().length < 3 || send.isPending}
                onClick={() => send.mutate()}
              >
                {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Gönder
              </Button>
            </div>
          </div>
        ) : null}

        {chips.length > 0 && !busy ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {chips.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  if (c.id === "human") {
                    setHandoff(true);
                    setUsedChips((s) => new Set(s).add(c.id));
                    return;
                  }
                  setUsedChips((s) => new Set(s).add(c.id));
                  ask.mutate({ chip: c.id, label: c.label });
                }}
                className="rounded-full border border-cyan-600/40 bg-background px-3 py-1.5 text-left text-sm text-cyan-800 transition hover:bg-cyan-50 dark:text-cyan-200 dark:hover:bg-cyan-500/10"
              >
                {c.label}
              </button>
            ))}
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="border-t border-border bg-background px-3 py-3">
        <div className="flex items-end gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            maxLength={800}
            placeholder="Sorunu yaz…"
            aria-label="Asistana soru"
            className="h-11 min-w-0 flex-1 rounded-full border border-input bg-background px-4 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
          />
          <Button
            type="submit"
            size="icon"
            className="size-11 shrink-0 rounded-full bg-cyan-700 text-white hover:bg-cyan-800"
            disabled={!input.trim() || busy}
            aria-label="Soruyu gönder"
          >
            <Send className="size-4" aria-hidden />
          </Button>
        </div>
        <p className="mt-1.5 px-1 text-[11px] text-muted-foreground">
          Yapay zekâ cevapları kredinden düşmez
          {dailyLeft != null ? ` · bugün ${dailyLeft} serbest soru hakkın var` : ""}.
        </p>
      </form>
    </div>
  );
}

function Bubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  return (
    <div className={cn("flex", role === "user" ? "justify-end" : "justify-start")}>
      <p
        className={cn(
          "max-w-[85%] whitespace-pre-line break-words rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
          role === "user"
            ? "rounded-br-md bg-cyan-700 text-white"
            : "rounded-bl-md bg-muted text-foreground",
        )}
      >
        {text}
      </p>
    </div>
  );
}
