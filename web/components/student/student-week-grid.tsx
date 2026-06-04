import Link from "next/link";
import { LayoutGrid } from "lucide-react";

import { cn } from "@/lib/utils";
import type { StudentWeekDay, StudentTask } from "@/lib/types/student";
import {
  findSubjectByExactName,
  findSubjectInTitle,
  subjectGroupKey,
  subjectToneIndex,
  type SubjectRef,
} from "@/lib/subject-match";

/**
 * Hafta Izgarası (öğrenci) — koç Hafta Izgarası'nın salt-okunur eşi.
 *
 * 7 günü YAN YANA tek bakışta gösterir: ders bazlı gruplu (periyot bölümlü) +
 * görev durumu (✓/◐/☐) + sayı/birim. Her güne tıklayınca o günün detayı açılır
 * (/student/day). Editör yok — öğrenci yalnızca görür ve gününe gider.
 *
 * Ders gruplama + ton + başlık-eşleştirme mantığı koç tarafıyla AYNI
 * (lib/subject-match) — aynı isimli ders (test + branş deneme + " · " öneki)
 * tek grupta birleşir, aynı ad daima aynı renk.
 */

type GState = "done" | "partial" | "todo";

function gorevState(t: StudentTask): GState {
  const done =
    t.status === "completed" ||
    (t.planned_count > 0 && t.completed_count >= t.planned_count);
  if (done) return "done";
  return t.completed_count > 0 ? "partial" : "todo";
}

const MARK: Record<GState, { ch: string; cls: string }> = {
  done: { ch: "✓", cls: "text-emerald-600 dark:text-emerald-400" },
  partial: { ch: "◐", cls: "text-amber-600 dark:text-amber-400" },
  todo: { ch: "☐", cls: "text-muted-foreground/60" },
};

const DENEME_TYPES = new Set(["brans_denemesi", "genel_deneme"]);

function taskUnit(t: StudentTask): string {
  if (t.work_block_unit) return t.work_block_unit; // serbest blok birimi öncelikli
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && it.book_id == null) return "soru"; // kitapsız tam deneme
  if (it?.book_type && DENEME_TYPES.has(it.book_type)) return "deneme";
  return "test";
}

function taskLabel(t: StudentTask): string {
  const first = t.items.find((it) => it.book_id != null) ?? t.items[0];
  if (first?.book_id) {
    return first.book_name + (first.section_label ? ` · ${first.section_label}` : "");
  }
  // Etkinlik: başlık "{Ders} · {içerik}" → içerik kısmını göster.
  const sep = t.title.indexOf(" · ");
  if (sep > 0 && sep < t.title.length - 3) return t.title.substring(sep + 3);
  return t.title || "—";
}

function isActivity(t: StudentTask): boolean {
  return t.planned_count <= 0 && t.items.every((it) => (it.planned ?? 0) <= 0);
}

const SUBJECT_TONES = [
  { text: "text-indigo-700 dark:text-indigo-300", dot: "bg-indigo-500" },
  { text: "text-emerald-700 dark:text-emerald-300", dot: "bg-emerald-500" },
  { text: "text-amber-700 dark:text-amber-300", dot: "bg-amber-500" },
  { text: "text-rose-700 dark:text-rose-300", dot: "bg-rose-500" },
  { text: "text-violet-700 dark:text-violet-300", dot: "bg-violet-500" },
  { text: "text-cyan-700 dark:text-cyan-300", dot: "bg-cyan-500" },
  { text: "text-fuchsia-700 dark:text-fuchsia-300", dot: "bg-fuchsia-500" },
  { text: "text-sky-700 dark:text-sky-300", dot: "bg-sky-500" },
];
const OTHER_TONE = { text: "text-muted-foreground", dot: "bg-slate-400" };

