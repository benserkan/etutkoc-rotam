"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, Clock, Gem, Loader2, Lock, Mail, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getTeacherPlan, submitSubscriptionRequest, teacherKeys } from "@/lib/api/teacher";
import type { TeacherPlanResponse } from "@/lib/types/teacher";

function tl(n: number): string {
  return `${n.toLocaleString("tr-TR")} ₺`;
}

const SOLO_FEATURES = [
  "Sınırsız öğrenci — koçluğun büyüdükçe öde",
  "Yapay zekâ: sesli dikte + fotoğraftan not + koçluk içgörüsü",
  "Veliye otomatik ilerleme bildirimi + deneme/net takibi",
  "Aylık kredi dahil",
];

export function TeacherPlanClient({ initial }: { initial: TeacherPlanResponse }) {
  const q = useQuery<TeacherPlanResponse>({
    queryKey: teacherKeys.plan(),
    queryFn: getTeacherPlan,
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="mx-auto max-w-3xl space-y-5 p-4 sm:p-6">
      <header className="space-y-1">
        <h1 className="flex items-center gap-2 text-xl font-semibold">
          <Gem className="size-5 text-cyan-700" aria-hidden /> Abonelik
        </h1>
        <p className="text-sm text-muted-foreground">
          Mevcut paketin, durumu ve yapay zekâ erişimin.
        </p>
      </header>

      {/* Mevcut durum */}
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Mevcut paket</p>
            <p className="text-lg font-semibold">{data.plan_label}</p>
            <StatusLine status={data.status} daysLeft={data.trial_days_left} />
          </div>
          <AiPill aiPremium={data.ai_premium} status={data.status} daysLeft={data.trial_days_left} />
        </CardContent>
      </Card>

      {data.status === "managed" || !data.is_solo ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
          {data.note ?? "Paketin kurumun tarafından yönetilir."}
        </div>
      ) : data.status === "active" ? (
        <Card>
          <CardContent className="space-y-2 p-4">
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-700">
              <CheckCircle2 className="size-4" aria-hidden /> Aboneliğin aktif — tüm yapay zekâ özellikleri açık.
            </p>
            {data.subscription_period_end ? (
              <p className="text-sm">
                Sonraki yenileme: <strong>{fmtDate(data.subscription_period_end)}</strong>
                {data.subscription_cycle === "academic_year" ? " (akademik yıl)" : " (aylık)"}
              </p>
            ) : null}
            <p className="text-xs text-muted-foreground">
              Plan yönetimi (değiştir/iptal) çok yakında bu sayfada olacak.
            </p>
          </CardContent>
        </Card>
      ) : (
        <SoloUpgradeCard data={data} />
      )}

      <p className="text-[11px] text-muted-foreground">
        Yapay zekâ özellikleri (sesli dikte, fotoğraftan seans doldurma, koçluk içgörüsü)
        ücretli pakette ve aktif denemede açıktır; kullanım kendi kredinden düşer.
      </p>
    </div>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}

function StatusLine({ status, daysLeft }: { status: string; daysLeft: number | null }) {
  if (status === "trialing") {
    const d = daysLeft ?? 0;
    return <p className="text-xs text-amber-700">Deneme sürümü — {d <= 0 ? "bugün bitiyor" : `${d} gün kaldı`}</p>;
  }
  if (status === "active") {
    return <p className="text-xs text-emerald-700">Aktif abonelik</p>;
  }
  if (status === "past_due") {
    return <p className="text-xs text-rose-700">Aboneliğin yenilenmedi — yenileme gerekli</p>;
  }
  if (status === "free") {
    return <p className="text-xs text-slate-500">Ücretsiz — 3 öğrenci, yapay zekâ kapalı</p>;
  }
  return null;
}

function AiPill({
  aiPremium,
  status,
  daysLeft,
}: {
  aiPremium: boolean;
  status: string;
  daysLeft: number | null;
}) {
  let label = "Yapay zekâ kapalı";
  if (aiPremium && status === "trialing") {
    label = `Yapay zekâ — denemede açık${daysLeft != null ? ` (${daysLeft} gün)` : ""}`;
  } else if (aiPremium) {
    label = "Yapay zekâ açık";
  }
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium",
        aiPremium ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-amber-200 bg-amber-50 text-amber-800",
      )}
    >
      {aiPremium ? <Sparkles className="size-3.5" aria-hidden /> : <Lock className="size-3.5" aria-hidden />}
      {label}
    </span>
  );
}

