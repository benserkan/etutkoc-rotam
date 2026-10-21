import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { StudentExamsResponse } from "@/lib/types/student";
import type { ExamResultRow } from "@/lib/types/teacher";
import { PrintBrandHeader, fmtLongDate, getPrintBrand } from "@/components/print/print-brand";
import { PrintButton } from "./print-button";

/**
 * /student/exams/print — deneme sonuçlarım, A4 dikey.
 *
 * İki bölüm: (1) karne / elle girilen denemeler (tür bazlı, ders kırılımlı),
 * (2) programdaki branş denemeleri (görevden girilen sonuçlar). Netler yalnız aynı
 * türde kıyaslanır — her tür ayrı tablo.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Deneme Sonuçlarım — Yazdır" };

function fmt(n: number): string {
  return n.toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}
function short(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function groupBy(rows: ExamResultRow[], key: (r: ExamResultRow) => string) {
  const map = new Map<string, ExamResultRow[]>();
  for (const r of rows) map.set(key(r), [...(map.get(key(r)) ?? []), r]);
  return Array.from(map.entries());
}

export default async function StudentExamsPrintPage() {
  let data: StudentExamsResponse | null = null;
  try {
    data = await apiServer<StudentExamsResponse>("/api/v2/student/exams");
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  const brand = await getPrintBrand();
  const today = new Date().toISOString().slice(0, 10);

  if (!data) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Deneme Sonuçlarım</h1>
        <p className="mt-3 text-stone-600">Denemeler yüklenemedi.</p>
      </main>
    );
  }
  const karne = [...data.rows].sort((a, b) => a.exam_date.localeCompare(b.exam_date));
  const program = [...(data.program_rows ?? [])].sort((a, b) => a.exam_date.localeCompare(b.exam_date));

  return (
    <main className="mx-auto w-full max-w-[800px] bg-white px-8 py-6 text-stone-900 print:max-w-none print:px-0 print:py-0">
      <style>{`
        @media print {
          @page { size: A4 portrait; margin: 12mm; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>
      <div className="no-print mb-4 flex items-center justify-between gap-3">
        <PrintButton />
        <span className="text-xs text-stone-400">Dikey A4</span>
      </div>

      <PrintBrandHeader
        title="Deneme Sonuçlarım"
        subtitle={`${fmtLongDate(today)} itibarıyla`}
        studentName={brand.studentName}
        instName={brand.instName}
        logoUrl={brand.logoUrl}
        right={
          <div className="text-stone-600">
            <b className="text-stone-900">{karne.length}</b> deneme
            {program.length > 0 ? <> · <b className="text-stone-900">{program.length}</b> branş denemesi</> : null}
          </div>
        }
      />

      {karne.length === 0 && program.length === 0 ? (
        <p className="mt-6 text-sm italic text-stone-500">Henüz deneme sonucu yok.</p>
      ) : null}

      {groupBy(karne, (r) => r.series_label ?? r.section_label).map(([label, rows]) => (
        <ExamTable key={label} title={label} rows={rows} withSubjects />
      ))}

      {program.length > 0 ? (
        <>
          <h2 className="mt-6 border-b border-stone-300 pb-0.5 text-xs font-bold uppercase tracking-wider text-indigo-800">
            Programdaki branş denemeleri
          </h2>
          {groupBy(program, (r) => r.series_label ?? r.section_label).map(([label, rows]) => (
            <ExamTable key={label} title={label} rows={rows} />
          ))}
        </>
      ) : null}

      <p className="mt-6 text-[10px] text-stone-400">
        Netler yalnız aynı türdeki denemelerle kıyaslanır. Net = Doğru − Yanlış ÷ ceza (LGS 3, YKS 4).
      </p>
    </main>
  );
}

function ExamTable({ title, rows, withSubjects = false }: { title: string; rows: ExamResultRow[]; withSubjects?: boolean }) {
  const best = Math.max(...rows.map((r) => r.net));
  return (
    <section className="mt-4 break-inside-avoid">
      <h3 className="mb-1 text-sm font-bold text-stone-800">
        {title} <span className="text-[11px] font-normal text-stone-500">· {rows.length} deneme · en iyi {fmt(best)} net</span>
      </h3>
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr className="bg-stone-100 text-left text-stone-600">
            <th className="border border-stone-300 px-1.5 py-1">Tarih</th>
            <th className="border border-stone-300 px-1.5 py-1">Deneme</th>
            <th className="border border-stone-300 px-1.5 py-1 text-right">D</th>
            <th className="border border-stone-300 px-1.5 py-1 text-right">Y</th>
            <th className="border border-stone-300 px-1.5 py-1 text-right">B</th>
            <th className="border border-stone-300 px-1.5 py-1 text-right">Net</th>
            <th className="border border-stone-300 px-1.5 py-1 text-right">Fark</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const prev = i > 0 ? rows[i - 1].net : null;
            const diff = prev == null ? null : r.net - prev;
            return (
              <tr key={r.id} className="align-top">
                <td className="whitespace-nowrap border border-stone-300 px-1.5 py-1 tabular-nums">{short(r.exam_date)}</td>
                <td className="border border-stone-300 px-1.5 py-1">
                  <div className="font-medium">{r.title}</div>
                  {withSubjects && r.subjects.length > 0 ? (
                    <div className="mt-0.5 text-[10px] text-stone-600">
                      {r.subjects.map((s) => `${s.name} ${fmt(s.net)}`).join(" · ")}
                    </div>
                  ) : null}
                </td>
                <td className="border border-stone-300 px-1.5 py-1 text-right tabular-nums">{r.total_correct}</td>
                <td className="border border-stone-300 px-1.5 py-1 text-right tabular-nums">{r.total_wrong}</td>
                <td className="border border-stone-300 px-1.5 py-1 text-right tabular-nums">{r.total_blank}</td>
                <td className="border border-stone-300 px-1.5 py-1 text-right font-bold tabular-nums">{fmt(r.net)}</td>
                <td
                  className={
                    "border border-stone-300 px-1.5 py-1 text-right tabular-nums " +
                    (diff == null ? "text-stone-400" : diff >= 0 ? "text-emerald-700" : "text-rose-700")
                  }
                >
                  {diff == null ? "—" : `${diff >= 0 ? "+" : ""}${fmt(diff)}`}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
