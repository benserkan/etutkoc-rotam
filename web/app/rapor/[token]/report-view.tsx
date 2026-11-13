"use client";

import * as React from "react";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Download, Loader2, Pause, Play } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ExamReportSubject {
  name: string;
  questions: number;
  correct: number;
  wrong: number;
  blank: number;
  net_text: string;
  pct: number;
  level: "strong" | "ok" | "support";
  level_label: string;
  sentence: string;
}

export interface ExamReport {
  student_first: string;
  student_gen: string;
  exam_title: string;
  exam_date_tr: string;
  section_label: string | null;
  brand_name: string;
  brand_logo_url: string | null;
  coach_name: string | null;
  net_text: string;
  correct: number;
  wrong: number;
  blank: number;
  total_questions: number;
  correct_pct: number;
  headline: string;
  trend_text: string;
  delta_direction: "up" | "down" | "flat" | null;
  prev_net_text: string | null;
  narrative: string[];
  explain: string;
  subjects: ExamReportSubject[];
  history: {
    has_data: boolean;
    exams: { title: string; date_tr: string; net_text: string; is_current: boolean }[];
    rows: { subject: string; nets: (string | null)[]; direction: string | null }[];
    totals: string[];
  };
  opportunities: { subject: string; topic: string; gain_text: string }[];
  opportunity_total_text: string | null;
  opportunity_exam_count: number;
  tips: string[];
  speech_text: string;
  voice_available: boolean;
  voice_ready: boolean;
  expires_at: string;
}

const LEVEL_TONE: Record<ExamReportSubject["level"], { chip: string; bar: string }> = {
  strong: { chip: "bg-emerald-700 text-white", bar: "bg-emerald-600" },
  ok: { chip: "bg-amber-600 text-white", bar: "bg-amber-500" },
  support: { chip: "bg-rose-700 text-white", bar: "bg-rose-500" },
};

export function ReportView({ token, report: r }: { token: string; report: ExamReport }) {
  const base = `/api/v2/public/exam-report/${encodeURIComponent(token)}`;
  const TrendIcon = r.delta_direction === "up" ? ArrowUpRight : r.delta_direction === "down" ? ArrowDownRight : ArrowRight;

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

        <h1 className="text-2xl font-extrabold leading-tight">{r.student_gen} deneme raporu</h1>
        <p className="mt-1 text-sm text-slate-600">
          {r.exam_title} · {r.exam_date_tr}
          {r.section_label ? ` · ${r.section_label}` : ""}
        </p>

        {/* Özet */}
        <section className="mt-4 rounded-2xl bg-cyan-800 p-5 text-white">
          <p className="text-4xl font-extrabold tabular-nums">{r.net_text} <span className="text-xl font-bold">net</span></p>
          <p className="mt-2 text-base leading-snug">{r.headline}</p>
          <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-sm font-semibold">
            <TrendIcon className="size-4" aria-hidden />
            {r.trend_text}
            {r.prev_net_text ? ` (önceki ${r.prev_net_text} net)` : ""}
          </p>
          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <Stat label="Doğru" value={r.correct} />
            <Stat label="Yanlış" value={r.wrong} />
            <Stat label="Boş" value={r.blank} />
          </div>
        </section>

        <VoiceCard base={base} report={r} />

        {r.narrative.length ? (
          <Section title="Kısaca">
            <ul className="space-y-2">
              {r.narrative.map((line, i) => (
                <li key={i} className="flex gap-2 text-[15px] leading-relaxed">
                  <span className="mt-2 size-1.5 shrink-0 rounded-full bg-cyan-700" aria-hidden />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {r.subjects.length ? (
          <Section title="Ders ders" note="Her derste doğru yaptığı soruların oranı.">
            <ul className="space-y-3">
              {r.subjects.map((s) => (
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
                  <p className="mt-1 text-xs text-slate-500">
                    {s.correct} doğru · {s.wrong} yanlış · {s.blank} boş · {s.net_text} net
                  </p>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {r.history.has_data ? (
          <Section title="Önceki denemelerle karşılaştırma" note="Aynı türdeki son denemelerin ders netleri.">
            <div className="relative overflow-x-auto rounded-xl border border-slate-300 bg-white">
              <table className="w-full min-w-[420px] text-sm">
                <thead>
                  <tr className="bg-slate-100 text-left">
                    <th className="px-3 py-2 font-semibold">Ders</th>
                    {r.history.exams.map((e, i) => (
                      <th key={i} className={cn("px-3 py-2 text-right font-semibold", e.is_current && "text-cyan-800")}>
                        {e.date_tr}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {r.history.rows.map((row) => (
                    <tr key={row.subject} className="border-t border-slate-200">
                      <td className="px-3 py-2">{row.subject}</td>
                      {row.nets.map((v, i) => (
                        <td key={i} className="px-3 py-2 text-right tabular-nums">{v ?? "—"}</td>
                      ))}
                    </tr>
                  ))}
                  <tr className="border-t border-slate-300 font-bold">
                    <td className="px-3 py-2">Toplam net</td>
                    {r.history.totals.map((t, i) => (
                      <td key={i} className="px-3 py-2 text-right tabular-nums">{t}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </Section>
        ) : null}

        {r.opportunities.length ? (
          <Section
            title="Nerede net kazanabilir?"
            note={`${r.opportunity_exam_count > 1 ? `Son ${r.opportunity_exam_count} denemeye göre` : "Bu denemeye göre"}, bu konular kapandığında deneme başına kazanç.`}
          >
            <ul className="divide-y divide-slate-200 rounded-xl border border-slate-300 bg-white">
              {r.opportunities.map((o, i) => (
                <li key={i} className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
                  <span>
                    <span className="font-semibold">{o.topic}</span>
                    <span className="text-slate-500"> · {o.subject}</span>
                  </span>
                  <span className="shrink-0 font-bold text-emerald-700">+{o.gain_text} net</span>
                </li>
              ))}
              {r.opportunity_total_text ? (
                <li className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm font-bold">
                  <span>Hepsi kapanırsa</span>
                  <span className="text-emerald-700">+{r.opportunity_total_text} net</span>
                </li>
              ) : null}
            </ul>
          </Section>
        ) : null}

        <Section title="Evde nasıl destek olabilirsiniz?">
          <ul className="space-y-2">
            {r.tips.map((t, i) => (
              <li key={i} className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-[15px] leading-relaxed text-emerald-950">
                {t}
              </li>
            ))}
          </ul>
        </Section>

        <Section title="Net nasıl hesaplanır?">
          <p className="text-sm leading-relaxed text-slate-700">{r.explain}</p>
        </Section>

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

function Stat({ label, value }: { label: string; value: number }) {
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
