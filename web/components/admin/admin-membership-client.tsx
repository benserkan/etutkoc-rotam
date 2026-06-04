"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check,
  Copy,
  ExternalLink,
  Landmark,
  Loader2,
  MessageCircle,
  Search,
  Sparkles,
  X,
} from "lucide-react";

import { getAdminUsers } from "@/lib/api/admin";
import {
  getMembershipHavale,
  getMembershipOffers,
  membershipKeys,
} from "@/lib/api/membership";
import {
  useCreateMembershipOffer,
  useSetMembershipHavale,
} from "@/lib/hooks/use-membership-mutations";
import type { AdminUserListItem } from "@/lib/types/admin";
import type {
  MembershipHavaleInfo,
  MembershipOfferCreated,
  MembershipOfferListItem,
  MembershipOfferListResponse,
  MembershipPlanOption,
} from "@/lib/types/membership";
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
  initialHavale,
}: {
  initialOffers: MembershipOfferListResponse;
  initialHavale: MembershipHavaleInfo;
}) {
  const offersQ = useQuery({
    queryKey: membershipKeys.offers(),
    queryFn: getMembershipOffers,
    initialData: initialOffers,
    staleTime: 15_000,
  });
  const havaleQ = useQuery({
    queryKey: membershipKeys.havale(),
    queryFn: getMembershipHavale,
    initialData: initialHavale,
    staleTime: 60_000,
  });

  const planOptions = offersQ.data?.plan_options ?? [];
  const offers = offersQ.data?.items ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-6">
      <header>
        <h1 className="text-xl font-bold text-foreground">WhatsApp Üyelik Teklifleri</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {"Koça özel üyelik/yenileme teklifi oluştur → linki WhatsApp'tan gönder → kullanıcı markalı sayfada talep bırakır veya havale ile öder → İletişim Talepleri'nden aktive et."}
        </p>
      </header>

      <HavaleCard havale={havaleQ.data ?? initialHavale} />
      <Composer planOptions={planOptions} />
      <OffersList items={offers} planOptions={planOptions} />
    </div>
  );
}

// ---------------------------------------------------------------- Havale ayarı
function HavaleCard({ havale }: { havale: MembershipHavaleInfo }) {
  const setHavale = useSetMembershipHavale();
  const [iban, setIban] = React.useState(havale.iban);
  const [name, setName] = React.useState(havale.name);
  const [note, setNote] = React.useState(havale.note);

  // prop değişince (refetch) senkronla
  const sig = `${havale.iban}|${havale.name}|${havale.note}`;
  const [lastSig, setLastSig] = React.useState(sig);
  if (sig !== lastSig) {
    setLastSig(sig);
    setIban(havale.iban);
    setName(havale.name);
    setNote(havale.note);
  }

  return (
    <section className="rounded-lg border border-border bg-card p-5">
      <div className="flex items-center gap-2">
        <Landmark className="size-4 text-muted-foreground" aria-hidden />
        <h2 className="text-sm font-semibold text-foreground">Havale / EFT Bilgisi</h2>
        <span
          className={cn(
            "ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium",
            havale.enabled
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200"
              : "bg-muted text-muted-foreground",
          )}
        >
          {havale.enabled ? "Aktif" : "Kapalı (IBAN boş)"}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {"IBAN girilirse teklif sayfasında \"Havale/EFT ile öde\" seçeneği görünür. Boş bırakılırsa yalnız \"Üyelik talebi\" akışı çalışır."}
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium text-muted-foreground sm:col-span-2">
          IBAN
          <input
            value={iban}
            onChange={(e) => setIban(e.target.value)}
            placeholder="TR.. (boş = havale kapalı)"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 font-mono text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Alıcı adı
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Ad Soyad"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
        <label className="text-xs font-medium text-muted-foreground">
          Açıklama notu
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Örn. Açıklamaya adınızı yazın"
            className="mt-1 w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </label>
      </div>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={() => setHavale.mutate({ body: { iban, name, note } })}
          disabled={setHavale.isPending}
          className="inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-50"
        >
          {setHavale.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
          Kaydet
        </button>
      </div>
    </section>
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
  onClose,
}: {
  created: MembershipOfferCreated;
  targetName: string | null;
  planLabel: string;
  offerType: string;
  onClose: () => void;
}) {
  const typeLabel = offerType === "renewal" ? "üyelik yenileme" : "üyelik";
  const text = `Merhaba${targetName ? " " + targetName : ""},\n\nETÜTKOÇ ${typeLabel} teklifin hazır (${planLabel}).\nÜyeliğini tamamlamak için:\n${created.public_url}`;
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

// ------------------------------------------------------------------- Liste
function OffersList({
  items,
  planOptions,
}: {
  items: MembershipOfferListItem[];
  planOptions: MembershipPlanOption[];
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
        {items.map((o) => {
          const typeLabel = o.offer_type === "renewal" ? "Yenileme" : "Yeni";
          const text = `Merhaba${o.target_name ? " " + o.target_name : ""},\n\nETÜTKOÇ üyelik teklifin hazır (${o.plan_label}).\nÜyeliğini tamamlamak için:\n${o.public_url}`;
          return (
            <div
              key={o.id}
              className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border border-border/70 px-3 py-2 text-sm"
            >
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
              <div className="ml-auto flex items-center gap-2">
                <CopyButton value={o.public_url} label="Link" />
                <a
                  href={waUrl(o.target_phone, text)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                  title={o.target_phone ? "Doğrudan koça WhatsApp" : "WhatsApp aç (alıcı seç)"}
                >
                  <MessageCircle className="size-3" aria-hidden /> WhatsApp
                </a>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
