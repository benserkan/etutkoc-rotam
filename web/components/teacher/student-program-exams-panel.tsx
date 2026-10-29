"use client";

/**
 * Öğrenci detayı · Denemeler › "Branş denemeleri analizi" (2026-10-20 yeniden tasarım).
 *
 * Eskiden öğrenci detayında ayrı bir sekmeydi; menüyü iki satıra ittiği için Denemeler
 * sekmesinin içine, karne denemelerinin yanına üçüncü kart olarak alındı (#program-exams
 * bağlantısı bu görünümü açar).
 *
 * Programdaki deneme görevlerinin sonuçları (import_source="task") karne/elle girilen
 * deneme analizinden AYRI tutulur: soru-satırı ve konu eşlemesi taşımazlar, farklı soru
 * sayılı branş denemeleridir → kıyas NET YÜZDESİ (net ÷ soru) ile yapılır.
 *
 * Açılar (hepsi backend `deneme_analysis.py`, tek merkez):
 *   1. Kuşbakışı ölçüler (deneme · net % · doğruluk · boş · kaçan net · bekleyen)
 *   2. Öne çıkanlar (en güçlü / en zayıf / yükselen / gerileyen / en istikrarlı ders)
 *   3. Ders karnesi tablosu (normal aralık cetveli, eğilim, ivme, istikrar, test↔deneme)
 *   4. Dersler yan yana gidişat (tek eksen: net %)
 *   5. Ders × deneme ısı tablosu
 *   6. Haftalık deneme ritmi
 *   7. Seçili dersin derin analizi (bant + tahmin, D/Y/B dağılımı, kaçan net, süre)
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Award,
  CalendarDays,
  Clock,
  Gauge,
  Info,
  Minus,
  Target,
  TrendingDown,
  TrendingUp,
  Waves,
} from "lucide-react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DenemePendingCard } from "@/components/shared/deneme-pending-card";
import { OvSection, RatioLegend, ratioClass } from "@/components/shared/exam-ov/ov-ui";
import { ProgramExamsSection } from "@/components/shared/program-exams-section";
import { subjectColors } from "@/components/shared/subject-tag";
import { SeriesCard } from "@/components/teacher/student-weekly-progress";
import {
  denemeKeys,
  getDenemeAnalysis,
  type DenemeAnalysisSeries,
  type DenemeOverview,
  type DenemeOverviewPick,
} from "@/lib/api/deneme";
import { getTeacherStudentExams, teacherKeys } from "@/lib/api/teacher";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------- biçim

function p1(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `%${Number(v.toFixed(1)).toLocaleString("tr-TR")}`;
}

function n1(v: number | null | undefined, plus = false): string {
  if (v == null || Number.isNaN(v)) return "—";
  const s = Number(v.toFixed(1)).toLocaleString("tr-TR");
  if (plus && v > 0) return `+${s}`;
  return s.replace("-", "−");
}

const AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.split("-");
  return `${Number(d)} ${AY[Number(m) - 1] ?? ""}`;
}

function daysAgo(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n <= 0) return "bugün";
  if (n === 1) return "dün";
  return `${n} gün önce`;
}

/** Seri adı: branşta dersin adı ("Matematik"), genelde seri etiketi. */
function nameOf(s: DenemeAnalysisSeries): string {
  return s.kind === "brans" && s.subject ? s.subject : s.label;
}

function colorOf(s: DenemeAnalysisSeries): string {
  return subjectColors(s.subject ?? s.label).rail;
}

const CONSISTENCY: Record<string, { label: string; cls: string }> = {
  high: { label: "Düzenli", cls: "bg-teal-700 text-white" },
  mid: { label: "Orta", cls: "bg-amber-200 text-amber-950" },
  low: { label: "Dalgalı", cls: "bg-orange-300 text-orange-950" },
};

// ---------------------------------------------------------------- kök

