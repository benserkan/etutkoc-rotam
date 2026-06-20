"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Banknote,
  Calendar,
  CheckCircle2,
  CircleSlash,
  Clock,
  CreditCard,
  Phone,
  Receipt,
  Sofa,
  Wifi,
  XCircle,
} from "lucide-react";

import { getParentStudentSessions, parentKeys } from "@/lib/api/parent";
import type {
  ParentBillingMonth,
  ParentPaymentItem,
  ParentSessionItem,
  ParentSessionsResponse,
} from "@/lib/types/parent";
import { cn } from "@/lib/utils";

interface Props {
  initial: ParentSessionsResponse;
  studentId: number;
}

const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${TR_MONTHS[m - 1]} ${y}`;
}

function fmtTL(n: number): string {
  return new Intl.NumberFormat("tr-TR", {
    style: "currency",
    currency: "TRY",
    maximumFractionDigits: 0,
  }).format(n);
}

const STATUS_TONE: Record<string, string> = {
  done: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  postponed: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  cancelled: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  no_show: "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-200",
};

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  done: CheckCircle2,
  postponed: Clock,
  cancelled: XCircle,
  no_show: CircleSlash,
};

const CHANNEL_ICON: Record<string, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  in_person: Sofa,
  online: Wifi,
  phone: Phone,
};

const PAYMENT_METHOD_ICON: Record<string, React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>> = {
  cash: Banknote,
  transfer: CreditCard,
  other: Receipt,
};

export function ParentSessionsClient({ initial, studentId }: Props) {
  const [months, setMonths] = React.useState<number>(12);

  const q = useQuery({
    queryKey: parentKeys.studentSessions(studentId, months),
    queryFn: () => getParentStudentSessions(studentId, months),
    initialData: months === 12 ? initial : undefined,
    staleTime: 30_000,
  });

  const data = q.data ?? initial;
  const { sessions, billing, student_name } = data;

  return (
    <div className="px-3 sm:px-6 py-4 max-w-5xl mx-auto">
      {/* Geri linki */}
      <div className="mb-3">
        <Link
          href={`/parent/students/${studentId}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          {student_name} profiline geri dön
        </Link>
      </div>

      <header className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight">
          Seans Hareketleri
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Yapılan koçluk seansları + tahsilat kaydı.{" "}
          <span className="inline-block text-[11px] bg-muted px-1.5 py-0.5 rounded">
            Koça-özel notlar görünmez
          </span>
        </p>
      </header>

      {/* Açık hesap kartı */}
      <BalanceCard billing={billing} />

      {/* Pencere seçici */}
      <div className="mb-3 flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
          Pencere:
        </span>
        {[3, 6, 12, 24].map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMonths(m)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium border transition",
              months === m
                ? "border-foreground bg-foreground text-background"
                : "border-border bg-card text-foreground hover:bg-muted/50",
            )}
          >
            {m} ay
          </button>
        ))}
      </div>

      {/* 3 kolon: Aylık özet + Son seanslar + Son ödemeler — mobilde tek kolon */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="bg-card border border-border rounded-lg overflow-hidden">
          <header className="px-4 py-2.5 border-b border-border bg-muted/30">
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <Calendar className="size-4 text-muted-foreground" aria-hidden />
              Aylık Hesap
            </h2>
          </header>
          <MonthsTable months={billing.months} />
        </section>

        <section className="bg-card border border-border rounded-lg overflow-hidden">
          <header className="px-4 py-2.5 border-b border-border bg-muted/30">
            <h2 className="text-sm font-semibold flex items-center gap-1.5">
              <Clock className="size-4 text-muted-foreground" aria-hidden />
              Seans Listesi
            </h2>
          </header>
          <SessionsList sessions={sessions} />
        </section>
      </div>

      <section className="mt-4 bg-card border border-border rounded-lg overflow-hidden">
        <header className="px-4 py-2.5 border-b border-border bg-muted/30">
          <h2 className="text-sm font-semibold flex items-center gap-1.5">
            <Receipt className="size-4 text-muted-foreground" aria-hidden />
            Ödemeler
          </h2>
        </header>
        <PaymentsList payments={billing.payments} />
      </section>

      <p className="mt-4 text-[11px] text-muted-foreground italic">
        Bu sayfadaki tüm bilgiler koçunuzun girdiği seans + tahsilat
        kayıtlarına dayanır. Bir tutarsızlık fark ederseniz lütfen koçunuzla
        iletişime geçin.
      </p>
    </div>
  );
}