function SoloUpgradeCard({ data }: { data: TeacherPlanResponse }) {
  const [yearly, setYearly] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const months = data.annual_paid_months || 10;
  const monthly = data.solo_monthly_price || 0;
  const shownMonthly = yearly ? Math.round((monthly * months) / 12) : monthly;
  const cycleLabel = yearly ? "akademik yıl peşin · 2 ay bedava" : "aylık · istediğin zaman iptal";

  return (
    <Card className="overflow-hidden border-cyan-200">
      <div className="h-1 w-full bg-gradient-to-r from-cyan-600 to-cyan-800" aria-hidden />
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-display text-lg font-bold">
              {data.status === "past_due" ? "Aboneliğini yenile" : "Solo'ya geç"}
            </p>
            <p className="text-sm text-muted-foreground">
              {data.status === "trialing"
                ? "Denemen bitmeden geç; tüm öğrencilerin ve yapay zekâ kesintisiz devam etsin."
                : data.status === "past_due"
                  ? "Aboneliğin yenilenmedi. Ödeyip yenileyerek aktif koçluğa devam et."
                  : "Sınırsız öğrenci ve yapay zekâ özellikleriyle koçluğa devam et."}
            </p>
          </div>
          {/* Aylık / Akademik yıl toggle */}
          <div className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50/60 p-1 text-xs font-bold">
            <button
              type="button"
              onClick={() => setYearly(false)}
              className={cn("rounded-full px-3 py-1.5 transition", !yearly ? "bg-white text-cyan-800 shadow-sm" : "text-muted-foreground")}
            >
              Aylık
            </button>
            <button
              type="button"
              onClick={() => setYearly(true)}
              className={cn("inline-flex items-center gap-1 rounded-full px-3 py-1.5 transition", yearly ? "bg-white text-cyan-800 shadow-sm" : "text-muted-foreground")}
            >
              Akademik Yıl
              <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] uppercase text-amber-700">2 ay bedava</span>
            </button>
          </div>
        </div>

        <div>
          <span className="font-display text-3xl font-extrabold">{tl(shownMonthly)}</span>
          <span className="text-sm text-muted-foreground">/ay</span>
          <p className="mt-1 text-xs text-muted-foreground">
            {data.student_count} öğrenci için · {cycleLabel}
          </p>
        </div>

        <ul className="space-y-2 text-sm">
          {SOLO_FEATURES.map((f) => (
            <li key={f} className="flex items-start gap-2.5">
              <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
              <span className="text-foreground/85">{f}</span>
            </li>
          ))}
        </ul>

        <Button className="w-full bg-cyan-700 text-white hover:bg-cyan-800" onClick={() => setOpen(true)}>
          {data.status === "past_due" ? "Yenile (öde)" : "Solo'ya geç (öde)"}
        </Button>
      </CardContent>

      <UpgradeDialog
        open={open}
        onClose={() => setOpen(false)}
        plan="solo_pro"
        cycle={yearly ? "academic_year" : "monthly"}
        priceLabel={`${tl(shownMonthly)}/ay (${yearly ? "akademik yıl" : "aylık"})`}
        salesEmail={data.sales_email}
      />
    </Card>
  );
}

function UpgradeDialog({
  open,
  onClose,
  plan,
  cycle,
  priceLabel,
  salesEmail,
}: {
  open: boolean;
  onClose: () => void;
  plan: string;
  cycle: string;
  priceLabel: string;
  salesEmail: string;
}) {
  const qc = useQueryClient();
  const [done, setDone] = React.useState(false);
  const mut = useMutation({
    mutationFn: () => submitSubscriptionRequest({ plan, cycle }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      setDone(true);
    },
  });
  const mailto = salesEmail
    ? `mailto:${salesEmail}?subject=${encodeURIComponent("Solo abonelik aktivasyonu")}`
    : "";
  const errMsg = mut.error instanceof ApiError ? mut.error.detail.message : "Bir hata oluştu, tekrar deneyin.";

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) { onClose(); setDone(false); } }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Gem className="size-4 text-cyan-700" aria-hidden /> Solo&apos;ya geç
          </DialogTitle>
        </DialogHeader>
        {done ? (
          <div className="space-y-3 py-2 text-center">
            <CheckCircle2 className="mx-auto size-10 text-emerald-500" aria-hidden />
            <p className="text-sm font-medium">Talebin alındı</p>
            <p className="text-sm text-muted-foreground">
              Ödeme/aktivasyon için en kısa sürede iletişime geçeceğiz. Onaylanınca
              hesabın Solo&apos;ya geçer.
            </p>
          </div>
        ) : (
          <div className="space-y-3 text-sm">
            <div className="rounded-lg border border-cyan-200 bg-cyan-50/60 p-3">
              <span className="text-muted-foreground">Seçilen:</span>{" "}
              <span className="font-semibold text-cyan-900">Solo · {priceLabel}</span>
            </div>
            <p className="flex items-start gap-2 text-muted-foreground">
              <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
              &quot;Öde ve devam et&quot; talebini gönder; ödeme/aktivasyon manuel
              yapılıyor — onaylanınca hesabın Solo&apos;ya geçer. (Yakında ödeme
              doğrudan buradan olacak.)
            </p>
            {mut.isError ? (
              <p className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{errMsg}</p>
            ) : null}
          </div>
        )}
        <DialogFooter className="gap-2 pt-2">
          {done ? (
            <Button onClick={() => { onClose(); setDone(false); }}>Tamam</Button>
          ) : (
            <>
              {mailto ? (
                <Button asChild variant="ghost">
                  <a href={mailto}><Mail className="size-4" aria-hidden /> İletişim</a>
                </Button>
              ) : null}
              <Button
                className="bg-cyan-700 text-white hover:bg-cyan-800"
                disabled={mut.isPending}
                onClick={() => mut.mutate()}
              >
                {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                Öde ve devam et
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
