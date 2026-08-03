"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCircle2, Clock, CreditCard, Gem, Loader2, Lock, Mail, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { applyInvalidate } from "@/lib/invalidate";
import { AiConsentCard, AiUsageCard } from "@/components/teacher/ai-usage-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  cancelSubscription,
  getTeacherPlan,
  resumeSubscription,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  getPaymentProviderStatus,
  paymentKeys,
} from "@/lib/api/payment";
import { useInitPaymentCheckout } from "@/lib/hooks/use-payment-mutations";
import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import { CreditCostsTable, PlanFaq, PlanMatrix } from "@/components/pricing/plan-extras";
import { FeatureLine, buildGlossaryMap } from "@/components/pricing/feature-info";
import type { PricingCatalog } from "@/lib/types/pricing";
import type { TeacherPlanResponse } from "@/lib/types/teacher";

function tl(n: number): string {
  return `${n.toLocaleString("tr-TR")} ₺`;
}

function studentCapLabel(max: number | null): string {
  return max == null ? "Sınırsız öğrenci" : `${max} öğrenciye kadar`;
}

export function TeacherPlanClient({
  initial,
  initialPlan = null,
}: {
  initial: TeacherPlanResponse;
  initialPlan?: string | null;
}) {
  const q = useQuery<TeacherPlanResponse>({
    queryKey: teacherKeys.plan(),
    queryFn: getTeacherPlan,
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 sm:p-6">
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
            <p className="text-lg font-semibold">
              {data.trial_active && data.post_trial_plan_label
                ? `${data.post_trial_plan_label} — ${data.trial_days_left ?? 14} gün ücretsiz deneme`
                : data.plan_label}
            </p>
            <StatusLine status={data.status} daysLeft={data.trial_days_left} subStatus={data.subscription_status} />
          </div>
          <AiPill aiPremium={data.ai_premium} status={data.status} daysLeft={data.trial_days_left} />
        </CardContent>
      </Card>

      {/* Trial niyetli plan bilgi notu */}
      {data.trial_active && data.post_trial_plan && data.post_trial_plan !== "solo_free" && data.post_trial_plan_label ? (
        <div className="rounded-lg border border-cyan-200 bg-cyan-50/70 px-4 py-3 text-sm text-cyan-900 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-200">
          <p className="font-semibold">Deneme süren bittiğinde</p>
          <p className="mt-0.5">
            <strong>{data.post_trial_plan_label}</strong> paketine geçmek için <strong>ödeme</strong> talep edilir.
            {data.post_trial_plan_credits && data.post_trial_plan_credits > 0 ? (
              <>
                {" "}Yapay zekâ kredin{" "}
                <strong>{(data.post_trial_plan_credits).toLocaleString("tr-TR")} / ay</strong>{" "}
                olur ve ay başında otomatik yenilenir.
              </>
            ) : null}
            {" "}Ödemezsen <strong>Keşif</strong>&apos;e (ücretsiz — 3 öğrenci, yapay zekâ kapalı) düşersin.
          </p>
        </div>
      ) : null}

      {/* Deneme bitti + seçilen paket henüz ödenmedi — net ödeme daveti */}
      {!data.trial_active && data.status === "free" && data.post_trial_plan &&
       data.post_trial_plan !== "solo_free" && data.post_trial_plan_label ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
          <p className="font-semibold">Denemen bitti — ödemen bekleniyor</p>
          <p className="mt-0.5">
            Kayıt olurken <strong>{data.post_trial_plan_label}</strong> paketini seçmiştin.
            Öğrencilerin ve verilerin duruyor; kaldığın yerden tüm özelliklerle devam
            etmek için aşağıdan <strong>Kartla Öde</strong> ile ödemeni tamamlaman yeterli.
            Paketin seçili olarak geliyor.
          </p>
        </div>
      ) : null}

      {/* Ödeme kayıtsız ücretli plan (anormal durum) — ödemeye çağır */}
      {data.status === "payment_required" ? (
        <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200">
          <p className="font-semibold">Paketinin ödemesi tamamlanmamış görünüyor</p>
          <p className="mt-0.5">
            Aboneliğini aktive etmek için aşağıdan ödemeni tamamlayabilir veya
            bir yanlışlık olduğunu düşünüyorsan destek ekibiyle iletişime geçebilirsin.
          </p>
        </div>
      ) : null}

      {/* AI Kredi durumu — YALNIZ AI'ın açık olduğu durumlarda (deneme/aktif).
          Ücretsizde çubuk göstermek "kredim var ama kullanamıyorum" karışıklığı
          yaratıyordu (kullanıcı ekran görüntüsü, 2026-08-04). */}
      {data.is_solo && data.ai_credits_allocated > 0 &&
        (data.status === "trialing" || data.status === "active") ? (
        <AiCreditMeter
          used={data.ai_credits_used}
          allocated={data.ai_credits_allocated}
          trialActive={data.trial_active}
          postTrialPlanLabel={data.post_trial_plan_label}
          postTrialPlanCredits={data.post_trial_plan_credits}
        />
      ) : null}

      {data.status === "managed" || !data.is_solo ? (
        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30">
          {data.note ?? "Paketin kurumun tarafından yönetilir."}
        </div>
      ) : data.status === "active" ? (
        <>
          <ActiveSubscriptionCard data={data} />
          {/* Aktif abone de bir üst pakete kartla geçebilmeli — yükseltme anı
              CTA'sı (?plan=) burada karşılık bulur. App Store abonesi hariç
              (paket değişikliği Apple'da). */}
          {data.subscription_platform !== "app_store" ? (
            <SoloUpgradeCard data={data} initialPlan={initialPlan} />
          ) : null}
        </>
      ) : (
        <SoloUpgradeCard data={data} initialPlan={initialPlan} />
      )}

      {/* Krediler ne yapar + paket karşılaştırma + SSS (public /pricing ile ortak) */}
      <PlanExtras />

      {/* Yapay zekâ: kullanım dökümü (kim/ne harcadı) + onay anahtarı */}
      <AiUsageCard />
      <AiConsentCard />

      <p className="text-[11px] text-muted-foreground">
        Yapay zekâ özellikleri (sesli dikte, fotoğraftan seans doldurma, koçluk içgörüsü)
        ücretli pakette ve aktif denemede açıktır; kullanım kendi kredinden düşer.
        Öğrenci ve veli özellikleri de senin havuzundan harcar — kişi bazında
        açma/kapatma öğrenci sayfasındaki &quot;Yapay zekâ erişimi&quot; kartındadır.
      </p>
    </div>
  );
}

