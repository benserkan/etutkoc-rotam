"use client";

import * as React from "react";
import Link from "next/link";
import { Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
  CohortStatsItem,
  InstitutionBrief,
  WeekOverWeekInfo,
} from "@/lib/types/institution";
import {
  PrintFooter,
  PrintHeader,
  formatTodayTr,
} from "@/components/institution/at-risk-print-sheet";

interface SectionData {
  label: string;
  cohorts: CohortStatsItem[];
}

interface Props {
  institution: InstitutionBrief;
  wow: WeekOverWeekInfo;
  sections: SectionData[];
}

/**
 * Kohort raporu — A4 landscape yazdırma sayfası (4 sekme tek sayfada).
 *
 * Jinja kaynağı: app/templates/institution/cohorts_print.html
 */
export function CohortsPrintSheet({ institution, wow, sections }: Props) {
  const today = formatTodayTr();
  return (
    <>
      <PrintStyles />

      <div className="no-print sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            <b>Kohort Karşılaştırma Raporu</b> — yazdırılabilir / PDF
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/institution/cohorts">← Geri</Link>
            </Button>
            <Button
              size="sm"
              onClick={() => {
                if (typeof window !== "undefined") window.print();
              }}
            >
              <Printer className="size-4" aria-hidden />
              Yazdır / PDF
            </Button>
          </div>
        </div>
      </div>

      <div className="sheet">
        <PrintHeader
          institution={institution.name}
          subtitle="Kohort Karşılaştırma Raporu"
          today={`${today} · son 7 gün`}
        />

        {/* WoW özet */}
        <div className="wow-grid no-break">
          <WowCell label="Bu hafta" value={wow.this_week_rate} color={rateHex(wow.this_week_rate)} />
          <WowCell
            label="Geçen hafta"
            value={wow.last_week_rate}
            color="#334155"
          />
          <WowCell
            label="Değişim"
            value={wow.delta_pct}
            color={
              wow.direction === "up"
                ? "#059669"
                : wow.direction === "down"
                  ? "#dc2626"
                  : "#475569"
            }
            sign={
              wow.direction === "up"
                ? "↑ +"
                : wow.direction === "down"
                  ? "↓ "
                  : "— "
            }
          />
        </div>

        {/* 4 kohort tablosu — 2x2 grid */}
        <div className="cohort-grid">
          {sections.map((s) => (
            <div key={s.label} className="cohort-card no-break">
              <h3 className="cohort-title">{s.label}</h3>
              {s.cohorts.length === 0 ? (
                <div className="text-[10px] text-slate-400 italic">
                  Bu kategoride veri yok
                </div>
              ) : (
                <table className="cohort-table">
                  <thead>
                    <tr>
                      <th>Kohort</th>
                      <th className="text-right">N</th>
                      <th className="text-right">Plan</th>
                      <th className="text-right">Tam.</th>
                      <th className="text-right">Oran</th>
                      <th className="text-right">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.cohorts.map((c) => (
                      <tr key={c.cohort_key}>
                        <td>
                          <b>{c.cohort_label}</b>
                        </td>
                        <td className="text-right">{c.student_count}</td>
                        <td className="text-right">{c.weekly_planned}</td>
                        <td className="text-right">{c.weekly_completed}</td>
                        <td className="text-right">
                          {c.weekly_rate_pct == null ? (
                            "—"
                          ) : (
                            <span
                              className={`pill pill-${c.rate_color}`}
                            >
                              %{c.weekly_rate_pct}
                            </span>
                          )}
                        </td>
                        <td className="text-right">
                          {c.at_risk_pct != null && c.at_risk_pct > 0 ? (
                            <span className="text-rose-700 font-medium">
                              %{c.at_risk_pct}
                            </span>
                          ) : (
                            <span className="text-emerald-700">✓</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>

        <PrintFooter today={today} />
      </div>
    </>
  );
}

function WowCell({
  label,
  value,
  color,
  sign,
}: {
  label: string;
  value: number | null;
  color: string;
  sign?: string;
}) {
  return (
    <div className="wow-cell">
      <div className="text-[9px] text-slate-500 uppercase">{label}</div>
      <div className="text-2xl font-bold" style={{ color }}>
        {value == null ? "—" : `${sign ?? ""}${sign ? "" : "%"}${value}`}
      </div>
    </div>
  );
}

function rateHex(pct: number | null): string {
  if (pct == null) return "#94a3b8";
  if (pct >= 70) return "#059669";
  if (pct >= 40) return "#d97706";
  return "#dc2626";
}

function PrintStyles() {
  return (
    <style>{`
      @page { size: A4 landscape; margin: 8mm; }
      html, body { background: white; }
      body {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        color: #0f172a;
        font-size: 10px;
        line-height: 1.35;
      }
      @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .no-print { display: none !important; }
        .sheet { width: auto; padding: 0; margin: 0; box-shadow: none; page-break-after: always; }
        .sheet:last-child { page-break-after: auto; }
      }
      .sheet {
        width: 297mm; min-height: 200mm;
        padding: 8mm; margin: 1rem auto;
        background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      }
      .no-break { break-inside: avoid; page-break-inside: avoid; }

      .wow-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-bottom: 16px;
      }
      .wow-cell {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 8px 10px;
      }

      .cohort-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
      }
      .cohort-card {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 8px;
      }
      .cohort-title {
        font-size: 12px;
        font-weight: 600;
        color: #334155;
        margin-bottom: 6px;
      }
      .cohort-table {
        width: 100%;
        border-collapse: collapse;
      }
      .cohort-table th, .cohort-table td {
        padding: 4px 6px;
        text-align: left;
      }
      .cohort-table th {
        font-size: 9px;
        text-transform: uppercase;
        color: #64748b;
        background: #f1f5f9;
      }
      .cohort-table .text-right { text-align: right; }
      .cohort-table tbody tr { border-top: 1px solid #e2e8f0; }
      .text-emerald-700 { color: #047857; }
      .text-rose-700 { color: #be123c; }

      .pill {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 9999px;
        font-size: 9px;
        font-weight: 600;
      }
      .pill-green  { background: #d1fae5; color: #047857; }
      .pill-amber  { background: #fef3c7; color: #92400e; }
      .pill-red    { background: #fee2e2; color: #991b1b; }
      .pill-slate  { background: #e2e8f0; color: #475569; }
    `}</style>
  );
}