function toneForKey(key: string, name: string) {
  if (key === "other") return OTHER_TONE;
  return SUBJECT_TONES[subjectToneIndex(name, SUBJECT_TONES.length)];
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

function groupDay(tasks: StudentTask[], subjects: SubjectRef[]): SubjGroup[] {
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
  if (!usePeriods) return [{ pkey: null, groups: groupDay(tasks, subjects) }];
  return PERIOD_ORDER.map((pk) => ({
    pkey: pk,
    groups: groupDay(tasks.filter((t) => periodKey(t.period) === pk), subjects),
  })).filter((s) => s.groups.length > 0);
}

const TR_MONTHS_SHORT = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

/** Hafta görevlerinden ders listesi türet (başlık-eşleştirme için). */
function deriveSubjects(days: StudentWeekDay[]): SubjectRef[] {
  const map = new Map<number, SubjectRef>();
  for (const day of days) {
    for (const t of day.tasks) {
      for (const it of t.items) {
        if (it.subject_id != null && it.subject_name) {
          if (!map.has(it.subject_id)) {
            map.set(it.subject_id, { id: it.subject_id, name: it.subject_name });
          }
        }
      }
    }
  }
  return Array.from(map.values());
}

function SubjGroupBlock({ g }: { g: SubjGroup }) {
  const tone = toneForKey(g.key, g.name);
  return (
    <div>
      <div className="flex items-center gap-1 leading-tight">
        <span className={cn("size-1.5 rounded-full flex-shrink-0", tone.dot)} aria-hidden />
        <span className={cn("text-[10px] font-bold uppercase tracking-wide truncate", tone.text)}>
          {g.name}
        </span>
      </div>
      <ul className="mt-0.5 space-y-px">
        {g.tasks.map((t) => {
          const mk = MARK[gorevState(t)];
          return (
            <li key={t.id} className="flex items-start gap-1 text-[10px] leading-snug">
              <span className={cn("shrink-0 font-bold", mk.cls)} aria-hidden>
                {mk.ch}
              </span>
              <span className="min-w-0 flex-1 text-foreground/90">
                <span className="truncate inline-block max-w-full align-bottom">
                  {taskLabel(t)}
                </span>
                {isActivity(t) ? (
                  (t.solved_count ?? 0) > 0 ? (
                    <span className="text-muted-foreground tabular-nums">
                      {" "}· {t.solved_count} soru
                    </span>
                  ) : null
                ) : (
                  <span className="font-semibold tabular-nums text-muted-foreground">
                    {" "}{t.completed_count}/{t.planned_count} {taskUnit(t)}
                  </span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function StudentWeekGrid({ days }: { days: StudentWeekDay[] }) {
  const subjects = deriveSubjects(days);
  const totalTasks = days.reduce((a, d) => a + d.tasks.length, 0);

  return (
    <section className="rounded-xl border border-border bg-card">
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-border/60">
        <LayoutGrid className="size-4 text-muted-foreground flex-shrink-0" aria-hidden />
        <span className="text-sm font-semibold text-foreground">Hafta Izgarası</span>
        <span className="text-[11px] text-muted-foreground">
          — tüm günler bir bakışta · {totalTasks} görev
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5 px-3 pt-3 pb-2">
        {days.map((day) => {
          const sections = daySections(day.tasks, subjects);
          const doneCount = day.tasks.filter((t) => gorevState(t) === "done").length;
          const pct = Math.round(day.pct * 100);
          return (
            <Link
              key={day.date}
              href={`/student/day?date=${day.date}`}
              className={cn(
                "flex flex-col rounded-lg border min-h-[64px] overflow-hidden transition-colors",
                day.is_today
                  ? "border-foreground/25 bg-card hover:bg-muted/30"
                  : "border-border bg-card hover:bg-muted/30",
              )}
              title={`${day.dow_label} — detay için tıkla`}
            >
              <div
                className={cn(
                  "flex items-baseline justify-between px-2 py-1 border-b border-border/60",
                  day.is_today ? "bg-foreground text-background" : "bg-muted/40",
                )}
              >
                <span className="text-[11px] font-bold leading-tight">{day.dow_label}</span>
                <span
                  className={cn(
                    "text-[9px]",
                    day.is_today ? "text-background/70" : "text-muted-foreground",
                  )}
                >
                  {shortDate(day.date)}
                </span>
              </div>

              <div className="px-1.5 py-1.5 space-y-1.5 flex-1">
                {day.tasks.length === 0 ? (
                  <p className="text-[10px] italic text-muted-foreground/60">boş</p>
                ) : (
                  sections.map((sec) => (
                    <div key={sec.pkey ?? "_"} className="space-y-1">
                      {sec.pkey ? (
                        <div className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground border-b border-border/50 pb-0.5">
                          {PERIOD_LABELS[sec.pkey] ?? PERIOD_LABELS.none}
                        </div>
                      ) : null}
                      {sec.groups.map((g) => (
                        <SubjGroupBlock key={g.key} g={g} />
                      ))}
                    </div>
                  ))
                )}
              </div>

              {day.tasks.length > 0 ? (
                <div className="border-t border-border/50 px-2 py-1 space-y-1">
                  <div className="h-1 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn(
                        "h-full",
                        pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-muted-foreground/20",
                      )}
                      style={{ width: `${Math.min(100, pct)}%` }}
                      aria-hidden
                    />
                  </div>
                  <p className="text-[9px] text-muted-foreground tabular-nums">
                    {doneCount}/{day.tasks.length} görev
                    {day.test_planned > 0 ? ` · ${day.test_completed}/${day.test_planned} test` : ""}
                  </p>
                </div>
              ) : null}
            </Link>
          );
        })}
      </div>

      <p className="px-4 pb-2.5 text-[11px] text-muted-foreground">
        Bir güne tıkla → o günün detayı açılır.
        <span className="text-emerald-600"> ✓</span> yapıldı ·
        <span className="text-amber-600"> ◐</span> kısmen ·
        <span> ☐</span> yapılmadı
      </p>
    </section>
  );
}
