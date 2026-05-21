"use client";

import * as React from "react";
import {
  BookOpen,
  Calculator,
  CheckCircle2,
  FlaskConical,
  Globe,
  Landmark,
  MessageCircle,
  Moon,
  Flame,
  TrendingUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Landing feature kartı sağ-yan görselleri. Jinja `landing/mockups/*.html`
 * FEATURE paritesi (aynı veriyi gösterir) — ama tamamen yeniden tasarlandı
 * (emoji yok, Lucide ikon, fresh palet). mockup_type → component map.
 */

function Panel({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "w-full rounded-2xl border border-border bg-card/80 p-4 shadow-sm backdrop-blur",
        className,
      )}
    >
      {children}
    </div>
  );
}

function DailySchedule() {
  const rows = [
    { time: "09:00", icon: Calculator, subj: "Matematik", topic: "Üçgenlerde benzerlik", count: "8 soru", tag: "Yeni", tone: "text-cyan-700 bg-cyan-50" },
    { time: "11:00", icon: BookOpen, subj: "Türkçe", topic: "Cümlede anlam", count: "10 soru", tag: "Yeni", tone: "text-emerald-600 bg-emerald-50" },
    { time: "14:00", icon: FlaskConical, subj: "Fen", topic: "Hücre bölünmesi", count: "6 soru", tag: "Tekrar", tone: "text-amber-600 bg-amber-50" },
    { time: "16:00", icon: Landmark, subj: "Sosyal", topic: "Atatürkçülük", count: "5 soru", tag: "Yeni", tone: "text-rose-600 bg-rose-50" },
    { time: "20:00", icon: Globe, subj: "İngilizce", topic: "Kelime tekrar", count: "12 kart", tag: "FSRS", tone: "text-violet-600 bg-violet-50" },
  ];
  return (
    <Panel>
      <div className="mb-3 flex items-center justify-between border-b border-border pb-2">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Salı, 11 Mayıs</p>
          <p className="font-display text-sm font-bold">Ayşe K. · 8. sınıf</p>
        </div>
        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
          <CheckCircle2 className="size-3" aria-hidden /> Planlandı
        </span>
      </div>
      <div className="space-y-1.5">
        {rows.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.time} className="flex items-center gap-2 rounded-lg px-1.5 py-1.5 transition hover:bg-muted">
              <span className="w-10 shrink-0 font-mono text-[10px] font-bold text-muted-foreground">{r.time}</span>
              <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              <p className="min-w-0 flex-1 truncate text-[11px] font-semibold">
                {r.subj} <span className="font-normal text-muted-foreground">· {r.topic}</span>
              </p>
              <span className="shrink-0 text-[10px] font-bold text-muted-foreground">{r.count}</span>
              <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold", r.tone)}>{r.tag}</span>
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 flex items-center justify-between border-t border-border pt-2.5 text-[11px]">
        <span className="text-muted-foreground">Toplam: <b className="text-foreground">5 görev</b> · ~95 dk</span>
      </div>
    </Panel>
  );
}

function FsrsRating() {
  const btns = [
    { label: "Tekrar", cls: "bg-rose-50 text-rose-700" },
    { label: "Zor", cls: "bg-amber-50 text-amber-700" },
    { label: "İyi", cls: "bg-emerald-50 text-emerald-700" },
    { label: "Kolay", cls: "bg-sky-50 text-sky-700" },
  ];
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">Bugünkü kart</span>
        <span className="font-mono text-[9px] text-muted-foreground">1 / 8</span>
      </div>
      <p className="mb-3 text-xs font-semibold leading-snug">Üçgenlerde benzerlik · Geometri</p>
      <div className="grid grid-cols-2 gap-1.5">
        {btns.map((b) => (
          <button key={b.label} type="button" className={cn("rounded-md py-1.5 text-[10px] font-bold transition hover:brightness-95", b.cls)}>
            {b.label}
          </button>
        ))}
      </div>
    </Panel>
  );
}

function BurnoutGauge() {
  const chips = [
    { icon: Moon, label: "Gece kuşu", cls: "bg-rose-50 text-rose-700" },
    { icon: TrendingUp, label: "Yoğunluk", cls: "bg-rose-50 text-rose-700" },
    { icon: Flame, label: "Streak risk", cls: "bg-amber-50 text-amber-700" },
  ];
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">Tükenmişlik riski</span>
        <span className="text-xs font-extrabold text-rose-600">73<span className="font-medium text-muted-foreground">/100</span></span>
      </div>
      <div className="mb-2.5 h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-gradient-to-r from-amber-400 via-orange-500 to-rose-600" style={{ width: "73%" }} />
      </div>
      <div className="flex flex-wrap gap-1">
        {chips.map((c) => {
          const Icon = c.icon;
          return (
            <span key={c.label} className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-semibold", c.cls)}>
              <Icon className="size-2.5" aria-hidden /> {c.label}
            </span>
          );
        })}
      </div>
    </Panel>
  );
}

function BooksProgress() {
  const books = [
    { name: "Matematik", pct: 80, cls: "bg-cyan-600" },
    { name: "Türkçe", pct: 100, cls: "bg-emerald-500" },
    { name: "Fen", pct: 40, cls: "bg-amber-500" },
  ];
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[9px] font-bold uppercase tracking-wider text-muted-foreground">Kitap envanteri</span>
        <span className="font-mono text-[9px] text-muted-foreground">3/4</span>
      </div>
      {books.map((b) => (
        <div key={b.name} className="mb-1.5">
          <div className="mb-0.5 flex items-center justify-between">
            <span className="text-[10px] font-semibold">{b.name}</span>
            <span className="text-[10px] font-bold text-muted-foreground">%{b.pct}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className={cn("h-full rounded-full", b.cls)} style={{ width: `${b.pct}%` }} />
          </div>
        </div>
      ))}
    </Panel>
  );
}

function WhatsappChat() {
  return (
    <Panel>
      <div className="mb-2 flex items-center gap-1.5">
        <span className="flex size-5 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">A</span>
        <span className="text-[9px] font-semibold">Ayşe&apos;nin annesi</span>
        <MessageCircle className="ml-auto size-3 text-emerald-600" aria-hidden />
      </div>
      <div className="mb-1 rounded-lg border border-border bg-background px-2 py-1.5 text-[10px] leading-snug shadow-sm">
        <b className="text-emerald-700">Haftalık karne</b>
        <br />Tamamlama: %72 · Streak: 12 gün
      </div>
      <div className="ml-auto max-w-[85%] rounded-lg bg-emerald-100 px-2 py-1.5 text-[10px] leading-snug text-emerald-900 shadow-sm">
        &quot;Süper iş, teşekkürler!&quot;
      </div>
    </Panel>
  );
}

const MAP: Record<string, React.ComponentType> = {
  daily_schedule: DailySchedule,
  fsrs_rating: FsrsRating,
  burnout_gauge: BurnoutGauge,
  books_progress: BooksProgress,
  whatsapp_chat: WhatsappChat,
};

export function MockupByType({ type }: { type: string | null }) {
  if (!type) return null;
  const Cmp = MAP[type];
  if (!Cmp) return null;
  return <Cmp />;
}
