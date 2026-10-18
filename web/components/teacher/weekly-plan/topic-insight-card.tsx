"use client";

import { cn } from "@/lib/utils";
import type { TeacherTask, TopicInsight } from "@/lib/types/teacher";

/**
 * Hafta ızgarası konu özeti (2026-10-18) — görevin üzerine gelince açılan kısa kart.
 * Konu ilerlemesi (Müfredat sekmesiyle aynı) · kaynak kaynak çözülen/toplam ·
 * doğru/yanlış/boş (Konu Performansı ile aynı) · denemede doğruluk.
 * Kalabalık olmasın: en çok 3 kaynak (görevin kendi kitabı başta), gerisi "+N".
 */

const STATUS_TONE: Record<TopicInsight["status"], string> = {
  tamamlandi: "bg-emerald-700 text-white",
  devam: "bg-sky-700 text-white",
  planlandi: "bg-violet-700 text-white",
  baslanmadi: "bg-slate-600 text-white",
  kaynak_yok: "bg-slate-500 text-white",
};

const LEVEL_TONE: Record<string, string> = {
  zayif: "bg-rose-700 text-white",
  dikkat: "bg-amber-600 text-white",
  iyi: "bg-emerald-700 text-white",
};

export function taskTopicIds(t: TeacherTask): number[] {
  const out: number[] = [];
  for (const it of t.items) {
    const id = it.curriculum_topic_id ?? null;
    if (id != null && !out.includes(id)) out.push(id);
  }
  return out;
}

function Bar({ value, total, tone }: { value: number; total: number; tone: string }) {
  const pct = total > 0 ? Math.min(100, Math.round((value * 100) / total)) : 0;
  return (
    <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-muted" aria-hidden>
      <span className={cn("block h-full", tone)} style={{ width: `${pct}%` }} />
    </span>
  );
}

function TopicBlock({ ins, ownBooks }: { ins: TopicInsight; ownBooks: string[] }) {
  const sources = [...ins.sources].sort((a, b) => {
    const ao = ownBooks.includes(a.book) ? 0 : 1;
    const bo = ownBooks.includes(b.book) ? 0 : 1;
    return ao - bo || b.total - a.total;
  });
  const shown = sources.slice(0, 3);
  const rest = sources.length - shown.length;
  const p = ins.perf;
  const answered = p ? p.correct + p.wrong + p.blank : 0;
  return (
    <div className="space-y-1.5" data-topic-insight={ins.topic_id}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="font-semibold">{ins.name}</span>
        <span className={cn("rounded px-1.5 py-px text-[10px] font-medium", STATUS_TONE[ins.status])}>{ins.status_label}</span>
      </div>

      {ins.test_total > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Konu ilerlemesi</span>
          <Bar value={ins.completed} total={ins.test_total} tone="bg-emerald-600" />
          <span className="tabular-nums">%{ins.pct}</span>
          <span className="tabular-nums text-muted-foreground">· {ins.completed}/{ins.test_total} test</span>
        </div>
      )}

      {shown.length > 0 && (
        <ul className="space-y-0.5">
          {shown.map((s) => (
            <li key={s.book} className="flex items-center gap-2">
              <span className={cn("min-w-0 flex-1 break-words", ownBooks.includes(s.book) && "font-medium")}>{s.book}</span>
              <Bar value={s.solved} total={s.total} tone="bg-sky-600" />
              <span className="w-12 text-right tabular-nums">{s.solved}/{s.total}</span>
            </li>
          ))}
          {rest > 0 && <li className="text-muted-foreground">+{rest} kaynak daha</li>}
        </ul>
      )}
      {ins.sourceless_completed > 0 && (
        <div className="text-muted-foreground">Kaynaksız: {ins.sourceless_completed} test çözüldü</div>
      )}
      {ins.test_total === 0 && ins.sourceless_completed === 0 && (
        <div className="text-muted-foreground">Bu konuda öğrencinin kitabı yok, henüz test çözülmedi.</div>
      )}

      <div className="border-t pt-1.5">
        {p && answered > 0 ? (
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-medium text-emerald-700 dark:text-emerald-300">{p.correct} D</span>
              <span className="font-medium text-rose-700 dark:text-rose-300">{p.wrong} Y</span>
              <span className="font-medium text-slate-600 dark:text-slate-300">{p.blank} B</span>
              {p.accuracy_pct != null && <span className="tabular-nums">· %{p.accuracy_pct} doğru</span>}
              {p.level_label && (
                <span className={cn("rounded px-1.5 py-px text-[10px] font-medium", LEVEL_TONE[p.level] ?? "bg-slate-600 text-white")}>
                  {p.level_label}
                </span>
              )}
            </div>
            <span className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted" aria-hidden>
              <span className="bg-emerald-600" style={{ width: `${(p.correct * 100) / answered}%` }} />
              <span className="bg-rose-600" style={{ width: `${(p.wrong * 100) / answered}%` }} />
              <span className="bg-slate-400" style={{ width: `${(p.blank * 100) / answered}%` }} />
            </span>
            {p.tests_solved > p.tests_with_result && (
              <div className="text-muted-foreground">
                {p.tests_solved} testin {p.tests_with_result}&apos;inde sonuç girilmiş
              </div>
            )}
          </div>
        ) : (
          <div className="text-muted-foreground">
            Doğru/yanlış girilmemiş{p && p.tests_solved > 0 ? ` (${p.tests_solved} test çözüldü)` : ""}
          </div>
        )}
        {p && p.exam_answered > 0 && p.exam_accuracy_pct != null && (
          <div className="mt-1">
            Denemelerde (son 90 gün): <span className="tabular-nums font-medium">%{p.exam_accuracy_pct}</span>
            <span className="text-muted-foreground"> · {p.exam_answered} soru</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function TopicInsightCard({ task, insights, loading, footer }: {
  task: TeacherTask;
  insights: Map<number, TopicInsight>;
  loading: boolean;
  footer: string;
}) {
  const ids = taskTopicIds(task).slice(0, 2);
  const ownBooks = task.items.map((it) => it.book_name).filter(Boolean) as string[];
  const own = task.items.find((it) => it.planned_count > 0);
  return (
    <div className="w-72 space-y-2 text-[11px] leading-snug" data-section="grid:topic-insight">
      {ids.map((id) => {
        const ins = insights.get(id);
        if (ins) return <TopicBlock key={id} ins={ins} ownBooks={ownBooks} />;
        return (
          <div key={id} className="text-muted-foreground">{loading ? "Konu özeti yükleniyor…" : "Konu özeti alınamadı."}</div>
        );
      })}
      <div className="border-t pt-1.5 text-muted-foreground">
        {own && (
          <div>
            Bu görev: <span className="tabular-nums">{own.completed_count}/{own.planned_count}</span> test
            {typeof own.section_remaining === "number" && own.book_id ? ` · bölümde kalan ${own.section_remaining}` : ""}
          </div>
        )}
        <div>{footer}</div>
      </div>
    </div>
  );
}
