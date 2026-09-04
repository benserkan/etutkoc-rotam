"use client";

/**
 * Sınıf dönemleri — koç düzeltme arayüzü (P2 backend + P3 arayüz).
 *
 * Öğrenci sınıf atlayınca sistem bir dönem sınırı çizer:
 *   başlangıç = min(yükseltme tarihi, 1 Eylül)
 * Sınıf geçmişi kayıtlı olmadığı için geriye dönük dönemler TAHMİNDİR; yanlış
 * çıkarsa koç buradan düzeltir.
 *
 * Dönem SİLMEK görev/deneme SİLMEZ — yalnız sınırı kaldırır, aralığı komşu
 * dönem devralır. Tek dönem varsa kart hiç görünmez (yönetilecek bir şey yok).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Loader2, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import {
  deleteGradePeriod,
  getGradePeriods,
  teacherKeys,
  updateGradePeriod,
} from "@/lib/api/teacher";
import { applyInvalidate } from "@/lib/invalidate";
import type { GradePeriodListResponse } from "@/lib/types/period";

const ERR: Record<string, string> = {
  first_period_start: "İlk dönemin başlangıcı değiştirilemez.",
  start_before_previous: "Tarih, önceki dönemin başlangıcından sonra olmalı.",
  start_after_end: "Tarih bu dönemin bitişinden sonra olamaz.",
  start_after_next: "Tarih, sonraki dönemin başlangıcından önce olmalı.",
  last_period: "Tek dönem silinemez.",
  invalid_date: "Geçersiz tarih.",
};

function errText(e: unknown, fallback: string): string {
  const code =
    e instanceof ApiError
      ? ((e.detail as { code?: string } | undefined)?.code ?? "")
      : "";
  return ERR[code] ?? fallback;
}

export function GradePeriodsCard({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const q = useQuery<GradePeriodListResponse>({
    queryKey: teacherKeys.gradePeriods(studentId),
    queryFn: () => getGradePeriods(studentId),
    staleTime: 60_000,
  });
  const [edit, setEdit] = React.useState<Record<number, string>>({});

  const saveMut = useMutation({
    mutationFn: ({ id, startedOn }: { id: number; startedOn: string }) =>
      updateGradePeriod(studentId, id, startedOn),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.invalidateQueries({ queryKey: teacherKeys.gradePeriods(studentId) });
      toast.success("Dönem başlangıcı güncellendi");
      setEdit({});
    },
    onError: (e) => toast.error(errText(e, "Dönem güncellenemedi")),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => deleteGradePeriod(studentId, id),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.invalidateQueries({ queryKey: teacherKeys.gradePeriods(studentId) });
      toast.success("Dönem silindi — görevler korundu");
    },
    onError: (e) => toast.error(errText(e, "Dönem silinemedi")),
  });

  const periods = q.data?.periods ?? [];
  // Tek dönemli öğrencide yönetilecek bir sınır yok.
  if (periods.length < 2) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarRange className="size-4 text-cyan-600" aria-hidden />
          Sınıf dönemleri
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Sınıf atladığında sistem dönem sınırını{" "}
          <strong>1 Eylül</strong>e göre çizer. Geçmiş dönemler tahmindir —
          yanlışsa başlangıcı düzelt. <strong>Dönem silmek görev/deneme
          silmez</strong>, yalnız sınırı kaldırır.
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        {periods.map((p, i) => {
          const isFirst = i === periods.length - 1; // liste en yeni önce
          const draft = edit[p.id] ?? p.started_on;
          const dirty = draft !== p.started_on;
          return (
            <div
              key={p.id}
              className="flex flex-wrap items-center gap-2 rounded-lg border p-2.5 text-sm"
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {p.grade_label}
                  {p.is_current ? (
                    <span className="ml-2 rounded-full bg-cyan-100 px-2 py-0.5 text-[10px] font-medium text-cyan-900 dark:bg-cyan-500/20 dark:text-cyan-200">
                      bu dönem
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-muted-foreground">
                  {p.started_on} → {p.ended_on ?? "devam ediyor"}
                  {" · "}
                  {p.task_count} görev · {p.exam_count} deneme
                  {p.curriculum_label ? ` · ${p.curriculum_label}` : ""}
                </p>
              </div>

              {isFirst ? (
                <span className="text-xs text-muted-foreground">
                  ilk dönem — başlangıç sabit
                </span>
              ) : (
                <div className="flex items-center gap-1.5">
                  <Input
                    type="date"
                    value={draft}
                    onChange={(ev) =>
                      setEdit((prev) => ({ ...prev, [p.id]: ev.target.value }))
                    }
                    className="h-8 w-[9.5rem] text-xs"
                    aria-label="Dönem başlangıcı"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8"
                    disabled={!dirty || saveMut.isPending}
                    onClick={() =>
                      saveMut.mutate({ id: p.id, startedOn: draft })
                    }
                  >
                    {saveMut.isPending ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    ) : (
                      <Save className="size-3.5" aria-hidden />
                    )}
                    Kaydet
                  </Button>
                </div>
              )}

              <Button
                size="sm"
                variant="ghost"
                className="h-8 text-xs"
                disabled={delMut.isPending}
                onClick={() => {
                  if (
                    !window.confirm(
                      `"${p.grade_label}" dönemini silmek istiyor musunuz?\n\n` +
                        `Bu dönemdeki ${p.task_count} görev ve ${p.exam_count} deneme SİLİNMEZ — ` +
                        "aralığı komşu dönem devralır.",
                    )
                  ) {
                    return;
                  }
                  delMut.mutate(p.id);
                }}
              >
                <Trash2 className="size-3.5" aria-hidden />
                Sil
              </Button>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
