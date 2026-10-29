"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Eye, EyeOff, Loader2, Lock, Mail, TriangleAlert } from "lucide-react";


import { api, ApiError } from "@/lib/api";
import type { LoginResponse } from "@/lib/types/me";
import { roleHome, safeReturnUrl } from "@/lib/role-home";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { TurnstileWidget, type TurnstileStatus } from "@/components/turnstile-widget";

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
  const searchParams = useSearchParams();
  const returnUrlParam = searchParams.get("returnUrl");

  const form = useForm<LoginValues>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: "", password: "" },
  });

  const [isSubmitting, setSubmitting] = React.useState(false);
  const [challenge, setChallenge] = React.useState<string | null>(null);
  const [showPassword, setShowPassword] = React.useState(false);
  const [capsLock, setCapsLock] = React.useState(false);
  const showCaptcha = turnstileEnabled && !!turnstileSiteKey;
  const [captchaReset, setCaptchaReset] = React.useState(0);
  const [captchaToken, setCaptchaToken] = React.useState<string | null>(null);
  const [captchaStatus, setCaptchaStatus] = React.useState<TurnstileStatus>("loading");
  // Kullanıcı doğrulama bitmeden "Giriş yap"a basarsa isteği beklet, token
  // gelince kendiliğinden gönder (butonu kilitleyip "neden basamıyorum?" dedirtme).
  const [pendingValues, setPendingValues] = React.useState<LoginValues | null>(null);

  const handleSuccess = React.useCallback((res: LoginResponse) => {
    // TAM SAYFA geçiş — router.refresh()+router.push ikilisi App Router'da
    // yarışıp navigasyonu iptal edebiliyor (2026-08-12 saha bug'ı).
    if (res.must_change_password) {
      toast.warning("Şifrenizi değiştirmeniz gerekiyor.", {
        description: "Devam etmeden önce hesap güvenliği için şifrenizi yenileyin.",
      });
      window.location.assign("/password/change");
      return;
    }
    const role = res.user?.role ?? "student";
    // returnUrl yalnız kullanıcının kendi panel alanına aitse onurlandırılır
    const target = safeReturnUrl(returnUrlParam, role) ?? roleHome(role);
    if (res.user) toast.success(`Hoş geldin, ${res.user.full_name}`);
    window.location.assign(target);
  }, [returnUrlParam]);

  const submitWithToken = React.useCallback(async (values: LoginValues, token: string) => {
    setPendingValues(null);
    setSubmitting(true);
    let redirecting = false;
    try {
      const res = await api<LoginResponse>("/api/v2/auth/login", {
        method: "POST",
        body: JSON.stringify({ ...values, turnstile_token: token }),
      });
      if (res.two_factor_required && res.challenge) {
        setChallenge(res.challenge);
        return;
      }
      redirecting = true; // handleSuccess daima tam-sayfa geçiş başlatır
      handleSuccess(res);
    } catch (e) {
      redirecting = false;
      // Her denemeden sonra token tek kullanımlık → yeni token iste
      if (showCaptcha) {
        setCaptchaToken(null);
        setCaptchaReset((n) => n + 1);
      }
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        if (e.status === 423 && code === "locked") {
          const seconds = (e.detail.details as LockedDetails | undefined)?.retry_after_seconds;
          form.setError("password", {
            message: `Hesap geçici olarak kilitli${seconds ? ` (${Math.ceil(seconds / 60)} dakika)` : ""}.`,
          });
          toast.error("Hesap kilitli", { description: e.detail?.message ?? undefined });
        } else if (e.status === 429 && code === "ip_blocked") {
          form.setError("email", { message: "Bu ağ geçici olarak engellendi." });
          toast.error("Erişim engellendi", { description: e.detail?.message });
        } else if (e.status === 429) {
          form.setError("email", { message: "Çok fazla deneme. Lütfen 1 dakika bekleyin." });
        } else if (e.status === 401 && code === "captcha_failed") {
          form.setError("root", { message: "Güvenlik kontrolü geçilemedi, yenilendi. Tekrar dene." });
        } else if (e.status === 401 && code === "invalid_credentials") {
          form.setError("password", { message: "E-posta veya şifre hatalı." });
        } else {
          toast.error("Giriş başarısız", { description: e.detail?.message });
        }
      } else {
        toast.error("Sunucuya ulaşılamadı", {
          description: "İnternet bağlantını kontrol edip tekrar dene.",
        });
      }
    } finally {
      if (!redirecting) setSubmitting(false);
    }
  }, [showCaptcha, form, handleSuccess]);

  const onSubmit = React.useCallback((values: LoginValues) => {
    if (!showCaptcha) {
      void submitWithToken(values, "");
      return;
    }
    if (captchaToken) {
      void submitWithToken(values, captchaToken);
      return;
    }
    if (captchaStatus === "error") {
      form.setError("root", { message: "Güvenlik kontrolü yüklenemedi — aşağıdan yeniden dene." });
      return;
    }
    setPendingValues(values); // token gelince gönderilir
    setSubmitting(true);
  }, [showCaptcha, captchaToken, captchaStatus, submitWithToken, form]);

  const onCaptchaToken = React.useCallback((token: string | null) => {
    setCaptchaToken(token);
    if (token && pendingValues) void submitWithToken(pendingValues, token);
  }, [submitWithToken, pendingValues]);

  const onCaptchaStatus = React.useCallback((s: TurnstileStatus) => {
    setCaptchaStatus(s);
    if (s === "error" && pendingValues) {
      setPendingValues(null);
      setSubmitting(false);
    }
  }, [pendingValues]);

  const onKeyState = (e: React.KeyboardEvent<HTMLInputElement>) => {
    setCapsLock(e.getModifierState?.("CapsLock") ?? false);
  };

  if (challenge) {
    return <TwoFactorStep challenge={challenge} onSuccess={handleSuccess} onCancel={() => setChallenge(null)} />;
  }

  const errors = form.formState.errors;
  const inputCls =
    "h-12 rounded-xl border-slate-300 bg-slate-50 pl-11 text-base text-slate-900 placeholder:text-slate-400 " +
    "transition focus-visible:border-cyan-600 focus-visible:bg-white focus-visible:ring-cyan-600/30 focus-visible:ring-offset-0 " +
    "aria-[invalid=true]:border-rose-400";

  return (
    <form
      method="post"
      action="/login"
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-5"
      noValidate
    >
      <div className="space-y-2">
        <Label htmlFor="email" className="text-sm font-medium text-slate-700">E-posta</Label>
        <div className="relative">
          <Mail className="pointer-events-none absolute left-4 top-1/2 size-4.5 -translate-y-1/2 text-slate-400" aria-hidden />
          <Input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            autoFocus
            placeholder="ornek@eposta.com"
            disabled={isSubmitting}
            className={inputCls}
            {...form.register("email")}
            aria-invalid={!!errors.email}
          />
        </div>
        {errors.email ? <p className="text-sm text-rose-600">{errors.email.message}</p> : null}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="password" className="text-sm font-medium text-slate-700">Şifre</Label>
          <Link href="/password/forgot" className="text-sm font-medium text-cyan-800 hover:underline">
            Şifremi unuttum
          </Link>
        </div>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-4 top-1/2 size-4.5 -translate-y-1/2 text-slate-400" aria-hidden />
          <Input
            id="password"
            type={showPassword ? "text" : "password"}
            autoComplete="current-password"
            placeholder="••••••••"
            disabled={isSubmitting}
            className={`${inputCls} pr-12`}
            onKeyDown={onKeyState}
            onKeyUp={onKeyState}
            {...form.register("password")}
            aria-invalid={!!errors.password}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-2 top-1/2 inline-flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-200 hover:text-slate-800 dark:hover:bg-slate-500/25"
            aria-label={showPassword ? "Şifreyi gizle" : "Şifreyi göster"}
            aria-pressed={showPassword}
          >
            {showPassword ? <EyeOff className="size-4.5" /> : <Eye className="size-4.5" />}
          </button>
        </div>
        {capsLock ? (
          <p className="flex items-center gap-1.5 text-xs font-medium text-amber-700">
            <TriangleAlert className="size-3.5" aria-hidden />
            Büyük harf kilidi (Caps Lock) açık.
          </p>
        ) : null}
        {errors.password ? <p className="text-sm text-rose-600">{errors.password.message}</p> : null}
      </div>

      {showCaptcha && turnstileSiteKey ? (
        <TurnstileWidget
          resetKey={captchaReset}
          siteKey={turnstileSiteKey}
          action="login"
          onToken={onCaptchaToken}
          onStatus={onCaptchaStatus}
        />
      ) : null}

      {errors.root ? (
        <p className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700">{errors.root.message}</p>
      ) : null}

      <Button
        type="submit"
        disabled={isSubmitting}
        className="h-12 w-full rounded-xl bg-cyan-700 text-base font-semibold text-white shadow-sm hover:bg-cyan-800"
      >
        {isSubmitting ? <Loader2 className="animate-spin" /> : null}
        {pendingValues ? "Güvenlik kontrolü bekleniyor…" : isSubmitting ? "Giriş yapılıyor…" : "Giriş yap"}
      </Button>
    </form>
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
    let redirecting = false;
    try {
      const res = await api<LoginResponse>("/api/v2/auth/2fa/verify", {
        method: "POST",
        body: JSON.stringify({ challenge, code: code.trim() }),
      });
      redirecting = true;
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
      if (!redirecting) setSubmitting(false);
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
