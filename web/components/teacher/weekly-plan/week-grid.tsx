"use client";

import * as React from "react";
import { ChevronDown, LayoutGrid } from "lucide-react";

import { cn } from "@/lib/utils";
import type { TeacherStudentWeekDay, TeacherTask } from "@/lib/types/teacher";
import {
  findSubjectByExactName,
  findSubjectInTitle,
  type SubjectRef,
} from "@/lib/subject-match";

/**
 * Hafta Izgarası (Katman 2) — 7 günü YAN YANA, hep görünür tek bakış.
 *
 * Amaç: koç bir günü planlarken geçmiş/gelecek günleri aynı anda görür
 * ("geçmişe bakarak geleceği planlamak"). Tek-açık akordeonun üstünde durur;
 * bir güne tıklayınca o günün düzenleyicisi aşağıda açılır + oraya kaydırılır.
 * Salt-okuma özet: ders bazlı gruplu + görev durumu + sayı/birim.
 */

type GState = "done" | "partial" | "todo";

function gorevState(t: TeacherTask): GState {
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

function taskUnit(t: TeacherTask): string {
  if (t.work_block_unit) return t.work_block_unit; // serbest blok birimi öncelikli
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && it.book_id == null) return "soru"; // kitapsız tam deneme
  if (it?.book_type && DENEME_TYPES.has(it.book_type)) return "deneme";
  return "test";
}

function taskLabel(t: TeacherTask): string {
  const first = t.items.find((it) => it.book_id != null) ?? t.items[0];
  if (first?.book_id) {
    return (
      first.book_name + (first.section_label ? ` · ${first.section_label}` : "")
    );
  }
  // Etkinlik: başlık "{Ders} · {içerik}" → içerik kısmını göster.
  const sep = t.title.indexOf(" · ");
  if (sep > 0 && sep < t.title.length - 3) return t.title.substring(sep + 3);
  return t.title || "—";
}

function isActivity(t: TeacherTask): boolean {
  return (
    t.planned_count <= 0 && t.items.every((it) => (it.planned_count ?? 0) <= 0)
  );
}

// Ders bazlı renk — day-board ile aynı stable hash → ton.
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

function nameHash(name: string): number {
  return Math.abs(
    Array.from(name).reduce((h, c) => (h * 31 + c.charCodeAt(0)) | 0, 0),
  );
}

// Grup anahtarına göre ton: "s{id}" → subject hash · "n:.." → ad hash · other → nötr.
function toneForKey(key: string, name: string) {
  if (key === "other") return OTHER_TONE;
  if (key.startsWith("s")) {
    const id = Number(key.slice(1));
    if (Number.isFinite(id)) return SUBJECT_TONES[Math.abs(id) % SUBJECT_TONES.length];
  }
  return SUBJECT_TONES[nameHash(name) % SUBJECT_TONES.length];
}

interface SubjGroup {
  key: string;
  name: string;
  order: number;
  tasks: TeacherTask[];
}

// Görevin ders grubu — item subject'i; " · " öneki (video/blok); branş/genel deneme
// başlığında ders adı (subjects ile). Bilinen ders → `s{id}` (test ile birleşir).
function taskSubjKey(t: TeacherTask, subjects?: SubjectRef[]): { key: string; name: string } {
  const ws = t.items.find((it) => it.subject_id != null);
  if (ws?.subject_id != null) {
    return { key: `s${ws.subject_id}`, name: ws.subject_name ?? "Ders" };
  }
  if (t.items.length === 0 || t.work_block_id != null) {
    const sep = t.title.indexOf(" · ");
    if (sep > 0 && sep < t.title.length - 3) {
      const nm = t.title.substring(0, sep);
      const resolved = findSubjectByExactName(nm, subjects);
      if (resolved) return { key: `s${resolved.id}`, name: resolved.name };
      return { key: `n:${nm.toLocaleLowerCase("tr")}`, name: nm };
    }
  }
  const inTitle = findSubjectInTitle(t.title, subjects);
  if (inTitle) return { key: `s${inTitle.id}`, name: inTitle.name };
  return { key: "other", name: "Diğer" };
}

