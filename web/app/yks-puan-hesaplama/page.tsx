import type { Metadata } from "next";
import Link from "next/link";
import { Activity, Database, Lock, Sparkles } from "lucide-react";

import { SiteHeader } from "@/components/marketing/site-header";
import { LandingFooter } from "@/components/landing/landing-client";
import { YksSimulator } from "@/components/tools/yks-simulator";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: { absolute: "YKS Puan ve Sıralama Hesaplama 2027 — Netten Puan, Sınav Günü Tahmini | Etütkoç" },
  description:
    "TYT ve AYT doğru-yanlış sayılarını gir; netini, ham puanını ve Türkiye sıralamanı hesapla. Etütkoç'un YKS simülasyonu sınav gününe kadarki gidişatını da hesaba katarak olası puan ve sıralama aralığını gösterir. Ücretsiz, üyeliksiz.",
  alternates: { canonical: "/yks-puan-hesaplama" },
};

const FAQ = [
  {
    q: "YKS puanı nasıl hesaplanır?",
    a: "Her testte net, doğru sayısından yanlış sayısının dörtte biri çıkarılarak bulunur. Netler ÖSYM'nin o yılki standart puan dönüşümüyle ham puana çevrilir. Bu araç dönüşümü YÖK Atlas'ta programlara yerleşen adayların gerçek netlerinden ve puanlarından çıkarılmış katsayılarla yapar; 2025 Sayısal için tipik hata yarım puan civarındadır.",
  },
  {
    q: "Sıralama nasıl tahmin ediliyor?",
    a: "Ham puana diploma notunun katkısı (diploma × 5 × 0,12) eklenerek yerleştirme puanı bulunur ve YÖK Atlas'taki program taban puanları ile başarı sıraları üzerinden Türkiye sırasına çevrilir. Diploma notu girmezsen aynı puanla yerleşen adayların tipik diploma puanı kullanılır.",
  },
  {
    q: "Sınav günü tahmini diğer hesaplama araçlarından nasıl farklı?",
    a: "Çoğu araç yalnız bugünkü netlerin puanını verir. Bu araç her ders için deneme seviyeni ve gidişatını hesaplar, sınav gününe kadar kalan haftaları ve sınav günü oynaklığını hesaba katar, 4.000 olası senaryo çalıştırır. Sonuç tek bir sayı değil, en olası puan ve iyi-kötü senaryo aralığıdır.",
  },
  {
    q: "Neden aralık bu kadar geniş?",
    a: "Tek denemeye dayanan tahmin belirsizdir: denemeden denemeye netler bir testte 4-5 net oynayabilir ve sınava aylar varken gidişat da değişir. Önceki denemelerini tarihleriyle eklersen kendi oynaklığın ve eğilimin hesaba katılır, aralık daralır.",
  },
  {
    q: "Girdiğim netler kaydediliyor mu?",
    a: "Hayır. Hesaplama isteği yalnız sonucu üretmek için işlenir; netlerin ya da diploma notun saklanmaz, üyelik gerekmez.",
  },
];

function JsonLd() {
  const data = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebApplication",
        name: "YKS Puan ve Sıralama Hesaplama",
        url: `${SITE_URL}/yks-puan-hesaplama`,
        applicationCategory: "EducationalApplication",
        operatingSystem: "Web",
        inLanguage: "tr-TR",
        offers: { "@type": "Offer", price: "0", priceCurrency: "TRY" },
        publisher: { "@id": "https://etutkoc.com/#organization" },
      },
      {
        "@type": "FAQPage",
        mainEntity: FAQ.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })),
      },
    ],
  };
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

const METHOD = [
  { n: "1", title: "Net", text: "Her testte doğru sayısından yanlışların dörtte biri çıkarılır. Boş sorular nete etki etmez." },
  { n: "2", title: "Ham puan", text: "Netler ÖSYM'nin dönüşümüne göre puana çevrilir. Katsayılar YÖK Atlas'ta programlara yerleşen binlerce adayın gerçek netlerinden ve puanlarından çıkarıldı; her testin puana etkisi farklıdır." },
  { n: "3", title: "Sıralama", text: "Ham puana diploma notunun katkısı eklenir ve YÖK Atlas'taki program tabanlarından Türkiye sırası bulunur." },
  { n: "4", title: "Sınav günü", text: "Her ders için deneme seviyen ve haftalık gidişatın hesaplanır; sınav günü oynaklığı eklenerek 4.000 senaryo çalıştırılır." },
];

const BADGES = [
  { icon: Database, text: "YÖK Atlas verisiyle kalibre" },
  { icon: Activity, text: "Sınav günü tahmini" },
  { icon: Lock, text: "Üyeliksiz, kayıt tutmaz" },
];

