"use client";

import * as React from "react";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2, ShieldCheck } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { UserPublic } from "@/lib/types/me";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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

const Schema = z
  .object({
    full_name: z.string().min(3, "Ad Soyad en az 3 karakter"),
    email: z.string().min(1, "E-posta gerekli").email("Geçerli bir e-posta girin"),
    // P1 — cep telefonu zorunlu, SMS ile doğrulanır
    phone: z.string().min(10, "Cep telefonunuzu girin (örn: 0532 123 45 67)"),
    password: z.string().min(10, "Öğretmen şifresi en az 10 karakter olmalı"),
    password_confirm: z.string().min(1, "Şifre tekrarı gerekli"),
    accept_terms: z.boolean().refine((v) => v, "Kullanım şartlarını kabul etmelisiniz"),
  })
  .refine((v) => v.password === v.password_confirm, {
    path: ["password_confirm"],
    message: "Şifreler birbiriyle eşleşmiyor",
  });
type Values = z.infer<typeof Schema>;

interface SignupOk {
  user: UserPublic;
  email_verification_sent: boolean;
}

interface Props {
  turnstileEnabled: boolean;
  turnstileSiteKey: string | null;
  /**
   * /pricing'den "14 gün ücretsiz dene" ile gelen pakete kodu
   * (solo_pro/solo_elite/solo_unlimited). Backend bu plan'ı `post_trial_plan`
   * olarak kaydeder — trial bitince koç bu pakete geçmek için ödeme yapar.
   */
  intendedPlan?: string;
}

