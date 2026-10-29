"use client";

/**
 * Veli — koça talep (P3). "Koça yeni soru" (çocuk seçimli, parent endpoint) +
 * SupportCenter ile liste/thread/yanıt (çift yönlü; koç gelen kutusunda görür).
 */
import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";

import { ApiError } from "@/lib/api";
import { createParentCoachRequest } from "@/lib/api/parent";
import type { SupportListResponse } from "@/lib/types/support";
import { SupportCenter } from "@/components/support/support-center";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: "progress_question", label: "Gidişat sorusu" },
  { value: "exam_comment", label: "Deneme yorumu" },
  { value: "other", label: "Diğer" },
];

interface Child { id: number; name: string }

export function ParentSupportClient({ initial, childList }: { initial: SupportListResponse; childList: Child[] }) {
  const qc = useQueryClient();
  const sp = useSearchParams();
  const qpChild = sp.get("child");
  const qpCategory = sp.get("category");
  const [open, setOpen] = React.useState(!!qpChild);
  const [childId, setChildId] = React.useState<number | "">(
    qpChild ? Number(qpChild) : childList.length === 1 ? childList[0].id : "",
  );
  const [category, setCategory] = React.useState(
    qpCategory && CATEGORIES.some((c) => c.value === qpCategory) ? qpCategory : "progress_question",
  );
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const [err, setErr] = React.useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: () => createParentCoachRequest(Number(childId), { category, subject: subject.trim(), body: body.trim() }),
    onMutate: () => setErr(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["support", "mine"] });
      setOpen(false);
      setSubject(""); setBody(""); setCategory("progress_question");
    },
    onError: (e) => setErr(e instanceof ApiError ? (e.detail?.message ?? e.message) : "Gönderilemedi."),
  });

  const canSend = childId !== "" && subject.trim().length > 0 && body.trim().length > 0 && !createMut.isPending;

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight font-display">Koça Talep</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Çocuğunuzun koçuna soru/talep iletin (deneme yorumu, gidişat sorusu); yanıtları buradan takip edin.
          </p>
        </div>
        <button onClick={() => setOpen(true)}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-[#117A86] px-3 py-2 text-sm font-semibold text-white hover:bg-[#0E5F69]">
          <MessageSquarePlus className="size-4" aria-hidden /> Koça yeni soru
        </button>
      </div>

      <SupportCenter view="mine" initial={initial} canCreate={false} title="" description="" />

      {open ? (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center" onClick={() => setOpen(false)}>
          <div className="w-full max-w-lg rounded-t-2xl bg-card p-5 sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-base font-bold text-foreground">Koça yeni soru / talep</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">Çocuğunuzun koçuna iletilir; koç yanıtladığında bildirim alırsınız.</p>

            <div className="mt-4 space-y-3">
              {childList.length > 1 ? (
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Çocuk</label>
                  <select value={childId} onChange={(e) => setChildId(e.target.value === "" ? "" : Number(e.target.value))}
                    className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                    <option value="">— seçin —</option>
                    {childList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              ) : null}
              <div>
                <label className="text-xs font-medium text-muted-foreground">Konu türü</label>
                <select value={category} onChange={(e) => setCategory(e.target.value)}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm">
                  {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Başlık</label>
                <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200}
                  placeholder="örn. Son deneme hakkında" className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Mesajınız</label>
                <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={4000} rows={4}
                  placeholder="Koçunuza iletmek istediğiniz soru/talep…" className="mt-1 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm" />
              </div>
              {err ? <p className="text-sm text-rose-600">{err}</p> : null}
            </div>

            <div className="mt-4 flex gap-2">
              <button onClick={() => setOpen(false)} className="flex-1 rounded-xl border border-border py-2.5 text-sm font-semibold text-muted-foreground hover:bg-muted/50">Vazgeç</button>
              <button onClick={() => createMut.mutate()} disabled={!canSend}
                className={cn("flex-1 rounded-xl py-2.5 text-sm font-semibold text-white", canSend ? "bg-[#117A86] hover:bg-[#0E5F69]" : "bg-[#117A86]/40")}>
                {createMut.isPending ? "Gönderiliyor…" : "Koça gönder"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
