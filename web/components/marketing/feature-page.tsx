import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Check } from "lucide-react";

import { BrandLogo } from "@/components/brand-logo";
import { LandingFooter } from "@/components/landing/landing-client";
import { SITE_URL } from "@/lib/site";

/**
 * Herkese açık tanıtım sayfaları için ortak iskelet (arama motoru sayfaları).
 * İçerik tamamen sunucuda çizilir; görseller ürünün gerçek ekranlarından kırpımdır
 * (web/public/urun). Her sayfa kendi SSS'sini FAQPage şeması olarak da yayınlar —
 * şema yalnız sayfada görünen soruları içerir.
 */

export const MARKETING_NAV = [
  { href: "/ogrenci-takip-programi", label: "Öğrenci takip" },
  { href: "/deneme-analizi", label: "Deneme analizi" },
  { href: "/kurumlar", label: "Kurumlar" },
  { href: "/bagimsiz-koclar", label: "Bağımsız koçlar" },
  { href: "/yks-puan-hesaplama", label: "YKS puan hesaplama" },
  { href: "/pricing", label: "Paketler" },
];

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-cyan-900/15 bg-[#f7f5f0]/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <BrandLogo />
        <nav className="hidden items-center gap-5 text-sm font-medium text-slate-600 lg:flex">
          {MARKETING_NAV.map((n) => (
            <Link key={n.href} href={n.href} className="transition hover:text-cyan-800">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link
            href="/login"
            className="inline-flex items-center rounded-full border border-cyan-700/30 px-3 py-1.5 text-xs font-semibold text-cyan-800 transition hover:border-cyan-700 sm:px-4 sm:py-2 sm:text-sm"
          >
            Giriş
          </Link>
          <Link
            href="/signup/teacher"
            className="inline-flex items-center rounded-full bg-cyan-700 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-cyan-800 sm:px-4 sm:py-2 sm:text-sm"
          >
            Ücretsiz Dene
          </Link>
        </div>
      </div>
    </header>
  );
}

export interface FeatureSection {
  id: string;
  title: string;
  body: string[];
  bullets?: string[];
  image?: { src: string; alt: string; width: number; height: number };
}

export interface FaqItem {
  q: string;
  a: string;
}

export interface FeaturePageContent {
  path: string;
  eyebrow: string;
  h1: string;
  lead: string;
  highlights: string[];
  sections: FeatureSection[];
  faq: FaqItem[];
  related: { href: string; title: string; text: string }[];
  ctaTitle: string;
  ctaText: string;
}

function JsonLd({ content }: { content: FeaturePageContent }) {
  const url = `${SITE_URL}${content.path}`;
  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Etütkoç Rotam", item: SITE_URL },
          { "@type": "ListItem", position: 2, name: content.eyebrow, item: url },
        ],
      },
      {
        "@type": "FAQPage",
        mainEntity: content.faq.map((f) => ({
          "@type": "Question",
          name: f.q,
          acceptedAnswer: { "@type": "Answer", text: f.a },
        })),
      },
    ],
  };
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

