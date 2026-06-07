"use client";

import * as React from "react";
import Link from "next/link";
import Script from "next/script";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Clock,
  Headphones,
  Mail,
  MessageCircle,
  Phone,
  Send,
  ShieldCheck,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { submitContactRequest } from "@/lib/api/pricing";
import type { PricingCatalog } from "@/lib/types/pricing";
import { BrandLogo } from "@/components/brand-logo";
import { FloatingWhatsApp } from "@/components/contact/floating-whatsapp";

interface TurnstileApi {
  render: (el: HTMLElement, opts: Record<string, unknown>) => string;
  reset: (id?: string) => void;
  getResponse: (id?: string) => string | undefined;
}
declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

const TOPICS = [
  { value: "iletisim_genel", label: "Genel soru" },
  { value: "iletisim_kurumsal", label: "Kurumsal teklif (etüt / dershane / okul)" },
  { value: "iletisim_destek", label: "Teknik destek" },
  { value: "iletisim_isbirligi", label: "İş birliği / Basın" },
];

export function IletisimClient({
  catalog,
  initialTopic = "",
  turnstileEnabled = false,
  turnstileSiteKey = null,
}: {
  catalog: PricingCatalog;
  initialTopic?: string;
  turnstileEnabled?: boolean;
  turnstileSiteKey?: string | null;
}) {
  const contact = catalog.contact;
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const hasRenderedRef = React.useRef(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;
  const [done, setDone] = React.useState(false);
  const [captchaError, setCaptchaError] = React.useState<string | null>(null);
  const validTopic = TOPICS.some((t) => t.value === initialTopic) ? initialTopic : "iletisim_genel";
  const [form, setForm] = React.useState({
    name: "",
    email: "",
    phone: "",
    topic: validTopic,
    message: "",
  });

  const renderWidget = React.useCallback(() => {
    if (!showCaptcha || !widgetRef.current || !window.turnstile) return;
    if (hasRenderedRef.current) return;
    window.turnstile.render(widgetRef.current, { sitekey: turnstileSiteKey, theme: "light" });
    hasRenderedRef.current = true;
  }, [showCaptcha, turnstileSiteKey]);

  React.useEffect(() => {
    if (showCaptcha && window.turnstile) renderWidget();
  }, [showCaptcha, renderWidget]);

  // eslint-disable-next-line lgs/missing-invalidate -- public form; istemcide tazelenecek query yok (kayıt süper admin panelinde görünür)
  const mut = useMutation({
    mutationFn: () =>
      submitContactRequest({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        message: form.message.trim() || undefined,
        source: form.topic,
        turnstile_token: showCaptcha ? (window.turnstile?.getResponse() ?? "") : "",
      }),
    onSuccess: () => setDone(true),
    onError: () => {
      if (showCaptcha && window.turnstile) window.turnstile.reset();
    },
  });

  const setF = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  const errMsg = mut.error instanceof ApiError ? mut.error.detail.message : "Bir hata oluştu, tekrar deneyin.";
  const waDigits = (contact.whatsapp ?? "").replace(/[^0-9]/g, "");
  const waHref = waDigits
    ? `https://wa.me/${waDigits}?text=${encodeURIComponent("Merhaba, ETÜTKOÇ Rotam hakkında bilgi almak istiyorum.")}`
    : "";
  const telDigits = (contact.phone ?? "").replace(/[^0-9+]/g, "");

  return (
    <div className="force-light min-h-screen bg-gradient-to-b from-cyan-50/60 to-white text-slate-900">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-5">
        <BrandLogo />
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-600 hover:text-cyan-700">
          <ArrowLeft className="size-4" aria-hidden /> Anasayfa
        </Link>
      </header>

      <main className="mx-auto max-w-5xl px-5 pb-20">
        {/* Hero */}
        <section className="pt-6 text-center sm:pt-10">
          <span className="inline-flex items-center gap-2 rounded-full bg-cyan-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-cyan-800">
            <Headphones className="size-3.5" aria-hidden /> İletişim
          </span>
          <h1 className="mt-4 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Size nasıl yardımcı olabiliriz?
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-base text-slate-600">
            Bağımsız koç musunuz, bir kurumu mu yönetiyorsunuz, yoksa mevcut bir
            sorunuz mu var — doğru ekibe ulaştıralım. Genelde aynı gün dönüş yapıyoruz.
          </p>
        </section>

        <div className="mt-10 grid gap-6 lg:grid-cols-5">
          {/* Sol: kanallar */}
          <aside className="space-y-3 lg:col-span-2">
            {waHref ? (
              <ChannelCard
                href={waHref} external icon={MessageCircle} tone="emerald"
                title="WhatsApp" sub="Anında yazışma — en hızlı kanal"
              />
            ) : null}
            {telDigits ? (
              <ChannelCard
                href={`tel:${telDigits}`} icon={Phone} tone="cyan"
                title="Telefon" sub={contact.phone}
              />
            ) : null}
            <ChannelCard
              href={`mailto:${contact.sales_email}`} icon={Building2} tone="amber"
              title="Kurumsal / satış" sub={contact.sales_email}
            />
            <ChannelCard
              href={`mailto:${contact.support_email}`} icon={Mail} tone="slate"
              title="Teknik destek" sub={contact.support_email}
            />
            <div className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-white p-4">
              <Clock className="mt-0.5 size-5 text-slate-400" aria-hidden />
              <div>
                <p className="text-sm font-semibold text-slate-800">Çalışma saatleri</p>
                <p className="text-sm text-slate-500">Hafta içi 09:00–18:00. Form 7/24 açık.</p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-2xl border border-cyan-100 bg-cyan-50/60 p-4">
              <ShieldCheck className="mt-0.5 size-5 text-cyan-600" aria-hidden />
              <p className="text-sm text-cyan-900">
                Bilgileriniz KVKK&apos;ya uygun işlenir; yalnızca size dönüş yapmak için kullanılır.
              </p>
            </div>
          </aside>

          {/* Sağ: form */}
          <div className="lg:col-span-3">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
              {done ? (
                <div className="flex flex-col items-center py-10 text-center">
                  <CheckCircle2 className="size-14 text-emerald-500" aria-hidden />
                  <h2 className="mt-4 font-display text-xl font-bold">Mesajınız bize ulaştı</h2>
                  <p className="mt-2 max-w-sm text-sm text-slate-600">
                    En kısa sürede dönüş yapacağız. Acelesi varsa soldaki kanallardan
                    doğrudan da ulaşabilirsiniz.
                  </p>
                  <Link href="/" className="mt-6 inline-flex items-center gap-1.5 rounded-xl bg-cyan-700 px-4 py-2.5 text-sm font-bold text-white hover:bg-cyan-800">
                    Anasayfaya dön
                  </Link>
                </div>
              ) : (
                <>
                  <h2 className="font-display text-xl font-bold">Mesaj gönderin</h2>
                  <p className="mt-1 text-sm text-slate-500">Birkaç bilgi yeterli — gerisini biz halledelim.</p>
                  {showCaptcha ? (
                    <Script
                      src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
                      strategy="afterInteractive"
                      onLoad={renderWidget}
                    />
                  ) : null}
                  <form
                    method="post"
                    className="mt-5 space-y-3"
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (mut.isPending) return;
                      if (showCaptcha && !window.turnstile?.getResponse()) {
                        setCaptchaError("Lütfen güvenlik doğrulamasını tamamlayın.");
                        return;
                      }
                      setCaptchaError(null);
                      mut.mutate();
                    }}
                  >
                    <Field label="Konu">
                      <select className={inputCls} value={form.topic} onChange={setF("topic")}>
                        {TOPICS.map((t) => (
                          <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Ad Soyad" required>
                      <input className={inputCls} value={form.name} onChange={setF("name")} required minLength={2} placeholder="Adınız" />
                    </Field>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <Field label="E-posta" required>
                        <input type="email" className={inputCls} value={form.email} onChange={setF("email")} required placeholder="ornek@eposta.com" />
                      </Field>
                      <Field label="Telefon">
                        <input className={inputCls} value={form.phone} onChange={setF("phone")} placeholder="05xx xxx xx xx" />
                      </Field>
                    </div>
                    <Field label="Mesajınız" required>
                      <textarea className={`${inputCls} min-h-28 resize-y`} value={form.message} onChange={setF("message")} required placeholder="Nasıl yardımcı olabiliriz?" />
                    </Field>

                    {showCaptcha ? <div ref={widgetRef} className="min-h-[65px]" /> : null}
                    {captchaError ? <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{captchaError}</p> : null}
                    {mut.isError ? <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{errMsg}</p> : null}

                    <button
                      type="submit"
                      disabled={mut.isPending}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-4 py-3 text-sm font-bold text-white transition hover:bg-cyan-800 disabled:opacity-60"
                    >
                      {mut.isPending ? "Gönderiliyor…" : (<><Send className="size-4" aria-hidden /> Gönder</>)}
                    </button>
                  </form>
                </>
              )}
            </div>
          </div>
        </div>
      </main>

      <FloatingWhatsApp phone={contact.whatsapp} />
    </div>
  );
}

function ChannelCard({
  href, external, icon: Icon, tone, title, sub,
}: {
  href: string; external?: boolean; icon: React.ElementType;
  tone: "emerald" | "cyan" | "amber" | "slate"; title: string; sub: string;
}) {
  const tones: Record<string, string> = {
    emerald: "text-emerald-600 bg-emerald-50",
    cyan: "text-cyan-700 bg-cyan-50",
    amber: "text-amber-600 bg-amber-50",
    slate: "text-slate-600 bg-slate-100",
  };
  return (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-cyan-300 hover:shadow-sm"
    >
      <span className={`inline-flex size-11 shrink-0 items-center justify-center rounded-xl ${tones[tone]}`}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-sm font-semibold text-slate-800">{title}</p>
        <p className="truncate text-sm text-slate-500">{sub}</p>
      </div>
    </a>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">
        {label}{required ? <span className="text-cyan-600"> *</span> : null}
      </span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20";
