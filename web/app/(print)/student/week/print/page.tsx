import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { StudentWeekResponse, StudentWeekDay, StudentTask } from "@/lib/types/student";
import type { MyAccountResponse } from "@/lib/types/me";
import {
  findSubjectByExactName,
  findSubjectInTitle,
  subjectGroupKey,
  subjectToneIndex,
  type SubjectRef,
} from "@/lib/subject-match";
import { PrintButton } from "./print-button";

/**
 * /student/week/print?start=YYYY-MM-DD
 *
 * Haftalık program — A4 YATAY tek sayfa. Koç programı yazdırma ile AYNI biçim:
 * gün × DERS bazlı gruplu (periyot bölümlü) kompakt ızgara, her görev durum
 * işaretiyle (✓ yapıldı / ◐ kısmen / ☐ yapılmadı). Kuruma bağlı öğrenci →
 * kurum logosu, bağımsız koçun öğrencisi → platform amblemi.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Haftalık Program — Yazdır" };

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

// Ders text rengi — ADA göre stabil (ekran ızgarası + koç çıktısı ile aynı).
const SUBJECT_TEXT = [
  "text-indigo-700", "text-emerald-700", "text-amber-700", "text-rose-700",
  "text-violet-700", "text-cyan-700", "text-fuchsia-700", "text-sky-700",
];
function subjectColor(key: string, name: string): string {
  if (key === "other") return "text-stone-500";
  return SUBJECT_TEXT[subjectToneIndex(name, SUBJECT_TEXT.length)];
}

type GState = "done" | "partial" | "todo";
function gorevState(t: StudentTask): GState {
  const done =
    t.status === "completed" ||
    (t.planned_count > 0 && t.completed_count >= t.planned_count);
  if (done) return "done";
  return t.completed_count > 0 ? "partial" : "todo";
}

interface SubjGroup {
  key: string;
  name: string;
  order: number;
  tasks: StudentTask[];
}
function taskSubjKey(t: StudentTask, subjects: SubjectRef[]): { key: string; name: string } {
  const ws = t.items.find((it) => it.subject_id != null);
  if (ws?.subject_id != null) {
    const nm = ws.subject_name ?? "Ders";
    return { key: subjectGroupKey(nm), name: nm };
  }
  if (t.items.length === 0 || t.work_block_id != null) {
    const sep = t.title.indexOf(" · ");
    if (sep > 0 && sep < t.title.length - 3) {
      const nm = t.title.substring(0, sep);
      const resolved = findSubjectByExactName(nm, subjects);
      const name = resolved ? resolved.name : nm;
      return { key: subjectGroupKey(name), name };
    }
  }
  const inTitle = findSubjectInTitle(t.title, subjects);
  if (inTitle) return { key: subjectGroupKey(inTitle.name), name: inTitle.name };
  return { key: "other", name: "Diğer" };
}
function groupDayBySubject(tasks: StudentTask[], subjects: SubjectRef[]): SubjGroup[] {
  const map = new Map<string, SubjGroup>();
  for (const t of tasks) {
    const { key, name } = taskSubjKey(t, subjects);
    const g = map.get(key);
    if (g) g.tasks.push(t);
    else map.set(key, { key, name, order: key === "other" ? 1 : 0, tasks: [t] });
  }
  return Array.from(map.values()).sort(
    (a, b) => a.order - b.order || a.name.localeCompare(b.name, "tr"),
  );
}

const PERIOD_ORDER = ["morning", "noon", "evening", "none"] as const;
const PERIOD_LABELS: Record<string, string> = {
  morning: "Sabah", noon: "Öğle", evening: "Akşam", none: "Belirsiz",
};
function periodKey(p: string | null | undefined): string {
  return p === "morning" || p === "noon" || p === "evening" ? p : "none";
}
interface DaySection {
  pkey: string | null;
  groups: SubjGroup[];
}
function daySections(tasks: StudentTask[], subjects: SubjectRef[]): DaySection[] {
  const usePeriods = tasks.some((t) => t.period != null);
  if (!usePeriods) return [{ pkey: null, groups: groupDayBySubject(tasks, subjects) }];
  return PERIOD_ORDER.map((pk) => ({
    pkey: pk,
    groups: groupDayBySubject(tasks.filter((t) => periodKey(t.period) === pk), subjects),
  })).filter((s) => s.groups.length > 0);
}

const TASK_TYPE_LABEL: Record<string, string> = {
  test: "Test", video: "Video", ozet: "Özet", tekrar: "Tekrar", other: "Diğer",
};
function taskLabel(t: StudentTask): string {
  const first = t.items.find((it) => it.book_id != null) ?? t.items[0];
  if (first?.book_id) {
    return first.book_name + (first.section_label ? ` · ${first.section_label}` : "");
  }
  return t.title || "—";
}
const DENEME_TYPES = new Set(["brans_denemesi", "genel_deneme"]);
function taskUnit(t: StudentTask): string {
  if (t.work_block_unit) return t.work_block_unit;
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && it.book_id == null) return "soru";
  if (it?.book_type && DENEME_TYPES.has(it.book_type)) return "deneme";
  return "test";
}

function deriveSubjects(days: StudentWeekDay[]): SubjectRef[] {
  const map = new Map<number, SubjectRef>();
  for (const day of days) {
    for (const t of day.tasks) {
      for (const it of t.items) {
        if (it.subject_id != null && it.subject_name && !map.has(it.subject_id)) {
          map.set(it.subject_id, { id: it.subject_id, name: it.subject_name });
        }
      }
    }
  }
  return Array.from(map.values());
}

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentWeekPrintPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const raw = sp.start;
  const start = typeof raw === "string" ? raw : undefined;
  const qs = start ? `?start=${encodeURIComponent(start)}` : "";

  let weekData: StudentWeekResponse | null = null;
  let fetchError: string | null = null;
  try {
    weekData = await apiServer<StudentWeekResponse>(`/api/v2/student/week${qs}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    fetchError = "Hafta verisi yüklenemedi.";
  }

  if (!weekData) {
    return (
      <main className="mx-auto max-w-[800px] bg-white px-10 py-12 text-stone-900">
        <h1 className="text-xl font-bold">Haftalık Program — Çıktı</h1>
        <p className="mt-3 text-stone-600">{fetchError}</p>
      </main>
    );
  }

  // Öğrenci adı + kurum markası (/me). Kuruma bağlı öğrenci → kurum logosu;
  // bağımsız koçun öğrencisi → platform amblemi.
  let me: MyAccountResponse | null = null;
  try {
    me = await apiServer<MyAccountResponse>("/api/v2/me");
  } catch {
    me = null;
  }
  const studentName = me?.user.full_name ?? "";
  const inst = me?.institution ?? null;
  const instLogoUrl = inst?.has_logo ? inst.logo_url ?? null : null;

  const subjects = deriveSubjects(weekData.days);

  return (
    <main className="mx-auto w-full max-w-[1100px] bg-white px-6 py-4 text-stone-900 print:max-w-none print:px-0 print:py-0">
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 7mm; }
          .no-print { display: none !important; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>

      <div className="no-print mb-3 flex items-center justify-between gap-3">
        <PrintButton />
        <span className="text-xs text-stone-400">
          Yatay A4 · yazdırırken yatay seçili gelir
        </span>
      </div>

      {/* Header — solda logo (kurum veya platform) */}
      <header className="mb-2 flex items-end justify-between gap-4 border-b-2 border-stone-800 pb-1.5">
        <div className="flex items-center gap-3">
          {instLogoUrl ? (
            // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF kurum logosu ucu + yazdırma
            <img
              src={instLogoUrl}
              alt={inst?.name ?? "Kurum"}
              className="h-10 w-auto max-w-[150px] object-contain"
            />
          ) : (
            // eslint-disable-next-line @next/next/no-img-element -- platform amblemi (yazdırma)
            <img
              src="/etutkoc-mark.png"
              alt="ETÜTKOÇ Rotam"
              className="h-9 w-9 object-contain"
            />
          )}
          <div>
            <div className="flex items-baseline gap-3">
              <h1 className="text-base font-bold tracking-tight">Haftalık Program</h1>
              <span className="text-sm font-semibold text-stone-800">{studentName || "—"}</span>
            </div>
            <div className="text-[11px] text-stone-500">
              {fmtDate(weekData.start_date)} — {fmtDate(weekData.end_date)}
              {inst ? <span className="text-stone-600"> · {inst.name}</span> : null}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-stone-500">
          <span>Görev <b className="text-stone-800">{weekData.total_gorev_done}/{weekData.total_gorev}</b></span>
          {weekData.total_test_planned > 0 ? (
            <span>Test <b className="text-stone-800">{weekData.total_test_completed}/{weekData.total_test_planned}</b></span>
          ) : null}
          <span className="text-stone-400">· etütkoç·rotam</span>
        </div>
      </header>

      {/* Lejant */}
      <div className="mb-2 flex items-center gap-3 text-[9px] text-stone-500">
        <span><b className="text-emerald-700">✓</b> yapıldı</span>
        <span><b className="text-amber-700">◐</b> kısmen</span>
        <span><b className="text-stone-400">☐</b> yapılmadı</span>
        <span className="text-stone-400">· test/deneme: çözülen/planlanan · diğer: etkinlik</span>
      </div>

      {/* 7 günlük ızgara */}
      <div className="grid grid-cols-7 gap-1.5">
        {weekData.days.map((day) => (
          <DayColumn key={day.date} day={day} subjects={subjects} />
        ))}
      </div>

      <div className="no-print mt-4 text-center">
        <p className="text-xs text-stone-400">Yazdırmak için Ctrl/Cmd + P (yatay seçili gelir).</p>
      </div>
    </main>
  );
}

