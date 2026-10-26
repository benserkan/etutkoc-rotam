import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** Arama motorları yalnız tanıtım ve yasal sayfaları tarar; paneller kapalı. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/api/",
          "/teacher",
          "/student",
          "/parent",
          "/institution",
          "/admin",
          "/me",
          "/payment",
          "/membership",
          "/offers",
          "/kampanya",
          "/password",
          "/verify-email",
          "/signup/invite",
          "/legal/kvkk-veli",
        ],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
