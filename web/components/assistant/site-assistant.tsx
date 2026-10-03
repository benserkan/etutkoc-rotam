"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, Loader2, MessageCircle, Send, Sparkles, UserRound, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { ApiError } from "@/lib/api";
import {
  askAssistant,
  assistantKeys,
  getAssistantState,
  handoffAssistant,
  ROTA_OPEN,
  ROTA_OPEN_SECTION,
  ROTA_SELECT_PLAN,
  type AssistantAction,
  type AssistantMessage,
} from "@/lib/api/site-assistant";
import { cn } from "@/lib/utils";

/**
 * Rota — sitenin her yerinde TEK yapay zekâ asistanı (2026-10-03).
 * Ziyaretçi dahil herkes kullanır; bilgisi role ve bulunulan sayfaya göre
 * değişir. Hazır sorular anında (yapay zekâsız), serbest sorular yapay
 * zekâyla cevaplanır; çözemezse "Ekibe yaz" ya da WhatsApp.
 * Konuşma sayfa geçişlerinde ve sayfa yenilemede (sekme açık kaldıkça) korunur.
 */

type Msg = AssistantMessage & { action?: AssistantAction | null; pending?: boolean };

const KEY_STORE = "rota-asistan-key";
const CHAT_STORE = "rota-asistan-chat";
const NUDGE_STORE = "rota-asistan-nudge";

function readKey(): string {
  if (typeof window === "undefined") return "";
  try {
    const k = window.localStorage.getItem(KEY_STORE);
    if (k && /^[A-Za-z0-9_-]{8,64}$/.test(k)) return k;
    const n = `v${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`.slice(0, 40);
    window.localStorage.setItem(KEY_STORE, n);
    return n;
  } catch {
    return `v${Math.random().toString(36).slice(2, 14)}x`;
  }
}

function readChat(): Msg[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(CHAT_STORE);
    const arr = raw ? (JSON.parse(raw) as Msg[]) : [];
    return Array.isArray(arr) ? arr.filter((m) => !m.pending).slice(-30) : [];
  } catch {
    return [];
  }
}

function hiddenOn(path: string): boolean {
  return path.includes("/print") || /\/guide(\/|$)/.test(path);
}

export function SiteAssistant() {
  const pathname = usePathname() || "/";
  const [open, setOpen] = React.useState(false);
  const [pendingQ, setPendingQ] = React.useState<{ question: string; chip?: string } | null>(null);
  const [nudge, setNudge] = React.useState(false);

  React.useEffect(() => {
    const onOpen = (e: Event) => {
      const d = (e as CustomEvent<{ question?: string; chip?: string }>).detail;
      setOpen(true);
      setNudge(false);
      if (d?.question) setPendingQ({ question: d.question, chip: d.chip });
    };
    window.addEventListener(ROTA_OPEN, onOpen);
    return () => window.removeEventListener(ROTA_OPEN, onOpen);
  }, []);

  // Fiyat sayfasında ziyaretçiye bir kez "yardım edeyim mi?" baloncuğu.
  React.useEffect(() => {
    if (!pathname.startsWith("/pricing")) return;
    let seen = false;
    try {
      seen = window.sessionStorage.getItem(NUDGE_STORE) === "1";
    } catch {
      seen = true;
    }
    if (seen) return;
    const t = window.setTimeout(() => {
      setNudge(true);
      try {
        window.sessionStorage.setItem(NUDGE_STORE, "1");
      } catch {
        /* yok say */
      }
    }, 15_000);
    return () => window.clearTimeout(t);
  }, [pathname]);

  if (hiddenOn(pathname)) return null;
  const lift = pathname === "/" ? "bottom-24 sm:bottom-6" : "bottom-5 sm:bottom-6";

  return (
    <>
      {!open ? (
        <div className={cn("fixed right-4 z-40 flex flex-col items-end gap-2 sm:right-6", lift)}>
          {nudge ? (
            <div className="relative max-w-[16rem] rounded-2xl rounded-br-md border border-border bg-card px-4 py-3 text-sm text-foreground shadow-lg">
              <button
                type="button"
                onClick={() => setNudge(false)}
                className="absolute right-1.5 top-1.5 rounded-full p-1 text-muted-foreground hover:bg-muted"
                aria-label="Kapat"
              >
                <X className="size-3.5" aria-hidden />
              </button>
              <p className="pr-4">Paket seçmene yardım edeyim mi? Kaç öğrencinle çalıştığını söylemen yeter.</p>
              <button
                type="button"
                onClick={() => {
                  setNudge(false);
                  setOpen(true);
                }}
                className="mt-2 font-semibold text-cyan-800 hover:underline dark:text-cyan-300"
              >
                Rota&apos;ya sor
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setOpen(true);
              setNudge(false);
            }}
            className="flex items-center gap-2 rounded-full bg-cyan-700 py-1.5 pl-1.5 pr-4 text-sm font-semibold text-white shadow-lg ring-4 ring-background transition hover:bg-cyan-800 focus-visible:outline-none focus-visible:ring-cyan-400"
            aria-label="Rota asistanını aç"
          >
            <GuideAvatar size={34} />
            <span>Rota&apos;ya sor</span>
          </button>
        </div>
      ) : (
        <Panel
          pathname={pathname}
          onClose={() => setOpen(false)}
          initialQuestion={pendingQ}
          onConsumeQuestion={() => setPendingQ(null)}
        />
      )}
    </>
  );
}

