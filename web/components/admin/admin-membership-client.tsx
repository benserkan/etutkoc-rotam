"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check,
  Copy,
  ExternalLink,
  Loader2,
  MessageCircle,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import { getAdminUsers } from "@/lib/api/admin";
import {
  getMembershipAudience,
  getMembershipOffers,
  membershipKeys,
} from "@/lib/api/membership";
import {
  useCreateMembershipOffer,
  useCreateMembershipOffersBulk,
  useSendMembershipOfferWhatsApp,
} from "@/lib/hooks/use-membership-mutations";
import type { AdminUserListItem } from "@/lib/types/admin";
import type {
  BulkMembershipOfferResult,
  MembershipAudienceMember,
  MembershipOfferCreated,
  MembershipOfferListItem,
  MembershipOfferListResponse,
  MembershipPlanOption,
} from "@/lib/types/membership";
import { buildMembershipWaText } from "@/lib/membership-message";
import { cn } from "@/lib/utils";

const CYCLE_LABEL: Record<string, string> = {
  monthly: "Aylık",
  annual: "Akademik yıl (10 ay peşin)",
};

function fmtTry(n: number): string {
  return new Intl.NumberFormat("tr-TR").format(n);
}

function waUrl(phone: string | null, text: string): string {
  const t = encodeURIComponent(text);
  const p = (phone ?? "").replace(/\D/g, "");
  return p ? `https://wa.me/${p}?text=${t}` : `https://wa.me/?text=${t}`;
}