function PlanExtras() {
  const q = useQuery<PricingCatalog>({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 5 * 60_000,
  });
  if (!q.data) return null;
  return (
    <div className="space-y-5">
      <CreditCostsTable rows={q.data.credit_costs ?? []} />
      <PlanMatrix catalog={q.data} />
      <PlanFaq />
    </div>
  );
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}

function AiCreditMeter({
  used, allocated, trialActive, postTrialPlanLabel, postTrialPlanCredits,
}: {
  used: number;
  allocated: number;
  trialActive: boolean;
  postTrialPlanLabel: string | null;
  postTrialPlanCredits: number | null;
}) {
  const remaining = Math.max(0, allocated - used);
  const pct = allocated > 0 ? Math.min(100, Math.round((used / allocated) * 100)) : 0;
  const exhausted = remaining === 0;
  const lowThreshold = trialActive ? 10 : Math.max(5, Math.round(allocated * 0.1));
  const low = remaining > 0 && remaining <= lowThreshold;

  const barColor = exhausted ? "bg-rose-500" : low ? "bg-amber-500" : "bg-emerald-500";
  const ringColor = exhausted ? "border-rose-200 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/30" : low ? "border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30" : "border-emerald-200 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-500/30";
  const textColor = exhausted ? "text-rose-900" : low ? "text-amber-900" : "text-emerald-900";

  // Deneme kredisi vs. paket kredisi karşılaştırması
  const hasIntendedPlan = trialActive && postTrialPlanLabel && postTrialPlanCredits && postTrialPlanCredits > 0;
  const multiplier = hasIntendedPlan ? Math.round((postTrialPlanCredits ?? 0) / allocated) : 0;

  return (
    <div className={cn("rounded-lg border px-4 py-3 text-sm", ringColor, textColor)}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-semibold">
          {trialActive ? "Yapay zekâ kredisi (deneme)" : "Yapay zekâ kredisi"}
        </p>
        <p className="tabular-nums">
          <span className="font-semibold">{used.toLocaleString("tr-TR")}</span>
          <span className="opacity-70"> / {allocated.toLocaleString("tr-TR")} kullanıldı</span>
          <span className="ml-2 font-semibold">({remaining.toLocaleString("tr-TR")} kaldı)</span>
        </p>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/70">
        <div className={cn("h-full transition-all", barColor)} style={{ width: `${pct}%` }} />
      </div>

      {/* Deneme açıklaması — kullanıcı 50'nin "denemeye özel" tavan olduğunu görsün */}
      {hasIntendedPlan ? (
        <div className="mt-2 rounded-md border border-current/20 bg-white/50 px-3 py-2 text-xs">
          <p>
            <strong>{allocated} kredi yalnız deneme süresine özeldir.</strong>{" "}
            <strong className="text-cyan-800">{postTrialPlanLabel}</strong> paketine geçtiğinde
            aylık <strong className="text-cyan-800">{(postTrialPlanCredits ?? 0).toLocaleString("tr-TR")} kredi</strong>{" "}
            ({multiplier > 1 ? `~${multiplier}× daha fazla` : "yenilenen kredi"}) tanımlanır ve ay başında otomatik yenilenir.
          </p>
        </div>
      ) : null}

      {exhausted ? (
        <p className="mt-2 text-xs">
          <strong>Krediniz bitti.</strong>
          {trialActive && postTrialPlanLabel
            ? ` Deneme süreniz devam etse de yapay zekâ için ${postTrialPlanLabel} paketine geçmeniz gerekir.`
            : " Ay başında otomatik yenilenir veya paketinizi yükseltebilirsiniz."}
        </p>
      ) : low ? (
        <p className="mt-2 text-xs">
          Krediniz azaldı. {trialActive && postTrialPlanLabel
            ? `${postTrialPlanLabel} paketine geçerek artırın.`
            : "Ay başında yenilenir."}
        </p>
      ) : null}
    </div>
  );
}