function DayColumn({ day, subjects }: { day: StudentWeekDay; subjects: SubjectRef[] }) {
  const sections = daySections(day.tasks, subjects);
  return (
    <section className="break-inside-avoid rounded border border-stone-300">
      <header
        className={
          "flex items-baseline justify-between px-1.5 py-1 " +
          (day.is_today ? "bg-stone-800 text-white" : "bg-stone-100")
        }
      >
        <span className="text-[10.5px] font-bold leading-tight">{day.dow_label}</span>
        <span className={"text-[8.5px] " + (day.is_today ? "text-stone-300" : "text-stone-500")}>
          {fmtShort(day.date)}
        </span>
      </header>
      <div className="px-1 py-1 space-y-1.5">
        {day.tasks.length === 0 ? (
          <p className="text-[9px] italic text-stone-400">—</p>
        ) : (
          sections.map((sec) => (
            <div key={sec.pkey ?? "_"} className="space-y-1">
              {sec.pkey ? (
                <div className="text-[8px] font-bold uppercase tracking-wider text-stone-600 border-b border-stone-300 leading-tight">
                  {PERIOD_LABELS[sec.pkey] ?? PERIOD_LABELS.none}
                </div>
              ) : null}
              {sec.groups.map((g) => (
                <div key={g.key}>
                  <div className={"text-[9px] font-bold uppercase tracking-wide leading-tight " + subjectColor(g.key, g.name)}>
                    {g.name}
                  </div>
                  <ul className="mt-0.5 space-y-0.5">
                    {g.tasks.map((t) => (
                      <TaskRow key={t.id} task={t} />
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function TaskRow({ task }: { task: StudentTask }) {
  const st = gorevState(task);
  const mark = st === "done" ? "✓" : st === "partial" ? "◐" : "☐";
  const markCls =
    st === "done" ? "text-emerald-700" : st === "partial" ? "text-amber-700" : "text-stone-400";
  const isActivity = task.planned_count <= 0 && task.items.every((it) => (it.planned ?? 0) <= 0);
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