export function StudentProgramExamsPanel({
  studentId,
  onBack,
}: {
  studentId: number;
  /** Verilirse üstte "Karne denemelerine dön" bağlantısı çizilir. */
  onBack?: () => void;
}) {
  const analysisQ = useQuery({
    queryKey: denemeKeys.analysis(studentId),
    queryFn: () => getDenemeAnalysis(studentId),
    staleTime: 30_000,
  });
  const examsQ = useQuery({
    queryKey: teacherKeys.studentExams(studentId),
    queryFn: () => getTeacherStudentExams(studentId),
    staleTime: 30_000,
  });

  const a = analysisQ.data;
  const branch = React.useMemo(() => (a?.series ?? []).filter((s) => s.kind === "brans"), [a]);
  const genel = (a?.series ?? []).filter((s) => s.kind === "genel");
  const legacy = (a?.series ?? []).filter((s) => (s.legacy_rows ?? 0) > 0);
  const rows = examsQ.data?.program_rows ?? [];
  const ov = a?.overview ?? null;

  const [sel, setSel] = React.useState<string | null>(null);
  // Varsayılan seçili ders: işareti olan ilk ders, yoksa en çok denemesi olan
  const flagged = a?.flags.find((f) => branch.some((s) => s.key === f.series))?.series;
  const activeKey =
    sel && branch.some((s) => s.key === sel) ? sel : (flagged ?? branch[0]?.key ?? null);
  const active = branch.find((s) => s.key === activeKey) ?? null;

  function focusSubject(key: string) {
    setSel(key);
    if (typeof document !== "undefined") {
      document.getElementById("brans-detail")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <div className="flex flex-col gap-5" data-section="program-exams">
      {/* Başlık şeridi */}
      <div className="relative overflow-hidden rounded-2xl border border-teal-200 bg-card p-5">
        <div className="pointer-events-none absolute -right-16 -top-16 size-48 rounded-full bg-teal-500/10" aria-hidden />
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="mb-3 inline-flex items-center gap-1.5 text-[13px] font-semibold text-teal-800 hover:underline"
          >
            <ArrowLeft className="size-4" aria-hidden />
            Karne denemelerine dön
          </button>
        ) : null}
        <div className="text-xs font-bold tracking-wider text-teal-800">BRANŞ DENEMELERİ</div>
        <h3 className="mt-1 text-xl font-extrabold leading-snug sm:text-2xl">Ders ders deneme gidişatı</h3>
        <p className="mt-1.5 max-w-3xl text-[13px] leading-relaxed text-muted-foreground">
          Haftalık programa deneme görevi olarak verilen ve sonucu görevden girilen denemeler. Karne yüklenen
          denemelerden ayrı tutulur. Dersler farklı soru sayısıyla çözüldüğü için kıyas{" "}
          <b className="text-foreground">net yüzdesi</b> (net ÷ soru sayısı) üzerinden yapılır.
        </p>
      </div>

      <DenemePendingCard audience={{ kind: "coach", studentId }} />

      {analysisQ.isLoading ? (
        <div className="h-64 animate-pulse rounded-2xl bg-muted" aria-label="Yükleniyor" />
      ) : analysisQ.isError ? (
        <p className="rounded-2xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Branş denemesi analizi yüklenemedi.
        </p>
      ) : branch.length === 0 && genel.length === 0 ? (
        <div className="flex items-start gap-3 rounded-2xl border border-border bg-card p-5 text-sm">
          <Info className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden />
          <p className="text-muted-foreground">
            Henüz sonucu girilmiş program denemesi yok. Haftalık programa deneme görevi verip öğrenci doğru/yanlış
            girdikçe burada ders ders gidişat oluşur.
          </p>
        </div>
      ) : (
        <>
          {ov && branch.length > 0 ? <Kpis ov={ov} pending={a?.summary.pending ?? 0} /> : null}

          {ov && branch.length > 1 ? <Highlights ov={ov} series={branch} onPick={focusSubject} /> : null}

          {a && a.flags.length > 0 ? (
            <OvSection
              eyebrow="KOÇUN BAKACAĞI YERLER"
              tone="orange"
              title={`${a.flags.length} işaret`}
              desc="Yargı değil, bakılacak yer: sistem ölçtüğünü söyler, nedeni seansta konuşulur."
            >
              <ul className="grid gap-2 md:grid-cols-2">
                {a.flags.map((f, i) => {
                  const s = branch.find((x) => x.key === f.series);
                  return (
                    <li key={`${f.code}-${f.series}-${i}`}>
                      <button
                        type="button"
                        onClick={() => s && focusSubject(s.key)}
                        className={cn(
                          "flex w-full items-start gap-2.5 rounded-xl border p-3 text-left text-sm transition-colors",
                          f.level === "warn"
                            ? "border-orange-300 bg-orange-50 text-orange-950 hover:bg-orange-100"
                            : "border-border bg-card hover:bg-muted",
                        )}
                      >
                        {f.level === "warn" ? (
                          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-orange-700" aria-hidden />
                        ) : (
                          <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                        )}
                        <span className="min-w-0 flex-1">{f.text}</span>
                        {s ? <ArrowRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden /> : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </OvSection>
          ) : null}

          {branch.length > 0 ? <ReportCard series={branch} activeKey={activeKey} onPick={focusSubject} /> : null}

          {branch.length > 1 ? <CompareChart series={branch} /> : null}

          {branch.length > 0 ? <HeatTable series={branch} onPick={focusSubject} /> : null}

          {ov && branch.length > 0 ? <Rhythm ov={ov} /> : null}

          {active ? (
            <SubjectDeepDive
              s={active}
              series={branch}
              onPick={setSel}
            />
          ) : null}

          {genel.length > 0 ? (
            <OvSection
              eyebrow="PROGRAMDAKİ GENEL DENEMELER"
              tone="violet"
              title="Programdan verilen genel denemeler"
              desc="Karne yüklenmeden, görevden sonucu girilen genel denemeler. Karne analizine karışmaz."
            >
              <div className="grid gap-3.5 md:grid-cols-2 xl:grid-cols-3">
                {genel.map((s) => (
                  <SeriesCard key={s.key} s={s} />
                ))}
              </div>
            </OvSection>
          ) : null}

          {legacy.length > 0 ? (
            <p className="text-xs leading-relaxed text-muted-foreground">
              Eski kayıtlarda birden çok deneme tek satırda toplandığı için seriye girmez; yalnız doğruluk hesabına
              katılır ({legacy.map((s) => `${nameOf(s)}: ${s.legacy_rows} kayıt`).join(" · ")}).
            </p>
          ) : null}
        </>
      )}

      <ProgramExamsSection rows={rows} audience="coach" />
    </div>
  );
}

// ---------------------------------------------------------------- 1. kuşbakışı

function Kpi({
  label,
  value,
  unit,
  desc,
  icon: Icon,
  children,
}: {
  label: string;
  value: string;
  unit?: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1.5 rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
        <Icon className="size-3.5 shrink-0" aria-hidden />
        {label}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-extrabold tabular-nums leading-none">{value}</span>
        {unit ? <span className="text-xs font-medium text-muted-foreground">{unit}</span> : null}
      </div>
      {children}
      <p className="text-[11.5px] leading-snug text-muted-foreground">{desc}</p>
    </div>
  );
}

function Kpis({ ov, pending }: { ov: DenemeOverview; pending: number }) {
  const lostTotal = ov.lost_wrong + ov.lost_blank;
  const perExam = ov.exams ? lostTotal / ov.exams : 0;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-section="brans:kpis">
      <Kpi
        icon={CalendarDays}
        label="Çözülen deneme"
        value={String(ov.exams)}
        unit={`deneme · ${ov.subjects} ders`}
        desc={`Toplam ${ov.questions.toLocaleString("tr-TR")} soru, sonucu girilenler.`}
      />
      <Kpi
        icon={Target}
        label="Ortalama net yüzdesi"
        value={p1(ov.avg_net_pct)}
        desc="Derslerin ortalama net ÷ soru oranı (en az 2 denemesi olan dersler)."
      />
      <Kpi
        icon={Gauge}
        label="Doğruluk"
        value={p1(ov.accuracy_pct)}
        desc={`Cevapladığı ${(ov.correct + ov.wrong).toLocaleString("tr-TR")} sorunun ne kadarı doğru (boş hariç).`}
      />
      <Kpi
        icon={Waves}
        label="Boş oranı"
        value={p1(ov.blank_rate_pct)}
        desc={`${ov.blank.toLocaleString("tr-TR")} soru boş bırakıldı — girmeye cesaret / süre sinyali.`}
      />
      <Kpi
        icon={TrendingDown}
        label="Kaçan net"
        value={n1(perExam)}
        unit="net / deneme"
        desc="Tam puandan kaçan net: yanlışlar (cezasıyla) + boşlar."
      >
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
          <div className="bg-rose-600" style={{ width: `${lostTotal ? (100 * ov.lost_wrong) / lostTotal : 0}%` }} />
          <div className="ml-0.5 bg-slate-400" style={{ width: `${lostTotal ? (100 * ov.lost_blank) / lostTotal : 0}%` }} />
        </div>
        <div className="flex justify-between text-[11px] font-semibold">
          <span className="text-rose-800">yanlış {n1(ov.lost_wrong)}</span>
          <span className="text-muted-foreground">boş {ov.lost_blank}</span>
        </div>
      </Kpi>
      <Kpi
        icon={Clock}
        label="Sonucu bekleyen"
        value={String(pending)}
        unit="deneme"
        desc={pending > 0 ? "Çözüldü işaretli ama doğru/yanlış girilmedi — analize giremiyor." : "Çözülen her denemenin sonucu girilmiş."}
      />
    </div>
  );
}

// ---------------------------------------------------------------- 2. öne çıkanlar

function Highlights({
  ov,
  series,
  onPick,
}: {
  ov: DenemeOverview;
  series: DenemeAnalysisSeries[];
  onPick: (key: string) => void;
}) {
  const items: {
    pick: DenemeOverviewPick | null;
    title: string;
    icon: React.ComponentType<{ className?: string }>;
    tone: string;
    value: (v: number) => string;
    note: string;
  }[] = [
    {
      pick: ov.strongest,
      title: "En güçlü ders",
      icon: Award,
      tone: "border-teal-300",
      value: (v) => `${p1(v)} ortalama net`,
      note: "Net yüzdesi en yüksek ders.",
    },
    {
      pick: ov.weakest,
      title: "En çok net kaçan ders",
      icon: Target,
      tone: "border-rose-300",
      value: (v) => `${p1(v)} ortalama net`,
      note: "Net yüzdesi en düşük ders.",
    },
    {
      pick: ov.rising,
      title: "Yükselen",
      icon: TrendingUp,
      tone: "border-emerald-300",
      value: (v) => `deneme başına ${n1(v, true)} puan`,
      note: "Son denemelerde en hızlı artan.",
    },
    {
      pick: ov.falling,
      title: "Gerileyen",
      icon: TrendingDown,
      tone: "border-orange-300",
      value: (v) => `deneme başına ${n1(v, true)} puan`,
      note: "Son denemelerde en hızlı düşen.",
    },
    {
      pick: ov.steadiest,
      title: "En düzenli gidişat",
      icon: Waves,
      tone: "border-cyan-300",
      value: (v) => `±${n1(v)} puan sapma`,
      note: "Kendi eğiliminden en az sapan (zikzak çizmeyen).",
    },
  ];
  const shown = items.filter((i) => i.pick);
  if (shown.length === 0) return null;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5" data-section="brans:highlights">
      {shown.map((i) => {
        const Icon = i.icon;
        const ser = series.find((x) => x.key === i.pick!.key);
        const subj = ser ? nameOf(ser) : i.pick!.label;
        return (
          <button
            key={i.title}
            type="button"
            onClick={() => onPick(i.pick!.key)}
            className={cn(
              "flex min-w-0 flex-col gap-1 rounded-2xl border-2 bg-card p-4 text-left transition-colors hover:bg-muted",
              i.tone,
            )}
          >
            <span className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground">
              <Icon className="size-3.5" aria-hidden />
              {i.title}
            </span>
            <span className="flex items-center gap-2 text-base font-extrabold">
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: ser ? colorOf(ser) : subjectColors(subj).rail }} aria-hidden />
              <span className="break-words">{subj}</span>
            </span>
            <span className="text-[13px] font-semibold tabular-nums">{i.value(i.pick!.value)}</span>
            <span className="text-[11.5px] text-muted-foreground">{i.note}</span>
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- 3. ders karnesi

/** 0–100 cetvel: normal bant + ortalama + son deneme işareti. */
function BandRuler({ s }: { s: DenemeAnalysisSeries }) {
  const last = s.last_net_pct;
  return (
    <div className="w-full min-w-[140px]">
      <div className="relative h-3 rounded-full bg-muted">
        {s.normal_low != null && s.normal_high != null ? (
          <div
            className="absolute inset-y-0 rounded-full bg-teal-600/30"
            style={{ left: `${s.normal_low}%`, width: `${Math.max(1.5, s.normal_high - s.normal_low)}%` }}
          />
        ) : null}
        {last != null ? (
          <div
            className={cn(
              "absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card",
              s.last_position === "below" ? "bg-orange-600" : s.last_position === "above" ? "bg-teal-700" : "bg-foreground",
            )}
            style={{ left: `${Math.max(0, Math.min(100, last))}%` }}
            title={`Son deneme ${p1(last)}`}
          />
        ) : null}
      </div>
      <div className="mt-1 text-[11px] text-muted-foreground">
        {s.normal_low != null && s.normal_high != null
          ? `genelde ${p1(s.normal_low)}–${n1(s.normal_high)}`
          : "normal aralık için 4 deneme gerekir"}
      </div>
    </div>
  );
}

function TrendPill({ s }: { s: DenemeAnalysisSeries }) {
  if (s.slope == null) return <span className="text-xs text-muted-foreground">—</span>;
  const Icon = s.direction === "up" ? ArrowUpRight : s.direction === "down" ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold",
        s.direction === "up"
          ? "bg-teal-700 text-white"
          : s.direction === "down"
            ? "bg-orange-600 text-white"
            : "bg-slate-200 text-slate-800",
      )}
      title="Son en çok 8 denemeye oturtulan doğrunun eğimi: deneme başına net yüzdesi değişimi"
    >
      <Icon className="size-3.5" aria-hidden />
      {n1(s.slope, true)}
    </span>
  );
}

function AccBars({ s }: { s: DenemeAnalysisSeries }) {
  const rows: { label: string; v: number | null | undefined; cls: string }[] = [
    { label: "Deneme", v: s.accuracy_pct, cls: "bg-foreground" },
    { label: "Test", v: s.test_accuracy_pct, cls: "bg-cyan-700" },
    { label: "Genel d.", v: s.genel_accuracy_pct, cls: "bg-violet-600" },
  ];
  return (
    <div className="flex min-w-[160px] flex-col gap-1">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[52px_1fr_38px] items-center gap-1.5 text-[11px]">
          <span className="text-muted-foreground">{r.label}</span>
          <div className="h-1.5 rounded-full bg-muted">
            {r.v != null ? <div className={cn("h-1.5 rounded-full", r.cls)} style={{ width: `${r.v}%` }} /> : null}
          </div>
          <span className="text-right font-semibold tabular-nums">{r.v != null ? `%${Math.round(r.v)}` : "—"}</span>
        </div>
      ))}
    </div>
  );
}

