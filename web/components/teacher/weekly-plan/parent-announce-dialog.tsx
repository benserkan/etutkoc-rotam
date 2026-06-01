"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Loader2,
  Mail,
  Megaphone,
  MessageCircle,
} from "lucide-react";

import { getParentProgramPreview } from "@/lib/api/teacher";
import type { ParentProgramPreviewResponse } from "@/lib/types/teacher";
import { useNotifyParents } from "@/lib/hooks/use-weekly-plan-mutations";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const TYPE_LABEL: Record<string, string> = {
  test: "Test",
  video: "Video",
  ozet: "Özet",
  tekrar: "Tekrar",
  other: "Diğer",
};

/**
 * "Veliye duyur" gönderim öncesi ÖNİZLEME modalı.
 *
 * Veliye gidecek tam içeriği (gün gün program + Diğer/etkinlik görevleri dahil)
 * ve alıcı velileri gösterir. "Velilere gönder" denmeden HİÇBİR bildirim
 * gitmez (önizleme salt okuma `/program/parent-preview` ucundan gelir).
 */
export function ParentAnnounceDialog({
  studentId,
  weekStart,
  programId,
  draftTotal,
  open,
  onOpenChange,
}: {
  studentId: number;
  weekStart: string;
  programId: number | null;
  draftTotal: number;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const notifyParents = useNotifyParents(studentId);

  const q = useQuery<ParentProgramPreviewResponse>({
    queryKey: [
      "teacher", "me", "students", String(studentId),
      "parent-preview", programId ?? weekStart,
    ],
    queryFn: () => getParentProgramPreview(studentId, { start: weekStart, programId }),
    enabled: open,
    staleTime: 15_000,
  });

  function send() {
    notifyParents.mutate(
      { body: { week_start: weekStart, program_id: programId ?? undefined } },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  const data = q.data;
  const daysWithTasks = data?.daily_breakdown.filter((d) => d.has_tasks) ?? [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="inline-flex items-center gap-2">
            <Megaphone className="size-5 text-emerald-600" aria-hidden />
            Veliye duyur — önizleme
          </DialogTitle>
          <DialogDescription>
            Aşağıdaki içerik bağlı velilere e-posta (ve uygunsa WhatsApp) olarak
            gönderilecek. Göndermeden önce kontrol edin.
          </DialogDescription>
        </DialogHeader>

        {q.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Önizleme hazırlanıyor…
          </div>
        ) : q.isError || !data ? (
          <p className="py-6 text-sm text-destructive">
            Önizleme yüklenemedi. Lütfen tekrar deneyin.
          </p>
        ) : (
          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-emerald-900">
              <p>
                <b>{data.student_name}</b> · {data.week_start} — {data.week_end}
              </p>
              <p className="mt-0.5">
                Toplam <b>{data.total_tasks} yayınlanmış görev</b> velilere iletilecek.
              </p>
            </div>

            {draftTotal > 0 ? (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-900">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  {draftTotal} taslak görev YAYINLANMAMIŞ — bu duyuruya girmez.
                  İsterseniz önce &quot;Tüm haftayı yayınla&quot;.
                </span>
              </div>
            ) : null}

            {/* Alıcı veliler */}
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">Alıcı veliler</h3>
              {data.has_recipients ? (
                <ul className="space-y-1">
                  {data.recipients.map((r, i) => (
                    <li key={i} className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-medium text-foreground">{r.name}</span>
                      <span className="inline-flex items-center gap-1 text-muted-foreground">
                        <Mail className="size-3" aria-hidden /> e-posta
                        {r.whatsapp ? (
                          <>
                            <MessageCircle className="ml-1 size-3" aria-hidden /> WhatsApp
                          </>
                        ) : null}
                      </span>
                      {r.recently_notified ? (
                        <span className="text-amber-700">· son 24 saatte duyuruldu, atlanacak</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Bağlı veli yok — duyuru gönderilmez.
                </p>
              )}
            </div>

            {/* Gün gün program (veli mailindeki içerikle aynı) */}
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">Veliye gidecek program</h3>
              {daysWithTasks.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Bu pencerede yayınlanmış görev yok.
                </p>
              ) : (
                <div className="space-y-2">
                  {daysWithTasks.map((d) => (
                    <div key={d.day_iso} className="rounded-lg border border-border px-3 py-2">
                      <div className="flex items-baseline justify-between">
                        <span className="font-semibold text-foreground">
                          {d.day_name} · {d.day_label}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {d.total_planned} soru
                        </span>
                      </div>
                      <ul className="mt-1 space-y-1">
                        {d.tasks.map((t, ti) => (
                          <li key={ti} className="text-xs leading-relaxed">
                            {t.is_activity ? (
                              <span className="italic text-slate-600">
                                <span className="mr-1 rounded bg-slate-100 px-1 text-[10px] font-medium not-italic text-slate-600">
                                  {TYPE_LABEL[t.type] ?? t.type}
                                </span>
                                {t.title || "Etkinlik"}
                              </span>
                            ) : (
                              t.rows.map((r, ri) => (
                                <span key={ri} className="block text-slate-700">
                                  <span className="font-medium">{r.book}</span>
                                  {r.section ? ` · ${r.section}` : ""}
                                  <span className="text-muted-foreground"> — {r.planned} soru</span>
                                </span>
                              ))
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={notifyParents.isPending}
          >
            Vazgeç
          </Button>
          <Button
            onClick={send}
            disabled={notifyParents.isPending || q.isLoading || !data?.has_recipients}
            className="bg-emerald-600 text-white hover:bg-emerald-700"
          >
            {notifyParents.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Megaphone className="size-4" aria-hidden />
            )}
            Velilere gönder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
