"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { HeartHandshake, Loader2, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAcceptParentInvitation } from "@/lib/hooks/use-parent-mutations";
import type { ParentInvitationInfo } from "@/lib/types/parent";

interface Props {
  invitation: ParentInvitationInfo;
}

/**
 * Davet kabul form — Jinja `invitation_accept.html` feature parity.
 *
 * Veri yapısı backend ile birebir: full_name, password, password_confirm,
 * kvkk_accept. Hata kodları: name_required / password_too_short /
 * password_mismatch / kvkk_not_accepted / email_in_use_other_role.
 */
export function ParentInvitationClient({ invitation }: Props) {
  const router = useRouter();
  const mut = useAcceptParentInvitation(invitation.token);
  const [fullName, setFullName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [passwordConfirm, setPasswordConfirm] = React.useState("");
  const [kvkkAccept, setKvkkAccept] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);

    // Client-side validasyon — server zaten doğrular ama UX için
    if (fullName.trim().length < 3) {
      setLocalError("Ad-soyad en az 3 karakter olmalıdır.");
      return;
    }
    if (password.length < 8) {
      setLocalError("Şifre en az 8 karakter olmalıdır.");
      return;
    }
    if (password !== passwordConfirm) {
      setLocalError("Şifreler eşleşmiyor.");
      return;
    }
    if (!kvkkAccept) {
      setLocalError(
        "Hesap oluşturmak için aydınlatma metnini onaylamanız gereklidir.",
      );
      return;
    }

    mut.mutate(
      {
        full_name: fullName.trim(),
        password,
        password_confirm: passwordConfirm,
        kvkk_accept: kvkkAccept,
      },
      {
        onSuccess: (data) => {
          router.push(data.redirect_url || "/parent");
          router.refresh();
        },
        onError: (e) => {
          if (e instanceof ApiError) {
            setLocalError(e.detail?.message ?? "Hesap oluşturulamadı.");
          } else {
            setLocalError("Beklenmeyen bir hata oluştu.");
          }
        },
      },
    );
  }

  return (
    <div className="min-h-screen bg-muted/20 flex items-center justify-center p-4 py-8">
      <div className="w-full max-w-lg">
        <div className="flex flex-col items-center mb-5">
          <div className="rounded-full bg-[#117A86]/10 text-[#117A86] p-3 mb-2">
            <HeartHandshake className="size-8" aria-hidden />
          </div>
          <p className="font-display text-xl font-bold tracking-tight">
            ETÜTKOÇ
          </p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-1">
            Veli Daveti
          </p>
        </div>

        <Card className="border-border shadow-sm">
          <CardContent className="p-7 space-y-5">
            <div>
              <h1 className="text-lg font-semibold mb-1">Hoş geldiniz</h1>
              <p className="text-sm text-muted-foreground leading-relaxed">
                <strong className="text-foreground">
                  {invitation.invited_by_full_name}
                </strong>
                , velisi olduğunuz{" "}
                <strong className="text-foreground">
                  {invitation.student_full_name}
                </strong>{" "}
                adlı öğrencinin sınav hazırlık sürecini birlikte takip edebilmek
                için sizi davet etti. Hesabınızı oluşturmak için aşağıdaki
                bilgileri doldurun.
              </p>
            </div>

            <div className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground space-y-0.5">
              <div>
                <strong className="text-foreground">Davet edilen:</strong>{" "}
                <span className="font-mono">{invitation.invited_email}</span>
              </div>
              <div>
                <strong className="text-foreground">İlişki:</strong>{" "}
                {invitation.relation_label}
                {invitation.is_primary && (
                  <span className="ml-1 inline-block bg-[#117A86]/10 text-[#117A86] px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold">
                    Birincil veli
                  </span>
                )}
              </div>
            </div>

            {localError && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800">
                {localError}
              </div>
            )}

            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <Label htmlFor="full_name">Ad-Soyad</Label>
                <Input
                  id="full_name"
                  type="text"
                  required
                  minLength={3}
                  maxLength={120}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="password">Şifre</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  className="mt-1"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  En az 8 karakter.
                </p>
              </div>

              <div>
                <Label htmlFor="password_confirm">Şifre (tekrar)</Label>
                <Input
                  id="password_confirm"
                  type="password"
                  required
                  minLength={8}
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  autoComplete="new-password"
                  className="mt-1"
                />
              </div>

              <label className="flex items-start gap-2 text-xs text-muted-foreground cursor-pointer pt-1">
                <input
                  type="checkbox"
                  required
                  checked={kvkkAccept}
                  onChange={(e) => setKvkkAccept(e.target.checked)}
                  className="mt-0.5 accent-[#117A86]"
                />
                <span>
                  <Link
                    href="/legal/kvkk-veli"
                    target="_blank"
                    className="text-[#117A86] hover:underline inline-flex items-center gap-0.5"
                  >
                    <ShieldCheck className="size-3" aria-hidden />
                    Veli Aydınlatma Metni
                  </Link>
                  &apos;ni okudum, anladım ve kişisel verilerimin belirtilen
                  amaçlarla işlenmesini kabul ediyorum.
                </span>
              </label>

              <Button
                type="submit"
                className="w-full bg-[#117A86] hover:bg-[#0E5F69] text-white"
                disabled={mut.isPending}
              >
                {mut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Hesap oluşturuluyor…
                  </>
                ) : (
                  "Hesabımı Oluştur"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-[11px] text-muted-foreground mt-6">
          © ETÜTKOÇ Rotam · Veli paneli
        </p>
      </div>
    </div>
  );
}