function CopyButton({ value, label = "Kopyala" }: { value: string; label?: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      onClick={() =>
        navigator.clipboard?.writeText(value).then(
          () => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          },
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

export function AdminMembershipClient({
  initialOffers,
}: {
  initialOffers: MembershipOfferListResponse;
}) {
  const offersQ = useQuery({
    queryKey: membershipKeys.offers(),
    queryFn: getMembershipOffers,
    initialData: initialOffers,
    staleTime: 15_000,
  });

  const planOptions = offersQ.data?.plan_options ?? [];
  const offers = offersQ.data?.items ?? [];
  const [mode, setMode] = React.useState<"single" | "bulk">("single");

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-6">
      <header>
        <h1 className="text-xl font-bold text-foreground">WhatsApp Üyelik Teklifleri</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {"Koça özel üyelik/yenileme teklifi oluştur → linki WhatsApp'tan gönder → kullanıcı markalı sayfada kartla öder (iyzico) → paketi aktive olur."}
        </p>
      </header>

      <div className="inline-flex rounded-lg border border-border bg-card p-1">
        {(["single", "bulk"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={cn(
              "rounded-md px-4 py-1.5 text-sm font-medium transition",
              mode === m
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {m === "single" ? "Tekli teklif" : "Toplu / gruplu teklif"}
          </button>
        ))}
      </div>

      {mode === "single" ? (
        <Composer planOptions={planOptions} />
      ) : (
        <BulkComposer planOptions={planOptions} />
      )}

      <OffersList
        items={offers}
        planOptions={planOptions}
        whatsappEnabled={offersQ.data?.whatsapp_enabled ?? false}
      />
    </div>
  );
}

// ------------------------------------------------------------------- Oluşturucu
function Composer({ planOptions }: { planOptions: MembershipPlanOption[] }) {
  const create = useCreateMembershipOffer();

  const [target, setTarget] = React.useState<AdminUserListItem | null>(null);
  const [offerType, setOfferType] = React.useState("new");
  const [planCode, setPlanCode] = React.useState(planOptions[0]?.code ?? "");
  const [cycle, setCycle] = React.useState("monthly");
  const [amount, setAmount] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [expires, setExpires] = React.useState("30");
  const [created, setCreated] = React.useState<MembershipOfferCreated | null>(null);

  const selectedPlan = planOptions.find((p) => p.code === planCode);
  const defaultPrice = selectedPlan
    ? cycle === "annual"
      ? selectedPlan.annual
      : selectedPlan.monthly
    : 0;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!planCode) {
      toast.error("Plan seç");
      return;
    }
    const amt = amount.trim() ? Number(amount) : null;
    create.mutate(
      {
        body: {
          target_user_id: target?.id ?? null,
          offer_type: offerType,
          plan_code: planCode,
          cycle,
          amount: amt && amt > 0 ? amt : null,
          title: title.trim() || null,
          message: message.trim() || null,
          expires_in_days: expires.trim() ? Number(expires) : null,
        },
      },
      { onSuccess: (res) => setCreated(res) },
    );
  }

  const solo = planOptions.filter((p) => p.audience === "solo");
  const inst = planOptions.filter((p) => p.audience === "institution");

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 text-muted-foreground" aria-hidden />
        <h2 className="text-sm font-semibold text-foreground">Yeni Üyelik Teklifi</h2>
      </div>

      <form onSubmit={onSubmit} className="mt-3 space-y-4">
        <TargetPicker target={target} onSelect={setTarget} />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-muted-foreground">
            Teklif tipi
            <select
              value={offerType}
              onChange={(e) => setOfferType(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="new">Yeni Üyelik</option>
              <option value="renewal">Üyelik Yenileme</option>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Döngü
            <select
              value={cycle}
              onChange={(e) => setCycle(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="monthly">Aylık</option>
              <option value="annual">Akademik yıl (10 ay peşin)</option>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Plan
            <select
              value={planCode}
              onChange={(e) => setPlanCode(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <optgroup label="Bireysel (Koç)">
                {solo.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.label}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Kurum">
                {inst.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.label}
                  </option>
                ))}
              </optgroup>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Özel fiyat (₺) — boş = plan fiyatı
            <input
              type="number"
              min={0}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={defaultPrice > 0 ? `${fmtTry(defaultPrice)} (plan fiyatı)` : "size özel"}
              className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
        </div>

        <label className="block text-xs font-medium text-muted-foreground">
          Başlık (opsiyonel) — sayfada büyük gösterilir
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Örn. Sana özel %20 indirimli yenileme"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="block text-xs font-medium text-muted-foreground">
          Mesaj (opsiyonel)
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={2}
            maxLength={600}
            placeholder="Sayfada başlığın altında görünür."
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>

        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-muted-foreground">
            Süre (gün)
            <input
              type="number"
              min={1}
              value={expires}
              onChange={(e) => setExpires(e.target.value)}
              className="ml-2 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm text-foreground tabular-nums focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </label>
          <button
            type="submit"
            disabled={create.isPending || !planCode}
            className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800 disabled:opacity-50"
          >
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="size-4" aria-hidden />
            )}
            Teklif Oluştur + Link Üret
          </button>
        </div>
      </form>

      {created ? (
        <CreatedCard
          created={created}
          targetName={target?.full_name ?? null}
          planLabel={selectedPlan?.label ?? created.plan_code}
          offerType={offerType}
          amount={created.amount ?? (defaultPrice > 0 ? defaultPrice : null)}
          onClose={() => setCreated(null)}
        />
      ) : null}
    </section>
  );
}

function CreatedCard({
  created,
  targetName,
  planLabel,
  offerType,
  amount,
  onClose,
}: {
  created: MembershipOfferCreated;
  targetName: string | null;
  planLabel: string;
  offerType: string;
  amount: number | null;
  onClose: () => void;
}) {
  const text = buildMembershipWaText({
    offerType,
    targetName,
    planLabel,
    amount,
    cycle: created.cycle,
    url: created.public_url,
  });
  return (
    <div className="mt-4 rounded-lg border border-cyan-300 bg-cyan-50 p-4 dark:border-cyan-900 dark:bg-cyan-950/30">
      <div className="flex items-center gap-2">
        <Check className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
        <span className="text-sm font-semibold text-cyan-900 dark:text-cyan-100">
          Teklif oluşturuldu
        </span>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto text-cyan-700/70 hover:text-cyan-900 dark:text-cyan-300/70"
          aria-label="Kapat"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <div className="mt-2 flex items-center gap-2 rounded-md bg-white px-2.5 py-1.5 dark:bg-slate-900">
        <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-700 dark:text-slate-300">
          {created.public_url}
        </span>
        <CopyButton value={created.public_url} label="Linki Kopyala" />
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <a
          href={waUrl(null, text)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
        >
          <MessageCircle className="size-4" aria-hidden /> {"WhatsApp'ta Aç"}
        </a>
        <a
          href={created.public_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted/60"
        >
          <ExternalLink className="size-4" aria-hidden /> Sayfayı Önizle
        </a>
      </div>
      <p className="mt-2 text-[11px] text-cyan-800/80 dark:text-cyan-200/70">
        {"WhatsApp'ta Aç → mesaj + link hazır gelir; alıcıyı seçip gönder."}
      </p>
    </div>
  );
}

// --------------------------------------------------------------- Hedef seçici
function TargetPicker({
  target,
  onSelect,
}: {
  target: AdminUserListItem | null;
  onSelect: (u: AdminUserListItem | null) => void;
}) {
  const [q, setQ] = React.useState("");
  const usersQ = useQuery({
    queryKey: ["admin", "me", "membership-usersearch", q],
    queryFn: () => getAdminUsers("teacher", null, q),
    enabled: q.trim().length >= 2 && !target,
    staleTime: 10_000,
  });

  if (target) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2">
        <span className="text-sm text-foreground">
          Hedef: <b>{target.full_name}</b>{" "}
          <span className="text-muted-foreground">({target.email})</span>
        </span>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <X className="size-3" aria-hidden /> Değiştir
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5">
        <Search className="size-4 text-muted-foreground" aria-hidden />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Hedef koç ara (ad/e-posta) — boş bırakılırsa genel link"
          className="w-full bg-transparent text-sm text-foreground focus:outline-none"
        />
      </div>
      {q.trim().length >= 2 ? (
        <div className="mt-1 max-h-44 overflow-y-auto rounded-md border border-border">
          {usersQ.isLoading ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Aranıyor…</p>
          ) : (usersQ.data?.items?.length ?? 0) === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground">Sonuç yok.</p>
          ) : (
            usersQ.data!.items.map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={() => {
                  onSelect(u);
                  setQ("");
                }}
                className="flex w-full items-center justify-between gap-2 border-b border-border/60 px-3 py-2 text-left text-sm last:border-0 hover:bg-muted/50"
              >
                <span className="text-foreground">{u.full_name}</span>
                <span className="text-xs text-muted-foreground">{u.email}</span>
              </button>
            ))
          )}
        </div>
      ) : (
        <p className="mt-1 px-1 text-[11px] text-muted-foreground">
          {"Hedef seçmezsen \"genel link\" üretilir (herkese aynı, kişiselleştirme yok)."}
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Toplu mod
function BulkComposer({ planOptions }: { planOptions: MembershipPlanOption[] }) {
  const audienceQ = useQuery({
    queryKey: membershipKeys.audience(),
    queryFn: getMembershipAudience,
    staleTime: 30_000,
  });
  const bulk = useCreateMembershipOffersBulk();

  const [groupKey, setGroupKey] = React.useState<string>("");
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const [offerType, setOfferType] = React.useState("new");
  const [planCode, setPlanCode] = React.useState(planOptions[0]?.code ?? "");
  const [cycle, setCycle] = React.useState("monthly");
  const [amount, setAmount] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [expires, setExpires] = React.useState("30");
  const [results, setResults] = React.useState<BulkMembershipOfferResult | null>(null);

  const groups = audienceQ.data?.groups ?? [];
  const activeGroup = groups.find((g) => g.key === groupKey);
  const members: MembershipAudienceMember[] = activeGroup?.members ?? [];

  function pickGroup(key: string) {
    setGroupKey(key);
    const g = groups.find((x) => x.key === key);
    setSelected(new Set((g?.members ?? []).map((m) => m.id)));
    setResults(null);
  }

  function toggle(id: number) {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size === 0) {
      toast.error("Hedef koç seç");
      return;
    }
    const amt = amount.trim() ? Number(amount) : null;
    bulk.mutate(
      {
        body: {
          target_user_ids: Array.from(selected),
          offer_type: offerType,
          plan_code: planCode,
          cycle,
          amount: amt && amt > 0 ? amt : null,
          title: title.trim() || null,
          message: message.trim() || null,
          expires_in_days: expires.trim() ? Number(expires) : null,
        },
      },
      { onSuccess: (res) => setResults(res) },
    );
  }

  const solo = planOptions.filter((p) => p.audience === "solo");
  const inst = planOptions.filter((p) => p.audience === "institution");
  const selectedPlan = planOptions.find((p) => p.code === planCode);
  const bulkEffAmount =
    amount.trim() && Number(amount) > 0
      ? Number(amount)
      : selectedPlan
        ? cycle === "annual"
          ? selectedPlan.annual
          : selectedPlan.monthly
        : 0;

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-foreground">Toplu / Gruplu Üyelik Teklifi</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        Bir koç grubu seç → her birine kişisel link üretilir → WhatsApp&apos;tan tek
        tek gönder (toplu broadcast için linkleri kopyala).
      </p>

      {/* Grup seçimi */}
      <div className="mt-3 flex flex-wrap gap-2">
        {audienceQ.isLoading ? (
          <span className="text-xs text-muted-foreground">Gruplar yükleniyor…</span>
        ) : (
          groups.map((g) => (
            <button
              key={g.key}
              type="button"
              onClick={() => pickGroup(g.key)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-xs font-medium transition",
                groupKey === g.key
                  ? "border-cyan-600 bg-cyan-50 text-cyan-800 dark:bg-cyan-950/40 dark:text-cyan-200"
                  : "border-border text-foreground hover:bg-muted/50",
              )}
            >
              {g.label} ({g.count})
            </button>
          ))
        )}
      </div>

      {/* Üye listesi */}
      {groupKey ? (
        members.length === 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">Bu grupta koç yok.</p>
        ) : (
          <div className="mt-3 rounded-md border border-border">
            <div className="flex items-center justify-between border-b border-border/60 bg-muted/30 px-3 py-1.5 text-xs">
              <span className="text-muted-foreground">
                {selected.size}/{members.length} seçili
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setSelected(new Set(members.map((m) => m.id)))}
                  className="text-cyan-700 hover:underline dark:text-cyan-300"
                >
                  Tümünü seç
                </button>
                <button
                  type="button"
                  onClick={() => setSelected(new Set())}
                  className="text-muted-foreground hover:underline"
                >
                  Temizle
                </button>
              </div>
            </div>
            <div className="max-h-44 overflow-y-auto">
              {members.map((m) => (
                <label
                  key={m.id}
                  className="flex cursor-pointer items-center gap-2 border-b border-border/40 px-3 py-1.5 text-sm last:border-0 hover:bg-muted/40"
                >
                  <input
                    type="checkbox"
                    checked={selected.has(m.id)}
                    onChange={() => toggle(m.id)}
                    className="size-4"
                  />
                  <span className="text-foreground">{m.full_name}</span>
                  <span className="text-xs text-muted-foreground">{m.email}</span>
                  {!m.phone ? (
                    <span className="ml-auto text-[10px] text-amber-600">telefon yok</span>
                  ) : null}
                </label>
              ))}
            </div>
          </div>
        )
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">Önce bir grup seç.</p>
      )}

      {/* Teklif parametreleri */}
      <form onSubmit={onSubmit} className="mt-4 space-y-3">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <label className="text-xs font-medium text-muted-foreground">
            Tip
            <select value={offerType} onChange={(e) => setOfferType(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground">
              <option value="new">Yeni</option>
              <option value="renewal">Yenileme</option>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Plan
            <select value={planCode} onChange={(e) => setPlanCode(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground">
              <optgroup label="Bireysel">
                {solo.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
              </optgroup>
              <optgroup label="Kurum">
                {inst.map((p) => <option key={p.code} value={p.code}>{p.label}</option>)}
              </optgroup>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Döngü
            <select value={cycle} onChange={(e) => setCycle(e.target.value)}
              className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm text-foreground">
              <option value="monthly">Aylık</option>
              <option value="annual">Akademik yıl</option>
            </select>
          </label>
          <label className="text-xs font-medium text-muted-foreground">
            Özel fiyat (₺)
            <input type="number" min={0} value={amount} onChange={(e) => setAmount(e.target.value)}
              placeholder={selectedPlan && selectedPlan.monthly > 0 ? "plan fiyatı" : "—"}
              className="mt-1 w-full rounded-md border border-input bg-background px-2 py-1.5 text-sm tabular-nums text-foreground" />
          </label>
        </div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200}
          placeholder="Başlık (opsiyonel)"
          className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
        <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={2} maxLength={600}
          placeholder="Mesaj (opsiyonel)"
          className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground" />
        <div className="flex items-center gap-3">
          <label className="text-xs font-medium text-muted-foreground">
            Süre (gün)
            <input type="number" min={1} value={expires} onChange={(e) => setExpires(e.target.value)}
              className="ml-2 w-20 rounded-md border border-input bg-background px-2 py-1 text-sm tabular-nums text-foreground" />
          </label>
          <button type="submit" disabled={bulk.isPending || selected.size === 0}
            className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-cyan-700 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-800 disabled:opacity-50">
            {bulk.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            {selected.size} koça teklif üret
          </button>
        </div>
      </form>

      {results ? <BulkResults results={results} offerType={offerType}
        planLabel={selectedPlan?.label ?? planCode}
        amount={bulkEffAmount > 0 ? bulkEffAmount : null} cycle={cycle} /> : null}
    </section>
  );
}

function BulkResults({
  results,
  offerType,
  planLabel,
  amount,
  cycle,
}: {
  results: BulkMembershipOfferResult;
  offerType: string;
  planLabel: string;
  amount: number | null;
  cycle: string;
}) {
  function textFor(name: string | null, url: string): string {
    return buildMembershipWaText({ offerType, targetName: name, planLabel, amount, cycle, url });
  }
  const broadcast = results.items
    .map((it) => `${it.full_name ?? "Koç"}: ${it.public_url}`)
    .join("\n");
  return (
    <div className="mt-4 rounded-lg border border-cyan-300 bg-cyan-50 p-4 dark:border-cyan-900 dark:bg-cyan-950/30">
      <div className="flex items-center gap-2">
        <Check className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
        <span className="text-sm font-semibold text-cyan-900 dark:text-cyan-100">
          {results.created} teklif oluşturuldu
          {results.skipped > 0 ? ` · ${results.skipped} atlandı` : ""}
        </span>
        <span className="ml-auto">
          <CopyButton value={broadcast} label="Tüm linkleri kopyala" />
        </span>
      </div>
      <div className="mt-2 max-h-60 space-y-1.5 overflow-y-auto">
        {results.items.map((it) => (
          <div key={it.token} className="flex items-center gap-2 rounded-md bg-white px-2.5 py-1.5 text-sm dark:bg-slate-900">
            <span className="min-w-0 flex-1 truncate text-slate-800 dark:text-slate-200">
              {it.full_name ?? "Koç"}
              {!it.phone ? <span className="ml-1 text-[10px] text-amber-600">telefon yok</span> : null}
            </span>
            <CopyButton value={it.public_url} label="Link" />
            <a
              href={waUrl(it.phone, textFor(it.full_name, it.public_url))}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
            >
              <MessageCircle className="size-3" aria-hidden /> WhatsApp
            </a>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-cyan-800/80 dark:text-cyan-200/70">
        {"Sıralı gönderim: her satırdaki WhatsApp ile koça aç → gönder. Broadcast için \"Tüm linkleri kopyala\"."}
      </p>
    </div>
  );
}

// ------------------------------------------------------------------- Liste
function OffersList({
  items,
  planOptions,
  whatsappEnabled,
}: {
  items: MembershipOfferListItem[];
  planOptions: MembershipPlanOption[];
  whatsappEnabled: boolean;
}) {
  void planOptions;
  if (items.length === 0) {
    return (
      <section className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
        Henüz teklif oluşturulmadı.
      </section>
    );
  }
  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-foreground">Son Teklifler</h2>
      <div className="mt-3 space-y-2">
        {items.map((o) => (
          <OfferRow key={o.id} o={o} whatsappEnabled={whatsappEnabled} />
        ))}
      </div>
    </section>
  );
}

function OfferRow({
  o,
  whatsappEnabled,
}: {
  o: MembershipOfferListItem;
  whatsappEnabled: boolean;
}) {
  const sendWa = useSendMembershipOfferWhatsApp();
  const typeLabel = o.offer_type === "renewal" ? "Yenileme" : "Yeni";
  const text = buildMembershipWaText({
    offerType: o.offer_type,
    targetName: o.target_name,
    planLabel: o.plan_label,
    amount: o.amount,
    cycle: o.cycle,
    url: o.public_url,
  });
  // Cloud API doğrudan gönderim: anahtarlar dolu + hedefin telefonu var
  const canCloudSend = whatsappEnabled && !!o.target_phone;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-border/70 px-3 py-2 text-sm">
      <span className="font-medium text-foreground">
        {o.target_name ?? "Genel link"}
      </span>
      <span className="text-xs text-muted-foreground">
        {typeLabel} · {o.plan_label} · {CYCLE_LABEL[o.cycle] ?? o.cycle}
        {o.amount ? ` · ${fmtTry(o.amount)} ₺` : ""}
      </span>
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-[11px] font-medium",
          o.completion
            ? "bg-amber-100 text-amber-800 dark:bg-amber-950/50 dark:text-amber-200"
            : o.viewed
              ? "bg-sky-100 text-sky-800 dark:bg-sky-950/50 dark:text-sky-200"
              : "bg-muted text-muted-foreground",
        )}
      >
        {o.completion ? o.completion_label : o.viewed ? "Görüntülendi" : "Bekliyor"}
      </span>
      {o.wa_sent ? (
        <span className="inline-flex items-center gap-1 rounded-full bg-cyan-100 px-2 py-0.5 text-[11px] font-medium text-cyan-800 dark:bg-cyan-950/50 dark:text-cyan-200">
          <Check className="size-3" aria-hidden /> WhatsApp gönderildi
        </span>
      ) : null}
      <div className="ml-auto flex items-center gap-2">
        <CopyButton value={o.public_url} label="Link" />
        {/* Cloud API: doğrudan branded şablon (mavi tik) */}
        {canCloudSend ? (
          <button
            type="button"
            disabled={sendWa.isPending}
            onClick={() => sendWa.mutate({ id: o.id })}
            className="inline-flex items-center gap-1 rounded-md bg-cyan-600 px-2 py-1 text-xs font-medium text-white hover:bg-cyan-700 disabled:opacity-50"
            title="Cloud API ile markalı şablon gönder (mavi tik)"
          >
            {sendWa.isPending ? (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="size-3" aria-hidden />
            )}
            {o.wa_sent ? "Tekrar gönder" : "Cloud API gönder"}
          </button>
        ) : null}
        {/* Manuel wa.me (Faz 1) — her zaman var */}
        <a
          href={waUrl(o.target_phone, text)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
          title={o.target_phone ? "Doğrudan koça WhatsApp (manuel)" : "WhatsApp aç (alıcı seç)"}
        >
          <MessageCircle className="size-3" aria-hidden /> Manuel
        </a>
      </div>
    </div>
  );
}
