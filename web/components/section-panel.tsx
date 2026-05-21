import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * SectionPanel — admin panel + tüm sayfa bölümlerinin standart sarmalayıcısı.
 *
 * Eşdeğer: app/templates/_macros/section_panel.html (Jinja makrosu).
 *
 * KIRMIZI ÇİZGİ ENFORCEMENT:
 *   - `description` ZORUNLU. "Çıplak h2 + grid" pattern'i yasak
 *     ([[feedback_admin_section_panel]] memory'sinde kayıtlı).
 *   - `accent` rengi marka token'larından — sabit renk yok.
 *   - "Yamalı görünüm yasak" kullanıcı kuralı bu component'in API'sıyla
 *     sağlanır: her bölüm aynı kabuk, sadece renkli üst şerit değişir.
 */
export type SectionPanelAccent =
  | "lacivert"   // primary (varsayılan)
  | "haki"       // secondary
  | "risk"       // kırmızı şerit — uyarı bölümleri
  | "dikkat"     // sarı şerit — bilgilendirme
  | "yolunda";   // yeşil şerit — başarı/sağlık

const ACCENT_BAR: Record<SectionPanelAccent, string> = {
  lacivert: "bg-primary",
  haki: "bg-secondary",
  risk: "bg-status-risk",
  dikkat: "bg-status-dikkat",
  yolunda: "bg-status-yolunda",
};

interface SectionPanelProps {
  title: string;
  /**
   * ZORUNLU. Bölümün ne işe yaradığını sade Türkçe açıklayan 1-2 cümle.
   * Boş bırakmak component'i çağırmamak demek (TypeScript zorunlu).
   * [[feedback_admin_panel_jargon]] — jargon yasak, açıklamasız metrik yasak.
   */
  description: string;
  accent?: SectionPanelAccent;
  /** Sağ üstte aksiyon butonları (örn. "Yeni ekle", "Filtrele"). */
  actions?: React.ReactNode;
  /** Başlık ile içerik arasında ekstra satır (örn. mini özet, breadcrumb). */
  meta?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

export function SectionPanel({
  title,
  description,
  accent = "lacivert",
  actions,
  meta,
  className,
  children,
}: SectionPanelProps) {
  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-lg border border-border bg-card text-card-foreground shadow-sm",
        className
      )}
    >
      {/* Renkli üst şerit — accent göstergesi */}
      <div className={cn("h-1 w-full", ACCENT_BAR[accent])} aria-hidden="true" />

      <header className="flex flex-col gap-3 border-b border-border px-6 py-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-col gap-1.5">
          <h2 className="font-display text-xl font-semibold leading-tight tracking-tight">
            {title}
          </h2>
          {/* Açıklama — gizlenmez, küçülmez. Kullanıcı kırmızı çizgisi. */}
          <p className="text-sm text-muted-foreground max-w-prose">{description}</p>
          {meta ? <div className="text-xs text-muted-foreground/80">{meta}</div> : null}
        </div>
        {actions ? <div className="flex items-center gap-2 shrink-0">{actions}</div> : null}
      </header>

      <div className="p-6">{children}</div>
    </section>
  );
}
