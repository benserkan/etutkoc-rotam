import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { apiServer } from "@/lib/api-server";
import { Check, ShieldCheck } from "lucide-react";

import { MembershipActions } from "./membership-actions";

/**
 * /membership/[token] — WhatsApp üyelik teklifi public sayfası (Paket 1).
 *
 * Login GEREKTİRMEZ. Kullanıcı WhatsApp'tan gelen linke tıklar (uygulama-içi
 * tarayıcı) → markalı ETÜTKOÇ sayfası → kartla ödemeye yönlendirilir (iyzico).
 * OG meta → WhatsApp link önizlemesinde ETÜTKOÇ logosu.
 */
export const dynamic = "force-dynamic";

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
  list_price: number | null;
  savings: number | null;
  discount_pct: number | null;
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
  const isRenewal = offer?.offer_type === "renewal";
  const planBit = offer?.plan_label
    ? offer.amount
      ? `${offer.plan_label} · ${new Intl.NumberFormat("tr-TR").format(offer.amount)} ₺/${offer.cycle_label}`
      : offer.plan_label
    : null;

  // Başlık + açıklama amaç-net (sigortam.net kalitesi): kart, dokunmadan ÖNCE
  // neden geldiğini ve değerini anlatır.
  const title =
    offer?.title ||
    (isRenewal
      ? "ETÜTKOÇ Rotam — Üyeliğini Yenile"
      : "ETÜTKOÇ Rotam — Sana Özel Üyelik");
  const desc = isRenewal
    ? `${planBit ? planBit + ". " : ""}Öğrenci takibin, deneme analizin ve veli bildirimlerin kesintisiz devam etsin — yenilemek için dokun.`
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
      // Statik 1200×630 banner (Content-Length + uzun cache + .png) → WhatsApp
      // tarayıcısı BÜYÜK hero önizleme gösterir. Dinamik next/og route'u
      // (Content-Length yok + must-revalidate) küçük thumbnail'e düşüyordu.
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
        <div className="mx-auto max-w-lg px-5 py-3 flex items-center justify-between gap-2.5">
          <Link href="/" className="flex items-center" aria-label="ETÜTKOÇ rotam ana sayfa">
            <Image src="/etutkoc-logo.svg" alt="ETÜTKOÇ rotam" width={132} height={30} priority />
          </Link>
          <nav className="flex items-center gap-4 text-sm font-semibold">
            <Link href="/" className="text-slate-600 hover:text-cyan-700">Anasayfa</Link>
            <Link href="/login" className="text-cyan-700 hover:text-cyan-800">Giriş</Link>
          </nav>
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
                    ? "Üyeliğin sona eriyor. Öğrenci takibin, deneme analizin ve veli bildirimlerin kesintisiz devam etsin diye avantajlı yenileme teklifini hazırladık."
                    : "ETÜTKOÇ Rotam ile öğrenci koçluğunu tek panelden yönet — program, deneme takibi, veli bilgilendirme ve yapay zekâ hazırlık. Sana özel üyelik teklifini hazırladık.")}
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
                      {offer.list_price && offer.savings ? (
                        <div className="text-sm font-medium text-slate-400 line-through">
                          {fmtTry(offer.list_price)} ₺
                        </div>
                      ) : null}
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

              {offer.savings && offer.amount ? (
                <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-center text-sm font-semibold text-emerald-800">
                  Sana özel {offer.discount_pct ? `%${offer.discount_pct} ` : ""}indirim ·
                  {" "}{fmtTry(offer.savings)} ₺ tasarruf
                  <span className="font-normal"> ({offer.cycle_label})</span>
                </div>
              ) : null}

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
              planCode={offer.plan_code}
              initialCompletion={
                isAccepted &&
                (offer.completion === "requested" || offer.completion === "havale_claimed")
                  ? offer.completion
                  : null
              }
            />

            {/* Tüm paketler — kullanıcı diğer seçenekleri de görebilsin */}
            <a
              href="https://rotam.etutkoc.com/pricing"
              target="_blank"
              rel="noopener noreferrer"
              className="block rounded-2xl border border-slate-200 bg-white px-5 py-3.5 text-center text-sm font-medium text-cyan-700 shadow-sm hover:bg-cyan-50"
            >
              Tüm paketleri ve özellikleri incele →
            </a>

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
