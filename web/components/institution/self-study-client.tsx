"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, TentTree } from "lucide-react";

import {
  getInstitutionSelfStudyReport,
  institutionKeys,
} from "@/lib/api/institution";
import type {
  InstitutionSelfStudyReportResponse,
  SelfStudyReportCoachRow,
  SelfStudyReportEntryRow,
} from "@/lib/types/institution";
import { cn } from "@/lib/utils";

/**
 * Bağımsız Çalışma Girişleri raporu — kurum yöneticisi görünürlük yüzeyi.
 * Engelleme yok: kim/ne kadar/beyanlı mı şeffaflaşır; "beyansız yüklü giriş"
 * satırı dikkat işareti alır (tatil dönüşü meşru olabilir — koçla konuşulur).
 */

const DAY_OPTIONS = [7, 30, 90] as const;

const SOURCE_LABEL: Record<string, string> = {
  student: "Öğrenci beyanı",
  coach: "Koç girişi",
};
const STATUS_LABEL: Record<string, string> = {
  pending: "Onay bekliyor",
  approved: "Onaylandı",
  rejected: "Reddedildi",
};
const STATUS_TONE: Record<string, string> = {
  pending: "bg-amber-500/10 text-amber-800 dark:text-amber-200",
  approved: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
  rejected: "bg-rose-500/10 text-rose-800 dark:text-rose-200",
};

function fmtDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function InstitutionSelfStudyClient({
  initial,
}: {
  initial: InstitutionSelfStudyReportResponse;
}) {
  const [days, setDays] = React.useState(30);
  const q = useQuery({
    queryKey: institutionKeys.selfStudyReport(days),
    queryFn: () => getInstitutionSelfStudyReport(days),
    initialData: days === 30 ? initial : undefined,
    staleTime: 60_000,
  });
  const data = q.data ?? initial;
  const s = data.summary;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-bold tracking-tight flex items-center gap-2">
          <TentTree className="size-6 text-cyan-600 dark:text-cyan-400" aria-hidden />
          Bağımsız Çalışma Girişleri
        </h1>
        <p className="text-sm text-muted-foreground max-w-3xl">
          Koçların programa girmeden (tatil, kurs, öğrencinin kendi çalışması)
          kitap ilerlemesine işlediği testler. Her giriş kayıtlıdır: kim girdi,
          ne zaman, öğrenci beyanıyla mı yoksa koç tek taraflı mı.
        </p>
      </header>

      <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm flex items-start gap-2.5">
        <Info className="size-4 text-sky-600 dark:text-sky-400 shrink-0 mt-0.5" aria-hidden />
        <div className="space-y-1 text-sky-900 dark:text-sky-200">
          <p>
            <strong>Bu girişler kurumun uyum ve karne metriklerini DEĞİŞTİRMEZ</strong>{" "}
            — o metrikler yalnız programdaki görevlerden hesaplanır. Elle girişler
            müfredat kapsamasını, sınava yetişme tahminini ve veli ekranındaki ders
            ilerlemesini etkiler; bu rapor o girişlerin denetim yüzeyidir.
          </p>
          <p className="text-xs opacity-90">
            Dikkat işareti = dönemde öğrenci beyanı olmadan yüklü koç girişi
            (200+ test ve girişlerin %80+&apos;i tek taraflı). Tatil dönüşü toplu
            güncelleme meşru olabilir — işaret suçlama değil, konuşma daveti.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-muted-foreground">Dönem:</span>
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => setDays(d)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              days === d
                ? "border-foreground bg-foreground text-background"
                : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            Son {d} gün
          </button>
        ))}
        {q.isFetching ? (
          <span className="text-xs text-muted-foreground">güncelleniyor…</span>
        ) : null}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi
          label="İşlenen test"
          value={s.applied_tests_total}
          hint={`${s.entries_total} giriş kaydı`}
        />
        <Kpi
          label="Öğrenci beyanıyla"
          value={s.student_declared_tests}
          hint="koç onayından geçti"
          tone="emerald"
        />
        <Kpi
          label="Koç tek taraflı"
          value={s.coach_direct_tests}
          hint="beyansız giriş"
          tone="amber"
        />
        <Kpi
          label="Dikkat işareti"
          value={s.attention_count}
          hint={`${s.coaches_with_entries} koç giriş yaptı`}
          tone={s.attention_count > 0 ? "rose" : undefined}
        />
      </div>

      <section className="space-y-2">
        <h2 className="font-display text-lg font-semibold tracking-tight">
          Koç kırılımı
        </h2>
        {data.coaches.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
            Bu dönemde hiç bağımsız çalışma girişi yok.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Koç</th>
                  <th className="px-3 py-2 font-medium text-right">İşlenen test</th>
                  <th className="px-3 py-2 font-medium text-right">Öğrenci beyanı</th>
                  <th className="px-3 py-2 font-medium text-right">Koç girişi</th>
                  <th className="px-3 py-2 font-medium text-right">Tek taraflı payı</th>
                  <th className="px-3 py-2 font-medium text-right">Öğrenci</th>
                  <th className="px-3 py-2 font-medium text-right">Bekleyen</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.coaches.map((c) => (
                  <CoachRow key={c.coach_id} row={c} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="font-display text-lg font-semibold tracking-tight">
          Son girişler
        </h2>
        {data.recent.length === 0 ? (
          <p className="text-sm text-muted-foreground">Kayıt yok.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Zaman</th>
                  <th className="px-3 py-2 font-medium">Koç</th>
                  <th className="px-3 py-2 font-medium">Öğrenci</th>
                  <th className="px-3 py-2 font-medium">Kitap · Bölüm</th>
                  <th className="px-3 py-2 font-medium text-right">Test</th>
                  <th className="px-3 py-2 font-medium">Kaynak</th>
                  <th className="px-3 py-2 font-medium">Durum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.recent.map((r) => (
                  <EntryRow key={r.id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  tone?: "emerald" | "amber" | "rose";
}) {
  const toneCls =
    tone === "emerald"
      ? "text-emerald-700 dark:text-emerald-300"
      : tone === "amber"
        ? "text-amber-700 dark:text-amber-300"
        : tone === "rose"
          ? "text-rose-700 dark:text-rose-300"
          : "text-foreground";
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-2xl font-bold tabular-nums", toneCls)}>{value}</p>
      <p className="text-[11px] text-muted-foreground mt-0.5">{hint}</p>
    </div>
  );
}

function CoachRow({ row: c }: { row: SelfStudyReportCoachRow }) {
  return (
    <tr
      className={cn(
        c.attention &&
          "bg-amber-500/10 border-l-4 border-l-amber-500",
      )}
    >
      <td className="px-3 py-2">
        <span className="font-medium">{c.coach_name}</span>
        {c.attention ? (
          <span
            className="ml-2 inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:text-amber-200"
            title="Dönemde öğrenci beyanı olmadan yüklü giriş — koçla konuşulmalı (tatil dönüşü meşru olabilir)."
          >
            <AlertTriangle className="size-3" aria-hidden />
            beyansız yüklü giriş
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2 text-right tabular-nums font-medium">
        {c.applied_tests}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-emerald-700 dark:text-emerald-300">
        {c.student_declared_tests}
      </td>
      <td className="px-3 py-2 text-right tabular-nums text-amber-700 dark:text-amber-300">
        {c.coach_direct_tests}
      </td>
      <td className="px-3 py-2 text-right tabular-nums">
        %{c.coach_direct_share_pct}
      </td>
      <td className="px-3 py-2 text-right tabular-nums">{c.student_count}</td>
      <td className="px-3 py-2 text-right tabular-nums">
        {c.pending_count > 0 ? c.pending_count : "—"}
      </td>
    </tr>
  );
}

function EntryRow({ row: r }: { row: SelfStudyReportEntryRow }) {
  return (
    <tr>
      <td className="px-3 py-2 whitespace-nowrap text-xs text-muted-foreground">
        {fmtDateTime(r.created_at)}
      </td>
      <td className="px-3 py-2">{r.coach_name}</td>
      <td className="px-3 py-2">{r.student_name}</td>
      <td className="px-3 py-2 max-w-[260px]">
        <span className="block truncate" title={`${r.book_name} · ${r.section_label}`}>
          {r.book_name} <span className="text-muted-foreground">· {r.section_label}</span>
        </span>
        {r.note ? (
          <span className="block truncate text-[11px] text-muted-foreground italic">
            “{r.note}”
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2 text-right tabular-nums">
        {r.status === "approved" ? r.applied_count : r.test_count}
      </td>
      <td className="px-3 py-2 text-xs">
        <span
          className={cn(
            r.source === "coach"
              ? "text-amber-700 dark:text-amber-300"
              : "text-emerald-700 dark:text-emerald-300",
          )}
        >
          {SOURCE_LABEL[r.source] ?? r.source}
        </span>
      </td>
      <td className="px-3 py-2">
        <span
          className={cn(
            "inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium",
            STATUS_TONE[r.status] ?? "bg-muted text-muted-foreground",
          )}
        >
          {STATUS_LABEL[r.status] ?? r.status}
        </span>
      </td>
    </tr>
  );
}
