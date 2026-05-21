"use client";

import * as React from "react";
import Link from "next/link";

import type { WeekPrintResponse, WeekPrintTask } from "@/lib/types/student";

interface Props {
  data: WeekPrintResponse;
}

/**
 * Haftalık plan A4 yatay yazdırma — Jinja `student/week_print.html`'in
 * görsel-eşit Next.js karşılığı.
 *
 * Mimari:
 *   - 289mm × 202mm tek sayfa "sheet"
 *   - 4×2 grid: 7 gün kartı + 1 not/imza kartı
 *   - Görev sayısına göre yoğunluk modu: normal / dense / tight / ultra
 *     (font + padding küçülerek tek sayfa kısıtı altında nowrap/ellipsis korunur)
 *   - `@media print` ile araç çubuğu gizlenir, kart gölgeleri kaldırılır
 */
export function WeekPrintSheet({ data }: Props) {
  return (
    <>
      <PrintStyles />

      {/* Araç çubuğu — yazdırmada gizli */}
      <div className="no-print sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-2 flex items-center justify-between gap-3 flex-wrap">
          <div className="text-sm text-slate-600">
            <b>Yatay A4 · Tek sayfa</b> — uzun başlıklar tek satırda kesilir (…). Yazdırırken{" "}
            <kbd className="px-1.5 py-0.5 bg-slate-100 border border-slate-300 rounded text-xs">Ctrl+P</kbd>{" "}
            · <b>Düzen: Yatay</b> · <b>Kenar boşluğu: Minimum</b>
          </div>
          <div className="flex gap-2">
            <Link
              href={`/student/week?start=${data.start_date}`}
              className="text-sm px-3 py-1.5 border border-slate-300 rounded text-slate-700 hover:bg-slate-50"
            >
              ← Geri
            </Link>
            <PrintButton />
          </div>
        </div>
      </div>

      <div className="sheet">
        <header className="hdr-row flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="leading-tight">
              <div
                className="text-base font-black leading-none"
                style={{ letterSpacing: "0.05em" }}
              >
                <span style={{ color: "#117A86" }}>etütkoç</span>
                <span style={{ color: "#94a3b8", margin: "0 2px" }}>·</span>
                <span style={{ color: "#E8AC2D" }}>rotam</span>
              </div>
              <div className="text-[8px] text-slate-500 uppercase mt-0.5" style={{ letterSpacing: "0.18em" }}>
                Haftalık Çalışma Programı
              </div>
            </div>
          </div>
          <div className="text-center leading-tight">
            <div className="text-sm font-semibold text-slate-900">{data.student_name}</div>
            <div className="text-[10px] text-slate-600">
              {data.grade_level ? `${data.grade_level}. Sınıf` : null}
              {data.academic_year_name ? (
                <>
                  {data.grade_level ? " · " : ""}
                  {data.academic_year_name}
                </>
              ) : null}
              {data.exam_label && data.exam_date ? (
                <>
                  {" · "}
                  {data.exam_label}: {formatTrShort(data.exam_date)}
                </>
              ) : null}
            </div>
          </div>
          <div className="text-right leading-tight">
            <div className="text-sm font-semibold text-slate-900">
              {data.start_day} {data.start_month_label} – {data.end_day} {data.end_month_label} {data.end_year}
            </div>
            <div className="text-[10px] text-slate-500">{data.start_dow_label} başlangıçlı</div>
          </div>
        </header>

        <div className="grid-week">
          {data.days.map((d) => (
            <DayCard key={d.date} day={d} />
          ))}
          <NotesCard notes={data.week_notes} />
        </div>

        <footer className="ft-row flex items-center justify-between text-[9px] text-slate-500">
          <div>ETÜTKOÇ Rotam · Çalışma Takip Sistemi</div>
          <div>{formatTrShort(data.start_date)} haftası</div>
        </footer>
      </div>
    </>
  );
}

// =============================================================================
// Gün kartı
// =============================================================================

