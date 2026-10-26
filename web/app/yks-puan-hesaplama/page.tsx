import type { Metadata } from "next";
import Link from "next/link";

import { MarketingHeader } from "@/components/marketing/feature-page";
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

export default function Page() {
  return (
    <div className="force-light min-h-screen bg-[#f7f5f0] text-slate-900">
      <JsonLd />
      <MarketingHeader />
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:py-14">
        <h1 className="font-display text-3xl font-extrabold leading-tight tracking-tight sm:text-4xl">
          YKS puan ve sıralama hesaplama
        </h1>
        <p className="mt-3 text-[17px] leading-relaxed text-slate-700">
          TYT ve AYT doğru-yanlış sayılarını gir; netini, ham puanını ve Türkiye sıralamanı gör. Bununla kalmaz:
          Etütkoç&apos;un deneme analiz sistemindeki YKS simülasyonu, sınav gününe kadar kalan süreyi ve gidişatını hesaba
          katarak <b>sınav günü olası puan ve sıralama aralığını</b> da hesaplar.
        </p>

        <div className="mt-8">
          <YksSimulator />
        </div>

        <section className="mt-14 space-y-4 text-[16px] leading-relaxed text-slate-700">
          <h2 className="font-display text-2xl font-bold text-slate-900">Hesaplama nasıl yapılıyor?</h2>
          <p>
            <b>1. Net:</b> Her testte doğru sayısından yanlışların dörtte biri çıkarılır. Boş sorular nete etki etmez.
          </p>
          <p>
            <b>2. Ham puan:</b> Netler, ÖSYM&apos;nin o yılki dönüşümüne göre puana çevrilir. Katsayılar YÖK Atlas&apos;ta programlara
            taban puanla yerleşen binlerce adayın gerçek netlerinden ve puanlarından çıkarıldı. Fizik, Kimya ve Biyoloji ya
            da Edebiyat ve Sosyal Bilimler testlerinin ayrı ayrı girilmesi bu yüzden önemli: her testin puana etkisi farklıdır.
          </p>
          <p>
            <b>3. Sıralama:</b> Ham puana diploma notunun katkısı eklenir ve YÖK Atlas&apos;taki program tabanlarından Türkiye
            sırası bulunur.
          </p>
          <p>
            <b>4. Sınav günü tahmini:</b> Her ders için deneme seviyen ve haftalık gidişatın hesaplanır. Az veride gidişat,
            Etütkoç öğrencilerinin ölçülen ortalama gidişatına yaslanır. Sınav günü oynaklığı ve deneme ile gerçek sınav
            arasındaki fark eklenerek 4.000 senaryo çalıştırılır. Ortadaki değer en olası puanın; kenarlar iyi ve kötü senaryodur.
          </p>
          <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            Bu bir tahmindir, kesin sonuç değildir. ÖSYM&apos;nin o yılki dönüşümü ve sınava giren aday sayısı değiştikçe puan ve
            sıra da değişir. Deneme netleri gerçek sınav netinden sapabilir.
          </p>
        </section>

        <section className="mt-12">
          <h2 className="font-display text-2xl font-bold text-slate-900">Sık sorulan sorular</h2>
          <div className="mt-5 divide-y divide-slate-200 rounded-2xl border border-slate-200 bg-white">
            {FAQ.map((f) => (
              <details key={f.q} className="p-5">
                <summary className="cursor-pointer list-none font-semibold text-slate-900">{f.q}</summary>
                <p className="mt-3 text-[15px] leading-relaxed text-slate-700">{f.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="mt-12 grid gap-4 sm:grid-cols-2">
          <Link href="/deneme-analizi" className="rounded-2xl border border-slate-200 bg-white p-5 hover:border-cyan-700/40">
            <div className="font-semibold text-slate-900">Deneme karnesi analizi</div>
            <p className="mt-1.5 text-sm text-slate-600">Karnedeki her soruyu konusuna bağlar; hangi konudan kaç net kazanılacağını gösterir.</p>
          </Link>
          <a href="https://etutkoc.com" className="rounded-2xl border border-slate-200 bg-white p-5 hover:border-cyan-700/40">
            <div className="font-semibold text-slate-900">Etütkoç Akademi — birebir YKS koçluğu</div>
            <p className="mt-1.5 text-sm text-slate-600">Trabzon&apos;da yüz yüze ve tüm Türkiye&apos;de online öğrenci koçluğu.</p>
          </a>
        </section>
      </main>
      <LandingFooter />
    </div>
  );
}
