import type { Metadata } from "next";

import { YksSimulator } from "@/components/tools/yks-simulator";

/**
 * Gömülü sürüm — etutkoc.com sayfasında iframe içinde çalışır (Caddy bu yola yalnız
 * etutkoc.com'dan çerçeve izni verir). Arama motorları asıl sayfayı dizine alsın diye noindex.
 */
export const metadata: Metadata = {
  title: { absolute: "YKS Puan ve Sıralama Hesaplama" },
  robots: { index: false, follow: true },
  alternates: { canonical: "/yks-puan-hesaplama" },
};

export default function Page() {
  return (
    <div className="force-light bg-transparent p-1 text-slate-900">
      <YksSimulator embedded />
    </div>
  );
}
