"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Atom,
  BookOpenText,
  Calculator,
  CalendarClock,
  Check,
  ChevronRight,
  GraduationCap,
  Info,
  Lightbulb,
  Loader2,
  Pencil,
  Plus,
  RotateCcw,
  Scale,
  ScrollText,
  Trash2,
  TrendingDown,
  TrendingUp,
  Trophy,
} from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ───────── Tipler (app/services/yks_public_sim.simulate yanıtı) ───────── */

type Field = "TYT" | "SAY" | "EA" | "SÖZ";

interface NowRow { score: number; rank: number | null; placement_score: number | null }
interface ForecastRow {
  score: { p10: number; p50: number; p90: number };
  rank: { best: number | null; p50: number | null; worst: number | null };
}
interface Lesson {
  key: string; label: string; max: number; current: number; predicted: number;
  p10: number; p90: number; weekly_trend: number; n: number;
}
interface SimResult {
  exam_date: string; exam_official: boolean; weeks_remaining: number;
  now: Record<string, NowRow>; forecast: Record<string, ForecastRow>;
  lessons: Lesson[]; warnings: string[]; n_denemeler: number; rank_year: number;
}

/* ───────── Testler ───────── */

interface Test { key: string; label: string; q: number }

const TYT_TESTS: Test[] = [
  { key: "tyt_trk", label: "Türkçe", q: 40 },
  { key: "tyt_sos", label: "Sosyal Bilimler", q: 20 },
  { key: "tyt_mat", label: "Temel Matematik", q: 40 },
  { key: "tyt_fen", label: "Fen Bilimleri", q: 20 },
];
const AYT_TESTS: Record<Exclude<Field, "TYT">, Test[]> = {
  SAY: [
    { key: "mat", label: "Matematik", q: 40 },
    { key: "fiz", label: "Fizik", q: 14 },
    { key: "kim", label: "Kimya", q: 13 },
    { key: "bio", label: "Biyoloji", q: 13 },
  ],
  EA: [
    { key: "mat", label: "Matematik", q: 40 },
    { key: "tde", label: "Türk Dili ve Edebiyatı", q: 24 },
    { key: "trh1", label: "Tarih-1", q: 10 },
    { key: "cog1", label: "Coğrafya-1", q: 6 },
  ],
  SÖZ: [
    { key: "tde", label: "Türk Dili ve Edebiyatı", q: 24 },
    { key: "trh1", label: "Tarih-1", q: 10 },
    { key: "cog1", label: "Coğrafya-1", q: 6 },
    { key: "trh2", label: "Tarih-2", q: 11 },
    { key: "cog2", label: "Coğrafya-2", q: 11 },
    { key: "fel", label: "Felsefe Grubu", q: 12 },
    { key: "din", label: "Din Kültürü", q: 6 },
  ],
};
const FIELDS: { key: Field; label: string; sub: string; icon: typeof Atom }[] = [
  { key: "SAY", label: "Sayısal", sub: "TYT + Matematik, Fen", icon: Atom },
  { key: "EA", label: "Eşit Ağırlık", sub: "TYT + Matematik, Edebiyat-Sosyal 1", icon: Scale },
  { key: "SÖZ", label: "Sözel", sub: "TYT + Edebiyat-Sosyal 1, Sosyal 2", icon: ScrollText },
  { key: "TYT", label: "Yalnız TYT", sub: "Türkçe, Sosyal, Matematik, Fen", icon: BookOpenText },
];
const FIELD_NAME: Record<string, string> = { TYT: "TYT", SAY: "Sayısal", EA: "Eşit Ağırlık", "SÖZ": "Sözel" };

function testsFor(field: Field) {
  return field === "TYT" ? TYT_TESTS : [...TYT_TESTS, ...AYT_TESTS[field]];
}

/* ───────── Yardımcılar ───────── */

