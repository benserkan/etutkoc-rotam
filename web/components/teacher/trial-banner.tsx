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

  if (!data || !data.is_solo) return null;

  // 1) Ödeme duvarı — past_due (abonelik yenilenmedi) VEYA deneme bitti+limit aşımı
  if (data.paywall) {
    if (data.past_due) {
      return (
        <div className="border-b border-rose-200 bg-rose-50">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2.5 text-sm text-rose-900">
              <Lock className="mt-0.5 size-4 shrink-0 text-rose-600" aria-hidden />
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
    return (
      <div className="border-b border-rose-200 bg-rose-50">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-2.5 text-sm text-rose-900">
            <Lock className="mt-0.5 size-4 shrink-0 text-rose-600" aria-hidden />
            <span>
              <strong>Deneme süreniz bitti.</strong> {data.student_count} öğrenciniz var;
              ücretsiz sürüm {data.student_limit} öğrenci destekler. Koçluğa devam etmek
              için paketi yükseltin <em>ya da</em> {data.student_limit} öğrenci tutup
              gerisini arşivleyin.
            </span>
          </div>
          <div className="flex shrink-0 gap-2">
            <Link
              href="/teacher/students"
              className="inline-flex items-center justify-center rounded-lg border border-rose-300 bg-white px-3 py-1.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-50"
            >
              Öğrencileri yönet
            </Link>
            <Link
              href="/teacher/plan"
              className="inline-flex items-center justify-center rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700"
            >
              Paketi yükselt
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
      <div className="border-b border-amber-200 bg-amber-50">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5">
          <Clock className="size-4 shrink-0 text-amber-600" aria-hidden />
          <p className="flex-1 text-sm text-amber-900">
            <strong>Pro denemeniz {left} bitiyor.</strong>{" "}
            Solo&apos;ya geçerek tüm öğrencileriniz ve yapay zekâ özellikleriyle devam edin.
          </p>
          <Link
            href="/teacher/plan"
            className="inline-flex shrink-0 items-center justify-center rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-amber-950 transition hover:bg-amber-400"
          >
            Solo&apos;ya geç
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
            className="shrink-0 rounded p-1 text-amber-700 transition hover:bg-amber-100"
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