function DayCard({ day }: { day: WeekPrintResponse["days"][number] }) {
  const c = DAY_COLORS[day.dow_index] ?? DAY_COLORS[0];
  const density = densityFor(day.task_count);

  return (
    <div
      className={`day-card rounded-md border ${density}`}
      style={{ borderColor: c.border, background: c.bg }}
    >
      <div className="day-head text-white font-semibold" style={{ background: c.head }}>
        <div className="day-head-row">
          <span>{day.dow_label}</span>
          <span className="opacity-95 font-normal">
            {day.day_of_month} {day.month_label}
          </span>
        </div>
        <div className="day-stat-row">
          <span
            className="day-stat"
            title={`Bu öğrencinin son 12 ${day.dow_label.toLocaleLowerCase("tr-TR")} gününde tamamladığı görev oranı`}
          >
            {day.history_pct !== null ? `◷ Geçmiş %${day.history_pct}` : "◷ Geçmiş —"}
          </span>
          <span className="day-stat" title="Bu gün için planlanmış görev sayısı">
            ☰ {day.task_count} görev
          </span>
        </div>
      </div>
      <div className="day-body" style={{ color: c.text }}>
        {day.tasks.length === 0 ? (
          <div className="opacity-50 italic">—</div>
        ) : (
          day.tasks.map((t, idx) => <TaskRow key={idx} task={t} />)
        )}
      </div>
    </div>
  );
}

function TaskRow({ task }: { task: WeekPrintTask }) {
  if (task.is_single_item && task.book_name) {
    return (
      <div className="task-row" title={task.title}>
        <span className="task-main">
          <b>{task.book_name}</b>
          {task.section_label ? <> · {task.section_label}</> : null}
          {task.topic_name ? <> ({task.topic_name})</> : null}
        </span>
        <span className="task-count">{task.planned_count}</span>
      </div>
    );
  }
  return (
    <div className="task-row" title={task.title}>
      <span className="task-main">
        <b>{task.title}</b>
        {task.type_label ? (
          <span className="opacity-60 italic"> [{task.type_label}]</span>
        ) : null}
      </span>
      {task.planned_count > 0 ? <span className="task-count">{task.planned_count}</span> : null}
    </div>
  );
}

// =============================================================================
// Notlar & imza kartı
// =============================================================================

