"use client";

import * as React from "react";
import { toast } from "sonner";
import { Check, CreditCard, Loader2, UserPlus } from "lucide-react";

import { api, ApiError } from "@/lib/api";

type Completion = "requested" | "havale_claimed" | null;

/**
 * Üyelik teklifi aksiyonları — TEK ödeme yöntemi: iyzico kart (havale KALDIRILDI).
 * Kart ödemesi giriş yapmış kullanıcı gerektirir → mevcut koç giriş yapıp
 * /teacher/plan'dan kartla öder; hesabı olmayan prospect kaydolup öder. İsteğe
 * bağlı "bilgilerimi bırak" lead'i (ödeme değil — iletişim).
 */
export function MembershipActions({
  token,
  planCode,
  initialCompletion,
}: {
  token: string;
  planCode: string | null;
  initialCompletion: Completion;
}) {
  const [leadDone, setLeadDone] = React.useState<boolean>(initialCompletion != null);
  const [pending, setPending] = React.useState(false);

  async function leaveLead() {
    setPending(true);
    try {
      await api(`/api/v2/membership/${token}/request`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setLeadDone(true);
    } catch (e) {
      toast.error(
        e instanceof ApiError
          ? e.detail?.message ?? "Bir sorun oluştu. Lütfen tekrar dene."
          : "Bağlantı hatası. Lütfen tekrar dene.",
      );
    } finally {
      setPending(false);
    }
  }

  const signupHref = planCode
    ? `/signup/teacher?plan=${encodeURIComponent(planCode)}`
    : "/signup/teacher";

  return (
    <section className="space-y-3">
      {/* Birincil: kartla öde (mevcut koç → giriş → /teacher/plan) */}
      <a
        href="/teacher/plan"
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-700 px-5 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-cyan-800"
      >
        <CreditCard className="size-5" aria-hidden />
        Kartla Öde ve Üyeliğimi Başlat
      </a>
      <p className="px-1 text-center text-xs text-slate-500">
        Güvenli kart ödemesi (3D Secure · iyzico). Hesabın varsa giriş yapman istenir.
      </p>

      {/* Hesabı olmayan: kaydol ve öde */}
      <a
        href={signupHref}
        className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-cyan-700 px-5 py-3 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-50"
      >
        <UserPlus className="size-4" aria-hidden />
        Hesabım yok — Kaydol ve öde
      </a>

      {/* İsteğe bağlı lead (ödeme değil — iletişim) */}
      {leadDone ? (
        <p className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-center text-sm text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-500/30">
          <Check className="mr-1 inline size-4" aria-hidden />
          Bilgilerin alındı, en kısa sürede sana ulaşacağız.
        </p>
      ) : (
        <button
          type="button"
          onClick={leaveLead}
          disabled={pending}
          className="flex w-full items-center justify-center gap-1.5 text-sm font-medium text-slate-500 transition hover:text-slate-700 disabled:opacity-50"
        >
          {pending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Şimdi ödeyemiyorum — bilgilerimi bırak, beni arayın
        </button>
      )}
    </section>
  );
}
