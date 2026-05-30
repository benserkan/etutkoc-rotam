"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Smartphone } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PhoneCard } from "@/components/me/phone-card";
import type { MyAccountResponse } from "@/lib/types/me";

interface Props {
  /** Telefon SMS ile doğrulandı mı (UserPublic.phone_verified). Server-side
   *  prop; gerçek "şu an doğrulandı mı" sorusunu /me query'sinden de takip
   *  ederiz (doğrulama bittikten sonra anlık yansır). */
  phoneVerified: boolean;
}

/**
 * Üst sayfa bandı — kullanıcının cep telefonu doğrulanmadıysa **kapatılamaz**
 * uyarı banner'ı. "Şimdi Doğrula" tıklanınca inline dialog açılır; kullanıcı
 * panelden ayrılmadan telefon ekleyip doğrulayabilir.
 *
 * Tasarım kararları (kullanıcı 2026-05-30):
 *   - Çarpı/X kapatma butonu YOK — doğrulama tamamlanana kadar görünür kalır
 *   - "/me/account" sayfasına yönlendirme yok — kullanıcı sayfayı değiştirmez
 *     (güvenlik algısı + UX: panelden ayrılmadan tek tıkla doğrulama)
 *   - Dialog kapanınca router.refresh() → SSR taze, doğrulanmış kullanıcıda
 *     banner otomatik kaybolur; doğrulamadan kapatırsa banner kalır (doğru)
 */
export function PhoneVerifyBanner({ phoneVerified }: Props) {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();

  // İçeride PhoneCard'ın kullandığı /me query'sini biz de takip edelim →
  // doğrulama anında banner anında gizlenir (SSR refresh beklemez).
  const meQuery = useQuery<MyAccountResponse>({
    queryKey: ["me"],
    queryFn: () => api<MyAccountResponse>("/api/v2/me"),
    enabled: !phoneVerified,
    staleTime: 30_000,
  });

  const liveVerified =
    meQuery.data?.phone?.phone_verified_at != null;
  const showBanner = !phoneVerified && !liveVerified;

  // Dialog kapandığında: doğrulandıysa SSR'ı tazele (banner kaybolur)
  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next && liveVerified) {
      router.refresh();
    }
  }

  if (!showBanner) return null;

  return (
    <>
      <div className="bg-amber-50 border-b border-amber-300">
        <div className="mx-auto max-w-6xl px-4 py-3 flex flex-wrap items-center gap-3">
          <div className="rounded-full bg-amber-200 p-2 shrink-0">
            <Smartphone className="size-4 text-amber-800" aria-hidden />
          </div>
          <div className="flex-1 min-w-[220px]">
            <div className="text-sm font-semibold text-amber-900">
              Cep telefonunuzu doğrulayın
            </div>
            <p className="text-xs text-amber-800/90 mt-0.5 leading-relaxed max-w-3xl">
              WhatsApp bildirimleri, şifre sıfırlama ve önemli güvenlik
              uyarıları için cep telefonunuzun SMS ile doğrulanması gereklidir.
              Doğrulanana kadar bu uyarı her sayfada görünür.
            </p>
          </div>
          <Button
            type="button"
            onClick={() => setOpen(true)}
            className="bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-2 h-auto shrink-0"
            aria-label="Cep telefonu doğrulama akışını başlat"
          >
            Şimdi Doğrula
            <ChevronRight className="size-3.5" aria-hidden />
          </Button>
        </div>
      </div>

      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <Smartphone className="size-5 text-[#117A86]" aria-hidden />
              Cep telefonu doğrulama
            </DialogTitle>
            <DialogDescription>
              SMS ile gönderilecek 6 haneli kodu girerek telefonunuzu
              doğrulayın. Panelden ayrılmadan tamamlayabilirsiniz.
            </DialogDescription>
          </DialogHeader>
          {/* PhoneCard kendi /me query'sini paylaşır; mutation success
              sonrası dialog otomatik yeşil "Doğrulandı" durumuna geçer.
              Kullanıcı dialog'u kapatınca router.refresh() çağrılır. */}
          <div className="mt-2">
            <PhoneCard slot="primary" />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
