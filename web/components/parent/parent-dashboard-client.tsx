"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, HeartHandshake, Info } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { getParentDashboard, parentKeys } from "@/lib/api/parent";
import type {
  ParentChildSummary,
  ParentDashboardResponse,
  WarningLevel,
} from "@/lib/types/parent";

interface Props {
  initial: ParentDashboardResponse;
}

const RELATION_LABELS: Record<string, string> = {
  anne: "Anne",
  baba: "Baba",
  vasi: "Vasi",
  diger: "Diğer",
};

/**
 * Veli dashboard — Jinja `dashboard.html` feature parity.
 *
 * Çocuk kartları: bugün şeridi + bu hafta progress + 7g rate + istikrar.
 * warning_level border-l-4 + üst-bant subtle tonal background.
 * Tıklanır → /parent/students/{id}
 */
export function ParentDashboardClient({ initial }: Props) {
  const q = useQuery<ParentDashboardResponse>({
    queryKey: parentKeys.dashboard(),
    queryFn: () => getParentDashboard(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const { children } = data;

  return (
    <div className="space-y-6">
      <header>
        <p className="text-[11px] uppercase tracking-wider text-[#117A86] font-semibold">
          <HeartHandshake className="inline size-3.5 mr-1" aria-hidden />
          Veli Görünümü
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          {children.length === 1
            ? "Çocuğunuzun bugünkü ve haftalık durumu"
            : `Velisi olduğunuz ${children.length} öğrencinin durumu`}
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Görev tamamlama oranları, istikrar ve genel ilerleme metrikleri
          aşağıda. Detaylar için kartın üzerine tıklayın.
        </p>
      </header>

      {children.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {children.map((c) => (
            <ChildCard key={c.student_id} child={c} />
          ))}
        </div>
      )}

      <PrivacyNote />
    </div>
  );
}

function ChildCard({ child }: { child: ParentChildSummary }) {
  const tone = warningToneClasses(child.warning_level);
  return (
    <Link
      href={`/parent/students/${child.student_id}`}
      className="group block focus:outline-none focus:ring-2 focus:ring-[#117A86]/40 rounded-lg"
    >
      <Card
        className={cn(
          "overflow-hidden hover:shadow-md transition-shadow border-l-4",
          tone.borderL,
        )}
      >
        <div
          className={cn(
            "px-5 py-3 flex items-center justify-between gap-3",
            tone.bg,
          )}
        >
          <div className="min-w-0">
            <div className="text-base font-semibold truncate">
              {child.full_name}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {child.display_grade_label || (child.grade_level
                ? `${child.grade_level}. Sınıf`
                : null)}
              {child.academic_year ? ` · ${child.academic_year}` : null}
            </div>
          </div>
          <div className="text-right text-xs flex flex-col items-end gap-1">
            {child.is_primary && (
              <span className="inline-block bg-[#117A86]/10 text-[#117A86] px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold">
                Birincil
              </span>
            )}
            {child.relation && (
              <span className="text-muted-foreground">
                {RELATION_LABELS[child.relation] ?? "—"}
              </span>
            )}
          </div>
        </div>

        <CardContent className="p-5 space-y-4">
          {/* Bugün şeridi */}
          <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
              Bugün
            </span>
            <span className="text-sm">
              {child.today_gorev_total > 0 ? (
                <>
                  <span className="font-semibold tabular-nums">
                    {child.today_gorev_done}
                  </span>
                  <span className="text-muted-foreground/60 mx-0.5">/</span>
                  <span className="text-muted-foreground tabular-nums">
                    {child.today_gorev_total}
                  </span>
                  <span className="text-muted-foreground text-xs ml-1">
                    görev
                  </span>
                </>
              ) : (
                <span className="text-muted-foreground italic">
                  bugün görev yok
                </span>
              )}
            </span>
          </div>

          {/* Son 7 gün progress (rolling — "bu hafta" DEĞİL; geçen haftanın
              tamamlanmış günlerini de kapsar) */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="uppercase tracking-wider text-muted-foreground font-medium">
                Son 7 gün
              </span>
              <span className="font-semibold tabular-nums">
                {child.week_gorev_total > 0 ? (
                  <>
                    {child.week_gorev_done}/{child.week_gorev_total} görev
                    {child.week_gorev_rate != null && (
                      <span className="text-muted-foreground ml-1">
                        · %{child.week_gorev_rate}
                      </span>
                    )}
                  </>
                ) : (
                  "—"
                )}
              </span>
            </div>
            {child.week_gorev_total > 0 && (
              <>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn("h-full", tone.bar)}
                    style={{ width: `${child.week_gorev_rate ?? 0}%` }}
                  />
                </div>
                {child.week_test_planned > 0 && (
                  <div className="text-[11px] text-muted-foreground mt-1">
                    Test: {child.week_test_completed}/{child.week_test_planned}{" "}
                    (deneme ayrı sayılır)
                  </div>
                )}
              </>
            )}
          </div>

          {/* 7g rate + istikrar */}
          <div className="grid grid-cols-2 gap-3 pt-1">
            <Stat
              label="Tutturma"
              value={child.rate_7d != null ? `%${child.rate_7d}` : "—"}
              tone={
                child.rate_7d != null ? tone.text : "text-muted-foreground"
              }
              sub="planlanana göre"
            />
            <Stat
              label="İstikrar"
              value={
                child.consistency_7d != null
                  ? `%${child.consistency_7d}`
                  : "—"
              }
              tone="text-foreground"
              sub="7 günde aktif gün"
            />
          </div>

          {/* Son deneme — varsa */}
          {child.latest_exam_count > 0 ? (
            <div className="rounded-lg border border-[#117A86]/20 bg-[#117A86]/5 px-3 py-2.5">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="text-[11px] font-medium uppercase tracking-wider text-[#117A86]">
                  Son Deneme
                </span>
                <span className="text-[10px] text-muted-foreground">
                  toplam {child.latest_exam_count} deneme
                </span>
              </div>
              {child.latest_exam_title ? (
                <div className="truncate text-sm font-medium" title={child.latest_exam_title}>
                  {child.latest_exam_title}
                </div>
              ) : null}
              <div className="mt-1 flex items-center gap-3 text-xs">
                {child.latest_exam_net != null ? (
                  <span className="inline-flex items-baseline gap-1">
                    <span className="text-muted-foreground">Net:</span>
                    <span className="text-base font-bold tabular-nums text-[#117A86]">
                      {child.latest_exam_net.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}
                    </span>
                  </span>
                ) : null}
                {child.latest_exam_section ? (
                  <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-semibold text-[#117A86]">
                    {child.latest_exam_section}
                  </span>
                ) : null}
                {child.latest_exam_date ? (
                  <span className="text-muted-foreground">
                    {formatExamDate(child.latest_exam_date)}
                  </span>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="pt-2 border-t border-border text-xs text-[#117A86] group-hover:text-[#0E5F69] inline-flex items-center gap-0.5">
            Detayları gör
            <ChevronRight
              className="size-3.5 transition-transform group-hover:translate-x-0.5"
              aria-hidden
            />
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function formatExamDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch {
    return iso;
  }
}

function Stat({
  label,
  value,
  tone,
  sub,
}: {
  label: string;
  value: string;
  tone: string;
  sub?: string;
}) {
  return (
    <div className="text-center">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={cn("text-lg font-semibold mt-0.5 tabular-nums", tone)}>
        {value}
      </div>
      {sub ? (
        <div className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
          {sub}
        </div>
      ) : null}
    </div>
  );
}

function EmptyState() {
  return (
    <Card className="border-amber-200 bg-amber-50/40">
      <CardContent className="p-8 text-center">
        <p className="text-sm text-amber-800">
          Henüz size bağlı bir öğrenci yok. Lütfen sizi davet eden eğitim
          koçunuzla iletişime geçin.
        </p>
      </CardContent>
    </Card>
  );
}

function PrivacyNote() {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground flex items-start gap-2">
      <Info className="size-4 shrink-0 mt-0.5 text-[#117A86]" aria-hidden />
      <p className="leading-relaxed">
        <strong className="text-foreground">Bilgi:</strong> Bu panelde size
        görev tamamlama oranı, ders bazında dağılım, istikrar, genel ilerleme ve
        deneme net sonuçları gösterilir. Konu bazında doğru-yanlış kırılımı ve
        öğrenci-koç arasındaki çalışma notları gizlilik gereği paylaşılmaz.
      </p>
    </div>
  );
}

function warningToneClasses(level: WarningLevel): {
  borderL: string;
  bg: string;
  bar: string;
  text: string;
} {
  if (level === "red") {
    return {
      borderL: "border-l-rose-500",
      bg: "bg-rose-50/60",
      bar: "bg-rose-500",
      text: "text-rose-700",
    };
  }
  if (level === "amber") {
    return {
      borderL: "border-l-amber-500",
      bg: "bg-amber-50/60",
      bar: "bg-amber-500",
      text: "text-amber-700",
    };
  }
  return {
    borderL: "border-l-emerald-500",
    bg: "bg-emerald-50/60",
    bar: "bg-emerald-500",
    text: "text-emerald-700",
  };
}

export { warningToneClasses, RELATION_LABELS };
