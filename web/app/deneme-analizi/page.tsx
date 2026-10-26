import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Deneme Karnesi Analiz Programı — LGS, TYT ve AYT Konu Analizi",
  description:
    "Deneme sonuç PDF'ini yükleyin; Etütkoç Rotam soruları tek tek okur, konulara bağlar, net fırsatını, unutulan konuları ve puan tahminini çıkarır. Koç, öğrenci ve veli için.",
  alternates: { canonical: "/deneme-analizi" },
};

const content: FeaturePageContent = {
  path: "/deneme-analizi",
  eyebrow: "Deneme karnesi analizi",
  h1: "Deneme karnesi analiz programı: PDF'i yükleyin, konu konu analiz hazır",
  lead:
    "Yayınevlerinin ve okulların deneme sonuç belgeleri her kurumda farklı biçimde gelir. Etütkoç Rotam belgeyi soru soru okur, her soruyu müfredat konusuna bağlar ve koçun seansta konuşacağı tabloyu hazırlar. LGS, TYT, AYT ve okul denemeleri için çalışır.",
  highlights: [
    "Sonuç PDF'i iki ayrı okumayla kontrol edilir; şüpheli satırlar işaretlenir",
    "Her soru resmi müfredat konusuna bağlanır, yayınevi adı fark etmez",
    "Net fırsatı: hangi konu kapanırsa deneme başına kaç net kazanılır",
    "Unutulan ve gelişen konular, konu × deneme ısı haritası",
    "Netten puan tahmini ve aynı sınav türünde gidişat",
    "Veliye düzenlenebilir deneme sonucu e-postası",
  ],
  sections: [
    {
      id: "pdf",
      title: "Sonuç belgesini yükleyin, satırları kontrol edin",
      body: [
        "Koç ya da öğrenci deneme sonuç PDF'ini yükler. Sistem belgeyi iki kez bağımsız okur ve iki okumanın sonucunu karşılaştırır; uyuşmayan satırlar sarıyla işaretlenir. Belgede ders özeti varsa doğru, yanlış ve boş sayıları ayrıca çapraz kontrol edilir.",
        "Önizleme ekranında her sorunun konusunu, öğrencinin cevabını ve doğru cevabı görürsünüz. Yanlış eşleşen bir konuyu tek tıkla düzeltirsiniz; sistem bu düzeltmeyi öğrenir ve aynı yayınevinin bir sonraki denemesinde kendiliğinden uygular.",
      ],
      bullets: [
        "LGS, TYT, AYT (Sayısal, Eşit Ağırlık, Sözel), okul ve sınıf izleme sınavları",
        "Net hesabı sınav türüne göre: LGS'de 3 yanlış, YKS'de 4 yanlış bir doğruyu götürür",
        "Aynı belge ikinci kez yüklenirse uyarı verir; mükerrer kayıt oluşmaz",
      ],
      image: { src: "/urun/pdf-karne-onizleme.webp", alt: "Deneme sonucu PDF'ten aktarım önizlemesi", width: 900, height: 840 },
    },
    {
      id: "net-firsati",
      title: "Net fırsatı: önce hangi konu çalışılmalı?",
      body: [
        "Bir öğrencinin denemede kaybettiği netlerin çoğu birkaç konuda toplanır. Rotam son denemelerdeki yanlış ve boşları konu bazında toplar ve şu soruyu cevaplar: bu konu kapanırsa deneme başına kaç net kazanılır?",
        "Liste büyükten küçüğe sıralanır. Koç haftalık programı hazırlarken bu sırayı kullanır; öğrenci de neden o konuya çalıştığını görür.",
      ],
      image: { src: "/urun/net-firsati.webp", alt: "Net fırsatı ve unutulan, gelişen konular", width: 1170, height: 450 },
    },
    {
      id: "isi-haritasi",
      title: "Konu × deneme ısı haritası ve unutulan konular",
      body: [
        "Isı haritası her konuyu her denemede ayrı hücrede gösterir. Soldan sağa kızaran bir satır, öğrencinin eskiden bildiği bir konuyu unutmaya başladığını gösterir. Sistem bu durumu ayrıca \"unutulan konular\" listesinde, kanıt denemeleriyle birlikte belirtir.",
        "Tersi de görünür: önceden zayıf olup son denemelerde düzelen konular \"gelişen konular\" olarak listelenir. Seansta öğrenciye somut bir gelişme göstermek için iyi bir başlangıçtır.",
      ],
      image: { src: "/urun/konu-isi-haritasi.webp", alt: "Konu analizi ve konu × deneme ısı haritası", width: 1170, height: 860 },
    },
    {
      id: "gidisat",
      title: "Net gelişimi ve puan tahmini",
      body: [
        "Denemeler türüne göre ayrı serilerde izlenir: branş denemesi ile genel deneme aynı grafikte karıştırılmaz. Her deneme için net, doğru-yanlış-boş dağılımı ve bir önceki denemeye göre fark görünür.",
        "Puan tahmini, son genel denemenin ders netlerinden hesaplanır. YKS için puan modeli, YÖK Atlas'ta yerleşen adayların gerçek netlerinden kalibre edilmiştir. Üye olmadan denemek isterseniz YKS puan ve sıralama hesaplama aracımızı kullanabilirsiniz.",
      ],
      image: { src: "/urun/net-gelisimi.webp", alt: "Deneme sonuçları ve net gelişimi grafiği", width: 1170, height: 600 },
    },
    {
      id: "veli",
      title: "Veliye anlaşılır bir deneme özeti",
      body: [
        "Koç tek düğmeyle veliye deneme sonucunu e-postayla gönderir. E-postada net, bir önceki denemeye göre değişim, en çok net kazanılabilecek konular ve kısa bir değerlendirme yer alır. Koç göndermeden önce her cümleyi görür, düzenler ya da siler.",
        "Aynı içerik PDF olarak da indirilir; WhatsApp'tan paylaşmak isteyen koçlar bunu kullanır.",
      ],
      image: { src: "/urun/veli-deneme-maili.webp", alt: "Veliye deneme sonucu e-postası önizlemesi", width: 1141, height: 1400 },
    },
  ],
  faq: [
    { q: "Hangi yayınevlerinin deneme karneleriyle çalışıyor?", a: "Belirli bir biçime bağlı değildir. Yayınevi karneleri, okul ve kurum izleme sınavları ile ÖSYM biçimli sonuç belgeleri okunur. Konu adları farklı yazılsa da resmi müfredat konusuna bağlanır; koçun yaptığı düzeltmeler bir sonraki karnede kendiliğinden uygulanır." },
    { q: "Öğrenci karneyi kendisi yükleyebilir mi?", a: "Evet. Öğrenci kendi panelinden PDF yükler; analiz koçun ekranına da düşer. Satır düzeltmeleri koç tarafından yapılır." },
    { q: "Yanlış yapılan sorular ne oluyor?", a: "Koç ya da öğrenci denemedeki yanlışlardan istediklerini tek tıkla Yanlış Soru Arşivi'ne gönderir. Arşivdeki sorular aralıklı tekrar ile yeniden çözülür ve iki kez aralıklı doğru çözülünce kapanır." },
    { q: "Deneme analizi ücretli mi?", a: "Etütkoç Rotam 14 gün ücretsiz denenebilir ve 3 öğrenciye kadar ücretsiz pakette kullanılabilir. PDF'ten yapay zekâ ile okuma 14 günlük denemede ve ücretli paketlerde açıktır; deneme sonucunu elle girmek her pakette mümkündür." },
    { q: "Veriler kimlerle paylaşılıyor?", a: "Deneme sonuçları yalnız öğrencinin koçu, öğrencinin kendisi ve bağlı velisi tarafından görülür. Koçun öğrenciye özel notları veliye gösterilmez." },
  ],
  related: [
    { href: "/yks-puan-hesaplama", title: "YKS puan ve sıralama hesaplama", text: "Üye olmadan netlerini gir; bugünkü puanını ve sınav günü tahminini gör." },
    { href: "/ogrenci-takip-programi", title: "Öğrenci takip programı", text: "Kitaba bağlı haftalık program, günlük takip ve erken uyarılar." },
    { href: "/kurumlar", title: "Etüt merkezi ve dershaneler", text: "Kurum geneli deneme sonuçları ve öğretmen bazında akademik çıktı." },
  ],
  ctaTitle: "Bir sonraki denemeyi Rotam'la analiz edin",
  ctaText: "Hesabınızı açın, son deneme karnesini yükleyin ve konu analizini birkaç dakikada görün. Kredi kartı gerekmez.",
};

export default function Page() {
  return <FeaturePage content={content} />;
}
