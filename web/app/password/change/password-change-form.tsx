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
import type { MutationResponse } from "@/lib/api";
import type { PasswordChangeResult, UserPublic, UserRole } from "@/lib/types/me";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function defaultLandingFor(role: UserRole): string {
  if (role === "super_admin") return "/admin";
  if (role === "institution_admin") return "/institution";
  if (role === "teacher") return "/teacher/dashboard";
  if (role === "parent") return "/parent";
  return "/student";
}

const Schema = z
  .object({
    current_password: z.string().optional(),
    new_password: z.string().min(8, "Şifre en az 8 karakter olmalı"),
    confirm_password: z.string().min(1, "Şifre tekrarı gerekli"),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    message: "Şifreler birbiriyle eşleşmiyor",
  });
type Values = z.infer<typeof Schema>;

interface Props {
  isForced: boolean;
}

export function PasswordChangeForm({ isForced }: Props) {
  const router = useRouter();
  const qc = useQueryClient();
  const [isSubmitting, setSubmitting] = React.useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: Values) {
    setSubmitting(true);
    try {
      await api<MutationResponse<PasswordChangeResult>>("/api/v2/me/password-change", {
        method: "POST",
        body: JSON.stringify({
          current_password: isForced ? null : (values.current_password ?? ""),
          new_password: values.new_password,
          confirm_password: values.confirm_password,
        }),
      });

      toast.success("Şifreniz güncellendi.");
      qc.clear();
      // Artık must_change=False → role'e göre panele yönlendir
      let role: UserRole = "student";
      try {
        const me = await api<UserPublic>("/api/v2/auth/me");
        role = me.role;
      } catch {
        // role alınamazsa student fallback
      }
      router.refresh();
      router.push(defaultLandingFor(role));
    } catch (e) {
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        const msg = e.detail?.message;
        if (code === "wrong_current_password") {
          form.setError("current_password", { message: msg ?? "Mevcut şifre yanlış." });
        } else if (code === "password_mismatch") {
          form.setError("confirm_password", { message: msg ?? "Şifreler eşleşmiyor." });
        } else if (code === "password_weak") {
          form.setError("new_password", { message: msg ?? "Şifre yeterince güçlü değil." });
        } else if (code === "password_same") {
          form.setError("new_password", { message: msg ?? "Yeni şifre eskiyle aynı olamaz." });
        } else if (code === "password_breached") {
          form.setError("new_password", { message: msg ?? "Bu şifre sızdırılmış listelerde — başka seçin." });
        } else if (e.status === 423) {
          toast.error("Hesap kilitli", { description: msg });
        } else {
          toast.error("Şifre değiştirilemedi", { description: msg });
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
      {!isForced ? (
        <div className="space-y-2">
          <Label htmlFor="current_password">Mevcut şifre</Label>
          <Input
            id="current_password"
            type="password"
            autoComplete="current-password"
            disabled={isSubmitting}
            {...form.register("current_password")}
            aria-invalid={!!form.formState.errors.current_password}
          />
          {form.formState.errors.current_password ? (
            <p className="text-sm text-destructive">{form.formState.errors.current_password.message}</p>
          ) : null}
        </div>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="new_password">Yeni şifre</Label>
        <Input
          id="new_password"
          type="password"
          autoComplete="new-password"
          autoFocus={isForced}
          disabled={isSubmitting}
          {...form.register("new_password")}
          aria-invalid={!!form.formState.errors.new_password}
        />
        {form.formState.errors.new_password ? (
          <p className="text-sm text-destructive">{form.formState.errors.new_password.message}</p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor="confirm_password">Yeni şifre (tekrar)</Label>
        <Input
          id="confirm_password"
          type="password"
          autoComplete="new-password"
          disabled={isSubmitting}
          {...form.register("confirm_password")}
          aria-invalid={!!form.formState.errors.confirm_password}
        />
        {form.formState.errors.confirm_password ? (
          <p className="text-sm text-destructive">{form.formState.errors.confirm_password.message}</p>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        En az 8 karakter, büyük + küçük harf ve rakam içermeli. Yöneticiler için özel karakter de gerekir.
      </p>

      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting ? <Loader2 className="animate-spin" /> : null}
        {isSubmitting ? "Kaydediliyor…" : "Şifreyi güncelle"}
      </Button>
    </form>
  );
}
