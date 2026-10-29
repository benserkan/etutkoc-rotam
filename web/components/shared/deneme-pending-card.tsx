"use client";

/**
 * Sonucu girilmemiş denemeler (D3, 2026-10-20).
 *
 * Çözüldü işaretlenmiş ama doğru/yanlışı girilmemiş deneme satırları. Sonuç girilince
 * deneme Denemeler'e (net grafiği, gelişim raporu) kendiliğinden yazılır. Liste boşsa
 * kart hiç çizilmez. Öğrenci (Bugün, Denemelerim) ve koç (Denemeler sekmesi) ortak.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";
import { toast } from "sonner";

import { DenemeResultDialog, type DenemeRowOutput } from "@/components/shared/deneme-result-dialog";
import { Button } from "@/components/ui/button";
import { api, type ApiError, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";

export interface DenemePendingRow {
  task_id: number;
  item_id: number;
  date: string;
  task_title: string;
  label: string;
  exam_kind: string;
  question_count: number | null;
  days_waiting: number;
  exam_section: string | null;
  duration_minutes: number | null;
}

export interface DenemePendingResponse {
  count: number;
  tasks: number;
  rows: DenemePendingRow[];
}

type Audience = { kind: "student" } | { kind: "coach"; studentId: number };

export function denemePendingKey(a: Audience) {
  return a.kind === "student"
    ? (["student", "deneme-pending"] as const)
    : (["teacher", "me", "students", String(a.studentId), "deneme-pending"] as const);
}

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

function waitText(days: number): string {
  if (days <= 0) return "bugün";
  if (days === 1) return "dün";
  return `${days} gün önce`;
}

export function DenemePendingCard({ audience }: { audience: Audience }) {
  const qc = useQueryClient();
  const url =
    audience.kind === "student"
      ? "/api/v2/student/deneme-pending"
      : `/api/v2/teacher/students/${audience.studentId}/deneme-pending`;
  const q = useQuery<DenemePendingResponse>({
    queryKey: denemePendingKey(audience),
    queryFn: () => api<DenemePendingResponse>(url),
    staleTime: 30_000,
  });
  const [openRow, setOpenRow] = React.useState<DenemePendingRow | null>(null);
  const save = useMutation<MutationResponse<unknown>, ApiError, { row: DenemePendingRow; rows: DenemeRowOutput[] }>({
    mutationFn: ({ row, rows }) =>
      api<MutationResponse<unknown>>(
        audience.kind === "student"
          ? `/api/v2/student/tasks/${row.task_id}/deneme-results`
          : `/api/v2/teacher/tasks/${row.task_id}/deneme-results`,
        { method: "POST", body: JSON.stringify({ rows }) },
      ),
    onError: (err) =>
      toast.error("Sonuç kaydedilemedi", { description: err.message || "Sunucu hatası." }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      void qc.invalidateQueries({ queryKey: denemePendingKey(audience) });
      toast.success("Deneme sonucu kaydedildi — Denemeler'e işlendi");
      setOpenRow(null);
    },
  });

  const data = q.data;
  if (!data || data.count === 0) return null;
  const isCoach = audience.kind === "coach";
  return (
    <section
      data-section="deneme-pending"
      className="rounded-xl border border-amber-300 bg-amber-50 p-4"
    >
      <div className="flex items-start gap-3">
        <ClipboardList className="mt-0.5 size-5 shrink-0 text-amber-700" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-amber-950">
            Sonucu girilmemiş {data.count} deneme
          </h3>
          <p className="mt-0.5 text-xs text-amber-900">
            {isCoach
              ? "Öğrenci bu denemeleri çözdü ama doğru/yanlışını girmedi. Seansta birlikte girebilirsin; girilen sonuç Denemeler'e ve net grafiğine işlenir."
              : "Bu denemeleri çözdün ama doğru/yanlışını girmedin. Sonucu girince Denemelerim'e ve net grafiğine işlenir."}
          </p>
          <ul className="mt-3 space-y-2">
            {data.rows.map((r) => (
              <li
                key={r.item_id}
                data-testid="deneme-pending-row"
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg bg-card px-3 py-2 ring-1 ring-amber-200"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium break-words text-foreground">{r.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {fmtDate(r.date)} · {waitText(r.days_waiting)}
                    {r.question_count ? ` · ${r.question_count} soru` : ""}
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  onClick={() => setOpenRow(r)}
                  className="bg-cyan-700 text-white hover:bg-cyan-800"
                >
                  Sonucu gir
                </Button>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <DenemeResultDialog
        open={openRow != null}
        onClose={() => setOpenRow(null)}
        title={openRow ? openRow.label : "Deneme sonucu"}
        audience={isCoach ? "coach" : "student"}
        saving={save.isPending}
        rows={
          openRow
            ? [{
                id: openRow.item_id,
                label: openRow.label,
                examSection: openRow.exam_section,
                questionCount: openRow.question_count,
                completed: 1,
                correct: null,
                wrong: null,
                blank: null,
                durationMinutes: openRow.duration_minutes,
              }]
            : []
        }
        onSubmit={(rows) => openRow && save.mutate({ row: openRow, rows })}
      />
    </section>
  );
}
