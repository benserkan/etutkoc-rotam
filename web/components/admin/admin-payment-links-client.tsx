"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  Building2,
  CheckCircle2,
  Copy,
  Link2,
  Loader2,
  Plus,
  User as UserIcon,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getAdminPaymentLinks,
  paymentKeys,
} from "@/lib/api/payment";
import {
  useCancelPaymentLink,
  useCreatePaymentLink,
} from "@/lib/hooks/use-payment-mutations";
import type {
  PaymentLinkCreateBody,
  PaymentLinkItem,
  PaymentLinkListResponse,
} from "@/lib/types/payment";

interface Props {
  initial: PaymentLinkListResponse;
}

type StatusFilter = "" | "active" | "consumed" | "cancelled" | "expired";

const STATUS_LABELS: Record<string, string> = {
  active: "Aktif",
  consumed: "Ödendi",
  cancelled: "İptal",
  expired: "Süresi geçti",
};

const STATUS_TONE: Record<string, string> = {
  active: "bg-amber-100 text-amber-800 border-amber-200",
  consumed: "bg-emerald-100 text-emerald-800 border-emerald-200",
  cancelled: "bg-slate-200 text-slate-700 border-slate-300",
  expired: "bg-rose-100 text-rose-800 border-rose-200",
};

export function AdminPaymentLinksClient({ initial }: Props) {
  const [statusFilter, setStatusFilter] = React.useState<StatusFilter>("");
  const [createOpen, setCreateOpen] = React.useState(false);

  const q = useQuery<PaymentLinkListResponse>({
    queryKey: paymentKeys.adminLinks(statusFilter || null, null),
    queryFn: () => getAdminPaymentLinks(statusFilter || null),
    initialData: statusFilter === "" ? initial : undefined,
  });

  const data = q.data ?? initial;
  const counts = React.useMemo(() => {
    const c: Record<string, number> = {
      total: initial.items.length,
      active: 0, consumed: 0, cancelled: 0, expired: 0,
    };
    for (const it of initial.items) {
      c[it.status] = (c[it.status] ?? 0) + 1;
    }
    return c;
  }, [initial.items]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ödeme Linkleri</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Kurum ödemesi için tek-kullanımlık link oluştur. Link e-posta/WhatsApp ile
            gönderilir; kurum yöneticisi linkten kartla öder; plan otomatik aktive olur.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" aria-hidden /> Yeni Ödeme Linki
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <CountCard label="Toplam" value={counts.total} tone="slate" />
        <CountCard label="Aktif (bekliyor)" value={counts.active} tone="amber" />
        <CountCard label="Ödendi" value={counts.consumed} tone="emerald" />
        <CountCard label="İptal" value={counts.cancelled} tone="slate" />
        <CountCard label="Süresi geçti" value={counts.expired} tone="rose" />
      </div>

      <div className="flex flex-wrap gap-2">
        <FilterChip
          active={statusFilter === ""}
          onClick={() => setStatusFilter("")}
        >
          Tümü
        </FilterChip>
        {(["active", "consumed", "cancelled", "expired"] as StatusFilter[]).map((s) => (
          <FilterChip
            key={s}
            active={statusFilter === s}
            onClick={() => setStatusFilter(s)}
          >
            {STATUS_LABELS[s as string]}
          </FilterChip>
        ))}
      </div>

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            {q.isLoading ? (
              <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
            ) : (
              "Bu filtrede link yok."
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Hedef</th>
                  <th className="px-4 py-2 text-left font-medium">Paket</th>
                  <th className="px-4 py-2 text-right font-medium">Tutar</th>
                  <th className="px-4 py-2 text-left font-medium">Durum</th>
                  <th className="px-4 py-2 text-left font-medium">Süre</th>
                  <th className="px-4 py-2 text-right font-medium">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((it) => (
                  <LinkRow key={it.id} item={it} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* key ile remount → her açılışta form sıfırlanır (set-state-in-effect yerine) */}
      <CreateLinkDialog
        key={createOpen ? "open" : "closed"}
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </div>
  );
}

function CountCard({
  label, value, tone,
}: {
  label: string;
  value: number;
  tone: "slate" | "amber" | "sky" | "emerald" | "rose";
}) {
  const cls: Record<typeof tone, string> = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    sky: "border-sky-200 bg-sky-50 text-sky-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
  };
  return (
    <div className={cn("rounded-xl border p-4", cls[tone])}>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs font-medium opacity-80">{label}</div>
    </div>
  );
}

function FilterChip({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition",
        active
          ? "border-indigo-500 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
      )}
    >
      {children}
    </button>
  );
}

