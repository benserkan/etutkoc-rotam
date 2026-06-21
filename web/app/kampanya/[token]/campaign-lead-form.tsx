"use client";

import * as React from "react";
import { toast } from "sonner";
import { Check, Loader2, Sparkles } from "lucide-react";

import { api, ApiError } from "@/lib/api";

/**
 * Kampanya lead formu — ziyaretçi ad+telefon (+ ops. e-posta/not) bırakır →
 * POST /api/v2/campaign/{token}/lead → backend prospect + contact request üretir.
 */
export function CampaignLeadForm({
  token,
  isInst,
}: {
  token: string;
  isInst: boolean;
}) {
  const [name, setName] = React.useState("");
  const [phone, setPhone] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [note, setNote] = React.useState("");
  const [pending, setPending] = React.useState(false);
  const [done, setDone] = React.useState(false);

  const valid = name.trim().length >= 2 && phone.trim().length >= 10;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || pending) return;
    setPending(true);
    try {
      await api(`/api/v2/campaign/${token}/lead`, {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          phone: phone.trim(),
          email: email.trim() || undefined,
          note: note.trim() || undefined,
        }),
      });
      setDone(true);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.detail?.message ?? "Bir sorun oluştu. Lütfen tekrar dene."
          : "Bağlantı hatası. Lütfen tekrar dene.";
      toast.error(msg);
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-center shadow-sm">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-emerald-600 text-white">
          <Check className="size-6" aria-hidden />
        </div>
        <h3 className="mt-3 text-lg font-bold text-emerald-900">Talebin alındı</h3>
        <p className="mt-1.5 text-sm text-emerald-800">
          En kısa sürede seninle iletişime geçilecek. Teşekkürler!
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-bold text-slate-900">
        {isInst ? "Kurumunuz için bilgi alın" : "Hemen başlamak için bilgilerini bırak"}
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Ad ve telefonunu bırak; ekibimiz seninle iletişime geçip üyeliğini başlatsın.
      </p>
      <form onSubmit={submit} method="post" className="mt-4 space-y-3">
        <div>
          <label className="text-xs font-medium text-slate-600">Ad Soyad</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={isInst ? "Yetkili adı soyadı" : "Adın soyadın"}
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-200"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600">Telefon</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            inputMode="tel"
            placeholder="05XX XXX XX XX"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-200"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600">
            E-posta <span className="text-slate-400">(opsiyonel)</span>
          </label>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            inputMode="email"
            placeholder="ornek@eposta.com"
            className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-200"
          />
        </div>
        {isInst ? (
          <div>
            <label className="text-xs font-medium text-slate-600">
              Kurum adı / not <span className="text-slate-400">(opsiyonel)</span>
            </label>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Kurum adı, koç sayısı vb."
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-200"
            />
          </div>
        ) : null}
        <button
          type="submit"
          disabled={!valid || pending}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-cyan-800 disabled:opacity-50"
        >
          {pending ? (
            <Loader2 className="size-5 animate-spin" aria-hidden />
          ) : (
            <Sparkles className="size-5" aria-hidden />
          )}
          Bilgi al / Başvur
        </button>
        <p className="text-center text-[11px] text-slate-400">
          Bilgilerin yalnızca seninle iletişim için kullanılır.
        </p>
      </form>
    </section>
  );
}
