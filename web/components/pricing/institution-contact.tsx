"use client";

import * as React from "react";
import Script from "next/script";
import { useMutation } from "@tanstack/react-query";
import {
  Building2,
  CheckCircle2,
  Eye,
  HeartHandshake,
  Mail,
  MessageCircle,
  Phone,
  ShieldCheck,
  Users,
} from "lucide-react";

import { ApiError } from "@/lib/api";
import { submitContactRequest } from "@/lib/api/pricing";
import type { PricingCatalog } from "@/lib/types/pricing";

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

const BENEFITS: { icon: React.ElementType; title: string; body: string }[] = [
  {
    icon: Eye,
    title: "Kurum gözü — tek bakışta kontrol",
    body: "Hangi koç aktif, hangi öğrenci ihmal ediliyor, kim risk altında — hepsi tek panelde.",
  },
  {
    icon: Users,
    title: "Koç başına basit fiyat",
    body: "Öğrenci değil, koç sayısına göre öde. Her koç 30 öğrenciye kadar takip eder; koç sayısı arttıkça birim düşer.",
  },
  {
    icon: HeartHandshake,
    title: "Veli güveni → kayıt yenileme",
    body: "Veli düzenli ilerleme görür, kurumdan emin olur. Memnun veli, yenilenen kayıt demek.",
  },
  {
    icon: ShieldCheck,
    title: "30 gün ücretsiz pilot + 60 gün garanti",
    body: "Birkaç saatte kurulum, 30 gün boyunca ücretsiz deneyin. Sonuç alamazsanız 60 gün performans garantisi.",
  },
];

