"use client";

/**
 * Deneme analizi — alt sekme içerikleri (Faz 1, 2026-10-02).
 *
 * Genel Bakış · Gelişim · Sınav Davranışı + ortak bölüm çerçevesi ve paylaşma
 * menüsü. Hepsi TEK sınav türüne süzülmüş satırlarla (DESC: en yeni ilk) çalışır;
 * farklı türler (TYT/AYT/LGS) ayrı ölçekte olduğu için karıştırılmaz.
 * Yeni veri gerekmez: deneme listesi ucunun döndürdüğü ders kırılımı + puan.
 */

import * as React from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  ArrowDownRight,
  ArrowUpRight,
  ClipboardCopy,
  Eye,
  Lightbulb,
  MessageCircle,
  Minus,
  Printer,
  Share2,
} from "lucide-react";
import { toast } from "sonner";

import { ExamAveragesButton } from "@/components/teacher/exams/exam-averages-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  buildInsights,
  buildShareText,
  examPrintUrl,
  fmtInt,
  fmtNet,
  fmtSigned,
  fmtTRDate,
  percentile,
  sectionPenalty,
  subjectNetIn,
} from "@/lib/exam-format";
import type { ExamResultRow } from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

// Saf yardımcılar lib/exam-format'ta (yazdırma sayfası da kullanır); buradan da
// dışa açılır ki sekme dosyaları tek yerden alsın.
export {
  buildInsights,
  buildShareText,
  examPrintUrl,
  fmtNet,
  fmtSigned,
  fmtTRDate,
  percentile,
  previousExam,
  sectionPenalty,
  subjectNetIn,
} from "@/lib/exam-format";

// ---------------------------------------------------------------- bölüm çerçevesi

export function ExamSection({
  icon: Icon,
  title,
  description,
  actions,
  children,
  className,
}: {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border border-border bg-card", className)}>
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
        <div className="min-w-0">
          <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            {Icon ? <Icon className="size-4 text-cyan-700 dark:text-cyan-400" /> : null}
            {title}
          </h4>
          {description ? (
            <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Delta({ value, suffix = "" }: { value: number | null; suffix?: string }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  if (Math.abs(value) < 0.005) {
    return (
      <span className="inline-flex items-center gap-0.5 text-muted-foreground">
        <Minus className="size-3" aria-hidden />0
      </span>
    );
  }
  const up = value > 0;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 font-medium tabular-nums",
        up ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400",
      )}
    >
      {up ? (
        <ArrowUpRight className="size-3.5" aria-hidden />
      ) : (
        <ArrowDownRight className="size-3.5" aria-hidden />
      )}
      {fmtSigned(value)}
      {suffix}
    </span>
  );
}

// ---------------------------------------------------------------- paylaşma

export function ExamShareMenu({
  row,
  prev,
  studentId,
  studentName,
  size = "sm",
}: {
  row: ExamResultRow;
  prev: ExamResultRow | null;
  studentId: number;
  studentName?: string | null;
  size?: "sm" | "default";
}) {
  const text = () => buildShareText(row, prev, studentName);
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        size={size}
        variant="outline"
        onClick={() => window.open(examPrintUrl(studentId, row.id), "_blank", "noopener")}
        title="A4 deneme karnesi — yazdır ya da PDF olarak kaydet"
      >
        <Printer className="size-4" aria-hidden />
        Yazdır / PDF
      </Button>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button size={size} variant="outline">
            <Share2 className="size-4" aria-hidden />
            Paylaş
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64">
          <DropdownMenuItem
            onSelect={() =>
              window.open(`https://wa.me/?text=${encodeURIComponent(text())}`, "_blank", "noopener")
            }
          >
            <MessageCircle className="size-4 text-emerald-600" aria-hidden />
            <span>
              WhatsApp ile gönder
              <span className="block text-[11px] text-muted-foreground">
                Özet metni hazır açılır, kişiyi sen seçersin
              </span>
            </span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={async () => {
              try {
                await navigator.clipboard.writeText(text());
                toast.success("Deneme özeti kopyalandı");
              } catch {
                toast.error("Kopyalanamadı");
              }
            }}
          >
            <ClipboardCopy className="size-4" aria-hidden />
            <span>
              Özeti kopyala
              <span className="block text-[11px] text-muted-foreground">
                E-posta ya da mesaja yapıştırmak için
              </span>
            </span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => window.open(examPrintUrl(studentId, row.id), "_blank", "noopener")}
          >
            <Printer className="size-4" aria-hidden />
            <span>
              Karneyi PDF olarak kaydet
              <span className="block text-[11px] text-muted-foreground">
                Yazdır penceresinde “PDF olarak kaydet”i seç
              </span>
            </span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}

