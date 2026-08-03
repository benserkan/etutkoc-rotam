"use client";

/**
 * Bağlamsal yükseltme anı (Faz 2C, 2026-08-05).
 *
 * Reforge bulgusu: jenerik "yükselt" banner'ı yerine ÖZELLİĞİN ADI + PLANIN
 * FİYATI + TEK TIK, deneme dönüşümünü ~%28 artırır. Bu diyalog "değer anında"
 * açılır: koç kapasitesi dolmuşken yeni öğrenci eklemeye çalıştığında, sihirbaz
 * sonucu tarzında GEREKÇELİ teklif gösterir; tek tık /teacher/plan'a paket
 * ÖN-SEÇİLİ götürür. Veri: 422 plan_quota_exceeded detayındaki öneri yükü.
 */
import * as React from "react";
import { useRouter } from "next/navigation";
import { Check, TrendingUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface UpgradeMomentPayload {
  current: number;
  limit: number;
  current_plan_label: string;
  recommended_plan: string;
  recommended_label: string;
  recommended_monthly: number;
  recommended_students: number | null; // null = sınırsız
  recommended_credits: number;
}

/** 422 detail.details → payload (eksikse null — diyalog açılmaz, toast yeter). */
export function parseUpgradeMoment(details: unknown): UpgradeMomentPayload | null {
  const d = details as Record<string, unknown> | undefined;
  if (!d || d.scope !== "solo" || !d.recommended_plan) return null;
  return {
    current: Number(d.current ?? 0),
    limit: Number(d.limit ?? 0),
    current_plan_label: String(d.current_plan_label ?? ""),
    recommended_plan: String(d.recommended_plan),
    recommended_label: String(d.recommended_label ?? ""),
    recommended_monthly: Number(d.recommended_monthly ?? 0),
    recommended_students:
      d.recommended_students == null ? null : Number(d.recommended_students),
    recommended_credits: Number(d.recommended_credits ?? 0),
  };
}

export function UpgradeMomentDialog({
  payload,
  onClose,
}: {
  payload: UpgradeMomentPayload | null;
  onClose: () => void;
}) {
  const router = useRouter();
  if (!payload) return null;
  const p = payload;
  const capText =
    p.recommended_students == null
      ? "sınırsız öğrenci"
      : `${p.recommended_students} öğrenci kapasitesi`;

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <TrendingUp className="size-5 text-cyan-700" aria-hidden />
            {p.current_plan_label} doldu ({p.current}/{p.limit}) — büyüyorsun!
          </DialogTitle>
        </DialogHeader>

        <div className="rounded-xl border-2 border-cyan-600 bg-gradient-to-b from-cyan-50/80 to-white px-4 py-3">
          <p className="text-[11px] font-bold uppercase tracking-wide text-cyan-700">
            {p.current + 1}. öğrencin için sana uygun paket
          </p>
          <div className="mt-1 flex items-baseline justify-between gap-3">
            <span className="font-display text-2xl font-extrabold text-slate-900">
              {p.recommended_label}
            </span>
            <span className="text-lg font-bold text-slate-900">
              {p.recommended_monthly.toLocaleString("tr-TR")} ₺/ay
            </span>
          </div>
        </div>

        <ul className="space-y-1.5">
          {[
            `${capText} — bugün eklediğinle birlikte rahat sığarsın`,
            `Aylık ${p.recommended_credits.toLocaleString("tr-TR")} yapay zekâ kredisi — karne okuma ve veli asistanı kesintisiz`,
            "Yükseltince pasif öğrencilerin otomatik yeniden aktifleşir",
          ].map((r) => (
            <li key={r} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
              <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
              {r}
            </li>
          ))}
        </ul>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose}>
            Şimdilik vazgeç
          </Button>
          <Button
            className="bg-cyan-700 text-white hover:bg-cyan-800"
            onClick={() => {
              onClose();
              router.push(`/teacher/plan?plan=${encodeURIComponent(p.recommended_plan)}`);
            }}
          >
            {p.recommended_label}&apos;ya geç
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
