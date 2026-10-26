import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { PARENT_SITE_URL, PLAY_STORE_URL, SITE_URL } from "@/lib/site";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type { MyAccountResponse, UserRole } from "@/lib/types/me";
import { roleHome } from "@/lib/role-home";
import { LandingClient } from "@/components/landing/landing-client";

/**
 * Kök sayfa (/) — public tanıtım vitrini.
 *
 * Jinja parite (app/main.py index()): giriş yapmış kullanıcı rolüne göre
 * panele yönlendirilir; anonim ziyaretçi feature_catalog kartlı landing görür.
 * Kartlar + A/B + telemetri client tarafında (`/api/v2/landing`) yüklenir.
 */
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: { absolute: "Etütkoç Rotam — Öğrenci Koçluğu Takip ve Deneme Analizi Sistemi" },
  alternates: { canonical: "/" },
};

/**
 * Yapısal veri (schema.org JSON-LD). Rotam bir YAZILIM ÜRÜNÜDÜR: yerel işletme
 * kimliği (LocalBusiness, Trabzon adresi) etutkoc.com'da yaşar ve Google
 * İşletme Profili ile eşleşir. Burada aynı kuruluşa `@id` ile atıf yapılır —
 * iki site Google'a iki ayrı işletme değil, tek kuruluşun iki yüzü olarak
 * görünür. Şirket bilgileri `app/legal_info.py` COMPANY aynasıdır.
 */
const ORG_ID = `${PARENT_SITE_URL}/#organization`;
const JSONLD = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": ORG_ID,
      name: "Etütkoç Akademi",
      alternateName: ["Etütkoç", "ETÜTKOÇ"],
      legalName:
        "ETÜTKOÇ Akademi Kişisel Gelişim Özel Eğitim ve Öğretim Hizmetleri Limited Şirketi",
      url: PARENT_SITE_URL,
      logo: `${SITE_URL}/etutkoc-logo.png`,
      telephone: "+905056738561",
      email: "destek@etutkoc.com",
      address: {
        "@type": "PostalAddress",
        streetAddress: "İskenderpaşa Mah. Gazipaşa Cd. No:12/6",
        postalCode: "61400",
        addressLocality: "Ortahisar",
        addressRegion: "Trabzon",
        addressCountry: "TR",
      },
      sameAs: ["https://www.instagram.com/etutkoc/", "https://www.facebook.com/profile.php?id=61591843981542"],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "Etütkoç Rotam",
      inLanguage: "tr-TR",
      publisher: { "@id": ORG_ID },
    },
    {
      "@type": "SoftwareApplication",
      "@id": `${SITE_URL}/#software`,
      name: "Etütkoç Rotam",
      alternateName: "Rotam",
      url: SITE_URL,
      applicationCategory: "EducationalApplication",
      operatingSystem: "Web, Android",
      installUrl: PLAY_STORE_URL,
      downloadUrl: PLAY_STORE_URL,
      inLanguage: "tr-TR",
      description:
        "Öğrenci koçları, etüt merkezleri, dershaneler ve özel okullar için öğrenci takip, haftalık program ve deneme karnesi analiz sistemi. LGS, TYT ve AYT denemelerini konu konu okur, veliyi bilgilendirir.",
      audience: { "@type": "Audience", audienceType: "Öğrenci koçları ve eğitim kurumları" },
      offers: {
        "@type": "AggregateOffer",
        priceCurrency: "TRY",
        lowPrice: "0",
        highPrice: "7500",
        offerCount: "4",
        url: `${SITE_URL}/pricing`,
      },
      publisher: { "@id": ORG_ID },
    },
  ],
};

export default async function HomePage() {
  let role: UserRole | null = null;
  try {
    const me = await apiServer<MyAccountResponse>("/api/v2/me");
    role = me.user.role;
  } catch (e) {
    // 401/403 → anonim ziyaretçi (landing göster); diğer hatalar yukarı fırlar
    if (!(e instanceof ApiError)) throw e;
  }
  // redirect() NEXT_REDIRECT fırlatır → try/catch DIŞINDA çağrılmalı
  if (role) redirect(roleHome(role));

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSONLD) }}
      />
      <LandingClient />
    </>
  );
}
