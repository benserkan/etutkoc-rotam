import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";
import { shot } from "@/lib/product-shots";

export const metadata: Metadata = {
  title: "Deneme Karnesi Analiz Programı — LGS, TYT ve AYT Konu Analizi",
  description:
    "Deneme sonuç PDF'ini yükleyin; Etütkoç Rotam soruları tek tek okur, konulara bağlar, net fırsatını, unutulan konuları ve puan tahminini çıkarır. Koç, öğrenci ve veli için.",
  alternates: { canonical: "/deneme-analizi" },
};

const content: FeaturePageContent = {
  path: "/deneme-analizi",
  eyebrow: "Deneme karnesi analizi",
  h1: "Karneyi yükleyin, konu konu analiz hazır",
  lead:
    "Yayınevlerinin ve okulların deneme sonuç belgeleri her kurumda farklı biçimde gelir. Etütkoç Rotam belgeyi soru soru okur, her soruyu müfredat konusuna bağlar ve koçun seansta konuşacağı tabloyu hazırlar. LGS, TYT, AYT ve okul denemeleri için çalışır.",
  heroImage: shot("deneme-son", "Son deneme özeti ve kaçan netlerin ders ders dağılımı", "/teacher/students/…#exams"),
  highlights: [
    { title: "İki ayrı okuma, çapraz kontrol", text: "Sonuç PDF'i iki kez bağımsız okunur; uyuşmayan satırlar işaretlenir." },
    { title: "Her soru müfredat konusuna bağlanır", text: "Yayınevi konuyu farklı adlandırsa da resmi konuya eşlenir." },
    { title: "Net fırsatı", text: "Hangi konu kapanırsa deneme başına kaç net kazanılacağı sıralanır." },
    { title: "Unutulan ve gelişen konular", text: "Konu × deneme ısı haritası, kanıt denemeleriyle." },
    { title: "Gidişat ve puan tahmini", text: "Aynı sınav türündeki denemeler tek seride; netten tahmini puan." },
    { title: "Seans gündemi ve veli özeti", text: "Konuşulacak başlıklar hazır; veliye düzenlenebilir e-posta." },
  ],
  sections: [
    {
      id: "pdf",
      kicker: "1 · Yükleme",
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
      image: shot("pdf-aktar", "Deneme sonucunu PDF'ten aktarma penceresi", "/teacher/students/…#exams"),
    },
    {
      id: "gidisat",
      kicker: "2 · Gidişat",
      title: "Denemeden denemeye net gelişimi",
      body: [
        "Denemeler türüne göre ayrı serilerde izlenir: branş denemesi ile genel deneme aynı grafikte karıştırılmaz. Grafik öğrencinin normal aralığını da gösterir; bir deneme bu aralığın dışına düştüğünde nedeni altında yazar.",
        "Son denemelerin eğilimine göre bir sonraki denemenin tahmini de çizilir. Koç bir bakışta yükselişin süreklilik gösterip göstermediğini görür.",
      ],
      image: shot("deneme-gidisat", "Altı denemede net gelişimi ve normal aralık", "/teacher/students/…#exams"),
    },
    {
      id: "ders",
      kicker: "3 · Ders ders",
      title: "Her ders, her denemede tek tabloda",
      body: [
        "Tablo her dersin netini her denemede ayrı hücrede gösterir; renk, netin o dersteki soru sayısına oranıdır. Böylece 40 soruluk Türkçe ile 7 soruluk Kimya aynı ölçekte okunur.",
        "Son sütun kısa bir okuma verir: boş bırakmadan mı kaybediyor, yanlıştan mı, yoksa dalgalı mı gidiyor.",
      ],
      image: shot("deneme-ders-isi", "Ders × deneme tablosu: netin tam puana oranı", "/teacher/students/…#exams"),
    },
    {
      id: "net-firsati",
      kicker: "4 · Öncelik",
      title: "Net fırsatı: önce hangi konu çalışılmalı?",
      body: [
        "Bir öğrencinin denemede kaybettiği netlerin çoğu birkaç konuda toplanır. Rotam son denemelerdeki yanlış ve boşları konu bazında toplar ve şu soruyu cevaplar: bu konu kapanırsa deneme başına kaç net kazanılır?",
        "Yanında iki liste daha durur: eskiden yapıp son denemelerde kaçırdığı konular ve çalıştıkça karşılığını görmeye başladığı konular.",
      ],
      image: shot("deneme-firsat", "Net fırsatı, unutulan ve gelişen konular", "/teacher/students/…#exams"),
    },
    {
      id: "isi-haritasi",
      kicker: "5 · Konu × deneme",
      title: "En çok soru gelen konular, deneme deneme",
      body: [
        "Isı haritası her konuyu her denemede ayrı hücrede gösterir. Soldan sağa kızaran bir satır, öğrencinin eskiden bildiği bir konuyu unutmaya başladığını gösterir.",
        "Satırları en çok soru gelen ya da en zayıf konuya göre sıralayabilirsiniz; tümünü göster ile karnedeki her konu açılır.",
      ],
      image: shot("deneme-konu-isi", "Konu × deneme ısı haritası", "/teacher/students/…#exams"),
    },
    {
      id: "seans",
      kicker: "6 · Seans ve veli",
      title: "Seansta konuşulacak başlıklar hazır",
      body: [
        "Analizin sonunda koçun bir sonraki seansta öğrenciyle konuşacağı başlıklar çıkar; her biri tek tıkla seans gündemine eklenir.",
        "Koç tek düğmeyle veliye deneme sonucunu e-postayla da gönderir: net, önceki denemeye göre değişim ve en çok net kazanılabilecek konular. Göndermeden önce her cümleyi görür, düzenler ya da siler; aynı içerik PDF olarak indirilip WhatsApp'tan paylaşılabilir.",
      ],
      image: shot("deneme-seans", "Bu denemelerden seansta konuşulacak başlıklar", "/teacher/students/…#exams"),
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
    { href: "https://etutkoc.com/yks-puan-hesaplama", title: "YKS puan ve sıralama hesaplama", text: "Üye olmadan netlerini gir; bugünkü puanını ve sınav günü tahminini gör." },
    { href: "/ogrenci-takip-programi", title: "Öğrenci takip programı", text: "Kitaba bağlı haftalık program, günlük takip ve erken uyarılar." },
    { href: "/kurumlar", title: "Etüt merkezi ve dershaneler", text: "Kurum geneli deneme sonuçları ve öğretmen bazında akademik çıktı." },
  ],
  ctaTitle: "Bir sonraki denemeyi Rotam'la analiz edin",
  ctaText: "Hesabınızı açın, son deneme karnesini yükleyin ve konu analizini birkaç dakikada görün. Kredi kartı gerekmez.",
};

export default function Page() {
  return <FeaturePage content={content} />;
}
