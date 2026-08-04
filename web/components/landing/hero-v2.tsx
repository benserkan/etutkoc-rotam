"use client";

/**
 * Hero v2 — "Rota iş başında" (2026-08-05, tasarım değerlendirmesi turu).
 *
 * Tanı: eski hero (gradyan + stilize mock) "AI şablonu" kokuyordu — insan
 * yüzü yok, gerçek ürün yok, kanıt yok. Rakip taramasından çıkan desenler:
 *   Photomath  → hero'nun KENDİSİ ürünün iş akışını gösterir (scan→solve)
 *   Doping     → gerçek yüz + video oynatma + somut sayı
 *   Kopilot    → dönen kelime + kanıt-görsel + segment çipleri
 *   Udemy      → diyagonal renk bloğu + seri sanat yönetimi
 *   Duolingo   → karakter-güdümlü marka (maskot = insan dokunuşu)
 *
 * ÖZGÜN sentez: Rotam'ın maskotu değil ÇALIŞANI olan bir dijital insan var —
 * Rota. Hero, Rota'yı İŞ BAŞINDA gösteren 9 saniyelik canlı sahne:
 * karne süzülür → Rota okur (konuşma balonu) → GERÇEK panel kırpımları
 * belirir. İddia atmıyoruz; ürünü çalışırken gösteriyoruz. Sahne saf CSS
 * (globals.css hv2-*), görseller gerçek ekran kırpımları (temsili değil —
 * altında dürüstlük notu da var).
 */
import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import {
  ArrowRight,
  BadgeCheck,
  Check,
  FileText,
  Play,
  Sparkles,
  X,
} from "lucide-react";

import { Reveal } from "@/components/landing/reveal";

// Dönen kelimeler — koçun devretmek istediği angarya işler. Fiil öbeği sabit
// ("Rota'ya bırak") → dönen nesne kısa ve somut.
const ROTATING = [
  "Karne okumayı",
  "Veli iletişimini",
  "Yanlış takibini",
  "Program raporunu",
  "Randevu telaşını",
];

const SEGMENTS: { label: string; href: string }[] = [
  { label: "Bağımsız Koç", href: "#paketler" },
  { label: "Etüt Merkezi", href: "#kurumlar" },
  { label: "Dershane", href: "#kurumlar" },
  { label: "Özel Okul", href: "#kurumlar" },
];

// SVG grain — düz gradyanın "AI şablonu" hissini kıran doku (data-uri, istek yok)
const GRAIN =
  "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.5'/%3E%3C/svg%3E\")";

