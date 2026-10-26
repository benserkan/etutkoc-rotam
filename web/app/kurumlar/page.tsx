import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";
import { shot } from "@/lib/product-shots";

export const metadata: Metadata = {
  title: "Etüt Merkezi ve Dershane Öğrenci Takip Programı — Kurumlar için",
  description:
    "Etüt merkezi, dershane ve özel okullar için öğrenci takip sistemi: öğretmenlerin program uyumu, müdahale merkezi, deneme sonuçları, şube bazında haftalık görev havuzu ve veli bilgilendirme. Kurumunuza özel teklif.",
  alternates: { canonical: "/kurumlar" },
};

const content: FeaturePageContent = {
  path: "/kurumlar",
  eyebrow: "Etüt merkezi ve dershaneler",
  h1: "Program uygulanıyor mu, sonuç alınıyor mu? Tek panelde.",
  lead:
    "Kurumda asıl soru şudur: öğretmenlerin verdiği program uygulanıyor mu ve sonuç alınıyor mu? Etütkoç Rotam kurum yöneticisine bu soruyu öğrenci öğrenci, öğretmen öğretmen cevaplayan bir panel verir. Öğretmenler kendi öğrencileriyle çalışır; yönetici tüm kurumu görür.",
  heroImage: shot("kurum-pano", "Kurum paneli: öğretmenlerin son 7 günlük performansı", "/institution"),
  highlights: [
    { title: "Program uyum panosu", text: "Haftalık tamamlama ve doğruluk; kurum, öğretmen ve öğrenci kırılımı." },
    { title: "Müdahale merkezi", text: "Programı olmayan, düşük uyumlu ve risk altındaki öğrenciler öncelik sırasıyla." },
    { title: "Öğretmen karnesi", text: "Tamamlama, doğruluk, program disiplini ve riskli öğrenci sayısı." },
    { title: "Akademik çıktı", text: "Kurum geneli deneme netleri, gelişen ve gerileyen öğrenciler." },
    { title: "Dershane modu", text: "Şubenin ders programına göre haftalık görev havuzu." },
    { title: "Kurum kimliği", text: "Kurum logosuyla e-postalar ve paneller, toplu öğrenci kaydı." },
  ],
  sections: [
    {
      id: "uyum",
      kicker: "1 · Program uyumu",
      title: "Verilen program ne kadar uygulanıyor?",
      body: [
        "Uyum panosu son yedi günde verilen testlerin ne kadarının yapıldığını ve ne kadarının doğru yapıldığını gösterir. Haftalık trend, öğretmen kırılımı ve en düşük uyumlu öğrenciler aynı sayfadadır; programı hiç olmayan öğrenciler ayrıca listelenir.",
      ],
      bullets: [
        "Gizlilik: yönetici öğrencinin özel seans notlarını görmez, yalnız ölçümleri görür",
        "Yalnız yayınlanmış görevler sayılır; taslak program oranı bozmaz",
      ],
      image: shot("kurum-uyum", "Program uyumu: tamamlama, doğruluk ve öğretmen kırılımı", "/institution/compliance"),
    },
    {
      id: "mudahale",
      kicker: "2 · Müdahale",
      title: "Kime, ne zaman müdahale etmeli?",
      body: [
        "Müdahale merkezi aynı verileri önceliklendirilmiş kartlara çevirir: programı boş kalan öğrenci, uyumu düşen öğretmen grubu, risk puanı yükselen öğrenci. Her kartta nedeni ve önerilen adım yazar.",
        "Yönetici kartı tek tıkla ilgili öğretmene iletir; öğretmen bunu kendi panelinde talep olarak görür. Risk göstergeleri yeni kayıtlı öğrencide yanlış alarm vermez.",
      ],
      image: shot("kurum-mudahale", "Müdahale merkezi: öncelik sırasıyla aksiyon kartları", "/institution/action-center"),
    },
    {
      id: "karne",
      kicker: "3 · Öğretmen karnesi",
      title: "Hangi öğretmen sonuç alıyor?",
      body: [
        "Etkililik skoru dört ölçüden hesaplanır: tamamlama, doğruluk, program disiplini (öğrenci başına haftalık planlanan test) ve riskli öğrenci sayısı. En iyi pratiği örnek göstermek, zorlanan öğretmeni desteklemek için kullanılır.",
      ],
      image: shot("kurum-karne", "Öğretmen etkililik karnesi", "/institution/teacher-scorecard"),
    },
    {
      id: "havuz",
      kicker: "4 · Dershane modu",
      title: "Dershane modu: haftalık görev havuzu",
      body: [
        "Dershane ve etüt merkezlerinde öğrenci haftada bir rehber öğretmenle görüşür; gün gün program çoğu zaman tutmaz. Bu kurumlar için Rotam'da haftalık görev havuzu vardır: rehber, görüşmede öğrencinin bir haftalık işini havuza yazar; öğrenci her gün havuzdan kendi gününü seçer.",
        "Şubenin ders programı girildiğinde öğrenciye \"bugün dershanede Biyoloji vardı, havuzunda Biyoloji kalemin var\" hatırlatması gider. Rehber bir sonraki görüşmede ders ders ne yapıldığını ve gün gün ilerlemeyi tek ekranda görür.",
      ],
      image: shot("havuz-dersler", "Haftalık görev havuzu: derslere göre ilerleme", "/teacher/students/…/pool"),
    },
    {
      id: "sube",
      kicker: "5 · Şube",
      title: "Şube ve ders programı",
      body: [
        "Öğrenciler şubelere ayrılır; kitap setleri ve haftalık iskelet bir şubeye toplu uygulanır. Şubenin haftalık ders programı tabloya girilir ve görev dağılımı bu programa göre önerilir.",
      ],
      image: shot("sube-ders-programi", "Şube ders programı tablosu", "/teacher/students/…/pool"),
    },
    {
      id: "deneme",
      kicker: "6 · Akademik çıktı",
      title: "Deneme sonuçları kurum genelinde",
      body: [
        "Öğretmenler ya da öğrenciler deneme sonuç PDF'lerini yükler; her soru konusuna bağlanır. Kurum yöneticisi farklı soru sayılı sınavları karşılaştırmak için net başarı oranını, öğretmen bazında ortalamaları ve son denemelerde en çok gelişen ve gerileyen öğrencileri görür.",
      ],
      image: shot("kurum-akademik", "Akademik çıktı: net başarı, sınav türü ve koç kırılımı", "/institution/academic"),
    },
    {
      id: "kurulum",
      kicker: "7 · Kurulum",
      title: "Kurulum ve kurumsal kimlik",
      body: [
        "Öğrenciler listeden toplu eklenir; geçici şifreli giriş kartları yazdırılıp dağıtılır. Öğretmenler e-postayla davet edilir. Velilere giden e-postalar ve paneller kurumunuzun adı ve logosuyla görünür.",
        "Kurulumu birlikte yapıyoruz: kitap listeniz katalogdan eşlenir, şubeleriniz ve ders programınız tanımlanır, öğretmenlerinize kısa bir tanıtım yapılır.",
      ],
    },
  ],
  faq: [
    { q: "Hangi kurumlar kullanabilir?", a: "Etüt merkezleri, dershaneler, kurs merkezleri ve özel okulların rehberlik birimleri. Birkaç öğretmenli küçük etütlerden çok şubeli kurumlara kadar uygundur." },
    { q: "Fiyatlandırma nasıl?", a: "Kurumlar için fiyat öğretmen ve öğrenci sayısına göre teklifle belirlenir. Kurum Tanıma paketiyle 2 öğretmen ve 20 öğrenciye kadar ücretsiz başlanabilir." },
    { q: "Öğretmenler birbirinin öğrencisini görür mü?", a: "Hayır. Her öğretmen yalnız kendi öğrencilerini görür; kurum yöneticisi kurum genelini ölçümler düzeyinde görür." },
    { q: "Mevcut deneme sonuçlarımızı aktarabilir miyiz?", a: "Evet. Yayınevi ve kurum deneme karneleri PDF olarak yüklenir; sorular konulara bağlanır ve geçmiş denemelerle karşılaştırılır." },
    { q: "Veliler sisteme nasıl katılır?", a: "Öğretmen veliyi e-postayla davet eder ya da toplu kayıtta veli bilgisi girilir. Veli kendi hesabından çocuğunun programını ve deneme sonuçlarını görür, hangi bildirimleri alacağını seçer." },
  ],
  related: [
    { href: "/ogrenci-takip-programi", title: "Öğrenci takip programı", text: "Öğretmenlerin kullandığı program ve takip ekranları." },
    { href: "/deneme-analizi", title: "Deneme karnesi analizi", text: "PDF karneden soru soru konu analizi." },
    { href: "/pricing?type=kurum#kurumsal", title: "Kurumsal teklif", text: "Kurumunuza özel teklif ve kurulum görüşmesi isteyin." },
  ],
  ctaTitle: "Kurumunuz için görüşelim",
  ctaText: "Öğretmen ve öğrenci sayınızı bize iletin; kurulum planı ve kurumunuza özel teklifle dönelim.",
};

export default function Page() {
  return <FeaturePage content={content} />;
}
