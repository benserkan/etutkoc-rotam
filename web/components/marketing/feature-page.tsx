import Link from "next/link";
import Image from "next/image";
import { ArrowRight, Check, ChevronDown, PlayCircle, Smartphone, Sparkles } from "lucide-react";

import { LandingFooter } from "@/components/landing/landing-client";
import { SiteHeader } from "@/components/marketing/site-header";
import { PLAY_STORE_URL, SITE_URL } from "@/lib/site";
import type { Shot } from "@/lib/product-shots";
import { cn } from "@/lib/utils";

/**
 * Herkese açık ürün tanıtım sayfalarının ortak şablonu (arama motoru sayfaları).
 * İçerik sunucuda çizilir. Ekranlar ürünün gerçek panelinden 2x yakalanmış
 * kırpımlardır (lib/product-shots); tarayıcı çerçevesi içinde, okunur genişlikte
 * gösterilir ve tıklanınca tam boy açılır. Her sayfa SSS'sini FAQPage şeması
 * olarak da yayınlar — şema yalnız sayfada görünen soruları içerir.
 */

export interface FeatureSection {
  id: string;
  kicker: string;
  title: string;
  body: string[];
  bullets?: string[];
  image?: Shot;
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
  heroImage: Shot;
  /** Hero altındaki kısa öne çıkanlar (ikonlu kartlar). */
  highlights: { title: string; text: string }[];
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

/** Ürün ekranı — tarayıcı çerçevesi içinde; tıklanınca tam boy yeni sekmede açılır. */
export function BrowserShot({
  shot,
  priority = false,
  sizes = "(min-width: 1024px) 640px, 100vw",
  className,
}: {
  shot: Shot;
  priority?: boolean;
  sizes?: string;
  className?: string;
}) {
  return (
    <figure className={cn("relative", className)}>
      <a
        href={shot.src}
        target="_blank"
        rel="noopener"
        className="group block overflow-hidden rounded-2xl bg-white shadow-2xl shadow-slate-900/20 ring-1 ring-slate-900/10 transition duration-300 hover:-translate-y-1 hover:shadow-slate-900/30"
      >
        <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-3.5 py-2.5">
          <span className="size-2.5 rounded-full bg-rose-400" aria-hidden />
          <span className="size-2.5 rounded-full bg-amber-400" aria-hidden />
          <span className="size-2.5 rounded-full bg-emerald-400" aria-hidden />
          <span className="ml-2 min-w-0 flex-1 truncate rounded-md bg-white px-2.5 py-1 font-mono text-[11px] text-slate-500 ring-1 ring-slate-200">
            rotam.etutkoc.com{shot.url}
          </span>
        </div>
        <Image
          src={shot.src}
          alt={shot.alt}
          width={shot.width}
          height={shot.height}
          priority={priority}
          sizes={sizes}
          className="h-auto w-full"
        />
      </a>
      <figcaption className="mt-3 text-center text-xs text-slate-500">{shot.alt}</figcaption>
    </figure>
  );
}

function Hero({ content }: { content: FeaturePageContent }) {
  return (
    <section className="relative overflow-hidden bg-slate-950 text-white">
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.12]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgb(255 255 255 / 0.5) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.5) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
          maskImage: "radial-gradient(ellipse 80% 70% at 50% 30%, black, transparent)",
        }}
        aria-hidden
      />
      <div className="pointer-events-none absolute -left-40 -top-40 size-[34rem] rounded-full bg-cyan-500/30 blur-3xl" aria-hidden />
      <div className="pointer-events-none absolute -bottom-48 right-0 size-[30rem] rounded-full bg-amber-400/20 blur-3xl" aria-hidden />

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 pb-20 pt-12 sm:px-6 lg:grid-cols-12 lg:gap-10 lg:px-8 lg:pb-28 lg:pt-20">
        <div className="lg:col-span-5">
          <nav aria-label="Konum" className="mb-6 text-xs text-slate-400">
            <Link href="/" className="hover:text-white">Etütkoç Rotam</Link>
            <span className="mx-1.5">/</span>
            <span className="text-slate-200">{content.eyebrow}</span>
          </nav>
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-cyan-200 ring-1 ring-white/15">
            <Sparkles className="size-3.5 text-amber-300" aria-hidden /> {content.eyebrow}
          </span>
          <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-5xl">
            {content.h1}
          </h1>
          <p className="mt-6 text-lg leading-relaxed text-slate-300">{content.lead}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/signup/teacher"
              className="inline-flex items-center gap-2 rounded-full bg-amber-400 px-6 py-3.5 text-sm font-bold text-slate-950 shadow-lg shadow-amber-500/25 transition hover:-translate-y-0.5 hover:bg-amber-300"
            >
              14 gün ücretsiz dene <ArrowRight className="size-4" aria-hidden />
            </Link>
            <Link
              href="/demos"
              className="inline-flex items-center gap-2 rounded-full bg-white/10 px-6 py-3.5 text-sm font-semibold text-white ring-1 ring-white/20 transition hover:bg-white/15"
            >
              <PlayCircle className="size-4" aria-hidden /> Videoyu izle
            </Link>
          </div>
          <p className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <span>Kredi kartı istenmez</span>
            <span aria-hidden>·</span>
            <a href={PLAY_STORE_URL} className="inline-flex items-center gap-1 text-slate-300 hover:text-white">
              <Smartphone className="size-3.5" aria-hidden /> Android uygulaması
            </a>
          </p>
        </div>
        <div className="lg:col-span-7">
          <div className="relative">
            <div className="absolute -inset-4 rounded-[2rem] bg-gradient-to-tr from-cyan-500/30 via-transparent to-amber-400/30 blur-2xl" aria-hidden />
            <BrowserShot
              shot={content.heroImage}
              priority
              sizes="(min-width: 1024px) 760px, 100vw"
              className="relative [&_figcaption]:text-slate-400"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function Highlights({ items }: { items: FeaturePageContent["highlights"] }) {
  return (
    <section className="relative z-10 -mt-12 px-4 sm:px-6 lg:px-8">
      <div className="mx-auto grid max-w-7xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((h, i) => (
          <div key={h.title} className="flex gap-3.5 rounded-2xl border border-slate-200 bg-white p-5 shadow-lg shadow-slate-900/5">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-cyan-700 font-display text-sm font-bold text-white">
              {i + 1}
            </span>
            <div>
              <div className="font-semibold leading-snug text-slate-900">{h.title}</div>
              <p className="mt-1 text-sm leading-relaxed text-slate-600">{h.text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Section({ s, flip }: { s: FeatureSection; flip: boolean }) {
  return (
    <section id={s.id} className="scroll-mt-20 overflow-x-clip">
      <div
        className={cn(
          "mx-auto grid max-w-7xl items-center gap-10 px-4 py-16 sm:px-6 lg:gap-16 lg:px-8 lg:py-24",
          s.image ? "lg:grid-cols-12" : "",
        )}
      >
        <div className={cn(s.image ? "lg:col-span-5" : "max-w-3xl", flip && s.image ? "lg:order-2" : "")}>
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">{s.kicker}</div>
          <h2 className="mt-3 font-display text-3xl font-bold leading-tight tracking-tight text-slate-900 sm:text-4xl">
            {s.title}
          </h2>
          <div className="mt-5 space-y-4 text-[16px] leading-relaxed text-slate-600">
            {s.body.map((p) => (
              <p key={p.slice(0, 48)}>{p}</p>
            ))}
          </div>
          {s.bullets ? (
            <ul className="mt-6 space-y-3">
              {s.bullets.map((b) => (
                <li key={b} className="flex items-start gap-3 text-[15px] leading-snug text-slate-700">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
                    <Check className="size-3" aria-hidden strokeWidth={3} />
                  </span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        {s.image ? (
          <div className={cn("lg:col-span-7", flip ? "lg:order-1" : "")}>
            <div className="relative">
              <div
                className={cn(
                  "absolute -inset-6 rounded-[2.5rem] blur-2xl",
                  flip ? "bg-amber-200/30" : "bg-cyan-200/35",
                )}
                aria-hidden
              />
              <BrowserShot shot={s.image} className="relative" />
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export function FeaturePage({ content }: { content: FeaturePageContent }) {
  return (
    <div className="force-light min-h-screen text-slate-900">
      <JsonLd content={content} />
      <SiteHeader />

      <main>
        <Hero content={content} />
        <Highlights items={content.highlights} />

        <div className="divide-y divide-slate-200/70">
          {content.sections.map((s, i) => (
            <Section key={s.id} s={s} flip={i % 2 === 1} />
          ))}
        </div>

        {/* SSS */}
        <section className="border-t border-slate-200 bg-white">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-12 lg:px-8 lg:py-24">
            <div className="lg:col-span-4">
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">SSS</div>
              <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-slate-900">Sık sorulan sorular</h2>
              <p className="mt-4 text-slate-600">
                Başka bir sorunuz mu var?{" "}
                <Link href="/iletisim" className="font-semibold text-cyan-800 underline-offset-4 hover:underline">
                  Bize yazın
                </Link>
                .
              </p>
            </div>
            <div className="space-y-3 lg:col-span-8">
              {content.faq.map((f) => (
                <details key={f.q} className="group rounded-2xl border border-slate-200 bg-slate-50 p-5 open:bg-white open:shadow-md">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-semibold text-slate-900 [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <ChevronDown className="size-5 shrink-0 text-slate-500 transition group-open:rotate-180" aria-hidden />
                  </summary>
                  <p className="mt-3 text-[15px] leading-relaxed text-slate-600">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* İlgili sayfalar */}
        <section>
          <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <h2 className="font-display text-2xl font-bold text-slate-900">Bunlara da göz atın</h2>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {content.related.map((r) => (
                <Link
                  key={r.href}
                  href={r.href}
                  className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:border-cyan-700/40 hover:shadow-lg"
                >
                  <div className="font-display text-lg font-semibold text-slate-900">{r.title}</div>
                  <p className="mt-2 flex-1 text-sm leading-relaxed text-slate-600">{r.text}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-cyan-800">
                    İncele <ArrowRight className="size-4 transition group-hover:translate-x-1" aria-hidden />
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Son çağrı */}
        <section className="px-4 pb-20 sm:px-6 lg:px-8">
          <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-gradient-to-br from-cyan-800 via-cyan-900 to-slate-950 px-6 py-14 text-center sm:px-12">
            <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-amber-400/25 blur-3xl" aria-hidden />
            <h2 className="relative font-display text-3xl font-bold text-white sm:text-4xl">{content.ctaTitle}</h2>
            <p className="relative mx-auto mt-4 max-w-2xl text-lg text-cyan-100">{content.ctaText}</p>
            <div className="relative mt-8 flex flex-wrap justify-center gap-3">
              <Link
                href="/signup/teacher"
                className="inline-flex items-center gap-2 rounded-full bg-amber-400 px-7 py-3.5 text-sm font-bold text-slate-950 transition hover:-translate-y-0.5 hover:bg-amber-300"
              >
                14 gün ücretsiz başla <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link
                href="/pricing"
                className="rounded-full px-7 py-3.5 text-sm font-semibold text-white ring-1 ring-white/30 transition hover:bg-white/10"
              >
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
