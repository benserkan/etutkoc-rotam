"use client";

import * as React from "react";
import { toast } from "sonner";
import { Check, Copy, Loader2, Landmark, Sparkles } from "lucide-react";

import { api, ApiError } from "@/lib/api";

interface HavaleInfo {
  enabled: boolean;
  iban: string;
  name: string;
  note: string;
}

type Completion = "requested" | "havale_claimed" | null;

export function MembershipActions({
  token,
  havale,
  initialCompletion,
}: {
  token: string;
  havale: HavaleInfo | null;
  initialCompletion: Completion;
}) {
  const [done, setDone] = React.useState<Completion>(initialCompletion ?? null);
  const [showHavale, setShowHavale] = React.useState(false);
  const [pending, setPending] = React.useState<"request" | "havale" | null>(null);
  const [copied, setCopied] = React.useState(false);

  async function post(path: string, kind: "request" | "havale", onOk: Completion) {
    setPending(kind);
    try {
      await api(`/api/v2/membership/${token}/${path}`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setDone(onOk);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.detail?.message ?? "Bir sorun oluştu. Lütfen tekrar dene."
          : "Bağlantı hatası. Lütfen tekrar dene.";
      toast.error(msg);
    } finally {
      setPending(null);
    }
  }

  function copyIban() {
    if (!havale?.iban) return;
    navigator.clipboard?.writeText(havale.iban.replace(/\s/g, "")).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      },
      () => toast.error("Kopyalanamadı"),
    );
  }

  if (done) {
    const isHavale = done === "havale_claimed";
    return (
      <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-center shadow-sm dark:bg-emerald-500/10 dark:border-emerald-500/30">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-emerald-600 text-white">
          <Check className="size-6" aria-hidden />
        </div>
        <h3 className="mt-3 text-lg font-bold text-emerald-900">
          {isHavale ? "Bildirimin alındı" : "Talebin alındı"}
        </h3>
        <p className="mt-1.5 text-sm text-emerald-800">
          {isHavale
            ? "Ödemen kontrol edilip üyeliğin en kısa sürede aktive edilecek. Teşekkürler!"
            : "En kısa sürede seninle iletişime geçilip üyeliğin aktive edilecek. Teşekkürler!"}
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      {/* Birincil: Üye ol / Yenile talebi */}
      <button
        type="button"
        onClick={() => post("request", "request", "requested")}
        disabled={pending !== null}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-cyan-800 disabled:opacity-50"
      >
        {pending === "request" ? (
          <Loader2 className="size-5 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="size-5" aria-hidden />
        )}
        Üyeliğimi Başlat / Yenile
      </button>
      <p className="px-1 text-center text-xs text-slate-500">
        Tek dokunuşla talep bırak — ekibimiz üyeliğini aktive etsin.
      </p>

      {/* Havale/EFT ile öde */}
      {havale?.enabled ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          {!showHavale ? (
            <button
              type="button"
              onClick={() => setShowHavale(true)}
              className="flex w-full items-center justify-center gap-2 text-sm font-medium text-slate-700 hover:text-slate-900"
            >
              <Landmark className="size-4" aria-hidden />
              Havale / EFT ile ödeyeceğim
            </button>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                <Landmark className="size-4 text-cyan-700" aria-hidden />
                Havale / EFT Bilgileri
              </div>
              <div className="rounded-lg bg-slate-50 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-semibold text-slate-900 break-all">
                    {havale.iban}
                  </span>
                  <button
                    type="button"
                    onClick={copyIban}
                    className="flex flex-shrink-0 items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-[11px] text-slate-600 hover:bg-white"
                  >
                    {copied ? <Check className="size-3" aria-hidden /> : <Copy className="size-3" aria-hidden />}
                    {copied ? "Kopyalandı" : "Kopyala"}
                  </button>
                </div>
                {havale.name ? (
                  <p className="mt-1 text-slate-600">Alıcı: {havale.name}</p>
                ) : null}
                {havale.note ? (
                  <p className="mt-1 text-[12px] text-amber-700">{havale.note}</p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => post("havale-claim", "havale", "havale_claimed")}
                disabled={pending !== null}
                className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-cyan-700 px-5 py-3 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-50 disabled:opacity-50"
              >
                {pending === "havale" ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Check className="size-4" aria-hidden />
                )}
                Ödemeyi yaptım, bildir
              </button>
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
