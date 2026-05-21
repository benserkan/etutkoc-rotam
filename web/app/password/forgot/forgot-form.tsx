"use client";

import * as React from "react";
import Script from "next/script";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { CheckCircle2, Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
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

const Schema = z.object({
  email: z.string().min(1, "E-posta gerekli").email("Geçerli bir e-posta girin"),
});
type Values = z.infer<typeof Schema>;

interface GenericOk {
  ok: boolean;
  message: string;
}

interface Props {
  turnstileEnabled: boolean;
  turnstileSiteKey: string | null;
}

export function ForgotPasswordForm({ turnstileEnabled, turnstileSiteKey }: Props) {
  const form = useForm<Values>({ resolver: zodResolver(Schema), defaultValues: { email: "" } });
  const [isSubmitting, setSubmitting] = React.useState(false);
  const [sentMessage, setSentMessage] = React.useState<string | null>(null);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const hasRenderedRef = React.useRef(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;

  const renderWidget = React.useCallback(() => {
    if (!showCaptcha || !widgetRef.current || !window.turnstile) return;
    if (hasRenderedRef.current) return;
    window.turnstile.render(widgetRef.current, { sitekey: turnstileSiteKey, theme: "auto" });
    hasRenderedRef.current = true;
  }, [showCaptcha, turnstileSiteKey]);

  const onSubmit = React.useCallback(async (values: Values) => {
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
      const res = await api<GenericOk>("/api/v2/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: values.email, turnstile_token: turnstileToken }),
      });
      setSentMessage(res.message);
    } catch (e) {
      if (showCaptcha && window.turnstile) window.turnstile.reset();
      if (e instanceof ApiError) {
        if (e.status === 429) {
          toast.error("Çok fazla deneme", { description: "Lütfen kısa bir süre sonra tekrar deneyin." });
        } else if (e.detail?.code === "captcha_failed") {
          form.setError("email", { message: "Güvenlik doğrulaması başarısız, tekrar deneyin." });
        } else {
          toast.error("İstek gönderilemedi", { description: e.detail?.message });
        }
      } else {
        toast.error("Beklenmedik hata", {
          description: e instanceof Error ? e.message : "Sunucuya ulaşılamadı.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }, [showCaptcha, form]);

  if (sentMessage) {
    return (
      <div className="space-y-3 text-center">
        <CheckCircle2 className="mx-auto size-10 text-emerald-600" aria-hidden />
        <p className="text-sm text-muted-foreground">{sentMessage}</p>
      </div>
    );
  }

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
          <Label htmlFor="email">E-posta</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            autoFocus
            disabled={isSubmitting}
            {...form.register("email")}
            aria-invalid={!!form.formState.errors.email}
          />
          {form.formState.errors.email ? (
            <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        {showCaptcha ? <div ref={widgetRef} className="min-h-[65px]" /> : null}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? <Loader2 className="animate-spin" /> : null}
          {isSubmitting ? "Gönderiliyor…" : "Sıfırlama bağlantısı gönder"}
        </Button>
      </form>
    </>
  );
}
