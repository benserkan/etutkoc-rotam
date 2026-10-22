import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { StudentDayResponse, StudentTask } from "@/lib/types/student";
import { PrintVideoList } from "@/components/shared/print-video-list";
import { PrintBrandHeader, fmtLongDate, getPrintBrand } from "@/components/print/print-brand";
import { PrintButton } from "./print-button";

/**
 * /student/day/print?date=YYYY-MM-DD — günün programı, A4 dikey.
 *
 * Kâğıt üstünde çalışan öğrenci için: her görev bir satır, ders başlıkları altında,
 * kutucuk + planlanan sayı; test görevlerinde Doğru/Yanlış/Boş yazma alanı,
 * denemede net + süre alanı. Durum işaretleri (✓ ◐ ☐) ekrandakiyle aynı.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Günün Programı — Yazdır" };

const DENEME_TYPES = new Set(["brans_denemesi", "genel_deneme"]);
const PERIOD_LABELS: Record<string, string> = { morning: "Sabah", noon: "Öğle", evening: "Akşam" };
const TYPE_LABEL: Record<string, string> = {
  test: "Test", video: "Video", ozet: "Özet", tekrar: "Tekrar", other: "Etkinlik",
};

function isDeneme(t: StudentTask): boolean {
  return t.items.some((x) => x.exam_kind || (x.book_type != null && DENEME_TYPES.has(x.book_type)))
    || (t.items.length > 0 && t.items.every((x) => x.book_id == null && x.is_test_unit === false && x.topic_id == null));
}

function subjectOf(t: StudentTask): string {
  const ws = t.items.find((it) => it.subject_name);
  if (ws?.subject_name) return ws.subject_name;
  const sep = t.title.indexOf(" · ");
  if (sep > 0) return t.title.substring(0, sep);
  return "Diğer";
}

function state(t: StudentTask): "done" | "partial" | "todo" {
  if (t.status === "completed" || (t.planned_count > 0 && t.completed_count >= t.planned_count)) return "done";
  return t.completed_count > 0 ? "partial" : "todo";
}

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentDayPrintPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const date = typeof sp.date === "string" ? sp.date : undefined;
  let day: StudentDayResponse | null = null;
  try {
    day = await apiServer<StudentDayResponse>(`/api/v2/student/day${date ? `?date=${encodeURIComponent(date)}` : ""}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
  }
  if (!day) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Günün Programı</h1>
        <p className="mt-3 text-stone-600">Gün verisi yüklenemedi.</p>
      </main>
    );
  }
  const brand = await getPrintBrand();

  // Periyot (varsa) → ders → görev
  const usePeriods = day.tasks.some((t) => t.period != null);
  const sections: { label: string | null; groups: { name: string; tasks: StudentTask[] }[] }[] = [];
  const pkeys = usePeriods ? ["morning", "noon", "evening", "none"] : ["all"];
  for (const pk of pkeys) {
    const tasks = day.tasks.filter((t) =>
      pk === "all" ? true : pk === "none" ? !t.period || !(t.period in PERIOD_LABELS) : t.period === pk,
    );
    if (tasks.length === 0) continue;
    const map = new Map<string, StudentTask[]>();
    for (const t of tasks) {
      const s = isDeneme(t) ? "Denemeler" : subjectOf(t);
      map.set(s, [...(map.get(s) ?? []), t]);
    }
    sections.push({
      label: pk === "all" ? null : PERIOD_LABELS[pk] ?? "Zamanı belirtilmemiş",
      groups: Array.from(map.entries()).map(([name, ts]) => ({ name, tasks: ts })),
    });
  }

  const s = day.summary;
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
        <span className="text-xs text-stone-400">Dikey A4 · kâğıtta da işaretleyebilirsin</span>
      </div>

      <PrintBrandHeader
        title="Günün Programı"
        subtitle={fmtLongDate(day.date, true)}
        studentName={brand.studentName}
        instName={brand.instName}
        logoUrl={brand.logoUrl}
        right={
          <div className="space-x-2 text-stone-600">
            <span>Görev <b className="text-stone-900">{s.gorev_done}/{s.gorev_total}</b></span>
            {s.test_planned > 0 ? (
              <span>Test <b className="text-stone-900">{s.test_completed}/{s.test_planned}</b></span>
            ) : null}
            {s.deneme_count > 0 ? <span>Deneme <b className="text-stone-900">{s.deneme_count}</b></span> : null}
          </div>
        }
      />

      {day.tasks.length === 0 ? (
        <p className="mt-6 text-sm italic text-stone-500">Bu gün için görev yok.</p>
      ) : (
        <div className="space-y-4">
          {sections.map((sec, i) => (
            <section key={sec.label ?? i} className="space-y-2">
              {sec.label ? (
                <h2 className="border-b border-stone-300 pb-0.5 text-xs font-bold uppercase tracking-wider text-stone-600">
                  {sec.label}
                </h2>
              ) : null}
              {sec.groups.map((g) => (
                <div key={g.name} className="break-inside-avoid">
                  <h3
                    className={
                      "mb-1 text-sm font-bold " +
                      (g.name === "Denemeler" ? "text-indigo-800" : "text-stone-800")
                    }
                  >
                    {g.name}
                  </h3>
                  <ul className="space-y-1.5">
                    {g.tasks.map((t) => (
                      <TaskLine key={t.id} t={t} />
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          ))}
        </div>
      )}

      {day.day_note ? (
        <section className="mt-6 break-inside-avoid rounded border border-stone-300 p-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-stone-600">Günün notu</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm text-stone-800">{day.day_note}</p>
        </section>
      ) : (
        <section className="mt-6 break-inside-avoid rounded border border-dashed border-stone-300 p-3">
          <h2 className="text-xs font-bold uppercase tracking-wider text-stone-500">Günün notu</h2>
          <div className="mt-6 border-b border-stone-200" />
          <div className="mt-6 border-b border-stone-200" />
        </section>
      )}
    </main>
  );
}

function TaskLine({ t }: { t: StudentTask }) {
  const st = state(t);
  const mark = st === "done" ? "✓" : st === "partial" ? "◐" : "☐";
  const markCls = st === "done" ? "text-emerald-700" : st === "partial" ? "text-amber-700" : "text-stone-500";
  const deneme = isDeneme(t);
  const books = t.items.filter((it) => it.book_id != null || it.topic_name);
  const activity = t.items.length === 0;
  return (
    <li className="flex items-start gap-2 rounded border border-stone-200 px-2 py-1.5">
      <span className={"mt-px shrink-0 text-base font-bold leading-none " + markCls} aria-hidden>{mark}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline gap-x-2">
          {deneme ? (
            <span className="rounded bg-indigo-700 px-1.5 text-[9px] font-bold uppercase leading-4 text-white">Deneme</span>
          ) : activity ? (
            <span className="rounded bg-stone-200 px-1.5 text-[9px] font-bold uppercase leading-4 text-stone-700">
              {TYPE_LABEL[t.type] ?? "Etkinlik"}
            </span>
          ) : null}
          <span className="text-[13px] font-medium">{t.title || "—"}</span>
          {!activity ? (
            <span className="text-[12px] font-semibold tabular-nums text-stone-700">
              {t.completed_count}/{t.planned_count} {deneme ? "deneme" : "test"}
            </span>
          ) : null}
        </div>
        {books.length > 1 ? (
          <ul className="mt-0.5 text-[11px] text-stone-600">
            {books.map((it) => (
              <li key={it.id}>
                · {it.section_label ?? it.topic_name ?? it.book_name} ({it.planned})
              </li>
            ))}
          </ul>
        ) : null}
        <PrintVideoList videos={t.videos} />
        {!activity ? (
          <div className="mt-1 flex flex-wrap gap-4 text-[11px] text-stone-500">
            <span>Doğru ____</span>
            <span>Yanlış ____</span>
            <span>Boş ____</span>
            {deneme ? (
              <>
                <span>Net ____</span>
                <span>Süre ____ dk</span>
              </>
            ) : null}
          </div>
        ) : null}
      </div>
    </li>
  );
}