function StatusLine({ status, daysLeft, subStatus }: { status: string; daysLeft: number | null; subStatus?: string | null }) {
  if (status === "trialing") {
    const d = daysLeft ?? 0;
    return <p className="text-xs text-amber-700">Deneme sürümü — {d <= 0 ? "bugün bitiyor" : `${d} gün kaldı`}</p>;
  }
  if (status === "active") {
    if (subStatus === "canceled") {
      return <p className="text-xs text-amber-700">İptal edildi — dönem sonunda sona erecek</p>;
    }
    return <p className="text-xs text-emerald-700">Aktif abonelik</p>;
  }
  if (status === "past_due") {
    return <p className="text-xs text-rose-700">Aboneliğin yenilenmedi — yenileme gerekli</p>;
  }
  if (status === "free") {
    return <p className="text-xs text-slate-500">Ücretsiz — 3 öğrenci, yapay zekâ kapalı</p>;
  }
  if (status === "payment_required") {
    return <p className="text-xs text-rose-700">Ödeme bekleniyor — paket ödemesi tamamlanmadı</p>;
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

function ActiveSubscriptionCard({ data }: { data: TeacherPlanResponse }) {
  const qc = useQueryClient();
  const [confirmCancel, setConfirmCancel] = React.useState(false);
  const canceled = data.subscription_status === "canceled";
  // App Store (IAP) aboneliği: iptal/geri alma Apple tarafında yapılır —
  // buradaki butonlar gizlenir (backend de 400 app_store_managed döner).
  const appStoreManaged = data.subscription_platform === "app_store";

  const cancelMut = useMutation({
    mutationFn: () => cancelSubscription(),
    onSuccess: (res) => { applyInvalidate(qc, res.invalidate); setConfirmCancel(false); },
  });
  const resumeMut = useMutation({
    mutationFn: () => resumeSubscription(),
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        {canceled ? (
          <>
            <p className="flex items-start gap-2 text-sm font-medium text-amber-800">
              <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
              Aboneliğin iptal edildi
              {data.subscription_period_end ? <> — <strong>{fmtDate(data.subscription_period_end)}</strong> tarihinde sona erecek.</> : "."}
            </p>
            <p className="text-xs text-muted-foreground">
              O tarihe kadar tüm özellikler açık. Devam etmek istersen iptali geri alabilirsin.
            </p>
            {appStoreManaged ? (
              <p className="text-xs text-slate-600">
                Aboneliğin App Store üzerinden yönetiliyor — yeniden başlatmak için
                iPhone/iPad&apos;de <strong>Ayarlar → Apple Kimliği → Abonelikler</strong>.
              </p>
            ) : (
              <Button
                onClick={() => resumeMut.mutate()}
                disabled={resumeMut.isPending}
                className="bg-cyan-700 text-white hover:bg-cyan-800"
              >
                {resumeMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                İptali geri al
              </Button>
            )}
          </>
        ) : (
          <>
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-700">
              <CheckCircle2 className="size-4" aria-hidden /> Aboneliğin aktif — tüm yapay zekâ özellikleri açık.
            </p>
            {data.subscription_period_end ? (
              <p className="text-sm">
                Sonraki yenileme: <strong>{fmtDate(data.subscription_period_end)}</strong>
                {data.subscription_cycle === "academic_year" ? " (akademik yıl)" : " (aylık)"}
              </p>
            ) : null}
            {appStoreManaged ? (
              <p className="text-xs text-slate-600">
                Aboneliğin App Store üzerinden yönetiliyor — paket değişikliği ve iptal,
                iPhone/iPad&apos;deki uygulamadan veya <strong>Ayarlar → Apple Kimliği →
                Abonelikler</strong>&apos;den yapılır.
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmCancel(true)}
                className="text-xs text-rose-600 underline-offset-2 hover:underline"
              >
                Aboneliği iptal et
              </button>
            )}
          </>
        )}
      </CardContent>

      <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aboneliği iptal et</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Aboneliğin yenilenmeyecek. <strong>Dönem sonuna kadar
            ({data.subscription_period_end ? fmtDate(data.subscription_period_end) : "süre dolana kadar"})
            tüm özellikler açık kalır</strong>; sonra ücretsiz sürüme döner.
            Öğrencilerin ve verilerin silinmez.
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setConfirmCancel(false)} disabled={cancelMut.isPending}>
              Vazgeç
            </Button>
            <Button
              onClick={() => cancelMut.mutate()}
              disabled={cancelMut.isPending}
              className="bg-rose-600 text-white hover:bg-rose-700"
            >
              {cancelMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Aboneliği iptal et
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function SoloUpgradeCard({
  data,
  initialPlan = null,
}: {
  data: TeacherPlanResponse;
  initialPlan?: string | null;
}) {
  const [yearly, setYearly] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  const months = data.annual_paid_months || 10;
  // Paket özellik bullet dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200'ları TEK KAYNAK: /api/v2/pricing plan_features
  // (hardcoded TIER_DETAILS.features yerine; pazarlama dili + vitrinle tutarlı).
  const pricingQ = useQuery({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 5 * 60_000,
  });
  const catalogCards = pricingQ.data?.cards ?? [];
  const cardFor = (code: string) => catalogCards.find((c) => c.plan === code);

  // Yükseltilebilir Solo paketleri (3 kapaklı tier).
  // Öncelik: signup'ta seçilen paket (post_trial_plan) > recommended (öğrenci
  // sayısı) > tier önerisi > solo_pro. Kullanıcının kasıtlı seçimi kaybolmaz.
  const tiers = data.options.filter((o) => o.code !== "solo_free");
  const intendedFromSignup =
    data.post_trial_plan && data.post_trial_plan !== "solo_free"
      ? data.post_trial_plan
      : "";
  const recommended =
    (initialPlan && tiers.some((t) => t.code === initialPlan) ? initialPlan : "") ||
    intendedFromSignup ||
    data.recommended_plan ||
    tiers.find((t) => t.is_recommended)?.code ||
    tiers[0]?.code ||
    "solo_pro";
  const [selected, setSelected] = React.useState(recommended);
  // recommended değişirse (öğrenci sayısı tier sınırı aştığında) seçimi senkronla
  // — effect yerine "prop değişince state ayarla" render deseni.
  const [prevRec, setPrevRec] = React.useState(recommended);
  if (recommended !== prevRec) {
    setPrevRec(recommended);
    setSelected(recommended);
  }

  const selTier = tiers.find((t) => t.code === selected) ?? tiers[0];
  const monthly = selTier?.price_monthly_try ?? 0;
  const shownMonthly = yearly ? Math.round((monthly * months) / 12) : monthly;
  const cycleLabel = yearly ? "akademik yıl peşin · 2 ay bedava" : "aylık · istediğin zaman iptal";

  return (
    <Card className="overflow-hidden border-cyan-200">
      <div className="h-1 w-full bg-gradient-to-r from-cyan-600 to-cyan-800" aria-hidden />
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-display text-lg font-bold">
              {data.status === "past_due"
                ? "Aboneliğini yenile"
                : data.status === "payment_required"
                  ? "Ödemeni tamamla"
                  : data.status === "active"
                    ? "Paketini büyüt"
                    : data.status === "free" && intendedFromSignup && data.post_trial_plan_label
                      ? `Denemen bitti — ${data.post_trial_plan_label} ile devam et`
                      : "Paketini seç"}
            </p>
            <p className="text-sm text-muted-foreground">
              {data.status === "trialing"
                ? "Denemen bitmeden geç; tüm öğrencilerin ve yapay zekâ kesintisiz devam etsin."
                : data.status === "past_due"
                  ? "Aboneliğin yenilenmedi. Ödeyip yenileyerek aktif koçluğa devam et; pasif öğrencilerin otomatik yeniden aktif olur."
                  : data.status === "active"
                    ? "Öğrenci sayın büyüdüyse bir üst pakete kartla ödeyerek geçebilirsin — yeni paket ödemeyle birlikte hemen açılır."
                    : data.status === "free" && intendedFromSignup
                      ? "Seçtiğin paket aşağıda hazır. Kartla ödediğin anda tüm özellikler açılır; pasif öğrencilerin otomatik yeniden aktif olur."
                      : "Öğrenci sayına uygun paketi seç. Yükselttiğinde yapay zekâ açılır ve pasif öğrencilerin otomatik yeniden aktif olur."}
            </p>
          </div>
          {/* Aylık / Akademik yıl toggle */}
          <div className="inline-flex items-center gap-1 rounded-full border border-cyan-200 bg-cyan-50 p-1 text-xs font-bold dark:bg-cyan-500/10 dark:border-cyan-500/30">
            <button
              type="button"
              onClick={() => setYearly(false)}
              className={cn("rounded-full px-3 py-1.5 transition", !yearly ? "bg-white text-cyan-800 shadow-sm" : "text-slate-500")}
            >
              Aylık
            </button>
            <button
              type="button"
              onClick={() => setYearly(true)}
              className={cn("inline-flex items-center gap-1 rounded-full px-3 py-1.5 transition", yearly ? "bg-white text-cyan-800 shadow-sm" : "text-slate-500")}
            >
              Akademik Yıl
              <span className="rounded bg-amber-100 px-1 py-0.5 text-[9px] uppercase text-amber-700">2 ay bedava</span>
            </button>
          </div>
        </div>

        {/* Aktif öğrenci durumu */}
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200">
          Şu an <strong className="text-slate-900">{data.student_count}</strong> aktif öğrencin var.
          {data.post_trial_plan && data.post_trial_plan !== "solo_free" ? (
            <> Kayıtta seçtiğin paket: <strong className="text-cyan-800">{data.post_trial_plan_label}</strong>.</>
          ) : null}
          {" "}{cycleLabel}.
        </div>

        {/* 3 BÜYÜK detaylı paket kartı yan yana */}
        <div className="grid gap-4 lg:grid-cols-3">
          {tiers.map((t) => {
            const isSel = t.code === selected;
            const cCard = cardFor(t.code);
            const tierMonthly = yearly ? Math.round((t.price_monthly_try * months) / 12) : t.price_monthly_try;
            const tierYearlyTotal = t.price_monthly_try * months;
            const isIntended = data.post_trial_plan === t.code;
            const isRecommended = t.is_recommended;
            return (
              <div
                key={t.code}
                className={cn(
                  "relative flex flex-col rounded-2xl border-2 bg-white p-5 transition",
                  isSel
                    ? "border-cyan-600 shadow-lg ring-2 ring-cyan-100"
                    : "border-slate-200 hover:border-cyan-300",
                )}
              >
                {/* Üst rozetler */}
                {cCard?.badge ? (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 px-3 py-0.5 text-[11px] font-bold text-cyan-950 shadow-sm">
                    {cCard.badge}
                  </span>
                ) : null}
                {isIntended ? (
                  <span className="absolute right-3 top-3 rounded-full bg-cyan-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    Denemede açık
                  </span>
                ) : isRecommended && !isIntended ? (
                  <span className="absolute right-3 top-3 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800">
                    Sana uygun
                  </span>
                ) : null}

                {/* Başlık */}
                <div className="mb-3">
                  <h3 className="font-display text-xl font-extrabold text-slate-900">{t.label}</h3>
                  <p className="text-xs text-slate-600">{studentCapLabel(t.max_students)}</p>
                </div>

                {/* Fiyat */}
                <div className="mb-4">
                  <div className="flex items-baseline gap-1">
                    <span className="font-display text-3xl font-extrabold text-slate-900">{tl(tierMonthly)}</span>
                    <span className="text-sm text-slate-500">/ay</span>
                  </div>
                  {yearly ? (
                    <p className="text-[11px] text-slate-500">
                      yıllık <strong>{tl(tierYearlyTotal)}</strong> tek seferlik (2 ay bedava)
                    </p>
                  ) : (
                    <p className="text-[11px] text-slate-500">aylık · istediğin zaman iptal</p>
                  )}
                  {cCard?.per_student_note ? (
                    <p className="text-[11px] font-medium text-cyan-700">{cCard.per_student_note}</p>
                  ) : null}
                </div>

                {/* AI kredi ön plana çıkar — insan diliyle */}
                {cCard?.credits_monthly ? (
                  <div className="mb-4 rounded-lg border border-cyan-200 bg-cyan-50/70 px-3 py-2 dark:bg-cyan-500/10 dark:border-cyan-500/30">
                    <p className="text-[10px] font-bold uppercase tracking-wide text-cyan-800 dark:text-cyan-300">Aylık yapay zekâ kredisi</p>
                    <p className="font-display text-2xl font-extrabold text-cyan-900 dark:text-cyan-200">{cCard.credits_monthly.toLocaleString("tr-TR")} <span className="text-xs font-medium text-cyan-700 dark:text-cyan-300">kredi</span></p>
                    {cCard.credit_note ? (
                      <p className="mt-1 text-[11px] leading-4 text-cyan-800 dark:text-cyan-300">{cCard.credit_note}</p>
                    ) : null}
                  </div>
                ) : null}

                {/* Kademeli özellikler — TEK KAYNAK (katalog kartı):
                    "Öncekinin hepsi, artı:" + yalnız bu kademenin yenileri */}
                {cCard ? (
                  <ul className="mb-5 space-y-2 text-sm">
                    {cCard.inherits ? (
                      <li className="text-[11px] font-bold uppercase tracking-wide text-cyan-700">
                        {cCard.inherits}
                      </li>
                    ) : null}
                    {cCard.features.map((f) => (
                      <li key={f} className="flex items-start gap-2">
                        <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
                        <FeatureLine
                          text={f}
                          glossary={buildGlossaryMap(pricingQ.data?.feature_glossary)}
                        />
                      </li>
                    ))}
                  </ul>
                ) : null}

                {/* CTA — plan adı kart başlığında zaten büyük; buton sadeleşti */}
                <div className="mt-auto">
                  <Button
                    className={cn(
                      "w-full whitespace-normal text-sm",
                      isSel
                        ? "bg-cyan-700 text-white hover:bg-cyan-800"
                        : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
                    )}
                    onClick={() => {
                      setSelected(t.code);
                      if (isSel) setOpen(true);
                    }}
                  >
                    {isSel ? "Bu pakete geç (öde)" : "Bu paketi seç"}
                  </Button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Alt bilgi: seçili olanın özet açıklaması */}
        <div className="rounded-md border border-slate-200 bg-slate-50/60 px-3 py-2 text-[11px] text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30">
          Seçili paket <strong className="text-slate-900">{selTier?.label}</strong> · {tl(shownMonthly)}/ay.
          Aylık AI kredisi (sesli dikte 3, fotoğraftan not 5, koçluk içgörüsü 6 kredi başına) ay başında otomatik yenilenir.
          {data.status === "past_due" ? " Aboneliğin yenilenmedi — ödeme ile aktif koçluğa devam eder." : null}
        </div>
      </CardContent>

      <UpgradeDialog
        open={open}
        onClose={() => setOpen(false)}
        plan={selected}
        planLabel={selTier?.label ?? "Rota"}
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
  planLabel,
  cycle,
  priceLabel,
  salesEmail,
}: {
  open: boolean;
  onClose: () => void;
  plan: string;
  planLabel: string;
  cycle: string;
  priceLabel: string;
  salesEmail: string;
}) {
  // Tek ödeme yöntemi: iyzico kart (havale KALDIRILDI). provider available ise
  // "Kartla Öde"; geçici kapalıysa iletişim.
  const providerQ = useQuery({
    queryKey: paymentKeys.providerStatus(),
    queryFn: getPaymentProviderStatus,
    staleTime: 60_000,
    enabled: open,
  });
  const cardCheckout = useInitPaymentCheckout();
  const cardAvailable = providerQ.data?.available === true;
  const inSandbox = providerQ.data?.sandbox === true;

  const mailto = salesEmail
    ? `mailto:${salesEmail}?subject=${encodeURIComponent(`${planLabel} abonelik`)}`
    : "";

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Gem className="size-4 text-cyan-700" aria-hidden /> {planLabel} paketine geç
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-cyan-200 bg-cyan-50/60 p-3 dark:bg-cyan-500/10 dark:border-cyan-500/30">
            <span className="text-muted-foreground">Seçilen:</span>{" "}
            <span className="font-semibold text-cyan-900">{planLabel} · {priceLabel}</span>
          </div>
          {cardAvailable ? (
            <p className="flex items-start gap-2 text-muted-foreground">
              <CreditCard className="mt-0.5 size-4 shrink-0" aria-hidden />
              Kartınla anında ve güvenle ödersin (3D Secure, iyzico). Ödeme onaylanınca
              paketin hemen aktive olur.
              {inSandbox ? (
                <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
                  TEST modu
                </span>
              ) : null}
            </p>
          ) : (
            <p className="flex items-start gap-2 text-muted-foreground">
              <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
              Kartlı ödeme şu an geçici olarak kullanılamıyor. Kısa süre sonra
              tekrar dene veya bizimle iletişime geç.
            </p>
          )}
        </div>
        <DialogFooter className="gap-2 pt-2">
          {mailto ? (
            <Button asChild variant="ghost">
              <a href={mailto}><Mail className="size-4" aria-hidden /> İletişim</a>
            </Button>
          ) : null}
          {cardAvailable ? (
            <Button
              className="bg-cyan-700 text-white hover:bg-cyan-800"
              disabled={cardCheckout.isPending}
              onClick={() => {
                // Iyzico backend `monthly | annual` bekler; akademik yıl → annual.
                const iyzicoCycle: "monthly" | "annual" =
                  cycle === "academic_year" ? "annual" : "monthly";
                cardCheckout.mutate(
                  { plan_code: plan, cycle: iyzicoCycle },
                  { onSuccess: (res) => { window.location.href = res.payment_page_url; } },
                );
              }}
            >
              {cardCheckout.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <CreditCard className="size-4" aria-hidden />
              )}
              Kartla Öde
            </Button>
          ) : (
            <Button variant="outline" onClick={onClose}>Kapat</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
