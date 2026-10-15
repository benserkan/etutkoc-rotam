"use client";

/**
 * K53 — Veliye dönem (seans) özeti: ÖNİZLE · DÜZENLE · GÖNDER (2026-10-12, Adım 5).
 * Seans kapanınca özet OTOMATİK HAZIRLANIR, rehber cümleleri düzenler/siler, kalem
 * listesini ve denemeyi isterse çıkarır, sonra gönderir; otomatik GİTMEZ. Sayılar
 * (yüzde, birim, kalem) ÖLÇÜM — düzenlenmez (deneme duyurusu deseni). Gönderildiyse
 * salt-okuma: gönderilen hâl gösterilir.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Info, Loader2, Mail, MailX, Plus, RotateCcw, Send, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import {
  getPoolParentSummary, poolParentSummaryKey, useSendPoolParentSummary,
  type PoolParentSummaryResponse,
} from "@/lib/api/pool";

export function PoolParentSummaryDialog({ studentId, periodId, open, onOpenChange }: {
  studentId: number; periodId: number | null; open: boolean; onOpenChange: (v: boolean) => void;
}) {
  const q = useQuery({
    queryKey: poolParentSummaryKey(studentId, periodId ?? 0),
    queryFn: () => getPoolParentSummary(studentId, periodId!),
    enabled: open && periodId != null,
  });
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl" data-section="pool:parent-summary">
        {q.isLoading || !q.data ? (
          <>
            <DialogHeader><DialogTitle>Veli özeti</DialogTitle><DialogDescription>Yükleniyor…</DialogDescription></DialogHeader>
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" aria-hidden /> Özet hazırlanıyor</div>
          </>
        ) : (
          <Body key={`${q.data.period_id}:${q.data.is_sent_snapshot}`} studentId={studentId} data={q.data} onClose={() => onOpenChange(false)} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function Body({ studentId, data, onClose }: { studentId: number; data: PoolParentSummaryResponse; onClose: () => void }) {
  const sent = data.is_sent_snapshot;
  const [lines, setLines] = React.useState<string[]>(data.narrative);
  const [includeItems, setIncludeItems] = React.useState(data.include_items);
  const [includeExam, setIncludeExam] = React.useState(data.include_exam);
  const send = useSendPoolParentSummary(studentId, data.period_id);
  const recipients = data.recipients;
  const willSend = recipients.filter((r) => r.will_send).length;

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <Mail className="size-5" aria-hidden /> {sent ? "Veliye gönderilen dönem özeti" : "Veliye dönem özeti — önizle ve gönder"}
        </DialogTitle>
        <DialogDescription>
          {data.student_name} · {data.opened_label ?? data.opened_on} – {data.closed_label ?? data.closed_on} · {data.days} gün.
          {sent ? " Bu, veliye giden içeriğin aynısıdır." : " Cümleleri düzenle, istemediğini sil; sayılar ölçümdür, değişmez. Otomatik gitmez."}
        </DialogDescription>
      </DialogHeader>

      <div className="grid grid-cols-3 gap-2 text-center" data-section="pool:parent-summary:kpi">
        <Kpi label="tamamlanma" value={`%${data.pct}`} tone="cyan" />
        <Kpi label="birim" value={`${data.done_units}/${data.total_units}`} />
        <Kpi label="kalem bitti" value={`${data.items_done}/${data.items_total}`} />
      </div>

      <section className="space-y-2" data-section="pool:parent-summary:lines">
        <h3 className="text-sm font-semibold text-foreground">Veliye gidecek cümleler</h3>
        {lines.length === 0 && <p className="text-xs text-muted-foreground">Yorum cümlesi yok — yalnız sayılar gider.</p>}
        <ul className="space-y-2">
          {lines.map((ln, i) => (
            <li key={i} className="flex items-start gap-2">
              <textarea
                className={cn("min-h-[52px] flex-1 rounded-md border bg-background px-3 py-2 text-sm text-foreground", sent && "opacity-90")}
                value={ln}
                readOnly={sent}
                aria-label={`Cümle ${i + 1}`}
                onChange={(e) => setLines((prev) => prev.map((x, j) => (j === i ? e.target.value : x)))}
              />
              {!sent && (
                <Button type="button" variant="ghost" size="icon" aria-label="Cümleyi sil"
                        onClick={() => setLines((prev) => prev.filter((_, j) => j !== i))}>
                  <Trash2 className="size-4" aria-hidden />
                </Button>
              )}
            </li>
          ))}
        </ul>
        {!sent && (
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => setLines((p) => [...p, ""])}>
              <Plus className="size-4" aria-hidden /> Cümle ekle
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setLines(data.narrative)}>
              <RotateCcw className="size-4" aria-hidden /> Sıfırla
            </Button>
          </div>
        )}
      </section>

      <section className="space-y-1 text-sm" data-section="pool:parent-summary:subjects">
        <h3 className="font-semibold text-foreground">Ders bazında (ölçüm)</h3>
        <ul className="divide-y rounded-md border">
          {data.subjects.map((r) => (
            <li key={r.subject} className="flex items-center justify-between px-3 py-1.5">
              <span className="text-foreground">{r.subject}</span>
              <span className="text-xs text-muted-foreground">{r.done}/{r.total} birim · {r.items_done}/{r.items} kalem · <b className="text-foreground">%{r.pct}</b></span>
            </li>
          ))}
        </ul>
      </section>

      <div className="flex flex-wrap gap-4 text-sm">
        <label className="inline-flex items-center gap-2">
          <input type="checkbox" checked={includeItems} disabled={sent} onChange={(e) => setIncludeItems(e.target.checked)} />
          Kalem listesi ({data.items.length})
        </label>
        {data.exam && (
          <label className="inline-flex items-center gap-2">
            <input type="checkbox" checked={includeExam} disabled={sent} onChange={(e) => setIncludeExam(e.target.checked)} />
            Deneme ({data.exam.title} · net {data.exam.net.toFixed(2)})
          </label>
        )}
        {data.carried.length > 0 && (
          <span className="text-xs text-muted-foreground">Yeni döneme taşınan {data.carried.length} kalem mailde listelenir.</span>
        )}
      </div>

      <section className="rounded-md border p-3 text-sm" data-section="pool:parent-summary:recipients">
        <h3 className="font-semibold text-foreground">Alıcılar</h3>
        {recipients.length === 0 ? (
          <p className="text-xs text-muted-foreground">Bu öğrenciye bağlı veli yok.</p>
        ) : (
          <ul className="mt-1 space-y-1">
            {recipients.map((r) => (
              <li key={r.parent_id} className="flex flex-wrap items-center gap-2">
                {r.will_send ? <Mail className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden /> : <MailX className="size-4 text-amber-600 dark:text-amber-400" aria-hidden />}
                <span className="text-foreground">{r.name}</span>
                <span className="text-xs text-muted-foreground">{r.email}</span>
                {!r.will_send && r.reason && <span className="text-xs text-amber-800 dark:text-amber-200">— {r.reason}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        Rehbere özel seans notu, öğrencinin talepleri ve onaysız öğrenci kalemleri veliye gitmez. Veli uyarı almaz (havuz modunda veli görünümü salt okumadır).
      </p>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>Kapat</Button>
        {!sent && (
          <Button
            type="button"
            disabled={send.isPending || willSend === 0}
            onClick={() => send.mutate(
              { narrative: lines.map((l) => l.trim()).filter(Boolean), include_items: includeItems, include_exam: includeExam },
              { onSuccess: onClose },
            )}
            data-testid="pool-parent-summary-send"
          >
            {send.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
            {willSend} veliye gönder
          </Button>
        )}
      </DialogFooter>
    </>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: "cyan" }) {
  return (
    <div className={cn("rounded-md border px-2 py-2", tone === "cyan"
      ? "border-cyan-200 bg-cyan-50 text-cyan-900 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-100"
      : "bg-card text-foreground")}>
      <div className="text-lg font-bold">{value}</div>
      <div className="text-[11px] opacity-80">{label}</div>
    </div>
  );
}
