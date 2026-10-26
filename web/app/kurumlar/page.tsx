import type { Metadata } from "next";
import { FeaturePage, type FeaturePageContent } from "@/components/marketing/feature-page";

export const metadata: Metadata = {
  title: "Etüt Merkezi ve Dershane Öğrenci Takip Programı — Kurumlar için",
  description:
    "Etüt merkezi, dershane ve özel okullar için öğrenci takip sistemi: öğretmenlerin program uyumu, müdahale merkezi, deneme sonuçları, şube bazında haftalık görev havuzu ve veli bilgilendirme. Kurumunuza özel teklif.",
  alternates: { canonical: "/kurumlar" },
};

const content: FeaturePageContent = {
  path: "/kurumlar",
  eyebrow: "Etüt merkezi ve dershaneler",
  h1: "Etüt merkezi ve dershane öğrenci takip programı",
  lead:
    "Kurumda asıl soru şudur: öğretmenlerin verdiği program uygulanıyor mu ve sonuç alınıyor mu? Etütkoç Rotam kurum yöneticisine bu soruyu öğrenci öğrenci, öğretmen öğretmen cevaplayan bir panel verir. Öğretmenler kendi öğrencileriyle çalışır; yönetici tüm kurumu görür.",
  highlights: [
    "Program uyum panosu: haftalık tamamlama ve doğruluk, öğretmen bazında",
    "Müdahale merkezi: programı olmayan, düşük uyumlu ve risk altındaki öğrenciler",
    "Öğretmen karnesi: tamamlama, doğruluk, program disiplini ve risk",
    "Akademik çıktı: kurum geneli deneme netleri, gelişen ve gerileyen öğrenciler",
    "Dershane modu: şubenin ders programına göre haftalık görev havuzu",
    "Kurum logosuyla e-postalar ve paneller, toplu öğrenci kaydı",
  ],
  sections: [
    {
      id: "uyum",
      title: "Program uyumu ve müdahale merkezi",
      body: [
        "Uyum panosu son yedi günde verilen testlerin ne kadarının yapıldığını ve ne kadarının doğru yapıldığını gösterir. Kurum geneli, öğretmen bazında ve öğrenci bazında kırılım vardır; programı hiç olmayan öğrenciler ayrıca listelenir.",
        "Müdahale merkezi aynı verileri önceliklendirilmiş kartlara çevirir: \"3 gündür programı boş öğrenci\", \"uyumu %25'in altına düşen öğretmen grubu\". Yönetici kartı tek tıkla ilgili öğretmene iletir; öğretmen bunu panelinde talep olarak görür.",
      ],
      bullets: [
        "Gizlilik: yönetici öğrencinin özel seans notlarını görmez, yalnız ölçümleri görür",
        "Risk ve tükenmişlik göstergeleri yeni kayıtlı öğrencide yanlış alarm vermez",
      ],
      image: { src: "/urun/durum-ozeti.webp", alt: "Öğrenci durum özeti ve uyarılar", width: 1170, height: 580 },
    },
    {
      id: "havuz",
      title: "Dershane modu: haftalık görev havuzu",
      body: [
        "Dershane ve etüt merkezlerinde öğrenci haftada bir rehber öğretmenle görüşür; gün gün program çoğu zaman tutmaz. Bu kurumlar için Rotam'da haftalık görev havuzu vardır: rehber, görüşmede öğrencinin bir haftalık işini havuza yazar; öğrenci her gün havuzdan kendi gününü seçer.",
        "Şubenin ders programı girildiğinde öğrenciye \"bugün dershanede Biyoloji vardı, havuzunda Biyoloji kalemin var\" hatırlatması gider. Rehber bir sonraki görüşmede ders ders ne yapıldığını ve gün gün ilerlemeyi tek ekranda görür.",
      ],
      image: { src: "/urun/havuz-dersler.webp", alt: "Haftalık görev havuzu: derslere göre ilerleme", width: 1400, height: 933 },
    },
    {
      id: "sube",
      title: "Şube ve ders programı",
      body: [
        "Öğrenciler şubelere ayrılır; kitap setleri ve haftalık iskelet bir şubeye toplu uygulanır. Şubenin haftalık ders programı tabloya girilir ve görev dağılımı bu programa göre önerilir.",
      ],
      image: { src: "/urun/sube-ders-programi.webp", alt: "Şube ders programı tablosu", width: 1400, height: 1077 },
    },
    {
      id: "deneme",
      title: "Deneme sonuçları ve akademik çıktı",
      body: [
        "Öğretmenler ya da öğrenciler deneme sonuç PDF'lerini yükler; her soru konusuna bağlanır. Kurum yöneticisi farklı soru sayılı sınavları karşılaştırmak için net başarı oranını, öğretmen bazında ortalamaları ve son denemelerde en çok gelişen ve gerileyen öğrencileri görür.",
      ],
      image: { src: "/urun/konu-isi-haritasi.webp", alt: "Konu × deneme ısı haritası", width: 1170, height: 860 },
    },
    {
      id: "kurulum",
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