function Panel({
  pathname,
  onClose,
  initialQuestion,
  onConsumeQuestion,
}: {
  pathname: string;
  onClose: () => void;
  initialQuestion: { question: string; chip?: string } | null;
  onConsumeQuestion: () => void;
}) {
  const router = useRouter();
  const [sessionKey] = React.useState(readKey);
  const stateQ = useQuery({
    queryKey: assistantKeys.state(pathname),
    queryFn: () => getAssistantState(pathname, sessionKey),
    enabled: !!sessionKey,
    staleTime: 60_000,
  });
  const [msgs, setMsgs] = React.useState<Msg[]>(readChat);
  const [input, setInput] = React.useState("");
  const [usedChips, setUsedChips] = React.useState<Set<string>>(() => new Set());
  const [handoff, setHandoff] = React.useState(false);
  const [done, setDone] = React.useState<{ message: string; wa: string } | null>(null);
  const [left, setLeft] = React.useState<number | null>(null);
  const [form, setForm] = React.useState({ message: "", name: "", phone: "", email: "", website: "" });
  const endRef = React.useRef<HTMLDivElement>(null);
  const asked = React.useRef(false);

  React.useEffect(() => {
    try {
      window.sessionStorage.setItem(CHAT_STORE, JSON.stringify(msgs.filter((m) => !m.pending).slice(-30)));
    } catch {
      /* yok say */
    }
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, handoff, done]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const history = (): AssistantMessage[] =>
    msgs.filter((m) => !m.pending).map((m) => ({ role: m.role, text: m.text }));

  // eslint-disable-next-line lgs/missing-invalidate -- salt soru-cevap; sunucu durumu değişmez
  const ask = useMutation({
    mutationFn: (b: { chip?: string; question?: string; label: string }) =>
      askAssistant({
        session_key: sessionKey,
        page: pathname,
        chip: b.chip,
        label: b.label,
        question: b.question,
        history: history(),
      }),
    onMutate: (b) => {
      setMsgs((m) => [...m, { role: "user", text: b.label }, { role: "assistant", text: "", pending: true }]);
    },
    onSuccess: (res) => {
      setLeft(res.ai_left);
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", text: res.answer, action: res.action }]);
    },
    onError: (err) => {
      const text =
        err instanceof ApiError && err.status === 429
          ? err.message
          : "Bağlantıda bir sorun oldu. Tekrar dene ya da ekibimize yaz.";
      setMsgs((m) => [
        ...m.filter((x) => !x.pending),
        { role: "assistant", text, action: { type: "handoff", label: "Ekibe yaz" } },
      ]);
    },
  });

  // Başka bir sayfadan "asistana sor" ile gelen soru.
  React.useEffect(() => {
    if (initialQuestion && !asked.current && sessionKey) {
      asked.current = true;
      onConsumeQuestion();
      ask.mutate(
        initialQuestion.chip
          ? { chip: initialQuestion.chip, label: initialQuestion.question }
          : { question: initialQuestion.question, label: initialQuestion.question },
      );
    }
  }, [initialQuestion, sessionKey, onConsumeQuestion, ask]);

  const data = stateQ.data;
  const loggedIn = data?.logged_in ?? false;

  // eslint-disable-next-line lgs/missing-invalidate -- talep oluşturur; asistan durumu değişmez
  const send = useMutation({
    mutationFn: () =>
      handoffAssistant({
        session_key: sessionKey,
        page: pathname,
        message: form.message.trim(),
        transcript: history(),
        ...(loggedIn
          ? {}
          : {
              name: form.name.trim(),
              phone: form.phone.trim() || undefined,
              email: form.email.trim() || undefined,
              website: form.website || undefined,
            }),
      }),
    onSuccess: (res) => {
      setDone({ message: res.message, wa: res.whatsapp_url });
      setHandoff(false);
      setForm((f) => ({ ...f, message: "" }));
    },
  });

  const lastQuestion = [...msgs].reverse().find((m) => m.role === "user")?.text ?? "";
  const waNumber = data?.whatsapp ?? "905056738561";
  const waUrl = `https://wa.me/${waNumber}?text=${encodeURIComponent(
    `Merhaba, ETÜTKOÇ Rotam hakkında yazıyorum.${lastQuestion ? ` ${lastQuestion}` : ""}`,
  )}`;

  const chips = (data?.chips ?? []).filter((c) => !usedChips.has(c.id));
  const busy = ask.isPending;
  const aiLeft = left ?? data?.ai_left ?? null;

  function onAction(a: AssistantAction) {
    const mobile = typeof window !== "undefined" && window.innerWidth < 640;
    if (a.type === "handoff") {
      setHandoff(true);
      return;
    }
    if (a.type === "link" && a.href) {
      router.push(a.href);
      if (mobile) onClose();
      return;
    }
    if (a.type === "select_plan" && a.plan) {
      if (pathname.startsWith("/teacher/plan")) {
        window.dispatchEvent(new CustomEvent(ROTA_SELECT_PLAN, { detail: { plan: a.plan } }));
      } else {
        router.push(`/teacher/plan?plan=${encodeURIComponent(a.plan)}`);
      }
      onClose();
      return;
    }
    if (a.type === "open" && a.section) {
      if (pathname.startsWith("/teacher/plan")) {
        window.dispatchEvent(new CustomEvent(ROTA_OPEN_SECTION, { detail: { section: a.section } }));
      } else {
        router.push("/teacher/plan");
      }
      onClose();
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const q = input.trim();
    if (!q || busy) return;
    setInput("");
    ask.mutate({ question: q, label: q });
  }

  const sendErr = send.error instanceof ApiError ? send.error.message : send.isError ? "Gönderilemedi, tekrar dene." : null;
  const formOk =
    form.message.trim().length >= 3 &&
    (loggedIn || (form.name.trim().length >= 2 && (form.phone.trim() || form.email.trim())));

  return (
    <div
      role="dialog"
      aria-label="Rota asistanı"
      className={cn(
        "fixed z-50 flex flex-col overflow-hidden border border-border bg-background shadow-2xl",
        "inset-x-0 bottom-0 h-[88dvh] rounded-t-2xl",
        "sm:inset-x-auto sm:bottom-5 sm:right-5 sm:h-[620px] sm:max-h-[85dvh] sm:w-[410px] sm:rounded-2xl",
      )}
    >
      <header className="flex items-center gap-3 bg-cyan-800 px-4 py-3 text-white">
        <GuideAvatar size={40} speaking={busy} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Rota · ETÜTKOÇ asistanı</p>
          <p className="flex items-center gap-1.5 text-xs text-cyan-100">
            <Sparkles className="size-3.5" aria-hidden /> Yapay zekâ destekli
          </p>
        </div>
        <a
          href={waUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold hover:bg-white/25"
          aria-label="WhatsApp'tan yaz"
        >
          <MessageCircle className="size-4" aria-hidden />
          WhatsApp
        </a>
        <button type="button" onClick={onClose} className="rounded-full p-1.5 hover:bg-white/15" aria-label="Asistanı kapat">
          <X className="size-5" aria-hidden />
        </button>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        {stateQ.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Hazırlanıyor
          </p>
        ) : (
          <Bubble role="assistant" text={data?.greeting ?? "Merhaba! Sistemle ilgili ne sormak istersin?"} />
        )}

        {msgs.map((m, i) => (
          <div key={i} className="space-y-2">
            {m.pending ? (
              <div className="flex w-fit items-center gap-2 rounded-2xl rounded-bl-md bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Düşünüyor
              </div>
            ) : (
              <Bubble role={m.role} text={m.text} />
            )}
            {m.action && m.action.label ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="border-cyan-600 text-cyan-800 hover:bg-cyan-50 dark:text-cyan-200 dark:hover:bg-cyan-500/10"
                onClick={() => onAction(m.action!)}
              >
                {m.action.label}
              </Button>
            ) : null}
          </div>
        ))}

        {done ? (
          <div className="space-y-2 rounded-xl bg-emerald-600 px-3.5 py-3 text-sm text-white">
            <p className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden />
              {done.message}
            </p>
            <a
              href={done.wa}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-50"
            >
              <MessageCircle className="size-4" aria-hidden /> Acelen varsa WhatsApp&apos;tan da yaz
            </a>
          </div>
        ) : null}

        {handoff ? (
          <div className="space-y-2 rounded-xl border border-border bg-card p-3">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
              <UserRound className="size-4" aria-hidden /> Ekibimize yaz
            </p>
            <p className="text-xs text-muted-foreground">
              Bu konuşma da mesajınla birlikte iletilir.
              {loggedIn ? " Cevabı hesabındaki Destek sayfasından ya da e-postadan alırsın." : " Sana telefonla ya da e-postayla döneriz."}
            </p>
            {!loggedIn ? (
              <div className="grid gap-2 sm:grid-cols-2">
                <Field label="Adın" value={form.name} onChange={(v) => setForm((f) => ({ ...f, name: v }))} autoComplete="name" />
                <Field
                  label="Cep telefonun"
                  value={form.phone}
                  onChange={(v) => setForm((f) => ({ ...f, phone: v }))}
                  autoComplete="tel"
                  inputMode="tel"
                  placeholder="05XX XXX XX XX"
                />
                <div className="sm:col-span-2">
                  <Field
                    label="E-posta (isteğe bağlı)"
                    value={form.email}
                    onChange={(v) => setForm((f) => ({ ...f, email: v }))}
                    autoComplete="email"
                    inputMode="email"
                  />
                </div>
                <input
                  tabIndex={-1}
                  autoComplete="off"
                  value={form.website}
                  onChange={(e) => setForm((f) => ({ ...f, website: e.target.value }))}
                  className="hidden"
                  aria-hidden
                />
              </div>
            ) : null}
            <textarea
              value={form.message}
              onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
              rows={3}
              maxLength={2000}
              placeholder="Ne konuda yardım istediğini kısaca yaz"
              aria-label="Mesajın"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
            />
            {sendErr ? <p className="text-xs text-rose-700 dark:text-rose-300">{sendErr}</p> : null}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <a
                href={waUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 hover:underline dark:text-emerald-300"
              >
                <MessageCircle className="size-4" aria-hidden /> WhatsApp&apos;tan yaz
              </a>
              <div className="flex gap-2">
                <Button type="button" variant="ghost" size="sm" onClick={() => setHandoff(false)}>
                  Vazgeç
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="bg-cyan-700 text-white hover:bg-cyan-800"
                  disabled={!formOk || send.isPending}
                  onClick={() => send.mutate()}
                >
                  {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                  Gönder
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {chips.length > 0 && !busy && !handoff ? (
          <div className="flex flex-wrap gap-2 pt-1">
            {chips.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setUsedChips((s) => new Set(s).add(c.id));
                  if (c.id === "human") {
                    setHandoff(true);
                    return;
                  }
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
            placeholder="Sorunu yaz"
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
        <p className="mt-1.5 px-1 text-[11px] leading-snug text-muted-foreground">
          {aiLeft != null ? `Bugün ${aiLeft} serbest soru hakkın var · ` : ""}
          Yapay zekâ yanılabilir; önemli konularda ekibe yaz. Sorular hizmeti iyileştirmek için saklanır.
        </p>
      </form>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  ...rest
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  return (
    <label className="block text-xs text-muted-foreground">
      {label}
      <input
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 h-9 w-full rounded-lg border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
      />
    </label>
  );
}

function Bubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  return (
    <div className={cn("flex", role === "user" ? "justify-end" : "justify-start")}>
      <p
        className={cn(
          "max-w-[85%] whitespace-pre-line break-words rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
          role === "user" ? "rounded-br-md bg-cyan-700 text-white" : "rounded-bl-md bg-muted text-foreground",
        )}
      >
        {text}
      </p>
    </div>
  );
}
