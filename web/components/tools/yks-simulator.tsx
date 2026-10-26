"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowRight, Info, Loader2, Plus, Trash2 } from "lucide-react";

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

const TYT_TESTS = [
  { key: "tyt_trk", label: "Türkçe", q: 40 },
  { key: "tyt_sos", label: "Sosyal Bilimler", q: 20 },
  { key: "tyt_mat", label: "Temel Matematik", q: 40 },
  { key: "tyt_fen", label: "Fen Bilimleri", q: 20 },
];
const AYT_TESTS: Record<Exclude<Field, "TYT">, { key: string; label: string; q: number }[]> = {
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
const FIELDS: { key: Field; label: string }[] = [
  { key: "TYT", label: "Yalnız TYT" },
  { key: "SAY", label: "Sayısal" },
  { key: "EA", label: "Eşit Ağırlık" },
  { key: "SÖZ", label: "Sözel" },
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
  "h-10 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-center text-[15px] text-slate-900 tabular-nums outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600/20";

/* ───────── Bileşen ───────── */

export function YksSimulator({ embedded = false }: { embedded?: boolean }) {
  const [field, setField] = React.useState<Field>("SAY");
  const [dy, setDy] = React.useState<DY>({});
  const [diploma, setDiploma] = React.useState("");
  const [past, setPast] = React.useState<PastDeneme[]>([]);
  const [result, setResult] = React.useState<SimResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const resultRef = React.useRef<HTMLDivElement>(null);

  // Gömülü sürüm: kapsayan sayfaya (etutkoc.com) içerik yüksekliğini bildir → iframe boyu uyar.
  React.useEffect(() => {
    if (!embedded || typeof window === "undefined" || window.parent === window) return;
    const post = () => window.parent.postMessage({ type: "etutkoc-yks-height", height: document.documentElement.scrollHeight }, "*");
    const ro = new ResizeObserver(post);
    ro.observe(document.body);
    post();
    return () => ro.disconnect();
  }, [embedded]);

  const tests = testsFor(field);
  const nets: Record<string, number> = {};
  for (const t of tests) {
    const n = netOf(dy[t.key]?.d ?? "", dy[t.key]?.y ?? "");
    if (n != null) nets[t.key] = n;
  }

  function setCell(key: string, part: "d" | "y", value: string) {
    setDy((prev) => ({ ...prev, [key]: { d: prev[key]?.d ?? "", y: prev[key]?.y ?? "", [part]: value } }));
  }

  function validate(): string | null {
    for (const t of tests) {
      const c = dy[t.key];
      const d = toNum(c?.d ?? "") ?? 0;
      const y = toNum(c?.y ?? "") ?? 0;
      if (d < 0 || y < 0) return `${t.label}: sayılar negatif olamaz`;
      if (d + y > t.q) return `${t.label}: doğru + yanlış ${t.q} soruyu geçemez`;
    }
    if (!TYT_TESTS.every((t) => t.key in nets)) return "Dört TYT testinin doğru ve yanlış sayılarını gir";
    if (field !== "TYT" && !AYT_TESTS[field].every((t) => t.key in nets)) return `${FIELD_NAME[field]} testlerinin hepsini gir`;
    const dip = toNum(diploma);
    if (dip != null && (dip < 50 || dip > 100)) return "Diploma notu 50 ile 100 arasında olmalı";
    return null;
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = validate();
    if (v) { setError(v); return; }
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
        body: JSON.stringify({
          denemeler,
          score_type: field === "TYT" ? null : field,
          diploma: toNum(diploma),
        }),
      });
      setResult(r);
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail?.message ?? "Hesaplanamadı" : "Bağlantı sorunu, tekrar dene.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="text-slate-900">
      <form onSubmit={submit} method="post" className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        {/* Alan */}
        <fieldset>
          <legend className="text-sm font-semibold text-slate-800">Puan türü</legend>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {FIELDS.map((f) => (
              <button
                key={f.key}
                type="button"
                aria-pressed={field === f.key}
                onClick={() => { setField(f.key); setResult(null); }}
                className={cn(
                  "rounded-xl border px-3 py-2.5 text-sm font-semibold transition",
                  field === f.key ? "border-cyan-700 bg-cyan-700 text-white" : "border-slate-300 bg-white text-slate-700 hover:border-cyan-600",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
        </fieldset>

        {/* Testler */}
        {(["TYT", "AYT"] as const).map((session) => {
          const list = tests.filter((t) => (session === "TYT") === t.key.startsWith("tyt_"));
          if (!list.length) return null;
          return (
            <div key={session} className="mt-6">
              <h3 className="text-sm font-semibold text-slate-800">{session === "TYT" ? "TYT" : `AYT · ${FIELD_NAME[field]}`}</h3>
              <div className="mt-2 overflow-hidden rounded-xl border border-slate-200">
                <div className="grid grid-cols-[1fr_4.5rem_4.5rem_4rem] gap-2 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 sm:grid-cols-[1fr_6rem_6rem_5rem]">
                  <span>Test</span><span className="text-center">Doğru</span><span className="text-center">Yanlış</span><span className="text-center">Net</span>
                </div>
                {list.map((t) => {
                  const n = netOf(dy[t.key]?.d ?? "", dy[t.key]?.y ?? "");
                  return (
                    <div key={t.key} className="grid grid-cols-[1fr_4.5rem_4.5rem_4rem] items-center gap-2 border-t border-slate-100 px-3 py-2 sm:grid-cols-[1fr_6rem_6rem_5rem]">
                      <label htmlFor={`d-${t.key}`} className="text-sm leading-tight text-slate-800">
                        {t.label} <span className="text-xs text-slate-500">({t.q} soru)</span>
                      </label>
                      <input id={`d-${t.key}`} inputMode="numeric" aria-label={`${t.label} doğru`} className={inputCls}
                        value={dy[t.key]?.d ?? ""} onChange={(e) => setCell(t.key, "d", e.target.value)} />
                      <input inputMode="numeric" aria-label={`${t.label} yanlış`} className={inputCls}
                        value={dy[t.key]?.y ?? ""} onChange={(e) => setCell(t.key, "y", e.target.value)} />
                      <span className="text-center text-sm font-semibold tabular-nums text-cyan-800">{n == null ? "—" : fmt2(n)}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}

        {/* Diploma */}
        <div className="mt-6 grid gap-2 sm:grid-cols-[1fr_10rem] sm:items-center">
          <label htmlFor="diploma" className="text-sm text-slate-700">
            <span className="font-semibold text-slate-800">Diploma notu</span> (isteğe bağlı) — sıralama yerleştirme puanıyla hesaplanır
          </label>
          <input id="diploma" inputMode="decimal" placeholder="ör. 85" className={inputCls} value={diploma} onChange={(e) => setDiploma(e.target.value)} />
        </div>

        {/* Önceki denemeler */}
        <details className="mt-6 rounded-xl border border-dashed border-slate-300 p-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">
            Önceki denemelerini de ekle <span className="font-normal text-slate-600">— kendi gidişatın hesaba katılır, tahmin aralığı daralır</span>
          </summary>
          <p className="mt-2 text-xs text-slate-600">Her deneme için tarihini ve test netlerini gir. Boş bıraktığın testler hesaba katılmaz.</p>
          <div className="mt-3 space-y-3">
            {past.map((p, i) => (
              <div key={p.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-semibold text-slate-700" htmlFor={`pd-${p.id}`}>{i + 1}. deneme tarihi</label>
                  <input id={`pd-${p.id}`} type="date" max={today()} className="h-9 rounded-lg border border-slate-300 bg-white px-2 text-sm text-slate-900"
                    value={p.date} onChange={(e) => setPast((arr) => arr.map((x) => (x.id === p.id ? { ...x, date: e.target.value } : x)))} />
                  <button type="button" className="ml-auto inline-flex items-center gap-1 text-xs text-rose-700 hover:underline"
                    onClick={() => setPast((arr) => arr.filter((x) => x.id !== p.id))}>
                    <Trash2 className="size-3.5" aria-hidden /> Kaldır
                  </button>
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {tests.map((t) => (
                    <label key={t.key} className="text-xs text-slate-600">
                      {t.label} neti
                      <input inputMode="decimal" className={cn(inputCls, "mt-1 h-9")} value={p.nets[t.key] ?? ""}
                        onChange={(e) => setPast((arr) => arr.map((x) => (x.id === p.id ? { ...x, nets: { ...x.nets, [t.key]: e.target.value } } : x)))} />
                    </label>
                  ))}
                </div>
              </div>
            ))}
            {past.length < 7 ? (
              <button type="button" onClick={() => setPast((arr) => [...arr, { id: Date.now(), date: "", nets: {} }])}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-cyan-600">
                <Plus className="size-4" aria-hidden /> Deneme ekle
              </button>
            ) : null}
          </div>
        </details>

        {error ? <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm font-medium text-rose-800">{error}</p> : null}

        <button type="submit" disabled={busy}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-5 py-3.5 text-base font-semibold text-white transition hover:bg-cyan-800 disabled:opacity-60">
          {busy ? <Loader2 className="size-5 animate-spin" aria-hidden /> : null}
          Puanımı ve sıralamamı hesapla
        </button>
        <p className="mt-2 text-center text-xs text-slate-500">Üyelik gerekmez. Girdiğin netler kaydedilmez.</p>
      </form>

      {result ? <Results result={result} embedded={embedded} ref={resultRef} /> : null}
    </div>
  );
}

/* ───────── Sonuçlar ───────── */

const Results = React.forwardRef<HTMLDivElement, { result: SimResult; embedded: boolean }>(function Results({ result, embedded }, ref) {
  const types = Object.keys(result.now);
  const examDate = new Date(result.exam_date).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
  return (
    <div ref={ref} className="mt-8 scroll-mt-24 space-y-6">
      {/* Bugün */}
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="font-display text-xl font-bold text-slate-900">Sınav bugün olsaydı</h2>
        <p className="mt-1 text-sm text-slate-600">Girdiğin netlerle ham puanın ve {result.rank_year} YKS verisine göre Türkiye sıralaman.</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {types.map((st) => {
            const n = result.now[st];
            return (
              <div key={st} className="rounded-xl bg-cyan-50 p-4 ring-1 ring-cyan-200">
                <div className="text-xs font-semibold uppercase tracking-wide text-cyan-800">{FIELD_NAME[st]} puanı</div>
                <div className="mt-1 font-display text-3xl font-extrabold tabular-nums text-slate-900">{fmt2(n.score)}</div>
                <div className="mt-1 text-sm text-slate-700">Tahmini sıralama: <b className="tabular-nums text-slate-900">{fmtInt(n.rank)}</b></div>
                {n.placement_score ? <div className="mt-0.5 text-xs text-slate-600">Yerleştirme puanı (diploma dahil): {fmt2(n.placement_score)}</div> : null}
              </div>
            );
          })}
        </div>
      </section>

      {/* Sınav günü */}
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <h2 className="font-display text-xl font-bold text-slate-900">Sınav günü tahmini</h2>
        <p className="mt-1 text-sm text-slate-600">
          {examDate}{result.exam_official ? "" : " (tahmini tarih)"} · {fmt1(result.weeks_remaining)} hafta kaldı.
          Her ders için seviye ve gidişat hesaplanır, 4.000 olası sınav günü senaryosu çalıştırılır.
        </p>
        <div className="mt-4 space-y-4">
          {Object.entries(result.forecast).map(([st, f]) => {
            const lo = 100, hi = 500;
            const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
            return (
              <div key={st} className="rounded-xl border border-slate-200 p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">{FIELD_NAME[st]}</div>
                  <div className="text-sm text-slate-700">
                    En olası puan <b className="font-display text-xl tabular-nums text-slate-900">{fmt1(f.score.p50)}</b>
                    <span className="mx-2 text-slate-400">·</span>
                    sıralama <b className="tabular-nums text-slate-900">{fmtInt(f.rank.p50)}</b>
                  </div>
                </div>
                <div className="relative mt-4 h-3 rounded-full bg-slate-100" aria-hidden>
                  <div className="absolute inset-y-0 rounded-full bg-cyan-200" style={{ left: pos(f.score.p10), width: `calc(${pos(f.score.p90)} - ${pos(f.score.p10)})` }} />
                  <div className="absolute -top-1 h-5 w-1 rounded bg-cyan-800" style={{ left: pos(f.score.p50) }} />
                </div>
                <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  <div>Kötü senaryo: <b className="tabular-nums text-slate-800">{fmt1(f.score.p10)}</b> puan · {fmtInt(f.rank.worst)}. sıra</div>
                  <div className="text-right">İyi senaryo: <b className="tabular-nums text-slate-800">{fmt1(f.score.p90)}</b> puan · {fmtInt(f.rank.best)}. sıra</div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs text-slate-600">
                <th className="py-2 pr-2 font-semibold">Ders</th>
                <th className="px-2 py-2 text-right font-semibold">Şu an</th>
                <th className="px-2 py-2 text-right font-semibold">Sınav günü (olası)</th>
                <th className="px-2 py-2 text-right font-semibold">Aralık</th>
                <th className="py-2 pl-2 text-right font-semibold">Haftalık eğilim</th>
              </tr>
            </thead>
            <tbody>
              {result.lessons.map((l) => (
                <tr key={l.key} className="border-b border-slate-100">
                  <td className="py-2 pr-2 text-slate-800">{l.label} <span className="text-xs text-slate-500">/{l.max}</span></td>
                  <td className="px-2 py-2 text-right tabular-nums">{fmt1(l.current)}</td>
                  <td className="px-2 py-2 text-right font-semibold tabular-nums text-slate-900">{fmt1(l.predicted)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-slate-600">{fmt1(l.p10)} – {fmt1(l.p90)}</td>
                  <td className={cn("py-2 pl-2 text-right tabular-nums", l.weekly_trend > 0.02 ? "text-emerald-700" : l.weekly_trend < -0.02 ? "text-rose-700" : "text-slate-600")}>
                    {l.weekly_trend > 0 ? "+" : ""}{fmt2(l.weekly_trend)} net
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {result.warnings.length ? (
          <ul className="mt-4 space-y-1.5">
            {result.warnings.map((w) => (
              <li key={w} className="flex items-start gap-2 text-xs leading-relaxed text-slate-600">
                <Info className="mt-0.5 size-3.5 shrink-0 text-slate-500" aria-hidden />{w}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-2xl bg-cyan-900 p-5 text-white">
          <h2 className="font-display text-lg font-bold">Öğrenci misin?</h2>
          <p className="mt-1.5 text-sm text-cyan-100">
            Bu tahmin bir başlangıç. Etütkoç&apos;ta koçunla her denemeni konu konu analiz eder, eksik konulara göre haftalık programını birlikte kurarsınız.
          </p>
          <a href="https://etutkoc.com/contact" target={embedded ? "_top" : undefined}
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-400 px-5 py-2.5 text-sm font-semibold text-slate-900 hover:bg-amber-300">
            Ücretsiz tanışma görüşmesi <ArrowRight className="size-4" aria-hidden />
          </a>
        </div>
        <div className="rounded-2xl border border-cyan-200 bg-white p-5">
          <h2 className="font-display text-lg font-bold text-slate-900">Koç ya da kurum musun?</h2>
          <p className="mt-1.5 text-sm text-slate-700">
            Etütkoç Rotam&apos;da öğrencinin deneme karnesi PDF olarak yüklenir; netler, konu analizi ve bu tahmin her denemede kendiliğinden güncellenir.
          </p>
          <Link href="/signup/teacher" target={embedded ? "_blank" : undefined}
            className="mt-4 inline-flex items-center gap-2 rounded-full bg-cyan-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-cyan-800">
            Rotam&apos;ı 14 gün ücretsiz dene <ArrowRight className="size-4" aria-hidden />
          </Link>
        </div>
      </section>
    </div>
  );
});
