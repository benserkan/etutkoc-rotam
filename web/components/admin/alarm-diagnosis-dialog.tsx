"use client";

/**
 * Alarm Teşhis Kartı — "bu alarm ne demek, hâlâ geçerli mi, ne yapmalıyım?"
 *
 * NEDEN (2026-08-09): alarm körlüğü bu projede tekrarlayan bir sorun. Panel
 * alarmı gösteriyor ama süper admin ne yapacağını bilemiyordu; somut vakada
 * kök nedene ancak prod'da elle SQL koşturarak inildi ve alarmın KENDİSİNİN
 * hatalı olduğu görüldü. Bu kart dört şeyi tek ekranda verir:
 *   1. Sorun ŞU AN sürüyor mu (kural canlı yeniden hesaplanır)
 *   2. Sade dil: ne oldu / neden / ne yapmalı
 *   3. Kanıt: kimi/neyi ilgilendiriyor (tıklanabilir)
 *   4. Çözümleme: "çözüldü" ya da "bu yanlış alarmdı" (kural başına sayılır)
 */

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowRight, CheckCircle2, CircleSlash, Loader2,
  ShieldQuestion, Wrench,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAlarmDiagnosis } from "@/lib/api/admin";
import { useAlarmResolve } from "@/lib/hooks/use-admin-mutations";
import { fmtDateTime } from "@/components/admin/security-ui";
import type { AlarmEventItem } from "@/lib/types/admin";

/** Purge-safe ton haritası (Tailwind sınıfları statik olmalı). */
const TON: Record<string, string> = {
  rose: "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-500/30 dark:bg-rose-500/10 dark:text-rose-200",
  amber: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200",
  emerald: "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-200",
  slate: "border-slate-300 bg-slate-50 text-slate-900 dark:border-slate-500/30 dark:bg-slate-500/10 dark:text-slate-200",
};

const SORUMLU: Record<string, { etiket: string; sinif: string }> = {
  sen: { etiket: "Senin aksiyonun", sinif: "bg-cyan-600 text-white" },
  kod: { etiket: "Kod düzeltmesi gerekir", sinif: "bg-violet-600 text-white" },
  saglayici: { etiket: "Dış sağlayıcı", sinif: "bg-amber-600 text-white" },
};

export function AlarmDiagnosisDialog({
  event, open, onOpenChange,
}: {
  event: AlarmEventItem | null;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {/* İçerik yalnız açıkken mount edilir → her açılışta not alanı temiz
          başlar (effect içinde setState yasak — mount-reset deseni). */}
      {open && event ? (
        <Icerik key={event.id} event={event} onOpenChange={onOpenChange} />
      ) : null}
    </Dialog>
  );
}

