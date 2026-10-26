import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";
import { shot } from "@/lib/product-shots";

export const metadata: Metadata = {
  title: "Eğitim Koçu Programı — Bağımsız Koçlar için Öğrenci, Seans ve Tahsilat Takibi",
  description:
    "Bağımsız eğitim koçları için koçluk programı: öğrenci takibi, seans kaydı, tahsilat, online görüşme ve Google Meet bağlantısı, yapay zekâ ile seans hazırlığı, veli asistanı. 3 öğrenciye kadar ücretsiz.",
  alternates: { canonical: "/bagimsiz-koclar" },
};

const content: FeaturePageContent = {
  path: "/bagimsiz-koclar",
  eyebrow: "Bağımsız koçlar",
  h1: "Koçluk işinizin tamamı tek uygulamada",
  lead:
    "Tek başına çalışan bir koç hem öğretmen hem rehber hem de işletme sahibidir. Etütkoç Rotam öğrencinin programını ve deneme analizini yürütürken seanslarınızı, görüşme takviminizi ve tahsilatınızı da aynı yerde tutar.",
  heroImage: shot("koc-seans", "Koçluk seansları: gündem, not ve sonraki adım", "/teacher/students/…#sessions"),
  highlights: [
    { title: "Program ve kitap takibi", text: "Öğrencinin kitaplarından haftalık program, kalan test her an görünür." },
    { title: "Seans kaydı", text: "Gündem, not ve sonraki adım; sesle ya da form fotoğrafıyla doldurulur." },
    { title: "Tahsilat", text: "Seans ücreti, ay sonu hesabı ve ödeme kaydı." },
    { title: "Online görüşme takvimi", text: "Hatırlatmalar ve Google hesabınızla otomatik Meet bağlantısı." },
    { title: "Yapay zekâ ile seans hazırlığı", text: "Bu öğrenciyle bugün ne konuşmalı? Notlar ve veriden kısa özet." },
    { title: "Veli asistanı", text: "Veliye haftayı sesli anlatan, sorularını cevaplayan Rota." },
  ],
  sections: [
    {
      id: "seans",
      kicker: "1 · Seans",
      title: "Seans kaydı ve yapay zekâ ile hazırlık",
      body: [
        "Her görüşmenin gündemi, notu ve bir sonraki adımı kaydedilir. Kayıt anında öğrencinin o haftaki tamamlama oranı, geride kalan dersleri ve son deneme neti kendiliğinden eklenir; elle bir şey taşımanız gerekmez.",
        "Görüşme notunu sesle dikte edebilir ya da kâğıt formun fotoğrafını yükleyebilirsiniz. Bir sonraki seanstan önce yapay zekâ önceki notları ve akademik veriyi birlikte okuyup kısa bir hazırlık çıkarır: gündem önerileri ve dikkat edilecek noktalar.",
      ],
    },
    {
      id: "tahsilat",
      kicker: "2 · Tahsilat ve takvim",
      title: "Tahsilat ve görüşme takvimi",
      body: [
        "Her öğrenci için seans ücreti belirlenir. Ay sonunda yapılan seanslar sayılır, ödenen tutar düşülür ve kalan görünür; ertelenen ve iptal edilen seanslar ücrete sayılmaz.",
        "Görüşme takviminde haftalık tekrarlayan randevular kurulur. Öğrenci ve veli görüşmeden bir gün ve bir saat önce hatırlatma alır. Google hesabınızı bağlarsanız her randevu için Meet bağlantısı kendiliğinden oluşur; görüşme bitince tek tıkla seans kaydına dönüşür.",
      ],
    },
    {
      id: "program",
      kicker: "3 · Program",
      title: "Program ve takip",
      body: [
        "Öğrencinin kitapları bir kez tanımlanır; haftalık program bu kitaplardan hazırlanır ve atanan testler kitaptan düşülür. Öğrenci görevlerini telefondan işaretler, siz durum özetinden kimin geride kaldığını görürsünüz.",
      ],
      image: shot("hafta-izgara", "Hafta ızgarası ve haftanın ders dengesi", "/teacher/students/…/week"),
    },
    {
      id: "deneme",
      kicker: "4 · Deneme analizi",
      title: "Deneme analizi ve branş denemeleri",
      body: [
        "Deneme karnesini yükleyin; sorular konulara bağlanır, net fırsatı ve unutulan konular çıkar. Puan tahmini son genel denemenin ders netlerinden hesaplanır.",
        "Programda verdiğiniz branş denemelerinin sonuçları ayrıca toplanır: her ders tek satırda, öğrencinin normal aralığı, eğilimi ve istikrarıyla.",
      ],
      image: shot("brans-karne", "Branş denemeleri: her ders tek satırda", "/teacher/students/…#program-exams"),
    },
    {
      id: "paketler",
      kicker: "5 · Paketler",
      title: "Paketler",
      body: [
        "Keşif paketi 3 öğrenciye kadar ücretsizdir. Patika 10 öğrenciye kadar aylık 2.500 TL, Rota 25 öğrenciye kadar aylık 5.000 TL, Zirve sınırsız öğrenciyle aylık 7.500 TL'dir. Tüm paketler 14 gün ücretsiz denenir; kredi kartı istenmez.",
      ],
    },
  ],
  faq: [
    { q: "Ücretsiz paketle neler yapabilirim?", a: "Keşif paketinde 3 öğrenciyle program, takip, veli paneli ve deneme sonucu girişi kullanılır. Yapay zekâ özellikleri ücretli paketlerde ve 14 günlük denemede açıktır." },
    { q: "Online koçluk yapıyorum, işime yarar mı?", a: "Evet. Görüşme takvimi, hatırlatmalar ve Google Meet bağlantısı online koçluk için tasarlandı. Öğrenci ve veli hangi şehirde olursa olsun aynı panele girer." },
    { q: "Öğrencilerime nasıl ulaşırım?", a: "Uygulama içi bildirim, e-posta ve hazır WhatsApp şablonlarıyla. WhatsApp mesajları kendi telefonunuzdan, metni hazır olarak açılır." },
    { q: "Kendi koçluk markamla kullanabilir miyim?", a: "Bağımsız koç hesapları Etütkoç Rotam markasıyla çalışır. Kurumsal kimlik (logo ve kurum adı) kurum paketlerinde sunulur." },
    { q: "Verilerimi dışa aktarabilir miyim?", a: "Program, deneme raporları ve haftalık raporlar yazdırılabilir ve PDF olarak indirilebilir. Hesabınızı kapatmak isterseniz KVKK kapsamında verilerinizin silinmesini isteyebilirsiniz." },
  ],
  related: [
    { href: "/ogrenci-takip-programi", title: "Öğrenci takip programı", text: "Program, kitap takibi, erken uyarı ve veli raporu." },
    { href: "/deneme-analizi", title: "Deneme karnesi analizi", text: "PDF karneden konu analizi ve net fırsatı." },
    { href: "https://etutkoc.com/yks-puan-hesaplama", title: "YKS puan ve sıralama hesaplama", text: "Öğrencinizin netlerinden puan ve sıralama tahmini." },
  ],
  ctaTitle: "Koçluk işinizi tek yerden yönetin",
  ctaText: "14 gün ücretsiz deneyin. Öğrencilerinizi ekleyin, ilk haftalık programı hazırlayın, ilk seansı kaydedin.",
};

export default function Page() {
  return <FeaturePage content={content} />;
}
