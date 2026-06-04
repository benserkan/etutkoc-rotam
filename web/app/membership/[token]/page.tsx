import type { Metadata } from "next";
import Image from "next/image";
import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { Check, ShieldCheck } from "lucide-react";

import { MembershipActions } from "./membership-actions";

/**
 * /membership/[token] — WhatsApp üyelik teklifi public sayfası (Paket 1).
 *
 * Login GEREKTİRMEZ. Kullanıcı WhatsApp'tan gelen linke tıklar (uygulama-içi
 * tarayıcı) → markalı ETÜTKOÇ sayfası → "Üye ol/Yenile" talebi veya havale/EFT
 * ile ödeme bildirimi. OG meta → WhatsApp link önizlemesinde ETÜTKOÇ logosu.
 */
export const dynamic = "force-dynamic";

interface HavaleInfo {
  enabled: boolean;
  iban: string;
  name: string;
  note: string;
}
interface MembershipView {
  valid: boolean;
  status: string;
  completion: string | null;
  offer_type: string | null;
  offer_type_label: string | null;
  title: string | null;
  message: string | null;
  target_name: string | null;
  plan_code: string | null;
  plan_label: string | null;
  plan_short: string | null;
  plan_features: string[];
  cycle: string | null;
  cycle_label: string | null;
  amount: number | null;
  havale: HavaleInfo | null;
}

async function fetchOffer(token: string): Promise<MembershipView | null> {
  try {
    return await apiServer<MembershipView>(`/api/v2/membership/${token}`);
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
  const offer = await fetchOffer(token);
  const title = offer?.title || "ETÜTKOÇ — Üyelik Teklifin Hazır";
  const desc =
    offer?.plan_label
      ? `${offer.offer_type_label ?? "Üyelik"} · ${offer.plan_label}. Üyeliğini tamamlamak için dokun.`
      : "Sana özel üyelik teklifi. Tamamlamak için dokun.";
  return {
    title,
    description: desc,
    metadataBase: new URL("https://rotam.etutkoc.com"),
    openGraph: {
      title,
      description: desc,
      siteName: "ETÜTKOÇ Rotam",
      type: "website",
      images: [{ url: "/etutkoc-logo.png", width: 512, height: 512, alt: "ETÜTKOÇ" }],
    },
    twitter: { card: "summary", title, description: desc, images: ["/etutkoc-logo.png"] },
  };
}

function fmtTry(n: number): string {
  return new Intl.NumberFormat("tr-TR").format(n);
}

const DEAD_MESSAGE: Record<string, string> = {
  not_found: "Teklif bulunamadı. Bağlantıyı doğru açtığından emin ol.",
  expired: "Bu teklifin süresi dolmuş. Yeni teklif için bizimle iletişime geç.",
  cancelled: "Bu teklif iptal edilmiş.",
};

export default async function MembershipPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const offer = await fetchOffer(token);

  const status = offer?.status ?? "not_found";
  const isActive = offer?.valid && status === "active";
  const isAccepted = offer?.valid && status === "accepted";

  return (
    <main className="force-light min-h-screen bg-slate-50 text-slate-900">
      {/* Marka şeridi */}
      <header className="bg-white border-b border-slate-200">
        <div className="mx-auto max-w-lg px-5 py-3 flex items-center gap-2.5">
          <Image src="/etutkoc-logo.svg" alt="ETÜTKOÇ" width={132} height={30} priority />
        </div>
      </header>

      <div className="mx-auto max-w-lg px-5 py-6 space-y-5">
        {!offer || (!isActive && !isAccepted) ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
            <p className="text-slate-700">{DEAD_MESSAGE[status] ?? DEAD_MESSAGE.not_found}</p>
            <a
              href="https://wa.me/"
              className="mt-4 inline-block text-sm font-medium text-cyan-700 underline"
            >
              etutkoc.com
            </a>
          </div>
        ) : (
          <>
            {/* Hero */}
            <section className="rounded-2xl bg-gradient-to-br from-cyan-600 to-cyan-800 px-5 py-6 text-white shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wider text-cyan-100">
                {offer.offer_type_label ?? "Üyelik"}
              </p>
              <h1 className="mt-1 text-xl font-bold leading-snug">
                {offer.target_name ? `Merhaba ${offer.target_name},` : "Merhaba,"}
              </h1>
              <p className="mt-1.5 text-[15px] leading-relaxed text-cyan-50">
                {offer.title ||
                  (offer.offer_type === "renewal"
                    ? "Üyeliğini avantajlı şekilde yenilemen için teklifini hazırladık."
                    : "Sana özel üyelik teklifini hazırladık.")}
              </p>
            </section>

            {offer.message ? (
              <p className="px-1 text-[15px] leading-relaxed text-slate-700 whitespace-pre-line">
                {offer.message}
              </p>
            ) : null}

            {/* Plan kartı */}
            <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">{offer.plan_label}</h2>
                  {offer.plan_short ? (
                    <p className="text-sm text-slate-500">{offer.plan_short}</p>
                  ) : null}
                </div>
                <div className="text-right">
                  {offer.amount ? (
                    <>
                      <div className="text-2xl font-extrabold text-cyan-700">
                        {fmtTry(offer.amount)} ₺
                      </div>
                      <div className="text-[11px] text-slate-500">/ {offer.cycle_label}</div>
                    </>
                  ) : (
                    <div className="text-sm font-semibold text-cyan-700">Size özel</div>
                  )}
                </div>
              </div>

              {offer.plan_features.length > 0 ? (
                <ul className="mt-4 space-y-2">
                  {offer.plan_features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                      <Check className="mt-0.5 size-4 flex-shrink-0 text-emerald-600" aria-hidden />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            {/* Aksiyonlar (client) */}
            <MembershipActions
              token={token}
              havale={offer.havale}
              initialCompletion={
                isAccepted &&
                (offer.completion === "requested" || offer.completion === "havale_claimed")
                  ? offer.completion
                  : null
              }
            />

            {/* Güvence */}
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
