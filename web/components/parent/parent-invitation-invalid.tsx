import Link from "next/link";
import { AlertCircle, CheckCircle2, Clock, Link2Off } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

/**
 * Davet geçersiz ekranı — 4 durum (not_found/expired/consumed/diğer).
 *
 * Jinja parite: invitation_invalid.html — emoji yerine Lucide ikonu.
 */

interface Props {
  reason: string;
}

const TONES: Record<
  string,
  {
    Icon: typeof AlertCircle;
    title: string;
    body: string;
    iconClass: string;
    showLogin?: boolean;
  }
> = {
  not_found: {
    Icon: Link2Off,
    title: "Bu davet bağlantısı tanınmıyor",
    body: "Bağlantı eksik veya bozulmuş olabilir. Lütfen size gelen e-postadaki linki kopyalayıp tarayıcınıza yapıştırarak tekrar deneyin.",
    iconClass: "text-slate-500",
  },
  expired: {
    Icon: Clock,
    title: "Davetin süresi dolmuş",
    body: "Veli davetleri 7 gün geçerlidir. Lütfen sizi davet eden eğitim koçunuzla iletişime geçerek yeni bir davet talep edin.",
    iconClass: "text-amber-600",
  },
  consumed: {
    Icon: CheckCircle2,
    title: "Bu davet zaten kullanılmış",
    body: "Bu link daha önce kabul edilerek bir hesap oluşturuldu. Aşağıdaki butondan giriş yapabilirsiniz.",
    iconClass: "text-emerald-600",
    showLogin: true,
  },
};

export function ParentInvitationInvalid({ reason }: Props) {
  const tone = TONES[reason] ?? {
    Icon: AlertCircle,
    title: "Davet kullanılamıyor",
    body: "Bilinmeyen bir hata. Lütfen koçunuzla iletişime geçin.",
    iconClass: "text-rose-500",
  };
  const Icon = tone.Icon;

  return (
    <div className="min-h-screen bg-muted/20 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-5">
          <p className="font-display text-xl font-bold tracking-tight">
            ETÜTKOÇ
          </p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-1">
            Veli Daveti
          </p>
        </div>

        <Card className="border-border shadow-sm">
          <CardContent className="p-8 text-center space-y-3">
            <div className="flex justify-center">
              <div
                className={`rounded-full p-4 bg-muted ${tone.iconClass}`}
                aria-hidden
              >
                <Icon className="size-10" />
              </div>
            </div>
            <h1 className="text-lg font-semibold">{tone.title}</h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {tone.body}
            </p>
            {tone.showLogin && (
              <div className="pt-2">
                <Button asChild>
                  <Link href="/login">Giriş Yap</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