function ReportCard({
  series,
  activeKey,
  onPick,
}: {
  series: DenemeAnalysisSeries[];
  activeKey: string | null;
  onPick: (key: string) => void;
}) {
  return (
    <OvSection
      eyebrow="DERS KARNESİ"
      tone="cyan"
      title="Her ders tek satırda"
      desc={
        <>
          <b className="text-foreground">Normal aralık</b>: öğrencinin kendi denemelerinin orta yarısı (ortalama değil).
          Nokta son deneme. <b className="text-foreground">Eğilim</b>: deneme başına net yüzdesi değişimi.{" "}
          <b className="text-foreground">İvme</b>: son denemelerin ortalaması öncekilere göre.{" "}
          <b className="text-foreground">Doğruluk</b>: aynı dersin denemede, soru bankası testlerinde ve karne genel
          denemelerinde doğru oranı (son 90 gün).
        </>
      }
      dataSection="brans:report"
    >
      <div className="relative -mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[980px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="text-left text-[11px] font-bold uppercase tracking-wide text-muted-foreground">
              <th className="border-b border-border pb-2 pr-3">Ders</th>
              <th className="border-b border-border pb-2 pr-3 text-right">Ort. net</th>
              <th className="border-b border-border pb-2 pr-3 text-right">Son</th>
              <th className="border-b border-border pb-2 pr-3">Normal aralık · son deneme</th>
              <th className="border-b border-border pb-2 pr-3">Eğilim</th>
              <th className="border-b border-border pb-2 pr-3 text-right">İvme</th>
              <th className="border-b border-border pb-2 pr-3">İstikrar</th>
              <th className="border-b border-border pb-2 pr-3">Doğruluk</th>
              <th className="border-b border-border pb-2 pr-3 text-right">Boş</th>
              <th className="border-b border-border pb-2 text-right">Son deneme</th>
            </tr>
          </thead>
          <tbody>
            {series.map((s) => {
              const c = CONSISTENCY[s.consistency ?? ""];
              return (
                <tr
                  key={s.key}
                  onClick={() => onPick(s.key)}
                  className={cn("cursor-pointer align-middle transition-colors hover:bg-muted/60", s.key === activeKey && "bg-muted/60")}
                >
                  <td className="border-b border-border py-3 pr-3">
                    <div className="flex items-center gap-2.5">
                      <span className="h-8 w-1.5 shrink-0 rounded-full" style={{ background: colorOf(s) }} aria-hidden />
                      <div className="min-w-0">
                        <div className="font-bold">{nameOf(s)}</div>
                        <div className="text-[11px] text-muted-foreground">
                          {s.count} deneme · {s.avg_questions != null ? `${n1(s.avg_questions)} soru` : "soru —"}
                          {s.pending > 0 ? (
                            <span className="ml-1 font-semibold text-amber-800">· {s.pending} sonuç bekliyor</span>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="border-b border-border py-3 pr-3 text-right font-bold tabular-nums">{p1(s.avg_net_pct)}</td>
                  <td className="border-b border-border py-3 pr-3 text-right tabular-nums">{p1(s.last_net_pct)}</td>
                  <td className="border-b border-border py-3 pr-3">
                    <BandRuler s={s} />
                  </td>
                  <td className="border-b border-border py-3 pr-3">
                    <TrendPill s={s} />
                  </td>
                  <td
                    className={cn(
                      "border-b border-border py-3 pr-3 text-right font-semibold tabular-nums",
                      s.momentum != null && s.momentum >= 3 && "text-teal-800",
                      s.momentum != null && s.momentum <= -3 && "text-orange-800",
                    )}
                    title={s.momentum_window ? `Son ${s.momentum_window} deneme, önceki ${s.momentum_window} denemeyle` : undefined}
                  >
                    {s.momentum != null ? `${n1(s.momentum, true)} puan` : "—"}
                  </td>
                  <td className="border-b border-border py-3 pr-3">
                    {c ? (
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-bold", c.cls)} title={`Eğilimden ortalama sapma ±${n1(s.stdev_net_pct)} puan`}>
                        {c.label}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="border-b border-border py-3 pr-3">
                    <AccBars s={s} />
                  </td>
                  <td
                    className={cn(
                      "border-b border-border py-3 pr-3 text-right tabular-nums",
                      (s.blank_rate_pct ?? 0) >= 25 && "font-bold text-orange-800",
                    )}
                  >
                    {p1(s.blank_rate_pct)}
                  </td>
                  <td className="border-b border-border py-3 text-right text-xs text-muted-foreground">
                    <div className="font-semibold text-foreground">{daysAgo(s.days_since_last)}</div>
                    {s.avg_gap_days != null ? <div>~{n1(s.avg_gap_days)} günde bir</div> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[11.5px] text-muted-foreground">Satıra tıkla → dersin ayrıntılı analizi aşağıda açılır.</p>
    </OvSection>
  );
}

// ---------------------------------------------------------------- 4. dersler yan yana

function ChartTip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { name: string; date: string; net: number; pct: number | null; q: number | null } }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <div className="font-bold">{d.name}</div>
      <div className="text-muted-foreground">{shortDate(d.date)}</div>
      <div className="mt-1 tabular-nums">
        <b>{p1(d.pct)}</b> · {n1(d.net)} net{d.q ? ` / ${d.q} soru` : ""}
      </div>
    </div>
  );
}

function CompareChart({ series }: { series: DenemeAnalysisSeries[] }) {
  const lines = series.map((s) => ({
    s,
    data: s.points
      .filter((p) => p.net_pct != null)
      .map((p) => ({ x: Date.parse(p.date), name: nameOf(s), date: p.date, net: p.net, pct: p.net_pct, q: p.questions })),
  }));
  const xs = lines.flatMap((l) => l.data.map((d) => d.x));
  const min = Math.min(...xs);
  const max = Math.max(...xs);
  return (
    <OvSection
      eyebrow="DERSLER YAN YANA"
      tone="cyan"
      title="Net yüzdesi zaman içinde"
      desc="Her çizgi bir ders; farklı soru sayılı denemeler net yüzdesiyle aynı eksende. Noktanın üzerine gel: tarih, net ve soru sayısı."
      dataSection="brans:compare"
    >
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[13px]">
        {lines.map(({ s }) => (
          <span key={s.key} className="inline-flex items-center gap-1.5 font-semibold">
            <span className="h-0.5 w-4 rounded-full" style={{ background: colorOf(s) }} aria-hidden />
            {nameOf(s)}
          </span>
        ))}
      </div>
      <div className="relative -mx-1 overflow-x-auto px-1">
        <div className="h-[280px] min-w-[560px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
              <CartesianGrid stroke="currentColor" strokeOpacity={0.08} vertical={false} />
              <XAxis
                dataKey="x"
                type="number"
                domain={[min, max]}
                scale="time"
                tickFormatter={(v: number) => shortDate(new Date(v).toISOString().slice(0, 10))}
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
                stroke="currentColor"
                strokeOpacity={0.15}
                allowDuplicatedCategory={false}
              />
              <YAxis
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickFormatter={(v: number) => `%${v}`}
                tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
                stroke="currentColor"
                strokeOpacity={0.15}
                width={44}
              />
              <Tooltip content={<ChartTip />} cursor={{ stroke: "currentColor", strokeOpacity: 0.2 }} />
              {lines.map(({ s, data }) => (
                <Line
                  key={s.key}
                  data={data}
                  dataKey="pct"
                  name={nameOf(s)}
                  stroke={colorOf(s)}
                  strokeWidth={2}
                  dot={{ r: 4, strokeWidth: 2, stroke: "var(--card)", fill: colorOf(s) }}
                  activeDot={{ r: 6 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </OvSection>
  );
}

// ---------------------------------------------------------------- 5. ısı tablosu

const HEAT_COLS = 10;

function HeatTable({ series, onPick }: { series: DenemeAnalysisSeries[]; onPick: (key: string) => void }) {
  const cols = Math.min(HEAT_COLS, Math.max(...series.map((s) => s.points.length)));
  return (
    <OvSection
      eyebrow="DERS × DENEME"
      tone="violet"
      title="Son denemeler hücre hücre"
      desc={`Her dersin son ${cols} denemesi soldan sağa (en sağdaki en yeni). Hücre: net yüzdesi. Sağa doğru açılan renk gelişme, kararan renk gerileme demektir.`}
      right={<RatioLegend />}
      dataSection="brans:heat"
    >
      <div className="relative -mx-1 overflow-x-auto px-1">
        <table className="w-full min-w-[640px] border-separate border-spacing-1 text-xs">
          <thead>
            <tr className="text-[11px] font-semibold text-muted-foreground">
              <th className="pr-2 text-left">Ders</th>
              {Array.from({ length: cols }, (_, i) => (
                <th key={i} className="text-center font-medium">
                  {i === cols - 1 ? "son" : `${cols - 1 - i} önce`}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {series.map((s) => {
              const pts = s.points.slice(-cols);
              const pad = cols - pts.length;
              return (
                <tr key={s.key}>
                  <td className="pr-2">
                    <button
                      type="button"
                      onClick={() => onPick(s.key)}
                      className="flex items-center gap-1.5 whitespace-nowrap text-left text-[13px] font-semibold hover:underline"
                    >
                      <span className="size-2.5 rounded-full" style={{ background: colorOf(s) }} aria-hidden />
                      {nameOf(s)}
                    </button>
                  </td>
                  {Array.from({ length: pad }, (_, i) => (
                    <td key={`p${i}`} className="h-9 rounded-md bg-muted/40" />
                  ))}
                  {pts.map((p) => (
                    <td
                      key={p.exam_id}
                      className={cn(
                        "h-9 min-w-[48px] rounded-md text-center font-bold tabular-nums",
                        ratioClass(p.net_pct != null ? p.net_pct / 100 : null),
                      )}
                      title={`${shortDate(p.date)} · ${n1(p.net)} net / ${p.questions ?? "—"} soru · ${p.correct}D ${p.wrong}Y ${p.blank}B`}
                    >
                      {p.net_pct != null ? Math.round(p.net_pct) : "—"}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </OvSection>
  );
}

// ---------------------------------------------------------------- 6. ritim

function Rhythm({ ov }: { ov: DenemeOverview }) {
  const weeks = ov.weeks;
  const maxCount = Math.max(1, ...weeks.map((w) => w.count));
  const active = weeks.filter((w) => w.count > 0).length;
  const avg = weeks.reduce((a, w) => a + w.count, 0) / (weeks.length || 1);
  return (
    <OvSection
      eyebrow="DENEME RİTMİ"
      tone="emerald"
      title={`Son ${weeks.length} haftanın ${active}'${active === 1 ? "inde" : "sinde"} branş denemesi çözüldü`}
      desc={`Haftada ortalama ${n1(avg)} deneme. Sütun: o hafta çözülen deneme sayısı; altındaki değer haftanın ortalama net yüzdesi.`}
      dataSection="brans:rhythm"
    >
      <div className="grid grid-cols-8 items-end gap-2">
        {weeks.map((w, i) => (
          <div key={w.week_start} className="flex min-w-0 flex-col items-center gap-1">
            <span className="text-xs font-bold tabular-nums">{w.count || ""}</span>
            <div className="flex h-24 w-full items-end">
              <div
                className={cn(
                  "w-full rounded-t-md",
                  w.count === 0
                    ? "h-1 bg-muted"
                    : i === weeks.length - 1
                      ? "bg-emerald-700"
                      : "bg-emerald-600/60",
                )}
                style={w.count ? { height: `${(100 * w.count) / maxCount}%` } : undefined}
                title={`${shortDate(w.week_start)} haftası · ${w.count} deneme · ${w.subjects} ders`}
              />
            </div>
            <span className="text-[11px] font-semibold tabular-nums">{w.avg_net_pct != null ? p1(w.avg_net_pct) : "—"}</span>
            <span className="text-[10.5px] text-muted-foreground">{i === weeks.length - 1 ? "bu hafta" : shortDate(w.week_start)}</span>
          </div>
        ))}
      </div>
    </OvSection>
  );
}

// ---------------------------------------------------------------- 7. ders derin analizi

function DeepTip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { date: string; net: number; pct: number | null; q: number | null; c: number; w: number; b: number; min: number | null } }[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-md">
      <div className="font-bold">{shortDate(d.date)}</div>
      <div className="mt-1 tabular-nums">
        <b>{p1(d.pct)}</b> · {n1(d.net)} net{d.q ? ` / ${d.q} soru` : ""}
      </div>
      <div className="tabular-nums text-muted-foreground">
        {d.c} doğru · {d.w} yanlış · {d.b} boş
      </div>
      {d.min != null ? <div className="tabular-nums text-muted-foreground">{n1(d.min)} dk / soru</div> : null}
    </div>
  );
}

function MiniStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-muted/60 p-3">
      <div className="text-[11px] font-semibold text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-lg font-extrabold tabular-nums leading-tight">{value}</div>
      {sub ? <div className="text-[11px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

function SubjectDeepDive({
  s,
  series,
  onPick,
}: {
  s: DenemeAnalysisSeries;
  series: DenemeAnalysisSeries[];
  onPick: (key: string) => void;
}) {
  const color = colorOf(s);
  const data = s.points.map((p, i) => ({
    i: i + 1,
    date: p.date,
    net: p.net,
    pct: p.net_pct,
    q: p.questions,
    c: p.correct,
    w: p.wrong,
    b: p.blank,
    min: p.duration_minutes && p.questions ? p.duration_minutes / p.questions : null,
  }));
  const lastI = data.length;
  const proj =
    s.projected_net_pct != null && data.length
      ? [
          { i: lastI, proj: data[lastI - 1].pct },
          { i: lastI + 4, proj: s.projected_net_pct },
        ]
      : [];
  const lostW = s.lost_wrong_per_exam ?? 0;
  const lostB = s.lost_blank_per_exam ?? 0;
  const timed = data.filter((d) => d.min != null);

  return (
    <section
      id="brans-detail"
      className="flex scroll-mt-24 flex-col gap-5 rounded-2xl border-2 bg-card p-5 sm:p-6"
      style={{ borderColor: color }}
      data-section="brans:detail"
    >
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-bold tracking-wider text-muted-foreground">DERSİN DERİN ANALİZİ</div>
          <h3 className="mt-1 flex items-center gap-2 text-xl font-extrabold">
            <span className="size-3 rounded-full" style={{ background: color }} aria-hidden />
            {nameOf(s)}
            <span className="text-sm font-semibold text-muted-foreground">
              · {s.count} deneme · {shortDate(s.first_date)} – {shortDate(s.last_date)}
            </span>
          </h3>
        </div>
        {series.length > 1 ? (
          <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Ders seç">
            {series.map((x) => (
              <button
                key={x.key}
                type="button"
                role="tab"
                aria-selected={x.key === s.key}
                onClick={() => onPick(x.key)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[13px] font-semibold transition-colors",
                  x.key === s.key ? "border-foreground bg-foreground text-background" : "border-border hover:bg-muted",
                )}
              >
                <span className="size-2 rounded-full" style={{ background: colorOf(x) }} aria-hidden />
                {nameOf(x)}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        {/* Gidişat grafiği */}
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded-full" style={{ background: color }} aria-hidden /> net yüzdesi
            </span>
            {s.normal_low != null ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="h-3 w-4 rounded-sm bg-teal-600/20" aria-hidden /> normal aralık
              </span>
            ) : null}
            {proj.length ? (
              <span className="inline-flex items-center gap-1.5">
                <span className="w-4 border-t-2 border-dashed border-current" aria-hidden /> 4 deneme sonrası tahmin
              </span>
            ) : null}
          </div>
          <div className="relative -mx-1 overflow-x-auto px-1">
            <div className="h-[260px] min-w-[420px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart margin={{ top: 8, right: 16, bottom: 4, left: -8 }}>
                  <CartesianGrid stroke="currentColor" strokeOpacity={0.08} vertical={false} />
                  {s.normal_low != null && s.normal_high != null ? (
                    <ReferenceArea
                      y1={s.normal_low}
                      y2={s.normal_high}
                      fill="#0d9488"
                      fillOpacity={0.24}
                      stroke="#0d9488" strokeOpacity={0.5}
                      ifOverflow="extendDomain"
                    />
                  ) : null}
                  <XAxis
                    dataKey="i"
                    type="number"
                    domain={[1, proj.length ? lastI + 4 : Math.max(lastI, 2)]}
                    allowDecimals={false}
                    tickFormatter={(v: number) => (v > lastI ? `+${v - lastI}` : `${v}.`)}
                    tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
                    stroke="currentColor"
                    strokeOpacity={0.15}
                  />
                  <YAxis
                    domain={[0, 100]}
                    ticks={[0, 25, 50, 75, 100]}
                    tickFormatter={(v: number) => `%${v}`}
                    tick={{ fontSize: 11, fill: "currentColor", opacity: 0.6 }}
                    stroke="currentColor"
                    strokeOpacity={0.15}
                    width={44}
                  />
                  <Tooltip content={<DeepTip />} cursor={{ stroke: "currentColor", strokeOpacity: 0.2 }} />
                  <Line
                    data={data}
                    dataKey="pct"
                    stroke={color}
                    strokeWidth={2}
                    dot={{ r: 4, strokeWidth: 2, stroke: "var(--card)", fill: color }}
                    activeDot={{ r: 6 }}
                    isAnimationActive={false}
                  />
                  {proj.length ? (
                    <Line
                      data={proj}
                      dataKey="proj"
                      stroke={color}
                      strokeWidth={2}
                      strokeDasharray="5 4"
                      dot={false}
                      activeDot={false}
                      isAnimationActive={false}
                    />
                  ) : null}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
          <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
            {s.projected_net_pct != null
              ? `Böyle giderse 4 deneme sonra net yüzdesi ~${p1(s.projected_net_pct)} olur (son denemelerin doğrusu; kesin değil, yön gösterir).`
              : "Tahmin için en az 4 deneme gerekir."}
            {s.decline_run >= 3 ? ` Son ${s.decline_run + 1} denemede net üst üste düştü.` : ""}
          </p>
        </div>

        {/* Ölçüler */}
        <div className="flex min-w-0 flex-col gap-3">
          <div className="grid grid-cols-2 gap-2.5">
            <MiniStat label="Ortalama net" value={n1(s.avg_net)} sub={`${n1(s.avg_questions)} soruda · ${p1(s.avg_net_pct)}`} />
            <MiniStat label="Son deneme" value={p1(s.last_net_pct)} sub={daysAgo(s.days_since_last)} />
            <MiniStat label="En iyi" value={p1(s.best_net_pct)} sub={shortDate(s.best_date)} />
            <MiniStat label="En düşük" value={p1(s.worst_net_pct)} sub={shortDate(s.worst_date)} />
            <MiniStat
              label="Soru başına süre"
              value={s.min_per_question != null ? `${n1(s.min_per_question)} dk` : "—"}
              sub={s.timed_count ? `${s.timed_count} denemede süre girilmiş` : "süre girilmemiş"}
            />
            <MiniStat
              label="İstikrar"
              value={s.consistency ? CONSISTENCY[s.consistency].label : "—"}
              sub={s.stdev_net_pct != null ? `eğilimden ±${n1(s.stdev_net_pct)} puan` : "en az 3 deneme"}
            />
          </div>

          <div className="rounded-xl border border-border p-3">
            <div className="text-xs font-bold">Deneme başına kaçan net</div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <span className="text-2xl font-extrabold tabular-nums">{n1(lostW + lostB)}</span>
              <span className="text-xs text-muted-foreground">net · tam puana göre</span>
            </div>
            <div className="mt-2 flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-muted" aria-hidden>
              <div className="bg-rose-600" style={{ width: `${lostW + lostB ? (100 * lostW) / (lostW + lostB) : 0}%` }} />
              <div className="bg-slate-400" style={{ width: `${lostW + lostB ? (100 * lostB) / (lostW + lostB) : 0}%` }} />
            </div>
            <div className="mt-1.5 flex justify-between text-[11.5px]">
              <span className="font-semibold text-rose-800">
                yanlışlar {n1(lostW)} net ({s.penalty ?? 4} yanlış 1 doğruyu götürür)
              </span>
              <span className="font-semibold text-muted-foreground">boşlar {n1(lostB)}</span>
            </div>
            <p className="mt-1.5 text-[11.5px] text-muted-foreground">
              {lostW >= lostB * 1.5
                ? "Net kaybının çoğu yanlıştan: bilmediği soruya girmek ya da dikkat hatası."
                : lostB >= lostW * 1.5
                  ? "Net kaybının çoğu boştan: süre yetmiyor ya da çekiniyor olabilir."
                  : "Kayıp yanlış ve boş arasında dengeli."}
            </p>
          </div>
        </div>
      </div>

      {/* Deneme deneme D/Y/B */}
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="text-sm font-bold">Deneme deneme doğru · yanlış · boş</div>
          <div className="flex gap-3 text-[11.5px] font-semibold">
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-teal-700" aria-hidden />doğru</span>
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-rose-600" aria-hidden />yanlış</span>
            <span className="inline-flex items-center gap-1"><span className="size-2.5 rounded-sm bg-slate-400" aria-hidden />boş</span>
          </div>
        </div>
        <div className="relative -mx-1 overflow-x-auto px-1">
          <div className="flex min-w-max items-end gap-2">
            {data.slice(-12).map((d) => {
              const tot = d.c + d.w + d.b || 1;
              return (
                <div key={`${d.date}-${d.i}`} className="flex w-14 flex-col items-center gap-1">
                  <span className="text-[11px] font-bold tabular-nums">{p1(d.pct)}</span>
                  <div
                    className="flex h-28 w-7 flex-col-reverse gap-0.5 overflow-hidden rounded-md"
                    title={`${shortDate(d.date)} · ${d.c} doğru · ${d.w} yanlış · ${d.b} boş${d.min != null ? ` · ${n1(d.min)} dk/soru` : ""}`}
                  >
                    <div className="bg-teal-700" style={{ height: `${(100 * d.c) / tot}%` }} />
                    <div className="bg-rose-600" style={{ height: `${(100 * d.w) / tot}%` }} />
                    <div className="bg-slate-400" style={{ height: `${(100 * d.b) / tot}%` }} />
                  </div>
                  <span className="text-[10.5px] text-muted-foreground">{shortDate(d.date)}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Doğruluk kıyası + süre */}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border p-4">
          <div className="text-sm font-bold">Aynı dersin üç yerdeki doğruluğu</div>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">Son 90 gün · doğru ÷ (doğru + yanlış)</p>
          <div className="mt-3">
            <AccBars s={s} />
          </div>
          <p className="mt-3 text-[12px] leading-relaxed">
            {s.test_accuracy_pct != null && s.accuracy_pct != null
              ? s.test_accuracy_pct - s.accuracy_pct >= 15
                ? `Testlerde ${p1(s.test_accuracy_pct)}, denemede ${p1(s.accuracy_pct)}: konu biliniyor, süre baskısında ya da karma soruda zorlanıyor olabilir.`
                : s.accuracy_pct - s.test_accuracy_pct >= 10
                  ? "Denemede testlerden daha isabetli: deneme ortamı ona iyi geliyor."
                  : "Test ve deneme doğruluğu birbirine yakın: öğrendiği denemeye taşınıyor."
              : "Kıyas için bu derste sonucu girilmiş en az 10 test sorusu gerekir."}
          </p>
          {s.legacy_accuracy_pct != null ? (
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              Eski toplu kayıtlar ({s.legacy_rows}) dahil doğruluk: {p1(s.combined_accuracy_pct)}.
            </p>
          ) : null}
        </div>
        <div className="rounded-xl border border-border p-4">
          <div className="text-sm font-bold">Süre kullanımı</div>
          <p className="mt-0.5 text-[11.5px] text-muted-foreground">Soru başına dakika — öğrenci süreyi girdiyse</p>
          {timed.length >= 2 ? (
            <div className="mt-3 flex items-end gap-1.5">
              {timed.slice(-12).map((d) => {
                const maxMin = Math.max(...timed.map((t) => t.min ?? 0)) || 1;
                return (
                  <div key={`${d.date}-${d.i}`} className="flex flex-1 flex-col items-center gap-1">
                    <div className="flex h-20 w-full items-end">
                      <div
                        className="w-full rounded-t-md bg-cyan-700/70"
                        style={{ height: `${(100 * (d.min ?? 0)) / maxMin}%` }}
                        title={`${shortDate(d.date)} · ${n1(d.min)} dk/soru · ${p1(d.pct)}`}
                      />
                    </div>
                    <span className="text-[10px] tabular-nums text-muted-foreground">{n1(d.min)}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-3 text-[12px] text-muted-foreground">
              Süre bilgisi için en az 2 denemede süre girilmeli (öğrenci sonuç penceresinde girer).
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
