"use client";

import * as React from "react";
import Link from "next/link";
import { Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { AtRiskResponse } from "@/lib/types/institution";

interface Props {
  data: AtRiskResponse;
}

/**
 * Risk altındaki öğrenciler — A4 portrait yazdırma sayfası.
 *
 * Jinja kaynağı: app/templates/institution/at_risk_print.html
 */
export function AtRiskPrintSheet({ data }: Props) {
  const today = formatTodayTr();
  const { institution, counts, at_risk } = data;

  return (
    <>
      <PrintStyles />
      <Toolbar />

      <div className="sheet">
        <PrintHeader institution={institution.name} subtitle="Risk Altındaki Öğrenciler" today={today} />

        <div className="grid grid-cols-3 gap-3 mb-4">
          <CountCell label="🔴 Kritik" value={counts.critical} border="rose" />
          <CountCell label="🟠 Risk" value={counts.high} border="orange" />
          <CountCell label="🟡 Dikkat" value={counts.medium} border="amber" />
        </div>

        {at_risk.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <div className="text-4xl mb-2">🎉</div>
            <div className="font-semibold text-slate-700">
              Risk altında öğrenci yok
            </div>
            <div className="text-xs">
              Tüm öğrenciler izlemde, performans normal seyirde.
            </div>
          </div>
        ) : (
          <table className="prt-table">
            <thead>
              <tr>
                <th style={{ width: "35%" }}>Öğrenci / Öğretmen</th>
                <th>Seviye</th>
                <th className="text-right">Skor</th>
                <th style={{ width: "45%" }}>Niye</th>
              </tr>
            </thead>
            <tbody>
              {at_risk.map((r) => (
                <tr key={r.student_id} className={`lvl-${r.level}`}>
                  <td>
                    <div className="font-semibold">{r.full_name}</div>
                    <div className="text-[9px] text-slate-500">
                      {r.grade_level ? `${r.grade_level}. sınıf` : null}
                      {r.teacher_name ? (
                        <>
                          {r.grade_level ? " · " : ""}öğretmen: {r.teacher_name}
                        </>
                      ) : null}
                    </div>
                  </td>
                  <td>
                    <span style={{ fontSize: "10px" }}>{r.level_emoji}</span>{" "}
                    <span className="font-medium">{r.level_label}</span>
                  </td>
                  <td className="text-right">
                    <span
                      className="font-bold"
                      style={{ color: scoreColor(r.score) }}
                    >
                      {r.score}
                    </span>
                    /100
                  </td>
                  <td>
                    {r.indicators.map((ind) => (
                      <span key={ind.code} className="indicator-chip" title={ind.detail}>
                        {ind.title}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <PrintFooter today={today} />
      </div>
    </>
  );
}

function PrintStyles() {
  return (
    <style>{`
      @page { size: A4 portrait; margin: 10mm; }
      html, body { background: white; }
      body {
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        color: #0f172a;
        font-size: 10px;
        line-height: 1.4;
      }
      @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .no-print { display: none !important; }
        .sheet { width: auto; padding: 0; margin: 0; box-shadow: none; }
      }
      .sheet {
        width: 210mm; min-height: 297mm;
        padding: 10mm; margin: 1rem auto;
        background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      }
      .prt-table { width: 100%; border-collapse: collapse; }
      .prt-table th, .prt-table td { padding: 4px 6px; text-align: left; vertical-align: top; }
      .prt-table thead { background: #f1f5f9; }
      .prt-table tbody tr { border-top: 1px solid #e2e8f0; page-break-inside: avoid; }
      .prt-table .text-right { text-align: right; }
      .lvl-critical { background: #fef2f2; }
      .lvl-high { background: #fff7ed; }
      .lvl-medium { background: #fefce8; }
      .indicator-chip {
        display: inline-block;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        padding: 1px 6px;
        margin-right: 4px;
        margin-bottom: 2px;
        font-size: 9px;
      }
    `}</style>
  );
}

function Toolbar() {
  return (
    <div className="no-print sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-3xl mx-auto px-4 py-2 flex items-center justify-between gap-3">
        <div className="text-sm text-slate-600">
          <b>Risk Altındaki Öğrenciler</b> — basılabilir özet
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm">
            <Link href="/institution/at-risk">← Geri</Link>
          </Button>
          <PrintButton />
        </div>
      </div>
    </div>
  );
}

function PrintButton() {
  return (
    <Button
      size="sm"
      onClick={() => {
        if (typeof window !== "undefined") window.print();
      }}
    >
      <Printer className="size-4" aria-hidden />
      Yazdır / PDF
    </Button>
  );
}

export function PrintHeader({
  institution,
  subtitle,
  today,
  weeks,
}: {
  institution: string;
  subtitle: string;
  today: string;
  weeks?: number;
}) {
  return (
    <header
      className="flex items-end justify-between pb-2 mb-3"
      style={{ borderBottom: "2px solid #117A86" }}
    >
      <div className="flex items-center gap-3">
        <div>
          <div className="text-xl font-black leading-none">
            <span style={{ color: "#117A86" }}>etütkoç</span>
            <span style={{ color: "#94a3b8", margin: "0 3px" }}>·</span>
            <span style={{ color: "#E8AC2D" }}>rotam</span>
          </div>
          <div
            className="text-[9px] text-slate-500 uppercase mt-1"
            style={{ letterSpacing: "0.2em" }}
          >
            {subtitle}
            {weeks != null ? ` — son ${weeks} hafta` : ""}
          </div>
        </div>
      </div>
      <div className="text-right leading-tight">
        <div className="text-base font-semibold">{institution}</div>
        <div className="text-xs text-slate-600">{today}</div>
      </div>
    </header>
  );
}

export function PrintFooter({ today }: { today: string }) {
  return (
    <footer className="mt-4 pt-2 border-t border-slate-200 flex items-center justify-between text-[9px] text-slate-500">
      <div>ETÜTKOÇ Rotam · {today}</div>
      <div>Yetkili: Kurum Yöneticisi</div>
    </footer>
  );
}

function CountCell({
  label,
  value,
  border,
}: {
  label: string;
  value: number;
  border: "rose" | "orange" | "amber";
}) {
  const borderClass = {
    rose: "border-rose-200",
    orange: "border-orange-200",
    amber: "border-amber-200",
  }[border];
  const colorClass = {
    rose: "text-rose-700",
    orange: "text-orange-700",
    amber: "text-amber-700",
  }[border];
  return (
    <div className={`border ${borderClass} rounded p-2`}>
      <div className="text-[9px] uppercase text-slate-500">{label}</div>
      <div className={`text-2xl font-bold ${colorClass}`}>{value}</div>
    </div>
  );
}

function scoreColor(score: number): string {
  if (score >= 80) return "#dc2626";
  if (score >= 60) return "#d97706";
  return "#92400e";
}

export function formatTodayTr(): string {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
