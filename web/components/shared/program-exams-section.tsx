"use client";

/**
 * Programdaki denemeler — görevde girilen D/Y'den açılan kayıtlar
 * (import_source="task"). Soru-satırı ve konu eşlemesi taşımadıkları için deneme
 * ANALİZ sistemine (liste/özet/net grafiği/gelişim raporu/puan tahmini) karışmaz;
 * ayrı, sade bir listede gösterilir (2026-10-20 kullanıcı kararı).
 */
import * as React from "react";
import { ChevronDown, ClipboardList } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ExamResultRow } from "@/lib/types/teacher";

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return d && m && y ? `${d}.${m}.${y}` : iso;
}

export function ProgramExamsSection({
  rows,
  audience,
}: {
  rows: ExamResultRow[] | undefined;
  audience: "coach" | "student" | "parent";
}) {
  const [open, setOpen] = React.useState(true);
  const list = rows ?? [];
  if (list.length === 0) return null;

  // Seriye göre grupla (ör. "TYT Matematik branş", "TYT genel") — sıra korunur.
  const groups: { label: string; rows: ExamResultRow[] }[] = [];
  for (const r of list) {
    const label = r.series_label || r.section_label;
    const g = groups.find((x) => x.label === label);
    if (g) g.rows.push(r);
    else groups.push({ label, rows: [r] });
  }

  const hint =
    audience === "coach"
      ? "Sonuç programdaki görevden girilir/düzeltilir."
      : audience === "student"
        ? "Sonucu Bugün sayfasındaki deneme görevinden girersin."
        : "Sonuçları öğrenci programdaki görevden girer.";

  return (
    <Card data-section="exams:program">
      <CardContent className="p-0">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full items-start gap-3 p-4 text-left"
        >
          <ClipboardList className="mt-0.5 size-5 shrink-0 text-indigo-700" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">
              Programdaki denemeler{" "}
              <span className="ml-1 rounded-full bg-indigo-700 px-2 py-0.5 text-[11px] font-semibold text-white tabular-nums">
                {list.length}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Deneme görevlerinde girilen doğru/yanlış sonuçları. Soru soru konu bilgisi
              olmadığı için karne denemelerinin konu analizine katılmaz. {hint}
            </p>
          </div>
          <ChevronDown
            className={cn("mt-1 size-4 shrink-0 text-muted-foreground transition-transform", open && "rotate-180")}
            aria-hidden
          />
        </button>
        {open ? (
          <div className="space-y-3 border-t border-border p-4">
            {groups.map((g) => (
              <div key={g.label}>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.label} · {g.rows.length} deneme
                </p>
                <ul className="divide-y divide-border rounded-md border border-border">
                  {g.rows.map((r) => (
                    <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
                      <span className="w-20 shrink-0 text-xs tabular-nums text-muted-foreground">
                        {formatTRDate(r.exam_date)}
                      </span>
                      <span className="min-w-0 flex-1 basis-40 break-words text-sm">{r.title}</span>
                      <span className="text-xs tabular-nums">
                        <span className="text-emerald-700">{r.total_correct}D</span>{" "}
                        <span className="text-rose-700">{r.total_wrong}Y</span>{" "}
                        <span className="text-muted-foreground">{r.total_blank}B</span>
                        <span className="text-muted-foreground"> · {r.total_questions} soru</span>
                      </span>
                      <span className="w-20 shrink-0 text-right text-sm font-semibold tabular-nums">
                        {r.net.toFixed(2)} net
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

/**
 * Deneme sayfalarının üstündeki iki parçalı seçici (öğrenci + veli): karne/elle
 * girilen denemelerin analizi ile programdaki branş denemeleri AYRI görünür.
 */
export function ExamKindSwitch({
  value,
  onChange,
  karneCount,
  programCount,
}: {
  value: "karne" | "program";
  onChange: (v: "karne" | "program") => void;
  karneCount: number;
  programCount: number;
}) {
  const items: { key: "karne" | "program"; label: string; count: number }[] = [
    { key: "karne", label: "Karne denemeleri", count: karneCount },
    { key: "program", label: "Branş denemeleri (program)", count: programCount },
  ];
  return (
    <div role="tablist" aria-label="Deneme türü" className="flex flex-wrap gap-1 rounded-xl border border-border bg-card p-1">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          role="tab"
          aria-selected={value === it.key}
          onClick={() => onChange(it.key)}
          className={cn(
            "flex min-h-10 flex-1 items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold",
            value === it.key ? "bg-cyan-700 text-white" : "text-muted-foreground hover:text-foreground",
          )}
        >
          {it.label}
          <span
            className={cn(
              "rounded-full px-1.5 text-[11px] tabular-nums",
              value === it.key ? "bg-white/20 text-white" : "bg-muted text-foreground",
            )}
          >
            {it.count}
          </span>
        </button>
      ))}
    </div>
  );
}