// ---------------------------------------------------------------- Genel Bakış

export function OverviewTab({
  rows,
  studentId,
  studentName,
  onOpenDetail,
}: {
  rows: ExamResultRow[];
  /** null → öğrenci yüzeyi (paylaş/yazdır menüsü gizli). */
  studentId: number | null;
  studentName?: string | null;
  onOpenDetail: (row: ExamResultRow) => void;
}) {
  const last = rows[0];
  if (!last) return null;
  const prev = rows[1] ?? null;
  const insights = buildInsights(rows);
  const nets = rows.map((r) => r.net);
  const avg = nets.reduce((a, b) => a + b, 0) / nets.length;
  const best = Math.max(...nets);
  const pctl = percentile(last);

  return (
    <div className="space-y-4">
      <ExamSection
        icon={Eye}
        title="Son deneme"
        description={
          <>
            {last.title} · {fmtTRDate(last.exam_date)} · {last.section_label}
          </>
        }
        actions={
          <>
            <Button size="sm" onClick={() => onOpenDetail(last)}>
              <Eye className="size-4" aria-hidden />
              Deneme detayı
            </Button>
            {studentId != null ? (
              <ExamShareMenu row={last} prev={prev} studentId={studentId} studentName={studentName} />
            ) : null}
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi label="Toplam net" hint="Doğru − yanlış/4 (LGS: /3)">
            <span className="text-3xl font-semibold tabular-nums">{fmtNet(last.net)}</span>
            <span className="text-xs">
              <Delta value={prev ? last.net - prev.net : null} />{" "}
              <span className="text-muted-foreground">önceki denemeye göre</span>
            </span>
          </Kpi>
          <Kpi label="Doğru · Yanlış · Boş" hint={`${last.total_questions} soru`}>
            <span className="text-lg font-semibold tabular-nums">
              <span className="text-emerald-700 dark:text-emerald-400">{last.total_correct}</span>
              {" · "}
              <span className="text-rose-700 dark:text-rose-400">{last.total_wrong}</span>
              {" · "}
              <span className="text-muted-foreground">{last.total_blank}</span>
            </span>
            <DybBar d={last.total_correct} y={last.total_wrong} b={last.total_blank} />
          </Kpi>
          <Kpi label="Puan" hint="Karneden okunur">
            <span className="text-2xl font-semibold tabular-nums">
              {last.score?.score != null ? fmtNet(last.score.score) : "—"}
            </span>
            {last.score?.score == null ? (
              <span className="text-[11px] text-muted-foreground">
                Elle girilen ya da puan yazmayan karnede yok
              </span>
            ) : null}
          </Kpi>
          <Kpi label="Sıralama" hint="Karnedeki genel sıralama">
            <span className="text-2xl font-semibold tabular-nums">
              {last.score?.rank_overall ? fmtInt(last.score.rank_overall) : "—"}
            </span>
            <span className="text-[11px] text-muted-foreground">
              {last.score?.participants
                ? `${fmtInt(last.score.participants)} katılımcı${pctl != null ? ` · ilk %${String(pctl).replace(".", ",")}` : ""}`
                : "Karnede sıralama bilgisi yok"}
            </span>
          </Kpi>
        </div>

        {insights.length ? (
          <div className="mt-4 rounded-lg border border-cyan-200 bg-cyan-50 p-3 dark:border-cyan-500/30 dark:bg-cyan-500/10">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-cyan-950 dark:text-cyan-100">
              <Lightbulb className="size-3.5" aria-hidden />
              Öne çıkanlar
            </p>
            <ul className="space-y-1 text-sm text-cyan-950 dark:text-cyan-100">
              {insights.map((t) => (
                <li key={t} className="flex gap-2">
                  <span aria-hidden>•</span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </ExamSection>

      {last.subjects.length ? (
        <ExamSection
          title="Ders bazında sonuç"
          description={
            last.averages
              ? `Son denemede her dersin doğru, yanlış, boş ve neti; ${last.averages.label.toLocaleLowerCase("tr-TR")} ile fark ve önceki aynı tür denemeye göre fark.`
              : "Son denemede her dersin doğru, yanlış, boş ve neti; son sütun önceki aynı tür denemeye göre net farkı."
          }
          actions={studentId != null ? <ExamAveragesButton row={last} /> : null}
        >
          <SubjectTable row={last} prev={prev} />
        </ExamSection>
      ) : null}

      <ExamSection
        title={`${last.section_label} denemelerinin özeti`}
        description="Seçili dönemde bu türdeki tüm denemeler."
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Kpi label="Deneme sayısı">
            <span className="text-2xl font-semibold tabular-nums">{rows.length}</span>
          </Kpi>
          <Kpi label="Ortalama net">
            <span className="text-2xl font-semibold tabular-nums">{fmtNet(avg)}</span>
          </Kpi>
          <Kpi label="En iyi net">
            <span className="text-2xl font-semibold tabular-nums text-emerald-700 dark:text-emerald-400">
              {fmtNet(best)}
            </span>
          </Kpi>
        </div>
      </ExamSection>
    </div>
  );
}

function Kpi({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-background p-3">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      {children}
      {hint ? <span className="text-[11px] text-muted-foreground">{hint}</span> : null}
    </div>
  );
}

export function DybBar({ d, y, b }: { d: number; y: number; b: number }) {
  const t = d + y + b;
  if (!t) return null;
  return (
    <div
      className="flex h-2 w-full overflow-hidden rounded-full bg-muted"
      title={`${d} doğru · ${y} yanlış · ${b} boş`}
    >
      <div className="bg-emerald-500" style={{ width: `${(d / t) * 100}%` }} />
      <div className="bg-rose-500" style={{ width: `${(y / t) * 100}%` }} />
      <div className="bg-slate-300 dark:bg-slate-600" style={{ width: `${(b / t) * 100}%` }} />
    </div>
  );
}

export function SubjectTable({ row, prev }: { row: ExamResultRow; prev: ExamResultRow | null }) {
  const av = row.averages ?? null;
  const hasAvg = !!av && (Object.keys(av.subjects).length > 0 || av.total != null);
  return (
    <div className="relative overflow-x-auto">
      <table className={cn("w-full text-sm", hasAvg ? "min-w-[680px]" : "min-w-[520px]")}>
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="py-2 pr-2 font-medium">Ders</th>
            <th className="px-2 py-2 text-right font-medium">Doğru</th>
            <th className="px-2 py-2 text-right font-medium">Yanlış</th>
            <th className="px-2 py-2 text-right font-medium">Boş</th>
            <th className="px-2 py-2 text-right font-medium">Net</th>
            {hasAvg ? (
              <>
                <th className="px-2 py-2 text-right font-medium" title={av!.label}>
                  {av!.label}
                </th>
                <th className="px-2 py-2 text-right font-medium">Ortalamaya göre</th>
              </>
            ) : null}
            <th className="py-2 pl-2 text-right font-medium">Önceki denemeye göre</th>
          </tr>
        </thead>
        <tbody>
          {row.subjects.map((s) => {
            const p = subjectNetIn(prev, s.name);
            return (
              <tr key={s.name} className="border-b border-border/60 last:border-0">
                <td className="py-2 pr-2 text-foreground">{s.name}</td>
                <td className="px-2 py-2 text-right tabular-nums text-emerald-700 dark:text-emerald-400">
                  {s.correct}
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-rose-700 dark:text-rose-400">
                  {s.wrong}
                </td>
                <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">{s.blank}</td>
                <td className="px-2 py-2 text-right font-semibold tabular-nums">{fmtNet(s.net)}</td>
                {hasAvg ? (
                  <>
                    <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">
                      {fmtNet(av!.subjects[s.name])}
                    </td>
                    <td className="px-2 py-2 text-right text-xs">
                      <Delta value={av!.subjects[s.name] == null ? null : s.net - av!.subjects[s.name]} />
                    </td>
                  </>
                ) : null}
                <td className="py-2 pl-2 text-right text-xs">
                  <Delta value={p == null ? null : s.net - p} />
                </td>
              </tr>
            );
          })}
          <tr className="border-t-2 border-border font-semibold">
            <td className="py-2 pr-2">Toplam</td>
            <td className="px-2 py-2 text-right tabular-nums">{row.total_correct}</td>
            <td className="px-2 py-2 text-right tabular-nums">{row.total_wrong}</td>
            <td className="px-2 py-2 text-right tabular-nums">{row.total_blank}</td>
            <td className="px-2 py-2 text-right tabular-nums">{fmtNet(row.net)}</td>
            {hasAvg ? (
              <>
                <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">{fmtNet(av!.total)}</td>
                <td className="px-2 py-2 text-right text-xs">
                  <Delta value={av!.total == null ? null : row.net - av!.total} />
                </td>
              </>
            ) : null}
            <td className="py-2 pl-2 text-right text-xs">
              <Delta value={prev ? row.net - prev.net : null} />
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------- Gelişim

const MAX_COLS = 8;

export function ProgressTab({ rows }: { rows: ExamResultRow[] }) {
  // kronolojik (eski → yeni), son MAX_COLS deneme
  const chrono = React.useMemo(() => [...rows].reverse().slice(-MAX_COLS), [rows]);
  const subjects = React.useMemo(() => {
    const seen: string[] = [];
    for (const r of chrono) {
      for (const s of r.subjects) if (!seen.includes(s.name)) seen.push(s.name);
    }
    return seen;
  }, [chrono]);
  const points = chrono.map((r) => ({
    date: fmtTRDate(r.exam_date).slice(0, 5),
    net: r.net,
    title: r.title,
  }));

  if (rows.length < 2) {
    return (
      <ExamSection title="Gelişim" description="Aynı türden en az 2 deneme olunca gelişim tabloları burada görünür.">
        <p className="text-sm text-muted-foreground">
          Şimdilik bu türde tek deneme var. Yeni deneme ekledikçe toplam net çizgisi ve ders ders
          karşılaştırma tablosu oluşur.
        </p>
      </ExamSection>
    );
  }

  return (
    <div className="space-y-4">
      <ExamSection
        title="Toplam net gelişimi"
        description={`Son ${chrono.length} denemenin toplam neti. Noktanın üzerine gelince deneme adı görünür.`}
      >
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 5, right: 12, bottom: 0, left: -16 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                formatter={(v) => [fmtNet(Number(v)), "Net"]}
                labelFormatter={(_l, p) => p?.[0]?.payload?.title ?? ""}
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
              />
              <Line type="monotone" dataKey="net" stroke="#0e7490" strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </ExamSection>

      {subjects.length ? (
        <ExamSection
          title="Ders × deneme net tablosu"
          description="Her satır bir ders, her sütun bir deneme (eskiden yeniye). Son sütun ilk ve son deneme arasındaki fark — hangi ders yükseliyor, hangisi düşüyor bir bakışta."
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  <th className="py-2 pr-2 text-left font-medium">Ders</th>
                  {chrono.map((r) => (
                    <th key={r.id} className="px-2 py-2 text-right font-medium" title={r.title}>
                      {fmtTRDate(r.exam_date).slice(0, 5)}
                    </th>
                  ))}
                  <th className="py-2 pl-2 text-right font-medium">Değişim</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((name) => {
                  const vals = chrono.map((r) => subjectNetIn(r, name));
                  const known = vals.filter((v): v is number => v != null);
                  const change = known.length >= 2 ? known[known.length - 1] - known[0] : null;
                  return (
                    <tr key={name} className="border-b border-border/60 last:border-0">
                      <td className="py-2 pr-2 text-foreground">{name}</td>
                      {vals.map((v, i) => (
                        <td key={i} className="px-2 py-2 text-right tabular-nums">
                          {v == null ? <span className="text-muted-foreground">—</span> : fmtNet(v)}
                        </td>
                      ))}
                      <td className="py-2 pl-2 text-right text-xs">
                        <Delta value={change} />
                      </td>
                    </tr>
                  );
                })}
                <tr className="border-t-2 border-border font-semibold">
                  <td className="py-2 pr-2">Toplam</td>
                  {chrono.map((r) => (
                    <td key={r.id} className="px-2 py-2 text-right tabular-nums">
                      {fmtNet(r.net)}
                    </td>
                  ))}
                  <td className="py-2 pl-2 text-right text-xs">
                    <Delta value={chrono[chrono.length - 1].net - chrono[0].net} />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </ExamSection>
      ) : null}

      <ExamSection
        title="Doğru · yanlış · boş dağılımı"
        description="Her denemede soruların ne kadarı doğru (yeşil), yanlış (kırmızı) ve boş (gri). Net kaybının yanlıştan mı boştan mı geldiğini gösterir."
      >
        <ul className="space-y-2.5">
          {[...chrono].reverse().map((r) => (
            <li key={r.id} className="grid grid-cols-[minmax(0,12rem)_1fr] items-center gap-3 text-sm sm:grid-cols-[minmax(0,16rem)_1fr]">
              <span className="min-w-0 text-xs">
                <span className="block text-foreground">{r.title}</span>
                <span className="text-muted-foreground">
                  {fmtTRDate(r.exam_date)} · {r.total_correct}D {r.total_wrong}Y {r.total_blank}B
                </span>
              </span>
              <DybBar d={r.total_correct} y={r.total_wrong} b={r.total_blank} />
            </li>
          ))}
        </ul>
      </ExamSection>
    </div>
  );
}

// ---------------------------------------------------------------- Sınav Davranışı

function tendency(wrong: number, blank: number): { label: string; tone: string } | null {
  const t = wrong + blank;
  if (t < 4) return null;
  const share = wrong / t;
  if (share < 0.35) {
    return {
      label: "Temkinli — emin olmadığını boş bırakıyor",
      tone: "bg-sky-600 text-white",
    };
  }
  if (share > 0.7) {
    return {
      label: "Riskli — emin olmadığını da işaretliyor",
      tone: "bg-amber-600 text-white",
    };
  }
  return { label: "Dengeli", tone: "bg-emerald-600 text-white" };
}

export function BehaviorTab({ rows }: { rows: ExamResultRow[] }) {
  const section = rows[0]?.section;
  const p = section ? sectionPenalty(section) : 4;
  const agg = React.useMemo(() => {
    const m = new Map<string, { d: number; y: number; b: number; n: number }>();
    for (const r of rows) {
      for (const s of r.subjects) {
        const e = m.get(s.name) ?? { d: 0, y: 0, b: 0, n: 0 };
        e.d += s.correct;
        e.y += s.wrong;
        e.b += s.blank;
        e.n += 1;
        m.set(s.name, e);
      }
    }
    return [...m.entries()].map(([name, v]) => ({ name, ...v }));
  }, [rows]);
  const tot = agg.reduce(
    (a, s) => ({ d: a.d + s.d, y: a.y + s.y, b: a.b + s.b }),
    { d: 0, y: 0, b: 0 },
  );
  const overall = tendency(tot.y, tot.b);

  if (!agg.length) {
    return (
      <ExamSection title="Sınav davranışı" description="Ders kırılımı olan denemelerden hesaplanır.">
        <p className="text-sm text-muted-foreground">
          Bu türdeki denemelerde ders kırılımı yok. PDF&apos;ten aktarılan ya da ders ders girilen
          denemelerde burada boş bırakma ve işaretleme eğilimi görünür.
        </p>
      </ExamSection>
    );
  }

  return (
    <div className="space-y-4">
      <ExamSection
        title="İşaretleme eğilimi"
        description={
          <>
            Kaçan soruların (yanlış + boş) ne kadarı yanlış işaretlenmiş? Yanlış payı yüksekse
            öğrenci emin olmadığı soruları da işaretliyor (her 4 yanlış 1 doğruyu götürür);
            boş payı yüksekse bildiği konuda bile çekiniyor ya da süresi yetmiyor olabilir.
            Seçili dönemdeki {rows.length} denemenin toplamı.
          </>
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          {overall ? (
            <span className={cn("rounded-md px-2.5 py-1 text-sm font-semibold", overall.tone)}>
              Genel: {overall.label}
            </span>
          ) : null}
          <span className="text-sm text-muted-foreground">
            Toplam {tot.y} yanlış · {tot.b} boş
          </span>
        </div>
      </ExamSection>

      <ExamSection
        title="Ders bazında kaçan sorular"
        description={`“Kaçan net / deneme”: o dersteki yanlış ve boşlar doğru olsaydı deneme başına kazanılacak net (yanlış başına 1 + 1/${p}, boş başına 1). En büyük kayıp en üstte.`}
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-2 font-medium">Ders</th>
                <th className="px-2 py-2 text-right font-medium">Soru</th>
                <th className="px-2 py-2 text-right font-medium">Yanlış</th>
                <th className="px-2 py-2 text-right font-medium">Boş</th>
                <th className="px-2 py-2 text-right font-medium">Boş oranı</th>
                <th className="px-2 py-2 text-right font-medium">Kaçan net / deneme</th>
                <th className="py-2 pl-2 font-medium">Eğilim</th>
              </tr>
            </thead>
            <tbody>
              {agg
                .map((s) => ({
                  ...s,
                  total: s.d + s.y + s.b,
                  lost: (s.y * (1 + 1 / p) + s.b) / Math.max(s.n, 1),
                }))
                .sort((a, b) => b.lost - a.lost)
                .map((s) => {
                  const t = tendency(s.y, s.b);
                  return (
                    <tr key={s.name} className="border-b border-border/60 last:border-0">
                      <td className="py-2 pr-2 text-foreground">{s.name}</td>
                      <td className="px-2 py-2 text-right tabular-nums">{s.total}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-rose-700 dark:text-rose-400">{s.y}</td>
                      <td className="px-2 py-2 text-right tabular-nums text-muted-foreground">{s.b}</td>
                      <td className="px-2 py-2 text-right tabular-nums">
                        %{s.total ? Math.round((s.b / s.total) * 100) : 0}
                      </td>
                      <td className="px-2 py-2 text-right font-semibold tabular-nums">{fmtNet(s.lost)}</td>
                      <td className="py-2 pl-2">
                        {t ? (
                          <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium", t.tone)}>
                            {t.label.split(" — ")[0]}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">az veri</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      </ExamSection>

      <ExamSection
        title="Denemeden denemeye boş ve yanlış"
        description="Boşlar artıyorsa süre yönetimi, yanlışlar artıyorsa dikkat ya da konu eksiği konuşulabilir. Testin sonlarına doğru düşüş için deneme detayına bak."
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-2 font-medium">Deneme</th>
                <th className="px-2 py-2 text-right font-medium">Yanlış</th>
                <th className="px-2 py-2 text-right font-medium">Boş</th>
                <th className="py-2 pl-2 text-right font-medium">Net</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const prevR = rows[i + 1];
                return (
                  <tr key={r.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2 pr-2">
                      <span className="block text-foreground">{r.title}</span>
                      <span className="text-xs text-muted-foreground">{fmtTRDate(r.exam_date)}</span>
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {r.total_wrong}
                      {prevR ? (
                        <span className="ml-1 text-[11px] text-muted-foreground">
                          ({r.total_wrong - prevR.total_wrong >= 0 ? "+" : ""}
                          {r.total_wrong - prevR.total_wrong})
                        </span>
                      ) : null}
                    </td>
                    <td className="px-2 py-2 text-right tabular-nums">
                      {r.total_blank}
                      {prevR ? (
                        <span className="ml-1 text-[11px] text-muted-foreground">
                          ({r.total_blank - prevR.total_blank >= 0 ? "+" : ""}
                          {r.total_blank - prevR.total_blank})
                        </span>
                      ) : null}
                    </td>
                    <td className="py-2 pl-2 text-right font-semibold tabular-nums">{fmtNet(r.net)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </ExamSection>
    </div>
  );
}