function groupDay(tasks: TeacherTask[], subjects?: SubjectRef[]): SubjGroup[] {
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

// Periyot (Sabah/Öğle/Akşam) — gün periyotluysa alt bölümler.
const PERIOD_ORDER = ["morning", "noon", "evening", "none"] as const;
const PERIOD_LABELS: Record<string, string> = {
  morning: "Sabah", noon: "Öğle", evening: "Akşam", none: "Belirsiz",
};
function periodKey(p: string | null | undefined): string {
  return p === "morning" || p === "noon" || p === "evening" ? p : "none";
}

interface DaySection {
  pkey: string | null; // null = periyot kullanılmıyor
  groups: SubjGroup[];
}
function daySections(tasks: TeacherTask[], subjects?: SubjectRef[]): DaySection[] {
  const usePeriods = tasks.some((t) => t.period != null);
  if (!usePeriods) return [{ pkey: null, groups: groupDay(tasks, subjects) }];
  return PERIOD_ORDER.map((pk) => ({
    pkey: pk,
    groups: groupDay(
      tasks.filter((t) => periodKey(t.period) === pk),
      subjects,
    ),
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

export function WeekGrid({
  days,
  subjects,
  openDate,
  onOpenDay,
}: {
  days: TeacherStudentWeekDay[];
  subjects: SubjectRef[];
  openDate: string | null;
  onOpenDay: (date: string) => void;
}) {
  const [collapsed, setCollapsed] = React.useState(false);

  const totalTasks = days.reduce((a, d) => a + d.tasks.length, 0);

  return (
    <section className="rounded-xl border border-border bg-card">
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-left"
        aria-expanded={!collapsed}
      >
        <LayoutGrid className="size-4 text-muted-foreground flex-shrink-0" aria-hidden />
        <span className="text-sm font-semibold text-foreground">
          Hafta Izgarası
        </span>
        <span className="text-[11px] text-muted-foreground">
          — tüm günler bir bakışta · {totalTasks} görev
        </span>
        <ChevronDown
          className={cn(
            "ml-auto size-4 text-muted-foreground transition-transform",
            collapsed ? "" : "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {collapsed ? null : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-1.5 px-3 pb-3">
            {days.map((day) => {
              const sections = daySections(day.tasks, subjects);
              const isOpen = openDate === day.date;
              const doneCount = day.tasks.filter(
                (t) => gorevState(t) === "done",
              ).length;
              return (
                <button
                  key={day.date}
                  type="button"
                  onClick={() => onOpenDay(day.date)}
                  className={cn(
                    "flex flex-col text-left rounded-lg border min-h-[64px] overflow-hidden transition-colors",
                    isOpen
                      ? "border-foreground/40 ring-1 ring-foreground/10 bg-muted/40"
                      : day.is_today
                        ? "border-foreground/25 bg-card hover:bg-muted/30"
                        : "border-border bg-card hover:bg-muted/30",
                  )}
                  title={`${day.dow_label} — düzenlemek için tıkla`}
                >
                  <div
                    className={cn(
                      "flex items-baseline justify-between px-2 py-1 border-b border-border/60",
                      day.is_today ? "bg-foreground text-background" : "bg-muted/40",
                    )}
                  >
                    <span className="text-[11px] font-bold leading-tight">
                      {day.dow_label}
                    </span>
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
                      <p className="text-[10px] italic text-muted-foreground/60">
                        boş
                      </p>
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
                    <div className="px-2 py-0.5 border-t border-border/50 text-[9px] text-muted-foreground tabular-nums">
                      {doneCount}/{day.tasks.length} tamam
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
          <p className="px-4 pb-2.5 text-[11px] text-muted-foreground italic">
            Bir güne tıkla → o günün düzenleyicisi aşağıda açılır.
            <span className="not-italic"> ✓</span> yapıldı ·
            <span className="not-italic"> ◐</span> kısmen ·
            <span className="not-italic"> ☐</span> yapılmadı
          </p>
        </>
      )}
    </section>
  );
}