export default function Page() {
  return (
    <div className="force-light min-h-screen text-slate-900">
      <JsonLd />
      <SiteHeader />
      <main>
        <section className="relative overflow-hidden bg-slate-950 text-white">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.12]"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgb(255 255 255 / 0.5) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 0.5) 1px, transparent 1px)",
              backgroundSize: "44px 44px",
              maskImage: "radial-gradient(ellipse 80% 70% at 50% 20%, black, transparent)",
            }}
            aria-hidden
          />
          <div className="pointer-events-none absolute -left-32 -top-40 size-[30rem] rounded-full bg-cyan-500/30 blur-3xl" aria-hidden />
          <div className="pointer-events-none absolute -right-20 top-10 size-[24rem] rounded-full bg-amber-400/20 blur-3xl" aria-hidden />
          <div className="relative mx-auto max-w-4xl px-4 pb-36 pt-14 text-center sm:px-6 lg:pb-40 lg:pt-20">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-cyan-200 ring-1 ring-white/15">
              <Sparkles className="size-3.5 text-amber-300" aria-hidden /> Ücretsiz araç · 2027 YKS
            </span>
            <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.08] tracking-tight sm:text-6xl">
              YKS puan ve sıralama <span className="text-amber-300">hesaplama</span>
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-300">
              Doğru-yanlış sayılarını gir; netini, ham puanını ve Türkiye sıralamanı gör. Etütkoç&apos;un YKS simülasyonu
              sınav gününe kadar kalan süreyi ve gidişatını da hesaba katarak <b className="text-white">sınav günü olası puan ve sıralama aralığını</b> çıkarır.
            </p>
            <ul className="mt-8 flex flex-wrap justify-center gap-2.5">
              {BADGES.map((b) => (
                <li key={b.text} className="inline-flex items-center gap-2 rounded-full bg-white/10 px-4 py-2 text-sm font-medium text-slate-100 ring-1 ring-white/15">
                  <b.icon className="size-4 text-cyan-300" aria-hidden /> {b.text}
                </li>
              ))}
            </ul>
          </div>
        </section>

        <div className="relative z-10 mx-auto -mt-24 max-w-7xl px-4 sm:px-6 lg:px-8">
          <YksSimulator />
        </div>

        <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">Yöntem</div>
            <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">Hesaplama nasıl yapılıyor?</h2>
          </div>
          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {METHOD.map((m) => (
              <div key={m.n} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="font-display text-4xl font-extrabold text-cyan-700/25">{m.n}</div>
                <div className="mt-2 font-display text-lg font-bold text-slate-900">{m.title}</div>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{m.text}</p>
              </div>
            ))}
          </div>
          <p className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Bu bir tahmindir, kesin sonuç değildir. ÖSYM&apos;nin o yılki dönüşümü ve sınava giren aday sayısı değiştikçe puan ve
            sıra da değişir. Deneme netleri gerçek sınav netinden sapabilir.
          </p>
        </section>

        <section className="border-t border-slate-200 bg-white">
          <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-12 lg:px-8">
            <div className="lg:col-span-4">
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-700">SSS</div>
              <h2 className="mt-3 font-display text-3xl font-bold tracking-tight text-slate-900">Sık sorulan sorular</h2>
            </div>
            <div className="space-y-3 lg:col-span-8">
              {FAQ.map((f) => (
                <details key={f.q} className="group rounded-2xl border border-slate-200 bg-slate-50 p-5 open:bg-white open:shadow-md">
                  <summary className="cursor-pointer list-none font-semibold text-slate-900 [&::-webkit-details-marker]:hidden">{f.q}</summary>
                  <p className="mt-3 text-[15px] leading-relaxed text-slate-600">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid max-w-7xl gap-4 px-4 py-16 sm:px-6 md:grid-cols-2 lg:px-8">
          <Link href="/deneme-analizi" className="rounded-3xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:shadow-lg">
            <div className="font-display text-lg font-semibold text-slate-900">Deneme karnesi analizi</div>
            <p className="mt-2 text-sm text-slate-600">Karnedeki her soruyu konusuna bağlar; hangi konudan kaç net kazanılacağını gösterir.</p>
          </Link>
          <a href="https://etutkoc.com" className="rounded-3xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:shadow-lg">
            <div className="font-display text-lg font-semibold text-slate-900">Etütkoç Akademi — birebir YKS koçluğu</div>
            <p className="mt-2 text-sm text-slate-600">Trabzon&apos;da yüz yüze ve tüm Türkiye&apos;de online öğrenci koçluğu.</p>
          </a>
        </section>
      </main>
      <LandingFooter />
    </div>
  );
}
