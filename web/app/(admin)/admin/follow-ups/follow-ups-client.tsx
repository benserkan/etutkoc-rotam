"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BarChart3, ClipboardCheck, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FollowUpCard } from "@/components/admin/follow-ups/follow-up-card";
import { FollowUpFormDialog } from "@/components/admin/follow-ups/follow-up-form-dialog";
import { cn } from "@/lib/utils";
import { followUpKeys, getFollowUps } from "@/lib/api/follow-ups";
import type { FollowUpBucket, FollowUpItem, FollowUpListResponse } from "@/lib/types/follow-ups";

type Tab = "open" | "closed";

const GROUPS: { bucket: FollowUpBucket; title: string; hint: string; tone: string }[] = [
  { bucket: "overdue", title: "Gecikmiş", hint: "Vadesi geçti — 3 günde bir yeniden hatırlatılır", tone: "text-rose-700" },
  { bucket: "today", title: "Bugün", hint: "Bugün bakılacaklar", tone: "text-amber-700" },
  { bucket: "upcoming", title: "Bu hafta", hint: "Önümüzdeki 7 gün", tone: "text-cyan-800" },
  { bucket: "later", title: "Daha sonra", hint: "Takvimde bekleyenler", tone: "text-slate-700" },
];

export function FollowUpsClient({ initial }: { initial: FollowUpListResponse }) {
  const [tab, setTab] = React.useState<Tab>("open");
  const [only, setOnly] = React.useState<FollowUpBucket | "all">("all");
  const [formOpen, setFormOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<FollowUpItem | null>(null);

  const q = useQuery({
    queryKey: followUpKeys.list(tab),
    queryFn: () => getFollowUps(tab),
    initialData: tab === "open" ? initial : undefined,
  });
  const data = q.data;
  const meta = (data ?? initial).meta;
  const counts = (data ?? initial).counts;

  function openNew() {
    setEditing(null);
    setFormOpen(true);
  }
  function openEdit(it: FollowUpItem) {
    setEditing(it);
    setFormOpen(true);
  }

  const chips: { key: FollowUpBucket | "all"; label: string; n: number; cls: string }[] = [
    { key: "all", label: "Tümü", n: counts.overdue + counts.today + counts.upcoming + counts.later, cls: "bg-slate-800" },
    { key: "overdue", label: "Gecikmiş", n: counts.overdue, cls: "bg-rose-600" },
    { key: "today", label: "Bugün", n: counts.today, cls: "bg-amber-600" },
    { key: "upcoming", label: "Bu hafta", n: counts.upcoming, cls: "bg-cyan-700" },
    { key: "later", label: "Daha sonra", n: counts.later, cls: "bg-slate-600" },
  ];

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-800">
              <ClipboardCheck className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Takip listesi</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                &quot;2-3 hafta sonra bakılacak&quot; işler burada. Vadesi gelince sol menüde rozet çıkar,
                sabah 09:00&apos;da e-posta + bildirim gelir. Bir ölçüye bağlı işlerde sonucu sistem
                kendisi hesaplar — sana yalnız karar kalır.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/admin/metrics">
                <BarChart3 className="size-4" aria-hidden />
                Ölçümler
              </Link>
            </Button>
            <Button size="sm" onClick={openNew} className="bg-cyan-700 text-white hover:bg-cyan-800">
              <Plus className="size-4" aria-hidden />
              Yeni iş
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-border p-0.5">
            {(["open", "closed"] as Tab[]).map((t) => (
              <button key={t} type="button" onClick={() => setTab(t)}
                className={cn("rounded-md px-3 py-1 text-sm",
                  tab === t ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-muted")}>
                {t === "open" ? "Açık" : `Kapalı (${counts.closed})`}
              </button>
            ))}
          </div>
          {tab === "open"
            ? chips.map((c) => (
                <button key={c.key} type="button" onClick={() => setOnly(c.key)}
                  className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm",
                    only === c.key ? "border-slate-900 bg-slate-900 text-white" : "border-border text-slate-700 hover:bg-muted")}>
                  {c.label}
                  <span className={cn("rounded-full px-1.5 text-xs font-semibold text-white", c.cls)}>{c.n}</span>
                </button>
              ))
            : null}
        </div>
      </div>

      <div className="mt-5 space-y-6">
        {!data ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : tab === "closed" ? (
          data.items.length === 0 ? (
            <Empty text="Kapatılmış iş yok." />
          ) : (
            <div className="space-y-3">
              {data.items.map((it) => <FollowUpCard key={it.id} item={it} onEdit={openEdit} />)}
            </div>
          )
        ) : data.items.length === 0 ? (
          <Empty text="Açık iş yok. 'Yeni iş' ile tarihli bir hatırlatma ekle." />
        ) : (
          GROUPS.filter((g) => only === "all" || only === g.bucket).map((g) => {
            const items = data.items.filter((i) => i.bucket === g.bucket);
            if (!items.length) return null;
            return (
              <section key={g.bucket} data-section={`follow-ups:${g.bucket}`}>
                <div className="mb-2 flex items-baseline gap-2">
                  <h2 className={cn("text-sm font-semibold uppercase tracking-wide", g.tone)}>
                    {g.title} · {items.length}
                  </h2>
                  <span className="text-xs text-muted-foreground">{g.hint}</span>
                </div>
                <div className="space-y-3">
                  {items.map((it) => <FollowUpCard key={it.id} item={it} onEdit={openEdit} />)}
                </div>
              </section>
            );
          })
        )}
      </div>

      <FollowUpFormDialog
        key={editing ? `e${editing.id}` : "new"}
        open={formOpen}
        onOpenChange={setFormOpen}
        meta={meta}
        item={editing}
      />
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
      {text}
    </div>
  );
}
