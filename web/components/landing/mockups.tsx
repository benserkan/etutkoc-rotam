"use client";

import * as React from "react";
import {
  Activity,
  Award,
  BarChart3,
  BookOpen,
  Bot,
  BrainCircuit,
  Building2,
  Calculator,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  FlaskConical,
  Gauge,
  Globe,
  GraduationCap,
  Landmark,
  LifeBuoy,
  Lock,
  MessageCircle,
  MessageSquareText,
  Moon,
  Phone,
  Receipt,
  Flame,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Timer,
  TrendingUp,
  Users,
  Zap,
  type LucideIcon,
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

/**
 * Genel/şablonsuz kart görseli — bespoke mockup gerektirmeyen (temalı/AI-gruplu)
 * kartlar için marka temalı panel. Kart gövdesi zaten fayda listesini gösterir;
 * bu sağ-yan görsel "ürün ekranı" hissi verir.
 */
function GenericShowcase() {
  const rows = [
    { icon: Sparkles, w: "w-[88%]", tone: "text-cyan-700 bg-cyan-50" },
    { icon: TrendingUp, w: "w-[70%]", tone: "text-emerald-600 bg-emerald-50" },
    { icon: CheckCircle2, w: "w-[78%]", tone: "text-violet-600 bg-violet-50" },
    { icon: MessageCircle, w: "w-[62%]", tone: "text-amber-600 bg-amber-50" },
  ];
  return (
    <Panel>
      <div className="flex items-center gap-2">
        <span className="inline-flex size-7 items-center justify-center rounded-lg bg-cyan-600 text-white">
          <Sparkles className="size-4" aria-hidden />
        </span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Öne çıkan özellikler
        </span>
      </div>
      <div className="mt-3 space-y-2.5">
        {rows.map((r, i) => {
          const Icon = r.icon;
          return (
            <div key={i} className="flex items-center gap-2">
              <span className={cn("inline-flex size-6 items-center justify-center rounded-md", r.tone)}>
                <Icon className="size-3.5" aria-hidden />
              </span>
              <span className="flex-1">
                <span className={cn("block h-2 rounded-full bg-foreground/10", r.w)} />
              </span>
              <CheckCircle2 className="size-4 text-emerald-500" aria-hidden />
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/** Motivasyon / oyunlaştırma — seri + seviye + rozetler + puan. */
function Gamification() {
  const badges = [
    { icon: Flame, label: "7 günlük seri", tone: "text-amber-600 bg-amber-50" },
    { icon: Star, label: "Hız ustası", tone: "text-violet-600 bg-violet-50" },
    { icon: Zap, label: "Odak", tone: "text-cyan-700 bg-cyan-50" },
  ];
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
          <Award className="size-4 text-amber-500" aria-hidden /> Seviye 4
        </span>
        <span className="text-[11px] font-semibold text-amber-600">+120 puan bugün</span>
      </div>
      <div className="mt-2 h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full w-[72%] rounded-full bg-gradient-to-r from-amber-400 to-cyan-500" />
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {badges.map((b) => {
          const Icon = b.icon;
          return (
            <span key={b.label} className={cn("inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium", b.tone)}>
              <Icon className="size-3" aria-hidden /> {b.label}
            </span>
          );
        })}
      </div>
    </Panel>
  );
}

/** Yapay zeka asistanı — "bugün şunu konuş" öneri baloncuğu. */
function AiAssistant() {
  return (
    <Panel>
      <div className="flex items-center gap-2">
        <span className="inline-flex size-7 items-center justify-center rounded-lg bg-violet-600 text-white">
          <Bot className="size-4" aria-hidden />
        </span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Yapay Zeka Önerisi
        </span>
      </div>
      <div className="mt-3 rounded-2xl rounded-tl-sm bg-violet-50 p-3 text-[12px] leading-relaxed text-violet-900">
        <b>Bugün Elif ile şunu konuş:</b> matematikte son 3 denemede net düştü;
        önce eksik konuyu birlikte belirleyin.
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-cyan-50 px-2 py-1 text-[11px] text-cyan-700">Gündem hazır</span>
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">Sesle not</span>
      </div>
    </Panel>
  );
}

/** Deneme / net gelişimi — mini bar grafiği + son deneme skoru. */
function ExamTrend() {
  const bars = [40, 52, 48, 63, 71, 78];
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
          Net Gelişimi
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
          <TrendingUp className="size-3.5" aria-hidden /> +6 net
        </span>
      </div>
      <div className="mt-3 flex h-20 items-end gap-1.5">
        {bars.map((h, i) => (
          <div
            key={i}
            className={cn("flex-1 rounded-t", i === bars.length - 1 ? "bg-cyan-600" : "bg-cyan-200")}
            style={{ height: `${h}%` }}
          />
        ))}
      </div>
      <p className="mt-2 text-[12px] text-slate-700">
        Son deneme: <b className="text-cyan-800">78 net</b>
      </p>
    </Panel>
  );
}

/** Güvenlik / KVKK — kalkan + şifreli/uyumlu satırları + rol-bazlı erişim. */
function Security() {
  const rows = [
    { icon: Lock, label: "Tüm veriler şifreli saklanır" },
    { icon: ShieldCheck, label: "KVKK uyumlu altyapı" },
    { icon: CheckCircle2, label: "Rol-bazlı erişim kontrolü" },
  ];
  return (
    <Panel>
      <div className="flex items-center gap-2">
        <span className="inline-flex size-9 items-center justify-center rounded-xl bg-emerald-600 text-white">
          <ShieldCheck className="size-5" aria-hidden />
        </span>
        <div>
          <p className="text-sm font-bold text-slate-800">Verileriniz güvende</p>
          <p className="text-[11px] text-emerald-600">256-bit şifreleme · KVKK</p>
        </div>
      </div>
      <div className="mt-3 space-y-1.5">
        {rows.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.label} className="flex items-center gap-2 rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[12px] text-emerald-900">
              <Icon className="size-3.5 shrink-0 text-emerald-600" aria-hidden /> {r.label}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/** Ödeme / üyelik / tahsilat — plan kartı + ödeme satırı + yenileme. */
function Billing() {
  return (
    <Panel>
      <div className="flex items-center justify-between rounded-xl bg-gradient-to-r from-cyan-600 to-cyan-500 p-3 text-white">
        <div>
          <p className="text-[10px] font-medium uppercase tracking-wider text-cyan-100">Aktif paket</p>
          <p className="text-sm font-bold">Solo · Aylık</p>
        </div>
        <CreditCard className="size-6 text-cyan-100" aria-hidden />
      </div>
      <div className="mt-2.5 flex items-center justify-between rounded-lg bg-emerald-50 px-2.5 py-2 text-[12px]">
        <span className="inline-flex items-center gap-1.5 text-emerald-800">
          <Receipt className="size-3.5" aria-hidden /> 2.500 ₺
        </span>
        <span className="inline-flex items-center gap-1 font-semibold text-emerald-700">
          <CheckCircle2 className="size-3.5" aria-hidden /> Ödendi
        </span>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Sonraki yenileme: 12 Tem</p>
    </Panel>
  );
}

/** Veri analizi / panel — KPI kartları + mini çizgi grafik. */
function Analytics() {
  const bars = [30, 45, 38, 60, 52, 70, 64];
  return (
    <Panel>
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
          <BarChart3 className="size-4 text-violet-600" aria-hidden /> Panel
        </span>
        <span className="text-[11px] font-semibold text-emerald-600">↑ %12</span>
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <div className="rounded-lg bg-violet-50 px-2 py-1.5">
          <p className="text-[10px] text-violet-500">Aktif öğrenci</p>
          <p className="text-base font-bold text-violet-800">128</p>
        </div>
        <div className="rounded-lg bg-cyan-50 px-2 py-1.5">
          <p className="text-[10px] text-cyan-600">Tamamlama</p>
          <p className="text-base font-bold text-cyan-800">%74</p>
        </div>
      </div>
      <div className="mt-2 flex h-12 items-end gap-1">
        {bars.map((h, i) => (
          <div key={i} className="flex-1 rounded-t bg-violet-300" style={{ height: `${h}%` }} />
        ))}
      </div>
    </Panel>
  );
}

/** CRM — kişi satırları + aşama rozetleri + not. */
function Crm() {
  const rows = [
    { name: "Atlas Dershanesi", stage: "Görüşüldü", tone: "bg-amber-100 text-amber-700" },
    { name: "Bağımsız Koç · Elif", stage: "Kazanıldı", tone: "bg-emerald-100 text-emerald-700" },
    { name: "Final Etüt", stage: "Yeni", tone: "bg-cyan-100 text-cyan-700" },
  ];
  return (
    <Panel>
      <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
        <Users className="size-4 text-cyan-700" aria-hidden /> Müşteri İlişkileri
      </span>
      <div className="mt-2.5 space-y-1.5">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center justify-between rounded-lg border border-border bg-card px-2.5 py-1.5">
            <span className="inline-flex items-center gap-1.5 text-[12px] text-slate-700">
              <Phone className="size-3 text-slate-400" aria-hidden /> {r.name}
            </span>
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", r.tone)}>{r.stage}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/** Kurumsal kimlik / co-branding — logolu panel başlığı önizlemesi. */
function Branding() {
  return (
    <Panel>
      <div className="flex items-center gap-2 rounded-xl border border-dashed border-cyan-300 bg-cyan-50/60 p-3">
        <span className="inline-flex size-10 items-center justify-center rounded-lg bg-white shadow-sm">
          <Building2 className="size-5 text-cyan-700" aria-hidden />
        </span>
        <div>
          <p className="text-sm font-bold text-slate-800">Kurumunuzun Adı</p>
          <p className="text-[11px] text-slate-500">Paneliniz kendi logonuzla</p>
        </div>
      </div>
      <div className="mt-2.5 flex items-center gap-2">
        <span className="text-[11px] text-slate-500">Marka rengi:</span>
        <span className="size-4 rounded-full bg-cyan-600" />
        <span className="size-4 rounded-full bg-amber-500" />
        <span className="size-4 rounded-full bg-emerald-600" />
      </div>
    </Panel>
  );
}

/** Destek / sistem sağlığı — talep durumu + yeşil sistem göstergeleri. */
function Support() {
  const sys = ["Web", "Veritabanı", "Bildirim"];
  return (
    <Panel>
      <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-2.5 py-2">
        <span className="inline-flex items-center gap-1.5 text-[12px] text-emerald-900">
          <LifeBuoy className="size-3.5 text-emerald-600" aria-hidden /> Destek talebi #482
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700">
          <CheckCircle2 className="size-3.5" aria-hidden /> Çözüldü
        </span>
      </div>
      <div className="mt-2.5 space-y-1.5">
        {sys.map((s) => (
          <div key={s} className="flex items-center justify-between text-[12px] text-slate-700">
            <span className="inline-flex items-center gap-1.5">
              <Activity className="size-3.5 text-slate-400" aria-hidden /> {s}
            </span>
            <span className="inline-flex items-center gap-1 text-emerald-600">
              <span className="size-2 rounded-full bg-emerald-500" /> Çalışıyor
            </span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/** Akademik yapı / müfredat — sınıf seviyesi + müfredat modeli rozetleri. */
function Curriculum() {
  return (
    <Panel>
      <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
        <GraduationCap className="size-4 text-cyan-700" aria-hidden /> Her seviyeye uyumlu
      </span>
      <div className="mt-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">LGS</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {["5", "6", "7", "8"].map((g) => (
            <span key={g} className="rounded-md bg-cyan-50 px-2 py-0.5 text-[11px] font-medium text-cyan-700">{g}. sınıf</span>
          ))}
        </div>
      </div>
      <div className="mt-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">YKS</p>
        <div className="mt-1 flex flex-wrap gap-1">
          {["9", "10", "11", "12", "Mezun"].map((g) => (
            <span key={g} className="rounded-md bg-violet-50 px-2 py-0.5 text-[11px] font-medium text-violet-700">{g}</span>
          ))}
        </div>
      </div>
      <div className="mt-2 flex gap-1.5">
        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] text-amber-700">Maarif Modeli</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">Klasik</span>
      </div>
    </Panel>
  );
}

/** Odaklı çalışma / Pomodoro — geri sayım halkası + seri + süre. */
function FocusTimer() {
  return (
    <Panel>
      <div className="mb-3 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
          <Timer className="size-4 text-cyan-700" aria-hidden /> Odak Oturumu
        </span>
        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600">
          <Flame className="size-3" aria-hidden /> 5 gün seri
        </span>
      </div>
      <div className="flex items-center justify-center py-2">
        <div className="relative grid size-24 place-items-center rounded-full"
             style={{ background: "conic-gradient(#0e7490 264deg, #e2e8f0 0)" }}>
          <div className="grid size-[78px] place-items-center rounded-full bg-card">
            <span className="font-display text-xl font-extrabold text-slate-800">18:24</span>
          </div>
        </div>
      </div>
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
        <span>Bugün <b className="text-cyan-800">3 oturum</b></span>
        <span>Toplam <b className="text-cyan-800">95 dk</b></span>
      </div>
    </Panel>
  );
}

/** Hedefler — ana hedef + alt hedef ağacı + ilerleme. */
function Goals() {
  const subs = [
    { label: "TYT Matematik 30 net", pct: 80 },
    { label: "Paragraf hız çalışması", pct: 55 },
    { label: "Haftalık 4 deneme", pct: 100 },
  ];
  return (
    <Panel>
      <div className="flex items-center gap-2 rounded-lg bg-cyan-50 px-2.5 py-2">
        <Target className="size-4 shrink-0 text-cyan-700" aria-hidden />
        <span className="text-[12px] font-bold text-cyan-900">Hedef: Sayısal 350+ sıralama</span>
      </div>
      <div className="mt-2.5 space-y-2">
        {subs.map((s) => (
          <div key={s.label}>
            <div className="mb-0.5 flex items-center justify-between">
              <span className="text-[11px] font-medium text-slate-700">{s.label}</span>
              <span className="text-[10px] font-bold text-muted-foreground">%{s.pct}</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full", s.pct === 100 ? "bg-emerald-500" : "bg-cyan-600")}
                   style={{ width: `${s.pct}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/** Konu performansı — ders/konu bazında doğruluk barları. */
function TopicPerformance() {
  const rows = [
    { topic: "Üslü Sayılar", solved: 48, pct: 92, cls: "bg-emerald-500" },
    { topic: "Çarpanlara Ayırma", solved: 36, pct: 68, cls: "bg-amber-500" },
    { topic: "Olasılık", solved: 22, pct: 41, cls: "bg-rose-500" },
  ];
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-800">
          <BarChart3 className="size-4 text-violet-600" aria-hidden /> Konu Performansı
        </span>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Matematik</span>
      </div>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.topic}>
            <div className="mb-0.5 flex items-center justify-between text-[11px]">
              <span className="font-medium text-slate-700">{r.topic}</span>
              <span className="font-bold text-muted-foreground">%{r.pct} <span className="font-normal">· {r.solved} soru</span></span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted">
              <div className={cn("h-full rounded-full", r.cls)} style={{ width: `${r.pct}%` }} />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

const MAP: Record<string, React.ComponentType> = {
  daily_schedule: DailySchedule,
  focus_timer: FocusTimer,
  goals: Goals,
  topic_performance: TopicPerformance,
  fsrs_rating: FsrsRating,
  burnout_gauge: BurnoutGauge,
  books_progress: BooksProgress,
  whatsapp_chat: WhatsappChat,
  gamification: Gamification,
  ai_assistant: AiAssistant,
  exam_trend: ExamTrend,
  security: Security,
  billing: Billing,
  analytics: Analytics,
  crm: Crm,
  branding: Branding,
  support: Support,
  curriculum: Curriculum,
  generic: GenericShowcase,
};

export function MockupByType({ type }: { type: string | null }) {
  if (!type) return null;
  const Cmp = MAP[type];
  if (!Cmp) return null;
  return <Cmp />;
}

/** mockup_type → kart başlığındaki Lucide ikonu. Tek kaynak (landing + admin
 * önizleme aynı haritayı kullanır). Eşleşmezse Sparkles fallback. */
export const MOCKUP_ICON: Record<string, LucideIcon> = {
  daily_schedule: CalendarDays,
  fsrs_rating: BrainCircuit,
  burnout_gauge: Gauge,
  books_progress: BookOpen,
  whatsapp_chat: MessageSquareText,
  gamification: Award,
  ai_assistant: Bot,
  exam_trend: TrendingUp,
  security: ShieldCheck,
  billing: CreditCard,
  analytics: BarChart3,
  crm: Users,
  branding: Building2,
  support: LifeBuoy,
  curriculum: GraduationCap,
  focus_timer: Timer,
  goals: Target,
  topic_performance: BarChart3,
};
