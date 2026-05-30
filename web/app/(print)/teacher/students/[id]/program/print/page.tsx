import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type {
  TeacherStudentDetailResponse,
  TeacherStudentWeekResponse,
  TeacherTask,
  TeacherTaskItem,
} from "@/lib/types/teacher";

/**
 * /teacher/students/[id]/program/print?week=YYYY-MM-DD
 *
 * Yazdırılabilir haftalık program çıktısı. Mevcut + geçmiş haftalar için:
 *   - Her gün × görev satırları
 *   - Kalem detayı: kitap · bölüm · planlanan / çözülen / D / Y
 *   - Toplam özet (planlanan / çözülen / oran)
 *
 * D/Y null olan kalemler "—" gösterir. Geçmiş haftalarda D/Y dolu varsa
 * koç performans karşılaştırması yapabilir.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Haftalık Program Çıktısı" };

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${TR_MONTHS[m - 1]} ${y}`;
}

const TASK_TYPE_LABEL: Record<string, string> = {
  test: "Test",
  video: "Video",
  ozet: "Özet",
  tekrar: "Tekrar",
  other: "Diğer",
};

export default async function ProgramPrintPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ week?: string }>;
}) {
  const { id } = await params;
  const { week } = await searchParams;

  let studentName = "";
  let weekData: TeacherStudentWeekResponse | null = null;
  let fetchError: string | null = null;

  try {
    const detail = await apiServer<TeacherStudentDetailResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(id)}`,
    );
    studentName = detail.student.full_name;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    fetchError = "Öğrenci bulunamadı veya erişim yok.";
  }

  try {
    const qs = week ? `?start=${encodeURIComponent(week)}` : "";
    weekData = await apiServer<TeacherStudentWeekResponse>(
      `/api/v2/teacher/students/${encodeURIComponent(id)}/week${qs}`,
    );
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    fetchError = fetchError ?? "Hafta verisi yüklenemedi.";
  }

  if (!weekData) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Haftalık Program — Çıktı</h1>
        <p className="mt-3 text-stone-600">{fetchError}</p>
      </main>
    );
  }

  const totalCorrect = weekData.days.reduce(
    (acc, d) =>
      acc +
      d.tasks.reduce(
        (a, t) =>
          a +
          t.items.reduce((b, it) => b + (it.correct_count ?? 0), 0),
        0,
      ),
    0,
  );
  const totalWrong = weekData.days.reduce(
    (acc, d) =>
      acc +
      d.tasks.reduce(
        (a, t) =>
          a +
          t.items.reduce((b, it) => b + (it.wrong_count ?? 0), 0),
        0,
      ),
    0,
  );

  return (
    <main className="mx-auto max-w-[820px] bg-white px-8 py-6 text-stone-900">
      <style>{`
        @media print {
          @page { size: A4 portrait; margin: 12mm; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>

      {/* Header */}
      <header className="mb-5 border-b-2 border-stone-800 pb-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">Haftalık Program</h1>
            <p className="mt-1 text-base font-semibold text-stone-800">
              {studentName || "—"}
            </p>
            <p className="mt-0.5 text-sm text-stone-600">
              {fmtDate(weekData.start_date)} — {fmtDate(weekData.end_date)}
            </p>
          </div>
          <div className="text-right text-[11px] text-stone-500">
            <p>etütkoç · rotam</p>
            <p className="mt-0.5">{new Date().toLocaleDateString("tr-TR")}</p>
          </div>
        </div>
      </header>

      {/* Özet */}
      <section className="mb-4 grid grid-cols-4 gap-3 text-center text-sm">
        <SummaryCell label="Planlanan" value={weekData.total_planned} />
        <SummaryCell label="Çözülen" value={weekData.total_completed} />
        <SummaryCell label="Doğru" value={totalCorrect} />
        <SummaryCell label="Yanlış" value={totalWrong} />
      </section>

      {/* Günler */}
      <div className="space-y-4">
        {weekData.days.map((day) => (
          <DayBlock
            key={day.date}
            date={day.date}
            dowLabel={day.dow_label}
            isToday={day.is_today}
            tasks={day.tasks}
            planned={day.planned}
            completed={day.completed}
          />
        ))}
      </div>

      {/* Notes */}
      {weekData.notes.length > 0 ? (
        <section className="mt-6 border-t border-stone-300 pt-4">
          <h2 className="mb-2 text-sm font-semibold text-stone-800">
            Hafta notları
          </h2>
          <div className="space-y-2">
            {weekData.notes.map((n) => (
              <div
                key={n.id}
                className="rounded border border-stone-200 bg-stone-50 px-3 py-2 text-[12px] text-stone-800"
              >
                {n.body}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <footer className="mt-6 flex items-center justify-between border-t border-stone-200 pt-3 text-[10px] text-stone-500">
        <span>etütkoç · rotam</span>
        <span>Kişiseldir; öğrenci için hazırlanmıştır.</span>
      </footer>

      <div className="no-print mt-6 text-center">
        <p className="text-xs text-stone-400">
          Yazdırmak için tarayıcıdan Ctrl/Cmd + P.
        </p>
      </div>
    </main>
  );
}

function SummaryCell({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-stone-300 bg-stone-50 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wider text-stone-500">
        {label}
      </div>
      <div className="text-xl font-bold tabular-nums text-stone-900">
        {value}
      </div>
    </div>
  );
}

function DayBlock({
  date,
  dowLabel,
  isToday,
  tasks,
  planned,
  completed,
}: {
  date: string;
  dowLabel: string;
  isToday: boolean;
  tasks: TeacherTask[];
  planned: number;
  completed: number;
}) {
  return (
    <section className="break-inside-avoid">
      <header className="mb-1.5 flex items-baseline justify-between border-b border-stone-300 pb-1">
        <h3 className="text-sm font-bold text-stone-800">
          {dowLabel}{" "}
          <span className="font-normal text-stone-500">· {fmtDate(date)}</span>
          {isToday ? (
            <span className="ml-2 rounded-sm bg-stone-800 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white">
              bugün
            </span>
          ) : null}
        </h3>
        <span className="text-[11px] tabular-nums text-stone-600">
          {completed}/{planned}
        </span>
      </header>
      {tasks.length === 0 ? (
        <p className="px-2 py-1.5 text-[11px] italic text-stone-400">
          — görev yok —
        </p>
      ) : (
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="border-b border-stone-200 text-[10px] uppercase tracking-wider text-stone-500">
              <th className="px-1 py-1 text-left">Tip</th>
              <th className="px-1 py-1 text-left">Kitap / Bölüm</th>
              <th className="px-1 py-1 text-right">Plan.</th>
              <th className="px-1 py-1 text-right">Çöz.</th>
              <th className="px-1 py-1 text-right">D</th>
              <th className="px-1 py-1 text-right">Y</th>
            </tr>
          </thead>
          <tbody>
            {tasks.flatMap((t) =>
              t.items.map((it, idx) => (
                <TaskItemRow
                  key={`${t.id}-${it.id}`}
                  task={t}
                  item={it}
                  isFirst={idx === 0}
                />
              )),
            )}
          </tbody>
        </table>
      )}
    </section>
  );
}

function TaskItemRow({
  task,
  item,
  isFirst,
}: {
  task: TeacherTask;
  item: TeacherTaskItem;
  isFirst: boolean;
}) {
  const typeLabel = TASK_TYPE_LABEL[task.type] ?? task.type;
  // Title-only kalemlerde (Video/Özet/Tekrar/Diğer items=[]) book_name "Deneme"
  // veya boş; başlık tablo'da göster.
  const label = item.book_id
    ? `${item.book_name}${item.section_label ? ` · ${item.section_label}` : ""}`
    : task.title || "—";
  return (
    <tr className="border-b border-stone-100">
      <td className="px-1 py-1 text-stone-600">
        {isFirst ? typeLabel : ""}
      </td>
      <td className="px-1 py-1 text-stone-900">
        {label}
        {item.topic_name ? (
          <span className="text-stone-500"> ({item.topic_name})</span>
        ) : null}
      </td>
      <td className="px-1 py-1 text-right tabular-nums text-stone-700">
        {item.planned_count}
      </td>
      <td className="px-1 py-1 text-right tabular-nums text-stone-900">
        {item.completed_count}
      </td>
      <td className="px-1 py-1 text-right tabular-nums text-emerald-700">
        {item.correct_count ?? "—"}
      </td>
      <td className="px-1 py-1 text-right tabular-nums text-rose-700">
        {item.wrong_count ?? "—"}
      </td>
    </tr>
  );
}
