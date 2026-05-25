"use client";

import * as React from "react";
import Script from "next/script";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { LoginResponse } from "@/lib/types/me";
import { roleHome, safeReturnUrl } from "@/lib/role-home";
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

const LoginSchema = z.object({
  email: z.string().min(1, "E-posta gerekli").email("Geçerli bir e-posta girin"),
  password: z.string().min(1, "Şifre gerekli"),
});
type LoginValues = z.infer<typeof LoginSchema>;

interface LockedDetails {
  retry_after_seconds?: number;
}

interface Props {
  turnstileEnabled: boolean;
  turnstileSiteKey: string | null;
}

export function LoginForm({ turnstileEnabled, turnstileSiteKey }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const returnUrlParam = searchParams.get("returnUrl");
  const qc = useQueryClient();

  const form = useForm<LoginValues>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: "", password: "" },
  });

  const [isSubmitting, setSubmitting] = React.useState(false);
  const [challenge, setChallenge] = React.useState<string | null>(null);
  const widgetRef = React.useRef<HTMLDivElement | null>(null);
  const hasRenderedRef = React.useRef(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;

  const handleSuccess = React.useCallback((res: LoginResponse) => {
    if (res.must_change_password) {
      toast.warning("Şifrenizi değiştirmeniz gerekiyor.", {
        description: "Devam etmeden önce hesap güvenliği için şifrenizi yenileyin.",
      });
      qc.clear();
      router.refresh();
      router.push("/password/change");
      return;
    }
    qc.clear();
    const role = res.user?.role ?? "student";
    // returnUrl yalnız kullanıcının kendi panel alanına aitse onurlandırılır;
    // aksi halde rolün kendi paneline (rol-uyuşmazlığı + open-redirect koruması)
    const target = safeReturnUrl(returnUrlParam, role) ?? roleHome(role);
    if (res.user) toast.success(`Hoş geldin, ${res.user.full_name}`);
    router.refresh();
    router.push(target);
  }, [qc, router, returnUrlParam]);

  const renderWidget = React.useCallback(() => {
    if (!showCaptcha || !widgetRef.current || !window.turnstile) return;
    if (hasRenderedRef.current) return;
    window.turnstile.render(widgetRef.current, {
      sitekey: turnstileSiteKey,
      theme: "auto",
    });
    hasRenderedRef.current = true;
  }, [showCaptcha, turnstileSiteKey]);

  const onSubmit = React.useCallback(async (values: LoginValues) => {
    setSubmitting(true);
    try {
      let turnstileToken = "";
      if (showCaptcha) {
        turnstileToken = window.turnstile?.getResponse() ?? "";
        if (!turnstileToken) {
          form.setError("password", { message: "Lütfen güvenlik doğrulamasını tamamlayın." });
          setSubmitting(false);
          return;
        }
      }

      const res = await api<LoginResponse>("/api/v2/auth/login", {
        method: "POST",
        body: JSON.stringify({ ...values, turnstile_token: turnstileToken }),
      });

      if (res.two_factor_required && res.challenge) {
        setChallenge(res.challenge);
        return;
      }

      handleSuccess(res);
    } catch (e) {
      // Her hatadan sonra CAPTCHA token tek-kullanımlık → sıfırla
      if (showCaptcha && window.turnstile) {
        window.turnstile.reset();
      }
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        if (e.status === 423 && code === "locked") {
          const seconds = (e.detail.details as LockedDetails | undefined)?.retry_after_seconds;
          form.setError("password", {
            message: `Hesap geçici olarak kilitli${seconds ? ` (${seconds} saniye)` : ""}.`,
          });
          toast.error("Hesap kilitli", { description: e.detail?.message ?? undefined });
        } else if (e.status === 429 && code === "ip_blocked") {
          form.setError("email", { message: "Bu ağ geçici olarak engellendi." });
          toast.error("Erişim engellendi", { description: e.detail?.message });
        } else if (e.status === 429) {
          form.setError("email", { message: "Çok fazla deneme. Lütfen 1 dakika bekleyin." });
          toast.error("Hız sınırı aşıldı", {
            description: "Birden çok hatalı giriş — sunucu kısa süreliğine engelliyor.",
          });
        } else if (e.status === 401 && code === "captcha_failed") {
          form.setError("password", { message: "Güvenlik doğrulaması başarısız, tekrar deneyin." });
          toast.error("Doğrulama başarısız", { description: e.detail?.message });
        } else if (e.status === 401 && code === "invalid_credentials") {
          form.setError("password", { message: "E-posta veya şifre hatalı." });
        } else {
          toast.error("Giriş başarısız", { description: e.detail?.message });
        }
      } else {
        toast.error("Beklenmedik hata", {
          description: e instanceof Error ? e.message : "Sunucuya ulaşılamadı.",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }, [showCaptcha, form, handleSuccess]);

  if (challenge) {
    return <TwoFactorStep challenge={challenge} onSuccess={handleSuccess} onCancel={() => setChallenge(null)} />;
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
      <form
        method="post"
        action="/login"
        onSubmit={form.handleSubmit(onSubmit)}
        className="space-y-4"
        noValidate
      >
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

        <div className="space-y-2">
          <Label htmlFor="password">Şifre</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            disabled={isSubmitting}
            {...form.register("password")}
            aria-invalid={!!form.formState.errors.password}
          />
          {form.formState.errors.password ? (
            <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>

        {showCaptcha ? <div ref={widgetRef} className="min-h-[65px]" /> : null}

        <Button type="submit" disabled={isSubmitting} className="w-full">
          {isSubmitting ? <Loader2 className="animate-spin" /> : null}
          {isSubmitting ? "Giriş yapılıyor…" : "Giriş yap"}
        </Button>
      </form>
    </>
  );
}

function TwoFactorStep({
  challenge,
  onSuccess,
  onCancel,
}: {
  challenge: string;
  onSuccess: (res: LoginResponse) => void;
  onCancel: () => void;
}) {
  const [code, setCode] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [isSubmitting, setSubmitting] = React.useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await api<LoginResponse>("/api/v2/auth/2fa/verify", {
        method: "POST",
        body: JSON.stringify({ challenge, code: code.trim() }),
      });
      onSuccess(res);
    } catch (err) {
      if (err instanceof ApiError) {
        const c = err.detail?.code;
        if (c === "invalid_2fa_code") setError("Doğrulama kodu hatalı. Tekrar deneyin.");
        else if (c === "challenge_invalid") {
          setError("Oturum süresi doldu. Baştan giriş yapın.");
          toast.error("Doğrulama süresi doldu");
          onCancel();
        } else if (err.status === 423) {
          setError("Çok fazla başarısız deneme — hesap kilitlendi.");
        } else {
          setError(err.detail?.message ?? "Doğrulama başarısız.");
        }
      } else {
        setError("Sunucuya ulaşılamadı.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form method="post" action="/login" onSubmit={submit} className="space-y-4" noValidate>
      <p className="text-sm text-muted-foreground">
        Hesabınız iki faktörlü doğrulama ile korunuyor. Authenticator uygulamanızdaki
        6 haneli kodu (veya bir yedek kodu) girin.
      </p>
      <div className="space-y-2">
        <Label htmlFor="totp_code">Doğrulama kodu</Label>
        <Input
          id="totp_code"
          inputMode="numeric"
          autoComplete="one-time-code"
          autoFocus
          placeholder="123456"
          disabled={isSubmitting}
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
      <Button type="submit" disabled={isSubmitting || !code.trim()} className="w-full">
        {isSubmitting ? <Loader2 className="animate-spin" /> : null}
        {isSubmitting ? "Doğrulanıyor…" : "Doğrula ve gir"}
      </Button>
      <button type="button" onClick={onCancel} className="w-full text-center text-sm text-muted-foreground underline hover:text-foreground">
        Vazgeç
      </button>
    </form>
  );
}
