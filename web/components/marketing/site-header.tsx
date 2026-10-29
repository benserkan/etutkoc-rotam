import Link from "next/link";
import {
  Building2,
  Calculator,
  ChevronDown,
  ClipboardList,
  LineChart,
  Menu,
  PlayCircle,
  UserRound,
} from "lucide-react";

import { BrandLogo } from "@/components/brand-logo";
import { YKS_TOOL_URL } from "@/lib/site";

/**
 * Herkese açık sayfaların TEK üst menüsü — ana sayfa, ürün sayfaları ve YKS
 * hesaplama aynı menüyü gösterir (önceden ana sayfa çapa bağlantılı, diğer
 * sayfalar farklı bir liste gösteriyordu). Hook yok: sunucu ve istemci
 * bileşenlerinde kullanılır. Masaüstü açılır menü CSS (hover + focus-within),
 * mobil menü <details> ile çalışır — JavaScript yüklenmeden de açılır.
 */

export const PRODUCT_LINKS = [
  {
    href: "/ogrenci-takip-programi",
    label: "Öğrenci takip programı",
    text: "Kitaba bağlı haftalık program, günlük işaretleme, erken uyarı",
    icon: ClipboardList,
  },
  {
    href: "/deneme-analizi",
    label: "Deneme analizi",
    text: "PDF karneden konu analizi, net fırsatı ve puan tahmini",
    icon: LineChart,
  },
  {
    href: "/kurumlar",
    label: "Kurumlar için",
    text: "Etüt, dershane ve okullar için koç ve öğrenci panosu",
    icon: Building2,
  },
  {
    href: "/bagimsiz-koclar",
    label: "Bağımsız koçlar için",
    text: "Seans, tahsilat, görüşme takvimi ve öğrenci takibi",
    icon: UserRound,
  },
] as const;

export const SITE_NAV = [
  { href: "/#nasil-calisir", label: "Nasıl çalışır?" },
  { href: YKS_TOOL_URL, label: "YKS puan hesaplama", badge: "Ücretsiz" },
  { href: "/pricing", label: "Paketler" },
  { href: "/iletisim", label: "İletişim" },
] as const;

export function SiteHeader() {
  return (
    <header className="force-light sticky top-0 z-40 border-b border-slate-900/10 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <BrandLogo />

        <nav aria-label="Ana menü" className="hidden items-center gap-1 text-sm font-medium text-slate-700 lg:flex">
          <div className="group relative">
            <button
              type="button"
              className="inline-flex items-center gap-1 rounded-full px-3 py-2 transition hover:bg-slate-100 hover:text-slate-900 group-focus-within:bg-slate-100"
            >
              Ürün <ChevronDown className="size-4 transition group-hover:rotate-180" aria-hidden />
            </button>
            <div className="invisible absolute left-0 top-full z-50 w-[min(560px,90vw)] pt-2 opacity-0 transition group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100">
              <div className="grid grid-cols-2 gap-1 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-900/10">
                {PRODUCT_LINKS.map((p) => (
                  <Link key={p.href} href={p.href} className="flex gap-3 rounded-xl p-3 transition hover:bg-cyan-50">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-700 text-white">
                      <p.icon className="size-4.5" aria-hidden />
                    </span>
                    <span>
                      <span className="block font-semibold text-slate-900">{p.label}</span>
                      <span className="mt-0.5 block text-xs leading-snug text-slate-600">{p.text}</span>
                    </span>
                  </Link>
                ))}
                <Link
                  href="/demos"
                  className="col-span-2 flex items-center gap-2 rounded-xl border-t border-slate-200 px-3 py-2.5 text-sm font-semibold text-cyan-800 transition hover:bg-cyan-50"
                >
                  <PlayCircle className="size-4" aria-hidden /> Tanıtım videolarını izle
                </Link>
              </div>
            </div>
          </div>
          {SITE_NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className="inline-flex items-center gap-1.5 rounded-full px-3 py-2 transition hover:bg-slate-100 hover:text-slate-900"
            >
              {n.href === YKS_TOOL_URL ? <Calculator className="size-4 text-cyan-700" aria-hidden /> : null}
              {n.label}
              {"badge" in n ? (
                <span className="rounded-full bg-amber-400 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-900">
                  {n.badge}
                </span>
              ) : null}
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
            className="hidden items-center rounded-full bg-cyan-700 px-3 py-1.5 text-xs font-semibold text-white shadow-sm shadow-cyan-700/20 transition hover:bg-cyan-800 sm:inline-flex sm:px-4 sm:py-2 sm:text-sm"
          >
            Ücretsiz Dene
          </Link>
          <details className="group/m relative lg:hidden">
            <summary
              aria-label="Menüyü aç"
              className="flex size-9 cursor-pointer list-none items-center justify-center rounded-full border border-slate-300 text-slate-800 [&::-webkit-details-marker]:hidden"
            >
              <Menu className="size-5" aria-hidden />
            </summary>
            <div className="absolute right-0 top-full z-50 mt-2 w-[min(340px,calc(100vw-2rem))] rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-900/15">
              <div className="px-3 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">Ürün</div>
              {PRODUCT_LINKS.map((p) => (
                <Link key={p.href} href={p.href} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-900 hover:bg-cyan-50">
                  <p.icon className="size-4 text-cyan-700" aria-hidden /> {p.label}
                </Link>
              ))}
              <div className="my-1 border-t border-slate-200" />
              {SITE_NAV.map((n) => (
                <Link key={n.href} href={n.href} className="flex items-center justify-between rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-900 hover:bg-cyan-50">
                  {n.label}
                  {"badge" in n ? (
                    <span className="rounded-full bg-amber-400 px-1.5 py-0.5 text-[10px] font-bold uppercase text-slate-900">{n.badge}</span>
                  ) : null}
                </Link>
              ))}
              <Link href="/demos" className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold text-cyan-800 hover:bg-cyan-50">
                <PlayCircle className="size-4" aria-hidden /> Tanıtım videoları
              </Link>
              <Link
                href="/signup/teacher"
                className="mt-1 flex items-center justify-center rounded-xl bg-cyan-700 px-3 py-3 text-sm font-semibold text-white"
              >
                14 gün ücretsiz dene
              </Link>
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}