function NotesCard({ notes }: { notes: string[] }) {
  return (
    <div className="day-card rounded-md border border-slate-300 bg-slate-50">
      <div className="day-head text-white font-semibold" style={{ background: "#475569" }}>
        <div className="day-head-row">
          <span>Notlar & İmza</span>
          {notes.length > 0 ? (
            <span className="opacity-95 font-normal text-[10px]">{notes.length} madde</span>
          ) : null}
        </div>
      </div>
      <div className="day-body flex flex-col justify-between text-slate-700">
        <div className="min-h-0 flex-1 overflow-hidden">
          {notes.length > 0 ? (
            notes.map((n, idx) => (
              <div key={idx} className="flex items-start gap-1 text-[10px] leading-snug mb-0.5">
                <span className="flex-shrink-0 text-amber-700 font-bold">•</span>
                <span style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{n}</span>
              </div>
            ))
          ) : (
            <>
              <div className="opacity-60 italic text-[10px] mb-1">Not:</div>
              <div className="border-b border-slate-300 h-[10px]" />
              <div className="border-b border-slate-300 h-[10px] mt-1" />
            </>
          )}
        </div>
        <div className="mt-1 flex justify-between text-[10px] flex-shrink-0">
          <div>
            Öğrenci:
            <br />
            <span className="inline-block border-b border-slate-400 w-[65px] mt-1">&nbsp;</span>
          </div>
          <div>
            Veli:
            <br />
            <span className="inline-block border-b border-slate-400 w-[65px] mt-1">&nbsp;</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Print toolbar — window.print()
// =============================================================================

function PrintButton() {
  const onClick = React.useCallback(() => {
    if (typeof window !== "undefined") window.print();
  }, []);
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded"
    >
      🖨️ Yazdır
    </button>
  );
}

// =============================================================================
// Stiller — sayfa içinde inline. Tailwind print: variant'ı yetmiyor (A4 size,
// sheet boyutu, density mode'ları için gerçek CSS gerek).
// =============================================================================

function PrintStyles() {
  // styled-jsx yok; düz <style> dom node'una basıyoruz.
  return (
    <style
      dangerouslySetInnerHTML={{
        __html: STYLES,
      }}
    />
  );
}

const STYLES = `
@page { size: A4 landscape; margin: 4mm; }
html, body { background: #f1f5f9; }
body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #0f172a; font-size: 11px; line-height: 1.45; margin: 0; padding: 0; }
@media print {
  body { background: white; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .no-print { display: none !important; }
  .sheet { width: 289mm; height: 202mm; padding: 0; margin: 0; box-shadow: none; page-break-after: avoid; }
}
.sheet { width: 289mm; height: 202mm; padding: 0; margin: 0.5rem auto; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.08); display: flex; flex-direction: column; overflow: hidden; }
.day-card { break-inside: avoid; page-break-inside: avoid; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.day-head { font-size: 11px; padding: 3px 7px; flex-shrink: 0; line-height: 1.2; display: flex; flex-direction: column; gap: 1px; }
.day-head-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.day-stat-row { display: flex; align-items: center; justify-content: space-between; gap: 4px; font-size: 8.5px; font-weight: 500; opacity: 0.92; }
.day-stat { display: inline-flex; align-items: center; gap: 2px; background: rgba(255,255,255,0.22); padding: 0 4px; border-radius: 6px; line-height: 1.5; }
.day-body { padding: 5px 7px 6px; font-size: 11px; line-height: 1.45; flex: 1 1 0; min-height: 0; overflow: hidden; }
.task-row { display: flex; align-items: baseline; gap: 5px; padding: 2px 0; }
.task-row + .task-row { border-top: 1px dashed rgba(0,0,0,0.08); }
.task-main { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-count { flex-shrink: 0; font-weight: 700; font-size: 10.5px; padding: 0 5px; border-radius: 3px; background: rgba(15,23,42,0.1); }
.day-card.density-dense .day-body { font-size: 10px; line-height: 1.3; padding: 3px 6px 4px; }
.day-card.density-dense .task-row { padding: 1px 0; }
.day-card.density-dense .task-count { font-size: 9.5px; padding: 0 4px; }
.day-card.density-tight .day-body { font-size: 9px; line-height: 1.22; padding: 2px 5px 3px; }
.day-card.density-tight .task-row { padding: 0; gap: 4px; }
.day-card.density-tight .task-count { font-size: 8.5px; padding: 0 3px; }
.day-card.density-ultra .day-body { font-size: 8px; line-height: 1.15; padding: 2px 4px 2px; }
.day-card.density-ultra .task-row { padding: 0; gap: 3px; border-top: none !important; }
.day-card.density-ultra .task-row + .task-row { border-top: none; }
.day-card.density-ultra .task-count { font-size: 7.5px; padding: 0 2px; }
.grid-week { display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: 1fr 1fr; gap: 2mm; flex: 1 1 0; min-height: 0; }
.hdr-row { padding-bottom: 2mm; margin-bottom: 2mm; border-bottom: 1.5px solid #0f172a; flex-shrink: 0; padding-left: 4mm; padding-right: 4mm; padding-top: 2mm; }
.ft-row { padding-top: 1mm; margin-top: 1mm; border-top: 1px solid #cbd5e1; flex-shrink: 0; padding-left: 4mm; padding-right: 4mm; padding-bottom: 2mm; }
.grid-week { padding-left: 4mm; padding-right: 4mm; }
`;

// =============================================================================
// Yardımcılar
// =============================================================================

interface DayColor {
  bg: string;
  head: string;
  border: string;
  text: string;
}

const DAY_COLORS: DayColor[] = [
  { bg: "#e0f2fe", head: "#0369a1", border: "#7dd3fc", text: "#0c4a6e" }, // Pzt
  { bg: "#ffedd5", head: "#c2410c", border: "#fdba74", text: "#7c2d12" }, // Sal
  { bg: "#d1fae5", head: "#047857", border: "#6ee7b7", text: "#064e3b" }, // Çar
  { bg: "#ede9fe", head: "#6d28d9", border: "#c4b5fd", text: "#4c1d95" }, // Per
  { bg: "#ffe4e6", head: "#be123c", border: "#fda4af", text: "#881337" }, // Cum
  { bg: "#ccfbf1", head: "#0f766e", border: "#5eead4", text: "#134e4a" }, // Cmt
  { bg: "#fef3c7", head: "#b45309", border: "#fcd34d", text: "#78350f" }, // Paz
];

function densityFor(n: number): string {
  if (n >= 18) return "density-ultra";
  if (n >= 13) return "density-tight";
  if (n >= 9) return "density-dense";
  return "density-normal";
}

function formatTrShort(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}
