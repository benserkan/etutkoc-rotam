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
import { useSetTaskItemResult } from "@/lib/hooks/use-teacher-mutations";
import type { TeacherTask, TeacherTaskItem } from "@/lib/types/teacher";

interface Props {
  studentId: number;
  dateIso: string;
  task: TeacherTask;
  item: TeacherTaskItem;
  /** Inline mode — list satırı içinde göster; default true */
  inline?: boolean;
}

export function TaskItemResultBadge({
  studentId,
  dateIso,
  task,
  item,
  inline = true,
}: Props) {
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const mutate = useSetTaskItemResult(studentId, dateIso);

  const hasResult = item.correct_count != null || item.wrong_count != null;
  const isDeneme = item.book_id == null;

  function handleSubmit(r: CompleteSheetResult) {
    mutate.mutate(
      {
        taskId: task.id,
        itemId: item.id,
        body: {
          completed: r.completed,
          correct: r.correct,
          wrong: r.wrong,
        },
      },
      {
        onSuccess: () => setSheetOpen(false),
      },
    );
  }

  const wrapClass = inline ? "inline-flex items-center" : "flex items-center";

  return (
    <>
      {hasResult ? (
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
          {(() => {
            const c = item.correct_count ?? 0;
            const w = item.wrong_count ?? 0;
            const blank = Math.max(0, item.completed_count - c - w);
            return blank > 0 ? (
              <>
                <span className="text-muted-foreground/60">·</span>
                <span className="text-muted-foreground">{blank}B</span>
              </>
            ) : null;
          })()}
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
        isDeneme={isDeneme}
        saving={mutate.isPending}
      />
    </>
  );
}