export function FeaturePage({ content }: { content: FeaturePageContent }) {
  return (
    <div className="force-light min-h-screen bg-[#f7f5f0] text-slate-900">
      <JsonLd content={content} />
      <MarketingHeader />

      <main>
        {/* Hero */}
        <section className="border-b border-cyan-900/10">
          <div className="mx-auto max-w-5xl px-4 py-14 sm:px-6 lg:py-20">
            <nav aria-label="Konum" className="mb-5 text-xs text-slate-500">
              <Link href="/" className="hover:text-cyan-800">Etütkoç Rotam</Link>
              <span className="mx-1.5">/</span>
              <span className="text-slate-700">{content.eyebrow}</span>
            </nav>
            <h1 className="font-display text-3xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-5xl">
              {content.h1}
            </h1>
            <p className="mt-5 max-w-3xl text-lg leading-relaxed text-slate-700">{content.lead}</p>
            <ul className="mt-6 grid gap-2.5 sm:grid-cols-2">
              {content.highlights.map((h) => (
                <li key={h} className="flex items-start gap-2.5 text-[15px] leading-snug text-slate-700">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-cyan-800">
                    <Check className="size-3" aria-hidden />
                  </span>
                  <span>{h}</span>
                </li>
              ))}
            </ul>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/signup/teacher"
                className="inline-flex items-center gap-2 rounded-full bg-cyan-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-cyan-800"
              >
                14 gün ücretsiz dene <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link
                href="/demos"
                className="inline-flex items-center rounded-full border border-cyan-700/30 bg-white px-5 py-3 text-sm font-semibold text-cyan-800 transition hover:border-cyan-700"
              >
                Tanıtım videolarını izle
              </Link>
            </div>
          </div>
        </section>

        {/* Bölümler */}
        {content.sections.map((s, i) => (
          <section key={s.id} id={s.id} className={i % 2 ? "bg-white" : ""}>
            <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 lg:py-16">
              <h2 className="font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">{s.title}</h2>
              <div className="mt-4 max-w-3xl space-y-4 text-[16px] leading-relaxed text-slate-700">
                {s.body.map((p) => (
                  <p key={p.slice(0, 40)}>{p}</p>
                ))}
              </div>
              {s.bullets ? (
                <ul className="mt-5 max-w-3xl space-y-2">
                  {s.bullets.map((b) => (
                    <li key={b} className="flex items-start gap-2.5 text-[15px] leading-snug text-slate-700">
                      <Check className="mt-0.5 size-4 shrink-0 text-cyan-700" aria-hidden />
                      <span>{b}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {s.image ? (
                <figure className="mt-8">
                  <a href={s.image.src} target="_blank" rel="noopener" className="block overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <Image
                      src={s.image.src}
                      alt={s.image.alt}
                      width={s.image.width}
                      height={s.image.height}
                      className="h-auto w-full"
                      sizes="(min-width: 1024px) 960px, 100vw"
                    />
                  </a>
                  <figcaption className="mt-2 text-xs text-slate-500">{s.image.alt} — Etütkoç Rotam ekranı (büyütmek için tıklayın)</figcaption>
                </figure>
              ) : null}
            </div>
          </section>
        ))}

        {/* SSS */}
        <section className="border-t border-cyan-900/10 bg-white">
          <div className="mx-auto max-w-3xl px-4 py-12 sm:px-6 lg:py-16">
            <h2 className="font-display text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">Sık sorulan sorular</h2>
            <div className="mt-6 divide-y divide-slate-200 rounded-2xl border border-slate-200">
              {content.faq.map((f) => (
                <details key={f.q} className="group p-5">
                  <summary className="cursor-pointer list-none font-semibold text-slate-900 marker:hidden">
                    {f.q}
                  </summary>
                  <p className="mt-3 text-[15px] leading-relaxed text-slate-700">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* İlgili sayfalar */}
        <section>
          <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6">
            <h2 className="font-display text-xl font-bold text-slate-900">İlgili sayfalar</h2>
            <div className="mt-5 grid gap-4 sm:grid-cols-3">
              {content.related.map((r) => (
                <Link
                  key={r.href}
                  href={r.href}
                  className="rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-cyan-700/40 hover:shadow-sm"
                >
                  <div className="font-semibold text-slate-900">{r.title}</div>
                  <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{r.text}</p>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Son çağrı */}
        <section className="bg-cyan-900">
          <div className="mx-auto max-w-4xl px-4 py-14 text-center sm:px-6">
            <h2 className="font-display text-2xl font-bold text-white sm:text-3xl">{content.ctaTitle}</h2>
            <p className="mx-auto mt-3 max-w-2xl text-cyan-100">{content.ctaText}</p>
            <div className="mt-7 flex flex-wrap justify-center gap-3">
              <Link href="/signup/teacher" className="rounded-full bg-amber-400 px-6 py-3 text-sm font-semibold text-slate-900 transition hover:bg-amber-300">
                14 gün ücretsiz başla
              </Link>
              <Link href="/pricing" className="rounded-full border border-white/40 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10">
                Paketleri gör
              </Link>
            </div>
          </div>
        </section>
      </main>

      <LandingFooter />
    </div>
  );
}
