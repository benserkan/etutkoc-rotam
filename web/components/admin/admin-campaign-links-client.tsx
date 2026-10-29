"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check, Copy, ExternalLink, Eye, Loader2, MessageCircle, Pause, Play,
  Sparkles, Users,
} from "lucide-react";

import { campaignLinkKeys, getCampaignLinks } from "@/lib/api/campaign-links";
import {
  useCreateCampaignLink, useSetCampaignLinkStatus,
} from "@/lib/hooks/use-campaign-link-mutations";
import type {
  CampaignLinkItem, CampaignLinkListResponse, CampaignPlanOption,
} from "@/lib/types/campaign-link";
import { cn } from "@/lib/utils";

const CYCLE_LABEL: Record<string, string> = {
  monthly: "Aylık",
  annual: "Akademik yıl (10 ay peşin)",
};
const STATUS_TONE: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-800",
  paused: "bg-amber-100 text-amber-800",
  archived: "bg-slate-200 text-slate-700",
};

function fmtTry(n: number): string {
  return new Intl.NumberFormat("tr-TR").format(n);
}

function CopyBtn({ value, label = "Kopyala" }: { value: string; label?: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      onClick={() =>
        navigator.clipboard?.writeText(value).then(
          () => { setCopied(true); setTimeout(() => setCopied(false), 1600); },
          () => toast.error("Kopyalanamadı"),
        )
      }
      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs text-foreground hover:bg-muted/60"
    >
      {copied ? <Check className="size-3" aria-hidden /> : <Copy className="size-3" aria-hidden />}
      {copied ? "Kopyalandı" : label}
    </button>
  );
}

export function AdminCampaignLinksClient({ initial }: { initial: CampaignLinkListResponse }) {
  const q = useQuery({
    queryKey: campaignLinkKeys.list(),
    queryFn: getCampaignLinks,
    initialData: initial,
    staleTime: 15_000,
  });
  const planOptions = q.data?.plan_options ?? [];
  const items = q.data?.items ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-6">
      <header>
        <h1 className="text-xl font-bold text-foreground">Kampanya Linkleri</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {"Kişiye özel olmayan, tekrar kullanılabilir markalı tanıtım linki oluştur → WhatsApp grubuna / kanalına paylaş. Tıklayan herkes markalı sayfayı görüp ad+telefon bırakır → İletişim Talepleri'nde \"Koç/Kurum Aç + Aktive Et\" ile devam edersin."}
        </p>
      </header>

      <Composer planOptions={planOptions} />
      <LinksList items={items} />
    </div>
  );
}

// ---------------------------------------------------------------- Oluşturucu
function Composer({ planOptions }: { planOptions: CampaignPlanOption[] }) {
  const create = useCreateCampaignLink();
  const [name, setName] = React.useState("");
  const [planCode, setPlanCode] = React.useState(planOptions[0]?.code ?? "");
  const [cycle, setCycle] = React.useState("monthly");
  const [amount, setAmount] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [expires, setExpires] = React.useState("");

  const plan = planOptions.find((p) => p.code === planCode);
  const listPrice = plan ? (cycle === "annual" ? plan.annual : plan.monthly) : null;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (name.trim().length < 2 || !planCode) {
      toast.error("Kampanya adı ve plan zorunlu.");
      return;
    }
    create.mutate({
      body: {
        name: name.trim(),
        plan_code: planCode,
        cycle,
        amount: amount.trim() ? Number(amount) : null,
        title: title.trim() || null,
        message: message.trim() || null,
        expires_in_days: expires.trim() ? Number(expires) : null,
      },
    }, {
      onSuccess: () => {
        setName(""); setAmount(""); setTitle(""); setMessage(""); setExpires("");
      },
    });
  }

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-xl border border-border bg-card p-5"
    >
      <h2 className="text-sm font-semibold text-foreground">Yeni Kampanya Linki</h2>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground">Kampanya adı (iç etiket)</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Örn. Koçluk Grubu Ekim Kampanyası"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground">Plan</label>
          <select
            value={planCode}
            onChange={(e) => setPlanCode(e.target.value)}
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {planOptions.map((p) => (
              <option key={p.code} value={p.code}>
                {p.label} ({p.audience === "institution" ? "Kurum" : "Koç"})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="text-xs text-muted-foreground">Dönem</label>
          <select
            value={cycle}
            onChange={(e) => setCycle(e.target.value)}
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            <option value="monthly">Aylık</option>
            <option value="annual">Akademik yıl (10 ay peşin)</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-muted-foreground">
            Tutar (₺) — boş = liste fiyatı{listPrice ? ` (${fmtTry(listPrice)} ₺)` : ""}
          </label>
          <input
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            inputMode="numeric"
            placeholder={listPrice ? String(listPrice) : "Liste fiyatı"}
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div>
          <label className="text-xs text-muted-foreground">Geçerlilik (gün, boş = süresiz)</label>
          <input
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
            inputMode="numeric"
            placeholder="Süresiz"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground">Başlık (opsiyonel — hero üst yazısı)</label>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Örn. Koçluğunu büyütmeye hazır mısın?"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>

        <div className="sm:col-span-2">
          <label className="text-xs text-muted-foreground">Mesaj (opsiyonel — açıklama)</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={2}
            placeholder="Kısa tanıtım metni..."
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
      </div>

      <button
        type="submit"
        disabled={create.isPending}
        className="inline-flex items-center gap-2 rounded-md bg-foreground px-4 py-2 text-sm font-semibold text-background hover:opacity-90 disabled:opacity-50"
      >
        {create.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Sparkles className="size-4" aria-hidden />
        )}
        Kampanya Linki Oluştur
      </button>
    </form>
  );
}

