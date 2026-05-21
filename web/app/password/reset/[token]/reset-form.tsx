"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const Schema = z
  .object({
    new_password: z.string().min(8, "Şifre en az 8 karakter olmalı"),
    confirm_password: z.string().min(1, "Şifre tekrarı gerekli"),
  })
  .refine((v) => v.new_password === v.confirm_password, {
    path: ["confirm_password"],
    message: "Şifreler birbiriyle eşleşmiyor",
  });
type Values = z.infer<typeof Schema>;

interface GenericOk {
  ok: boolean;
  message: string;
}

interface Props {
  token: string;
}

export function ResetPasswordForm({ token }: Props) {
  const router = useRouter();
  const [isSubmitting, setSubmitting] = React.useState(false);
  const [tokenDead, setTokenDead] = React.useState(false);

  const form = useForm<Values>({
    resolver: zodResolver(Schema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  async function onSubmit(values: Values) {
    setSubmitting(true);
    try {
      await api<GenericOk>("/api/v2/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          token,
          new_password: values.new_password,
          confirm_password: values.confirm_password,
        }),
      });
      toast.success("Şifreniz güncellendi.", { description: "Yeni şifrenizle giriş yapabilirsiniz." });
      router.push("/login");
    } catch (e) {
      if (e instanceof ApiError) {
        const code = e.detail?.code;
        const msg = e.detail?.message;
        if (code === "invalid_token") {
          setTokenDead(true);
        } else if (code === "password_mismatch") {
          form.setError("confirm_password", { message: msg ?? "Şifreler eşleşmiyor." });
        } else if (code === "password_weak") {
          form.setError("new_password", { message: msg ?? "Şifre yeterince güçlü değil." });
        } else if (code === "password_same") {
          form.setError("new_password", { message: msg ?? "Yeni şifre eskiyle aynı olamaz." });
        } else if (code === "password_breached") {
          form.setError("new_password", { message: msg ?? "Bu şifre sızdırılmış listelerde — başka seçin." });
        } else {
          toast.error("Şifre sıfırlanamadı", { description: msg });
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

  if (tokenDead) {
    return (
      <div className="space-y-3 text-center">
        <p className="text-sm text-muted-foreground">
          Bu bağlantı geçersiz veya süresi dolmuş. Lütfen yeniden şifre sıfırlama isteyin.
        </p>
        <Button asChild className="w-full">
          <a href="/password/forgot">Yeni bağlantı iste</a>
        </Button>
      </div>
    );
  }

  return (
    <form method="post" onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="new_password">Yeni şifre</Label>
        <Input
          id="new_password"
          type="password"
          autoComplete="new-password"
          autoFocus
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
        {isSubmitting ? "Kaydediliyor…" : "Şifreyi sıfırla"}
      </Button>
    </form>
  );
}
