"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertOctagon,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock,
  Home,
  Landmark,
  Loader2,
  Lock,
  ShieldCheck,
  User as UserIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useLinkCheckout } from "@/lib/hooks/use-payment-mutations";
import type { PaymentLinkHavale, PaymentLinkPublicInfo } from "@/lib/types/payment";

interface Props {
  token: string;
  info: PaymentLinkPublicInfo | null;
}

const STATUS_TONE: Record<string, string> = {
  active: "bg-amber-100 text-amber-800",
  consumed: "bg-emerald-100 text-emerald-800",
  cancelled: "bg-slate-200 text-slate-700",
  expired: "bg-rose-100 text-rose-800",
};

export function PaymentLinkClient({ token, info }: Props) {
  const checkout = useLinkCheckout(token);

  if (!info) {
    return (
      <Layout>
        <Card>
          <CardContent className="p-10 text-center">
            <AlertOctagon className="mx-auto size-12 text-rose-500" aria-hidden />
            <h1 className="mt-4 text-xl font-bold">Link bulunamadı</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Bu ödeme linki geçersiz veya size ait değil. Bağlantınızın doğru
              olduğunu kontrol edin veya size linki gönderen kişiyle iletişime
              geçin.
            </p>
            <div className="mt-6">
              <Button variant="outline" asChild>
                <Link href="/">
                  <Home className="size-4" aria-hidden /> Ana sayfa
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </Layout>
    );
  }

  const isInst = info.target_owner_type === "institution";

  return (
    <Layout>
      <Card>
        <CardContent className="p-8">
          <div className="text-center">
            <ShieldCheck className="mx-auto size-12 text-indigo-500" aria-hidden />
            <h1 className="mt-3 text-2xl font-bold tracking-tight">
              Ödeme Talebi
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              ETÜTKOÇ Rotam tarafından oluşturulan ödeme bağlantısı
            </p>
          </div>

          <div className="mt-6 space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-5 dark:bg-slate-500/10 dark:border-slate-500/30">
            <div className="flex items-center gap-3">
              {isInst ? (
                <Building2 className="size-5 text-slate-500" aria-hidden />
              ) : (
                <UserIcon className="size-5 text-slate-500" aria-hidden />
              )}
              <div>
                <div className="text-xs text-slate-600">
                  {isInst ? "Kurum" : "Kullanıcı"}
                </div>
                <div className="font-semibold text-slate-900">
                  {info.target_owner_name}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 border-t border-slate-200 pt-3">
              <div>
                <div className="text-xs text-slate-600">Paket</div>
                <div className="font-medium text-slate-900">{info.plan_label}</div>
              </div>
              <div>
                <div className="text-xs text-slate-600">Dönem</div>
                <div className="font-medium text-slate-900">{info.cycle_label}</div>
              </div>
            </div>

            <div className="border-t border-slate-200 pt-3 text-center">
              <div className="text-xs text-slate-600">Toplam Tutar</div>
              <div className="text-3xl font-bold tabular-nums text-slate-900">
                {formatAmount(info.amount, info.currency)}
              </div>
            </div>

            {info.description ? (
              <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-900 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200">
                {info.description}
              </div>
            ) : null}

            <div className="flex items-center justify-between border-t border-slate-200 pt-3">
              <span className="text-xs text-slate-600">Durum</span>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-semibold",
                  STATUS_TONE[info.status] ?? "bg-slate-100 text-slate-700",
                )}
              >
                {info.status_label}
              </span>
            </div>

            {info.expires_at && info.is_usable ? (
              <div className="flex items-center gap-2 text-xs text-amber-700">
                <Clock className="size-3" aria-hidden />
                Bu link <strong>{formatDate(info.expires_at)}</strong> tarihine
                kadar geçerli.
              </div>
            ) : null}
          </div>

          <div className="mt-6">
            {info.status === "consumed" ? (
              <SuccessBox />
            ) : !info.is_usable ? (
              <UnusableBox label={info.status_label} />
            ) : !info.can_pay ? (
              <ForbiddenBox isInst={isInst} />
            ) : info.provider_available ? (
              <PayButton
                onClick={() => {
                  checkout.mutate(undefined, {
                    onSuccess: (res) => {
                      // Iyzico checkout sayfasına yönlendir
                      window.location.href = res.payment_page_url;
                    },
                  });
                }}
                loading={checkout.isPending}
              />
            ) : (
              <HavaleFallback havale={info.havale} />
            )}
          </div>

          {info.provider_available ? (
            <p className="mt-4 text-center text-xs text-muted-foreground">
              <Lock className="mr-1 inline size-3" aria-hidden />
              Kart bilgileriniz ETÜTKOÇ&apos;a iletilmez. Ödeme, PCI-DSS
              sertifikalı Iyzico altyapısı üzerinden 3D Secure ile yapılır.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </Layout>
  );
}