function LinkRow({ item }: { item: PaymentLinkItem }) {
  const [confirmCancel, setConfirmCancel] = React.useState(false);
  const cancelM = useCancelPaymentLink();

  const isInst = item.target_owner_type === "institution";

  return (
    <>
      <tr className={cn(item.status === "active" && "bg-amber-50/20")}>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {isInst ? (
              <Building2 className="size-4 text-slate-500" aria-hidden />
            ) : (
              <UserIcon className="size-4 text-slate-500" aria-hidden />
            )}
            <div>
              <div className="font-medium">
                {item.target_owner_name ?? "—"}
              </div>
              <div className="text-xs text-muted-foreground">
                {isInst ? "Kurum" : "Kullanıcı"} #{item.target_owner_id}
              </div>
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-xs">
          <div className="font-medium text-slate-800">{item.plan_code}</div>
          <div className="text-muted-foreground">
            {item.cycle === "annual" ? "Yıllık" : "Aylık"}
          </div>
        </td>
        <td className="px-4 py-3 text-right tabular-nums">
          <div className="font-semibold">
            {formatAmount(item.amount, item.currency)}
          </div>
        </td>
        <td className="px-4 py-3">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
              STATUS_TONE[item.status] ?? "bg-slate-100 text-slate-700",
            )}
          >
            {item.status === "consumed" && <CheckCircle2 className="size-3" aria-hidden />}
            {item.status === "active" && <Link2 className="size-3" aria-hidden />}
            {item.status === "expired" && <AlertOctagon className="size-3" aria-hidden />}
            {item.status_label}
          </span>
          {item.status === "consumed" && item.consumed_by_user_name ? (
            <div className="mt-1 text-xs text-emerald-700">
              {item.consumed_by_user_name}
            </div>
          ) : null}
        </td>
        <td className="px-4 py-3 text-xs text-muted-foreground tabular-nums">
          {item.expires_at ? formatDate(item.expires_at) : "—"}
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center justify-end gap-2">
            <CopyButton url={item.public_url} disabled={item.status !== "active"} />
            {item.status === "active" && (
              <Button
                size="sm"
                variant="outline"
                className="text-rose-700"
                onClick={() => setConfirmCancel(true)}
              >
                <X className="size-3" aria-hidden /> İptal
              </Button>
            )}
          </div>
        </td>
      </tr>
      <Dialog open={confirmCancel} onOpenChange={setConfirmCancel}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bu linki iptal et?</DialogTitle>
          </DialogHeader>
          <div className="text-sm text-muted-foreground">
            <strong>{item.target_owner_name}</strong> için oluşturulan{" "}
            <strong>{formatAmount(item.amount, item.currency)}</strong> tutarındaki link
            iptal edilecek. Bu işlem geri alınamaz; aynı kurum için yeni link
            oluşturulabilir.
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmCancel(false)}>
              Vazgeç
            </Button>
            <Button
              variant="destructive"
              disabled={cancelM.isPending}
              onClick={() => {
                cancelM.mutate(item.id, {
                  onSuccess: () => setConfirmCancel(false),
                });
              }}
            >
              {cancelM.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                "Evet, iptal et"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function CopyButton({ url, disabled }: { url: string; disabled: boolean }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <Button
      size="sm"
      variant="outline"
      disabled={disabled}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(url);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          // sessizce yut — bazı tarayıcılar https zorunlu kılar
        }
      }}
    >
      {copied ? (
        <>
          <CheckCircle2 className="size-3 text-emerald-600" aria-hidden /> Kopyalandı
        </>
      ) : (
        <>
          <Copy className="size-3" aria-hidden /> URL Kopyala
        </>
      )}
    </Button>
  );
}

