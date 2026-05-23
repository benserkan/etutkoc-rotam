"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
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

const Schema = z
  .object({
    full_name: z.string().min(3, "Ad Soyad en az 3 karakter"),
    email: z.string().min(1, "E-posta gerekli").email("Geçerli bir e-posta girin"),
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
}

export function SignupInviteForm({ token, defaultEmail, defaultFullName, role }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const [isSubmitting, setSubmitting] = React.useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: {
      full_name: defaultFullName,
      email: defaultEmail,
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
      router.refresh();
      router.push(defaultLandingFor((res.user.role as UserRole) ?? role));
    } catch (e) {
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        if (e.status === 410 || code === "invitation_unusable") {
          toast.error("Davetiye geçersiz", { description: e.detail?.message });
        } else if (e.status === 409 && code === "email_taken") {
          form.setError("email", { message: "Bu e-posta zaten kayıtlı." });
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

  return (
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

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? <Loader2 className="animate-spin" /> : null}
        {isSubmitting ? "Hesap oluşturuluyor…" : "Hesabı oluştur"}
      </Button>
    </form>
  );
}