// ---------------------------------------------------------------- Liste
function LinksList({ items }: { items: CampaignLinkItem[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        Henüz kampanya linki yok. Yukarıdan oluştur.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-foreground">Kampanyalar</h2>
      {items.map((it) => <LinkRow key={it.id} item={it} />)}
    </div>
  );
}

function LinkRow({ item }: { item: CampaignLinkItem }) {
  const setStatus = useSetCampaignLinkStatus();
  const waText = `${item.title || "ETÜTKOÇ Rotam üyelik"}\n${item.public_url}`;
  const waHref = `https://wa.me/?text=${encodeURIComponent(waText)}`;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-foreground">{item.name}</span>
            <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", STATUS_TONE[item.status] ?? "bg-slate-100 text-slate-700")}>
              {item.status_label}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {item.plan_label} · {CYCLE_LABEL[item.cycle] ?? item.cycle}
            {item.amount ? ` · ${fmtTry(item.amount)} ₺` : " · liste fiyatı"}
            {" · "}{item.audience === "institution" ? "Kurum" : "Koç"}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1" title="Görüntülenme">
            <Eye className="size-3.5" aria-hidden /> {item.view_count}
          </span>
          <span className="inline-flex items-center gap-1 font-semibold text-foreground" title="Lead (talep bırakan)">
            <Users className="size-3.5" aria-hidden /> {item.lead_count}
          </span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <code className="max-w-full truncate rounded bg-muted px-2 py-1 text-xs text-foreground">
          {item.public_url}
        </code>
        <CopyBtn value={item.public_url} label="Linki kopyala" />
        <a
          href={waHref}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-emerald-700"
        >
          <MessageCircle className="size-3.5" aria-hidden /> WhatsApp&apos;tan paylaş
        </a>
        <a
          href={item.public_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs text-foreground hover:bg-muted/60"
        >
          <ExternalLink className="size-3.5" aria-hidden /> Önizle
        </a>

        <div className="ml-auto flex items-center gap-2">
          {item.status === "active" ? (
            <button
              type="button"
              onClick={() => setStatus.mutate({ id: item.id, status: "paused" })}
              disabled={setStatus.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
            >
              <Pause className="size-3.5" aria-hidden /> Duraklat
            </button>
          ) : item.status === "paused" ? (
            <button
              type="button"
              onClick={() => setStatus.mutate({ id: item.id, status: "active" })}
              disabled={setStatus.isPending}
              className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
            >
              <Play className="size-3.5" aria-hidden /> Yayına al
            </button>
          ) : null}
          {item.status !== "archived" ? (
            <button
              type="button"
              onClick={() => {
                if (confirm("Bu kampanyayı arşivle? Link artık çalışmaz.")) {
                  setStatus.mutate({ id: item.id, status: "archived" });
                }
              }}
              disabled={setStatus.isPending}
              className="inline-flex items-center rounded-md border border-border px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted/60 disabled:opacity-50"
            >
              Arşivle
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