function Icerik({
  event, onOpenChange,
}: {
  event: AlarmEventItem;
  onOpenChange: (v: boolean) => void;
}) {
  const q = useQuery({
    queryKey: adminKeys.alarmDiagnosis(event.id),
    queryFn: () => getAlarmDiagnosis(event.id),
  });
  const resolve = useAlarmResolve();
  const [not, setNot] = React.useState("");

  const d = q.data;

  function cozumle(yanlisAlarm: boolean) {
    resolve.mutate(
      { eventId: event.id, note: not.trim(), falsePositive: yanlisAlarm },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <DialogContent className="max-h-[88vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldQuestion className="size-5 text-cyan-600" aria-hidden />
            {event.rule_name}
          </DialogTitle>
        </DialogHeader>

        {q.isLoading ? (
          <p className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Teşhis hazırlanıyor…
          </p>
        ) : !d ? (
          <p className="py-8 text-sm text-rose-700 dark:text-rose-300">
            Teşhis yüklenemedi.
          </p>
        ) : (
          <div className="space-y-4 text-sm">
            {/* 1) CANLI DURUM — en kritik bilgi en üstte */}
            <div
              className={cn(
                "rounded-lg border p-3",
                d.hala_gecerli ? TON.rose : TON.emerald,
              )}
            >
              <div className="flex items-center gap-2 font-semibold">
                {d.hala_gecerli ? (
                  <><AlertTriangle className="size-4" aria-hidden /> Sorun şu an da sürüyor</>
                ) : (
                  <><CheckCircle2 className="size-4" aria-hidden /> Şu an geçerli değil — sorun geçmiş görünüyor</>
                )}
              </div>
              <p className="mt-1 text-[13px] leading-5">
                Alarm anında <b>{d.value}</b> {d.birim} ölçülmüştü (eşik {d.threshold}).{" "}
                {d.degerlendirme_hatasi ? (
                  <>Şu anki değer hesaplanamadı: <code className="text-[11px]">{d.degerlendirme_hatasi}</code></>
                ) : (
                  <>Şimdi ölçülen: <b>{d.guncel_deger ?? "—"}</b> {d.birim}.</>
                )}
                {!d.hala_gecerli ? " Kapatabilirsin." : ""}
              </p>
            </div>

            {/* 2) SADE DİL */}
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Ne oldu?
              </h3>
              <p className="mt-1 leading-6">{d.ne_oldu}</p>
              <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Neden tetiklenir?
              </h3>
              <p className="mt-1 leading-6 text-muted-foreground">{d.neden}</p>
            </section>

            {/* 3) NE YAPMALI */}
            <section className="rounded-lg border border-cyan-200 bg-cyan-50 p-3 dark:border-cyan-500/30 dark:bg-cyan-500/10">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-cyan-900 dark:text-cyan-200">
                  Ne yapmalısın?
                </h3>
                <span className={cn("rounded px-2 py-0.5 text-[10px] font-semibold",
                  SORUMLU[d.sorumlu]?.sinif ?? "bg-slate-600 text-white")}>
                  {SORUMLU[d.sorumlu]?.etiket ?? d.sorumlu}
                </span>
              </div>
              <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-[13px] leading-5 text-cyan-900 dark:text-cyan-100">
                {d.ne_yapmali.map((adim, i) => <li key={i}>{adim}</li>)}
              </ol>
              {d.baglantilar.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {d.baglantilar.map((b) => (
                    <Link
                      key={b.href}
                      href={b.href}
                      className="inline-flex items-center gap-1 rounded-md bg-cyan-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-cyan-800"
                    >
                      {b.etiket} <ArrowRight className="size-3" aria-hidden />
                    </Link>
                  ))}
                </div>
              ) : null}
            </section>

            {/* 4) KANIT */}
            <section>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Kimi / neyi ilgilendiriyor?
              </h3>
              {d.kanit.length === 0 ? (
                <p className="mt-1 text-[13px] text-muted-foreground">
                  Şu an bu kuralı tetikleyen kayıt bulunamadı — sorun büyük
                  olasılıkla giderilmiş.
                </p>
              ) : (
                <ul className="mt-2 space-y-1.5">
                  {d.kanit.map((k, i) => (
                    <li key={i} className={cn("rounded-md border px-3 py-2", TON[k.ton] ?? TON.slate)}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[13px] font-medium">{k.baslik}</div>
                          {k.detay ? (
                            <div className="truncate text-[12px] opacity-80">{k.detay}</div>
                          ) : null}
                        </div>
                        <div className="shrink-0 text-right">
                          {k.zaman ? (
                            <div className="text-[11px] opacity-70">{fmtDateTime(k.zaman)}</div>
                          ) : null}
                          {k.href ? (
                            <Link href={k.href} className="text-[11px] font-medium underline underline-offset-2">
                              Aç
                            </Link>
                          ) : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {/* 5) GEÇMİŞ / GÜRÜLTÜ */}
            <section className="rounded-lg border border-border bg-muted/30 p-3 text-[13px]">
              Bu kural son 30 günde <b>{d.son_30g_tetik}</b> kez çaldı;{" "}
              <b>{d.son_30g_yanlis_alarm}</b> tanesi yanlış alarm olarak işaretlendi.
              {d.gurultu_uyarisi ? (
                <p className="mt-1.5 flex items-start gap-1.5 font-medium text-amber-800 dark:text-amber-300">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  Bu kural gürültü üretiyor olabilir — eşiğini veya tanımını
                  gözden geçir, yoksa gerçek alarmlar arasında kaybolur.
                </p>
              ) : null}
            </section>

            {/* 6) ÇÖZÜMLEME */}
            {d.resolved_at ? (
              <div className={cn("rounded-lg border p-3", d.false_positive ? TON.amber : TON.emerald)}>
                <b>{d.false_positive ? "Yanlış alarm olarak kapatıldı" : "Çözüldü olarak kapatıldı"}</b>
                {" · "}{fmtDateTime(d.resolved_at)}
                {d.resolution_note ? <p className="mt-1 text-[13px]">{d.resolution_note}</p> : null}
              </div>
            ) : (
              <section>
                <label htmlFor="alarm-not" className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Çözüm notu (isteğe bağlı)
                </label>
                <textarea
                  id="alarm-not"
                  value={not}
                  onChange={(e) => setNot(e.target.value)}
                  rows={2}
                  placeholder="Örn: ZeptoMail anahtarı yenilendi, gönderim düzeldi."
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </section>
            )}
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Kapat</Button>
          {d && !d.resolved_at ? (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={resolve.isPending}
                onClick={() => cozumle(true)}
                className="border-amber-300 text-amber-800 hover:bg-amber-50 dark:text-amber-300"
              >
                <CircleSlash className="mr-1.5 size-4" aria-hidden />
                Bu yanlış alarm
              </Button>
              <Button
                disabled={resolve.isPending}
                onClick={() => cozumle(false)}
                className="bg-emerald-600 text-white hover:bg-emerald-700"
              >
                <Wrench className="mr-1.5 size-4" aria-hidden />
                Çözüldü
              </Button>
            </div>
          ) : null}
      </DialogFooter>
    </DialogContent>
  );
}