export function InstitutionContact({
  catalog,
  autoFocus = false,
  turnstileEnabled = false,
  turnstileSiteKey = null,
}: {
  catalog: PricingCatalog;
  autoFocus?: boolean;
  turnstileEnabled?: boolean;
  turnstileSiteKey?: string | null;
}) {
  const contact = catalog.contact;
  const sectionRef = React.useRef<HTMLDivElement>(null);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const hasRenderedRef = React.useRef(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;
  const [done, setDone] = React.useState(false);
  const [captchaError, setCaptchaError] = React.useState<string | null>(null);
  const [form, setForm] = React.useState({
    name: "",
    email: "",
    phone: "",
    institution_name: "",
    coach_count: "",
    message: "",
  });

  React.useEffect(() => {
    if (autoFocus && sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [autoFocus]);

  const renderWidget = React.useCallback(() => {
    if (!showCaptcha || !widgetRef.current || !window.turnstile) return;
    if (hasRenderedRef.current) return;
    window.turnstile.render(widgetRef.current, { sitekey: turnstileSiteKey, theme: "dark" });
    hasRenderedRef.current = true;
  }, [showCaptcha, turnstileSiteKey]);

  // Script onLoad ilk yüklemede tetikler; sekme değişimiyle bileşen remount
  // olursa (turnstile zaten yüklü) onLoad tekrar gelmez → mount'ta da dene.
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
        institution_name: form.institution_name.trim() || undefined,
        coach_count: form.coach_count ? Number(form.coach_count) : undefined,
        message: form.message.trim() || undefined,
        source: "pricing_institution",
        turnstile_token: showCaptcha ? (window.turnstile?.getResponse() ?? "") : "",
      }),
    onSuccess: () => setDone(true),
    onError: () => {
      // CAPTCHA token tek-kullanımlık → her hatadan sonra sıfırla
      if (showCaptcha && window.turnstile) window.turnstile.reset();
    },
  });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const errMsg = mut.error instanceof ApiError ? mut.error.detail.message : "Bir hata oluştu, tekrar deneyin.";
  const waHref = contact.whatsapp
    ? `https://wa.me/${contact.whatsapp.replace(/[^0-9]/g, "")}?text=${encodeURIComponent("Merhaba, kurumsal teklif almak istiyorum.")}`
    : "";

  return (
    <div
      ref={sectionRef}
      id="kurumsal"
      className="scroll-mt-20 overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-xl"
    >
      <div className="grid gap-0 lg:grid-cols-2">
        {/* Sol: anlatım */}
        <div className="p-7 sm:p-9">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-amber-300">
            <Building2 className="size-3.5" aria-hidden /> Kurumlar için
          </span>
          <h2 className="mt-4 font-display text-2xl font-extrabold sm:text-3xl">
            Kurumunuza özel çözüm
          </h2>
          <p className="mt-2 text-sm text-white/75">
            Etüt merkezi, dershane ve özel okullar için. Fiyatı koç sayınıza ve
            ihtiyacınıza göre birlikte belirliyoruz — formu doldurun, size en uygun
            teklifi hazırlayıp dönelim.
          </p>

          <ul className="mt-6 space-y-4">
            {BENEFITS.map((b) => (
              <li key={b.title} className="flex gap-3">
                <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-amber-300">
                  <b.icon className="size-5" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-semibold">{b.title}</p>
                  <p className="text-sm text-white/65">{b.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {/* Sağ: form / fallback */}
        <div className="border-t border-white/10 bg-white/5 p-7 backdrop-blur sm:p-9 lg:border-l lg:border-t-0">
          {done ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <CheckCircle2 className="size-12 text-emerald-400" aria-hidden />
              <h3 className="mt-4 font-display text-xl font-bold">Talebiniz alındı</h3>
              <p className="mt-2 max-w-xs text-sm text-white/75">
                Ekibimiz en kısa sürede sizinle iletişime geçecek. Acelesi varsa
                aşağıdaki kanallardan da ulaşabilirsiniz.
              </p>
              <ContactChannels contact={contact} waHref={waHref} className="mt-6" />
            </div>
          ) : (
            <>
              <h3 className="font-display text-lg font-bold">Kurumsal teklif alın</h3>
              <p className="mt-1 text-xs text-white/60">
                Birkaç bilgi yeterli — gerisini biz arayalım.
              </p>
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
                <Field label="Ad Soyad" required>
                  <input className={inputCls} value={form.name} onChange={set("name")} required minLength={2} placeholder="Adınız" />
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="E-posta" required>
                    <input type="email" className={inputCls} value={form.email} onChange={set("email")} required placeholder="ornek@kurum.com" />
                  </Field>
                  <Field label="Telefon">
                    <input className={inputCls} value={form.phone} onChange={set("phone")} placeholder="05xx xxx xx xx" />
                  </Field>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Kurum adı">
                    <input className={inputCls} value={form.institution_name} onChange={set("institution_name")} placeholder="Kurumunuz" />
                  </Field>
                  <Field label="Koç sayısı">
                    <input type="number" min={0} className={inputCls} value={form.coach_count} onChange={set("coach_count")} placeholder="Örn. 8" />
                  </Field>
                </div>
                <Field label="Mesajınız">
                  <textarea className={`${inputCls} min-h-20 resize-y`} value={form.message} onChange={set("message")} placeholder="İhtiyacınızı kısaca yazın (opsiyonel)" />
                </Field>

                {showCaptcha ? <div ref={widgetRef} className="min-h-[65px]" /> : null}

                {captchaError ? (
                  <p className="rounded-lg bg-rose-500/15 px-3 py-2 text-xs text-rose-200">{captchaError}</p>
                ) : null}

                {mut.isError ? (
                  <p className="rounded-lg bg-rose-500/15 px-3 py-2 text-xs text-rose-200">{errMsg}</p>
                ) : null}

                <button
                  type="submit"
                  disabled={mut.isPending}
                  className="inline-flex w-full items-center justify-center rounded-xl bg-amber-400 px-4 py-2.5 text-sm font-bold text-cyan-950 transition hover:bg-amber-300 disabled:opacity-60"
                >
                  {mut.isPending ? "Gönderiliyor…" : "Teklif iste"}
                </button>
              </form>

              <div className="mt-5 border-t border-white/10 pt-4">
                <p className="text-xs text-white/55">Form doldurmak istemez misiniz? Doğrudan ulaşın:</p>
                <ContactChannels contact={contact} waHref={waHref} className="mt-3" />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ContactChannels({
  contact,
  waHref,
  className,
}: {
  contact: PricingCatalog["contact"];
  waHref: string;
  className?: string;
}) {
  return (
    <div className={`flex flex-wrap gap-2 ${className ?? ""}`}>
      {waHref ? (
        <a href={waHref} target="_blank" rel="noopener noreferrer" className={channelCls}>
          <MessageCircle className="size-4" aria-hidden /> WhatsApp
        </a>
      ) : null}
      {contact.phone ? (
        <a href={`tel:${contact.phone.replace(/[^0-9+]/g, "")}`} className={channelCls}>
          <Phone className="size-4" aria-hidden /> {contact.phone}
        </a>
      ) : null}
      <a href={`mailto:${contact.sales_email}?subject=${encodeURIComponent("Kurumsal teklif talebi")}`} className={channelCls}>
        <Mail className="size-4" aria-hidden /> {contact.sales_email}
      </a>
    </div>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-white/70">
        {label}{required ? <span className="text-amber-300"> *</span> : null}
      </span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-white/15 bg-white/10 px-3 py-2 text-sm text-white placeholder:text-white/40 outline-none transition focus:border-amber-300/60 focus:bg-white/15";

const channelCls =
  "inline-flex items-center gap-2 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-medium text-white transition hover:bg-white/10";
