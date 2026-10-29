"use client";

/**
 * Koç tarafı görev kalemi sonuç rozeti + "düzelt" akışı.
 *
 * Davranış:
 *  - completed_count > 0 + D/Y dolu → emerald rozet "8 ✓ · 2 ✗ · 0 boş" (tıkla düzelt)
 *  - completed_count > 0 + D/Y boş → "+ doğru/yanlış" linki (sonradan ekleme)
 *  - completed_count == 0 → küçük "📊 sonuç" linki (öğrenci tamamlamadıysa koç manuel ekleyebilir)
 *
 * Sheet açıldığında öğrenci CompleteSheet ile aynı bileşen kullanılır — koç
 * edit mode pre-fill ile mevcut değerlerle başlar.
 */

import * as React from "react";
import { Plus, SlidersHorizontal } from "lucide-react";

import {
  CompleteSheet,
  type CompleteSheetResult,
} from "@/components/shared/complete-sheet";
import {
  DenemeResultDialog,
  denemeSummary,
} from "@/components/shared/deneme-result-dialog";
import { useSetDenemeResultsCoach, useSetTaskItemResult } from "@/lib/hooks/use-teacher-mutations";
import type { TeacherTask, TeacherTaskItem } from "@/lib/types/teacher";

interface Props {
  studentId: number;
  dateIso: string;
  task: TeacherTask;
  item: TeacherTaskItem;
  /** Inline mode — list satırı içinde göster; default true */
  inline?: boolean;
}

export function TaskItemResultBadge(props: Props) {
  // Deneme kalemi (D2): ortak deneme sonuç penceresi (soru sayısı esnek, net, süre).
  return props.item.exam_kind ? <ExamResultBadge {...props} /> : <PlainResultBadge {...props} />;
}

function ExamResultBadge({ task, item }: Props) {
  const [open, setOpen] = React.useState(false);
  const save = useSetDenemeResultsCoach();
  const sm = denemeSummary({
    completed: item.completed_count, correct: item.correct_count, wrong: item.wrong_count,
    blank: item.blank_count, net: item.net, durationMinutes: item.duration_minutes,
    resultPending: item.result_pending,
  });
  const label = item.section_label || item.book_name || "Deneme";
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        title="Deneme sonucunu gir / düzelt"
        className={
          "ml-2 inline-flex items-center rounded-full px-1.5 py-0.5 text-[11px] font-medium tabular-nums " +
          (sm.tone === "done"
            ? "bg-emerald-600 text-white"
            : sm.tone === "pending"
              ? "bg-amber-500 text-amber-950"
              : "text-muted-foreground hover:text-foreground")
        }
      >
        {sm.tone === "todo" ? "sonuç" : sm.text}
      </button>
      <DenemeResultDialog
        open={open}
        onClose={() => setOpen(false)}
        title={`${task.title} — ${label}`}
        audience="coach"
        saving={save.isPending}
        rows={[{
          id: item.id, label, examSection: item.exam_section, questionCount: item.question_count,
          completed: item.completed_count, correct: item.correct_count, wrong: item.wrong_count,
          blank: item.blank_count, durationMinutes: item.duration_minutes,
        }]}
        onSubmit={(rows) => save.mutate({ taskId: task.id, rows }, { onSuccess: () => setOpen(false) })}
      />
    </>
  );
}

function PlainResultBadge({
  studentId,
  dateIso,
  task,
  item,
  inline = true,
}: Props) {
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const mutate = useSetTaskItemResult(studentId, dateIso);

  const hasResult =
    item.correct_count != null ||
    item.wrong_count != null ||
    item.blank_count != null;
  // Soru birimli eski kitapsız tam deneme. Kaynaksız konu kalemi ve yeni deneme
  // kalemi (exam_kind, 1 kalem = 1 deneme) değildir: D/Y/B soru, tavan yok.
  const isDeneme = item.book_id == null && item.topic_id == null && !item.exam_kind;

  function handleSubmit(r: CompleteSheetResult) {
    mutate.mutate(
      {
        taskId: task.id,
        itemId: item.id,
        body: {
          completed: r.completed,
          correct: r.correct,
          wrong: r.wrong,
          blank: r.blank,
        },
      },
      {
        onSuccess: () => setSheetOpen(false),
      },
    );
  }

  const wrapClass = inline ? "inline-flex items-center" : "flex items-center";
  // Sayfa birimli kaynaksız kalem (2026-10-22): D/Y yok — yapılan sayfa düzeltilir.
  const pageMode = item.book_id == null && item.unit === "sayfa";
  const pageRange =
    item.unit === "sayfa" && item.page_from && item.page_to
      ? `s. ${item.page_from}–${item.page_to}`
      : null;

  return (
    <>
      {pageMode ? (
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className={`${wrapClass} gap-1 ml-2 text-[11px] tabular-nums text-muted-foreground hover:text-foreground hover:underline`}
          title="Yapılan sayfayı düzelt (öğrenci adına)"
        >
          {item.completed_count}/{item.planned_count} sayfa
        </button>
      ) : hasResult ? (
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className={`${wrapClass} gap-1.5 ml-2 text-[11px] tabular-nums hover:underline`}
          title="Sonucu düzelt"
        >
          <span className="text-emerald-700 font-medium">
            {item.correct_count ?? 0}D
          </span>
          <span className="text-muted-foreground/60">·</span>
          <span className="text-rose-700 font-medium">
            {item.wrong_count ?? 0}Y
          </span>
          {(item.blank_count ?? 0) > 0 ? (
            <>
              <span className="text-muted-foreground/60">·</span>
              <span className="text-muted-foreground">{item.blank_count}B</span>
            </>
          ) : null}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setSheetOpen(true)}
          className={`${wrapClass} gap-1 ml-2 text-[11px] text-muted-foreground hover:text-foreground transition`}
          title={
            item.completed_count > 0
              ? "Doğru/yanlış ekle"
              : "Sonuç gir (öğrenci adına)"
          }
        >
          {item.completed_count > 0 ? (
            <>
              <Plus className="size-2.5" aria-hidden />
              D/Y ekle
            </>
          ) : (
            <>
              <SlidersHorizontal className="size-2.5" aria-hidden />
              sonuç
            </>
          )}
        </button>
      )}

      <CompleteSheet
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onSubmit={handleSubmit}
        taskTitle={task.title}
        itemLabel={
          item.book_name +
          (item.section_label ? ` · ${item.section_label}` : "")
        }
        planned={item.planned_count}
        initialCompleted={
          item.completed_count > 0 ? item.completed_count : item.planned_count
        }
        initialCorrect={item.correct_count}
        initialWrong={item.wrong_count}
        initialBlank={item.blank_count}
        isDeneme={isDeneme}
        unit={item.book_id == null && item.unit ? item.unit : "test"}
        pageRange={pageRange}
        saving={mutate.isPending}
      />
    </>
  );
}
