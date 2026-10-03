"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Clock, Lock, X } from "lucide-react";

import { getTeacherTrialStatus, teacherKeys } from "@/lib/api/teacher";
import type { TrialStatusResponse } from "@/lib/types/teacher";

/**
 * Bağımsız koç trial geri-sayım + ödeme-duvarı bandı.
 *
 * Gösterim (kullanıcı kararı): son 3 gün geri-sayım uyarısı + deneme bitince
 * ödeme duvarı. Diğer zamanlarda bant gösterilmez (gürültü olmasın).
 *  - paywall (ücretsiz + limit aşıldı): kırmızı, KAPATILAMAZ → yükselt/arşivle.
 *  - trial_critical (≤3 gün): amber, kapatılabilir geri-sayım.
 *  - capacity_exceeded (ücretli paket + öğrenci sayısı kapasiteyi aştı): kırmızı,
 *    KAPATILAMAZ → tek tıkla uygun pakete geç (ödeme penceresi açık gelir) ya da
 *    fazla öğrenciyi pasife al.
 *  - payment_pending (deneme bitti + signup'ta ücretli paket seçilmişti +
 *    henüz ödenmedi): amber "ödemeni tamamla" hatırlatması — günlük
 *    kapatılabilir, ertesi gün yeniden görünür (Google tarzı ödeme daveti).
 */