function PayButton({
  onClick, loading,
}: {
  onClick: () => void;
  loading: boolean;
}) {
  return (
    <Button size="lg" className="w-full" onClick={onClick} disabled={loading}>
      {loading ? (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden /> Yönlendiriliyor...
        </>
      ) : (
        <>
          Şimdi Öde <ChevronRight className="size-4" aria-hidden />
        </>
      )}
    </Button>
  );
}

/**
 * İyzico aktif değilken (provider_available=false) kartlı ödeme yerine havale/EFT
 * gösterilir — gerçek aday çiğ hata almasın. İyzico key girilince otomatik
 * "Şimdi Öde"ye döner (provider_available=true).
 */
function HavaleFallback({ havale }: { havale: PaymentLinkHavale | null }) {
  const [copied, setCopied] = React.useState(false);

  function copyIban() {
    if (!havale?.iban) return;
    navigator.clipboard?.writeText(havale.iban.replace(/\s/g, "")).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      () => undefined,
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
        <p className="font-semibold">Kartlı ödeme yakında aktif olacak</p>
        <p className="mt-1 text-xs">
          {havale?.enabled
            ? "Şimdilik havale / EFT ile ödeyebilirsin. Ödemeni aldıktan sonra ekibimiz üyeliğini aktive eder."
            : "Ekibimiz seninle iletişime geçip ödeme adımlarını paylaşacak."}
        </p>
      </div>

      {havale?.enabled ? (
        <div className="rounded-lg border border-slate-200 bg-white p-4 dark:bg-slate-900 dark:border-slate-700">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
            <Landmark className="size-4 text-cyan-600" aria-hidden /> Havale / EFT Bilgileri
          </div>
          <dl className="mt-3 space-y-2 text-sm">
            <div>
              <dt className="text-xs text-slate-500">IBAN</dt>
              <dd className="mt-0.5 flex items-center gap-2">
                <code className="flex-1 break-all rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-900 dark:bg-slate-800 dark:text-slate-100">
                  {havale.iban}
                </code>
                <Button size="sm" variant="outline" onClick={copyIban}>
                  {copied ? "Kopyalandı" : "Kopyala"}
                </Button>
              </dd>
            </div>
            {havale.name ? (
              <div>
                <dt className="text-xs text-slate-500">Alıcı</dt>
                <dd className="mt-0.5 text-slate-900 dark:text-slate-100">{havale.name}</dd>
              </div>
            ) : null}
            {havale.note ? (
              <div>
                <dt className="text-xs text-slate-500">Açıklama</dt>
                <dd className="mt-0.5 whitespace-pre-line text-slate-700 dark:text-slate-300">{havale.note}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      ) : null}
    </div>
  );
}

function SuccessBox() {
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-center dark:bg-emerald-500/10 dark:border-emerald-500/30">
      <CheckCircle2 className="mx-auto size-8 text-emerald-600" aria-hidden />
      <p className="mt-2 text-sm font-semibold text-emerald-800">
        Bu link daha önce ödendi
      </p>
      <p className="mt-1 text-xs text-emerald-700">
        Tekrar ödeme yapmak istiyorsanız, size linki gönderen kişiden yeni link
        talep edin.
      </p>
    </div>
  );
}

function UnusableBox({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-center dark:bg-slate-500/10 dark:border-slate-500/30">
      <AlertOctagon className="mx-auto size-8 text-slate-500" aria-hidden />
      <p className="mt-2 text-sm font-semibold text-slate-700">
        Bu link artık ödenemez ({label})
      </p>
      <p className="mt-1 text-xs text-muted-foreground">
        Size linki gönderen kişi ile iletişime geçin.
      </p>
    </div>
  );
}

function ForbiddenBox({ isInst }: { isInst: boolean }) {
  return (
    <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-center dark:bg-rose-500/10 dark:border-rose-500/30">
      <Lock className="mx-auto size-8 text-rose-500" aria-hidden />
      <p className="mt-2 text-sm font-semibold text-rose-700">
        Bu linki ödemeye yetkili değilsiniz
      </p>
      <p className="mt-1 text-xs text-rose-600">
        {isInst
          ? "Bu link belirli bir kurum için oluşturuldu. Kurumun yöneticisi olarak giriş yapmanız gerekiyor."
          : "Bu link belirli bir kullanıcı için oluşturuldu. Hedef kullanıcının hesabıyla giriş yapın."}
      </p>
    </div>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  // force-light: payment sayfaları sabit açık tema (login deseni)
  return (
    <div className="force-light min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-lg">{children}</div>
    </div>
  );
}

function formatAmount(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("tr-TR", {
      style: "currency",
      currency: currency || "TRY",
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value} ${currency}`;
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
