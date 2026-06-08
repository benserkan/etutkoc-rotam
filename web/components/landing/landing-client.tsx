"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Award,
  BarChart3,
  BookOpen,
  Bot,
  BrainCircuit,
  Building2,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Compass,
  CreditCard,
  Flame,
  Gauge,
  Gift,
  GraduationCap,
  HelpCircle,
  LayoutGrid,
  LifeBuoy,
  LineChart,
  Lock,
  MessageSquareText,
  PlayCircle,
  RotateCcw,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

import {
  getLandingCards,
  landingKeys,
  sendLandingTelemetry,
} from "@/lib/api/landing";
import type { LandingCard, LandingResponse } from "@/lib/types/landing";
import { Reveal } from "@/components/landing/reveal";
import { MockupByType } from "@/components/landing/mockups";
import { demosForRole, demoPlayUrl, type DemoRole } from "@/lib/demos";
import { PricingCards } from "@/components/pricing/pricing-cards";
import { BrandLogo } from "@/components/brand-logo";
import { FloatingWhatsAppAuto } from "@/components/contact/floating-whatsapp-auto";

const NAV = [
  { href: "#ozellikler", label: "Özellikler" },
  { href: "#kurumlar", label: "Kurumlar" },
  { href: "#nasil-calisir", label: "Nasıl Çalışır?" },
  { href: "#izle", label: "İzle" },
  { href: "#paketler", label: "Paketler" },
  { href: "/iletisim", label: "İletişim" },
];

// Kurumsal demo/teklif → /pricing kurumsal formu (zengin: koç sayısı + fayda).
const DEMO_MAIL = "/pricing?type=kurum#kurumsal";

export function LandingClient() {
  const q = useQuery<LandingResponse>({
    queryKey: landingKeys.cards(5, "teacher"),
    queryFn: () => getLandingCards(5, "teacher"),
    staleTime: 60_000,
  });
  const cards = q.data?.cards ?? [];
  const variant = q.data?.variant_slug ?? null;

  return (
    <div className="force-light min-h-screen bg-background text-foreground">
      <Header />
      <Hero />
      <Reassurance />
      <HowItWorks />
      <DemoGallery />
      <Features cards={cards} variant={variant} loading={q.isLoading} />
      <Comparison />
      <Institutions />
      <Pricing />
      <Faq />
      <FinalCta />
      <Footer />
      <div className="h-20 md:hidden" aria-hidden />
      <StickyMobileCta />
      <FloatingWhatsAppAuto />
    </div>
  );
}

/* ───────────────────────── Reassurance band (risk-tersine) ───────────────────────── */

function Reassurance() {
  const items = [
    { icon: Gift, label: "14 gün ücretsiz" },
    { icon: CreditCard, label: "Kredi kartı gerekmez" },
    { icon: RotateCcw, label: "İstediğin an iptal" },
    { icon: ShieldCheck, label: "60 gün performans garantisi" },
    { icon: Lock, label: "KVKK uyumlu" },
  ];
  return (
    <section className="border-y border-cyan-900/15 bg-cyan-50/50">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-7 gap-y-3 px-4 py-4 sm:px-6 lg:px-8">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <span key={it.label} className="inline-flex items-center gap-2 text-sm font-medium text-cyan-900/80">
              <Icon className="size-4 text-cyan-600" aria-hidden />
              {it.label}
            </span>
          );
        })}
      </div>
    </section>
  );
}

/* ───────────────────────── Comparison (problem → çözüm) ───────────────────────── */

