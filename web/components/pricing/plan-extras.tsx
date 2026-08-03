"use client";

/**
 * Paket sayfası ortak blokları (2026-08-04 üyelik yenilemesi):
 *  - CreditCostsTable — "Krediler ne yapar?" (işlem başına maliyet, tek kaynak API)
 *  - PlanMatrix — kademeli paket karşılaştırma tablosu (kategorili)
 *  - PlanFaq — sık sorulanlar
 * Hem public /pricing hem /teacher/plan aynı bileşenleri kullanır (tutarlılık).
 */
import * as React from "react";
import { Check, ChevronDown, Minus, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import type { CreditCostRow, PricingCatalog } from "@/lib/types/pricing";

// ---------------------------------------------------------------------------
// Krediler ne yapar?
// ---------------------------------------------------------------------------

export function CreditCostsTable({
  rows,
  className,
}: {
  rows: CreditCostRow[];
  className?: string;
}) {
  if (!rows?.length) return null;
  return (
    <section className={cn("rounded-2xl border border-border bg-card p-5", className)}>
      <h3 className="flex items-center gap-2 text-sm font-semibold">
        <Sparkles className="size-4 text-violet-600" aria-hidden />
        Krediler ne yapar?
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Her yapay zekâ işlemi sabit kredi harcar; kredin ay başında otomatik yenilenir.
        Örnek: 1.500 kredi ≈ ayda 60 veli sesli yorumu + 100 soru etiketleme.
      </p>
      <div className="mt-3 grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
        {rows.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between gap-3 text-sm">
            <span className="text-foreground/85">{r.label}</span>
            <span className="shrink-0 font-medium tabular-nums text-muted-foreground">
              {r.credits} kredi
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Karşılaştırma matrisi
// ---------------------------------------------------------------------------

type Cell = boolean | string;

interface MatrixRow {
  label: string;
  cells: [Cell, Cell, Cell, Cell]; // Keşif · Patika · Rota · Zirve
}

interface MatrixGroup {
  title: string;
  rows: MatrixRow[];
}

function buildMatrix(catalog: PricingCatalog): { plans: string[]; groups: MatrixGroup[] } {
  const tiers = catalog.solo.tiers;
  const freeLabel =
    catalog.cards.find((c) => c.key === "free")?.name ?? "Keşif";
  const plans = [freeLabel, ...tiers.map((t) => t.label)];
  const caps = [
    String(catalog.solo.free.students),
    ...tiers.map((t) => (t.max_students == null ? "Sınırsız" : String(t.max_students))),
  ];
  const credits = catalog.cards
    .filter((c) => c.audience === "solo")
    .map((c) => (c.credits_monthly ? c.credits_monthly.toLocaleString("tr-TR") : "—"));

  const groups: MatrixGroup[] = [
    {
      title: "Takip ve Program",
      rows: [
        { label: "Aktif öğrenci", cells: caps as [Cell, Cell, Cell, Cell] },
        { label: "Kitap → haftalık program → günlük takip", cells: [true, true, true, true] },
        { label: "Deneme girişi + net gelişim grafiği", cells: [true, true, true, true] },
        { label: "Yanlış Soru Arşivi (aralıklı tekrar)", cells: [true, true, true, true] },
        { label: "Randevu sistemi + Google Meet", cells: [false, true, true, true] },
        { label: "Mobil uygulama (öğrenci · veli · koç)", cells: [true, true, true, true] },
      ],
    },
    {
      title: "Yapay Zekâ",
      rows: [
        {
          label: "Aylık yapay zekâ kredisi",
          cells: (credits.length === 4 ? credits : ["—", "1.500", "4.000", "8.000"]) as [Cell, Cell, Cell, Cell],
        },
        { label: "AI karne okuma (deneme sonucu PDF → konu analizi)", cells: [false, true, true, true] },
        { label: "Yanlışına ipucu (AI yol gösterir)", cells: [false, true, true, true] },
        { label: "Sesli dikte + fotoğraftan seans notu", cells: [false, true, true, true] },
        { label: "Görüşme öncesi özet (AI)", cells: [false, true, true, true] },
        { label: "Kariyer önerisi (AI)", cells: [false, false, true, true] },
      ],
    },
    {
      title: "Veli Deneyimi",
      rows: [
        { label: "Veli daveti + haftalık e-posta raporu", cells: [true, true, true, true] },
        { label: "Veli yapay zekâ asistanı (sesli yorum + sohbet)", cells: [false, true, "Tam kapasite", "Tam kapasite"] },
        { label: "Deneme/net gelişimi veli panelinde", cells: [true, true, true, true] },
      ],
    },
    {
      title: "Destek ve Hizmet",
      rows: [
        { label: "Sesli rehber turu", cells: [true, true, true, true] },
        { label: "Öncelikli destek", cells: [false, false, true, true] },
        { label: "Birebir kurulum ve taşıma desteği", cells: [false, false, false, true] },
        { label: "Yeni özelliklere erken erişim", cells: [false, false, false, true] },
      ],
    },
  ];
  return { plans, groups };
}

function CellView({ v }: { v: Cell }) {
  if (v === true) return <Check className="mx-auto size-4 text-emerald-600" aria-hidden />;
  if (v === false) return <Minus className="mx-auto size-4 text-slate-300" aria-hidden />;
  return <span className="text-xs font-medium">{v}</span>;
}

export function PlanMatrix({
  catalog,
  defaultOpen = false,
  className,
}: {
  catalog: PricingCatalog;
  defaultOpen?: boolean;
  className?: string;
}) {
  const { plans, groups } = buildMatrix(catalog);
  return (
    <details
      className={cn("group rounded-2xl border border-border bg-card", className)}
      open={defaultOpen}
    >
      <summary className="flex cursor-pointer items-center justify-between gap-2 p-5 text-sm font-semibold">
        Paketleri karşılaştır
        <ChevronDown className="size-4 text-muted-foreground transition group-open:rotate-180" aria-hidden />
      </summary>
      <div className="overflow-x-auto px-5 pb-5">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground">
              <th className="w-2/5 py-2 text-left font-medium">Özellik</th>
              {plans.map((p, i) => (
                <th
                  key={p}
                  className={cn(
                    "py-2 text-center font-semibold",
                    i === 2 && "text-cyan-700 dark:text-cyan-300", // Rota (en popüler)
                  )}
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <React.Fragment key={g.title}>
                <tr>
                  <td
                    colSpan={5}
                    className="pb-1 pt-4 text-[11px] font-bold uppercase tracking-wide text-muted-foreground"
                  >
                    {g.title}
                  </td>
                </tr>
                {g.rows.map((r) => (
                  <tr key={r.label} className="border-t border-border/60">
                    <td className="py-2 pr-3 text-foreground/85">{r.label}</td>
                    {r.cells.map((c, i) => (
                      <td key={i} className="py-2 text-center">
                        <CellView v={c} />
                      </td>
                    ))}
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// SSS
// ---------------------------------------------------------------------------

const FAQ_ITEMS: { q: string; a: string }[] = [
  {
    q: "Deneme nasıl işliyor? Kart bilgisi gerekiyor mu?",
    a: "Kayıt olduğunda 14 gün boyunca Rota deneyimi (tüm özellikler + 50 yapay zekâ kredisi) kart bilgisi OLMADAN açılır. Süre bitince hesabın Keşif'e (ücretsiz) döner; verilerin aynen korunur, hiçbir şey silinmez.",
  },
  {
    q: "Kredim biterse ne olur?",
    a: "Yapay zekâ özellikleri o ay için durur; takip, program ve raporlama aynen çalışır. Kredin her ay başında otomatik yenilenir. Kredini kimin, hangi özellikte harcadığını Paket sayfandaki kullanım dökümünde görürsün.",
  },
  {
    q: "İstediğim zaman iptal edebilir miyim?",
    a: "Evet. İptal ettiğinde dönem sonuna kadar tüm özellikler açık kalır; sonrasında hesabın Keşif'e döner. Taahhüt ve cayma bedeli yok.",
  },
  {
    q: "Paketimi sonradan değiştirebilir miyim?",
    a: "Evet — öğrenci sayın arttıkça tek tıkla üst pakete geçersin; pasif öğrencilerin otomatik yeniden aktifleşir. Sistem öğrenci sayına göre sana uygun paketi zaten önerir.",
  },
  {
    q: "Ödeme nasıl alınıyor?",
    a: "Kartla, 3D Secure ile (iyzico altyapısı). Kart bilgilerin bize hiç ulaşmaz. Akademik yıl seçersen 10 ay öder, 12 ay kullanırsın.",
  },
  {
    q: "Kurum (etüt/dershane/okul) için fark ne?",
    a: "Kurum paketlerinde her koçun tüm araçlarına ek olarak kurum panosu vardır: koç performansı, program uyumu, risk ve akademik çıktı tek ekranda. Fiyat koç sayısına göre kurumunuza özel tekliflendirilir.",
  },
];

export function PlanFaq({ className }: { className?: string }) {
  return (
    <section className={cn("space-y-2", className)}>
      <h3 className="text-sm font-semibold">Sık sorulanlar</h3>
      {FAQ_ITEMS.map((it) => (
        <details key={it.q} className="group rounded-xl border border-border bg-card px-4 py-3">
          <summary className="flex cursor-pointer items-center justify-between gap-2 text-sm font-medium">
            {it.q}
            <ChevronDown className="size-4 shrink-0 text-muted-foreground transition group-open:rotate-180" aria-hidden />
          </summary>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{it.a}</p>
        </details>
      ))}
    </section>
  );
}
