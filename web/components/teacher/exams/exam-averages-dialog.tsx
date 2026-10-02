"use client";

/**
 * Genel ortalama girişi (Faz 3) — karne katılımcı ortalamasını yazmıyorsa ya da
 * okuma eksikse koç elle girer. Elle giriş karne okumasından önceliklidir;
 * tüm alanlar boş kaydedilirse elle giriş kaldırılır (karne değeri varsa geri gelir).
 */

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { api, ApiError } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import type { ExamResultRow } from "@/lib/types/teacher";

type Result = { exam_id: number; averages: unknown; invalidate?: string[] };

const toStr = (v: number | null | undefined) => (v == null ? "" : String(v).replace(".", ","));
const parse = (v: string) => {
  const n = Number(v.replace(",", "."));
  return v.trim() === "" || Number.isNaN(n) ? null : n;
};

export function ExamAveragesButton({ row }: { row: ExamResultRow }) {
  const [open, setOpen] = React.useState(false);
  const has = !!row.averages;
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Users className="size-4" aria-hidden />
        {has ? "Ortalamayı düzenle" : "Genel ortalama gir"}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          {open ? <AveragesForm row={row} onDone={() => setOpen(false)} /> : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function AveragesForm({ row, onDone }: { row: ExamResultRow; onDone: () => void }) {
  const av = row.averages ?? null;
  const [label, setLabel] = React.useState(av?.label ?? "Genel ortalama");
  const [total, setTotal] = React.useState(toStr(av?.total));
  const [subj, setSubj] = React.useState<Record<string, string>>(() =>
    Object.fromEntries(row.subjects.map((s) => [s.name, toStr(av?.subjects[s.name])])),
  );
  const qc = useQueryClient();
  const mut = useMutation<Result, ApiError, Record<string, unknown>>({
    mutationFn: (body) =>
      api<Result>(`/api/v2/teacher/exams/${row.id}/averages`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      toast.success("Genel ortalama kaydedildi");
      onDone();
    },
    onError: (e) => toast.error(e.message || "Kaydedilemedi"),
  });
  const save = (clear = false) => {
    if (clear) {
      mut.mutate({});
      return;
    }
    const subjects: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(subj)) subjects[k] = parse(v);
    mut.mutate({ label, total: parse(total), subjects });
  };
  return (
    <>
      <DialogHeader>
        <DialogTitle>Genel ortalama</DialogTitle>
        <DialogDescription>
          Karnede katılımcıların ortalama neti yazıyorsa buraya gir; ders tablosunda öğrencinin netiyle yan
          yana gösterilir. {av?.source === "auto" ? "Şu anki değerler karneden okundu." : ""}
        </DialogDescription>
      </DialogHeader>
      <div className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Ortalamanın adı</span>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              maxLength={60}
              placeholder="Genel ortalama / Kurum ortalaması"
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Ortalamanın adı"
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Toplam ortalama net</span>
            <input
              inputMode="decimal"
              value={total}
              onChange={(e) => setTotal(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              aria-label="Toplam ortalama net"
            />
          </label>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {row.subjects.map((s) => (
            <label key={s.name} className="flex items-center justify-between gap-2 text-sm">
              <span className="min-w-0 break-words">
                {s.name}
                <span className="ml-1 text-[11px] text-muted-foreground">(öğrenci {toStr(s.net)})</span>
              </span>
              <input
                inputMode="decimal"
                value={subj[s.name] ?? ""}
                onChange={(e) => setSubj((o) => ({ ...o, [s.name]: e.target.value }))}
                className="h-8 w-20 shrink-0 rounded-md border border-input bg-background px-2 text-sm"
                aria-label={`${s.name} ortalama net`}
              />
            </label>
          ))}
        </div>
      </div>
      <DialogFooter className="gap-2">
        {av?.source === "manual" ? (
          <Button variant="outline" onClick={() => save(true)} disabled={mut.isPending}>
            Elle girişi kaldır
          </Button>
        ) : null}
        <Button onClick={() => save()} disabled={mut.isPending}>
          Kaydet
        </Button>
      </DialogFooter>
    </>
  );
}
