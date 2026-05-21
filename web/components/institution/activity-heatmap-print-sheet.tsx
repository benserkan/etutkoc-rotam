"use client";

import * as React from "react";
import Link from "next/link";
import { AlertCircle, Printer } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ActivityHeatmapResponse } from "@/lib/types/institution";
import { HeatmapGrid } from "@/components/institution/heatmap-grid";
import {
  PrintFooter,
  PrintHeader,
  formatTodayTr,
} from "@/components/institution/at-risk-print-sheet";

interface Props {
  data: ActivityHeatmapResponse;
  weeks: number;
}

/**
 * Öğretmen aktivite haritası — A4 landscape yazdırma sayfası.
 *
 * Jinja kaynağı: app/templates/institution/activity_heatmap_print.html
 */
export function ActivityHeatmapPrintSheet({ data, weeks }: Props) {
  const today = formatTodayTr();
  const {
    institution,
    days_count,
    inactive_threshold_days,
    inactive_count,
    teachers,
  } = data;

  return (
    <>
      <PrintStyles />

      <div className="no-print sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-2 flex items-center justify-between gap-3">
          <div className="text-sm text-slate-600">
            <b>Öğretmen Aktivite Raporu</b> — yazdırılabilir / PDF · son {weeks} hafta
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href={`/institution/activity-heatmap?weeks=${weeks}`}>
                ← Geri
              </Link>
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
          subtitle="Öğretmen Aktivite Raporu"
          today={today}
          weeks={weeks}
        />

        {inactive_count > 0 && (
          <div className="rose-banner">
            <AlertCircle
              style={{ width: 12, height: 12, display: "inline-block" }}
              aria-hidden
            />{" "}
            <b>{inactive_count}</b> öğretmen son {inactive_threshold_days}{" "}
            gündür hiç aktivite yok — kırmızı arkaplanlı satırlar.
          </div>
        )}

        {teachers.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <div className="text-4xl mb-2">👥</div>
            <div className="font-semibold">Henüz öğretmen yok</div>
          </div>
        ) : (
          <table className="prt-table">
            <thead>
              <tr>
                <th style={{ width: "25%" }}>Öğretmen</th>
                <th>Aktivite ısı haritası ({days_count} gün)</th>
                <th className="text-right" style={{ width: "18%" }}>
                  Toplam
                </th>
              </tr>
            </thead>
            <tbody>
              {teachers.map((t) => (
                <tr
                  key={t.teacher_id}
                  style={t.is_inactive ? { background: "#fef2f2" } : undefined}
                >
                  <td>
                    <div className="font-semibold">{t.full_name}</div>
                    <div className="text-[9px] text-slate-500">
                      {t.is_inactive ? (
                        <span className="text-rose-700 font-medium">
                          PASİF
                        </span>
                      ) : null}
                      {t.is_inactive && t.last_active_day ? " · " : null}
                      {t.last_active_day
                        ? `son aktivite ${t.days_since_active}g önce`
                        : "hiç aktivite yok"}
                    </div>
                  </td>
                  <td>
                    <HeatmapGrid cells={t.cells} print />
                  </td>
                  <td className="text-right text-[9px]">
                    <div>
                      <b>{t.total_logins}</b> giriş
                    </div>
                    <div className="text-slate-500">
                      {t.total_tasks} task · {t.total_notes} not
                    </div>
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
        .sheet { width: auto; padding: 0; margin: 0; box-shadow: none; }
      }
      .sheet {
        width: 297mm; min-height: 200mm;
        padding: 8mm; margin: 1rem auto;
        background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.08);
      }
      .prt-table { width: 100%; border-collapse: collapse; }
      .prt-table th, .prt-table td { padding: 4px 6px; vertical-align: middle; }
      .prt-table thead { background: #f1f5f9; }
      .prt-table tbody tr { border-top: 1px solid #e2e8f0; page-break-inside: avoid; }
      .prt-table .text-right { text-align: right; }
      .rose-banner {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 4px;
        padding: 6px 8px;
        margin-bottom: 12px;
        font-size: 10px;
        color: #9f1239;
      }
    `}</style>
  );
}
