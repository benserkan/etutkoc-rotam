import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Öğrenci Koçluğu Takip Programı — Haftalık Program, Kitap Takibi, Veli Raporu",
  description:
    "Öğrenci koçları için takip programı: kitaba bağlı haftalık program, kalan test takibi, öğrencinin günlük işaretlemesi, erken uyarılar, yanlış soru arşivi ve veliye otomatik rapor. Web ve mobil.",
  alternates: { canonical: "/ogrenci-takip-programi" },
};

const content: FeaturePageContent = {
  path: "/ogrenci-takip-programi",
  eyebrow: "Öğrenci takip programı",
  h1: "Öğrenci koçluğu takip programı: program, takip ve rapor tek yerde",
  lead:
    "Koçluğun çoğu zamanı program hazırlamakla, \"bu hafta ne yaptın\" sorusunu sormakla ve veliye durum anlatmakla geçer. Etütkoç Rotam bu üç işi birbirine bağlar: program öğrencinin kitaplarından hazırlanır, öğrenci her gün işaretler, koç ve veli aynı veriyi görür.",
  highlights: [
    "Haftalık program öğrencinin kendi kitaplarından ve ünitelerinden kurulur",
    "Atanan testler kitaptan düşülür; kalan test sayısı her an görünür",
    "Öğrenci görevini telefondan işaretler, doğru, yanlış ve boş sayısını girer",
    "Programa uymayan öğrenci için erken uyarı: boş geçen günler, kaçınılan dersler",
    "Yanlış soru arşivi: fotoğrafla eklenir, aralıklı tekrarla kapanır",
    "Veliye haftalık rapor ve yeni program bildirimi",
  ],
  sections: [
    {
      id: "program",
      title: "Kitaba bağlı haftalık program",
      body: [
        "Koç öğrencinin kitaplarını bir kez tanımlar: hangi ünite, kaç test. Hazır katalogdaki kitaplar tek tıkla eklenir; katalogda olmayan kitap içindekiler sayfasının fotoğrafından okunur. Program hazırlarken görev kutusuna konu adını yazmak yeter; sistem uygun kitabı ve üniteyi önerir.",
        "Haftalık ızgarada her gün ders renkleriyle görünür. Görevler sürükle-bırakla taşınır, kopyalanır ya da haftaya yayılır. Sabah, öğle ve akşam olarak bölmek isteyen koçlar periyot ekler.",
      ],
      bullets: [
        "Haftalık iskelet: her hafta tekrar eden ders yerleşimi öneri olarak gelir",
        "Geçen haftadan yapılmayan görevler tek tıkla yeni haftaya taşınır",
        "Program öğrenciye ve veliye yazdırılabilir, PDF olarak paylaşılabilir",
      ],
      image: { src: "/urun/haftalik-program.webp", alt: "Haftalık program ve hafta ızgarası", width: 1170, height: 620 },
    },
    {
      id: "kaynak",
      title: "Kalan test takibi: bir kitaptan iki kez aynı test verilmez",
      body: [
        "Bir teste görev atandığında o test kitapta ayrılır. Kaynak durumu panelinde her ünitenin kaç testinin çözüldüğü, kaçının programda beklediği ve kaçının hâlâ atanabilir olduğu görünür. Böylece kitap bitmeden yeni kitap alınmaz, bitmiş üniteye tekrar görev verilmez.",
        "Öğrenci programı yapmadıysa ayrılan testler hafta bitince kendiliğinden serbest kalır ve yeniden atanabilir.",
      ],
      image: { src: "/urun/kaynak-durumu.webp", alt: "Kaynak durumu ve kitap bazında kalan testler", width: 1170, height: 880 },
    },
    {
      id: "ogrenci",
      title: "Öğrenci tarafı: günün listesi telefonda",
      body: [
        "Öğrenci Bugün ekranında o günün görevlerini görür, bitirdiğini işaretler ve çözdüğü testlerde doğru, yanlış ve boş sayısını girer. Yapamadığı görev için koçuna sayı ya da kaynak değişikliği talebi gönderebilir.",
        "Mobil uygulama Android'de yayında. Öğrenci aynı hesapla web'den de girer.",
      ],
      image: { src: "/urun/ogrenci-bugun.webp", alt: "Öğrencinin Bugün ekranı", width: 1440, height: 760 },
    },
    {
      id: "uyari",
      title: "Erken uyarı: kopan öğrenciyi hafta bitmeden görün",
      body: [
        "Durum özeti her öğrenci için tek cümleyle ne olduğunu söyler: program bitti mi, son günler boş mu geçti, hangi dersten kaçınılıyor, deneme netleri düşüyor mu. Her uyarının yanında gerekçesi ve ilgili sayfaya bağlantısı vardır.",
        "Uyarılar öğrencinin kendi ritmine göre hesaplanır: gece çalışan bir öğrenci için akşam saatinde \"bugün başlamadı\" uyarısı çıkmaz. Ele alınan uyarı \"gördüm\" ile kapatılır.",
      ],
      image: { src: "/urun/durum-ozeti.webp", alt: "Öğrenci durum özeti ve uyarılar", width: 1170, height: 580 },
    },
    {
      id: "veli",
      title: "Veli bilgilendirme",
      body: [
        "Veli kendi hesabından çocuğunun haftalık programını, tamamlama oranını ve deneme sonuçlarını görür. Haftalık rapor e-postası, yeni program bildirimi ve deneme sonucu e-postası otomatik gider; veli hangi bildirimleri alacağını kendisi seçer.",
        "Rota adlı yapay zekâ asistanı veliye haftayı sesli anlatır ve sorularını cevaplar: \"Bu hafta programa uydu mu?\" sorusunun cevabı, yapılmayan görevlerin adıyla birlikte gelir.",
      ],
    },
  ],
  faq: [
    { q: "Öğrenci koçluğu takip programı kimler için?", a: "Bağımsız çalışan eğitim koçları, etüt merkezleri, dershaneler ve özel okulların rehberlik birimleri için. LGS hazırlığındaki ortaokul öğrencilerinden YKS'ye hazırlanan lise ve mezun öğrencilere kadar kullanılır." },
    { q: "Kaç öğrenci ekleyebilirim?", a: "Ücretsiz pakette 3 öğrenci eklenir. Patika 10, Rota 25 öğrenciye kadar; Zirve paketinde öğrenci sınırı yoktur. Her paket 14 gün ücretsiz denenebilir." },
    { q: "Öğrencinin kitapları sistemde yoksa ne olur?", a: "Katalogda yüzlerce LGS, TYT ve AYT kitabı ünite ve test sayılarıyla hazırdır. Olmayan kitap için içindekiler sayfasının fotoğrafını yüklemek yeterli; bölümler ve test sayıları okunur." },
    { q: "Mobil uygulama var mı?", a: "Evet. Etütkoç Rotam Android uygulaması yayında; öğrenci, veli, koç ve kurum yöneticisi aynı hesapla girer. iOS sürümü Apple incelemesinden sonra yayınlanacak." },
    { q: "Verilerim güvende mi?", a: "Veriler Türkiye'deki şirketimiz Etütkoç Akademi Ltd. Şti. sorumluluğunda, KVKK'ya uygun saklanır. Koçun öğrenciye özel notları veliye gösterilmez." },
  ],
  related: [
    { href: "/deneme-analizi", title: "Deneme karnesi analizi", text: "PDF karneden konu analizi, net fırsatı ve puan tahmini." },
    { href: "/bagimsiz-koclar", title: "Bağımsız koçlar", text: "Seans kaydı, tahsilat, online görüşme ve paketler." },
    { href: "/kurumlar", title: "Etüt merkezi ve dershaneler", text: "Öğretmenlerin program uyumu ve kurum geneli raporlar." },
  ],
  ctaTitle: "Öğrencilerinizi tek ekrandan takip edin",
  ctaText: "Hesabınızı açın, ilk öğrencinizi ve kitabını ekleyin, haftalık programı on dakikada hazırlayın.",
};

export default function Page() {
  return <FeaturePage content={content} />;
}