function CreateLinkDialog({
  open, onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const [form, setForm] = React.useState<PaymentLinkCreateBody>({
    target_owner_type: "institution",
    target_owner_id: 0,
    plan_code: "etut_standart",
    cycle: "annual",
    amount: 0,
    description: "",
    expires_in_days: 14,
  });

  const create = useCreatePaymentLink();

  // Form reset için useEffect KULLANMA — parent component `key` ile remount eder
  // (set-state-in-effect kuralı için bu desen tercih edildi)

  const isInst = form.target_owner_type === "institution";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Yeni Ödeme Linki</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Hedef türü</Label>
            <div className="flex gap-2">
              <OwnerTypeButton
                active={isInst}
                onClick={() => setForm((f) => ({ ...f, target_owner_type: "institution" }))}
              >
                <Building2 className="size-4" aria-hidden /> Kurum
              </OwnerTypeButton>
              <OwnerTypeButton
                active={!isInst}
                onClick={() => setForm((f) => ({ ...f, target_owner_type: "user" }))}
              >
                <UserIcon className="size-4" aria-hidden /> Bağımsız Koç
              </OwnerTypeButton>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="target_id">
              {isInst ? "Kurum ID" : "Kullanıcı ID"}
            </Label>
            <Input
              id="target_id"
              type="number"
              min={1}
              value={form.target_owner_id || ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, target_owner_id: Number(e.target.value) || 0 }))
              }
              placeholder={isInst ? "Örn. 1" : "Örn. 42"}
            />
            <p className="text-xs text-muted-foreground">
              {isInst
                ? "/admin/institutions sayfasından kurumu bulup ID'sini kopyalayın."
                : "/admin/users sayfasından kullanıcıyı bulup ID'sini kopyalayın."}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="plan_code">Paket kodu</Label>
              <select
                id="plan_code"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.plan_code}
                onChange={(e) => setForm((f) => ({ ...f, plan_code: e.target.value }))}
              >
                {isInst ? (
                  <>
                    <option value="etut_standart">Etüt Standart</option>
                    <option value="dershane_pro">Dershane Pro</option>
                    <option value="enterprise">Enterprise (Özel)</option>
                  </>
                ) : (
                  <>
                    <option value="solo_pro">Solo Başlangıç</option>
                    <option value="solo_elite">Solo</option>
                    <option value="solo_unlimited">Solo Sınırsız</option>
                  </>
                )}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="cycle">Dönem</Label>
              <select
                id="cycle"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={form.cycle}
                onChange={(e) =>
                  setForm((f) => ({ ...f, cycle: e.target.value as "monthly" | "annual" }))
                }
              >
                <option value="monthly">Aylık</option>
                <option value="annual">Yıllık (10 ay peşin)</option>
              </select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="amount">Tutar (₺)</Label>
            <Input
              id="amount"
              type="number"
              min={1}
              step={1}
              value={form.amount || ""}
              onChange={(e) =>
                setForm((f) => ({ ...f, amount: Number(e.target.value) || 0 }))
              }
              placeholder="Örn. 100000"
            />
            <p className="text-xs text-muted-foreground">
              Müzakere edilen tutar. Sistem otomatik hesaplamaz (kurum fiyatı özel olabilir).
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="description">Açıklama (opsiyonel)</Label>
            <Input
              id="description"
              maxLength={500}
              value={form.description ?? ""}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="Örn. 2026-2027 sezonu özel teklif"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="expires">Geçerlilik süresi (gün)</Label>
            <Input
              id="expires"
              type="number"
              min={1}
              max={365}
              value={form.expires_in_days ?? 14}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  expires_in_days: Number(e.target.value) || 14,
                }))
              }
            />
            <p className="text-xs text-muted-foreground">
              Bu süre sonunda link otomatik geçersiz olur (varsayılan 14 gün).
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Vazgeç
          </Button>
          <Button
            disabled={
              create.isPending ||
              !form.target_owner_id ||
              !form.amount ||
              form.amount <= 0
            }
            onClick={() => {
              create.mutate(form, {
                onSuccess: () => onOpenChange(false),
              });
            }}
          >
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              "Link Oluştur"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function OwnerTypeButton({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-2 rounded-md border px-3 py-2 text-sm font-medium transition",
        active
          ? "border-indigo-500 bg-indigo-50 text-indigo-700"
          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300",
      )}
    >
      {children}
    </button>
  );
}

function formatAmount(value: number, currency: string): string {
  try {
    return new Intl.NumberFormat("tr-TR", {
      style: "currency",
      currency: currency || "TRY",
      maximumFractionDigits: 0,
    }).format(value);
  } catch {
    return `${value} ${currency}`;
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