function Comparison() {
  const oldWay = [
    "Excel, WhatsApp ve kağıt arasında dağılan takip",
    "Hangi öğrenci nerede kaldı — belirsiz",
    "Veli iletişimi düzensiz, unutulan raporlar",
    "Tükenmişlik ve düşüş geç fark ediliyor",
    "Tekrar planı yok; konular unutuluyor",
  ];
  const newWay = [
    "Plan, takip, tekrar, veli — hepsi tek panelde",
    "Anlık tamamlama ve doğruluk görünürlüğü",
    "Otomatik WhatsApp haftalık veli raporu",
    "Burnout radarı düşüş başlamadan uyarır",
    "FSRS ile bilimsel aralıklı tekrar",
  ];
  return (
    <section className="bg-background py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em] text-amber-600">Neden ETÜTKOÇ</p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Dağınık araçlar mı, <span className="text-cyan-700">tek akış</span> mı?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Koçluğun yükünü araçlar çoğaltmamalı. Aradaki farkı yan yana görün.
          </p>
        </Reveal>
        <div className="grid gap-5 md:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-2xl border border-rose-200 bg-rose-50/40 p-6">
              <p className="mb-4 inline-flex items-center gap-2 font-display text-lg font-bold text-rose-700">
                <XCircle className="size-5" aria-hidden /> Eski yöntem
              </p>
              <ul className="space-y-3">
                {oldWay.map((t) => (
                  <li key={t} className="flex items-start gap-2.5 text-sm text-rose-900/70">
                    <XCircle className="mt-0.5 size-4 shrink-0 text-rose-400" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
          <Reveal delayMs={90}>
            <div className="lp-card relative h-full overflow-hidden rounded-2xl border border-cyan-200 bg-card p-6">
              <div className="pointer-events-none absolute -right-10 -top-10 size-32 rounded-full bg-cyan-500/10 blur-2xl" />
              <p className="mb-4 inline-flex items-center gap-2 font-display text-lg font-bold text-cyan-700">
                <CheckCircle2 className="size-5" aria-hidden /> ETÜTKOÇ ile
              </p>
              <ul className="space-y-3">
                {newWay.map((t) => (
                  <li key={t} className="flex items-start gap-2.5 text-sm">
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-cyan-600" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
              <Link
                href="/signup/teacher"
                className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-cyan-700 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-cyan-800"
              >
                Tek akışa geç <ArrowRight className="size-4" aria-hidden />
              </Link>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── FAQ (itiraz giderme) ───────────────────────── */

function Faq() {
  const items = [
    { q: "Başlamak için kredi kartı gerekiyor mu?", a: "Hayır. 14 gün boyunca tüm Pro özellikleri kart bilgisi vermeden ücretsiz denersiniz. Deneme bitince otomatik ücret alınmaz." },
    { q: "İstediğim zaman iptal edebilir miyim?", a: "Evet, taahhüt yok. Üyeliğinizi tek tıkla istediğiniz an dondurabilir veya iptal edebilirsiniz; yazları kullanmıyorsanız akademik yıl planı otomatik pause olur." },
    { q: "Öğrenci ve veli verileri güvende mi?", a: "Sistem KVKK uyumludur; veriler şifreli saklanır, IP/cihaz bilgileri denetim için hash'lenir. Veli yalnızca özet metrikleri görür; net ve konu detayları paylaşılmaz." },
    { q: "Mevcut kitap ve kaynaklarımı kullanabilir miyim?", a: "Evet. Kendi kitap envanterinizi tanımlar, görevleri bu kaynaklar üzerinden planlarsınız. Hazır şablonlar ve AI önerileri de işinizi hızlandırır." },
    { q: "Kurumsal geçiş nasıl oluyor?", a: "Kurumsal demo talep edersiniz; öğretmen ve öğrencileriniz tek panele taşınır. 60 günlük performans garantisi ile kriterler sağlanmazsa iade hakkınız vardır." },
    { q: "Teknik bilgi gerekiyor mu?", a: "Hayır. Dakikalar içinde öğrenci ekler, hedef belirler ve ilk haftalık programı oluşturursunuz. Arayüz koçlar için tasarlandı." },
  ];
  return (
    <section className="bg-background py-20">
      <div className="mx-auto max-w-3xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mb-10 text-center">
          <p className="mb-3 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.25em] text-amber-600">
            <HelpCircle className="size-3.5" aria-hidden /> Sık sorulanlar
          </p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">Aklınızdaki sorular</h2>
        </Reveal>
        <Reveal className="space-y-3">
          {items.map((it) => (
            <details key={it.q} className="lp-card group rounded-2xl border border-slate-200 bg-card p-5 transition">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-display font-semibold">
                {it.q}
                <ChevronDown className="size-5 shrink-0 text-cyan-600 transition group-open:rotate-180" aria-hidden />
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{it.a}</p>
            </details>
          ))}
        </Reveal>
        <p className="mt-8 text-center text-sm text-muted-foreground">
          Başka sorunuz mu var?{" "}
          <Link href="/iletisim" className="font-medium text-cyan-700 underline-offset-4 hover:underline">
            Bize ulaşın
          </Link>
        </p>
      </div>
    </section>
  );
}

/* ───────────────────────── Sticky mobile CTA ───────────────────────── */

function StickyMobileCta() {
  return (
    <div className="fixed inset-x-0 bottom-0 z-50 border-t border-cyan-900/15 bg-background/95 px-4 py-3 backdrop-blur md:hidden">
      <div className="flex items-center justify-between gap-2">
        <div className="leading-tight">
          <p className="text-sm font-bold text-cyan-900">14 gün ücretsiz</p>
          <p className="text-[11px] text-muted-foreground">Kredi kartı gerekmez</p>
        </div>
        <div className="flex items-center gap-1.5">
          <Link
            href="/login"
            className="inline-flex items-center rounded-full border border-cyan-700/40 px-3 py-2 text-xs font-bold text-cyan-800 hover:bg-cyan-50"
          >
            Giriş
          </Link>
          <Link
            href="/signup/teacher"
            className="inline-flex items-center gap-1 rounded-full bg-cyan-700 px-4 py-2 text-xs font-bold text-white shadow-sm"
          >
            Ücretsiz Dene <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────── Header ───────────────────────── */

function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-cyan-900/15 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <BrandLogo />
        <nav className="hidden items-center gap-7 text-sm font-medium text-muted-foreground md:flex">
          {NAV.map((n) => (
            <a key={n.href} href={n.href} className="transition hover:text-cyan-800">
              {n.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2 sm:gap-2.5">
          <Link
            href="/login"
            className="inline-flex items-center rounded-full border border-cyan-700/30 px-3 py-1.5 text-xs font-semibold text-cyan-800 transition hover:border-cyan-700 hover:bg-cyan-50 sm:px-4 sm:py-2 sm:text-sm"
          >
            Giriş
          </Link>
          <Link
            href="/signup/teacher"
            className="inline-flex items-center gap-1.5 rounded-full bg-cyan-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-cyan-700/20 transition hover:-translate-y-0.5 hover:bg-cyan-800 sm:px-4 sm:py-2 sm:text-sm"
          >
            Ücretsiz Dene
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ───────────────────────── Hero ───────────────────────── */

function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-cyan-50/70 via-background to-background">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_55%_45%_at_100%_0%,theme(colors.amber.400/0.16),transparent_60%),radial-gradient(ellipse_50%_45%_at_0%_85%,theme(colors.cyan.500/0.12),transparent_60%)]" />
      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-12 lg:gap-10 lg:py-24 lg:px-8">
        <Reveal className="lg:col-span-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white/80 px-3 py-1 text-xs font-semibold text-cyan-800 shadow-sm backdrop-blur">
            <Compass className="size-3.5 text-amber-500" aria-hidden />
            Yapay zeka destekli koçluk · KVKK uyumlu
          </span>
          <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
            Öğrencinin başarı{" "}
            <span className="relative whitespace-nowrap text-cyan-700">
              rotasını
              <svg className="absolute -bottom-1 left-0 w-full" viewBox="0 0 200 8" fill="none" preserveAspectRatio="none" aria-hidden>
                <path d="M2 5.5C40 2 160 2 198 5.5" stroke="#EBA62E" strokeWidth="3" strokeLinecap="round" />
              </svg>
            </span>{" "}
            veriyle çizin.
            <span className="mt-3 block text-2xl font-bold text-muted-foreground sm:text-3xl">
              LGS ve YKS koçluğunda yapay zeka dönemi.
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            Saniyeler içinde kişiselleştirilmiş haftalık programlar oluşturun,{" "}
            <b className="text-foreground">kaynak bitirme oranlarını</b> anlık izleyin.
            Bilimsel tekrar sistemiyle unutmayı engelleyin,{" "}
            <b className="text-foreground">tükenmişlik radarıyla</b> sınav sürecini güvenle yönetin.
          </p>
          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              href="/signup/teacher"
              className="inline-flex items-center gap-2 rounded-full bg-cyan-700 px-7 py-3.5 font-semibold text-white shadow-lg shadow-cyan-700/25 transition hover:-translate-y-0.5 hover:bg-cyan-800"
            >
              <Sparkles className="size-4 text-amber-300" aria-hidden /> 14 Gün Ücretsiz Dene
            </Link>
            <a
              href={DEMO_MAIL}
              className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white px-7 py-3.5 font-semibold text-cyan-800 transition hover:-translate-y-0.5 hover:border-cyan-300 hover:shadow-md"
            >
              Kurumsal Demo <ArrowRight className="size-4" aria-hidden />
            </a>
          </div>
          <div className="mt-7 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Check className="size-4 text-cyan-600" aria-hidden /> Dakikalar içinde kurulum
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Sparkles className="size-4 text-amber-500" aria-hidden /> Yapay zeka önerili planlama
            </span>
          </div>
        </Reveal>

        <Reveal className="lg:col-span-6" delayMs={120}>
          <HeroMock />
        </Reveal>
      </div>
    </section>
  );
}

function HeroMock() {
  const days = ["Pz", "Sa", "Ça", "Pe", "Cu", "Ct", "Pa"];
  const hours = ["06", "09", "12", "15", "18", "21", "00", "03"];
  const grid = [
    [0.2, 0.1, 0.6, 0.95, 0.8, 0.45, 0.1, 0],
    [0.15, 0.25, 0.85, 0.75, 0.9, 0.55, 0.15, 0],
    [0.1, 0.05, 0.5, 0.95, 1, 0.65, 0.2, 0],
    [0.25, 0.3, 0.7, 0.85, 0.95, 0.4, 0.05, 0],
    [0.15, 0.2, 0.55, 0.8, 0.75, 0.3, 0.1, 0],
    [0.05, 0.4, 0.65, 0.6, 0.55, 0.85, 0.95, 0.45],
    [0.1, 0.45, 0.5, 0.4, 0.35, 0.3, 0.5, 0.2],
  ];
  return (
    <div className="relative">
      <div className="overflow-hidden rounded-2xl border border-cyan-900/15 bg-card shadow-2xl shadow-cyan-900/10">
        <div className="flex items-center gap-1.5 border-b border-border bg-cyan-50/60 px-4 py-2.5">
          <span className="size-2.5 rounded-full bg-rose-400" />
          <span className="size-2.5 rounded-full bg-amber-400" />
          <span className="size-2.5 rounded-full bg-cyan-400" />
          <span className="ml-2 font-mono text-xs text-muted-foreground">rotam.etutkoc.com/teacher</span>
        </div>
        <div className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                Çalışma DNA&apos;sı · Son 7 gün
              </p>
              <p className="font-display text-lg font-bold">Ayşe K. · 8. sınıf</p>
            </div>
            <span className="rounded-full bg-cyan-50 px-2.5 py-1 text-xs font-semibold text-cyan-700 ring-1 ring-cyan-200">LGS Hedef</span>
          </div>
          <div className="grid grid-cols-9 gap-1">
            <div />
            {hours.map((h) => (
              <div key={h} className="text-center font-mono text-[8px] text-muted-foreground">{h}</div>
            ))}
            {grid.map((row, di) => (
              <React.Fragment key={di}>
                <div className="flex items-center text-[9px] font-bold text-muted-foreground">{days[di]}</div>
                {row.map((v, hi) => (
                  <div
                    key={hi}
                    className="h-4 rounded-sm"
                    style={{ background: v === 0 ? "var(--muted)" : `rgba(14,116,144,${v})` }}
                  />
                ))}
              </React.Fragment>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-border pt-3 text-sm">
            <span className="inline-flex items-center gap-1.5">
              <Flame className="size-4 text-amber-500" aria-hidden /> <b>12 gün</b>{" "}
              <span className="text-xs text-muted-foreground">streak</span>
            </span>
            <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-bold text-amber-700 ring-1 ring-amber-200">+285 puan</span>
          </div>
        </div>
      </div>

      <div className="absolute -bottom-5 -left-4 hidden w-60 rounded-xl border border-cyan-900/15 bg-card p-3 shadow-xl lg:block">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-rose-50 text-rose-600">
            <Gauge className="size-4" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-bold text-rose-700">Tükenmişlik riski · 73/100</p>
            <p className="text-[10px] text-muted-foreground">Gece kuşu + mola yok</p>
          </div>
        </div>
      </div>
      <div className="absolute -right-4 -top-5 hidden w-56 rounded-xl border border-cyan-900/15 bg-card p-3 shadow-xl lg:block">
        <div className="flex items-center gap-2">
          <span className="flex size-8 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700">
            <MessageSquareText className="size-4" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-[11px] font-bold text-cyan-700">Veli · WhatsApp</p>
            <p className="text-[10px] text-muted-foreground">&quot;Süper iş!&quot;</p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────── Features (temiz showcase) ───────────────────────── */

const MOCKUP_ICON: Record<string, LucideIcon> = {
  daily_schedule: CalendarDays,
  fsrs_rating: BrainCircuit,
  burnout_gauge: Gauge,
  books_progress: BookOpen,
  whatsapp_chat: MessageSquareText,
  gamification: Award,
  ai_assistant: Bot,
  exam_trend: TrendingUp,
  security: ShieldCheck,
  billing: CreditCard,
  analytics: BarChart3,
  crm: Users,
  branding: Building2,
  support: LifeBuoy,
  curriculum: GraduationCap,
};

/** Benefit metninden baştaki emoji/sembolleri temizler (DB verisi emoji ile geliyor). */
function cleanBenefit(s: string): string {
  return s.replace(/^[^\p{L}\p{N}]+/u, "").trim();
}

/** Kart görünürlük telemetrisi (impression + view) — paylaşılan. */
function useCardTelemetry(slug: string, variant: string | null) {
  const ref = React.useRef<HTMLDivElement | null>(null);
  React.useEffect(() => {
    sendLandingTelemetry(slug, "impression", variant);
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) return;
    let viewed = false;
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && e.intersectionRatio >= 0.5 && !viewed) {
          viewed = true;
          sendLandingTelemetry(slug, "view", variant);
          io.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [slug, variant]);
  return ref;
}

function Features({
  cards,
  variant,
  loading,
}: {
  cards: LandingCard[];
  variant: string | null;
  loading: boolean;
}) {
  const hero = cards[0];
  const rest = cards.slice(1);
  return (
    <section id="ozellikler" className="bg-background py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center">
          <p className="mb-3 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.25em] text-amber-600">
            <Sparkles className="size-3.5" aria-hidden /> Uçtan uca koçluk
          </p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Öğrenciyi hedefe taşıyan{" "}
            <span className="text-cyan-700">her şey</span>, tek platformda
          </h2>
          <p className="mt-3 text-muted-foreground">
            Dağınık araçlar yerine; plan, takip, bilimsel tekrar, risk radarı ve veli
            iletişimi — hepsi tek akışta, tek panelde.
          </p>
        </Reveal>

        {loading ? (
          <div className="space-y-6">
            <div className="h-80 animate-pulse rounded-3xl border border-slate-200 bg-white" />
            <div className="grid gap-6 sm:grid-cols-2">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-72 animate-pulse rounded-2xl border border-slate-200 bg-white" />
              ))}
            </div>
          </div>
        ) : cards.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Henüz yayında özellik kartı yok.</p>
        ) : (
          <div className="space-y-6">
            {hero ? <HeroFeature card={hero} variant={variant} /> : null}
            {rest.length > 0 ? (
              <div className="grid gap-6 sm:grid-cols-2">
                {rest.map((c, i) => (
                  <FeatureCard key={c.slug} card={c} variant={variant} index={i} />
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}

function FeatureChecklist({ benefits, accent }: { benefits: string[]; accent: string }) {
  if (benefits.length === 0) return null;
  return (
    <ul className="space-y-2">
      {benefits.map((b) => (
        <li key={b} className="flex items-start gap-2.5 text-sm">
          <Check className="mt-0.5 size-4 shrink-0" style={{ color: accent }} aria-hidden />
          <span className="text-foreground/80">{cleanBenefit(b)}</span>
        </li>
      ))}
    </ul>
  );
}

function DemoLink({
  card,
  variant,
  accent,
}: {
  card: LandingCard;
  variant: string | null;
  accent: string;
}) {
  if (!card.demo_slug) return null;
  return (
    <a
      href={`/demos?play=${encodeURIComponent(card.demo_slug)}`}
      onClick={() => sendLandingTelemetry(card.slug, "demo_click", variant)}
      className="inline-flex items-center gap-1.5 text-sm font-semibold transition hover:gap-2"
      style={{ color: accent }}
    >
      <PlayCircle className="size-4" aria-hidden /> Demo İzle
      {card.demo_duration_label ? (
        <span className="text-xs font-normal text-muted-foreground">· {card.demo_duration_label}</span>
      ) : null}
    </a>
  );
}

function HeroFeature({ card, variant }: { card: LandingCard; variant: string | null }) {
  const accent = card.accent_color || "#0e7490";
  const ref = useCardTelemetry(card.slug, variant);
  const Icon = (card.mockup_type && MOCKUP_ICON[card.mockup_type]) || Sparkles;
  return (
    <Reveal>
      <div
        ref={ref}
        className="lp-card relative overflow-hidden rounded-3xl border border-slate-200 bg-card p-6 transition lg:p-9"
      >
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div className="min-w-0">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex size-12 items-center justify-center rounded-2xl" style={{ background: `${accent}16`, color: accent }}>
                <Icon className="size-6" aria-hidden />
              </span>
              <span className="text-xs font-bold uppercase tracking-wider" style={{ color: accent }}>
                {card.category_label}
              </span>
            </div>
            <h3 className="font-display text-2xl font-bold leading-tight lg:text-3xl">{card.title}</h3>
            <p
              className="mt-3 text-base leading-relaxed text-muted-foreground [&_strong]:font-semibold [&_strong]:text-foreground"
              dangerouslySetInnerHTML={{ __html: card.tagline }}
            />
            <div className="mt-5">
              <FeatureChecklist benefits={card.benefits} accent={accent} />
            </div>
            <div className="mt-6">
              <DemoLink card={card} variant={variant} accent={accent} />
            </div>
          </div>
          {card.mockup_type ? (
            <div className="relative">
              <div className="pointer-events-none absolute -inset-6 rounded-[2rem] opacity-40 blur-2xl" style={{ background: `${accent}22` }} />
              <div className="relative">
                <MockupByType type={card.mockup_type} />
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </Reveal>
  );
}

function FeatureCard({
  card,
  variant,
  index,
}: {
  card: LandingCard;
  variant: string | null;
  index: number;
}) {
  const accent = card.accent_color || "#0e7490";
  const ref = useCardTelemetry(card.slug, variant);
  const Icon = (card.mockup_type && MOCKUP_ICON[card.mockup_type]) || Sparkles;
  return (
    <Reveal delayMs={index * 80}>
      <div
        ref={ref}
        className="lp-card group flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-card p-6 transition hover:-translate-y-1 hover:border-cyan-300"
      >
        <div className="mb-3 flex items-center gap-3">
          <span className="flex size-11 items-center justify-center rounded-xl" style={{ background: `${accent}16`, color: accent }}>
            <Icon className="size-5" aria-hidden />
          </span>
          <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: accent }}>
            {card.category_label}
          </span>
        </div>
        <h3 className="font-display text-lg font-bold">{card.title}</h3>
        <p
          className="mt-2 text-sm leading-relaxed text-muted-foreground [&_strong]:font-semibold [&_strong]:text-foreground"
          dangerouslySetInnerHTML={{ __html: card.tagline }}
        />
        {card.mockup_type ? (
          <div className="my-5 rounded-xl bg-slate-50/80 p-3 ring-1 ring-slate-100">
            <MockupByType type={card.mockup_type} />
          </div>
        ) : null}
        <div className="mt-auto space-y-4">
          <FeatureChecklist benefits={card.benefits} accent={accent} />
          <DemoLink card={card} variant={variant} accent={accent} />
        </div>
      </div>
    </Reveal>
  );
}

/* ───────────────────────── Institutions (B2B) ───────────────────────── */

function Institutions() {
  // Kurum bandı kartları feature_catalog'tan (audience=institution_admin) —
  // admin'den düzenlenebilir; statik değil.
  const instQ = useQuery<LandingResponse>({
    queryKey: landingKeys.cards(6, "institution_admin"),
    queryFn: () => getLandingCards(6, "institution_admin"),
    staleTime: 60_000,
  });
  const instCards = instQ.data?.cards ?? [];
  const teachers = ["A. Yılmaz", "B. Demir", "C. Kaya", "D. Çelik", "E. Şahin", "F. Arslan"];
  const heat = [
    [0.95, 0.9, 0.85, 0.95, 1, 0.9, 0.85, 0.95, 0.9, 1, 0.95, 0.85],
    [0.8, 0.75, 0.85, 0.7, 0.8, 0.75, 0.85, 0.8, 0.75, 0.85, 0.8, 0.75],
    [0.45, 0.55, 0.5, 0.6, 0.55, 0.5, 0.55, 0.6, 0.5, 0.55, 0.6, 0.55],
    [0.85, 0.9, 0.95, 0.85, 0.9, 0.95, 1, 0.95, 0.9, 0.95, 1, 0.95],
    [0.3, 0.25, 0.2, 0.3, 0.25, 0.15, 0.1, 0.2, 0.15, 0.1, 0.05, 0],
    [0.7, 0.75, 0.8, 0.75, 0.85, 0.8, 0.75, 0.85, 0.8, 0.9, 0.85, 0.8],
  ];
  const cells = (v: number) =>
    v < 0.15 ? "rgba(244,63,94,0.85)" : v < 0.4 ? "rgba(245,158,11,0.75)" : `rgba(45,212,191,${Math.max(v, 0.25)})`;
  const mini = [
    { icon: LayoutGrid, title: "Kohort Karşılaştırması", desc: "4 sekme: sınıf, alan, müfredat, hedef sınav. Hafta-hafta değişim." },
    { icon: BarChart3, title: "Öğretmen Isı Haritası", desc: "4-12 hafta heatmap ile pasif öğretmenleri bir bakışta görün." },
    { icon: Target, title: "Risk Altındaki Öğrenciler", desc: "Kurum geneli düşüş sinyali · öğretmen-öğrenci eşlemesiyle." },
    { icon: ShieldCheck, title: "60 Gün Garanti", desc: "Performans kriterleri sağlanmazsa iade hakkı." },
  ];
  return (
    <section id="kurumlar" className="relative overflow-hidden bg-cyan-950 py-20 text-white lg:py-24">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_25%,theme(colors.amber.400/0.14),transparent_45%),radial-gradient(circle_at_85%_80%,theme(colors.cyan.400/0.16),transparent_50%)]" />
      <div className="relative mx-auto grid max-w-7xl items-start gap-10 px-4 sm:px-6 lg:grid-cols-12 lg:px-8">
        <Reveal className="lg:col-span-5">
          <span className="inline-flex items-center gap-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-amber-200">
            <span className="size-1.5 rounded-full bg-amber-400 shadow-[0_0_8px] shadow-amber-400" />
            Kurumlar için
          </span>
          <h2 className="mt-4 font-display text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
            Kurumunuzun başarısını{" "}
            <span className="bg-gradient-to-r from-amber-300 to-amber-500 bg-clip-text text-transparent">
              tek panelden
            </span>{" "}
            yönetin.
          </h2>
          <p className="mt-5 text-base leading-relaxed text-cyan-50/80">
            Kohort karşılaştırmaları, öğretmen aktivite ısı haritaları ve kurum geneli{" "}
            <b className="text-white">Risk Altındaki Öğrenciler</b> paneliyle kaliteyi standartlaştırın.{" "}
            <b className="text-amber-300">60 günlük performans garantisi</b> ile risk almadan geçin.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <a href={DEMO_MAIL} className="inline-flex items-center gap-2 rounded-full bg-amber-400 px-6 py-3 font-semibold text-cyan-950 shadow-lg transition hover:-translate-y-0.5 hover:brightness-105">
              Kurumsal Demo <ArrowRight className="size-4" aria-hidden />
            </a>
            <a href="#paketler" className="inline-flex items-center rounded-full border border-white/25 px-6 py-3 font-semibold transition hover:bg-white/10">
              Kurumsal Paketi İncele
            </a>
          </div>
          <div className="mt-8 grid grid-cols-3 gap-4 border-t border-white/10 pt-6">
            {[["4", "Kohort sekmesi"], ["12 hf.", "Heatmap penceresi"], ["60 gün", "Garanti"]].map(([n, l]) => (
              <div key={l}>
                <div className="font-display text-2xl font-bold text-amber-300">{n}</div>
                <div className="mt-0.5 text-[11px] font-semibold uppercase tracking-wider text-cyan-100/55">{l}</div>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal className="lg:col-span-7" delayMs={120}>
          <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 shadow-2xl backdrop-blur">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber-300/85">Öğretmen Aktivite Isı Haritası</p>
                <p className="font-display font-bold">Son 12 hafta · 6 öğretmen</p>
              </div>
              <span className="rounded-md border border-amber-400/30 bg-amber-400/15 px-2 py-1 text-[10px] font-bold text-amber-200">CANLI</span>
            </div>
            <div className="space-y-1">
              {heat.map((row, ri) => (
                <div key={ri} className="flex items-center gap-1.5">
                  <span className="w-16 shrink-0 truncate text-[9px] font-semibold text-cyan-100/65">{teachers[ri]}</span>
                  <div className="grid flex-1 grid-cols-12 gap-1">
                    {row.map((v, ci) => (
                      <div key={ci} className="h-3 rounded-sm" style={{ background: cells(v) }} />
                    ))}
                  </div>
                  {ri === 4 ? (
                    <span className="rounded border border-rose-400/30 bg-rose-500/20 px-1.5 py-0.5 text-[9px] font-bold text-rose-300">PASİF</span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {(instCards.length > 0
              ? instCards.map((c) => ({
                  key: c.slug,
                  Icon: MOCKUP_ICON[c.mockup_type ?? ""] ?? Target,
                  title: c.title,
                  desc: c.tagline,
                  label: c.category_label,
                }))
              : mini.map((m) => ({
                  key: m.title, Icon: m.icon, title: m.title, desc: m.desc, label: "",
                }))
            ).map((m) => {
              const Icon = m.Icon;
              return (
                <div key={m.key} className="rounded-xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur transition hover:bg-white/[0.08]">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="flex size-8 items-center justify-center rounded-lg bg-amber-400/15 text-amber-300 ring-1 ring-amber-400/25">
                      <Icon className="size-4" aria-hidden />
                    </span>
                    <h3 className="font-display text-sm font-bold">{m.title}</h3>
                  </div>
                  {m.label ? (
                    <span className="mb-1.5 inline-block rounded border border-amber-400/25 bg-amber-400/10 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-amber-200">{m.label}</span>
                  ) : null}
                  <p className="text-xs leading-relaxed text-cyan-100/65">{m.desc}</p>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────── How it works ───────────────────────── */

// Uçtan uca koçluk döngüsü — rol-renkli adımlar (purge-safe explicit sınıflar)
const ROLE_TONE: Record<
  string,
  { label: string; node: string; chip: string; result: string }
> = {
  koc: { label: "Koç", node: "bg-cyan-700 shadow-cyan-700/25", chip: "bg-cyan-50 text-cyan-700 border-cyan-200", result: "text-cyan-700" },
  ogrenci: { label: "Öğrenci", node: "bg-emerald-600 shadow-emerald-600/25", chip: "bg-emerald-50 text-emerald-700 border-emerald-200", result: "text-emerald-700" },
  sistem: { label: "Sistem", node: "bg-violet-600 shadow-violet-600/25", chip: "bg-violet-50 text-violet-700 border-violet-200", result: "text-violet-700" },
  veli: { label: "Veli", node: "bg-amber-500 shadow-amber-500/25", chip: "bg-amber-50 text-amber-700 border-amber-200", result: "text-amber-700" },
  kurum: { label: "Kurum", node: "bg-slate-800 shadow-slate-800/25", chip: "bg-slate-100 text-slate-800 border-slate-300", result: "text-slate-800" },
};

function HowItWorks() {
  const steps: {
    num: string; role: keyof typeof ROLE_TONE; icon: LucideIcon;
    title: string; desc: string; result: string; loop?: boolean;
  }[] = [
    { num: "01", role: "koc", icon: BookOpen, title: "Koç kütüphaneyi kurar",
      desc: "Koç kullandığı kitapları sisteme tanıtır: her kitabın üniteleri ve içindeki test/soru sayıları girilir. Program böylece gerçek bir soru havuzuna dayanır.",
      result: "Çözülecek soru havuzu hazır" },
    { num: "02", role: "koc", icon: CalendarDays, title: "Koç günlük/haftalık programı hazırlar",
      desc: "Her öğrenciye gün gün görev verir (örn. 'Matematik – Üslü Sayılar, 40 soru'). Sistem atanan soruları kitaptan otomatik rezerve eder: aynı sorular iki kez verilmez, her ünitenin kalan kapasitesi anlık görünür.",
      result: "Çakışmasız, takip edilebilir plan" },
    { num: "03", role: "ogrenci", icon: CheckCircle2, title: "Öğrenci günlük uygular",
      desc: "Öğrenci her gün kendi programını açar; bitirdiği görevi 'tamamladım' olarak işaretler ve çözdüğü soruların doğru/yanlış sayısını girer.",
      result: "Günlük uyum + gerçek çözüm verisi" },
    { num: "04", role: "sistem", icon: LineChart, title: "Sistem ölçer",
      desc: "Tamamlama oranı, doğruluk yüzdesi, deneme neti ve çalışma düzeni otomatik hesaplanır; geride kalan veya tempo düşüren öğrenci işaretlenir.",
      result: "Net trendi + erken risk uyarısı" },
    { num: "05", role: "veli", icon: MessageSquareText, title: "Veli bilgilenir",
      desc: "Veliye otomatik bildirim gider; çocuğunun haftalık gidişatını ve net grafiğini kendi panelinden görür — koç tek tek rapor yazmaz.",
      result: "Veli güveni" },
    { num: "06", role: "koc", icon: Sparkles, title: "Koç erkenden müdahale eder",
      desc: "Kopan öğrenci panoda kırmızı yanar; yapay zekâ 'bugün şu öğrenciyle şunu konuş' diye hazırlık verir; görüşmeyle program güncellenir — döngü başa sarar.",
      result: "Zamanında müdahale", loop: true },
    { num: "07", role: "kurum", icon: LayoutGrid, title: "Kurum tek panelden görür",
      desc: "Program uyumu, akademik çıktı ve müdahale merkeziyle tüm koçların sonucunu izler; hangi öğrenci geride, hangi koç sonuç alıyor görür, kaliteyi standartlaştırır.",
      result: "Ölçülebilir kurum başarısı" },
  ];
  return (
    <section id="nasil-calisir" className="relative bg-background py-20">
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-3 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.25em] text-amber-600">
            <Route className="size-3.5" aria-hidden /> Uçtan uca koçluk
          </p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Plandan ölçülebilir başarıya, adım adım
          </h2>
          <p className="mt-3 text-muted-foreground">
            Koçun program hazırlamasıyla başlar, öğrencinin uyumuyla ilerler, kurumun
            çıktıyı görmesiyle döngü tamamlanır.
          </p>
        </Reveal>

        {/* Aktör lejantı */}
        <Reveal className="mb-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
          {(["koc", "ogrenci", "sistem", "veli", "kurum"] as const).map((r) => (
            <span key={r} className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <span className={cn("size-2.5 rounded-full", ROLE_TONE[r].node.split(" ")[0])} />
              {ROLE_TONE[r].label}
            </span>
          ))}
        </Reveal>

        <div className="relative space-y-4">
          {/* dikey rota çizgisi */}
          <div className="pointer-events-none absolute bottom-8 left-[39px] top-8 hidden w-px bg-gradient-to-b from-cyan-300 via-violet-300 to-slate-300 sm:block" />
          {steps.map((s, i) => {
            const Icon = s.icon;
            const tone = ROLE_TONE[s.role];
            return (
              <Reveal key={s.num} delayMs={i * 60}>
                <div className="lp-card relative flex items-start gap-4 rounded-2xl border border-slate-200 bg-card p-5 transition hover:-translate-y-0.5 sm:p-6">
                  <div className={cn("relative z-10 flex size-14 shrink-0 items-center justify-center rounded-2xl text-white shadow-md", tone.node)}>
                    <Icon className="size-6" aria-hidden />
                    <span className="absolute -right-2 -top-2 flex size-6 items-center justify-center rounded-full bg-amber-400 text-[10px] font-bold text-cyan-950 ring-2 ring-background">
                      {s.num}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider", tone.chip)}>
                        {tone.label}
                      </span>
                      {s.loop ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-cyan-600">
                          <RotateCcw className="size-3" aria-hidden /> döngü başa sarar
                        </span>
                      ) : null}
                    </div>
                    <h3 className="mt-1 font-display text-lg font-bold sm:text-xl">{s.title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{s.desc}</p>
                    <p className={cn("mt-2 inline-flex items-center gap-1 text-xs font-semibold", tone.result)}>
                      <ArrowRight className="size-3.5" aria-hidden /> {s.result}
                    </p>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>

        {/* Döngü kapanışı */}
        <Reveal delayMs={120} className="mt-6">
          <div className="flex items-start gap-3 rounded-2xl border border-cyan-200 bg-cyan-50/70 p-5 text-sm text-cyan-900">
            <RotateCcw className="mt-0.5 size-5 shrink-0 text-cyan-700" aria-hidden />
            <p className="leading-relaxed">
              <b>1–5. adımlar her hafta tekrarlanır;</b> öğrenci sürdürülebilir bir tempoda ilerler.
              6. adımda <b>kurum, tüm koçların çıktısını birleşik görür</b> — başarı ölçülebilir, kalite standart olur.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────── Demo galerisi (İzle) ───────────────────────── */

const GALLERY_ROLES: { key: keyof typeof ROLE_TONE; role: DemoRole }[] = [
  { key: "koc", role: "teacher" },
  { key: "ogrenci", role: "student" },
  { key: "veli", role: "parent" },
  { key: "kurum", role: "institution_admin" },
];

/**
 * Anasayfa "Nasıl çalışır — İzle" galerisi (satış-öncesi vitrin).
 * Rol-sekmeli; her rolün demoları registry'den (lib/demos) gelir → /demos?play=.
 * Yeni demo eklenince otomatik listelenir. Telemetri: demo_click.
 */
function DemoGallery() {
  const [active, setActive] = React.useState<keyof typeof ROLE_TONE>("koc");
  const role = GALLERY_ROLES.find((g) => g.key === active)?.role ?? "teacher";
  const demos = demosForRole(role);
  const activeBg = ROLE_TONE[active].node.split(" ")[0];

  return (
    <section id="izle" className="relative bg-slate-50/70 py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-8 max-w-2xl text-center">
          <p className="mb-3 inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.25em] text-cyan-700">
            <PlayCircle className="size-3.5" aria-hidden /> İzleyin
          </p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Üye olmadan, gerçek ekranlardan izleyin
          </h2>
          <p className="mt-3 text-muted-foreground">
            Her rol için kısa demolar — sistemin aşama aşama nasıl çalıştığını görün,
            kararınızı kolaylaştırın. Üyelikten sonra bu demolar panelinizde de
            başucu rehberi olarak durur.
          </p>
        </Reveal>

        {/* Rol sekmeleri */}
        <Reveal className="mb-8 flex flex-wrap items-center justify-center gap-2">
          {GALLERY_ROLES.map((g) => {
            const tone = ROLE_TONE[g.key];
            const isActive = g.key === active;
            const count = demosForRole(g.role).length;
            return (
              <button
                key={g.key}
                type="button"
                onClick={() => setActive(g.key)}
                aria-pressed={isActive}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-4 py-1.5 text-sm font-semibold transition",
                  isActive
                    ? cn("border-transparent text-white shadow", tone.node.split(" ")[0])
                    : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
                )}
              >
                {tone.label}
                <span
                  className={cn(
                    "rounded-full px-1.5 text-[10px] font-bold leading-5",
                    isActive ? "bg-white/25" : "bg-slate-100 text-slate-500",
                  )}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </Reveal>

        {/* Demo kartları */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {demos.map((d, i) => (
            <Reveal key={d.slug} delayMs={(i % 3) * 60}>
              <a
                href={demoPlayUrl(d.slug)}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => sendLandingTelemetry(d.slug, "demo_click", null)}
                className="lp-card group flex h-full items-center gap-3 rounded-2xl border border-slate-200 bg-card p-4 transition hover:-translate-y-0.5"
              >
                <span
                  className={cn(
                    "flex size-11 shrink-0 items-center justify-center rounded-xl text-white shadow-sm",
                    activeBg,
                  )}
                >
                  <PlayCircle className="size-5" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold text-slate-800">
                    {d.title}
                  </span>
                  <span className="text-xs text-slate-500">{d.durationLabel}</span>
                </span>
                <ChevronRight
                  className="size-4 shrink-0 text-slate-400 transition group-hover:translate-x-0.5"
                  aria-hidden
                />
              </a>
            </Reveal>
          ))}
        </div>

        <Reveal delayMs={120} className="mt-8 text-center">
          <a
            href="/demos"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-full bg-cyan-700 px-5 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-cyan-800"
          >
            <PlayCircle className="size-4" aria-hidden /> Tüm demoları aç
          </a>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────── Pricing ───────────────────────── */

function Pricing() {
  return (
    <section id="paketler" className="bg-background py-20">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <Reveal className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-3 text-xs font-bold uppercase tracking-[0.25em] text-amber-600">Üyelik</p>
          <h2 className="font-display text-3xl font-extrabold tracking-tight sm:text-4xl">İhtiyacınıza uygun paketler</h2>
          <p className="mt-3 text-muted-foreground">Bağımsız koç 14 gün ücretsiz · Kurum 30 gün pilot + 60 gün performans garantisi</p>
        </Reveal>

        <PricingCards />

        <div className="mt-10 text-center">
          <Link href="/pricing" className="inline-flex items-center gap-1 text-sm font-medium text-cyan-700 underline-offset-4 hover:underline">
            Tüm plan detaylarını karşılaştır <ChevronRight className="size-4" aria-hidden />
          </Link>
        </div>
      </div>
    </section>
  );
}

/* ───────────────────────── Final CTA + Footer ───────────────────────── */

function FinalCta() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-cyan-700 via-cyan-800 to-cyan-900 py-16 text-white">
      <div className="pointer-events-none absolute -bottom-32 -left-24 size-96 rounded-full bg-amber-400/15 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="relative mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-8 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-5">
          <span className="flex items-center justify-center rounded-2xl bg-white p-2 shadow-lg">
            <Image src="/etutkoc-mark.svg" alt="ETÜTKOÇ" width={56} height={56} className="size-14 object-contain" unoptimized />
          </span>
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-amber-300">ETÜTKOÇ · ROTAM</p>
            <h2 className="font-display text-2xl font-bold leading-snug sm:text-3xl">
              Başarıya giden rotada <span className="text-amber-300">yanınızdayız.</span>
            </h2>
          </div>
        </div>
        <Link
          href="/signup/teacher"
          className="inline-flex items-center gap-2 rounded-full bg-amber-400 px-7 py-3 font-bold text-cyan-950 shadow-lg transition hover:-translate-y-0.5 hover:brightness-105"
        >
          Ücretsiz Dene <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer id="iletisim" className="bg-cyan-950 pt-14 pb-7 text-cyan-100/70">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="mb-10 grid grid-cols-2 gap-8 md:grid-cols-5">
          <div className="col-span-2">
            <div className="mb-4">
              <BrandLogo wordmarkClassName="text-white" />
            </div>
            <p className="max-w-sm text-sm leading-relaxed">
              Koçluk süreçlerinizi dijitalleştiriyor, öğrencinin başarı rotasını birlikte çiziyoruz.
            </p>
            <p className="mt-4 font-mono text-xs text-cyan-200/40">500+ otomatik test ile doğrulandı</p>
          </div>
          <FooterCol title="Platform" links={[["#ozellikler", "Özellikler"], ["#paketler", "Paketler"], ["#nasil-calisir", "Nasıl Çalışır?"], ["#kurumlar", "Kurumlar"]]} />
          <FooterCol title="İletişim" links={[["/iletisim", "Bize ulaşın"], ["/pricing?type=kurum#kurumsal", "Kurumsal teklif"], ["/iletisim?konu=iletisim_destek", "Teknik destek"]]} />
          <FooterCol title="Yasal" links={[["/kvkk", "Kullanım Şartları"], ["/privacy", "Gizlilik Politikası"], ["/kvkk", "KVKK Aydınlatma"]]} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-6 text-xs text-cyan-200/50">
          <p>© 2026 ETÜTKOÇ Rotam · Tüm hakları saklıdır.</p>
          <p className="font-mono">etütkoç · rotam</p>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div>
      <h4 className="mb-4 font-display text-sm font-semibold text-white">{title}</h4>
      <ul className="space-y-2 text-sm">
        {links.map(([href, label], i) => (
          <li key={i}>
            <a href={href} className="transition hover:text-amber-300">{label}</a>
          </li>
        ))}
      </ul>
    </div>
  );
}
