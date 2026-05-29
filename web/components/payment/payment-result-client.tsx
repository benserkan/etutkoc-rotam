"use client";

import * as React from "react";
import Link from "next/link";
import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  Home,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { PaymentResult } from "@/lib/types/payment";

interface Props {
  result?: PaymentResult;
  errorCode?: string;
}

const ERROR_LABELS: Record<string, string> = {
  payment_provider_unavailable: "Ödeme sağlayıcıya ulaşılamadı",
  payment_not_found: "Ödeme kaydı bulunamadı",
  not_found: "Ödeme kaydı bulunamadı veya size ait değil",
  payment_token_missing: "Ödeme tokeni eksik",
};

export function PaymentResultClient({ result, errorCode }: Props) {
  if (errorCode) {
    return (
      <Layout>
        <Card>
          <CardContent className="p-10 text-center">
            <AlertOctagon className="mx-auto size-12 text-amber-500" aria-hidden />
            <h1 className="mt-4 text-xl font-bold">Bir sorun oldu</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {ERROR_LABELS[errorCode] ?? errorCode}
            </p>
            <div className="mt-6 flex justify-center gap-2">
              <Button variant="outline" asChild>
                <Link href="/">
                  <Home className="size-4" aria-hidden /> Ana sayfa
                </Link>
              </Button>
              <Button asChild>
                <Link href="/teacher/plan">
                  <RefreshCw className="size-4" aria-hidden /> Tekrar dene
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </Layout>
    );
  }

  if (!result) {
    return (
      <Layout>
        <Card>
          <CardContent className="p-10 text-center">
            <Loader2 className="mx-auto size-8 animate-spin text-muted-foreground" aria-hidden />
            <p className="mt-3 text-sm text-muted-foreground">Yükleniyor...</p>
          </CardContent>
        </Card>
      </Layout>
    );
  }

  const status = result.status;
  const succeeded = status === "succeeded";
  const failed = status === "failed" || status === "expired";
  const pending = status === "pending" || status === "3ds_pending";

  return (
    <Layout>
      <Card>
        <CardContent className="p-10 text-center">
          {succeeded ? (
            <>
              <CheckCircle2 className="mx-auto size-14 text-emerald-500" aria-hidden />
              <h1 className="mt-4 text-2xl font-bold text-emerald-700">
                Ödemen başarılı
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Paketin aktif edildi. Hesabına dönerek hizmetlerini kullanmaya
                başlayabilirsin.
              </p>
            </>
          ) : failed ? (
            <>
              <XCircle className="mx-auto size-14 text-rose-500" aria-hidden />
              <h1 className="mt-4 text-2xl font-bold text-rose-700">
                Ödeme alınamadı
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {result.status_reason ?? "Bilinmeyen bir sebeple ödeme tamamlanamadı."}
              </p>
            </>
          ) : pending ? (
            <>
              <Clock className="mx-auto size-14 text-amber-500" aria-hidden />
              <h1 className="mt-4 text-2xl font-bold text-amber-700">
                Ödemeniz işleniyor
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Banka tarafında doğrulama bekleniyor. Birkaç dakika içinde sonuç
                e-posta ile bildirilecek.
              </p>
            </>
          ) : (
            <>
              <AlertOctagon className="mx-auto size-14 text-slate-400" aria-hidden />
              <h1 className="mt-4 text-2xl font-bold">Durum: {result.status_label}</h1>
            </>
          )}

          <div className="mx-auto mt-6 max-w-sm rounded-lg border border-slate-200 bg-slate-50 p-4 text-left text-sm">
            <Row label="İşlem No" value={`#${result.transaction_id}`} />
            <Row label="Paket" value={result.plan_code} />
            <Row label="Dönem" value={result.cycle === "annual" ? "Yıllık" : "Aylık"} />
            <Row
              label="Tutar"
              value={formatAmount(result.amount, result.currency)}
            />
            <Row
              label="Durum"
              value={result.status_label}
              tone={succeeded ? "emerald" : failed ? "rose" : "amber"}
            />
          </div>

          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button variant="outline" asChild>
              <Link href="/">
                <Home className="size-4" aria-hidden /> Ana sayfa
              </Link>
            </Button>
            {succeeded ? (
              <Button asChild>
                <Link href="/teacher/dashboard">Panele git</Link>
              </Button>
            ) : failed ? (
              <Button asChild>
                <Link href="/teacher/plan">
                  <RefreshCw className="size-4" aria-hidden /> Tekrar dene
                </Link>
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>
    </Layout>
  );
}

function Layout({ children }: { children: React.ReactNode }) {
  // force-light: payment sayfaları kimlik/landing gibi koyu/açık temadan
  // bağımsız sabit açık tema (login deseni). Kontrast tutarlı kalır.
  return (
    <div className="force-light min-h-screen bg-slate-50 px-4 py-12">
      <div className="mx-auto max-w-xl">{children}</div>
    </div>
  );
}

function Row({
  label, value, tone,
}: {
  label: string;
  value: string;
  tone?: "emerald" | "rose" | "amber";
}) {
  // Koyu temada bg-slate-50 üstüne tema text rengi beyaza çözülüp okunmuyor —
  // explicit slate tonları purge-safe.
  const toneCls = tone
    ? {
        emerald: "text-emerald-700 font-semibold",
        rose: "text-rose-700 font-semibold",
        amber: "text-amber-700 font-semibold",
      }[tone]
    : "text-slate-900 font-medium";
  return (
    <div className="flex items-center justify-between border-b border-slate-200 py-1.5 last:border-0">
      <span className="text-xs text-slate-600">{label}</span>
      <span className={cn("text-sm", toneCls)}>{value}</span>
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
