import Link from "next/link";
import { AlertCircle, BellOff, CheckCircle2 } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { ParentUnsubscribeResult } from "@/lib/types/parent";

/**
 * /parent/unsubscribe/{token} — Public bildirim kapama.
 *
 * Jinja kaynağı: parent.py:331-378 (parent_unsubscribe) + unsubscribed.html
 * Backend: token-based, auth gerekmez. 3 durum: unsubscribed / already / invalid.
 */
export const dynamic = "force-dynamic";

export const metadata = { title: "Bildirimler — ETÜTKOÇ Rotam" };

interface PageProps {
  params: Promise<{ token: string }>;
}

export default async function ParentUnsubscribePage({ params }: PageProps) {
  const { token } = await params;
  let status: ParentUnsubscribeResult["status"] = "invalid";

  try {
    const result = await apiServer<ParentUnsubscribeResult>(
      `/api/v2/parent/unsubscribe/${encodeURIComponent(token)}`,
    );
    status = result.status;
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    // Hata durumunda da "invalid" olarak kullan
  }

  return <UnsubscribeView status={status} />;
}

function UnsubscribeView({
  status,
}: {
  status: ParentUnsubscribeResult["status"];
}) {
  return (
    <div className="min-h-screen bg-muted/20 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-5">
          <p className="font-display text-xl font-bold tracking-tight">
            ETÜTKOÇ
          </p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-1">
            Bildirim Tercihi
          </p>
        </div>

        <Card className="border-border shadow-sm">
          <CardContent className="p-8 text-center space-y-3">
            {status === "unsubscribed" ? (
              <>
                <div className="flex justify-center">
                  <div
                    className="rounded-full p-4 bg-muted text-[#117A86]"
                    aria-hidden
                  >
                    <BellOff className="size-10" />
                  </div>
                </div>
                <h1 className="text-lg font-semibold">
                  Bildirimleriniz kapatıldı
                </h1>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Bu hesaba artık günlük özet, haftalık rapor veya uyarı
                  bildirimleri göndermeyeceğiz. Davet ve doğrulama mesajları
                  (örn. hesap güvenliği için) gönderilmeye devam edebilir.
                </p>
                <p className="text-xs text-muted-foreground pt-2">
                  Fikrinizi değiştirirseniz panele giriş yaparak bildirim
                  tercihlerinizi tekrar açabilirsiniz.
                </p>
                <div className="pt-2">
                  <Button variant="outline" asChild>
                    <Link href="/login">Giriş yap</Link>
                  </Button>
                </div>
              </>
            ) : status === "already" ? (
              <>
                <div className="flex justify-center">
                  <div
                    className="rounded-full p-4 bg-muted text-emerald-600"
                    aria-hidden
                  >
                    <CheckCircle2 className="size-10" />
                  </div>
                </div>
                <h1 className="text-lg font-semibold">
                  Bildirimleriniz zaten kapalı
                </h1>
                <p className="text-sm text-muted-foreground">
                  Şu anda size sadece davet/doğrulama gibi sistem mesajları
                  gönderiyoruz.
                </p>
              </>
            ) : (
              <>
                <div className="flex justify-center">
                  <div
                    className="rounded-full p-4 bg-muted text-rose-500"
                    aria-hidden
                  >
                    <AlertCircle className="size-10" />
                  </div>
                </div>
                <h1 className="text-lg font-semibold">Bağlantı tanınmıyor</h1>
                <p className="text-sm text-muted-foreground">
                  Lütfen bildirim e-postanızdaki &ldquo;kapat&rdquo; linkine
                  tekrar tıklayın.
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
