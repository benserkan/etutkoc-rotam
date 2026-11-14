"use client";

import * as React from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Download, Loader2, Pause, Play } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Tone = "strong" | "ok" | "support";

export type ReportSection =
  | { type: "bullets" | "tips"; title: string; note?: string; items: string[] }
  | { type: "text"; title: string; note?: string; text: string }
  | {
      type: "levels";
      title: string;
      note?: string;
      items: { name: string; pct: number; level: Tone; level_label: string; sentence: string; meta?: string }[];
    }
  | {
      type: "bars";
      title: string;
      note?: string;
      items: { label: string; value: string; pct: number; tone: "accent" | "neutral" }[];
    }
  | { type: "table"; title: string; note?: string; columns: string[]; rows: string[][]; total_row?: string[] }
  | {
      type: "gains";
      title: string;
      note?: string;
      items: { label: string; sub: string; value: string }[];
      total?: { label: string; value: string } | null;
    };

export interface ExamReport {
  kind: "exam" | "progress" | "weekly";
  title: string;
  subtitle: string;
  student_first: string;
  brand_name: string;
  brand_logo_url: string | null;
  coach_name: string | null;
  hero: {
    big: string;
    unit: string;
    headline: string;
    trend_text: string;
    trend_dir: "up" | "down" | "flat" | null;
    stats: { label: string; value: string }[];
  };
  sections: ReportSection[];
  speech_text: string;
  voice_available: boolean;
  voice_ready: boolean;
  expires_at: string;
}

const LEVEL_TONE: Record<Tone, { chip: string; bar: string }> = {
  strong: { chip: "bg-emerald-700 text-white", bar: "bg-emerald-600" },
  ok: { chip: "bg-amber-600 text-white", bar: "bg-amber-500" },
  support: { chip: "bg-rose-700 text-white", bar: "bg-rose-500" },
};

