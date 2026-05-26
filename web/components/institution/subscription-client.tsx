"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  Clock,
  Gem,
  HelpCircle,
  Loader2,
  Pause,
  Play,
  ShieldCheck,
  Sparkles,
  Sun,
} from "lucide-react";

import { cn } from "@/lib/utils";
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
  getInstitutionSubscription,
  institutionKeys,
} from "@/lib/api/institution";
import {
  useEnableGuarantee,
  usePauseForSummer,
  useRequestInstitutionUpgrade,
  useResumeFromPause,
  useSwitchAcademicYear,
} from "@/lib/hooks/use-institution-mutations";
import type {
  GuaranteeEvaluationInfo,
  InstitutionPlanOption,
  SubscriptionResponse,
  SubscriptionStatusInfo,
} from "@/lib/types/institution";

interface Props {
  initial: SubscriptionResponse;
}

/**
 * Abonelik durumu — Jinja `subscription.html` ile feature parity.
 *
 * Görsel yaklaşım fresh shadcn — Jinja'daki üst-üste panel/promo/pause/guarantee
 * yerine 4 modüler kart + sidebar avantajlar/yardım. Her aksiyon dialog
 * confirmation ile, Jinja onConfirm metinleri birebir.
 */
export function SubscriptionClient({ initial }: Props) {
  const q = useQuery<SubscriptionResponse>({
    queryKey: institutionKeys.subscription(),
    queryFn: () => getInstitutionSubscription(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const { status, guarantee_evaluation, plan, plan_label, institution } = data;

  return (
    <div className="space-y-6">
      <header>
        <Link
          href="/institution"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <p className="text-[11px] uppercase tracking-wider text-emerald-700 mt-1 font-semibold">
          Üyelik
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-0.5 flex items-center gap-2">
          <CalendarDays className="size-6 text-emerald-700" aria-hidden />
          Abonelik Yönetimi
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          {institution.name} kurumunun mevcut planı{" "}
          <strong className="text-foreground">{plan_label || plan}</strong> — burada
          planını yükseltmek için talep gönderebilir; akademik yıl planına geçiş,
          yaz pause modu ve 60 gün performans garantisini yönetebilirsin.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-5">
          <UpgradeRequestCard data={data} />
          <CurrentStatusCard status={status} plan={plan_label || plan} />
          {status.can_switch_to_academic_year && <AcademicYearPromoCard />}
          {(status.kind === "academic_year" || status.kind === "paused") && (
            <SummerPauseCard status={status} />
          )}
          <GuaranteeCard
            status={status}
            evaluation={guarantee_evaluation}
          />
        </div>

        <aside className="space-y-5">
          <AdvantagesCard />
          <HelpCard />
        </aside>
      </div>
    </div>
  );
}

// ============================================================================
// Plan yükseltme talebi (satın alma DEĞİL — süper admine sinyal)
// ============================================================================

function UpgradeRequestCard({ data }: { data: SubscriptionResponse }) {
  const mut = useRequestInstitutionUpgrade();
  const [open, setOpen] = React.useState(false);
  const [selected, setSelected] = React.useState<string>(
    data.available_plans[0]?.code ?? "",
  );
  const [note, setNote] = React.useState("");

  const pending = data.pending_upgrade_request;

  function submit() {
    mut.mutate(
      { plan: selected || null, note: note.trim() || null },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <Card className="overflow-hidden border-cyan-200">
      <div className="h-1 w-full bg-gradient-to-r from-cyan-600 to-cyan-800" aria-hidden />
      <CardContent className="space-y-4 p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
            <Gem className="size-5" aria-hidden />
          </span>
          <div>
            <h2 className="font-display text-lg font-bold">Planını yükselt</h2>
            <p className="text-sm text-muted-foreground">
              Daha fazla öğretmen ve öğrenci kapasitesi için paketini yükselt.
              Bu bir <strong className="text-foreground">satın alma değil</strong> —
              talebini iletirsin, ekibimiz seninle iletişime geçip kuruluma yardımcı olur.
            </p>
          </div>
        </div>

        {pending ? (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
            <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              <strong>Talebin alındı.</strong>{" "}
              {data.requested_plan_label && data.requested_plan_label !== "Belirtilmedi"
                ? `Hedef paket: ${data.requested_plan_label}. `
                : ""}
              Ekibimiz en kısa sürede seninle iletişime geçecek.
            </span>
          </div>
        ) : (
          <>
            {/* Kademe seçici */}
            <div className="grid gap-2 sm:grid-cols-3">
              {data.available_plans.map((p) => {
                const isSel = p.code === selected;
                return (
                  <button
                    key={p.code}
                    type="button"
                    onClick={() => setSelected(p.code)}
                    className={cn(
                      "rounded-xl border p-3 text-left transition",
                      isSel
                        ? "border-cyan-600 bg-cyan-50 ring-1 ring-cyan-600"
                        : "border-slate-200 bg-white hover:border-cyan-300",
                    )}
                  >
                    <p className="text-sm font-bold text-slate-900">{p.label}</p>
                    <p className="text-xs text-slate-600">{p.coaches}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{p.price_label}</p>
                  </button>
                );
              })}
            </div>
            <Button
              className="w-full bg-cyan-700 text-white hover:bg-cyan-800"
              onClick={() => setOpen(true)}
            >
              Yükseltme talebi gönder
            </Button>
          </>
        )}
      </CardContent>

      <Dialog open={open} onOpenChange={(v) => { if (!mut.isPending) setOpen(v); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Gem className="size-4 text-cyan-700" aria-hidden /> Plan yükseltme talebi
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <PlanOptionSummary options={data.available_plans} selected={selected} />
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Not (opsiyonel)
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Örn. 8 öğretmenimiz var, eylülde 4 yeni koç ekleyeceğiz."
                className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
              />
            </div>
            <p className="flex items-start gap-2 text-muted-foreground">
              <Clock className="mt-0.5 size-4 shrink-0" aria-hidden />
              Talep süper admin ekibine iletilir; ödeme/aktivasyon manuel yapılır.
            </p>
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button
              className="bg-cyan-700 text-white hover:bg-cyan-800"
              onClick={submit}
              disabled={mut.isPending}
            >
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Talebi gönder
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function PlanOptionSummary({
  options,
  selected,
}: {
  options: InstitutionPlanOption[];
  selected: string;
}) {
  const sel = options.find((o) => o.code === selected);
  if (!sel) return null;
  return (
    <div className="rounded-lg border border-cyan-200 bg-cyan-50/60 p-3">
      <span className="text-muted-foreground">Seçilen kademe:</span>{" "}
      <span className="font-semibold text-cyan-900">{sel.label}</span>{" "}
      <span className="text-cyan-800">· {sel.coaches} · {sel.price_label}</span>
    </div>
  );
}

// ============================================================================
// Mevcut abonelik durumu
// ============================================================================

function CurrentStatusCard({
  status,
  plan,
}: {
  status: SubscriptionStatusInfo;
  plan: string;
}) {
  return (
    <Card>
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
              Mevcut Plan
            </p>
            <h2 className="text-lg font-semibold mt-0.5">{plan}</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Abonelik türü:{" "}
              <span className="font-medium text-foreground">{status.kind_label}</span>
            </p>
          </div>
          <KindBadge kind={status.kind} />
        </div>

        <dl className="grid grid-cols-2 gap-4 pt-3 border-t border-border text-sm">
          <DefinitionItem
            label="Dönem sonu"
            value={
              status.period_end ? (
                <>
                  <span className="font-medium">
                    {formatDateOnly(status.period_end)}
                  </span>
                  {status.days_until_period_end != null && (
                    <span className="text-muted-foreground ml-1">
                      ({status.days_until_period_end} gün kaldı)
                    </span>
                  )}
                </>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            }
          />
          <DefinitionItem
            label="Pause dönüş"
            value={
              status.pause_until ? (
                <span className="font-medium">
                  {formatDateOnly(status.pause_until)}
                </span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            }
          />
          <DefinitionItem
            label="60 Gün Garanti"
            value={
              status.performance_guarantee ? (
                <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                  <CheckCircle2 className="size-3.5" aria-hidden />
                  Aktif
                </span>
              ) : (
                <span className="text-muted-foreground">Pasif</span>
              )
            }
          />
          <DefinitionItem
            label="Garanti uzatma"
            value={
              status.guarantee_extended_at ? (
                <span className="text-amber-700 font-medium">
                  {formatDateOnly(status.guarantee_extended_at)} (uzatıldı)
                </span>
              ) : (
                <span className="text-muted-foreground">—</span>
              )
            }
          />
        </dl>
      </CardContent>
    </Card>
  );
}

function KindBadge({ kind }: { kind: SubscriptionStatusInfo["kind"] }) {
  const tone =
    kind === "academic_year"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : kind === "paused"
        ? "bg-sky-50 text-sky-700 border-sky-200"
        : "bg-slate-100 text-slate-700 border-slate-200";
  const label =
    kind === "academic_year"
      ? "Akademik Yıl"
      : kind === "paused"
        ? "Pause Modu"
        : "Aylık";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border",
        tone,
      )}
    >
      {kind === "academic_year" && <CheckCircle2 className="size-3" aria-hidden />}
      {kind === "paused" && <Pause className="size-3" aria-hidden />}
      {kind === "monthly" && <CalendarDays className="size-3" aria-hidden />}
      {label}
    </span>
  );
}

function DefinitionItem({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wider text-muted-foreground mb-0.5">
        {label}
      </dt>
      <dd className="text-sm">{value}</dd>
    </div>
  );
}

// ============================================================================
// Akademik yıl planına geçiş promosyonu
// ============================================================================

function AcademicYearPromoCard() {
  const [open, setOpen] = React.useState(false);
  const mut = useSwitchAcademicYear();

  function confirm() {
    mut.mutate(undefined, {
      onSettled: () => setOpen(false),
    });
  }

  return (
    <Card className="border-emerald-200 bg-emerald-50/40">
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-emerald-100 p-2">
            <Sparkles className="size-5 text-emerald-700" aria-hidden />
          </div>
          <div className="flex-1 space-y-2">
            <h3 className="text-base font-semibold">
              Akademik Yıl Planına Geçin
            </h3>
            <p className="text-sm text-muted-foreground">
              Eylül-Haziran 10 ay peşin ödeme karşılığında <b>12 ay erişim</b>{" "}
              alırsınız — Temmuz-Ağustos için yaz pause modu opsiyonu. Aylıkla
              karşılaştırıldığında <b>yıllık 2 ay tasarruf</b>.
            </p>
            <Button
              size="sm"
              onClick={() => setOpen(true)}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <ArrowUpRight className="size-4" aria-hidden />
              Akademik Yıl Planına Geç
            </Button>
          </div>
        </div>
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Akademik yıl planına geçiş</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Akademik yıl planına geçişi onaylıyor musunuz?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={confirm}
              disabled={mut.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ArrowUpRight className="size-4" aria-hidden />
              )}
              Onayla & Geç
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ============================================================================
// Yaz pause modu
// ============================================================================

function SummerPauseCard({ status }: { status: SubscriptionStatusInfo }) {
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <h3 className="text-base font-semibold flex items-center gap-2">
          <Sun className="size-5 text-amber-600" aria-hidden />
          Yaz Pause Modu
        </h3>
        <p className="text-sm text-muted-foreground">
          Temmuz-Ağustos boyunca aboneliğinizi <b>pause moduna</b> alabilirsiniz.
          Bu sürede aylık ücretin sadece <b>%20&apos;si saklama ücreti</b>
          olarak tahsil edilir. Yapay zeka, e-posta ve WhatsApp özellikleri
          kapanır; ders verisi korunur. <b>31 Ağustos sonunda otomatik</b>{" "}
          olarak akademik yıl planına geri döner.
        </p>

        {status.can_pause && <PauseAction />}
        {status.can_resume && <ResumeAction />}
        {!status.can_pause && !status.can_resume && (
          <PauseHelpline status={status} />
        )}
      </CardContent>
    </Card>
  );
}

function PauseHelpline({ status }: { status: SubscriptionStatusInfo }) {
  if (status.kind !== "academic_year") {
    return (
      <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
        <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
        <span>
          Pause moduna geçmek için <b>akademik yıl planında</b> olmanız gerekir.
        </span>
      </div>
    );
  }
  if (!status.in_summer_window) {
    return (
      <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900 flex items-start gap-2">
        <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
        <span>
          Pause moduna <b>sadece Temmuz-Ağustos</b> penceresinde geçilebilir.
        </span>
      </div>
    );
  }
  return null;
}

function PauseAction() {
  const [open, setOpen] = React.useState(false);
  const mut = usePauseForSummer();
  function confirm() {
    mut.mutate(undefined, { onSettled: () => setOpen(false) });
  }
  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpen(true)}
        className="border-amber-300 text-amber-900 hover:bg-amber-50"
      >
        <Pause className="size-4" aria-hidden />
        Yaz Pause Moduna Geç
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yaz pause moduna geçiş</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Yaz pause moduna geçişi onaylıyor musunuz? 31 Ağustos sonuna kadar
            geçerli olur.
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button onClick={confirm} disabled={mut.isPending}>
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Pause className="size-4" aria-hidden />
              )}
              Pause Moduna Geç
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function ResumeAction() {
  const [open, setOpen] = React.useState(false);
  const mut = useResumeFromPause();
  function confirm() {
    mut.mutate(undefined, { onSettled: () => setOpen(false) });
  }
  return (
    <>
      <Button
        size="sm"
        onClick={() => setOpen(true)}
        className="bg-emerald-600 hover:bg-emerald-700 text-white"
      >
        <Play className="size-4" aria-hidden />
        Pause&apos;dan Çık (Akademik Yıla Dön)
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Pause&apos;dan çıkış</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Pause modundan çıkıp akademik yıl planına geri dönmeyi onaylıyor
            musunuz?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={confirm}
              disabled={mut.isPending}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Play className="size-4" aria-hidden />
              )}
              Akademik Yıla Dön
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================================
// 60 Gün Performans Garantisi
// ============================================================================

function GuaranteeCard({
  status,
  evaluation,
}: {
  status: SubscriptionStatusInfo;
  evaluation: GuaranteeEvaluationInfo;
}) {
  const thresholdPct = Math.round(evaluation.threshold * 100);
  return (
    <Card>
      <CardContent className="p-5 space-y-3">
        <h3 className="text-base font-semibold flex items-center gap-2">
          <ShieldCheck className="size-5 text-indigo-700" aria-hidden />
          60 Gün Performans Garantisi
        </h3>
        <p className="text-sm text-muted-foreground">
          Plana başlangıçtan itibaren <b>60 gün boyunca</b> kurum geneli koçluk
          verimini ölçeriz. Haftalık tamamlama oranı{" "}
          <b className="text-foreground">%{thresholdPct}</b> eşiğinin altındaysa
          aboneliğinize otomatik <b>1 ay uzatma</b> uygulanır. Garanti tek
          seferliktir.
        </p>

        {!status.performance_guarantee ? (
          <GuaranteeEnableAction />
        ) : (
          <GuaranteeDetails evaluation={evaluation} thresholdPct={thresholdPct} />
        )}
      </CardContent>
    </Card>
  );
}

function GuaranteeEnableAction() {
  const [open, setOpen] = React.useState(false);
  const mut = useEnableGuarantee();
  function confirm() {
    mut.mutate(undefined, { onSettled: () => setOpen(false) });
  }
  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <ShieldCheck className="size-4" aria-hidden />
        60 Gün Garantiyi Aktive Et
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>60 gün performans garantisi</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            60 gün performans garantisini aktive etmek istiyor musunuz? Tek
            seferliktir; başlangıç tarihinden 60 gün sonra koçluk verimi eşiğin
            altında ise 1 ay uzatma uygulanır.
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button onClick={confirm} disabled={mut.isPending}>
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ShieldCheck className="size-4" aria-hidden />
              )}
              Aktive Et
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function GuaranteeDetails({
  evaluation,
  thresholdPct,
}: {
  evaluation: GuaranteeEvaluationInfo;
  thresholdPct: number;
}) {
  const totalDays = evaluation.period_total_days || 60;
  const ratePct =
    evaluation.average_completion_rate != null
      ? Math.round(evaluation.average_completion_rate * 100)
      : null;
  const daysPct =
    evaluation.days_into_period != null
      ? Math.min(100, Math.round((evaluation.days_into_period / totalDays) * 100))
      : 0;
  const remaining =
    evaluation.days_into_period != null
      ? Math.max(0, totalDays - evaluation.days_into_period)
      : 0;
  const above = ratePct != null && ratePct >= thresholdPct;
  const delta = ratePct == null ? null : ratePct - thresholdPct;
  const fmt = (n: number) => new Intl.NumberFormat("tr-TR").format(n);
  const planned = evaluation.total_planned_questions;
  const completed = evaluation.total_completed_questions;

  return (
    <div className="space-y-3">
      {/* Değerlendirme dönemi — başlangıç + ilerleyiş bar + kalan */}
      <div className="rounded-md border border-border bg-muted/40 p-3 space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
          <span className="text-muted-foreground">Değerlendirme dönemi</span>
          <span>
            {evaluation.period_started_at && (
              <span className="font-medium">
                {formatDateOnly(evaluation.period_started_at)}
              </span>
            )}
            {evaluation.days_into_period != null && (
              <>
                <span className="text-muted-foreground"> · </span>
                <span className="font-medium">
                  {evaluation.days_into_period}/{totalDays} gün
                </span>
                {remaining > 0 && (
                  <span className="text-muted-foreground"> · {remaining} gün kaldı</span>
                )}
              </>
            )}
          </span>
        </div>
        <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
          <div className="h-full bg-indigo-500" style={{ width: `${daysPct}%` }} />
        </div>
      </div>

      {/* Eşik vs Mevcut — büyük + delta */}
      <div className="grid grid-cols-2 gap-3 rounded-md border border-border bg-background p-3">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Eşik (tetik altı)
          </div>
          <div className="mt-0.5 text-2xl font-bold tabular-nums">%{thresholdPct}</div>
          <div className="text-[11px] text-muted-foreground">
            Bu rakamın altındaysa 1 ay uzatma hakkı
          </div>
        </div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Şu anki tamamlama
          </div>
          <div
            className={cn(
              "mt-0.5 text-2xl font-bold tabular-nums",
              ratePct == null
                ? "text-muted-foreground"
                : above
                  ? "text-emerald-700"
                  : "text-rose-700",
            )}
          >
            {ratePct == null ? "—" : `%${ratePct}`}
          </div>
          {delta != null && (
            <div className={cn(
              "text-[11px]",
              above ? "text-emerald-700" : "text-rose-700",
            )}>
              eşikten {above ? "+" : ""}{delta} puan {above ? "yukarıda" : "aşağıda"}
            </div>
          )}
        </div>
      </div>

      {/* Açık breakdown — hesabı doğrulayabilesin diye */}
      <div className="rounded-md border border-dashed border-border bg-muted/30 p-3 text-xs space-y-1">
        <div className="font-medium text-foreground">Hesap nasıl yapıldı?</div>
        <div className="text-muted-foreground">
          Periyot içinde yayınlanmış tüm görevlerin <b>soru bazında</b> oranı
          (Program Uyum Panosu ile aynı metrik):
        </div>
        <div className="grid grid-cols-3 gap-2 pt-1">
          <span><b className="tabular-nums">{evaluation.student_count}</b> aktif öğrenci</span>
          <span><b className="tabular-nums">{fmt(planned)}</b> soru planlandı</span>
          <span><b className="tabular-nums">{fmt(completed)}</b> tamamlandı</span>
        </div>
        {planned > 0 && (
          <div className="text-muted-foreground pt-0.5">
            = <b className="tabular-nums">{fmt(completed)} / {fmt(planned)}</b>
            {" "}× 100 = <b>%{ratePct ?? 0}</b>
          </div>
        )}
      </div>

      {/* Durum banner — provisional / triggered / safe / extended */}
      {evaluation.already_extended ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
          <CheckCircle2 className="size-4 shrink-0 mt-0.5" aria-hidden />
          <span>
            Garanti uzatması <b>uygulandı</b>. Tek seferlik bir hak; tekrar tetiklenmez.
          </span>
        </div>
      ) : evaluation.is_provisional ? (
        <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900 flex items-start gap-2">
          <CheckCircle2 className="size-4 shrink-0 mt-0.5" aria-hidden />
          <span>
            <b>İlerleyiş izleme.</b> Resmi değerlendirme 60. günde yapılır
            ({remaining} gün kaldı). Yukarıdaki oran şu ANKİ ilerleyişin.
            {ratePct != null && above && " Eşiğin üstündesin — şimdilik uzatma hakkı oluşmadı."}
            {ratePct != null && !above && " Şu an eşik altında; 60. gün böyle kalırsa otomatik uzatma uygulanır."}
          </span>
        </div>
      ) : evaluation.triggered ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
          <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
          <span>
            <b>Tamamlama eşiğin altında.</b> Sistem otomatik 1 ay uzatma
            uygulayacak (cron Pazartesi 06:00 UTC).
          </span>
        </div>
      ) : (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 flex items-start gap-2">
          <CheckCircle2 className="size-4 shrink-0 mt-0.5" aria-hidden />
          <span>
            <b>Hedef yakalandı.</b> Tamamlama %{ratePct} (eşik %{thresholdPct})
            — uzatma hakkı oluşmadı.
          </span>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Sidebar — avantajlar + yardım
// ============================================================================

function AdvantagesCard() {
  const items = [
    "Eylül-Haziran 10 ay peşin ödeme — 12 ay erişim",
    "Yaz dönemi Temmuz-Ağustos pause: sadece %20 saklama ücreti",
    "60 gün performans garantisi — eşik altında 1 ay otomatik uzatma",
    "Kurum genelinde tek faturada birleşik takip",
  ];
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
          <Sparkles className="size-4 text-emerald-700" aria-hidden />
          Akademik Yıl Avantajları
        </h3>
        <ul className="space-y-2 text-sm text-muted-foreground">
          {items.map((it) => (
            <li key={it} className="flex items-start gap-2">
              <CheckCircle2
                className="size-4 text-emerald-600 shrink-0 mt-0.5"
                aria-hidden
              />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function HelpCard() {
  return (
    <Card>
      <CardContent className="p-5">
        <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
          <HelpCircle className="size-4 text-muted-foreground" aria-hidden />
          Yardım
        </h3>
        <ul className="space-y-2 text-sm">
          <li>
            <a
              href="/pricing"
              className="text-sky-700 hover:underline inline-flex items-center gap-1"
            >
              Fiyatlandırma sayfası
              <ArrowUpRight className="size-3" aria-hidden />
            </a>
          </li>
          <li>
            <a
              href="/plans/me"
              className="text-sky-700 hover:underline inline-flex items-center gap-1"
            >
              Mevcut plan detayları
              <ArrowUpRight className="size-3" aria-hidden />
            </a>
          </li>
          <li>
            <a
              href="mailto:destek@etutkoc.com"
              className="text-sky-700 hover:underline"
            >
              destek@etutkoc.com
            </a>
          </li>
        </ul>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Yardımcılar
// ============================================================================

function formatDateOnly(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
