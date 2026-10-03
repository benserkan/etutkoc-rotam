"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  CreditCard,
  Loader2,
  MessageCircleQuestion,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { applyInvalidate } from "@/lib/invalidate";
import { ApiError } from "@/lib/api";
import { AiConsentCard, AiUsageCard } from "@/components/teacher/ai-usage-card";
import { PlanAssistant } from "@/components/teacher/plan-assistant";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cancelSubscription, getTeacherPlan, resumeSubscription, teacherKeys } from "@/lib/api/teacher";
import { getPaymentProviderStatus, paymentKeys } from "@/lib/api/payment";
import { useInitCreditPackCheckout, useInitPaymentCheckout } from "@/lib/hooks/use-payment-mutations";
import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import { FeatureLine, buildGlossaryMap } from "@/components/pricing/feature-info";
import type { TeacherPlanOption, TeacherPlanResponse } from "@/lib/types/teacher";

/**
 * /teacher/plan — "Paketim" (2026-10-03 yeniden tasarım, mobil öncelikli).
 *
 * Tek soru: "Şu an neredeyim, ne yapmalıyım?" Sayfa üç bloktan oluşur:
 *   1. DURUM — paketin, renkli durum etiketi, üç temel bilgi ve TEK ana eylem.
 *   2. PAKETLER — öğrenci sayısına göre seçilebilen paketler + seçilen paketin
 *      içeriği + ödeme.
 *   3. DİĞER İŞLEMLER — kredi dökümü, yapay zekâ onayı, iptal (katlanır).
 * Sorun anında (ödeme geçmedi, süre doldu) sayfanın en üstünde sade dille ne
 * olduğu ve tek tıkla çözümü durur. Paket asistanı her zaman sağ altta.
 *
 * Renk dili: camgöbeği = ana eylem/marka · yeşil = her şey yolunda ·
 * kehribar = dikkat (deneme, iptal) · kırmızı = çözülmesi gereken sorun.
 */

type Cycle = "monthly" | "academic_year";

