import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import {
  buildInsights,
  fmtInt,
  fmtNet,
  fmtSigned,
  fmtTRDate,
  halfDrop,
  percentile,
  previousExam,
  subjectNetIn,
} from "@/lib/exam-format";
import type { ExamTopicAnalysisResponse } from "@/lib/types/exam-import";
import type { MyAccountResponse } from "@/lib/types/me";
import type {
  ExamQuestionsResponse,
  ExamResultRow,
  StudentExamListResponse,
  TeacherStudentDetailResponse,
} from "@/lib/types/teacher";
import { PrintButton } from "./print-button";

/**
 * /teacher/students/[id]/exams/[examId]/print — A4 dikey DENEME KARNESİ.
 *
 * Koç yazdırır ya da "PDF olarak kaydet" ile WhatsApp/e-postayla paylaşır.
 * Kurumsal kimlik (me.brand): kuruma bağlı koçta kurum logosu/adı, ETÜTKOÇ
 * yalnız altyapı notu. Sayılar ekrandaki analizle aynı yardımcılardan
 * (lib/exam-format) — ekran ile çıktı ayrışamaz.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Deneme Karnesi" };

const MAX_TREND = 6;

export default async function ExamReportPrintPage({
  params,
}: {
  params: Promise<{ id: string; examId: string }>;
}) {
  const { id, examId } = await params;
  const sid = encodeURIComponent(id);

  let studentName = "";
  let rows: ExamResultRow[] = [];
  try {
    const detail = await apiServer<TeacherStudentDetailResponse>(`/api/v2/teacher/students/${sid}`);
    studentName = detail.student.full_name;
    const list = await apiServer<StudentExamListResponse>(
      `/api/v2/teacher/students/${sid}/exams?period=all`,
    );
    rows = list.rows;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  const row = rows.find((r) => String(r.id) === examId) ?? null;
  if (!row) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Deneme Karnesi</h1>
        <p className="mt-3 text-stone-600">Deneme bulunamadı veya erişim yok.</p>
      </main>
    );
  }
  // aynı tür, en yeni ilk; bu denemeye KADARki denemeler (sonrakiler karneye girmez)
  const sameType = rows
    .filter((r) => (r.series_key || r.section) === (row.series_key || row.section))
    .sort((a, b) => (a.exam_date < b.exam_date ? 1 : a.exam_date > b.exam_date ? -1 : b.id - a.id));
  const upTo = sameType.slice(sameType.findIndex((r) => r.id === row.id));
  const prev = previousExam(sameType, row);
  const insights = buildInsights(upTo);
  const trend = [...upTo.slice(0, MAX_TREND)].reverse();
  const trendSubjects = [...new Set(trend.flatMap((r) => r.subjects.map((s) => s.name)))];

  let questions: ExamQuestionsResponse["items"] = [];
  if (row.import_source === "pdf_import") {
    try {
      questions = (
        await apiServer<ExamQuestionsResponse>(`/api/v2/teacher/exams/${encodeURIComponent(examId)}/questions`)
      ).items;
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
    }
  }
  let opportunities: ExamTopicAnalysisResponse["opportunities"] = [];
  let analysisExamCount = 0;
  try {
    const a = await apiServer<ExamTopicAnalysisResponse>(
      `/api/v2/teacher/students/${sid}/exam-topic-analysis?section=${encodeURIComponent(row.series_key || row.section)}`,
    );
    opportunities = a.opportunities.slice(0, 6);
    analysisExamCount = a.exams.length;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  let me: MyAccountResponse | null = null;
  try {
    me = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  const brand = me?.brand ?? null;
  const missed = questions.filter((q) => q.result !== "dogru");
  const drops = halfDrop(questions).filter((d) => d.second - d.first <= -0.2);
  const pctl = percentile(row);

  return (
    <main className="mx-auto w-full max-w-[820px] bg-white px-8 py-6 text-stone-900 print:max-w-none print:px-0 print:py-0">
      <style>{`
        @media print {
          @page { size: A4 portrait; margin: 10mm; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .avoid-break { break-inside: avoid; }
        }
      `}</style>

      <div className="no-print mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md bg-stone-100 px-3 py-2">
        <PrintButton />
        <span className="text-xs text-stone-600">
          PDF için yazdır penceresinde hedef olarak “PDF olarak kaydet”i seç; dosyayı WhatsApp ya da
          e-postayla paylaşabilirsin.
        </span>
      </div>

      <header className="mb-4 flex items-end justify-between gap-4 border-b-2 border-stone-800 pb-2">
        <div className="flex items-center gap-3">
          {brand?.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- kurum logosu (yazdırma)
            <img src={brand.logo_url} alt={brand.name} className="h-12 w-auto max-w-[170px] object-contain" />
          ) : brand ? (
            <span className="max-w-[200px] text-base font-bold leading-tight">{brand.name}</span>
          ) : (
            // eslint-disable-next-line @next/next/no-img-element -- platform amblemi (yazdırma)
            <img src="/etutkoc-mark.png" alt="ETÜTKOÇ Rotam" className="h-10 w-10 object-contain" />
          )}
          <div>
            <h1 className="text-lg font-bold tracking-tight">Deneme Karnesi</h1>
            <p className="text-sm font-semibold text-stone-800">{studentName}</p>
          </div>
        </div>
        <div className="text-right text-xs text-stone-600">
          <p className="max-w-[330px] font-semibold text-stone-900">{row.title}</p>
          <p>
            {row.series_label || row.section_label} · {fmtTRDate(row.exam_date)} · {row.total_questions} soru
          </p>
        </div>
      </header>

      <section className="avoid-break mb-4 grid grid-cols-4 gap-2">
        <Box label="Toplam net">
          <span className="text-2xl font-bold tabular-nums">{fmtNet(row.net)}</span>
          <span className="text-[11px] text-stone-600">
            {prev ? `önceki: ${fmtNet(prev.net)} (${fmtSigned(row.net - prev.net)})` : "bu türde ilk deneme"}
          </span>
          {row.averages?.total != null ? (
            <span className="text-[11px] text-stone-600">
              {row.averages.label.toLocaleLowerCase("tr-TR")}: {fmtNet(row.averages.total)} (
              {fmtSigned(row.net - row.averages.total)})
            </span>
          ) : null}
        </Box>
        <Box label="Doğru · Yanlış · Boş">
          <span className="text-lg font-bold tabular-nums">
            <span className="text-emerald-700">{row.total_correct}</span> ·{" "}
            <span className="text-rose-700">{row.total_wrong}</span> ·{" "}
            <span className="text-stone-500">{row.total_blank}</span>
          </span>
        </Box>
        <Box label="Puan">
          <span className="text-2xl font-bold tabular-nums">
            {row.score?.score != null ? fmtNet(row.score.score) : "—"}
          </span>
        </Box>
        <Box label="Sıralama">
          <span className="text-2xl font-bold tabular-nums">
            {row.score?.rank_overall ? fmtInt(row.score.rank_overall) : "—"}
          </span>
          {row.score?.participants ? (
            <span className="text-[11px] text-stone-600">
              {fmtInt(row.score.participants)} katılımcı
              {pctl != null ? ` · ilk %${String(pctl).replace(".", ",")}` : ""}
            </span>
          ) : null}
        </Box>
      </section>

      {row.subjects.length ? (
        <Section title="Ders bazında sonuç">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-300 text-left text-xs text-stone-600">
                <th className="py-1 pr-2">Ders</th>
                <th className="px-2 py-1 text-right">Doğru</th>
                <th className="px-2 py-1 text-right">Yanlış</th>
                <th className="px-2 py-1 text-right">Boş</th>
                <th className="px-2 py-1 text-right">Net</th>
                {row.averages ? (
                  <th className="px-2 py-1 text-right">{row.averages.label}</th>
                ) : null}
                <th className="py-1 pl-2 text-right">Önceki denemeye göre</th>
              </tr>
            </thead>
            <tbody>
              {row.subjects.map((s) => {
                const p = subjectNetIn(prev, s.name);
                return (
                  <tr key={s.name} className="border-b border-stone-200">
                    <td className="py-1 pr-2">{s.name}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-emerald-700">{s.correct}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-rose-700">{s.wrong}</td>
                    <td className="px-2 py-1 text-right tabular-nums text-stone-500">{s.blank}</td>
                    <td className="px-2 py-1 text-right font-semibold tabular-nums">{fmtNet(s.net)}</td>
                    {row.averages ? (
                      <td className="px-2 py-1 text-right tabular-nums text-stone-600">
                        {fmtNet(row.averages.subjects[s.name])}
                      </td>
                    ) : null}
                    <td className={`py-1 pl-2 text-right tabular-nums ${p == null ? "text-stone-400" : s.net - p >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                      {p == null ? "—" : fmtSigned(s.net - p)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Section>
      ) : null}

      {insights.length ? (
        <Section title="Öne çıkanlar">
          <ul className="space-y-0.5 text-sm">
            {insights.map((t) => (
              <li key={t}>• {t}</li>
            ))}
            {drops.map((d) => (
              <li key={d.subject}>
                • {d.subject}: testin ilk yarısında %{Math.round(d.first * 100)}, ikinci yarısında %
                {Math.round(d.second * 100)} doğruluk — sona doğru düşüş var.
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {trend.length >= 2 && trendSubjects.length ? (
        <Section title={`Gelişim — son ${trend.length} ${row.series_label || row.section_label} denemesi (net)`}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-300 text-stone-600">
                <th className="py-1 pr-2 text-left">Ders</th>
                {trend.map((r) => (
                  <th key={r.id} className={`px-1 py-1 text-right ${r.id === row.id ? "text-stone-900" : ""}`}>
                    {fmtTRDate(r.exam_date).slice(0, 5)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trendSubjects.map((name) => (
                <tr key={name} className="border-b border-stone-200">
                  <td className="py-1 pr-2">{name}</td>
                  {trend.map((r) => {
                    const v = subjectNetIn(r, name);
                    return (
                      <td key={r.id} className={`px-1 py-1 text-right tabular-nums ${r.id === row.id ? "font-semibold" : ""}`}>
                        {v == null ? "—" : fmtNet(v)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="py-1 pr-2">Toplam</td>
                {trend.map((r) => (
                  <td key={r.id} className="px-1 py-1 text-right tabular-nums">
                    {fmtNet(r.net)}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </Section>
      ) : null}

      {opportunities.length ? (
        <Section
          title="Net fırsatı"
          note={`Son ${analysisExamCount} denemede bu konulardaki yanlış ve boşlar doğru olsaydı deneme başına kazanılacak net.`}
        >
          <table className="w-full text-sm">
            <tbody>
              {opportunities.map((o) => (
                <tr key={o.topic_id} className="border-b border-stone-200">
                  <td className="py-1 pr-2">
                    <b>{o.topic_name}</b> <span className="text-stone-500">· {o.subject_name}</span>
                  </td>
                  <td className="px-2 py-1 text-right text-xs text-stone-600">
                    {o.wrong} yanlış · {o.blank} boş / {o.total} soru
                  </td>
                  <td className="py-1 pl-2 text-right font-semibold tabular-nums text-rose-700">
                    +{fmtNet(o.net_gain_per_exam)} net
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : null}

      {missed.length ? (
        <Section title={`Yanlış ve boş sorular (${missed.length})`}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-300 text-left text-stone-600">
                <th className="py-1 pr-2">Ders</th>
                <th className="px-2 py-1">No</th>
                <th className="px-2 py-1">Konu</th>
                <th className="px-2 py-1 text-center">Anahtar</th>
                <th className="px-2 py-1 text-center">Öğrenci</th>
              </tr>
            </thead>
            <tbody>
              {missed.map((q, i) => (
                <tr key={i} className="border-b border-stone-200">
                  <td className="py-0.5 pr-2 text-stone-600">{q.subject}</td>
                  <td className="px-2 py-0.5 tabular-nums">{q.question_no ?? "—"}</td>
                  <td className="px-2 py-0.5">{q.topic_name ?? q.topic_label ?? "—"}</td>
                  <td className="px-2 py-0.5 text-center">{q.correct_answer ?? "—"}</td>
                  <td className={`px-2 py-0.5 text-center ${q.result === "bos" ? "text-stone-400" : "text-rose-700"}`}>
                    {q.result === "bos" ? "boş" : q.student_answer ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : null}

      {row.note ? (
        <Section title="Koç notu">
          <p className="text-sm">{row.note}</p>
        </Section>
      ) : null}

      <footer className="mt-4 border-t border-stone-300 pt-1.5 text-[10px] text-stone-500">
        Net: doğru − yanlış/{row.section === "lgs" ? 3 : 4} · Puan ve sıralama karnede yazıyorsa
        gösterilir · {brand ? `${brand.name} · Altyapı: ETÜTKOÇ Rotam` : "etütkoç·rotam"}
      </footer>
    </main>
  );
}

function Box({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-md border border-stone-300 px-2.5 py-2">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-stone-500">{label}</span>
      {children}
    </div>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="avoid-break mb-4">
      <h2 className="border-b border-stone-400 pb-0.5 text-sm font-bold">{title}</h2>
      {note ? <p className="mt-0.5 text-[11px] text-stone-600">{note}</p> : null}
      <div className="mt-1.5">{children}</div>
    </section>
  );
}
