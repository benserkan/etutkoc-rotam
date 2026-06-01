"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Clock,
  Loader2,
  Phone,
  ShieldCheck,
  Smartphone,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import {
  usePhoneDelete,
  usePhoneSecondaryDelete,
  usePhoneSecondaryStart,
  usePhoneSecondaryVerify,
  usePhoneStart,
  usePhoneVerify,
} from "@/lib/hooks/use-me-mutations";
import type { MyAccountResponse, MyPhoneInfo } from "@/lib/types/me";

interface Props {
  /** "primary" — tüm roller; "secondary" — yalnız PARENT (anne+baba ayrımı). */
  slot: "primary" | "secondary";
  /** Server'dan ön-fetch edilen MyAccountResponse — phone alanı için. */
  initial?: MyAccountResponse;
}

/**
 * /me/account telefon doğrulama kartı.
 *
 * 3 durum (mevcut WhatsAppCard deseni):
 *   1. Kapalı (numara yok / doğrulanmamış) → telefon ekle formu
 *   2. Kod bekleniyor → kod gir + "Yeni kod" (cooldown sonrası) + dev_test_code
 *   3. Doğrulanmış → numara + tarih + "Kaldır" butonu
 *
 * Veri kaynağı: /api/v2/me (TanStack Query). initial server'dan gelir; mutate
 * sonrası invalidate ile tazelenir.
 */
export function PhoneCard({ slot, initial }: Props) {
  const q = useQuery<MyAccountResponse>({
    queryKey: ["me"],
    queryFn: () => api<MyAccountResponse>("/api/v2/me"),
    initialData: initial,
    staleTime: 30_000,
  });

  const data = q.data;

  // Yükleme durumu — initialData yoksa /me henüz gelmemiş olabilir (örn. dialog
  // açılış anında). Skeleton ile boş ekran yerine durum göster.
  if (!data) {
    return (
      <Card className="scroll-mt-20">
        <CardContent className="p-5 text-sm text-muted-foreground inline-flex items-center gap-2">
          <Loader2 className="size-4 animate-spin" aria-hidden />
          Telefon durumu yükleniyor…
        </CardContent>
      </Card>
    );
  }

  // /me yanıtında phone alanı yoksa (legacy istemci) — sessizce gizle
  if (!data.phone) return null;

  // Secondary slot yalnız PARENT için anlamlı — diğerlerinde tamamen gizle
  if (slot === "secondary" && !data.phone.secondary_slot_available) {
    return null;
  }

  // Slot bazlı alan seçimi
  const phone = pickPhoneFields(data.phone, slot);
  // Soft mod: SMS doğrulama operasyonel değilse, doğrulanmamış telefonu zorla
  // doğrulatma — start/verify formu kod gelmediği için dead-end olur. Bunun
  // yerine "yakında" bilgisi göster (numara varsa kayıtlı olarak gösterilir).
  const verificationAvailable = data.phone.verification_available !== false;

  if (phone.verified) {
    return <PhoneVerifiedPanel slot={slot} phone={phone} />;
  }
  if (!verificationAvailable) {
    return <PhoneSoftPanel slot={slot} phone={phone} />;
  }
  if (phone.pending) {
    return <PhonePendingPanel slot={slot} phone={phone} />;
  }
  return <PhoneStartPanel slot={slot} />;
}

// ============================================================================
// Slot bazlı alan seçici (DRY)
// ============================================================================

interface PickedPhone {
  number: string | null;
  verifiedAt: string | null;
  verified: boolean;
  pending: boolean;
  pendingNumber: string | null;
  pendingExpiresAt: string | null;
  devTestCode: string | null;
}

function pickPhoneFields(
  info: MyPhoneInfo,
  slot: "primary" | "secondary",
): PickedPhone {
  if (slot === "secondary") {
    return {
      number: info.phone_secondary,
      verifiedAt: info.phone_secondary_verified_at,
      verified: info.phone_secondary_verified_at != null,
      pending: info.phone_secondary_pending_verify,
      pendingNumber: info.phone_secondary_pending_phone,
      pendingExpiresAt: info.phone_secondary_pending_expires_at,
      devTestCode: info.phone_secondary_dev_test_code,
    };
  }
  return {
    number: info.phone,
    verifiedAt: info.phone_verified_at,
    verified: info.phone_verified_at != null,
    pending: info.phone_pending_verify,
    pendingNumber: info.phone_pending_phone,
    pendingExpiresAt: info.phone_pending_expires_at,
    devTestCode: info.phone_dev_test_code,
  };
}