export function SignupTeacherForm({ turnstileEnabled, turnstileSiteKey, intendedPlan }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const [isSubmitting, setSubmitting] = React.useState(false);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const hasRenderedRef = React.useRef(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;

  const form = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: { full_name: "", email: "", phone: "", password: "", password_confirm: "", accept_terms: false },
  });

  // #5 SMS telefon kapısı — yalnız sunucuda açıksa zorunlu (şu an dormant=false).
  // Açıkken: kayıt öncesi telefon SMS OTP ile doğrulanır, phone_token gönderilir.
  const [phoneRequired, setPhoneRequired] = React.useState<boolean | null>(null);
  const [otpSent, setOtpSent] = React.useState(false);
  const [otpCode, setOtpCode] = React.useState("");
  const [devCode, setDevCode] = React.useState<string | null>(null);
  const [phoneToken, setPhoneToken] = React.useState("");
  const [phoneVerified, setPhoneVerified] = React.useState(false);
  const [phoneBusy, setPhoneBusy] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    api<{ required: boolean }>("/api/v2/auth/signup/phone/required")
      .then((r) => { if (alive) setPhoneRequired(!!r.required); })
      .catch(() => { if (alive) setPhoneRequired(false); });
    return () => { alive = false; };
  }, []);

  const onSendCode = React.useCallback(async () => {
    const phone = form.getValues("phone")?.trim() ?? "";
    if (phone.length < 10) {
      form.setError("phone", { message: "Önce cep telefonunuzu girin." });
      return;
    }
    setPhoneBusy(true);
    try {
      const r = await api<{ sent: boolean; dev_code: string | null }>(
        "/api/v2/auth/signup/phone/start",
        { method: "POST", body: JSON.stringify({ phone }) },
      );
      setOtpSent(true);
      setDevCode(r.dev_code ?? null);
      form.clearErrors("phone");
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail?.message : "Kod gönderilemedi.";
      form.setError("phone", { message: msg ?? "Kod gönderilemedi." });
    } finally {
      setPhoneBusy(false);
    }
  }, [form]);

  const onVerifyCode = React.useCallback(async () => {
    const phone = form.getValues("phone")?.trim() ?? "";
    if (otpCode.trim().length !== 6) {
      form.setError("phone", { message: "6 haneli SMS kodunu girin." });
      return;
    }
    setPhoneBusy(true);
    try {
      const r = await api<{ phone_token: string }>(
        "/api/v2/auth/signup/phone/verify",
        { method: "POST", body: JSON.stringify({ phone, code: otpCode.trim() }) },
      );
      setPhoneToken(r.phone_token);
      setPhoneVerified(true);
      form.clearErrors("phone");
    } catch (e) {
      const msg = e instanceof ApiError ? e.detail?.message : "Doğrulama başarısız.";
      form.setError("phone", { message: msg ?? "Doğrulama başarısız." });
    } finally {
      setPhoneBusy(false);
    }
  }, [form, otpCode]);

  const renderWidget = React.useCallback(() => {
    if (!showCaptcha || !widgetRef.current || !window.turnstile) return;
    if (hasRenderedRef.current) return;
    window.turnstile.render(widgetRef.current, { sitekey: turnstileSiteKey, theme: "auto" });
    hasRenderedRef.current = true;
  }, [showCaptcha, turnstileSiteKey]);

  const onSubmit = React.useCallback(async (values: Values) => {
    if (phoneRequired && !phoneVerified) {
      form.setError("phone", { message: "Devam etmek için cep telefonunuzu SMS ile doğrulayın." });
      return;
    }
    setSubmitting(true);
    try {
      let turnstileToken = "";
      if (showCaptcha) {
        turnstileToken = window.turnstile?.getResponse() ?? "";
        if (!turnstileToken) {
          form.setError("email", { message: "Lütfen güvenlik doğrulamasını tamamlayın." });
          setSubmitting(false);
          return;
        }
      }
      const res = await api<SignupOk>("/api/v2/auth/signup/teacher", {
        method: "POST",
        body: JSON.stringify({
          ...values,
          turnstile_token: turnstileToken,
          intended_plan: intendedPlan || undefined,
          phone_token: phoneRequired ? phoneToken : undefined,
        }),
      });
      qc.clear();
      toast.success(`Hoş geldin, ${res.user.full_name}`, {
        description: res.email_verification_sent
          ? "E-postana doğrulama bağlantısı gönderdik."
          : undefined,
      });
      router.refresh();
      router.push("/teacher/dashboard");
    } catch (e) {
      if (showCaptcha && window.turnstile) window.turnstile.reset();
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        if (e.status === 409 && code === "email_taken") {
          form.setError("email", { message: "Bu e-posta zaten kayıtlı. Giriş yapmayı deneyin." });
        } else if (code === "captcha_failed") {
          form.setError("email", { message: "Güvenlik doğrulaması başarısız, tekrar deneyin." });
        } else if (code === "invalid_phone") {
          form.setError("phone", {
            message: "Geçersiz telefon. Türkiye cep formatı: 0532… veya +90 532…",
          });
        } else if (code === "phone_verification_required") {
          form.setError("phone", {
            message: "Devam etmek için cep telefonunuzu SMS ile doğrulayın.",
          });
        } else if (code === "phone_in_use") {
          form.setError("phone", {
            message: "Bu telefon numarası zaten bir hesapla ilişkili. Giriş yapmayı deneyin.",
          });
        } else if (code === "signup_invalid") {
          toast.error("Kayıt bilgileri geçersiz", { description: e.detail?.message });
        } else if (e.status === 429) {
          toast.error("Çok fazla deneme", { description: "Lütfen kısa süre sonra tekrar deneyin." });
        } else {
          toast.error("Kayıt başarısız", { description: e.detail?.message });
        }
      } else {
        toast.error("Beklenmedik hata", {
          description: e instanceof Error ? e.message : "Sunucuya ulaşılamadı.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }, [showCaptcha, form, qc, router, intendedPlan, phoneRequired, phoneVerified, phoneToken]);

  return (
    <>
      {showCaptcha ? (
        <Script
          src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
          strategy="afterInteractive"
          onLoad={renderWidget}
        />
      ) : null}
      <form method="post" onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
        <div className="space-y-2">
          <Label htmlFor="full_name">Ad Soyad</Label>
          <Input id="full_name" autoComplete="name" autoFocus disabled={isSubmitting}
                 {...form.register("full_name")} aria-invalid={!!form.formState.errors.full_name} />
          {form.formState.errors.full_name ? (
            <p className="text-sm text-destructive">{form.formState.errors.full_name.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">E-posta</Label>
          <Input id="email" type="email" autoComplete="username" disabled={isSubmitting}
                 {...form.register("email")} aria-invalid={!!form.formState.errors.email} />
          {form.formState.errors.email ? (
            <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="phone">Cep telefonu</Label>
          <div className="flex gap-2">
            <Input id="phone" type="tel" autoComplete="tel" placeholder="0532 123 45 67"
                   disabled={isSubmitting || phoneVerified}
                   className="flex-1"
                   {...form.register("phone")} aria-invalid={!!form.formState.errors.phone} />
            {phoneRequired && !phoneVerified && !otpSent ? (
              <Button type="button" variant="secondary" disabled={phoneBusy} onClick={onSendCode}>
                {phoneBusy ? <Loader2 className="animate-spin" /> : "Kod gönder"}
              </Button>
            ) : null}
            {phoneRequired && phoneVerified ? (
              <span className="flex items-center gap-1 px-2 text-sm font-medium text-emerald-600">
                <ShieldCheck className="size-4" /> Doğrulandı
              </span>
            ) : null}
          </div>

          {phoneRequired && otpSent && !phoneVerified ? (
            <div className="flex gap-2">
              <Input
                inputMode="numeric"
                maxLength={6}
                placeholder="6 haneli SMS kodu"
                value={otpCode}
                disabled={isSubmitting || phoneBusy}
                onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                className="flex-1"
              />
              <Button type="button" disabled={phoneBusy} onClick={onVerifyCode}>
                {phoneBusy ? <Loader2 className="animate-spin" /> : "Doğrula"}
              </Button>
            </div>
          ) : null}

          {phoneRequired && otpSent && !phoneVerified ? (
            <button type="button" onClick={onSendCode} disabled={phoneBusy}
                    className="text-xs font-medium text-primary hover:underline">
              Kodu tekrar gönder
            </button>
          ) : null}
          {devCode ? <p className="text-xs text-muted-foreground">Test kodu: {devCode}</p> : null}

          {form.formState.errors.phone ? (
            <p className="text-sm text-destructive">{form.formState.errors.phone.message}</p>
          ) : (
            <p className="text-xs text-muted-foreground">
              {phoneRequired
                ? "Devam etmeden önce telefonunuza SMS ile gönderilen 6 haneli kodla doğrulayın."
                : "Bildirimler ve şifre sıfırlama için kullanılır."}
            </p>
          )}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Şifre</Label>
          <Input id="password" type="password" autoComplete="new-password" disabled={isSubmitting}
                 {...form.register("password")} aria-invalid={!!form.formState.errors.password} />
          {form.formState.errors.password ? (
            <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="password_confirm">Şifre (tekrar)</Label>
          <Input id="password_confirm" type="password" autoComplete="new-password" disabled={isSubmitting}
                 {...form.register("password_confirm")} aria-invalid={!!form.formState.errors.password_confirm} />
          {form.formState.errors.password_confirm ? (
            <p className="text-sm text-destructive">{form.formState.errors.password_confirm.message}</p>
          ) : null}
        </div>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5" disabled={isSubmitting} {...form.register("accept_terms")} />
          <span>Kullanım şartlarını ve KVKK aydınlatma metnini okudum, kabul ediyorum.</span>
        </label>
        {form.formState.errors.accept_terms ? (
          <p className="text-sm text-destructive">{form.formState.errors.accept_terms.message}</p>
        ) : null}

        {showCaptcha ? <div ref={widgetRef} className="min-h-[65px]" /> : null}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? <Loader2 className="animate-spin" /> : null}
          {isSubmitting ? "Hesap oluşturuluyor…" : "Hesap oluştur"}
        </Button>
      </form>
    </>
  );
}
