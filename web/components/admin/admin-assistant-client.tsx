"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Bot, Loader2 } from "lucide-react";

import { assistantKeys, getAdminAssistant } from "@/lib/api/site-assistant";
import { cn } from "@/lib/utils";

const AUDIENCES: { v: string; label: string }[] = [
  { v: "", label: "Hepsi" },
  { v: "public", label: "Ziyaretçi" },
  { v: "teacher", label: "Koç" },
  { v: "student", label: "Öğrenci" },
  { v: "parent", label: "Veli" },
  { v: "institution_admin", label: "Kurum yöneticisi" },
];

const SOURCE_LABEL: Record<string, string> = {
  ai: "Yapay zekâ",
  rule: "Hazır cevap",
  fallback: "Yedek cevap",
  limit: "Hak doldu",
  handoff: "Ekibe yazdı",
};

function fmt(d: string) {
  return new Date(d).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/**
 * Rota asistanına kim ne sordu? — en çok sorulanlar (hangi ekran anlaşılmıyor)
 * + ziyaretçi konuşmaları + ekibe aktarılan talepler.
 */
export function AdminAssistantClient() {
  const [days, setDays] = React.useState(7);
  const [audience, setAudience] = React.useState("");
  const [onlyHandoff, setOnlyHandoff] = React.useState(false);
  const q = useQuery({
    queryKey: assistantKeys.admin(days, audience, onlyHandoff),
    queryFn: () => getAdminAssistant(days, audience, onlyHandoff),
  });
  const d = q.data;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6">
      <header>
        <h1 className="flex items-center gap-2 font-display text-2xl font-bold text-foreground">
          <Bot className="size-6 text-cyan-700 dark:text-cyan-400" aria-hidden /> Asistan soruları
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Sitenin her yerindeki Rota asistanına sorulanlar. Sık sorulan soru, o ekranın yeterince anlaşılmadığını
          gösterir. Ekibe yazanların talepleri İletişim Talepleri ve Talepler sayfalarına düşer.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm text-foreground"
          aria-label="Dönem"
        >
          <option value={1}>Son 24 saat</option>
          <option value={7}>Son 7 gün</option>
          <option value={30}>Son 30 gün</option>
          <option value={90}>Son 90 gün</option>
        </select>
        <select
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm text-foreground"
          aria-label="Kim sordu"
        >
          {AUDIENCES.map((a) => (
            <option key={a.v} value={a.v}>
              {a.label}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-foreground">
          <input type="checkbox" checked={onlyHandoff} onChange={(e) => setOnlyHandoff(e.target.checked)} />
          Yalnız ekibe yazanlar
        </label>
      </div>

      {q.isLoading || !d ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor
        </p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Kpi label="Toplam soru" hint={`son ${d.days} gün, hazır cevaplar dahil`} value={d.total} />
            <Kpi label="Yapay zekâ cevabı" hint="serbest sorulara verilen" value={d.ai_count} />
            <Kpi label="Ekibe yazan" hint="destek ya da iletişim talebi açtı" value={d.handoff_count} />
          </div>

          <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground">Kim soruyor?</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(d.by_audience).map(([k, v]) => (
                <span key={k} className="rounded-full bg-muted px-3 py-1 text-sm text-foreground">
                  {AUDIENCES.find((a) => a.v === k)?.label ?? k}: <b>{v}</b>
                </span>
              ))}
            </div>
          </section>

          <section className="rounded-2xl border border-border bg-card p-5">
            <h2 className="text-sm font-semibold text-foreground">En çok sorulanlar</h2>
            {d.top_questions.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">Bu dönemde soru yok.</p>
            ) : (
              <ol className="mt-3 space-y-1.5">
                {d.top_questions.map((t, i) => (
                  <li key={i} className="flex items-start justify-between gap-4 text-sm text-foreground">
                    <span className="break-words">{t.question}</span>
                    <span className="shrink-0 tabular-nums text-muted-foreground">{t.count} kez</span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">Son sorular</h2>
            {d.items.length === 0 ? <p className="text-sm text-muted-foreground">Kayıt yok.</p> : null}
            {d.items.map((r) => (
              <article key={r.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>{fmt(r.created_at)}</span>
                  <span className="rounded-full bg-slate-700 px-2 py-0.5 font-semibold text-white">{r.audience_label}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 font-semibold text-white",
                      r.handoff ? "bg-emerald-700" : r.source === "ai" ? "bg-cyan-700" : "bg-slate-500",
                    )}
                  >
                    {SOURCE_LABEL[r.source] ?? r.source}
                  </span>
                  {r.user_id ? (
                    <Link href={`/admin/users/${r.user_id}`} className="font-medium text-cyan-800 hover:underline dark:text-cyan-300">
                      {r.user_name ?? `#${r.user_id}`}
                    </Link>
                  ) : null}
                  {r.page ? <span>sayfa: {r.page}</span> : null}
                </div>
                <p className="mt-2 break-words text-sm font-medium text-foreground">{r.question}</p>
                {r.answer ? (
                  <p className="mt-1.5 whitespace-pre-line break-words text-sm text-muted-foreground">{r.answer}</p>
                ) : null}
              </article>
            ))}
          </section>
        </>
      )}
    </div>
  );
}

function Kpi({ label, hint, value }: { label: string; hint: string; value: number }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-4">
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <p className="mt-1 font-display text-3xl font-bold tabular-nums text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
    </div>
  );
}
