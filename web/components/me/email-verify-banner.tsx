"use client";

import * as React from "react";
import { toast } from "sonner";
import { MailWarning } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

/**
 * Soft e-posta doğrulama banner'ı (Dalga 7 P3/P5).
 * email_verified=false olan kullanıcıya gösterilir; "Tekrar gönder" ile
 * /auth/resend-verification çağrılır.
 */
export function EmailVerifyBanner({ emailVerified }: { emailVerified: boolean }) {
  const [sent, setSent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  if (emailVerified) return null;

  async function resend() {
    setBusy(true);
    try {
      await api<{ ok: boolean; message: string }>("/api/v2/auth/resend-verification", {
        method: "POST",
      });
      setSent(true);
      toast.success("Doğrulama bağlantısı e-postanıza gönderildi.");
    } catch (e) {
      toast.error("Gönderilemedi", {
        description: e instanceof ApiError ? e.detail?.message : undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <MailWarning className="mt-0.5 size-5 shrink-0 text-amber-600" aria-hidden />
        <div>
          <p className="text-sm font-medium text-amber-900">E-posta adresiniz henüz doğrulanmadı</p>
          <p className="text-xs text-amber-800">
            Hesabınızı güvende tutmak için e-postanıza gönderdiğimiz bağlantıya tıklayın.
          </p>
        </div>
      </div>
      <Button variant="outline" size="sm" disabled={busy || sent} onClick={resend} className="shrink-0">
        {sent ? "Gönderildi" : busy ? "Gönderiliyor…" : "Tekrar gönder"}
      </Button>
    </div>
  );
}
