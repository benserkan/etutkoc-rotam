"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Building2,
  Check,
  CheckCircle2,
  Copy,
  Inbox,
  Loader2,
  Mail,
  MailOpen,
  Phone,
  Rocket,
  Settings2,
} from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
import { adminKeys, getAdminContactRequests } from "@/lib/api/admin";
import { useOnboardInstitution, useUpdateContactRequest } from "@/lib/hooks/use-admin-mutations";
import type { OnboardInstitutionResult } from "@/lib/types/admin";
import type {
  ContactRequestItem,
  ContactRequestListResponse,
} from "@/lib/types/admin";

interface Props {
  initial: ContactRequestListResponse;
}

const FILTERS: { value: string | null; label: string }[] = [
  { value: null, label: "Tümü" },
  { value: "new", label: "Yeni" },
  { value: "contacted", label: "İletişime geçildi" },
  { value: "closed", label: "Kapatıldı" },
];

export function AdminContactRequestsClient({ initial }: Props) {
  const [status, setStatus] = React.useState<string | null>(null);

  const q = useQuery<ContactRequestListResponse>({
    queryKey: adminKeys.contactRequests(status),
    queryFn: () => getAdminContactRequests(status),
    initialData: status === null ? initial : undefined,
    staleTime: 20_000,
  });
  const data = q.data;
  const counts = data?.counts ?? initial.counts;

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">
          ← Panel
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <Inbox className="size-6 text-indigo-700" aria-hidden />
          İletişim Talepleri
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Fiyatlandırma sayfasının kurumsal bölümünden gelen teklif/iletişim
          talepleri. Buradan durumunu işaretleyip not ekleyebilirsiniz.
        </p>
      </header>

      {/* Sayım kartları */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <CountCard label="Toplam" value={counts.total ?? 0} tone="slate" />
        <CountCard label="Yeni" value={counts.new ?? 0} tone="amber" />
        <CountCard label="İletişime geçildi" value={counts.contacted ?? 0} tone="sky" />
        <CountCard label="Kapatıldı" value={counts.closed ?? 0} tone="emerald" />
      </div>

      {/* Filtre */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setStatus(f.value)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition",
              status === f.value
                ? "border-indigo-600 bg-indigo-600 text-white"
                : "border-input bg-card text-muted-foreground hover:border-indigo-300",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      {!data || data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            {q.isLoading ? (
              <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
            ) : (
              "Bu filtrede talep yok."
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">Tarih</th>
                  <th className="px-4 py-2 text-left font-medium">Kişi</th>
                  <th className="px-4 py-2 text-left font-medium">Kurum</th>
                  <th className="px-4 py-2 text-left font-medium">Mesaj</th>
                  <th className="px-4 py-2 text-left font-medium">Durum</th>
                  <th className="px-4 py-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((it) => (
                  <ContactRow key={it.id} item={it} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}

function CountCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "slate" | "amber" | "sky" | "emerald";
}) {
  const cls: Record<typeof tone, string> = {
    slate: "border-slate-200 bg-slate-50 text-slate-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    sky: "border-sky-200 bg-sky-50 text-sky-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className={cn("rounded-xl border p-4", cls[tone])}>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs font-medium opacity-80">{label}</div>
    </div>
  );
}

function ContactRow({ item }: { item: ContactRequestItem }) {
  return (
    <tr className={cn(item.status === "new" && "bg-amber-50/30")}>
      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground tabular-nums">
        {formatDateTime(item.created_at)}
      </td>
      <td className="px-4 py-3">
        <div className="font-medium">{item.name}</div>
        <a href={`mailto:${item.email}`} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline">
          <Mail className="size-3" aria-hidden /> {item.email}
        </a>
        {item.phone ? (
          <a href={`tel:${item.phone.replace(/[^0-9+]/g, "")}`} className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <Phone className="size-3" aria-hidden /> {item.phone}
          </a>
        ) : null}
      </td>
      <td className="px-4 py-3 text-xs">
        {item.institution_name ? (
          <span className="inline-flex items-center gap-1">
            <Building2 className="size-3 text-muted-foreground" aria-hidden /> {item.institution_name}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
        {item.coach_count != null ? (
          <div className="text-muted-foreground">{item.coach_count} koç</div>
        ) : null}
        <div className="mt-0.5 text-[11px] text-muted-foreground/70">{item.source_label}</div>
      </td>
      <td className="max-w-xs px-4 py-3 text-xs text-foreground/80">
        {item.message ? <span className="line-clamp-3">{item.message}</span> : <span className="text-muted-foreground">—</span>}
        {item.admin_note ? (
          <div className="mt-1 rounded bg-muted/60 px-2 py-1 text-[11px] text-muted-foreground">
            Not: {item.admin_note}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={item.status} label={item.status_label} />
      </td>
      <td className="px-4 py-3 text-right">
        <div className="inline-flex flex-col items-end gap-1">
          {item.status !== "closed" && !item.linked_institution_id && !item.linked_user_id ? (
            <OnboardDialog item={item} />
          ) : null}
          <ManageDialog item={item} />
        </div>
      </td>
    </tr>
  );
}

function StatusBadge({ status, label }: { status: string; label: string }) {
  const cls: Record<string, string> = {
    new: "bg-amber-50 text-amber-700 border-amber-200",
    contacted: "bg-sky-50 text-sky-700 border-sky-200",
    closed: "bg-slate-100 text-slate-600 border-slate-200",
  };
  return (
    <span className={cn("inline-flex items-center rounded border px-2 py-0.5 text-xs", cls[status] ?? cls.closed)}>
      {label}
    </span>
  );
}

function ManageDialog({ item }: { item: ContactRequestItem }) {
  const mut = useUpdateContactRequest(item.id);
  const [open, setOpen] = React.useState(false);
  const [status, setStatus] = React.useState(item.status);
  const [note, setNote] = React.useState(item.admin_note ?? "");

  function save() {
    mut.mutate(
      { status, admin_note: note.trim() || undefined },
      { onSuccess: () => setOpen(false) },
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-800"
      >
        <Settings2 className="size-3.5" aria-hidden /> Yönet
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <MailOpen className="size-4 text-indigo-700" aria-hidden />
              Talebi yönet
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs">
              <div className="font-medium">{item.name} · {item.email}</div>
              {item.institution_name ? <div className="text-muted-foreground">{item.institution_name}{item.coach_count != null ? ` · ${item.coach_count} koç` : ""}</div> : null}
              {/* Kurum abonelik talebi: mevcut → talep edilen planı NET göster */}
              {item.linked_institution_id && (item.institution_current_plan_label || item.requested_plan_label) ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-medium text-slate-700">
                    Mevcut: {item.institution_current_plan_label ?? "—"}
                  </span>
                  <ArrowUpRight className="size-3.5 text-cyan-600" aria-hidden />
                  <span className="rounded border border-cyan-300 bg-cyan-50 px-1.5 py-0.5 font-medium text-cyan-800">
                    Talep edilen: {item.requested_plan_label ?? "Belirtilmedi"}
                  </span>
                </div>
              ) : null}
              {item.message ? <p className="mt-1 text-muted-foreground">{item.message}</p> : null}
              {item.linked_user_id ? (
                <Link
                  href={`/admin/users/${item.linked_user_id}`}
                  className="mt-2 inline-flex items-center gap-1 font-medium text-indigo-600 hover:underline"
                >
                  <ArrowUpRight className="size-3.5" aria-hidden /> Koç sayfasına git (aboneliği aktive et)
                </Link>
              ) : null}
              {item.linked_institution_id ? (
                <div className="mt-2 space-y-1">
                  <Link
                    href={`/admin/institutions/${item.linked_institution_id}#plan`}
                    className="inline-flex items-center gap-1 font-medium text-indigo-600 hover:underline"
                  >
                    <ArrowUpRight className="size-3.5" aria-hidden /> Kurum sayfasına git (planı değiştir)
                  </Link>
                  <p className="text-[11px] text-muted-foreground">
                    Planı değiştirdikten sonra bu talebi aşağıdan{" "}
                    <strong>&quot;Kapatıldı&quot;</strong> olarak işaretle.
                  </p>
                </div>
              ) : null}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Durum</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
              >
                <option value="new">Yeni</option>
                <option value="contacted">İletişime geçildi</option>
                <option value="closed">Kapatıldı</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted-foreground">Not (yalnız yönetim görür)</label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                placeholder="Görüşme notu, sonraki adım…"
                className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={mut.isPending}>
              Vazgeç
            </Button>
            <Button onClick={save} disabled={mut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              Kaydet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Plan kodu → varsayılan aylık tutar (₺). pricing.py ile tutarlı.
 * Yıllık = aylık × 10 (akademik yıl peşin, 2 ay bedava — CLAUDE.md kuralı).
 * 0 = "özel teklif" veya ücretsiz, admin manuel girer.
 */
const PLAN_DEFAULT_AMOUNTS: Record<string, number> = {
  institution_free: 0,
  etut_standart: 10000,
  dershane_pro: 30000,
  enterprise: 0, // özel teklif — manuel
};

/**
 * "Talepten Aktivasyona" — tek dialog: kurum + yönetici + ödeme linki + e-posta.
 * Başarı sonrası geçici şifre + URL'yi gösteren sonuç ekranı.
 */
function OnboardDialog({ item }: { item: ContactRequestItem }) {
  const mut = useOnboardInstitution(item.id);
  const [open, setOpen] = React.useState(false);
  const [result, setResult] = React.useState<OnboardInstitutionResult | null>(null);

  // Form state — contact_request'tan ön-doldurulur
  const [instName, setInstName] = React.useState(item.institution_name ?? "");
  const [adminName, setAdminName] = React.useState(item.name ?? "");
  const [adminEmail, setAdminEmail] = React.useState(item.email ?? "");
  const [plan, setPlan] = React.useState("etut_standart");
  const [amount, setAmount] = React.useState(10000);
  const [cycle, setCycle] = React.useState<"monthly" | "annual">("monthly");
  const [description, setDescription] = React.useState("");
  const [expiresInDays, setExpiresInDays] = React.useState(14);
  const [sendEmail, setSendEmail] = React.useState(true);

  // Plan + cycle değişince tutarı otomatik güncelle (yıllık = aylık × 10).
  // Süper admin yine manuel override yapabilir (özel pazarlık).
  function changePlan(newPlan: string) {
    setPlan(newPlan);
    const d = PLAN_DEFAULT_AMOUNTS[newPlan];
    if (d != null) setAmount(cycle === "annual" ? d * 10 : d);
  }
  function changeCycle(newCycle: "monthly" | "annual") {
    setCycle(newCycle);
    const d = PLAN_DEFAULT_AMOUNTS[plan];
    if (d != null) setAmount(newCycle === "annual" ? d * 10 : d);
  }

  // Open'da prop değişirse state senkronla
  const initKey = `${item.id}|${item.institution_name ?? ""}`;
  const [prevInitKey, setPrevInitKey] = React.useState(initKey);
  if (initKey !== prevInitKey) {
    setPrevInitKey(initKey);
    setInstName(item.institution_name ?? "");
    setAdminName(item.name ?? "");
    setAdminEmail(item.email ?? "");
  }

  const valid = instName.trim().length >= 2
    && adminName.trim().length >= 3
    && /.+@.+\..+/.test(adminEmail)
    && amount > 0;

  function submit() {
    mut.mutate(
      {
        institution_name: instName.trim(),
        plan,
        admin_full_name: adminName.trim(),
        admin_email: adminEmail.trim().toLowerCase(),
        payment_amount: amount,
        payment_cycle: cycle,
        payment_description: description.trim() || undefined,
        payment_expires_in_days: expiresInDays,
        send_email: sendEmail,
      },
      { onSuccess: (res) => setResult(res.data) },
    );
  }

  function close() {
    setOpen(false);
    setResult(null);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded border border-cyan-300 bg-cyan-50 px-2 py-0.5 text-xs font-semibold text-cyan-700 hover:bg-cyan-100"
      >
        <Rocket className="size-3.5" aria-hidden /> Kurum Aç + Aktive Et
      </button>
      <Dialog open={open} onOpenChange={(v) => { if (!v) close(); else setOpen(true); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="inline-flex items-center gap-2">
              <Rocket className="size-4 text-cyan-700" aria-hidden />
              {result ? "Aktivasyon tamamlandı" : "Talepten aktivasyona"}
            </DialogTitle>
          </DialogHeader>

          {result ? (
            <OnboardSuccessPanel result={result} onClose={close} />
          ) : (
            <div className="space-y-4">
              {/* Talep özeti */}
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                <p className="font-semibold">Talep özeti</p>
                <p>{item.name} · {item.email}{item.phone ? ` · ${item.phone}` : ""}</p>
                {item.message ? <p className="mt-1 italic">{item.message}</p> : null}
              </div>

              {/* Kurum bilgileri */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-700">1. Kurum</h3>
                <div>
                  <Label htmlFor="inst_name" className="text-xs">Kurum adı</Label>
                  <Input
                    id="inst_name"
                    value={instName}
                    onChange={(e) => setInstName(e.target.value)}
                    placeholder="Demir Etüt Merkezi"
                  />
                </div>
                <div>
                  <Label htmlFor="plan" className="text-xs">Kurum paketi</Label>
                  <select
                    id="plan"
                    value={plan}
                    onChange={(e) => changePlan(e.target.value)}
                    className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
                  >
                    <option value="institution_free">Kurum Tanıma (Ücretsiz)</option>
                    <option value="etut_standart">Etüt Standart (≤10 koç)</option>
                    <option value="dershane_pro">Dershane Pro (≤50 koç)</option>
                    <option value="enterprise">Enterprise (Özel)</option>
                  </select>
                  <p className="mt-1 text-[11px] text-slate-500">
                    Paket veya dönem değişince tutar otomatik güncellenir. Özel pazarlık için manuel girin.
                  </p>
                </div>
              </div>

              {/* Yönetici */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-700">2. Kurum yöneticisi</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="adm_name" className="text-xs">Ad Soyad</Label>
                    <Input id="adm_name" value={adminName} onChange={(e) => setAdminName(e.target.value)} />
                  </div>
                  <div>
                    <Label htmlFor="adm_email" className="text-xs">E-posta</Label>
                    <Input id="adm_email" type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} />
                  </div>
                </div>
                <p className="text-[11px] text-slate-600">
                  14 karakter güçlü geçici şifre otomatik üretilir. İlk girişte zorunlu değiştirme.
                </p>
              </div>

              {/* Ödeme linki */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-slate-700">3. Ödeme linki</h3>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <Label htmlFor="amount" className="text-xs">Tutar (₺)</Label>
                    <Input
                      id="amount"
                      type="number"
                      min={1}
                      value={amount || ""}
                      onChange={(e) => setAmount(Number(e.target.value) || 0)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="cycle" className="text-xs">Dönem</Label>
                    <select
                      id="cycle"
                      value={cycle}
                      onChange={(e) => changeCycle(e.target.value as "monthly" | "annual")}
                      className="w-full rounded border border-input bg-card px-3 py-2 text-sm"
                    >
                      <option value="monthly">Aylık</option>
                      <option value="annual">Yıllık (10 ay)</option>
                    </select>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label htmlFor="desc" className="text-xs">Açıklama (ops.)</Label>
                    <Input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Özel pazarlık notu" />
                  </div>
                  <div>
                    <Label htmlFor="expires" className="text-xs">Geçerlilik (gün)</Label>
                    <Input
                      id="expires"
                      type="number"
                      min={1}
                      max={365}
                      value={expiresInDays}
                      onChange={(e) => setExpiresInDays(Number(e.target.value) || 14)}
                    />
                  </div>
                </div>
              </div>

              {/* E-posta seçeneği */}
              <label className="flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-xs">
                <input
                  type="checkbox"
                  checked={sendEmail}
                  onChange={(e) => setSendEmail(e.target.checked)}
                  className="mt-0.5"
                />
                <span>
                  <strong>Yöneticiye otomatik e-posta gönder</strong> — giriş bilgileri + ödeme bağlantısı tek mailde.
                  Kapatırsan süper admin elden iletir.
                </span>
              </label>
            </div>
          )}

          {!result ? (
            <DialogFooter className="gap-2 pt-2">
              <Button variant="ghost" onClick={close} disabled={mut.isPending}>
                Vazgeç
              </Button>
              <Button
                onClick={submit}
                disabled={!valid || mut.isPending}
                className="bg-cyan-700 text-white hover:bg-cyan-800"
              >
                {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Rocket className="size-4" aria-hidden />}
                Kurumu Oluştur + Ödeme Linki Hazırla
              </Button>
            </DialogFooter>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}

function OnboardSuccessPanel({
  result, onClose,
}: { result: OnboardInstitutionResult; onClose: () => void }) {
  const [copiedPwd, setCopiedPwd] = React.useState(false);
  const [copiedUrl, setCopiedUrl] = React.useState(false);

  async function copy(text: string, what: "pwd" | "url") {
    try {
      await navigator.clipboard.writeText(text);
      if (what === "pwd") {
        setCopiedPwd(true);
        setTimeout(() => setCopiedPwd(false), 2000);
      } else {
        setCopiedUrl(true);
        setTimeout(() => setCopiedUrl(false), 2000);
      }
    } catch {
      // sessizce yut
    }
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
        <p className="flex items-center gap-2 font-semibold">
          <CheckCircle2 className="size-4" aria-hidden /> {result.message}
        </p>
      </div>

      {/* Yönetici bilgileri */}
      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
        <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Kurum yöneticisi giriş bilgileri</p>
        <div className="mt-2 space-y-1.5 text-sm">
          <div>
            <span className="text-xs text-slate-600">E-posta:</span>{" "}
            <code className="rounded bg-white px-1.5 py-0.5 font-mono text-xs">{result.institution_admin_email}</code>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-600">Geçici şifre:</span>
            <code className="flex-1 rounded bg-amber-100 px-1.5 py-0.5 font-mono text-xs font-bold text-amber-900">{result.temp_password}</code>
            <button
              type="button"
              onClick={() => copy(result.temp_password, "pwd")}
              className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-2 py-0.5 text-xs hover:bg-slate-50"
            >
              {copiedPwd ? <Check className="size-3 text-emerald-600" aria-hidden /> : <Copy className="size-3" aria-hidden />}
              {copiedPwd ? "Kopyalandı" : "Kopyala"}
            </button>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-slate-600">
          Geçici şifre sadece <strong>bu ekran</strong>da görünür. Yönetici ilk girişte zorunlu olarak değiştirir.
        </p>
      </div>

      {/* Ödeme linki */}
      <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3">
        <p className="text-[11px] font-bold uppercase tracking-wide text-cyan-700">Ödeme linki</p>
        <div className="mt-2 flex items-center gap-2">
          <code className="flex-1 truncate rounded bg-white px-2 py-1 font-mono text-xs">{result.payment_link_url}</code>
          <button
            type="button"
            onClick={() => copy(result.payment_link_url, "url")}
            className="inline-flex items-center gap-1 rounded border border-cyan-300 bg-white px-2 py-0.5 text-xs hover:bg-cyan-50"
          >
            {copiedUrl ? <Check className="size-3 text-emerald-600" aria-hidden /> : <Copy className="size-3" aria-hidden />}
            {copiedUrl ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
        <p className="mt-2 text-[11px] text-cyan-800">
          Kurum yöneticisi <strong>önce giriş yapıp şifresini değiştirmeli</strong>, sonra bu linkten ödeme yapabilir.
        </p>
      </div>

      {/* E-posta durumu */}
      {result.email_sent ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/60 p-3 text-xs text-emerald-800">
          <Mail className="inline size-3.5" aria-hidden /> Yöneticiye onboarding e-postası başarıyla gönderildi
          (giriş bilgileri + ödeme bağlantısı dahil).
        </div>
      ) : (
        <div className="rounded-lg border border-amber-200 bg-amber-50/60 p-3 text-xs text-amber-800">
          ⚠ E-posta gönderilmedi — geçici şifreyi ve linki <strong>elden iletmen</strong> gerek (WhatsApp/SMS).
        </div>
      )}

      <DialogFooter className="pt-2">
        <Button onClick={onClose}>Tamam</Button>
        <Button asChild className="bg-cyan-700 text-white hover:bg-cyan-800">
          <Link href={`/admin/institutions/${result.institution_id}`}>
            Kurum sayfasına git <ArrowUpRight className="size-3" aria-hidden />
          </Link>
        </Button>
      </DialogFooter>
    </div>
  );
}

function formatDateTime(iso: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