export function TrialBanner({ enabled }: { enabled: boolean }) {
  const q = useQuery<TrialStatusResponse>({
    queryKey: teacherKeys.trialStatus(),
    queryFn: getTeacherTrialStatus,
    enabled,
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
  const data = q.data;
  const [dismissTick, setDismissTick] = React.useState(0);

  // Geri-sayım için günlük kapatma anahtarı (ertesi gün yeniden görünür).
  const dismissKey = data ? `trialbanner_dismiss_${data.days_left ?? "x"}` : "";
  const dismissed = React.useMemo(() => {
    if (!dismissKey || typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(dismissKey) === "1";
    } catch {
      return false;
    }
    // dismissTick: kapatınca yeniden hesapla
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dismissKey, dismissTick]);

  // "Ödemen bekleniyor" bandı için gün-bazlı kapatma anahtarı.
  const payDismissKey = `trialbanner_paypend_${new Date().toISOString().slice(0, 10)}`;
  const payDismissed = React.useMemo(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(payDismissKey) === "1";
    } catch {
      return false;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payDismissKey, dismissTick]);

  if (!data || !data.is_solo) return null;

  // 1) Ödeme duvarı — past_due (abonelik yenilenmedi) VEYA deneme bitti+limit aşımı
  if (data.paywall) {
    if (data.past_due) {
      return (
        <div className="border-b border-rose-200 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/30">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2.5 text-sm text-rose-900 dark:text-rose-200">
              <Lock className="mt-0.5 size-4 shrink-0 text-rose-600 dark:text-rose-300" aria-hidden />
              <span>
                <strong>Aboneliğin yenilenmedi.</strong> Öğrencilerin ve verilerin
                duruyor; aktif koçluğa devam etmek için aboneliğini yenile.
              </span>
            </div>
            <Link
              href="/teacher/plan"
              className="inline-flex shrink-0 items-center justify-center rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700"
            >
              Aboneliği yenile
            </Link>
          </div>
        </div>
      );
    }
    const recLabel = data.recommended_label ?? "Uygun paket";
    const checkoutHref = data.recommended_plan
      ? `/teacher/plan?plan=${data.recommended_plan}&checkout=1`
      : "/teacher/plan";
    if (data.capacity_exceeded) {
      const extra = Math.max(0, data.student_count - data.student_limit);
      const appStore = data.subscription_platform === "app_store";
      return (
        <div className="border-b border-rose-200 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/30">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2.5 text-sm text-rose-900 dark:text-rose-200">
              <Lock className="mt-0.5 size-4 shrink-0 text-rose-600 dark:text-rose-300" aria-hidden />
              <span>
                <strong>
                  {data.student_count} aktif öğrencin var, {recLabel} gerekir.
                </strong>{" "}
                {data.plan_label} paketin {data.student_limit} öğrenci içindir; program
                yazma ve yeni öğrenci ekleme şimdilik kapalı.{" "}
                {appStore
                  ? `Paketini App Store aboneliklerinden ${recLabel} paketine yükselt `
                  : `Tek tıkla ${recLabel} paketine geç `}
                <em>ya da</em> {extra} öğrenciyi pasif duruma al.
              </span>
            </div>
            <div className="flex shrink-0 gap-2">
              <Link
                href="/teacher/students"
                className="inline-flex items-center justify-center rounded-lg border border-rose-300 bg-card px-3 py-1.5 text-xs font-semibold text-rose-700 dark:text-rose-300 transition hover:bg-rose-50"
              >
                Öğrencileri yönet
              </Link>
              {appStore ? null : (
                <Link
                  href={checkoutHref}
                  className="inline-flex items-center justify-center rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700"
                >
                  {recLabel} paketine geç
                </Link>
              )}
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="border-b border-rose-200 bg-rose-50 dark:bg-rose-500/10 dark:border-rose-500/30">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2.5 text-sm text-rose-900 dark:text-rose-200">
            <Lock className="mt-0.5 size-4 shrink-0 text-rose-600 dark:text-rose-300" aria-hidden />
            <span>
              <strong>
                {data.trial_denied_reason ? "Ücretsiz paket sınırı." : "Deneme süreniz bitti."}
              </strong>{" "}
              {data.student_count} öğrenciniz var; ücretsiz Keşif paketi{" "}
              {data.student_limit} öğrenci destekler. Koçluğa devam etmek için{" "}
              {recLabel} paketine geçin <em>ya da</em> {data.student_limit} öğrenci tutup
              gerisini pasif duruma geçirin. Pakete geçtiğinizde pasif öğrencileriniz
              paketin kapasitesi kadar otomatik yeniden aktif olur.
            </span>
          </div>
          <div className="flex shrink-0 gap-2">
            <Link
              href="/teacher/students"
              className="inline-flex items-center justify-center rounded-lg border border-rose-300 bg-card px-3 py-1.5 text-xs font-semibold text-rose-700 dark:text-rose-300 transition hover:bg-rose-50"
            >
              Öğrencileri yönet
            </Link>
            <Link
              href={checkoutHref}
              className="inline-flex items-center justify-center rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700"
            >
              {recLabel} paketine geç
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // 2) Son 3 gün geri-sayım (kapatılabilir)
  if (data.trial_critical && !dismissed) {
    const d = data.days_left ?? 0;
    const left = d <= 0 ? "bugün" : d === 1 ? "yarın" : `${d} gün sonra`;
    return (
      <div className="border-b border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <Clock className="size-4 shrink-0 text-amber-600 dark:text-amber-300" aria-hidden />
          <p className="flex-1 text-sm text-amber-900 dark:text-amber-200">
            <strong>Denemen {left} bitiyor.</strong>{" "}
            <TrialValueLine value={data.trial_value} />
            Paketine geçerek tüm öğrencilerin ve yapay zekâ özellikleriyle devam et.
          </p>
          <Link
            href="/teacher/plan"
            className="inline-flex shrink-0 items-center justify-center rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-950 transition hover:bg-amber-400"
          >
            Paketini seç
          </Link>
          <button
            type="button"
            aria-label="Kapat"
            onClick={() => {
              try {
                window.localStorage.setItem(dismissKey, "1");
              } catch {
                /* yoksay */
              }
              setDismissTick((t) => t + 1);
            }}
            className="shrink-0 rounded p-1 text-amber-700 dark:text-amber-300 transition hover:bg-amber-100"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>
    );
  }

  // 3) Deneme bitti + seçilen paket ödenmedi (kapatılabilir, her gün döner).
  //    Deneme hiç verilmediyse (aynı kişinin önceki hesabı) metin bunu söyler.
  if ((data.payment_pending || data.trial_denied_reason) && !payDismissed) {
    const denied = !!data.trial_denied_reason;
    const reasonText =
      data.trial_denied_reason === "device"
        ? "bu cihazda"
        : data.trial_denied_reason === "phone"
          ? "bu telefon numarasıyla"
          : "bu e-posta adresiyle";
    return (
      <div className="border-b border-amber-200 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <Clock className="size-4 shrink-0 text-amber-600 dark:text-amber-300" aria-hidden />
          <p className="flex-1 text-sm text-amber-900 dark:text-amber-200">
            {denied ? (
              <>
                <strong>Ücretsiz deneme kişi başına bir kez verilir.</strong>{" "}
                {reasonText} daha önce bir koç hesabı açıldığı için bu hesap ücretsiz Keşif
                paketiyle ({data.student_limit} öğrenci) başladı.{" "}
                {data.intended_plan_label
                  ? `${data.intended_plan_label} paketine geçerek tüm özellikleri hemen açabilirsin.`
                  : "Bir pakete geçerek tüm özellikleri hemen açabilirsin."}
              </>
            ) : (
              <>
                <strong>Denemen bitti — ödemen bekleniyor.</strong>{" "}
                {data.intended_plan_label ?? "Seçtiğin paket"} ile kaldığın yerden
                devam etmek için ödemeni tamamla; öğrencilerin ve verilerin duruyor.
              </>
            )}
          </p>
          <Link
            href="/teacher/plan"
            className="inline-flex shrink-0 items-center justify-center rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-950 transition hover:bg-amber-400"
          >
            {denied ? "Paketleri gör" : "Ödemeyi tamamla"}
          </Link>
          <button
            type="button"
            aria-label="Kapat"
            onClick={() => {
              try {
                window.localStorage.setItem(payDismissKey, "1");
              } catch {
                /* yoksay */
              }
              setDismissTick((t) => t + 1);
            }}
            className="shrink-0 rounded p-1 text-amber-700 dark:text-amber-300 transition hover:bg-amber-100"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>
    );
  }

  // Diğer durumlar (trial başı, normal ücretsiz, ücretli) → bant yok.
  return null;
}

/**
 * Deneme değer sayacı (Faz 2D): "değeri gördün" anlatımı — denemede üretilen
 * somut çıktıları sayar. Hiç kullanım yoksa hiçbir şey basmaz.
 */
function TrialValueLine({ value }: { value: Record<string, number> | null | undefined }) {
  if (!value) return null;
  const parts: string[] = [];
  if (value.karne) parts.push(`${value.karne} karne okundu`);
  if (value.veli) parts.push(`${value.veli} veli yorumu/sohbeti`);
  if (value.etiket) parts.push(`${value.etiket} soru etiketlendi`);
  if (value.icgoru) parts.push(`${value.icgoru} görüşme özeti`);
  if (parts.length === 0) return null;
  return (
    <>
      Denemende şimdiden <strong>{parts.join(" · ")}</strong> — paketinde böyle devam eder.{" "}
    </>
  );
}