// ============================================================================
// Genel kart başlığı
// ============================================================================

function PhoneCardShell({
  slot,
  badge,
  children,
}: {
  slot: "primary" | "secondary";
  badge: React.ReactNode;
  children: React.ReactNode;
}) {
  const title =
    slot === "secondary" ? "İkinci Telefon (Veli)" : "Cep Telefonu";
  const description =
    slot === "secondary"
      ? "Anne/baba ayrımı için ikinci numara — WhatsApp bildirimleri de buraya gider."
      : "WhatsApp bildirimleriniz bu numaraya gider. SMS ile doğrulanır.";
  // Anchor: banner'dan "/me/account#cep-telefonu" linkiyle birincil karta scroll
  const anchorId = slot === "secondary" ? "ikinci-telefon" : "cep-telefonu";
  return (
    <Card id={anchorId} className="scroll-mt-20">
      <div className="px-5 py-3 border-b border-border flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold inline-flex items-center gap-1.5">
            {slot === "secondary" ? (
              <Phone className="size-4 text-[#117A86]" aria-hidden />
            ) : (
              <Smartphone className="size-4 text-[#117A86]" aria-hidden />
            )}
            {title}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
        </div>
        {badge}
      </div>
      <CardContent className="p-5">{children}</CardContent>
    </Card>
  );
}

// ============================================================================
// Doğrulanmış durum
// ============================================================================

function PhoneVerifiedPanel({
  slot,
  phone,
}: {
  slot: "primary" | "secondary";
  phone: PickedPhone;
}) {
  const delMutPrimary = usePhoneDelete();
  const delMutSecondary = usePhoneSecondaryDelete();
  const mut = slot === "secondary" ? delMutSecondary : delMutPrimary;

  function doDelete() {
    mut.mutate();
  }

  return (
    <PhoneCardShell
      slot={slot}
      badge={
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
          <CheckCircle2 className="size-3" aria-hidden />
          Doğrulandı
        </span>
      }
    >
      <div className="text-sm mb-2">
        Doğrulanan numara:{" "}
        <code className="bg-muted px-1.5 py-0.5 rounded font-mono">
          +{phone.number}
        </code>
      </div>
      {phone.verifiedAt && (
        <div className="text-xs text-muted-foreground mb-3">
          Doğrulama tarihi: {formatTimestamp(phone.verifiedAt)}
        </div>
      )}
      <Button
        size="sm"
        variant="outline"
        onClick={doDelete}
        disabled={mut.isPending}
        className="text-rose-700 border-rose-200 hover:bg-rose-50"
      >
        {mut.isPending ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : null}
        Telefonu kaldır
      </Button>
    </PhoneCardShell>
  );
}

// ============================================================================
// Kod bekleniyor durumu
// ============================================================================