function tl(n: number): string {
  return `${Math.round(n).toLocaleString("tr-TR")} ₺`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

function capLabel(max: number | null): string {
  return max == null ? "Sınırsız öğrenci" : `${max} öğrenciye kadar`;
}

const TONE = {
  emerald: { chip: "bg-emerald-600 text-white", bar: "bg-emerald-500", ring: "border-emerald-500/40" },
  amber: { chip: "bg-amber-500 text-white", bar: "bg-amber-500", ring: "border-amber-500/40" },
  rose: { chip: "bg-rose-600 text-white", bar: "bg-rose-500", ring: "border-rose-500/40" },
  slate: { chip: "bg-slate-600 text-white", bar: "bg-slate-400", ring: "border-border" },
} as const;
type Tone = keyof typeof TONE;

export function TeacherPlanClient({
  initial,
  initialPlan = null,
  autoCheckout = false,
}: {
  initial: TeacherPlanResponse;
  initialPlan?: string | null;
  autoCheckout?: boolean;
}) {
  const q = useQuery<TeacherPlanResponse>({
    queryKey: teacherKeys.plan(),
    queryFn: getTeacherPlan,
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const pricingQ = useQuery({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 5 * 60_000,
  });
  const catalog = pricingQ.data;
  const months = data.annual_paid_months || 10;

  const tiers = data.options.filter((o) => o.code !== "solo_free");
  const n = data.student_count;
  const fits = (t: TeacherPlanOption) => t.max_students == null || n <= t.max_students;
  const tierBy = (code: string | null | undefined) => tiers.find((t) => t.code === code);
  const current = tierBy(data.plan_code);
  const isPaidState = ["active", "past_due", "payment_required"].includes(data.status);

  // Önerilen paket — sunucudaki asistanla AYNI kural: yenilenecek/ödenecek
  // mevcut paket > kayıtta seçilen paket > öğrenci sayısına uygun; yetmiyorsa
  // yeten en küçük paket.
  const suggested = (() => {
    const pref =
      tierBy(initialPlan) ??
      (isPaidState ? current : undefined) ??
      (data.post_trial_plan && data.post_trial_plan !== "solo_free" ? tierBy(data.post_trial_plan) : undefined) ??
      tierBy(data.recommended_plan);
    if (pref && fits(pref)) return pref;
    return tiers.find(fits) ?? pref ?? tiers[0];
  })();

  // Aktif abone yalnız mevcut paketini (yenileme) ve üst paketleri görür —
  // alt pakete kartla "geçmek" dönem ortasında para yakardı.
  const visibleTiers =
    data.status === "active" && current
      ? tiers.filter((t) => t.tier_rank >= current.tier_rank)
      : tiers;

  const [selected, setSelected] = React.useState<string>(suggested?.code ?? "");
  const [cycle, setCycle] = React.useState<Cycle>("monthly");
  const [checkout, setCheckout] = React.useState<{ plan: string; cycle: Cycle } | null>(() =>
    autoCheckout && suggested && fits(suggested) ? { plan: suggested.code, cycle: "monthly" } : null,
  );
  const [assistantOpen, setAssistantOpen] = React.useState(false);
  const [moreOpen, setMoreOpen] = React.useState(false);
  const [cancelOpen, setCancelOpen] = React.useState(false);

  const appStore = data.subscription_platform === "app_store";
  const canceled = data.subscription_status === "canceled";
  const showPlans = data.is_solo && !appStore && tiers.length > 0;

  function selectPlan(code: string) {
    setSelected(code);
    document.getElementById("paketler")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function openSection(section: "ai" | "cancel") {
    setMoreOpen(true);
    if (section === "cancel") setCancelOpen(true);
    window.setTimeout(() => {
      document.getElementById(section === "ai" ? "yapay-zeka" : "diger")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }, 50);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 pb-28 pt-6 sm:px-6">
      <header>
        <h1 className="font-display text-2xl font-bold text-foreground">Paketim</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Paketin, ödemen ve yapay zekâ kredin tek yerde.
        </p>
      </header>

      {data.last_payment_issue ? (
        <PaymentIssueCard
          issue={data.last_payment_issue}
          canRetry={(() => {
            const t = tierBy(data.last_payment_issue.plan_code);
            return !!t && fits(t);
          })()}
          onRetry={() => {
            const i = data.last_payment_issue!;
            setCheckout({ plan: i.plan_code!, cycle: i.cycle === "academic_year" ? "academic_year" : "monthly" });
          }}
          onAsk={() => setAssistantOpen(true)}
        />
      ) : null}

      <StatusHero
        data={data}
        current={current}
        suggested={suggested}
        suggestedFits={!!suggested && fits(suggested)}
        onPay={(code) => setCheckout({ plan: code, cycle: "monthly" })}
        onSeePlans={() => selectPlan(suggested?.code ?? selected)}
      />

      {data.is_solo && (data.status === "trialing" || data.status === "active") && data.ai_credits_allocated > 0 ? (
        <CreditBlock data={data} />
      ) : null}

      {showPlans ? (
        <section id="paketler" className="scroll-mt-20 space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-display text-lg font-semibold text-foreground">
                {data.status === "active" ? "Yenile ya da büyüt" : "Paketler"}
              </h2>
              <p className="mt-0.5 text-sm text-muted-foreground">
                {n} aktif öğrencin var. Öğrenci sayına yetmeyen paket seçilemez.
              </p>
            </div>
            <CycleSwitch cycle={cycle} onChange={setCycle} months={months} />
          </div>

          <div className="grid gap-3 lg:grid-cols-3" role="radiogroup" aria-label="Paket seçimi">
            {visibleTiers.map((t) => (
              <TierOption
                key={t.code}
                tier={t}
                selected={t.code === selected}
                fits={fits(t)}
                studentCount={n}
                cycle={cycle}
                months={months}
                credits={catalog?.cards.find((c) => c.plan === t.code)?.credits_monthly ?? null}
                tag={
                  isPaidState && t.code === data.plan_code
                    ? "Mevcut paketin"
                    : !isPaidState && t.code === data.post_trial_plan
                      ? "Kayıtta seçtiğin"
                      : t.code === data.recommended_plan
                        ? "Öğrenci sayına uygun"
                        : null
                }
                onSelect={() => setSelected(t.code)}
              />
            ))}
          </div>

          <SelectedPlanPanel
            tier={tierBy(selected) ?? suggested}
            features={catalog?.plan_features?.[selected] ?? []}
            glossary={buildGlossaryMap(catalog?.feature_glossary)}
            cycle={cycle}
            months={months}
            isRenewal={isPaidState && selected === data.plan_code}
            disabled={!(tierBy(selected) && fits(tierBy(selected)!))}
            onPay={() => setCheckout({ plan: selected, cycle })}
          />
        </section>
      ) : null}

      <section id="diger" className="scroll-mt-20">
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          aria-expanded={moreOpen}
          className="flex w-full items-center justify-between rounded-2xl border border-border bg-card px-5 py-4 text-left transition hover:bg-muted/50"
        >
          <span>
            <span className="block text-sm font-semibold text-foreground">Diğer işlemler</span>
            <span className="block text-xs text-muted-foreground">
              Kredi dökümü, yapay zekâ onayı{data.status === "active" && !appStore ? ", aboneliği iptal" : ""}
            </span>
          </span>
          <ChevronDown className={cn("size-5 text-muted-foreground transition", moreOpen && "rotate-180")} aria-hidden />
        </button>
        {moreOpen ? (
          <div className="mt-4 space-y-4">
            <div id="yapay-zeka" className="scroll-mt-20 space-y-4">
              <AiUsageCard />
              <AiConsentCard />
            </div>
            {data.status === "active" && !appStore ? (
              <CancelBlock data={data} canceled={canceled} open={cancelOpen} onOpenChange={setCancelOpen} />
            ) : null}
            {appStore ? (
              <p className="rounded-2xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground">
                Aboneliğin App Store üzerinden. Paket değişikliği ve iptal için iPhone&apos;da
                <b className="text-foreground"> Ayarlar → Apple Kimliği → Abonelikler</b>.
              </p>
            ) : null}
            <a
              href="/pricing"
              className="flex items-center justify-between rounded-2xl border border-border bg-card px-5 py-4 text-sm font-medium text-foreground transition hover:bg-muted/50"
            >
              Tüm paketleri yan yana karşılaştır
              <ArrowRight className="size-4 text-muted-foreground" aria-hidden />
            </a>
          </div>
        ) : null}
      </section>

      <div className="flex items-start gap-3 rounded-2xl bg-muted/50 px-5 py-4">
        <MessageCircleQuestion className="mt-0.5 size-5 shrink-0 text-cyan-700 dark:text-cyan-400" aria-hidden />
        <p className="text-sm text-muted-foreground">
          Kafana takılan bir şey mi var?{" "}
          <button
            type="button"
            onClick={() => setAssistantOpen(true)}
            className="font-semibold text-cyan-800 underline-offset-2 hover:underline dark:text-cyan-300"
          >
            Paket asistanına sor
          </button>{" "}
          — hangi paketin uygun olduğunu, ödemenin neden geçmediğini, krediyi anında anlatır.
        </p>
      </div>

      <CheckoutDialog
        target={checkout}
        tier={checkout ? tierBy(checkout.plan) : undefined}
        months={months}
        data={data}
        onClose={() => setCheckout(null)}
        onAsk={() => {
          setCheckout(null);
          setAssistantOpen(true);
        }}
      />

      <PlanAssistant
        open={assistantOpen}
        onOpenChange={setAssistantOpen}
        onSelectPlan={selectPlan}
        onOpenSection={openSection}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Durum
// ---------------------------------------------------------------------------

function statusInfo(data: TeacherPlanResponse): { tone: Tone; label: string } {
  if (!data.is_solo || data.status === "managed") return { tone: "slate", label: "Kurum yönetiyor" };
  switch (data.status) {
    case "trialing":
      return { tone: "amber", label: `Deneme · ${data.trial_days_left ?? 0} gün kaldı` };
    case "active":
      return data.subscription_status === "canceled"
        ? { tone: "amber", label: "İptal edildi · dönem sonuna kadar açık" }
        : { tone: "emerald", label: "Aktif" };
    case "past_due":
      return { tone: "rose", label: "Süresi doldu" };
    case "payment_required":
      return { tone: "rose", label: "Ödeme bekleniyor" };
    default:
      return { tone: "slate", label: "Ücretsiz" };
  }
}

function StatusHero({
  data,
  current,
  suggested,
  suggestedFits,
  onPay,
  onSeePlans,
}: {
  data: TeacherPlanResponse;
  current: TeacherPlanOption | undefined;
  suggested: TeacherPlanOption | undefined;
  suggestedFits: boolean;
  onPay: (code: string) => void;
  onSeePlans: () => void;
}) {
  const qc = useQueryClient();
  const resume = useMutation({
    mutationFn: resumeSubscription,
    onSuccess: (res) => applyInvalidate(qc, res.invalidate),
  });
  const s = statusInfo(data);
  const tone = TONE[s.tone];
  const n = data.student_count;
  const appStore = data.subscription_platform === "app_store";
  const canceled = data.subscription_status === "canceled";
  const intended =
    data.post_trial_plan && data.post_trial_plan !== "solo_free" ? data.post_trial_plan_label : null;
  const freeLimit = data.options.find((o) => o.code === "solo_free")?.max_students ?? 3;

  const title =
    data.status === "trialing" && intended ? `${intended} denemesi` : data.plan_label;

  let sentence = "";
  if (!data.is_solo) sentence = data.note ?? "Paketin kurumun tarafından yönetilir.";
  else if (data.status === "trialing")
    sentence = `Denemen ${data.trial_days_left ?? 0} gün sonra bitiyor. Bitince ödeme yapmazsan ücretsiz pakete (${freeLimit} öğrenci, yapay zekâ kapalı) geçersin; verilerin silinmez.`;
  else if (data.status === "active" && appStore)
    sentence = "Aboneliğin App Store üzerinden kendiliğinden yenilenir.";
  else if (data.status === "active" && canceled)
    sentence = `İptal ettin. ${fmtDate(data.subscription_period_end)} tarihine kadar her şey açık, sonra ücretsiz pakete geçersin.`;
  else if (data.status === "active")
    sentence = `Her şey açık. Dönemin ${fmtDate(data.subscription_period_end)} tarihinde bitiyor; kartından kendiliğinden çekim yapılmaz, 3 gün önce hatırlatırız.`;
  else if (data.status === "past_due")
    sentence = `Süren ${fmtDate(data.subscription_period_end)} tarihinde doldu. Yenileyene kadar yeni program kuramazsın; öğrencilerin ve verilerin duruyor.`;
  else if (data.status === "payment_required")
    sentence = "Paketinin ödemesi tamamlanmamış görünüyor. Ödeyerek hemen aktive edebilirsin.";
  else if (intended)
    sentence = `Denemen bitti. Kayıtta ${intended} paketini seçmiştin; ödeyince kaldığın yerden tüm özelliklerle devam edersin.`;
  else
    sentence = `Ücretsiz pakettesin: ${freeLimit} öğrenciye kadar takip, yapay zekâ kapalı.${n > freeLimit ? ` ${n} öğrencin olduğu için yeni programlama kilitli.` : ""}`;

  // Kapasite: mevcut paketin sınırı
  const capText =
    data.status === "trialing"
      ? "denemede sınırsız"
      : current
        ? capLabel(current.max_students).toLowerCase()
        : data.status === "free"
          ? `${freeLimit} öğrenciye kadar`
          : "";
  const overCap = data.status === "free" && n > freeLimit;

  const aiOn = data.ai_premium && (data.status === "trialing" || data.status === "active");
  const aiLeft = Math.max(0, data.ai_credits_allocated - data.ai_credits_used);

  let dateLabel = "";
  let dateValue = "";
  if (data.status === "trialing") {
    dateLabel = "Deneme bitişi";
    dateValue = `${data.trial_days_left ?? 0} gün sonra`;
  } else if (data.status === "active") {
    dateLabel = canceled ? "Bitiş" : appStore ? "Yenileme" : "Dönem sonu";
    dateValue = data.subscription_period_end ? fmtDate(data.subscription_period_end) : "—";
  } else if (data.status === "past_due") {
    dateLabel = "Süre";
    dateValue = "Doldu";
  } else {
    dateLabel = "Ödeme";
    dateValue = data.status === "payment_required" ? "Bekleniyor" : "Yok";
  }

  // Tek ana eylem
  let primary: React.ReactNode = null;
  const renewalDue =
    data.status === "active" && !canceled && !appStore && (data.renewal_days_left ?? 99) <= 7;
  if (data.is_solo && !appStore) {
    if (["trialing", "free", "payment_required", "past_due"].includes(data.status) && suggested) {
      primary = suggestedFits ? (
        <Button
          size="lg"
          className="h-12 w-full bg-cyan-700 text-base text-white hover:bg-cyan-800 sm:w-auto"
          onClick={() => onPay(suggested.code)}
        >
          <CreditCard className="size-5" aria-hidden />
          {data.status === "past_due" ? `${suggested.label} paketini yenile` : `${suggested.label} ile devam et`}
          <span className="font-normal opacity-90">· {tl(suggested.price_monthly_try)}/ay</span>
        </Button>
      ) : null;
    } else if (renewalDue && current) {
      primary = (
        <Button
          size="lg"
          className="h-12 w-full bg-cyan-700 text-base text-white hover:bg-cyan-800 sm:w-auto"
          onClick={() => onPay(current.code)}
        >
          <CreditCard className="size-5" aria-hidden />
          Şimdi yenile · {data.renewal_days_left} gün kaldı
        </Button>
      );
    } else if (data.status === "active" && canceled) {
      primary = (
        <Button
          size="lg"
          className="h-12 w-full bg-cyan-700 text-base text-white hover:bg-cyan-800 sm:w-auto"
          disabled={resume.isPending}
          onClick={() => resume.mutate()}
        >
          {resume.isPending ? <Loader2 className="size-5 animate-spin" aria-hidden /> : null}
          İptali geri al
        </Button>
      );
    }
  }

  return (
    <section className={cn("rounded-3xl border-2 bg-card p-5 sm:p-7", tone.ring)} aria-label="Paket durumu">
      <span className={cn("inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold", tone.chip)}>
        <span className="size-1.5 rounded-full bg-white" aria-hidden />
        {s.label}
      </span>
      <h2 className="mt-3 font-display text-3xl font-bold text-foreground">{title}</h2>
      <p className="mt-2 text-base leading-relaxed text-muted-foreground">{sentence}</p>

      {data.is_solo ? (
        <dl className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Fact
            icon={<Users className="size-4" aria-hidden />}
            label="Öğrenci"
            value={`${n} aktif`}
            hint={capText}
            alert={overCap}
          />
          <Fact
            icon={<Sparkles className="size-4" aria-hidden />}
            label="Yapay zekâ"
            value={aiOn ? `${aiLeft.toLocaleString("tr-TR")} kredi` : "Kapalı"}
            hint={aiOn ? "bu ay kalan" : "ücretli pakette açılır"}
          />
          <Fact icon={<ShieldCheck className="size-4" aria-hidden />} label={dateLabel} value={dateValue} />
        </dl>
      ) : null}

      {primary ? <div className="mt-6 flex flex-wrap items-center gap-3">{primary}</div> : null}
      {primary && data.is_solo && !appStore && data.status !== "active" ? (
        <button
          type="button"
          onClick={onSeePlans}
          className="mt-3 text-sm font-medium text-cyan-800 underline-offset-2 hover:underline dark:text-cyan-300"
        >
          Diğer paketleri gör
        </button>
      ) : null}
    </section>
  );
}

function Fact({
  icon,
  label,
  value,
  hint,
  alert = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  alert?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-muted/50 px-4 py-3">
      <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className={cn("mt-1 text-lg font-semibold", alert ? "text-rose-700 dark:text-rose-400" : "text-foreground")}>
        {value}
      </dd>
      {hint ? <dd className="text-xs text-muted-foreground">{hint}</dd> : null}
    </div>
  );
}

function PaymentIssueCard({
  issue,
  canRetry,
  onRetry,
  onAsk,
}: {
  issue: NonNullable<TeacherPlanResponse["last_payment_issue"]>;
  canRetry: boolean;
  onRetry: () => void;
  onAsk: () => void;
}) {
  return (
    <section className="rounded-3xl bg-rose-600 p-5 text-white sm:p-6" role="alert">
      <p className="flex items-center gap-2 text-base font-semibold">
        <AlertTriangle className="size-5 shrink-0" aria-hidden />
        {issue.title}
      </p>
      <p className="mt-2 text-sm leading-relaxed text-rose-50">
        {issue.detail} Kartından para çekilmedi.
        {issue.plan_label ? ` Denediğin: ${issue.plan_label}.` : ""}
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {canRetry ? (
          <Button className="bg-white text-rose-700 hover:bg-rose-50" onClick={onRetry}>
            Tekrar dene
          </Button>
        ) : null}
        <Button variant="ghost" className="text-white hover:bg-white/15 hover:text-white" onClick={onAsk}>
          Asistana sor
        </Button>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Yapay zekâ kredisi
// ---------------------------------------------------------------------------

function CreditBlock({ data }: { data: TeacherPlanResponse }) {
  const used = data.ai_credits_used;
  const alloc = data.ai_credits_allocated;
  const left = Math.max(0, alloc - used);
  const pct = alloc > 0 ? Math.min(100, Math.round((used / alloc) * 100)) : 0;
  const tone: Tone = left === 0 ? "rose" : pct >= 80 ? "amber" : "emerald";
  const showPacks =
    data.status === "active" && data.subscription_platform !== "app_store" && pct >= 80;
  const intendedCredits =
    data.trial_active && data.post_trial_plan_credits ? data.post_trial_plan_credits : null;

  return (
    <section className="space-y-4" aria-label="Yapay zekâ kredisi">
      <div className="rounded-3xl border border-border bg-card p-5 sm:p-6">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-display text-lg font-semibold text-foreground">Yapay zekâ kredisi</h2>
          <p className="text-sm tabular-nums text-muted-foreground">
            <b className="text-foreground">{left.toLocaleString("tr-TR")}</b> / {alloc.toLocaleString("tr-TR")} kaldı
          </p>
        </div>
        <div className="mt-3 h-3 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Kullanılan kredi">
          <div className={cn("h-full rounded-full transition-all", TONE[tone].bar)} style={{ width: `${pct}%` }} />
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          {left === 0
            ? data.trial_active
              ? "Deneme kredin bitti. Paketini başlatınca aylık kredin hemen tanımlanır."
              : "Bu ayın kredisi bitti. Ay başında yenilenir; beklemek istemezsen aşağıdan ek kredi alabilirsin."
            : data.trial_active && intendedCredits
              ? `Denemede ${alloc} kredi var. Paketini başlatınca her ay ${intendedCredits.toLocaleString("tr-TR")} kredi gelir.`
              : "Karne okuma, veli yorumu, seans notu gibi yapay zekâ işlerinde harcanır; her ay başında yenilenir."}
        </p>
      </div>
      {showPacks ? <CreditPacks exhausted={left === 0} /> : null}
    </section>
  );
}

function CreditPacks({ exhausted }: { exhausted: boolean }) {
  const providerQ = useQuery({
    queryKey: paymentKeys.providerStatus(),
    queryFn: getPaymentProviderStatus,
    staleTime: 5 * 60_000,
  });
  const pricingQ = useQuery({ queryKey: pricingKeys.catalog(), queryFn: getPricingCatalog, staleTime: 5 * 60_000 });
  const buy = useInitCreditPackCheckout();
  const [buying, setBuying] = React.useState<string | null>(null);
  const packs = pricingQ.data?.credit_packs ?? [];
  if (providerQ.data?.available !== true || packs.length === 0) return null;
  return (
    <div className="rounded-3xl border-2 border-amber-500/40 bg-card p-5 sm:p-6">
      <h3 className="text-base font-semibold text-foreground">
        {exhausted ? "Ek kredi al, hemen devam et" : "Kredin azalıyor"}
      </h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Tek seferlik ödeme. Ek kredi ay sonunda yanmaz, kullanılana kadar durur.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {packs.map((p) => (
          <button
            key={p.code}
            type="button"
            disabled={buy.isPending}
            onClick={() => {
              setBuying(p.code);
              buy.mutate(
                { pack_code: p.code },
                {
                  onSuccess: (res) => {
                    window.location.href = res.payment_page_url;
                  },
                  onError: () => setBuying(null),
                },
              );
            }}
            className="flex items-center justify-between rounded-2xl border border-border bg-background px-4 py-3 text-left transition hover:border-cyan-600 disabled:opacity-60"
          >
            <span>
              <span className="block text-lg font-bold text-foreground">+{p.credits.toLocaleString("tr-TR")}</span>
              <span className="block text-xs text-muted-foreground">kredi</span>
            </span>
            <span className="text-sm font-semibold text-cyan-800 dark:text-cyan-300">
              {buying === p.code && buy.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : tl(p.price)}
            </span>
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Her ay yetmiyorsa bir üst paket genelde daha avantajlıdır.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. Paketler
// ---------------------------------------------------------------------------

function CycleSwitch({ cycle, onChange, months }: { cycle: Cycle; onChange: (c: Cycle) => void; months: number }) {
  const opt = (c: Cycle, label: React.ReactNode) => (
    <button
      type="button"
      role="radio"
      aria-checked={cycle === c}
      onClick={() => onChange(c)}
      className={cn(
        "rounded-full px-4 py-2 text-sm font-semibold transition",
        cycle === c ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {label}
    </button>
  );
  return (
    <div className="inline-flex rounded-full border border-border bg-muted/50 p-1" role="radiogroup" aria-label="Ödeme dönemi">
      {opt("monthly", "Aylık")}
      {opt("academic_year", <>Akademik yıl · {12 - months} ay bedava</>)}
    </div>
  );
}

function TierOption({
  tier,
  selected,
  fits,
  studentCount,
  cycle,
  months,
  credits,
  tag,
  onSelect,
}: {
  tier: TeacherPlanOption;
  selected: boolean;
  fits: boolean;
  studentCount: number;
  cycle: Cycle;
  months: number;
  credits: number | null;
  tag: string | null;
  onSelect: () => void;
}) {
  const monthly = cycle === "academic_year" ? (tier.price_monthly_try * months) / 12 : tier.price_monthly_try;
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={!fits}
      onClick={onSelect}
      className={cn(
        "relative flex w-full items-start gap-3 rounded-2xl border-2 bg-card p-4 text-left transition sm:p-5",
        selected ? "border-cyan-600 shadow-md" : "border-border hover:border-cyan-600/50",
        !fits && "cursor-not-allowed opacity-60 hover:border-border",
      )}
    >
      <span
        className={cn(
          "mt-1 flex size-5 shrink-0 items-center justify-center rounded-full border-2",
          selected ? "border-cyan-600 bg-cyan-600" : "border-muted-foreground/40",
        )}
        aria-hidden
      >
        {selected ? <Check className="size-3 text-white" /> : null}
      </span>
      <span className="min-w-0 flex-1">
        {tag ? (
          <span className="mb-1.5 inline-block rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-semibold text-white">
            {tag}
          </span>
        ) : null}
        <span className="block font-display text-lg font-bold text-foreground">{tier.label}</span>
        <span className="block text-sm text-muted-foreground">{capLabel(tier.max_students)}</span>
        <span className="mt-2 block">
          <span className="text-2xl font-bold text-foreground">{tl(monthly)}</span>
          <span className="text-sm text-muted-foreground"> /ay</span>
        </span>
        {credits ? (
          <span className="mt-1 block text-sm text-muted-foreground">
            Ayda {credits.toLocaleString("tr-TR")} yapay zekâ kredisi
          </span>
        ) : null}
        {!fits ? (
          <span className="mt-2 block text-xs font-medium text-rose-700 dark:text-rose-400">
            {studentCount} öğrencine yetmiyor
          </span>
        ) : null}
      </span>
    </button>
  );
}

function SelectedPlanPanel({
  tier,
  features,
  glossary,
  cycle,
  months,
  isRenewal,
  disabled,
  onPay,
}: {
  tier: TeacherPlanOption | undefined;
  features: string[];
  glossary: ReturnType<typeof buildGlossaryMap>;
  cycle: Cycle;
  months: number;
  isRenewal: boolean;
  disabled: boolean;
  onPay: () => void;
}) {
  if (!tier) return null;
  const total = cycle === "academic_year" ? tier.price_monthly_try * months : tier.price_monthly_try;
  return (
    <div className="rounded-3xl bg-muted/50 p-5 sm:p-6">
      <h3 className="text-base font-semibold text-foreground">{tier.label} paketinde neler var?</h3>
      {features.length ? (
        <ul className="mt-3 space-y-2.5">
          {features.map((f) => (
            <li key={f} className="flex items-start gap-2.5 text-sm">
              <Check className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden />
              <FeatureLine text={f} glossary={glossary} tone="theme" />
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-5 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          {cycle === "academic_year" ? "Akademik yıl, tek ödeme" : "Aylık ödeme"}:{" "}
          <b className="text-lg text-foreground">{tl(total)}</b>
        </p>
        <Button
          size="lg"
          disabled={disabled}
          onClick={onPay}
          className="h-12 w-full bg-cyan-700 text-base text-white hover:bg-cyan-800 sm:w-auto"
        >
          <CreditCard className="size-5" aria-hidden />
          {isRenewal ? "Yenile — kartla öde" : `${tier.label} — kartla öde`}
        </Button>
      </div>
    </div>
  );
}

function CheckoutDialog({
  target,
  tier,
  months,
  data,
  onClose,
  onAsk,
}: {
  target: { plan: string; cycle: Cycle } | null;
  tier: TeacherPlanOption | undefined;
  months: number;
  data: TeacherPlanResponse;
  onClose: () => void;
  onAsk: () => void;
}) {
  const open = target != null && tier != null;
  const providerQ = useQuery({
    queryKey: paymentKeys.providerStatus(),
    queryFn: getPaymentProviderStatus,
    staleTime: 60_000,
    enabled: open,
  });
  const pay = useInitPaymentCheckout();
  if (!target || !tier) return null;
  const yearly = target.cycle === "academic_year";
  const total = yearly ? tier.price_monthly_try * months : tier.price_monthly_try;
  const days = yearly ? 365 : 30;
  const extends_ =
    (data.subscription_status === "active" || data.subscription_status === "canceled") &&
    data.subscription_period_end &&
    new Date(data.subscription_period_end) > new Date();
  const available = providerQ.data?.available === true;
  const err = pay.error instanceof ApiError ? pay.error.message : pay.error ? "Ödeme sayfası açılamadı." : null;

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-display text-xl">Ödemeyi onayla</DialogTitle>
          <DialogDescription>Kart bilgilerini bir sonraki adımda iyzico&apos;nun güvenli sayfasına gireceksin.</DialogDescription>
        </DialogHeader>
        <dl className="divide-y divide-border rounded-2xl border border-border">
          <Row label="Paket" value={`${tier.label} · ${capLabel(tier.max_students).toLowerCase()}`} />
          <Row label="Dönem" value={yearly ? `Akademik yıl (${months} ay ödenir)` : "1 ay"} />
          <Row
            label="Başlangıç"
            value={extends_ ? `Mevcut dönemin bitişinden sonra (${days} gün eklenir)` : "Ödeme onaylanınca hemen"}
          />
          <Row label="Tutar" value={tl(total)} strong />
        </dl>
        <p className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
          3D Secure ile korunur; kart bilgin bize gelmez. Kendiliğinden yenileme yoktur.
          {providerQ.data?.sandbox ? " (Test modu)" : ""}
        </p>
        {!available && !providerQ.isLoading ? (
          <p className="rounded-xl bg-amber-500 px-3 py-2 text-sm text-white">
            Kartlı ödeme şu an kullanılamıyor. Biraz sonra tekrar dene ya da asistandan bize yaz.
          </p>
        ) : null}
        {err ? <p className="rounded-xl bg-rose-600 px-3 py-2 text-sm text-white">{err}</p> : null}
        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="ghost" onClick={onAsk}>
            Soru sor
          </Button>
          <Button
            className="h-11 bg-cyan-700 text-white hover:bg-cyan-800"
            disabled={!available || pay.isPending}
            onClick={() =>
              pay.mutate(
                { plan_code: tier.code, cycle: yearly ? "annual" : "monthly" },
                {
                  onSuccess: (res) => {
                    window.location.href = res.payment_page_url;
                  },
                },
              )
            }
          >
            {pay.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <CreditCard className="size-4" aria-hidden />}
            {tl(total)} öde
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-3 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("text-right", strong ? "text-lg font-bold text-foreground" : "font-medium text-foreground")}>
        {value}
      </dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. İptal
// ---------------------------------------------------------------------------

function CancelBlock({
  data,
  canceled,
  open,
  onOpenChange,
}: {
  data: TeacherPlanResponse;
  canceled: boolean;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const [reason, setReason] = React.useState("");
  const [note, setNote] = React.useState("");
  const cancel = useMutation({
    mutationFn: () =>
      cancelSubscription(reason || note.trim() ? { reason_code: reason || null, note: note.trim() || null } : undefined),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      onOpenChange(false);
    },
  });
  if (canceled) {
    return (
      <p className="rounded-2xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground">
        Aboneliğin iptal edildi; {fmtDate(data.subscription_period_end)} tarihine kadar açık. Geri almak için
        sayfanın üstündeki <b className="text-foreground">İptali geri al</b> düğmesini kullan.
      </p>
    );
  }
  return (
    <div className="rounded-2xl border border-border bg-card px-5 py-4">
      <p className="text-sm font-semibold text-foreground">Aboneliği iptal et</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Dönem sonuna kadar her şey açık kalır, sonra ücretsiz pakete geçersin. Öğrencilerin ve verilerin silinmez.
      </p>
      <Button
        variant="outline"
        className="mt-3 border-rose-600/50 text-rose-700 hover:bg-rose-50 dark:text-rose-300 dark:hover:bg-rose-500/10"
        onClick={() => onOpenChange(true)}
      >
        İptal et
      </Button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aboneliği iptal et</DialogTitle>
            <DialogDescription>
              {fmtDate(data.subscription_period_end)} tarihine kadar her şey açık kalır. İstersen sonra geri alabilirsin.
            </DialogDescription>
          </DialogHeader>
          <fieldset className="space-y-1">
            <legend className="mb-1 text-sm font-medium text-foreground">
              Neden ayrılıyorsun? <span className="font-normal text-muted-foreground">(isteğe bağlı)</span>
            </legend>
            {[
              ["price", "Fiyat yüksek geldi"],
              ["usage", "Yeterince kullanmadım"],
              ["missing_feature", "İhtiyacım olan bir özellik yok"],
              ["season_break", "Dönem bitti, ara veriyorum"],
              ["student_drop", "Öğrenci sayım azaldı"],
              ["other", "Başka bir neden"],
            ].map(([code, label]) => (
              <label key={code} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm text-foreground hover:bg-muted/60">
                <input
                  type="radio"
                  name="cancel-reason"
                  checked={reason === code}
                  onChange={() => setReason(code)}
                  className="size-4 accent-cyan-700"
                />
                {label}
              </label>
            ))}
          </fieldset>
          {reason ? (
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Eklemek istediğin bir şey var mı?"
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
            />
          ) : null}
          <DialogFooter className="gap-2">
            <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={cancel.isPending}>
              Vazgeç
            </Button>
            <Button className="bg-rose-600 text-white hover:bg-rose-700" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
              {cancel.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              İptal et
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
