/**
 * Print route group layout — minimum gövde.
 *
 * Mevcut `app/layout.tsx` root <html>/<body>'yi zaten veriyor. Burada
 * sadece SiteHeader'ı dışlamak için ayrı bir route group katmanı var.
 * Print sayfaları kendi sheet stilini içeride taşır.
 */
export const dynamic = "force-dynamic";

export default function PrintLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