function PhonePendingPanel({
  slot,
  phone,
}: {
  slot: "primary" | "secondary";
  phone: PickedPhone;
}) {
  const verifyPrimary = usePhoneVerify();
  const verifySecondary = usePhoneSecondaryVerify();
  const verify = slot === "secondary" ? verifySecondary : verifyPrimary;
  const startPrimary = usePhoneStart();
  const startSecondary = usePhoneSecondaryStart();
  const startMut = slot === "secondary" ? startSecondary : startPrimary;
  const [code, setCode] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    verify.mutate({ code });
  }

  function resend() {
    if (phone.pendingNumber) {
      startMut.mutate({ phone: phone.pendingNumber });
    }
  }

  return (
    <PhoneCardShell
      slot={slot}
      badge={
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700 border border-amber-200">
          <Clock className="size-3" aria-hidden />
          Kod bekleniyor
        </span>
      }
    >
      <div className="space-y-3">
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          <code className="bg-white/60 px-1.5 py-0.5 rounded font-mono">
            +{phone.pendingNumber}
          </code>{" "}
          numarasına 6 haneli SMS kodu gönderildi. Kodu girip onaylayın
          (geçerlilik 10 dakika).
        </div>

        {phone.devTestCode && (
          <div className="rounded-md border border-slate-300 bg-slate-100 p-2 text-xs flex items-center gap-2">
            <ShieldCheck className="size-4 text-slate-600 shrink-0" aria-hidden />
            <span className="font-semibold">DEV:</span>
            <span>SMS gönderim devre dışı (stub). Test kodu:</span>
            <code className="bg-white px-2 py-0.5 rounded border border-slate-300 font-mono">
              {phone.devTestCode}
            </code>
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor={`code-${slot}`}>Doğrulama kodu</Label>
            <Input
              id={`code-${slot}`}
              type="text"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              placeholder="6 haneli kod"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-40 mt-1 text-lg tracking-widest font-mono text-center"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button
              type="submit"
              className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
              disabled={verify.isPending}
            >
              {verify.isPending ? (
                <>
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                  Doğrulanıyor…
                </>
              ) : (
                "Kodu Doğrula"
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={resend}
              disabled={startMut.isPending}
              className="text-[#117A86]"
            >
              ↻ Yeni kod gönder
            </Button>
          </div>
        </form>
      </div>
    </PhoneCardShell>
  );
}

// ============================================================================
// Başlangıç durumu (telefon yok / kaldırıldı)
// ============================================================================

function PhoneStartPanel({ slot }: { slot: "primary" | "secondary" }) {
  const startPrimary = usePhoneStart();
  const startSecondary = usePhoneSecondaryStart();
  const mut = slot === "secondary" ? startSecondary : startPrimary;
  const [phone, setPhone] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate({ phone });
  }

  return (
    <PhoneCardShell
      slot={slot}
      badge={
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 border border-slate-200">
          Kapalı
        </span>
      }
    >
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {slot === "secondary"
            ? "İkinci numaranızı ekleyin. SMS ile gönderilecek 6 haneli kod ile doğrulanır."
            : "Cep telefonunuzu girin. SMS ile gönderilecek 6 haneli kod ile doğrulanır."}
        </p>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor={`phone-${slot}`}>Telefon numarası</Label>
            <Input
              id={`phone-${slot}`}
              type="tel"
              placeholder="+90 532 ..."
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full max-w-sm mt-1"
              autoComplete="tel"
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              Türkiye için <code>0532...</code> veya <code>+90 532...</code>{" "}
              formatı kabul edilir.
            </p>
          </div>
          <Button
            type="submit"
            className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
            disabled={mut.isPending}
          >
            {mut.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Gönderiliyor…
              </>
            ) : (
              "Doğrulama Kodu Gönder"
            )}
          </Button>
        </form>
      </div>
    </PhoneCardShell>
  );
}

// ============================================================================
// Soft mod — SMS doğrulama henüz operasyonel değil (sağlayıcı yok / SMS_ENABLED=false)
// ============================================================================

function PhoneSoftPanel({
  slot,
  phone,
}: {
  slot: "primary" | "secondary";
  phone: PickedPhone;
}) {
  return (
    <PhoneCardShell
      slot={slot}
      badge={
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 border border-slate-200">
          <Clock className="size-3" aria-hidden />
          Yakında
        </span>
      }
    >
      <div className="space-y-2 text-sm">
        {phone.number ? (
          <p>
            Kayıtlı numara:{" "}
            <code className="bg-muted px-1.5 py-0.5 rounded font-mono">
              +{phone.number}
            </code>
          </p>
        ) : (
          <p className="text-muted-foreground">Henüz telefon numarası eklenmedi.</p>
        )}
        <p className="text-xs text-muted-foreground leading-relaxed">
          SMS ile doğrulama şu an etkin değil.
          {phone.number ? " Numaranız kayıtlı; " : " "}
          doğrulama açıldığında buradan tek adımda tamamlayabilirsiniz. Şimdilik
          bir işlem yapmanıza gerek yok.
        </p>
      </div>
    </PhoneCardShell>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}