export function HeroV2() {
  const [wi, setWi] = React.useState(0);
  React.useEffect(() => {
    const t = setInterval(() => setWi((i) => (i + 1) % ROTATING.length), 2600);
    return () => clearInterval(t);
  }, []);

  return (
    <section className="relative overflow-hidden bg-[#f7f5f0]">
      {/* Diyagonal cyan blok (Udemy dersi: simetriyi kır) + grain dokusu */}
      <div
        className="pointer-events-none absolute inset-y-0 right-0 hidden w-[46%] bg-gradient-to-br from-cyan-700 via-cyan-800 to-cyan-950 lg:block"
        style={{ clipPath: "polygon(22% 0, 100% 0, 100% 100%, 0 100%)" }}
        aria-hidden
      >
        <div className="absolute inset-0 opacity-[0.07] mix-blend-overlay" style={{ backgroundImage: GRAIN }} />
        <div className="absolute -left-10 top-1/3 size-64 rounded-full bg-amber-400/20 blur-3xl" />
      </div>

      <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 py-14 sm:px-6 lg:grid-cols-12 lg:gap-6 lg:py-20 lg:px-8">
        {/* ── Sol: söz ── */}
        <Reveal className="lg:col-span-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white px-3 py-1 text-xs font-semibold text-cyan-800 shadow-sm">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
            </span>
            Rota çalışıyor — yapay zekâ koç asistanın
          </span>

          <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.06] tracking-tight text-slate-900 sm:text-5xl lg:text-[3.4rem]">
            <span className="relative block h-[1.34em] overflow-hidden">
              {/* key değişince animasyon yeniden başlar — kelime akar */}
              <span key={wi} className="hv2-word relative text-cyan-700">
                {ROTATING[wi]}
                <svg className="absolute left-0 top-[1.02em] w-full" viewBox="0 0 200 8" fill="none" preserveAspectRatio="none" aria-hidden>
                  <path d="M2 5.5C40 1.5 160 2.5 198 5" stroke="#EBA62E" strokeWidth="3.5" strokeLinecap="round" />
                </svg>
              </span>
            </span>
            Rota&apos;ya bırak.
            <span className="mt-2 block text-slate-900">Sen koçluğa odaklan.</span>
          </h1>

          <p className="mt-6 max-w-xl text-lg leading-relaxed text-slate-600">
            Rota deneme karnesini <b className="text-slate-900">40 saniyede</b> konu konu okur,
            veline durumu <b className="text-slate-900">sesli anlatır</b>, yanlışları kapanana
            kadar takip eder. Karar ve dokunuş hep sende kalır.
          </p>

          <div className="mt-7 flex flex-wrap items-center gap-3">
            <Link
              href="/signup/teacher"
              className="inline-flex items-center gap-2 rounded-full bg-cyan-700 px-7 py-3.5 font-semibold text-white shadow-lg shadow-cyan-700/25 transition hover:-translate-y-0.5 hover:bg-cyan-800"
            >
              <Sparkles className="size-4 text-amber-300" aria-hidden /> 14 Gün Ücretsiz Dene
            </Link>
            <a
              href="#izle"
              className="inline-flex items-center gap-2 rounded-full border-2 border-slate-300 bg-white px-6 py-3 font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-cyan-400 hover:text-cyan-800"
            >
              <span className="flex size-7 items-center justify-center rounded-full bg-cyan-700 text-white">
                <Play className="ml-0.5 size-3.5 fill-current" aria-hidden />
              </span>
              Rota&apos;yı izle · 2 dk
            </a>
          </div>

          {/* Kopilot dersi: ziyaretçi ilk 3 saniyede kendini seçsin */}
          <div className="mt-8">
            <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Kimin için?</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {SEGMENTS.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  className="rounded-full border border-slate-300 bg-white px-4 py-1.5 text-sm font-medium text-slate-700 transition hover:border-cyan-400 hover:bg-cyan-50 hover:text-cyan-800"
                >
                  {s.label}
                </a>
              ))}
            </div>
          </div>

          <div className="mt-7 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <Check className="size-4 text-cyan-600" aria-hidden /> Kurulumu birlikte yapıyoruz
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check className="size-4 text-cyan-600" aria-hidden /> Kart istemez · istediğin an iptal
            </span>
            <span className="inline-flex items-center gap-1.5">
              <BadgeCheck className="size-4 text-cyan-600" aria-hidden /> KVKK uyumlu
            </span>
          </div>
        </Reveal>

        {/* ── Sağ: Rota iş başında (9 sn'lik canlı sahne) ── */}
        <Reveal className="lg:col-span-6" delayMs={120}>
          <div className="rounded-3xl bg-gradient-to-br from-cyan-700 via-cyan-800 to-cyan-950 p-4 pb-8 sm:p-6 lg:rounded-none lg:bg-none lg:p-0">
            <RotaScene />
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/** Karne → Rota → analiz kartları. Zamanlama globals.css hv2-*.
 *
 * v3 (kullanıcı geri bildirimi): ham ekran kırpımları küçükte okunmuyordu ve
 * karmaşıktı → kartlar TASARLANMIŞ vinyetler oldu (Photoshop-tasarımcı
 * yaklaşımı): büyük punto, 2-3 bilgi, renkli durum çubukları. İçerikteki HER
 * DEĞER gerçek üründen (Elif'in gerçek karne importu: 120 soru, net 11,33,
 * Üslü İfadeler zayıflığı; Rota veli yorumunun gerçek cümle kalıbı). Portre
 * büyüdü + köşesinde ▶ rozeti (tanıtım videosunu modalda açar). */