export function ReportView({ token, report: r }: { token: string; report: ExamReport }) {
  const base = `/api/v2/public/exam-report/${encodeURIComponent(token)}`;
  const h = r.hero;
  const TrendIcon = h.trend_dir === "up" ? ArrowUpRight : h.trend_dir === "down" ? ArrowDownRight : ArrowRight;

  return (
    <main className="force-light min-h-screen bg-slate-100 pb-16 text-slate-900">
      <div className="mx-auto max-w-2xl px-4">
        <header className="flex items-center gap-3 pt-6 pb-4">
          {r.brand_logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- kurum logosu (API, boyut bilinmiyor)
            <img src={r.brand_logo_url} alt="" className="h-9 w-auto max-w-[140px] object-contain" />
          ) : null}
          <p className="text-sm font-bold text-cyan-800">{r.brand_name}</p>
        </header>

        <h1 className="text-2xl font-extrabold leading-tight">{r.title}</h1>
        <p className="mt-1 text-sm text-slate-600">{r.subtitle}</p>

        <section className="mt-4 rounded-2xl bg-cyan-800 p-5 text-white">
          <p className="text-4xl font-extrabold tabular-nums">
            {h.big} {h.unit ? <span className="text-xl font-bold">{h.unit}</span> : null}
          </p>
          {h.headline ? <p className="mt-2 text-base leading-snug">{h.headline}</p> : null}
          {h.trend_text ? (
            <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-sm font-semibold">
              <TrendIcon className="size-4 shrink-0" aria-hidden />
              {h.trend_text}
            </p>
          ) : null}
          {h.stats.length ? (
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              {h.stats.map((s) => (
                <Stat key={s.label} label={s.label} value={s.value} />
              ))}
            </div>
          ) : null}
        </section>

        <VoiceCard base={base} report={r} />

        {r.sections.map((sec, i) => (
          <SectionView key={i} sec={sec} />
        ))}

        <a
          href={`${base}/pdf`}
          className="mt-8 flex h-12 items-center justify-center gap-2 rounded-xl bg-slate-900 font-semibold text-white"
        >
          <Download className="size-5" aria-hidden />
          Raporu PDF olarak indir
        </a>

        <p className="mt-6 text-center text-xs text-slate-500">
          {r.coach_name ? `Koç: ${r.coach_name} · ` : ""}Bu bağlantı{" "}
          {new Date(r.expires_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" })}{" "}
          tarihine kadar açık.
        </p>
      </div>
    </main>
  );
}

function SectionView({ sec }: { sec: ReportSection }) {
  let body: React.ReactNode = null;
  if (sec.type === "bullets") {
    body = (
      <ul className="space-y-2">
        {sec.items.map((line, i) => (
          <li key={i} className="flex gap-2 text-[15px] leading-relaxed">
            <span className="mt-2 size-1.5 shrink-0 rounded-full bg-cyan-700" aria-hidden />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    );
  } else if (sec.type === "tips") {
    body = (
      <ul className="space-y-2">
        {sec.items.map((t, i) => (
          <li key={i} className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-[15px] leading-relaxed text-emerald-950">
            {t}
          </li>
        ))}
      </ul>
    );
  } else if (sec.type === "text") {
    body = <p className="text-[15px] leading-relaxed text-slate-700">{sec.text}</p>;
  } else if (sec.type === "levels") {
    body = (
      <ul className="space-y-3">
        {sec.items.map((s) => (
          <li key={s.name} className="rounded-xl border border-slate-300 bg-white p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-bold">{s.name}</p>
              <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-bold", LEVEL_TONE[s.level].chip)}>
                {s.level_label}
              </span>
            </div>
            <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-200">
              <div className={cn("h-full rounded-full", LEVEL_TONE[s.level].bar)} style={{ width: `${s.pct}%` }} />
            </div>
            <p className="mt-2 text-sm text-slate-700">{s.sentence}</p>
            {s.meta ? <p className="mt-1 text-xs text-slate-500">{s.meta}</p> : null}
          </li>
        ))}
      </ul>
    );
  } else if (sec.type === "bars") {
    body = (
      <ul className="space-y-2 rounded-xl border border-slate-300 bg-white p-3">
        {sec.items.map((b, i) => (
          <li key={i}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="text-slate-700">{b.label}</span>
              <span className="shrink-0 font-bold tabular-nums">{b.value}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className={cn("h-full rounded-full", b.tone === "accent" ? "bg-cyan-700" : "bg-slate-400")}
                style={{ width: `${b.pct}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    );
  } else if (sec.type === "table") {
    body = (
      <div className="relative overflow-x-auto rounded-xl border border-slate-300 bg-white">
        <table className="w-full min-w-[320px] text-sm">
          <thead>
            <tr className="bg-slate-100 text-left">
              {sec.columns.map((c, i) => (
                <th key={i} className={cn("px-3 py-2 font-semibold", i > 0 && "text-right")}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sec.rows.map((row, ri) => (
              <tr key={ri} className="border-t border-slate-200">
                {row.map((v, i) => (
                  <td key={i} className={cn("px-3 py-2", i > 0 && "text-right tabular-nums")}>
                    {v}
                  </td>
                ))}
              </tr>
            ))}
            {sec.total_row ? (
              <tr className="border-t border-slate-300 font-bold">
                {sec.total_row.map((v, i) => (
                  <td key={i} className={cn("px-3 py-2", i > 0 && "text-right tabular-nums")}>
                    {v}
                  </td>
                ))}
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    );
  } else if (sec.type === "gains") {
    body = (
      <ul className="divide-y divide-slate-200 rounded-xl border border-slate-300 bg-white">
        {sec.items.map((o, i) => (
          <li key={i} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
            <span>
              <span className="font-semibold">{o.label}</span>
              <span className="text-slate-500"> · {o.sub}</span>
            </span>
            <span className="shrink-0 font-bold text-emerald-700">{o.value}</span>
          </li>
        ))}
        {sec.total ? (
          <li className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm font-bold">
            <span>{sec.total.label}</span>
            <span className="text-emerald-700">{sec.total.value}</span>
          </li>
        ) : null}
      </ul>
    );
  }
  return (
    <Section title={sec.title} note={sec.note}>
      {body}
    </Section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-white/10 py-2">
      <p className="text-xl font-extrabold tabular-nums">{value}</p>
      <p className="text-xs">{label}</p>
    </div>
  );
}

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="mt-7">
      <h2 className="text-lg font-bold">{title}</h2>
      {note ? <p className="mb-2 text-sm text-slate-600">{note}</p> : <div className="mb-2" />}
      {children}
    </section>
  );
}

type VoiceState = "idle" | "preparing" | "playing" | "paused";
type VoiceMode = "server" | "device";

/** Rota'nın sesi (sunucu, önbellekli); olmazsa telefonun kendi Türkçe sesi.
 *  iPhone, uzun bir bekleyişten sonra dokunma izni olmadan ses başlatmaz →
 *  hazırlık bitince çalmayı dener, olmazsa "dokunun" der (ikinci dokunuş anında çalar). */
function VoiceCard({ base, report }: { base: string; report: ExamReport }) {
  const [state, setState] = React.useState<VoiceState>("idle");
  const [note, setNote] = React.useState<string | null>(null);
  const [mode, setMode] = React.useState<VoiceMode | null>(
    report.voice_ready ? "server" : report.voice_available ? null : "device",
  );
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const active = React.useRef<VoiceMode | null>(null);

  React.useEffect(() => () => {
    audioRef.current?.pause();
    if (typeof window !== "undefined") window.speechSynthesis?.cancel();
  }, []);

  function playDevice() {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) {
      setNote("Bu cihaz sesli okumayı desteklemiyor.");
      setState("idle");
      return;
    }
    synth.cancel();
    const u = new SpeechSynthesisUtterance(report.speech_text);
    u.lang = "tr-TR";
    const tr = synth.getVoices().find((v) => v.lang?.toLowerCase().startsWith("tr"));
    if (tr) u.voice = tr;
    u.rate = 0.95;
    u.onend = () => setState("idle");
    u.onerror = () => setState("idle");
    active.current = "device";
    synth.speak(u);
    setState("playing");
  }

  function playServer(afterWait: boolean) {
    audioRef.current?.pause();
    const a = new Audio(`${base}/audio`);
    a.addEventListener("ended", () => setState("idle"));
    audioRef.current = a;
    active.current = "server";
    void a
      .play()
      .then(() => setState("playing"))
      .catch(() => {
        setState("idle");
        if (afterWait) setNote("Ses hazır — dinlemek için oynat düğmesine dokunun.");
        else {
          setMode("device");
          playDevice();
        }
      });
  }

  async function onPlay() {
    setNote(null);
    if (state === "playing") {
      if (active.current === "device") window.speechSynthesis?.pause();
      else audioRef.current?.pause();
      setState("paused");
      return;
    }
    if (state === "paused") {
      if (active.current === "device") window.speechSynthesis?.resume();
      else void audioRef.current?.play();
      setState("playing");
      return;
    }
    if (mode === "server") return playServer(false);
    if (mode === "device") return playDevice();
    setState("preparing");
    try {
      const data = await api<{ ready: boolean }>(`${base}/voice`, { method: "POST", _skipRefresh: true });
      if (data.ready) {
        setMode("server");
        playServer(true);
      } else {
        setMode("device");
        setState("idle");
        setNote("Dinlemek için oynat düğmesine dokunun.");
      }
    } catch {
      setMode("device");
      setState("idle");
      setNote("Dinlemek için oynat düğmesine dokunun.");
    }
  }

  return (
    <section className="mt-4 flex items-center gap-4 rounded-2xl border border-slate-300 bg-white p-4">
      {/* eslint-disable-next-line @next/next/no-img-element -- statik avatar */}
      <img
        src="/static/guide/rota-avatar.png"
        alt=""
        className={cn("size-14 shrink-0 rounded-full object-cover", state === "playing" && "ring-4 ring-cyan-500")}
      />
      <div className="min-w-0 flex-1">
        <p className="font-bold">Raporu dinleyin</p>
        <p className="text-sm text-slate-600">
          {state === "preparing"
            ? "Rota sesi hazırlıyor, yarım dakika kadar sürebilir…"
            : note ?? "Rota sonucu ve önerileri size sesli anlatsın."}
        </p>
      </div>
      <button
        type="button"
        onClick={onPlay}
        disabled={state === "preparing"}
        aria-label={state === "playing" ? "Duraklat" : "Dinle"}
        className="flex size-14 shrink-0 items-center justify-center rounded-full bg-cyan-700 text-white disabled:opacity-70"
      >
        {state === "preparing" ? (
          <Loader2 className="size-6 animate-spin" aria-hidden />
        ) : state === "playing" ? (
          <Pause className="size-6" aria-hidden />
        ) : (
          <Play className="size-6 translate-x-0.5" aria-hidden />
        )}
      </button>
    </section>
  );
}
