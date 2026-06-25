import type { Metadata } from "next";
import Image from "next/image";
import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { Check, ShieldCheck } from "lucide-react";

import { CampaignLeadForm } from "./campaign-lead-form";

/**
 * /kampanya/[token] — public, markalı kampanya landing (Yol A).
 *
 * Login GEREKTİRMEZ. Admin linki WhatsApp grubuna paylaşır → tıklayan markalı
 * ETÜTKOÇ sayfasını görür → ad+telefon bırakır (lead). Kişiye özel DEĞİL
 * (membership 1:1; kampanya 1:çok). OG meta → WhatsApp önizlemesinde logo.
 */
export const dynamic = "force-dynamic";

interface CampaignView {
  valid: boolean;
  status: string;
  audience: string | null;
  title: string | null;
  message: string | null;
  plan_code: string | null;
  plan_label: string | null;
  plan_short: string | null;
  plan_features: string[];
  cycle: string | null;
  cycle_label: string | null;
  amount: number | null;
  list_price: number | null;
  savings: number | null;
  discount_pct: number | null;
}

async function fetchCampaign(token: string): Promise<CampaignView | null> {
  try {
    return await apiServer<CampaignView>(`/api/v2/campaign/${token}`);
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ token: string }>;
}): Promise<Metadata> {
  const { token } = await params;
  const c = await fetchCampaign(token);
  const planBit = c?.plan_label
    ? c.amount
      ? `${c.plan_label} · ${new Intl.NumberFormat("tr-TR").format(c.amount)} ₺/${c.cycle_label}`
      : c.plan_label
    : null;
  const isInst = c?.audience === "institution";
  const title = c?.title || "ETÜTKOÇ Rotam — Öğrenci Koçluğu Tek Panelde";
  const desc = isInst
    ? `Kurumunuzun tüm koçlarını, öğrencilerini ve veli iletişimini tek panelden yönetin.${planBit ? " " + planBit + "." : ""} Detaylar için dokun.`
    : `Program, deneme takibi, veli bilgilendirme ve yapay zekâ hazırlık tek panelde.${planBit ? " " + planBit + "." : ""} Detaylar için dokun.`;

  return {
    title,
    description: desc,
    metadataBase: new URL("https://rotam.etutkoc.com"),
    openGraph: {
      title,
      description: desc,
      siteName: "ETÜTKOÇ Rotam",
      type: "website",
      images: [
        { url: "/og-membership.png?v=2", width: 1200, height: 630, type: "image/png", alt: "ETÜTKOÇ Rotam" },
      ],
    },
    twitter: { card: "summary_large_image", title, description: desc, images: ["/og-membership.png?v=2"] },
  };
}

function fmtTry(n: number): string {
  return new Intl.NumberFormat("tr-TR").format(n);
}

const DEAD_MESSAGE: Record<string, string> = {
  not_found: "Kampanya bulunamadı. Bağlantıyı doğru açtığından emin ol.",
  expired: "Bu kampanyanın süresi dolmuş. Güncel teklif için bizimle iletişime geç.",
  paused: "Bu kampanya şu an aktif değil. Güncel teklif için bizimle iletişime geç.",
  archived: "Bu kampanya sona erdi.",
};

export default async function CampaignPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const c = await fetchCampaign(token);
  const status = c?.status ?? "not_found";
  const isActive = c?.valid && status === "active";
  const isInst = c?.audience === "institution";

  return (
    <main className="force-light min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-lg px-5 py-3 flex items-center gap-2.5">
          <Image src="/etutkoc-logo.svg" alt="ETÜTKOÇ" width={132} height={30} priority />
        </div>
      </header>

      <div className="mx-auto max-w-lg px-5 py-6 space-y-5">
        {!c || !isActive ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
            <p className="text-slate-700">{DEAD_MESSAGE[status] ?? DEAD_MESSAGE.not_found}</p>
            <a
              href="https://rotam.etutkoc.com/pricing"
              className="mt-4 inline-block text-sm font-medium text-cyan-700 underline"
            >
              Paketleri incele →
            </a>
          </div>
        ) : (
          <>
            {/* Hero */}
            <section className="rounded-2xl bg-gradient-to-br from-cyan-600 to-cyan-800 px-5 py-6 text-white shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-cyan-100">
                {isInst ? "Kurumsal Üyelik" : "Koçluk Üyeliği"}
              </p>
              <h1 className="mt-1 text-xl font-bold leading-snug">
                {c.title ||
                  (isInst
                    ? "Kurumunuzu tek panelden yönetin"
                    : "Öğrenci koçluğunu tek panelden yönet")}
              </h1>
              <p className="mt-1.5 text-[15px] leading-relaxed text-cyan-50">
                {isInst
                  ? "Tüm koçlarınız, öğrencileriniz ve veli iletişimi tek yerde — program, deneme takibi, akademik çıktı ve yapay zekâ hazırlık."
                  : "Program, deneme takibi, veli bilgilendirme ve yapay zekâ hazırlık — koçluğunu büyütmek için her şey tek panelde."}
              </p>
            </section>

            {c.message ? (
              <p className="px-1 text-[15px] leading-relaxed text-slate-700 whitespace-pre-line">
                {c.message}
              </p>
            ) : null}

            {/* Plan kartı */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{c.plan_label}</h2>
                  {c.plan_short ? (
                    <p className="text-sm text-slate-500">{c.plan_short}</p>
                  ) : null}
                </div>
                <div className="text-right">
                  {c.amount ? (
                    <>
                      {c.list_price && c.savings ? (
                        <div className="text-sm font-medium text-slate-400 line-through">
                          {fmtTry(c.list_price)} ₺
                        </div>
                      ) : null}
                      <div className="text-2xl font-extrabold text-cyan-700">
                        {fmtTry(c.amount)} ₺
                      </div>
                      <div className="text-[11px] text-slate-500">/ {c.cycle_label}</div>
                    </>
                  ) : (
                    <div className="text-sm font-semibold text-cyan-700">Size özel</div>
                  )}
                </div>
              </div>

              {c.savings && c.amount ? (
                <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-center text-sm font-semibold text-emerald-800">
                  {c.discount_pct ? `%${c.discount_pct} ` : ""}indirim ·
                  {" "}{fmtTry(c.savings)} ₺ tasarruf
                  <span className="font-normal"> ({c.cycle_label})</span>
                </div>
              ) : null}

              {c.plan_features.length > 0 ? (
                <ul className="mt-4 space-y-2">
                  {c.plan_features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                      <Check className="mt-0.5 size-4 flex-shrink-0 text-emerald-600" aria-hidden />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            {/* Lead formu (client) */}
            <CampaignLeadForm token={token} isInst={isInst} />

            {/* Tüm paketler */}
            <a
              href="https://rotam.etutkoc.com/pricing"
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-center text-sm font-medium text-cyan-700 shadow-sm hover:bg-cyan-50"
            >
              Tüm paketleri ve özellikleri incele →
            </a>

            <p className="flex items-center justify-center gap-1.5 text-center text-[11px] text-slate-400">
              <ShieldCheck className="size-3.5" aria-hidden />
              ETÜTKOÇ Rotam · güvenli üyelik
            </p>
          </>
        )}
      </div>
    </main>
  );
}
