"use client";

import * as React from "react";
import { Check, PlayCircle, ArrowRight, Sparkles } from "lucide-react";

import { MockupByType, MOCKUP_ICON } from "@/components/landing/mockups";

/** Anasayfa kartının form-girdisinden gelen alanları. */
export interface LandingCardPreviewData {
  title: string;
  tagline: string;
  categoryLabel: string;
  accentColor: string;
  mockupType: string | null;
  benefits: string[];
  demoDurationLabel?: string;
  hasDemo?: boolean;
}

/** Benefit metninden baştaki emoji/sembolleri temizler (landing ile aynı). */
function cleanBenefit(s: string): string {
  return s.replace(/^[^\p{L}\p{N}]+/u, "").trim();
}

/**
 * Anasayfa feature kartının BİREBİR statik önizlemesi (telemetri/navigasyon yok).
 * landing-client `FeatureCard` görünümünü yansıtır — admin yayın öncesi "kart
 * anasayfada nasıl görünecek" simülasyonu. Tek kaynak: MockupByType + mockupIcon.
 */
export function LandingCardPreview({ data }: { data: LandingCardPreviewData }) {
  const accent = data.accentColor || "#0e7490";
  const Icon = (data.mockupType && MOCKUP_ICON[data.mockupType]) || Sparkles;
  const benefits = data.benefits.map(cleanBenefit).filter(Boolean);
  return (
    <div className="force-light flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 text-slate-900">
      <div className="mb-3 flex items-center gap-3">
        <span
          className="flex size-11 items-center justify-center rounded-xl"
          style={{ background: `${accent}16`, color: accent }}
        >
          <Icon className="size-5" aria-hidden />
        </span>
        <span
          className="text-[11px] font-bold uppercase tracking-wider"
          style={{ color: accent }}
        >
          {data.categoryLabel || "KATEGORİ"}
        </span>
      </div>
      <h3 className="font-display text-lg font-bold text-slate-900">
        {data.title || "Kart başlığı"}
      </h3>
      <p
        className="mt-2 text-sm leading-relaxed text-slate-500 [&_em]:not-italic [&_strong]:font-semibold [&_strong]:text-slate-900"
        dangerouslySetInnerHTML={{
          __html: data.tagline || "Açıklama paragrafı burada görünecek.",
        }}
      />
      {data.mockupType ? (
        <div className="my-5 rounded-xl bg-slate-50/80 p-3 ring-1 ring-slate-100">
          <MockupByType type={data.mockupType} />
        </div>
      ) : null}
      <div className="mt-auto space-y-4">
        {benefits.length > 0 ? (
          <ul className="space-y-2">
            {benefits.map((b, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                <Check
                  className="mt-0.5 size-4 shrink-0"
                  style={{ color: accent }}
                  aria-hidden
                />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="flex items-center gap-3">
          {data.hasDemo ? (
            <span
              className="inline-flex items-center gap-1.5 text-sm font-semibold"
              style={{ color: accent }}
            >
              <PlayCircle className="size-4" aria-hidden />
              Demo İzle
              {data.demoDurationLabel ? (
                <span className="text-xs font-normal text-slate-400">
                  · {data.demoDurationLabel}
                </span>
              ) : null}
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-cyan-700">
            Ücretsiz dene <ArrowRight className="size-4" aria-hidden />
          </span>
        </div>
      </div>
    </div>
  );
}
