import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";
import { shot } from "@/lib/product-shots";

export const metadata: Metadata = {
  title: "Öğrenci Koçluğu Takip Programı — Haftalık Program, Kitap Takibi, Veli Raporu",
  description:
    "Öğrenci koçları için takip programı: kitaba bağlı haftalık program, kalan test takibi, öğrencinin günlük işaretlemesi, erken uyarılar, yanlış soru arşivi ve veliye otomatik rapor. Web ve mobil.",
  alternates: { canonical: "/ogrenci-takip-programi" },
};

const content: FeaturePageContent = {
  path: "/ogrenci-takip-programi",
  eyebrow: "Öğrenci takip programı",
  h1: "Program, takip ve rapor tek yerde",
  lead:
    "Koçluğun çoğu zamanı program hazırlamakla, \"bu hafta ne yaptın\" sorusunu sormakla ve veliye durum anlatmakla geçer. Etütkoç Rotam bu üç işi birbirine bağlar: program öğrencinin kitaplarından hazırlanır, öğrenci her gün işaretler, koç ve veli aynı veriyi görür.",
  heroImage: shot("hafta-izgara", "Hafta ızgarası ve haftanın ders dengesi", "/teacher/students/…/week"),
  highlights: [
    { title: "Kitaba bağlı haftalık program", text: "Program öğrencinin kendi kitaplarından ve ünitelerinden kurulur." },
    { title: "Kalan test her an görünür", text: "Atanan testler kitaptan düşülür; aynı test iki kez verilmez." },
    { title: "Öğrenci telefondan işaretler", text: "Bitirdiği görevi, doğru, yanlış ve boş sayısını girer." },
    { title: "Erken uyarı", text: "Boş geçen günler, kaçınılan dersler, düşen tempo hafta bitmeden görünür." },
    { title: "Haftadan haftaya gidişat", text: "Her hafta öğrencinin kendi normal aralığıyla kıyaslanır." },
    { title: "Veliye haftalık rapor", text: "Yeni program ve haftalık özet veliye kendiliğinden gider." },
  ],
  sections: [
    {
      id: "program",
      kicker: "1 · Program",
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
      image: shot("gun-karti", "Gün fihristi ve seçili günün görevleri, ders renkleriyle", "/teacher/students/…/week"),
    },
    {
      id: "kaynak",
      kicker: "2 · Kaynak ve müfredat",
      title: "Kalan test ve müfredat takibi",
      body: [
        "Bir teste görev atandığında o test kitapta ayrılır. Kaynak durumu panelinde her ünitenin kaç testinin çözüldüğü, kaçının programda beklediği ve kaçının hâlâ atanabilir olduğu görünür. Böylece kitap bitmeden yeni kitap alınmaz, bitmiş üniteye tekrar görev verilmez.",
        "Müfredat sekmesi her dersin konularını sırasıyla listeler: hangi konu başladı, hangisi bitti, hangisi henüz açılmadı. Konuyu ne zaman kapatacağınıza siz karar verirsiniz.",
        "Öğrenci programı yapmadıysa ayrılan testler hafta bitince kendiliğinden serbest kalır ve yeniden atanabilir.",
      ],
      image: shot("mufredat-dersler", "Müfredat ilerlemesi: dersler ve konu konu durum", "/teacher/students/…#curriculum"),
    },
    {
      id: "ogrenci",
      kicker: "3 · Öğrenci",
      title: "Öğrenci tarafı: gününü ve gelişimini görür",
      body: [
        "Öğrenci Bugün ekranında o günün görevlerini görür, bitirdiğini işaretler ve çözdüğü testlerde doğru, yanlış ve boş sayısını girer. Yapamadığı görev için koçuna sayı ya da kaynak değişikliği talebi gönderebilir.",
        "Gelişim sayfasında sınava kalan günü, bu haftaki uyumunu ve çözdüğü test sayısını geçmiş haftalarıyla birlikte görür. Mobil uygulama Android'de yayında; öğrenci aynı hesapla web'den de girer.",
      ],
      image: shot("ogr-gelisim-hero", "Öğrencinin Gelişim sayfası", "/student/progress"),
    },
    {
      id: "uyari",
      kicker: "4 · Erken uyarı",
      title: "Kopan öğrenciyi hafta bitmeden görün",
      body: [
        "Durum özeti her öğrenci için tek cümleyle ne olduğunu söyler: program bitti mi, son günler boş mu geçti, hangi dersten kaçınılıyor, deneme netleri düşüyor mu. Her uyarının yanında gerekçesi ve ilgili sayfaya bağlantısı vardır.",
        "Uyarılar öğrencinin kendi ritmine göre hesaplanır: gece çalışan bir öğrenci için akşam saatinde \"bugün başlamadı\" uyarısı çıkmaz. Ele alınan uyarı \"gördüm\" ile kapatılır.",
      ],
      image: shot("ilerleme-bu-hafta", "Bu hafta nasıl gidiyor? Görev uyumu, çözülen test ve gün gün durum", "/teacher/students/…"),
    },
    {
      id: "gidisat",
      kicker: "5 · Gidişat",
      title: "Haftadan haftaya: öğrenci kendi normaline göre",
      body: [
        "Bir haftanın iyi mi kötü mü geçtiğini sınıf ortalaması değil öğrencinin kendi geçmişi söyler. Son haftaların grafiği öğrencinin normal aralığını gösterir; bu hafta o aralığın altına düştüyse işaretlenir.",
        "Yanında ölçüme dayanan önlem önerileri durur: yarım kalan görevler, ertelenen ders, düşen doğruluk. Her öneri tek tıkla seans gündemine eklenir.",
      ],
      image: shot("ilerleme-gidisat", "Haftalar arası gidişat ve önerilen önlemler", "/teacher/students/…"),
    },
    {
      id: "veli",
      kicker: "6 · Veli",
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
