import { redirect } from "next/navigation";

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

/**
 * Google İşletme Profili / yerel arama eşleşmesi için yapılandırılmış işletme
 * verisi (schema.org JSON-LD). Değerler `app/legal_info.py` COMPANY sözlüğünün
 * aynasıdır — resmi bilgi değişirse iki yer birlikte güncellenir.
 */
const ORG_JSONLD = {
  "@context": "https://schema.org",
  "@type": ["LocalBusiness", "EducationalOrganization"],
  "@id": "https://rotam.etutkoc.com/#organization",
  name: "Etütkoç Akademi Kişisel Gelişim",
  legalName:
    "ETÜTKOÇ Akademi Kişisel Gelişim Özel Eğitim ve Öğretim Hizmetleri Limited Şirketi",
  url: "https://rotam.etutkoc.com",
  logo: "https://rotam.etutkoc.com/etutkoc-logo.png",
  image: "https://rotam.etutkoc.com/etutkoc-logo.png",
  telephone: "+905056738561",
  email: "destek@etutkoc.com",
  address: {
    "@type": "PostalAddress",
    streetAddress:
      "İskenderpaşa Mah. Gazipaşa Cad. Timurcıoğlu Apartmanı No: 12 / İç Kapı No: 6",
    addressLocality: "Ortahisar",
    addressRegion: "Trabzon",
    addressCountry: "TR",
  },
  areaServed: "Trabzon",
  knowsAbout: ["LGS koçluğu", "YKS koçluğu", "öğrenci koçluğu", "eğitim danışmanlığı"],
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
        dangerouslySetInnerHTML={{ __html: JSON.stringify(ORG_JSONLD) }}
      />
      <LandingClient />
    </>
  );
}