const fmtInt = (n: number | null | undefined) => (n == null ? "—" : n.toLocaleString("tr-TR"));
const fmt1 = (n: number) => n.toLocaleString("tr-TR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt2 = (n: number) => n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function toNum(v: string): number | null {
  if (v.trim() === "") return null;
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function netOf(d: string, y: string): number | null {
  const dc = toNum(d);
  const yc = toNum(y);
  if (dc == null && yc == null) return null;
  return Math.max(0, (dc ?? 0) - (yc ?? 0) / 4);
}

const today = () => new Date().toISOString().slice(0, 10);

type DY = Record<string, { d: string; y: string }>;
interface PastDeneme { id: number; date: string; nets: Record<string, string> }

const inputCls =
  "h-11 w-full rounded-xl border border-slate-300 bg-white px-2 text-center text-base font-semibold text-slate-900 tabular-nums outline-none transition placeholder:font-normal placeholder:text-slate-400 focus:border-cyan-600 focus:ring-4 focus:ring-cyan-600/15";

type Step = 1 | 2 | 3 | 4;

const STEPS: { n: Step; label: string }[] = [
  { n: 1, label: "Puan türü" },
  { n: 2, label: "Netlerin" },
  { n: 3, label: "Ek bilgi" },
  { n: 4, label: "Sonuç" },
];

/** Üstteki adım çubuğu — tamamlanan adıma tıklayınca geri dönülür. */
function Stepper({ step, maxStep, onGo }: { step: Step; maxStep: Step; onGo: (s: Step) => void }) {
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Hesaplama adımları">
      {STEPS.map((s) => {
        const active = s.n === step;
        const done = s.n < step || (s.n <= maxStep && s.n !== step);
        const reachable = s.n <= maxStep && s.n !== step;
        return (
          <li key={s.n}>
            <button
              type="button"
              disabled={!reachable}
              onClick={() => onGo(s.n)}
              aria-current={active ? "step" : undefined}
              className="group flex w-full flex-col gap-2 text-left disabled:cursor-default"
            >
              <span className={cn("h-1.5 w-full rounded-full transition", active ? "bg-cyan-600" : done ? "bg-cyan-300" : "bg-slate-200")} />
              <span className="flex items-center gap-1.5">
                <span className={cn(
                  "flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                  active ? "bg-cyan-700 text-white" : done ? "bg-cyan-100 text-cyan-800" : "bg-slate-100 text-slate-500",
                )}>
                  {done && !active ? <Check className="size-3" aria-hidden /> : s.n}
                </span>
                <span className={cn(
                  "whitespace-nowrap text-xs font-semibold sm:text-sm",
                  !active && "hidden sm:inline",
                  active ? "text-slate-900" : done ? "text-slate-700 group-hover:text-cyan-800" : "text-slate-400",
                )}>
                  {s.label}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

/** Adımın içindeki kısa açıklama kutusu (formun yanında, o adıma özel). */
function Tip({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5 rounded-2xl bg-cyan-50 px-4 py-3 text-sm leading-relaxed text-cyan-950 ring-1 ring-cyan-100">
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-cyan-700" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function YksSimulator({ embedded = false }: { embedded?: boolean }) {
  const [step, setStep] = React.useState<Step>(1);
  const [maxStep, setMaxStep] = React.useState<Step>(1);
  const [field, setField] = React.useState<Field>("SAY");
  const [dy, setDy] = React.useState<DY>({});
  const [diploma, setDiploma] = React.useState("");
  const [past, setPast] = React.useState<PastDeneme[]>([]);
  const [result, setResult] = React.useState<SimResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  // Gömülü sürüm: kapsayan sayfaya (etutkoc.com) içerik yüksekliğini bildir → iframe boyu uyar.
  // Ölçü İÇERİĞİN kendisinden alınır: documentElement.scrollHeight iframe boyundan küçük
  // olamadığı için (iframe = yükseklik + pay) her turda büyüyen bir döngü kuruyordu.
  const rootRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    const el = rootRef.current;
    if (!embedded || !el || typeof window === "undefined" || window.parent === window) return;
    let last = 0;
    const post = () => {
      const h = Math.ceil(el.getBoundingClientRect().height);
      if (h === last) return;
      last = h;
      window.parent.postMessage({ type: "etutkoc-yks-height", height: h }, "*");
    };
    const ro = new ResizeObserver(post);
    ro.observe(el);
    post();
    return () => ro.disconnect();
  }, [embedded]);

  /** Adım değişince aracın başına dön; gömülüde kaydırmayı kapsayan sayfa yapar. */
  function goTo(s: Step) {
    setStep(s);
    setMaxStep((m) => (s > m ? s : m));
    setError(null);
    requestAnimationFrame(() => {
      if (embedded && window.parent !== window) window.parent.postMessage({ type: "etutkoc-yks-scrolltop" }, "*");
      else rootRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const tests = testsFor(field);
  const nets: Record<string, number> = {};
  for (const t of tests) {
    const n = netOf(dy[t.key]?.d ?? "", dy[t.key]?.y ?? "");
    if (n != null) nets[t.key] = n;
  }
  const aytTests = field === "TYT" ? [] : AYT_TESTS[field];
  const tytNet = TYT_TESTS.reduce((a, t) => a + (nets[t.key] ?? 0), 0);
  const aytNet = aytTests.reduce((a, t) => a + (nets[t.key] ?? 0), 0);
  const aytMax = aytTests.reduce((a, t) => a + t.q, 0);
  const filled = tests.filter((t) => t.key in nets).length;

  function setCell(key: string, part: "d" | "y", value: string) {
    setDy((prev) => ({ ...prev, [key]: { d: prev[key]?.d ?? "", y: prev[key]?.y ?? "", [part]: value } }));
    setResult(null);
    setError(null);
  }

  function validateNets(): string | null {
    for (const t of tests) {
      const c = dy[t.key];
      const d = toNum(c?.d ?? "") ?? 0;
      const y = toNum(c?.y ?? "") ?? 0;
      if (d < 0 || y < 0) return `${t.label}: sayılar negatif olamaz`;
      if (d + y > t.q) return `${t.label}: doğru + yanlış ${t.q} soruyu geçemez`;
    }
    const missing = tests.filter((t) => !(t.key in nets));
    if (missing.length) return `Şu testleri doldur: ${missing.map((t) => t.label).join(", ")} (hiç çözmediysen 0 yaz)`;
    return null;
  }

  function nextFromNets() {
    const v = validateNets();
    if (v) { setError(v); return; }
    goTo(3);
  }

  async function calculate() {
    const v = validateNets();
    if (v) { setError(v); goTo(2); return; }
    const dip = toNum(diploma);
    if (dip != null && (dip < 50 || dip > 100)) { setError("Diploma notu 50 ile 100 arasında olmalı"); return; }
    setError(null);
    setBusy(true);
    const keys = new Set(tests.map((t) => t.key));
    const denemeler = [
      ...past
        .map((p) => ({
          date: p.date || null,
          nets: Object.fromEntries(
            Object.entries(p.nets).map(([k, val]) => [k, toNum(val)]).filter(([k, val]) => keys.has(k as string) && val != null),
          ),
        }))
        .filter((p) => Object.keys(p.nets).length > 0),
      { date: today(), nets },
    ];
    try {
      const r = await api<SimResult>("/api/v2/tools/yks-simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ denemeler, score_type: field === "TYT" ? null : field, diploma: dip }),
      });
      setResult(r);
      goTo(4);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail?.message ?? "Hesaplanamadı" : "Bağlantı sorunu, tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setDy({});
    setDiploma("");
    setPast([]);
    setResult(null);
    setMaxStep(1);
    goTo(1);
  }

  const errorBox = error ? (
    <p role="alert" className="flex items-start gap-2 rounded-2xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-900 ring-1 ring-rose-200">
      <Info className="mt-0.5 size-4 shrink-0 text-rose-700" aria-hidden />{error}
    </p>
  ) : null;

  return (
    <div ref={rootRef} className="scroll-mt-24 text-slate-900">
      <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-xl shadow-slate-900/5 sm:p-8">
        <Stepper step={step} maxStep={result ? 4 : maxStep === 4 ? 3 : maxStep} onGo={goTo} />

        {/* 1 · Puan türü */}
        {step === 1 ? (
          <section className="mt-8">
            <h2 className="font-display text-2xl font-bold text-slate-900 sm:text-3xl">Hangi puanı hesaplayalım?</h2>
            <p className="mt-1.5 text-slate-600">Tercih yapacağın puan türünü seç. Sayısal, eşit ağırlık ve sözelde TYT puanın da ayrıca hesaplanır.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {FIELDS.map((f) => {
                const active = field === f.key && maxStep > 1;
                return (
                  <button
                    key={f.key}
                    type="button"
                    onClick={() => {
                      if (f.key !== field) { setField(f.key); setResult(null); setMaxStep(2); }
                      goTo(2);
                    }}
                    className={cn(
                      "group flex items-center gap-4 rounded-2xl border-2 p-4 text-left transition hover:-translate-y-0.5 hover:border-cyan-600 hover:shadow-lg hover:shadow-cyan-600/10 sm:p-5",
                      active ? "border-cyan-600 bg-cyan-50" : "border-slate-200 bg-white",
                    )}
                  >
                    <span className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-slate-900 text-white transition group-hover:bg-cyan-700">
                      <f.icon className="size-6" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-display text-lg font-bold text-slate-900">{f.label}</span>
                      <span className="block text-sm text-slate-500">{f.sub}</span>
                    </span>
                    <ChevronRight className="size-5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-cyan-700" aria-hidden />
                  </button>
                );
              })}
            </div>
            <p className="mt-5 text-center text-xs text-slate-500">Üyelik gerekmez · Netlerin kaydedilmez · 1 dakika sürer</p>
          </section>
        ) : null}

        {/* 2 · Netler */}
        {step === 2 ? (
          <section className="mt-8">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-2xl font-bold text-slate-900 sm:text-3xl">Doğru ve yanlışlarını gir</h2>
                <p className="mt-1.5 text-slate-600">{FIELD_NAME[field]} puanı için {tests.length} test. Netin her satırda kendiliğinden hesaplanır.</p>
              </div>
              <button type="button" onClick={() => goTo(1)} className="text-sm font-semibold text-cyan-800 hover:underline">
                Puan türünü değiştir
              </button>
            </div>
            <div className="mt-5">
              <Tip>
                <b>Net = doğru − yanlış ÷ 4.</b> Dört yanlış bir doğruyu götürür; boş bıraktığın soru nete etki etmez.
                Hiç çözmediğin testte doğru ve yanlışa 0 yaz.
              </Tip>
            </div>

            {(["TYT", "AYT"] as const).map((session) => {
              const list = tests.filter((t) => (session === "TYT") === t.key.startsWith("tyt_"));
              if (!list.length) return null;
              return (
                <div key={session} className="mt-7">
                  <div className="mb-3 flex items-center gap-2">
                    <span className={cn("rounded-full px-2.5 py-1 text-xs font-bold", session === "TYT" ? "bg-cyan-700 text-white" : "bg-amber-400 text-slate-950")}>
                      {session}
                    </span>
                    <span className="text-sm font-semibold text-slate-700">
                      {session === "TYT" ? "Temel Yeterlilik Testi · 120 soru" : `${FIELD_NAME[field]} testleri · ${aytMax} soru`}
                    </span>
                  </div>
                  <div className="overflow-hidden rounded-2xl border border-slate-200">
                    <div className="hidden grid-cols-[1fr_6rem_6rem_5rem] gap-3 bg-slate-50 px-4 py-2 text-[11px] font-bold uppercase tracking-wide text-slate-500 sm:grid">
                      <span>Test</span><span className="text-center text-emerald-700">Doğru</span><span className="text-center text-rose-700">Yanlış</span><span className="text-right">Net</span>
                    </div>
                    <ul className="divide-y divide-slate-100">
                      {list.map((t) => {
                        const n = netOf(dy[t.key]?.d ?? "", dy[t.key]?.y ?? "");
                        const pct = n == null ? 0 : Math.min(100, (n / t.q) * 100);
                        return (
                          <li key={t.key} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-2 px-4 py-3 sm:grid-cols-[1fr_6rem_6rem_5rem]">
                            <div className="col-span-2 sm:col-span-1">
                              <label htmlFor={`d-${t.key}`} className="font-semibold text-slate-900">{t.label}</label>
                              <span className="ml-1.5 text-xs text-slate-500">{t.q} soru</span>
                              <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-100" aria-hidden>
                                <div className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all" style={{ width: `${pct}%` }} />
                              </div>
                            </div>
                            <div className="col-span-2 grid grid-cols-[1fr_1fr_4.5rem] items-center gap-2 sm:contents">
                              <label className="block">
                                <span className="mb-1 block text-[11px] font-bold uppercase text-emerald-700 sm:hidden">Doğru</span>
                                <input id={`d-${t.key}`} inputMode="numeric" placeholder="0" aria-label={`${t.label} doğru`} className={inputCls}
                                  value={dy[t.key]?.d ?? ""} onChange={(e) => setCell(t.key, "d", e.target.value)} />
                              </label>
                              <label className="block">
                                <span className="mb-1 block text-[11px] font-bold uppercase text-rose-700 sm:hidden">Yanlış</span>
                                <input inputMode="numeric" placeholder="0" aria-label={`${t.label} yanlış`} className={inputCls}
                                  value={dy[t.key]?.y ?? ""} onChange={(e) => setCell(t.key, "y", e.target.value)} />
                              </label>
                              <div className="text-right">
                                <span className="mb-1 block text-[11px] font-bold uppercase text-slate-500 sm:hidden">Net</span>
                                <span className="font-display text-xl font-extrabold tabular-nums text-cyan-800">{n == null ? "—" : fmt2(n)}</span>
                              </div>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>
              );
            })}

            {/* Toplam + ilerle */}
            <div className="mt-7 space-y-3">
              {errorBox}
              <div className="flex flex-col gap-4 rounded-2xl bg-slate-950 p-4 text-white sm:flex-row sm:items-center sm:p-5">
                <div className="flex flex-1 flex-wrap gap-x-8 gap-y-3">
                  <Total label="TYT neti" value={tytNet} max={120} tone="text-cyan-300" />
                  {aytTests.length ? <Total label="AYT neti" value={aytNet} max={aytMax} tone="text-amber-300" /> : null}
                  <div className="self-end text-sm text-slate-400">{filled}/{tests.length} test girildi</div>
                </div>
                <button type="button" onClick={nextFromNets}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-400 px-5 py-3 font-bold text-slate-950 transition hover:bg-amber-300">
                  Devam et <ArrowRight className="size-4" aria-hidden />
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {/* 3 · Ek bilgi */}
        {step === 3 ? (
          <section className="mt-8">
            <h2 className="font-display text-2xl font-bold text-slate-900 sm:text-3xl">Tahmini keskinleştir</h2>
            <p className="mt-1.5 text-slate-600">İkisi de isteğe bağlı. Boş bırakıp doğrudan hesaplayabilirsin.</p>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 p-5">
                <div className="flex items-center gap-2">
                  <GraduationCap className="size-5 text-cyan-700" aria-hidden />
                  <label htmlFor="diploma" className="font-display text-lg font-bold text-slate-900">Diploma notu</label>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                  Diploma notunun 5 ile çarpımının 0,12 katı puanına eklenir (OBP katkısı). Sıralaman bu yerleştirme puanıyla bulunur.
                </p>
                <input id="diploma" inputMode="decimal" placeholder="ör. 85" className={cn(inputCls, "mt-4 max-w-[10rem]")}
                  value={diploma} onChange={(e) => { setDiploma(e.target.value); setResult(null); }} />
                {toNum(diploma) != null && toNum(diploma)! >= 50 && toNum(diploma)! <= 100 ? (
                  <p className="mt-2 text-sm text-cyan-800">Puanına yaklaşık <b>{fmt1(toNum(diploma)! * 5 * 0.12)}</b> puan eklenir.</p>
                ) : null}
              </div>

              <div className="rounded-2xl border border-slate-200 p-5">
                <div className="flex items-center gap-2">
                  <CalendarClock className="size-5 text-cyan-700" aria-hidden />
                  <h3 className="font-display text-lg font-bold text-slate-900">Önceki denemelerin</h3>
                </div>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                  Eklersen gidişatın ve oynaklığın hesaba katılır; sınav günü tahmin aralığı daralır.
                </p>
                <div className="mt-4 space-y-3">
                  {past.map((p, i) => (
                    <div key={p.id} className="rounded-xl border border-slate-200 bg-slate-50/60 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <label className="text-xs font-semibold text-slate-700" htmlFor={`pd-${p.id}`}>{i + 1}. deneme tarihi</label>
                        <input id={`pd-${p.id}`} type="date" max={today()} className="h-9 rounded-lg border border-slate-300 bg-white px-2 text-sm text-slate-900"
                          value={p.date} onChange={(e) => setPast((arr) => arr.map((x) => (x.id === p.id ? { ...x, date: e.target.value } : x)))} />
                        <button type="button" className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-rose-700 hover:underline"
                          onClick={() => setPast((arr) => arr.filter((x) => x.id !== p.id))}>
                          <Trash2 className="size-3.5" aria-hidden /> Kaldır
                        </button>
                      </div>
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {tests.map((t) => (
                          <label key={t.key} className="text-xs text-slate-600">
                            {t.label} neti
                            <input inputMode="decimal" className={cn(inputCls, "mt-1 h-9 text-sm")} value={p.nets[t.key] ?? ""}
                              onChange={(e) => setPast((arr) => arr.map((x) => (x.id === p.id ? { ...x, nets: { ...x.nets, [t.key]: e.target.value } } : x)))} />
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                  {past.length < 7 ? (
                    <button type="button" onClick={() => setPast((arr) => [...arr, { id: Date.now(), date: "", nets: {} }])}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 hover:border-cyan-600">
                      <Plus className="size-4" aria-hidden /> Deneme ekle
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="mt-7 space-y-3">
              {errorBox}
              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
                <button type="button" onClick={() => goTo(2)} className="inline-flex items-center justify-center gap-1.5 rounded-xl px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-500/10">
                  <ArrowLeft className="size-4" aria-hidden /> Netlere dön
                </button>
                <button type="button" onClick={calculate} disabled={busy}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-amber-400 px-6 py-4 text-base font-bold text-slate-950 shadow-lg shadow-amber-500/25 transition hover:-translate-y-0.5 hover:bg-amber-300 disabled:translate-y-0 disabled:opacity-60">
                  {busy ? <Loader2 className="size-5 animate-spin" aria-hidden /> : <Calculator className="size-5" aria-hidden />}
                  Puanımı ve sıralamamı hesapla
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {/* 4 · Sonuç */}
        {step === 4 && result ? (
          <section className="mt-8">
            <div className="flex flex-wrap items-center gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
              <span className="font-semibold text-slate-900">{FIELD_NAME[field]}</span>
              <span>· TYT {fmt2(tytNet)}{aytTests.length ? <> · AYT {fmt2(aytNet)}</> : null} net</span>
              {toNum(diploma) != null ? <span>· diploma {diploma}</span> : null}
              {past.length ? <span>· {past.length} önceki deneme</span> : null}
              <span className="ml-auto flex gap-2">
                <button type="button" onClick={() => goTo(2)} className="inline-flex items-center gap-1 rounded-lg bg-white px-3 py-1.5 font-semibold text-cyan-800 ring-1 ring-slate-200 hover:ring-cyan-600">
                  <Pencil className="size-3.5" aria-hidden /> Netleri düzenle
                </button>
                <button type="button" onClick={restart} className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 font-semibold text-slate-700 hover:bg-white">
                  <RotateCcw className="size-3.5" aria-hidden /> Yeni hesap
                </button>
              </span>
            </div>
            <Results result={result} embedded={embedded} />
          </section>
        ) : null}
      </div>
    </div>
  );
}

function Total({ label, value, max, tone }: { label: string; value: number; max: number; tone: string }) {
  return (
    <div>
      <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{label}</div>
      <div className={cn("font-display text-3xl font-extrabold tabular-nums", tone)}>
        {fmt2(value)} <span className="text-sm font-semibold text-slate-500">/ {max}</span>
      </div>
    </div>
  );
}

/* ───────── Sonuçlar ───────── */

function ForecastBand({ f }: { f: ForecastRow }) {
  const lo = Math.max(100, Math.floor((f.score.p10 - 30) / 50) * 50);
  const hi = Math.min(560, Math.ceil((f.score.p90 + 30) / 50) * 50);
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const ticks: number[] = [];
  for (let t = lo; t <= hi; t += 50) ticks.push(t);
  return (
    <div className="mt-6" aria-hidden>
      <div className="relative h-14">
        <div className="absolute inset-x-0 top-5 h-4 rounded-full bg-slate-100" />
        <div
          className="absolute top-5 h-4 rounded-full bg-gradient-to-r from-rose-300 via-cyan-300 to-emerald-300"
          style={{ left: pos(f.score.p10), width: `calc(${pos(f.score.p90)} - ${pos(f.score.p10)})` }}
        />
        <div className="absolute top-2 flex -translate-x-1/2 flex-col items-center" style={{ left: pos(f.score.p50) }}>
          <div className="h-10 w-1.5 rounded-full bg-slate-900 shadow" />
        </div>
      </div>
      <div className="relative h-5 text-[11px] tabular-nums text-slate-400">
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-1/2" style={{ left: pos(t) }}>{t}</span>
        ))}
      </div>
    </div>
  );
}

function LessonRow({ l }: { l: Lesson }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / l.max) * 100))}%`;
  const up = l.weekly_trend > 0.02;
  const down = l.weekly_trend < -0.02;
  return (
    <li className="grid gap-2 py-4 sm:grid-cols-[11rem_1fr_7.5rem] sm:items-center sm:gap-5">
      <div className="font-semibold text-slate-900">
        {l.label} <span className="text-xs font-normal text-slate-500">/{l.max}</span>
      </div>
      <div>
        <div className="relative h-3 rounded-full bg-slate-100" aria-hidden>
          <div className="absolute inset-y-0 rounded-full bg-cyan-200" style={{ left: pct(l.p10), width: `calc(${pct(l.p90)} - ${pct(l.p10)})` }} />
          <div className="absolute -top-1 size-5 -translate-x-1/2 rounded-full border-2 border-white bg-slate-400 shadow" style={{ left: pct(l.current) }} />
          <div className="absolute -top-1 size-5 -translate-x-1/2 rounded-full border-2 border-white bg-cyan-700 shadow" style={{ left: pct(l.predicted) }} />
        </div>
        <div className="mt-2 flex justify-between text-xs text-slate-500">
          <span>Şu an <b className="tabular-nums text-slate-800">{fmt1(l.current)}</b></span>
          <span>Aralık {fmt1(l.p10)} – {fmt1(l.p90)}</span>
        </div>
      </div>
      <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-end">
        <div className="font-display text-2xl font-extrabold tabular-nums text-slate-900">{fmt1(l.predicted)}</div>
        <span className={cn(
          "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums",
          up ? "bg-emerald-100 text-emerald-800" : down ? "bg-rose-100 text-rose-800" : "bg-slate-100 text-slate-600",
        )}>
          {up ? <TrendingUp className="size-3.5" aria-hidden /> : down ? <TrendingDown className="size-3.5" aria-hidden /> : null}
          {l.weekly_trend > 0 ? "+" : ""}{fmt2(l.weekly_trend)}/hafta
        </span>
      </div>
    </li>
  );
}

function Results({ result, embedded }: { result: SimResult; embedded: boolean }) {
  const types = Object.keys(result.now);
  const examDate = new Date(result.exam_date).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
  return (
    <div className="mt-6 space-y-6">
      {/* Bugün */}
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-cyan-800 via-cyan-900 to-slate-950 p-6 text-white shadow-2xl shadow-cyan-900/30 sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-24 size-72 rounded-full bg-amber-400/25 blur-3xl" aria-hidden />
        <div className="relative">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em] text-cyan-200">
            <Trophy className="size-4 text-amber-300" aria-hidden /> Sınav bugün olsaydı
          </div>
          <p className="mt-2 text-sm text-cyan-100">Girdiğin netlerle ham puanın ve {result.rank_year} YKS verisine göre Türkiye sıralaman.</p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {types.map((st) => {
              const n = result.now[st];
              return (
                <div key={st} className="rounded-2xl bg-white/10 p-5 ring-1 ring-white/15 backdrop-blur">
                  <div className="text-xs font-semibold uppercase tracking-wider text-cyan-200">{FIELD_NAME[st]} puanı</div>
                  <div className="mt-1 font-display text-5xl font-extrabold tabular-nums">{fmt2(n.score)}</div>
                  <div className="mt-4 flex items-baseline justify-between gap-2 border-t border-white/15 pt-3">
                    <span className="text-sm text-cyan-100">Tahmini sıralama</span>
                    <span className="font-display text-2xl font-bold tabular-nums text-amber-300">{fmtInt(n.rank)}</span>
                  </div>
                  {n.placement_score ? <div className="mt-1 text-xs text-cyan-200">Yerleştirme puanı (diploma dahil): {fmt2(n.placement_score)}</div> : null}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Sınav günü */}
      <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">Sınav günü tahmini</div>
            <h2 className="mt-1 font-display text-2xl font-bold text-slate-900">
              {examDate}{result.exam_official ? "" : " (tahmini tarih)"}
            </h2>
          </div>
          <div className="rounded-full bg-slate-100 px-3 py-1.5 text-sm font-semibold text-slate-700">
            {fmt1(result.weeks_remaining)} hafta kaldı
          </div>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Her ders için seviyen ve gidişatın hesaplanır, 4.000 olası sınav günü senaryosu çalıştırılır. Ortadaki çizgi en olası puan; renkli bant kötü ile iyi senaryo arası.
        </p>

        <div className="mt-6 space-y-5">
          {Object.entries(result.forecast).map(([st, f]) => (
            <div key={st} className="rounded-2xl border border-slate-200 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <div className="font-semibold text-slate-900">{FIELD_NAME[st]}</div>
                <div className="flex items-baseline gap-4">
                  <span className="text-sm text-slate-500">En olası</span>
                  <span className="font-display text-3xl font-extrabold tabular-nums text-slate-900">{fmt1(f.score.p50)}</span>
                  <span className="text-sm text-slate-600">sıra <b className="tabular-nums text-slate-900">{fmtInt(f.rank.p50)}</b></span>
                </div>
              </div>
              <ForecastBand f={f} />
              <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl bg-rose-50 px-3 py-2 text-rose-900">
                  Kötü senaryo <b className="tabular-nums">{fmt1(f.score.p10)}</b> puan · {fmtInt(f.rank.worst)}. sıra
                </div>
                <div className="rounded-xl bg-emerald-50 px-3 py-2 text-right text-emerald-900">
                  İyi senaryo <b className="tabular-nums">{fmt1(f.score.p90)}</b> puan · {fmtInt(f.rank.best)}. sıra
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display text-lg font-bold text-slate-900">Ders ders sınav günü neti</h3>
            <div className="flex items-center gap-4 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-full bg-slate-400" />Şu an</span>
              <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-full bg-cyan-700" />Sınav günü</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-5 rounded-full bg-cyan-200" />Olası aralık</span>
            </div>
          </div>
          <ul className="mt-2 divide-y divide-slate-100">
            {result.lessons.map((l) => <LessonRow key={l.key} l={l} />)}
          </ul>
        </div>

        {result.warnings.length ? (
          <ul className="mt-6 space-y-2 rounded-2xl bg-slate-50 p-4">
            {result.warnings.map((w) => (
              <li key={w} className="flex items-start gap-2 text-xs leading-relaxed text-slate-600">
                <Info className="mt-0.5 size-3.5 shrink-0 text-slate-500" aria-hidden />{w}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="relative overflow-hidden rounded-3xl bg-slate-950 p-6 text-white">
          <div className="pointer-events-none absolute -bottom-16 -right-10 size-48 rounded-full bg-amber-400/20 blur-3xl" aria-hidden />
          <h2 className="relative font-display text-xl font-bold">Öğrenci misin?</h2>
          <p className="relative mt-2 text-sm leading-relaxed text-slate-300">
            Bu tahmin bir başlangıç. Etütkoç&apos;ta koçunla her denemeni konu konu analiz eder, eksik konulara göre haftalık programını birlikte kurarsınız.
          </p>
          <a href="https://etutkoc.com/contact" target={embedded ? "_top" : undefined}
            className="relative mt-5 inline-flex items-center gap-2 rounded-full bg-amber-400 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-amber-300">
            Ücretsiz tanışma görüşmesi <ArrowRight className="size-4" aria-hidden />
          </a>
        </div>
        <div className="rounded-3xl border border-cyan-200 bg-gradient-to-br from-cyan-50 to-white p-6">
          <h2 className="font-display text-xl font-bold text-slate-900">Koç ya da kurum musun?</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">
            Etütkoç Rotam&apos;da öğrencinin deneme karnesi PDF olarak yüklenir; netler, konu analizi ve bu tahmin her denemede kendiliğinden güncellenir.
          </p>
          <Link href="/signup/teacher" target={embedded ? "_blank" : undefined}
            className="mt-5 inline-flex items-center gap-2 rounded-full bg-cyan-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800">
            Rotam&apos;ı 14 gün ücretsiz dene <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </section>
    </div>
  );
}
