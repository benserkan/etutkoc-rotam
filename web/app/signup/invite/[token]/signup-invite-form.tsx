"use client";

import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import Link from "next/link";
import { ArrowRight, Eye, EyeOff, Loader2, Lock } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "@/lib/api";
import type { UserPublic, UserRole } from "@/lib/types/me";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function defaultLandingFor(role: string): string {
  if (role === "super_admin") return "/admin";
  if (role === "institution_admin") return "/institution";
  if (role === "teacher") return "/teacher/dashboard";
  if (role === "parent") return "/parent";
  return "/student";
}

/** Sunucudaki rol bazlı şifre politikasıyla aynı (auth_security). */
function passwordRule(role: string): string {
  const min = role === "institution_admin" ? 12 : role === "teacher" ? 10 : 8;
  const special = role === "institution_admin" || role === "teacher";
  return `En az ${min} karakter; büyük ve küçük harf, rakam${special ? " ve bir özel karakter (örn. @ # $ %)" : ""} içermeli.`;
}

const Schema = z
  .object({
    full_name: z.string().min(3, "Ad Soyad en az 3 karakter"),
    email: z.string().min(1, "E-posta gerekli").email("Geçerli bir e-posta girin"),
    // P1 — cep telefonu zorunlu, SMS ile doğrulanır
    phone: z.string().min(10, "Cep telefonunuzu girin (örn: 0532 123 45 67)"),
    password: z.string().min(8, "Şifre en az 8 karakter olmalı"),
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
  token: string;
  defaultEmail: string;
  defaultFullName: string;
  role: string;
  /** SMS doğrulaması canlı mı — kapalıyken "SMS ile doğrulanacak" denmez. */
  phoneVerificationAvailable?: boolean;
}

export function SignupInviteForm({
  token,
  defaultEmail,
  defaultFullName,
  role,
  phoneVerificationAvailable = false,
}: Props) {
  const [showPw, setShowPw] = React.useState(false);
  const qc = useQueryClient();
  const [isSubmitting, setSubmitting] = React.useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: {
      full_name: defaultFullName,
      email: defaultEmail,
      phone: "",
      password: "",
      password_confirm: "",
      accept_terms: false,
    },
  });

  async function onSubmit(values: Values) {
    setSubmitting(true);
    try {
      const res = await api<SignupOk>(`/api/v2/auth/signup/invite/${token}`, {
        method: "POST",
        body: JSON.stringify(values),
      });
      qc.clear();
      toast.success(`Hoş geldin, ${res.user.full_name}`, {
        description: res.email_verification_sent ? "E-postana doğrulama bağlantısı gönderdik." : undefined,
      });
      // Tam sayfa geçiş — refresh+push yarışı (login saha bug'ı 2026-08-12)
      window.location.assign(defaultLandingFor((res.user.role as UserRole) ?? role));
    } catch (e) {
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        if (e.status === 410 || code === "invitation_unusable") {
          toast.error("Davetiye geçersiz", { description: e.detail?.message });
        } else if (code === "email_mismatch") {
          form.setError("email", { message: e.detail?.message ?? "Bu davet başka bir adrese özel." });
        } else if (e.status === 409 && code === "email_taken") {
          form.setError("email", { message: "Bu e-posta zaten kayıtlı." });
        } else if (code === "invalid_phone") {
          form.setError("phone", {
            message: "Geçersiz telefon. Türkiye cep formatı: 0532… veya +90 532…",
          });
        } else if (code === "quota_exceeded") {
          toast.error("Kuota dolu", { description: e.detail?.message });
        } else if (code === "signup_invalid") {
          toast.error("Kayıt bilgileri geçersiz", { description: e.detail?.message });
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
  }

  const err = form.formState.errors;
  const inputCls = "h-11 bg-white text-slate-900";

  return (
    <form method="post" onSubmit={form.handleSubmit(onSubmit)} className="space-y-5" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="full_name" className="text-slate-800">Ad Soyad</Label>
        <Input id="full_name" autoComplete="name" autoFocus={!defaultFullName} disabled={isSubmitting}
               className={inputCls}
               {...form.register("full_name")} aria-invalid={!!err.full_name} />
        {err.full_name ? <p className="text-sm text-rose-700">{err.full_name.message}</p> : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email" className="text-slate-800">E-posta</Label>
        {defaultEmail ? (
          <div className="relative">
            <Input id="email" type="email" autoComplete="username" readOnly tabIndex={-1}
                   className="h-11 cursor-not-allowed border-slate-200 bg-slate-50 pr-10 text-slate-700"
                   {...form.register("email")} aria-invalid={!!err.email} aria-describedby="email-lock" />
            <Lock className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        ) : (
          <Input id="email" type="email" autoComplete="username" disabled={isSubmitting} className={inputCls}
                 {...form.register("email")} aria-invalid={!!err.email} />
        )}
        {defaultEmail ? (
          <p id="email-lock" className="text-xs text-slate-500">
            Davet bu adrese gönderildi; hesabınız bu adresle açılır.
          </p>
        ) : null}
        {err.email ? <p className="text-sm text-rose-700">{err.email.message}</p> : null}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="phone" className="text-slate-800">Cep telefonu</Label>
        <Input id="phone" type="tel" inputMode="tel" autoComplete="tel" placeholder="0532 123 45 67"
               disabled={isSubmitting} className={inputCls}
               {...form.register("phone")} aria-invalid={!!err.phone} />
        {err.phone ? (
          <p className="text-sm text-rose-700">{err.phone.message}</p>
        ) : (
          <p className="text-xs text-slate-500">
            {phoneVerificationAvailable
              ? "Kayıttan sonra SMS ile gönderilecek 6 haneli kodla doğrulayacaksınız."
              : "Kurumunuzun size ulaşabilmesi için."}
          </p>
        )}
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="password" className="text-slate-800">Şifre</Label>
          <div className="relative">
            <Input id="password" type={showPw ? "text" : "password"} autoComplete="new-password"
                   disabled={isSubmitting} className={`${inputCls} pr-10`}
                   {...form.register("password")} aria-invalid={!!err.password} />
            <button type="button" onClick={() => setShowPw((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-slate-500 hover:text-slate-800"
                    aria-label={showPw ? "Şifreyi gizle" : "Şifreyi göster"}>
              {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {err.password ? <p className="text-sm text-rose-700">{err.password.message}</p> : null}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="password_confirm" className="text-slate-800">Şifre (tekrar)</Label>
          <Input id="password_confirm" type={showPw ? "text" : "password"} autoComplete="new-password"
                 disabled={isSubmitting} className={inputCls}
                 {...form.register("password_confirm")} aria-invalid={!!err.password_confirm} />
          {err.password_confirm ? <p className="text-sm text-rose-700">{err.password_confirm.message}</p> : null}
        </div>
      </div>
      <p className="-mt-2 text-xs text-slate-500">{passwordRule(role)}</p>

      <label className="flex items-start gap-2.5 rounded-lg bg-slate-50 p-3 text-sm text-slate-700 ring-1 ring-slate-200">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-cyan-700" disabled={isSubmitting}
               {...form.register("accept_terms")} />
        <span>
          <Link href="/kullanim-sartlari" target="_blank" className="font-semibold text-cyan-700 hover:underline">
            Kullanım şartlarını
          </Link>{" "}
          ve{" "}
          <Link href="/kvkk" target="_blank" className="font-semibold text-cyan-700 hover:underline">
            KVKK aydınlatma metnini
          </Link>{" "}
          okudum, kabul ediyorum.
        </span>
      </label>
      {err.accept_terms ? <p className="-mt-3 text-sm text-rose-700">{err.accept_terms.message}</p> : null}

      <Button type="submit" disabled={isSubmitting}
              className="h-12 w-full bg-cyan-700 text-base font-semibold text-white shadow-md shadow-cyan-900/20 hover:bg-cyan-800">
        {isSubmitting ? <Loader2 className="animate-spin" /> : null}
        {isSubmitting ? "Hesap oluşturuluyor…" : "Daveti kabul et ve başla"}
        {isSubmitting ? null : <ArrowRight className="h-4 w-4" />}
      </Button>
    </form>
  );
}
