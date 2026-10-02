import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import { fmtNet, fmtSigned, fmtTRDate } from "@/lib/exam-format";
import type { ExamProgressResponse } from "@/lib/types/exam-progress";
import type { MyAccountResponse } from "@/lib/types/me";
import type { TeacherStudentDetailResponse } from "@/lib/types/teacher";
import { PrintButton } from "../../[examId]/print/print-button";

/**
 * /teacher/students/[id]/exams/report/print?section=tyt — A4 GELİŞİM RAPORU.
 *
 * Tek sınav türü: net gidişatı (grafik + tablo), hedef, ders gidişatı,
 * otomatik yorum ve aksiyon planı. Veri ekrandaki "Gelişim Raporu" sekmesiyle
 * aynı uçtan (/exam-progress) — ekran ile çıktı ayrışamaz.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Deneme Gelişim Raporu" };

const PRIORITY_LABEL: Record<number, string> = { 1: "Öncelikli", 2: "Önemli", 3: "Takip" };

export default async function ExamProgressPrintPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ section?: string; period?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const sid = encodeURIComponent(id);
  const qs = new URLSearchParams();
  if (sp.section) qs.set("section", sp.section);
  if (sp.period) qs.set("period", sp.period);

  let studentName = "";
  let d: ExamProgressResponse | null = null;
  try {
    const detail = await apiServer<TeacherStudentDetailResponse>(`/api/v2/teacher/students/${sid}`);
    studentName = detail.student.full_name;
    d = await apiServer<ExamProgressResponse>(
      `/api/v2/teacher/students/${sid}/exam-progress${qs.toString() ? `?${qs}` : ""}`,
    );
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  if (!d || !d.stats) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Deneme Gelişim Raporu</h1>
        <p className="mt-3 text-stone-600">Bu türde deneme bulunamadı veya erişim yok.</p>
      </main>
    );
  }
  let me: MyAccountResponse | null = null;
  try {
    me = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  const brand = me?.brand ?? null;
  const s = d.stats;
  const t = d.target;

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
          PDF için yazdır penceresinde “PDF olarak kaydet”i seç; dosyayı öğrenciyle ya da veliyle paylaşabilirsin.
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
            <h1 className="text-lg font-bold tracking-tight">Deneme Gelişim Raporu</h1>
            <p className="text-sm font-semibold text-stone-800">{studentName}</p>
          </div>
        </div>
        <div className="text-right text-xs text-stone-600">
          <p className="font-semibold text-stone-900">{d.section_label}</p>
          <p>
            {s.count} deneme · {fmtTRDate(d.exams[0].exam_date)} – {fmtTRDate(s.last_date)}
          </p>
          <p>Rapor tarihi: {fmtTRDate(d.generated_at.slice(0, 10))}</p>
        </div>
      </header>

      <section className="avoid-break mb-4 grid grid-cols-4 gap-2">
        <Box label="İlk → son net">
          <span className="text-lg font-bold tabular-nums">
            {fmtNet(s.first_net)} → {fmtNet(s.last_net)}
          </span>
          <span className="text-[11px] text-stone-600">{fmtSigned(s.change)} net</span>
        </Box>
        <Box label="Son 3 ortalama">
          <span className="text-2xl font-bold tabular-nums">{fmtNet(s.avg_last3)}</span>
        </Box>
        <Box label="En iyi net">
          <span className="text-2xl font-bold tabular-nums">{fmtNet(s.best_net)}</span>
        </Box>
        <Box label={t ? "Hedef" : "Eğim (net/deneme)"}>
          {t ? (
            <>
              <span className="text-2xl font-bold tabular-nums">{fmtNet(t.target_net)}</span>
              <span className="text-[11px] text-stone-600">
                {(t.gap ?? 0) <= 0 ? "hedef tuttu" : `kalan ${fmtNet(t.gap)} net`}
                {t.target_date ? ` · ${fmtTRDate(t.target_date)}` : ""}
              </span>
            </>
          ) : (
            <span className="text-2xl font-bold tabular-nums">{s.slope == null ? "—" : fmtSigned(s.slope)}</span>
          )}
        </Box>
      </section>

      <Section title="Net gidişatı">
        <NetChart data={d} />
        <table className="mt-2 w-full text-xs">
          <thead>
            <tr className="border-b border-stone-300 text-left text-stone-600">
              <th className="py-1 pr-2">Deneme</th>
              <th className="px-2 py-1 text-right">Tarih</th>
              <th className="px-2 py-1 text-right">D</th>
              <th className="px-2 py-1 text-right">Y</th>
              <th className="px-2 py-1 text-right">B</th>
              <th className="py-1 pl-2 text-right">Net</th>
            </tr>
          </thead>
          <tbody>
            {d.exams.map((e) => (
              <tr key={e.id} className="border-b border-stone-200">
                <td className="py-1 pr-2">{e.title}</td>
                <td className="px-2 py-1 text-right tabular-nums">{fmtTRDate(e.exam_date)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{e.correct}</td>
                <td className="px-2 py-1 text-right tabular-nums">{e.wrong}</td>
                <td className="px-2 py-1 text-right tabular-nums">{e.blank}</td>
                <td className="py-1 pl-2 text-right font-semibold tabular-nums">{fmtNet(e.net)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {d.subjects.length ? (
        <Section title="Ders gidişatı" note="İlk ve son denemedeki net, değişim ve deneme başına eğim.">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-stone-300 text-left text-stone-600">
                <th className="py-1 pr-2">Ders</th>
                <th className="px-2 py-1 text-right">İlk</th>
                <th className="px-2 py-1 text-right">Son</th>
                <th className="px-2 py-1 text-right">Değişim</th>
                <th className="px-2 py-1 text-right">Eğim</th>
                {t ? <th className="py-1 pl-2 text-right">Hedef / kalan</th> : null}
              </tr>
            </thead>
            <tbody>
              {d.subjects.map((x) => (
                <tr key={x.name} className="border-b border-stone-200">
                  <td className="py-1 pr-2">{x.name}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{fmtNet(x.first)}</td>
                  <td className="px-2 py-1 text-right font-semibold tabular-nums">{fmtNet(x.last)}</td>
                  <td
                    className={`px-2 py-1 text-right tabular-nums ${
                      (x.change ?? 0) >= 1 ? "text-emerald-700" : (x.change ?? 0) <= -1 ? "text-rose-700" : ""
                    }`}
                  >
                    {x.change == null ? "—" : fmtSigned(x.change)}
                  </td>
                  <td className="px-2 py-1 text-right tabular-nums">{x.slope == null ? "—" : fmtSigned(x.slope)}</td>
                  {t ? (
                    <td className="py-1 pl-2 text-right tabular-nums">
                      {x.target == null ? "—" : `${fmtNet(x.target)} / ${(x.gap ?? 0) <= 0 ? "tuttu" : fmtNet(x.gap)}`}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      ) : null}

      {d.commentary.length ? (
        <Section title="Değerlendirme">
          <ul className="space-y-1 text-sm">
            {d.commentary.map((c) => (
              <li key={c.text} className="flex gap-2">
                <span
                  className={`mt-1.5 size-2 shrink-0 rounded-full ${
                    c.tone === "good" ? "bg-emerald-600" : c.tone === "warn" ? "bg-amber-500" : "bg-sky-600"
                  }`}
                />
                <span>{c.text}</span>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {d.actions.length ? (
        <Section title="Aksiyon planı" note="Öncelik sırasına göre; kayıtlı deneme verisinden türetildi.">
          <ol className="space-y-1.5 text-sm">
            {d.actions.map((a, i) => (
              <li key={a.key} className="flex gap-2">
                <span className="w-5 shrink-0 text-right font-semibold tabular-nums">{i + 1}.</span>
                <span>
                  <b>{a.title}</b>{" "}
                  <span className="text-[10px] font-semibold uppercase text-stone-500">
                    {PRIORITY_LABEL[a.priority] ?? ""}
                  </span>
                  <span className="block text-xs text-stone-600">{a.detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}

      {t?.note ? (
        <Section title="Koç notu">
          <p className="text-sm">{t.note}</p>
        </Section>
      ) : null}

      <footer className="mt-4 border-t border-stone-300 pt-1.5 text-[10px] text-stone-500">
        Net: doğru − yanlış/{d.section === "lgs" ? 3 : 4} · Yorumlar kayıtlı verilerden kural tabanlı üretilir ·{" "}
        {brand ? `${brand.name} · Altyapı: ETÜTKOÇ Rotam` : "etütkoç·rotam"}
      </footer>
    </main>
  );
}

function NetChart({ data }: { data: ExamProgressResponse }) {
  const pts = data.exams;
  if (pts.length < 2) return null;
  const W = 740;
  const H = 150;
  const pad = { l: 34, r: 12, t: 10, b: 22 };
  const target = data.target?.target_net ?? null;
  const vals = pts.map((p) => p.net).concat(target != null ? [target] : []);
  const lo = Math.max(0, Math.floor(Math.min(...vals) - 5));
  const hi = Math.ceil(Math.max(...vals) + 5);
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / (pts.length - 1);
  const y = (v: number) => pad.t + ((hi - v) * (H - pad.t - pad.b)) / Math.max(1, hi - lo);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.net).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Net gidişatı grafiği">
      {[lo, Math.round((lo + hi) / 2), hi].map((v) => (
        <g key={v}>
          <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke="#e7e5e4" />
          <text x={pad.l - 4} y={y(v) + 3} textAnchor="end" fontSize="9" fill="#78716c">
            {v}
          </text>
        </g>
      ))}
      {target != null ? (
        <g>
          <line x1={pad.l} x2={W - pad.r} y1={y(target)} y2={y(target)} stroke="#d97706" strokeDasharray="5 4" />
          <text x={W - pad.r} y={y(target) - 3} textAnchor="end" fontSize="9" fill="#b45309">
            hedef {fmtNet(target)}
          </text>
        </g>
      ) : null}
      <path d={path} fill="none" stroke="#0e7490" strokeWidth="2" />
      {pts.map((p, i) => (
        <g key={p.id}>
          <circle cx={x(i)} cy={y(p.net)} r="3" fill="#0e7490" />
          <text x={x(i)} y={y(p.net) - 6} textAnchor="middle" fontSize="9" fill="#1c1917">
            {fmtNet(p.net)}
          </text>
          <text x={x(i)} y={H - 6} textAnchor="middle" fontSize="8" fill="#78716c">
            {fmtTRDate(p.exam_date).slice(0, 5)}
          </text>
        </g>
      ))}
    </svg>
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