function BalanceCard({ billing }: { billing: ParentSessionsResponse["billing"] }) {
  const balanceTone =
    billing.open_balance > 0
      ? "rose"
      : billing.open_balance < 0
        ? "sky"
        : "emerald";
  const toneClass: Record<string, string> = {
    rose: "border-rose-200 bg-rose-50 text-rose-900 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
    sky: "border-sky-200 bg-sky-50 text-sky-900 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  };
  return (
    <div
      className={cn(
        "rounded-lg border-2 p-4 mb-4 flex flex-wrap items-baseline justify-between gap-4",
        toneClass[balanceTone],
      )}
    >
      <div>
        <p className="text-xs uppercase tracking-wider font-medium opacity-80">
          {billing.open_balance > 0
            ? "Açık Hesap"
            : billing.open_balance < 0
              ? "Fazla Ödenmiş"
              : "Hesap Kapalı"}
        </p>
        <p className="text-3xl font-bold tabular-nums mt-1">
          {fmtTL(Math.abs(billing.open_balance))}
        </p>
        <p className="text-[11px] mt-0.5 opacity-70">
          Tahakkuk: {fmtTL(billing.total_accrued)} · Ödenen:{" "}
          {fmtTL(billing.total_paid)}
        </p>
      </div>
      <div className="text-right">
        <p className="text-xs uppercase tracking-wider font-medium opacity-80">
          Seans Ücreti
        </p>
        <p className="text-xl font-semibold tabular-nums mt-1">
          {billing.session_fee > 0
            ? fmtTL(billing.session_fee)
            : "—"}
        </p>
        <p className="text-[11px] mt-0.5 opacity-70">
          {billing.session_fee > 0
            ? "yapılan her seans"
            : "ücret henüz belirlenmedi"}
        </p>
      </div>
    </div>
  );
}

function MonthsTable({ months }: { months: ParentBillingMonth[] }) {
  if (months.length === 0) {
    return (
      <p className="px-4 py-6 text-sm italic text-muted-foreground text-center">
        Bu pencerede aylık hareket yok.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Ay</th>
            <th className="px-3 py-2 text-right font-medium">Seans</th>
            <th className="px-3 py-2 text-right font-medium">Tahakkuk</th>
            <th className="px-3 py-2 text-right font-medium">Ödenen</th>
            <th className="px-3 py-2 text-right font-medium">Kalan</th>
          </tr>
        </thead>
        <tbody>
          {/* En yeni → en eski */}
          {[...months].reverse().map((m) => {
            const balanceTone =
              m.balance > 0
                ? "text-rose-700"
                : m.balance < 0
                  ? "text-sky-700"
                  : "text-emerald-700";
            return (
              <tr key={m.period_month} className="border-b border-border/50 last:border-0">
                <td className="px-3 py-2 font-medium">{m.period_label}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {m.sessions_done}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                  {m.accrued > 0 ? fmtTL(m.accrued) : "—"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">
                  {m.paid > 0 ? fmtTL(m.paid) : "—"}
                </td>
                <td className={cn("px-3 py-2 text-right tabular-nums font-semibold", balanceTone)}>
                  {m.balance !== 0 ? fmtTL(Math.abs(m.balance)) : "—"}
                  {m.balance < 0 ? (
                    <span className="text-[10px] ml-1">fazla</span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SessionsList({ sessions }: { sessions: ParentSessionItem[] }) {
  if (sessions.length === 0) {
    return (
      <p className="px-4 py-6 text-sm italic text-muted-foreground text-center">
        Bu pencerede seans kaydı yok.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border max-h-[480px] overflow-y-auto">
      {sessions.map((s) => {
        const StatusIcon = STATUS_ICON[s.status] ?? AlertCircle;
        const ChannelIcon = s.channel ? CHANNEL_ICON[s.channel] : null;
        return (
          <li key={s.id} className="px-3 py-2.5 flex items-start gap-3">
            <span
              className={cn(
                "inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium uppercase tracking-wider whitespace-nowrap mt-0.5",
                STATUS_TONE[s.status] ?? STATUS_TONE.no_show,
              )}
            >
              <StatusIcon className="size-3" aria-hidden />
              {s.status_label}
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground">
                {fmtDate(s.session_date)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center flex-wrap gap-x-2">
                {s.duration_min ? (
                  <span className="inline-flex items-center gap-0.5">
                    <Clock className="size-3" aria-hidden />
                    {s.duration_min} dk
                  </span>
                ) : null}
                {s.channel_label ? (
                  <span className="inline-flex items-center gap-0.5">
                    {ChannelIcon ? (
                      <ChannelIcon className="size-3" aria-hidden />
                    ) : null}
                    {s.channel_label}
                  </span>
                ) : null}
              </p>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function PaymentsList({ payments }: { payments: ParentPaymentItem[] }) {
  if (payments.length === 0) {
    return (
      <p className="px-4 py-6 text-sm italic text-muted-foreground text-center">
        Bu pencerede ödeme kaydı yok.
      </p>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {payments.map((p) => {
        const Icon = PAYMENT_METHOD_ICON[p.method] ?? Receipt;
        return (
          <li key={p.id} className="px-3 py-2.5 flex items-start gap-3">
            <div className="size-8 inline-flex items-center justify-center rounded-md bg-emerald-50 border border-emerald-200 text-emerald-700 flex-shrink-0 mt-0.5 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
              <Icon className="size-4" aria-hidden />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-emerald-700 tabular-nums">
                {fmtTL(p.amount)}
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center flex-wrap gap-x-2">
                <span>{fmtDate(p.paid_at)}</span>
                <span className="text-muted-foreground/50">·</span>
                <span>{p.method_label}</span>
                {p.period_month ? (
                  <>
                    <span className="text-muted-foreground/50">·</span>
                    <span className="text-foreground/80">
                      kapatılan: {p.period_month}
                    </span>
                  </>
                ) : null}
              </p>
              {p.note ? (
                <p className="text-[11px] text-muted-foreground italic mt-0.5 border-l-2 border-border pl-2">
                  {p.note}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