function RotaScene() {
  const [videoOpen, setVideoOpen] = React.useState(false);
  return (
    <div className="relative mx-auto h-[500px] w-full max-w-[560px] select-none sm:h-[540px]">
      {/* Rota portresi — sahnenin yıldızı (büyütüldü) + oynat rozeti */}
      <div className="absolute right-0 top-0 z-20 w-[225px] sm:w-[270px]">
        <button
          type="button"
          onClick={() => setVideoOpen(true)}
          className="group relative block w-full cursor-pointer"
          aria-label="Rota'nın 2 dakikalık tanıtımını izle"
        >
          <span className="hv2-ring block overflow-hidden rounded-3xl border-4 border-white shadow-2xl shadow-cyan-950/30 [transform:rotate(2deg)]">
            <Image
              src="/static/landing/rota-portre.jpg"
              alt="Rota — Rotam'ın yapay zekâ koç asistanı"
              width={540}
              height={540}
              className="block h-auto w-full transition group-hover:scale-[1.03]"
              priority
              unoptimized
            />
          </span>
          <span className="absolute -bottom-2 -right-2 flex items-center gap-1.5 rounded-full bg-amber-400 py-1.5 pl-2 pr-3 shadow-lg ring-4 ring-white transition group-hover:scale-105 [transform:rotate(2deg)]">
            <span className="flex size-6 items-center justify-center rounded-full bg-amber-950/90 text-white">
              <Play className="ml-0.5 size-3 fill-current" aria-hidden />
            </span>
            <span className="text-xs font-bold text-amber-950">2 dk izle</span>
          </span>
        </button>
        <div className="mx-auto -mt-3 w-fit rounded-full border border-cyan-100 bg-white px-3 py-1 text-center shadow-md [transform:rotate(2deg)]">
          <p className="text-xs font-bold text-slate-900">
            Rota <span className="font-medium text-slate-500">· koç asistanın</span>
          </p>
        </div>
      </div>

      {/* Konuşma balonları — sahneyle senkron, anlamlı tam cümleler */}
      <div className="absolute left-0 top-0 z-30 w-[200px] sm:left-2 sm:w-64">
        <Bubble cls="hv2-bubble-1">
          Koçum karne yükledi — <b>120 soruyu</b> tek tek okuyorum
          <span className="ml-0.5 inline-flex">
            <span className="hv2-dot">.</span><span className="hv2-dot">.</span><span className="hv2-dot">.</span>
          </span>
        </Bubble>
        <Bubble cls="hv2-bubble-2">
          Bitti: her soruyu <b>konusuyla eşledim</b>. Üslü İfadeler&apos;de 3 yanlış
          var — programa tekrar ekledim.
        </Bubble>
        <Bubble cls="hv2-bubble-3">
          Veliye de <b>sesli anlattım</b>: &quot;Elif iyi gidiyor, matematikte küçük
          bir eksik kaldı.&quot;
        </Bubble>
      </div>

      {/* Faz A — karne dosyası Rota'ya süzülür */}
      <div className="hv2-scene-karne absolute left-2 top-[195px] z-10 w-64 rounded-xl border border-slate-200 bg-white p-3.5 shadow-xl">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-rose-50 text-rose-500">
            <FileText className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">karekok-lgs-deneme-3.pdf</p>
            <p className="text-[11px] text-slate-500">Koç yükledi · deneme karnesi</p>
          </div>
        </div>
        <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full w-2/3 rounded-full bg-cyan-600" />
        </div>
        <p className="mt-1 text-right text-[10px] font-medium text-cyan-700">Rota okuyor…</p>
      </div>

      {/* Faz B — TASARLANMIŞ analiz vinyeti (gerçek verilerle, büyük punto) */}
      <div className="hv2-scene-crop1 absolute bottom-10 left-0 z-10 w-[330px] max-w-[92%] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl sm:w-[360px]">
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-2">
          <span className="text-xs font-bold text-slate-700">Deneme analizi hazır</span>
          <span className="rounded-full bg-cyan-100 px-2 py-0.5 text-[10px] font-bold text-cyan-800">40 saniye</span>
        </div>
        <div className="p-4">
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-semibold text-slate-900">Karekök LGS-3</p>
            <p className="font-display text-2xl font-extrabold text-slate-900">
              11,33 <span className="text-xs font-semibold text-slate-500">net</span>
            </p>
          </div>
          <div className="mt-3 space-y-2">
            <TopicRow name="Çarpanlar ve Katlar" pct={100} tone="emerald" note="tam" />
            <TopicRow name="Kareköklü İfadeler" pct={66} tone="amber" note="1 boş" />
            <TopicRow name="Üslü İfadeler" pct={25} tone="rose" note="3 yanlış" />
          </div>
          <p className="mt-3 rounded-lg bg-cyan-50 px-3 py-2 text-[12px] font-medium leading-snug text-cyan-900">
            <Sparkles className="mr-1 inline size-3.5 text-amber-500" aria-hidden />
            Üslü İfadeler haftalık programa <b>tekrar olarak eklendi</b>.
          </p>
        </div>
      </div>

      {/* Faz C — TASARLANMIŞ veli vinyeti (sesli anlatım oynatıcısı) */}
      <div className="hv2-scene-crop2 absolute bottom-10 left-4 z-10 w-[330px] max-w-[92%] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl sm:w-[360px]">
        <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-4 py-2">
          <span className="text-xs font-bold text-slate-700">Veli uygulaması</span>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">az önce</span>
        </div>
        <div className="p-4">
          <div className="flex items-center gap-3">
            <Image
              src="/static/landing/rota-portre.jpg"
              alt=""
              width={44}
              height={44}
              className="size-11 shrink-0 rounded-full border-2 border-cyan-200 object-cover"
              unoptimized
            />
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900">Rota&apos;nın sesli yorumu</p>
              <p className="text-[11px] text-slate-500">Elif&apos;in bu haftası · 1 dk 42 sn</p>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2.5 rounded-xl bg-cyan-700 px-3.5 py-2.5">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white text-cyan-800">
              <Play className="ml-0.5 size-3.5 fill-current" aria-hidden />
            </span>
            <span className="flex h-6 flex-1 items-center gap-[3px]" aria-hidden>
              {[9, 14, 8, 18, 12, 20, 10, 16, 7, 13, 17, 9, 15, 11, 19, 8, 12, 6].map((h, i) => (
                <span key={i} className="w-[3px] rounded-full bg-cyan-200/80" style={{ height: `${h}px` }} />
              ))}
            </span>
            <span className="text-[11px] font-bold text-cyan-100">0:00</span>
          </div>
          <p className="mt-3 text-[12px] leading-snug text-slate-600">
            &quot;Elif bu hafta 13 görevden 10&apos;unu bitirdi. Matematikte Üslü
            İfadeler&apos;i birlikte tekrar edeceğiz…&quot;
          </p>
        </div>
      </div>

      {/* Dürüstlük imzası — değerler gerçek üründen */}
      <p className="absolute -bottom-4 left-0 z-10 inline-flex items-center gap-1.5 text-[11px] font-medium text-cyan-100/90 lg:-bottom-1 lg:text-slate-400">
        <ArrowRight className="size-3 -rotate-45" aria-hidden />
        Sahnedeki tüm sayılar gerçek üründen — tamamı için tanıtımı izle
      </p>

      {/* ▶ rozeti → tanıtım videosu modalı */}
      {videoOpen ? (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={() => setVideoOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-label="Rotam tanıtım videosu"
        >
          <div
            className="relative w-full max-w-3xl overflow-hidden rounded-2xl bg-black shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              onClick={() => setVideoOpen(false)}
              className="absolute right-3 top-3 z-10 flex size-9 items-center justify-center rounded-full bg-black/60 text-white transition hover:bg-black/80"
              aria-label="Videoyu kapat"
            >
              <X className="size-5" aria-hidden />
            </button>
            <video
              src="/static/video/rotam-tanitim.mp4"
              controls
              autoPlay
              playsInline
              className="block aspect-video w-full"
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Analiz vinyetindeki konu satırı — büyük punto, renkli durum çubuğu. */
function TopicRow({
  name, pct, tone, note,
}: {
  name: string; pct: number; tone: "emerald" | "amber" | "rose"; note: string;
}) {
  const bar = tone === "emerald" ? "bg-emerald-500" : tone === "amber" ? "bg-amber-400" : "bg-rose-500";
  const chip = tone === "emerald"
    ? "bg-emerald-50 text-emerald-700"
    : tone === "amber"
      ? "bg-amber-50 text-amber-700"
      : "bg-rose-50 text-rose-700";
  return (
    <div>
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-semibold text-slate-800">{name}</p>
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${chip}`}>{note}</span>
      </div>
      <div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${bar}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Bubble({ cls, children }: { cls: string; children: React.ReactNode }) {
  return (
    <div className={`${cls} absolute left-0 top-0 w-full`}>
      <div className="relative rounded-2xl rounded-tl-sm border border-cyan-100 bg-white px-3.5 py-2.5 text-[13px] font-medium leading-snug text-slate-800 shadow-lg">
        {children}
        <span className="absolute -left-1.5 top-3 size-3 rotate-45 border-b border-l border-cyan-100 bg-white" aria-hidden />
      </div>
    </div>
  );
}
