import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type {
  TeacherStudentDetailResponse,
  TeacherStudentWeekResponse,
  TeacherTask,
} from "@/lib/types/teacher";

/**
 * /teacher/students/[id]/program/print?week=YYYY-MM-DD | ?program_id=N
 *
 * Haftalık program — A4 YATAY tek sayfa. Gün × DERS bazlı gruplu kompakt ızgara.
 * Her görev: durum işareti (✓ yapıldı / ◐ kısmen / ☐ yapılmadı) + kitap·bölüm +
 * çözülen/planlanan. Etkinlik (Video/Özet/Tekrar/Diğer) görevleri de durum
 * işaretiyle gösterilir (test dışı konuların yapılıp yapılmadığı net görünür).
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
function fmtShort(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS[m - 1].slice(0, 3)}`;
}

const TASK_TYPE_LABEL: Record<string, string> = {
  test: "Test", video: "Video", ozet: "Özet", tekrar: "Tekrar", other: "Diğer",
};

// Ders text rengi — subject_id stable hash (print-color-adjust ile basılır).
const SUBJECT_TEXT = [
  "text-indigo-700", "text-emerald-700", "text-amber-700", "text-rose-700",
  "text-violet-700", "text-cyan-700", "text-fuchsia-700", "text-sky-700",
];
function subjectColor(subjectId: number | null): string {
  if (subjectId == null) return "text-stone-500";
  return SUBJECT_TEXT[Math.abs(subjectId) % SUBJECT_TEXT.length];
}

type GState = "done" | "partial" | "todo";
function gorevState(t: TeacherTask): GState {
  const done =
    t.status === "completed" ||
    (t.planned_count > 0 && t.completed_count >= t.planned_count);
  if (done) return "done";
  return t.completed_count > 0 ? "partial" : "todo";
}

interface SubjGroup {
  key: number | null;
  name: string;
  order: number;
  tasks: TeacherTask[];
}
function groupDayBySubject(tasks: TeacherTask[]): SubjGroup[] {
  const map = new Map<number | null, SubjGroup>();
  for (const t of tasks) {
    const ws = t.items.find((it) => it.subject_id != null);
    const key = ws?.subject_id ?? null;
    const name = ws?.subject_name ?? "Diğer";
    const g = map.get(key);
    if (g) g.tasks.push(t);
    else map.set(key, { key, name, order: key == null ? 1 : 0, tasks: [t] });
  }
  return Array.from(map.values()).sort(
    (a, b) => a.order - b.order || a.name.localeCompare(b.name, "tr"),
  );
}

// Görev etiketi (kompakt): tek kalemli test/deneme → "Kitap · Bölüm"; aksi → başlık
function taskLabel(t: TeacherTask): string {
  const first = t.items.find((it) => it.book_id != null) ?? t.items[0];
  if (first?.book_id) {
    return first.book_name + (first.section_label ? ` · ${first.section_label}` : "");
  }
  return t.title || "—";
}

const DENEME_TYPES = new Set(["brans_denemesi", "genel_deneme"]);
// Sayı birimi: deneme kitabı → "deneme"; kitapsız → "soru"; aksi → "test".
function taskUnit(t: TeacherTask): string {
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && !it.book_id) return "soru";              // kitapsız tam deneme
  if (it?.book_type && DENEME_TYPES.has(it.book_type)) return "deneme";
  return "test";
}

export default async function ProgramPrintPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ week?: string; program_id?: string }>;
}) {
  const { id } = await params;
  const { week, program_id } = await searchParams;

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
    const qsParts: string[] = [];
    if (program_id) qsParts.push(`program_id=${encodeURIComponent(program_id)}`);
    if (week && !program_id) qsParts.push(`start=${encodeURIComponent(week)}`);
    const qs = qsParts.length ? `?${qsParts.join("&")}` : "";
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
    (acc, d) => acc + d.tasks.reduce(
      (a, t) => a + t.items.reduce((b, it) => b + (it.correct_count ?? 0), 0), 0), 0);
  const totalWrong = weekData.days.reduce(
    (acc, d) => acc + d.tasks.reduce(
      (a, t) => a + t.items.reduce((b, it) => b + (it.wrong_count ?? 0), 0), 0), 0);

  return (
    <main className="mx-auto w-full max-w-[1100px] bg-white px-6 py-4 text-stone-900 print:max-w-none print:px-0 print:py-0">
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 7mm; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>

      {/* Header — kompakt tek satır */}
      <header className="mb-2 flex items-end justify-between gap-4 border-b-2 border-stone-800 pb-1.5">
        <div className="flex items-baseline gap-3">
          <h1 className="text-base font-bold tracking-tight">Haftalık Program</h1>
          <span className="text-sm font-semibold text-stone-800">{studentName || "—"}</span>
          <span className="text-[11px] text-stone-500">
            {fmtDate(weekData.start_date)} — {fmtDate(weekData.end_date)}
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-stone-500">
          <span>Plan. <b className="text-stone-800">{weekData.total_planned}</b></span>
          <span>Çöz. <b className="text-stone-800">{weekData.total_completed}</b></span>
          <span>D <b className="text-emerald-700">{totalCorrect}</b></span>
          <span>Y <b className="text-rose-700">{totalWrong}</b></span>
          <span className="text-stone-400">· etütkoç·rotam</span>
        </div>
      </header>

      {/* Lejant — durum işaretleri */}
      <div className="mb-2 flex items-center gap-3 text-[9px] text-stone-500">
        <span><b className="text-emerald-700">✓</b> yapıldı</span>
        <span><b className="text-amber-700">◐</b> kısmen</span>
        <span><b className="text-stone-400">☐</b> yapılmadı</span>
        <span className="text-stone-400">· test/deneme: çözülen/planlanan · diğer: etkinlik</span>
      </div>

      {/* 7 günlük ızgara — yatay */}
      <div className="grid grid-cols-7 gap-1.5">
        {weekData.days.map((day) => (
          <DayColumn key={day.date} day={day} />
        ))}
      </div>

      {/* Notes */}
      {weekData.notes.length > 0 ? (
        <section className="mt-3 border-t border-stone-300 pt-2">
          <h2 className="mb-1 text-[11px] font-semibold text-stone-700">Hafta notları</h2>
          <div className="flex flex-wrap gap-2">
            {weekData.notes.map((n) => (
              <div key={n.id} className="rounded border border-stone-200 bg-stone-50 px-2 py-1 text-[10px] text-stone-800">
                {n.body}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <div className="no-print mt-4 text-center">
        <p className="text-xs text-stone-400">Yazdırmak için Ctrl/Cmd + P (yatay seçili gelir).</p>
      </div>
    </main>
  );
}

function DayColumn({ day }: { day: TeacherStudentWeekResponse["days"][number] }) {
  const groups = groupDayBySubject(day.tasks);
  return (
    <section className="break-inside-avoid rounded border border-stone-300">
      <header
        className={
          "flex items-baseline justify-between px-1.5 py-1 " +
          (day.is_today ? "bg-stone-800 text-white" : "bg-stone-100")
        }
      >
        <span className="text-[10.5px] font-bold leading-tight">
          {day.dow_label}
        </span>
        <span className={"text-[8.5px] " + (day.is_today ? "text-stone-300" : "text-stone-500")}>
          {fmtShort(day.date)}
        </span>
      </header>
      <div className="px-1 py-1 space-y-1.5">
        {day.tasks.length === 0 ? (
          <p className="text-[9px] italic text-stone-400">—</p>
        ) : (
          groups.map((g) => (
            <div key={g.key ?? "other"}>
              <div className={"text-[9px] font-bold uppercase tracking-wide leading-tight " + subjectColor(g.key)}>
                {g.name}
              </div>
              <ul className="mt-0.5 space-y-0.5">
                {g.tasks.map((t) => (
                  <TaskRow key={t.id} task={t} />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function TaskRow({ task }: { task: TeacherTask }) {
  const st = gorevState(task);
  const mark = st === "done" ? "✓" : st === "partial" ? "◐" : "☐";
  const markCls =
    st === "done" ? "text-emerald-700" : st === "partial" ? "text-amber-700" : "text-stone-400";
  const isActivity = task.planned_count <= 0 && task.items.every((it) => (it.planned_count ?? 0) <= 0);
  const typeLabel = TASK_TYPE_LABEL[task.type] ?? task.type;

  return (
    <li className="flex items-start gap-1 text-[9.5px] leading-tight">
      <span className={"shrink-0 font-bold " + markCls} aria-hidden>{mark}</span>
      <span className="min-w-0 flex-1">
        <span className={st === "done" ? "text-stone-500" : "text-stone-900"}>
          {taskLabel(task)}
        </span>
        {isActivity ? (
          <span className="text-stone-400">
            {" "}({typeLabel})
            {(task.solved_count ?? 0) > 0 ? (
              <span className="font-semibold text-stone-700"> · {task.solved_count} soru</span>
            ) : ""}
          </span>
        ) : (
          <span className="font-semibold tabular-nums text-stone-800">
            {" "}{task.completed_count}/{task.planned_count} {taskUnit(task)}
          </span>
        )}
      </span>
    </li>
  );
}
