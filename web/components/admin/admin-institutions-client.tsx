"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  ChevronDown,
  ImageIcon,
  Loader2,
  Plus,
  Search,
  Upload,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { adminKeys, getAdminInstitutions, uploadInstitutionLogo } from "@/lib/api/admin";
import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import { useCreateInstitution } from "@/lib/hooks/use-admin-mutations";
import { buildInstitutionPlanOptions, institutionPlanLabel } from "@/lib/institution-plans";
import type {
  HealthLevel,
  InstitutionListItem,
  InstitutionListResponse,
  InstitutionMutationResult,
} from "@/lib/types/admin";
import type { PricingCatalog } from "@/lib/types/pricing";

interface Props {
  initial: InstitutionListResponse;
  initialLevel?: LevelFilter;
}

export type LevelFilter = "all" | HealthLevel;
type InstSort = "health" | "name" | "students" | "activity";

const LEVELS: { key: LevelFilter; label: string; hint: string; dot: string }[] = [
  { key: "all", label: "Tümü", hint: "Tüm kurumlar", dot: "bg-slate-400" },
  { key: "critical", label: "Acil ilgi", hint: "Sağlık puanı en kötü kademede — ayrılma riski yüksek", dot: "bg-rose-600" },
  { key: "risk", label: "Riskli", hint: "Birden çok olumsuz işaret var", dot: "bg-orange-500" },
  { key: "watch", label: "Gözlem", hint: "Tek tük işaret — izlemeye değer", dot: "bg-amber-400" },
  { key: "healthy", label: "Sağlıklı", hint: "Olumsuz işaret yok ya da çok az", dot: "bg-emerald-600" },
];

const LEVEL_RING: Record<HealthLevel, string> = {
  critical: "ring-rose-600 text-rose-800",
  risk: "ring-orange-500 text-orange-800",
  watch: "ring-amber-400 text-amber-800",
  healthy: "ring-emerald-600 text-emerald-800",
};

function trLower(s: string) {
  return s.toLocaleLowerCase("tr");
}

function lastSeen(item: InstitutionListItem): string | null {
  const vals = [item.last_teacher_login, item.last_student_login].filter(Boolean) as string[];
  return vals.length ? vals.sort().slice(-1)[0] : null;
}

function agoText(iso: string | null): string {
  if (!iso) return "hiç giriş yok";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "bugün";
  if (days === 1) return "dün";
  return `${days} gün önce`;
}

/**
 * Kurumlar — Kullanıcılar sayfasıyla aynı dil (2026-10-17): sağlık çipleri
 * (sayılı), arama, paket süzgeci, sıralama, kart satırlar. Liste küçük
 * olduğundan süzme/sıralama istemcide; sağlık süzgeci URL'de (?level=).
 */
export function AdminInstitutionsClient({ initial, initialLevel = "all" }: Props) {
  const router = useRouter();
  const q = useQuery<InstitutionListResponse>({
    queryKey: adminKeys.institutions("health", null),
    queryFn: () => getAdminInstitutions("health", null),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const [createOpen, setCreateOpen] = React.useState(false);
  const [level, setLevel] = React.useState<LevelFilter>(initialLevel);
  const [term, setTerm] = React.useState("");
  const [plan, setPlan] = React.useState("");
  const [sort, setSort] = React.useState<InstSort>("health");

  function pickLevel(l: LevelFilter) {
    setLevel(l);
    router.replace(l === "all" ? "/admin/institutions" : `/admin/institutions?level=${l}`, { scroll: false });
  }

  const counts: Record<LevelFilter, number> = {
    all: data.items.length,
    critical: data.summary.critical,
    risk: data.summary.risk,
    watch: data.summary.watch,
    healthy: data.summary.healthy,
  };
  const plans = [...new Set(data.items.map((i) => i.institution.plan ?? ""))].filter(Boolean);
  const t = trLower(term.trim());
  const shown = data.items
    .filter((i) => level === "all" || i.level === level)
    .filter((i) => !plan || i.institution.plan === plan)
    .filter((i) => !t || trLower(i.institution.name).includes(t) || trLower(i.institution.slug).includes(t))
    .sort((a, b) => {
      if (sort === "name") return a.institution.name.localeCompare(b.institution.name, "tr");
      if (sort === "students") return b.student_count - a.student_count;
      if (sort === "activity") return (lastSeen(b) ?? "").localeCompare(lastSeen(a) ?? "");
      return b.score - a.score;
    });

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">← Panel</Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Building2 className="size-6 text-indigo-700" aria-hidden />
            Kurumlar
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Sağlık durumuna göre süz; puan yükseldikçe ayrılma riski artar. Satırda son 7 günde giriş yapan koç ve
            öğrenci oranı görünür.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)} className="bg-indigo-700 text-white hover:bg-indigo-800">
          <Plus className="size-4" aria-hidden /> Yeni Kurum
        </Button>
      </header>

      <div className="flex flex-wrap gap-1.5 rounded-xl border bg-card p-2" role="radiogroup" aria-label="Sağlık durumu"
           data-section="inst:levels">
        {LEVELS.map((l) => {
          const active = level === l.key;
          return (
            <button key={l.key} type="button" role="radio" aria-checked={active} title={l.hint}
                    onClick={() => pickLevel(l.key)}
                    className={cn("inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium",
                      active ? "bg-indigo-700 text-white" : "text-foreground hover:bg-muted")}>
              <span className={cn("size-2 rounded-full", l.dot)} aria-hidden />
              {l.label}
              <span className={cn("rounded-full px-1.5 text-xs tabular-nums", active ? "bg-white/20" : "bg-muted")}>
                {counts[l.key]}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Kurum adı ara"
                 aria-label="Kurum ara" className="h-9 pl-8" />
        </div>
        <select aria-label="Paket" value={plan} onChange={(e) => setPlan(e.target.value)}
                className="h-9 rounded-md border border-input bg-card px-2 text-sm">
          <option value="">Tüm paketler</option>
          {plans.map((p) => <option key={p} value={p}>{institutionPlanLabel(p)}</option>)}
        </select>
        <select aria-label="Sıralama" value={sort} onChange={(e) => setSort(e.target.value as InstSort)}
                className="h-9 rounded-md border border-input bg-card px-2 text-sm">
          <option value="health">Risk (yüksek önce)</option>
          <option value="activity">Son aktivite</option>
          <option value="students">Öğrenci sayısı</option>
          <option value="name">Ada göre</option>
        </select>
      </div>

      <section className="overflow-hidden rounded-xl border bg-card" data-section="inst:list">
        <div className="border-b px-4 py-2 text-xs text-muted-foreground">{shown.length} / {data.items.length} kurum</div>
        {shown.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">
            {data.items.length === 0 ? "Henüz kurum yok. Sağ üstten ekle." : "Bu süzgeçle eşleşen kurum yok."}
          </p>
        ) : (
          <ul className="divide-y">{shown.map((i) => <InstitutionItem key={i.institution.id} item={i} />)}</ul>
        )}
      </section>

      <CreateInstitutionDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}

function InstitutionItem({ item }: { item: InstitutionListItem }) {
  const [open, setOpen] = React.useState(false);
  const inst = item.institution;
  const seen = lastSeen(item);
  return (
    <li className={cn("grid gap-x-4 gap-y-2 px-4 py-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1.5fr)_auto]",
                      !inst.is_active && "bg-muted/40")}
        data-institution-id={inst.id}>
      <div className="flex min-w-0 items-start gap-3">
        <span className={cn("mt-0.5 grid size-10 shrink-0 place-items-center rounded-full bg-card text-sm font-semibold tabular-nums ring-2",
                            LEVEL_RING[item.level])}
              title={`Sağlık puanı ${item.score} — ${item.level_label} (yüksek = riskli)`}>{item.score}</span>
        <div className="min-w-0">
          <Link href={`/admin/institutions/${inst.id}`} className="break-words font-medium hover:underline">{inst.name}</Link>
          <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs">
            <span className="rounded bg-sky-700 px-1.5 py-0.5 font-medium text-white">{institutionPlanLabel(inst.plan)}</span>
            <span className="text-muted-foreground">{item.level_label}</span>
            {!inst.is_active && <span className="rounded bg-slate-600 px-1.5 py-0.5 text-white">pasif</span>}
          </div>
          {item.indicators.length > 0 && (
            <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                    className="mt-1 inline-flex items-center gap-0.5 text-xs text-muted-foreground hover:text-foreground">
              <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} aria-hidden />
              {item.indicators.length} işaret — neden?
            </button>
          )}
          {open && (
            <ul className="mt-1 space-y-0.5 text-xs">
              {item.indicators.map((ind) => (
                <li key={ind.code} className="break-words">
                  <span className="font-medium">{ind.title}</span>
                  <span className="text-muted-foreground"> · {ind.detail} (+{ind.weight})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="min-w-0 space-y-1.5 text-sm">
        <div>
          <span className="tabular-nums">{item.teacher_count}</span> koç · <span className="tabular-nums">{item.student_count}</span> öğrenci
        </div>
        <ActivityBar label="Koç" pct={item.teacher_active_pct} tone="indigo" title="Son 7 günde giriş yapan koç oranı" />
        <ActivityBar label="Öğrenci" pct={item.student_active_pct} tone="emerald" title="Son 7 günde giriş yapan öğrenci oranı" />
      </div>

      <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
        <span className="whitespace-nowrap text-xs text-muted-foreground" title="Koç ya da öğrencinin en son girişi">
          son giriş {agoText(seen)}
        </span>
        <div className="flex gap-2">
          <Link href={`/admin/revenue/institutions/${inst.id}`}
                className="inline-flex items-center gap-0.5 rounded-md border px-2 py-1 text-xs hover:bg-muted">
            Ticari 360 <ArrowRight className="size-3" aria-hidden />
          </Link>
          <Link href={`/admin/institutions/${inst.id}`} className="rounded-md border px-2 py-1 text-xs hover:bg-muted">Yönetim</Link>
        </div>
      </div>
    </li>
  );
}

function ActivityBar({ label, pct, tone, title }: {
  label: string; pct: number | null; tone: "indigo" | "emerald"; title: string;
}) {
  return (
    <div className="flex items-center gap-2 text-xs" title={title}>
      <span className="w-14 text-muted-foreground">{label}</span>
      {pct == null ? <span className="text-muted-foreground">—</span> : (
        <>
          <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <span className={cn("block h-full", tone === "indigo" ? "bg-indigo-600" : "bg-emerald-600")}
                  style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
          </span>
          <span className="tabular-nums text-muted-foreground">%{pct} aktif</span>
        </>
      )}
    </div>
  );
}

const LOGO_TYPES = ["image/png", "image/jpeg", "image/webp"];
const LOGO_MAX = 2 * 1024 * 1024;

function CreateInstitutionDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const mut = useCreateInstitution();
  const catalogQ = useQuery<PricingCatalog>({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 60_000,
  });
  const planOptions = buildInstitutionPlanOptions(catalogQ.data);
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [contactEmail, setContactEmail] = React.useState("");
  const [plan, setPlan] = React.useState("institution_free");
  const [adminName, setAdminName] = React.useState("");
  const [createAdmin, setCreateAdmin] = React.useState(true);
  const [sendCreds, setSendCreds] = React.useState(true);
  const [logoFile, setLogoFile] = React.useState<File | null>(null);
  const [logoUrl, setLogoUrl] = React.useState<string | null>(null);
  const [logoError, setLogoError] = React.useState<string | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [done, setDone] = React.useState<{
    res: InstitutionMutationResult;
    logo: "none" | "ok" | "failed";
  } | null>(null);
  const [copied, setCopied] = React.useState(false);
  const selectedPlan = planOptions.find((p) => p.value === plan) ?? planOptions[0];

  function pickLogo(f: File | null) {
    if (logoUrl) URL.revokeObjectURL(logoUrl);
    setLogoError(null);
    if (!f) {
      setLogoFile(null);
      setLogoUrl(null);
      return;
    }
    if (!LOGO_TYPES.includes(f.type)) {
      setLogoFile(null);
      setLogoUrl(null);
      setLogoError("Yalnız PNG, JPEG veya WebP yükleyebilirsin.");
      return;
    }
    if (f.size > LOGO_MAX) {
      setLogoFile(null);
      setLogoUrl(null);
      setLogoError("Logo en fazla 2 MB olabilir.");
      return;
    }
    setLogoFile(f);
    setLogoUrl(URL.createObjectURL(f));
  }

  function reset() {
    setName("");
    setSlug("");
    setContactEmail("");
    setPlan("institution_free");
    setAdminName("");
    setCreateAdmin(true);
    setSendCreds(true);
    pickLogo(null);
    setDone(null);
    setCopied(false);
  }

  const adminReady =
    !createAdmin || (adminName.trim().length >= 3 && contactEmail.trim().length > 3);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        name: name.trim(),
        slug: slug.trim() || null,
        contact_email: contactEmail.trim() || null,
        plan,
        admin_full_name: createAdmin ? adminName.trim() : null,
        admin_email: createAdmin ? contactEmail.trim() : null,
        send_credentials: createAdmin && sendCreds,
      },
      {
        onSuccess: async (res) => {
          let logo: "none" | "ok" | "failed" = "none";
          const instId = res.data.institution?.id;
          if (logoFile && instId) {
            setUploading(true);
            try {
              await uploadInstitutionLogo(instId, logoFile);
              logo = "ok";
            } catch {
              logo = "failed";
            } finally {
              setUploading(false);
            }
          }
          setDone({ res: res.data, logo });
          router.refresh();
        },
      },
    );
  }

  const busy = mut.isPending || uploading;

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (busy) return;
        if (!v) reset();
        onOpenChange(v);
      }}
    >
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{done ? "Kurum hazır" : "Yeni Kurum"}</DialogTitle>
        </DialogHeader>

        {done ? (
          <div className="space-y-4 text-sm" data-testid="institution-created">
            <p className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-2 text-emerald-900">
              {done.res.message}
            </p>
            {done.logo === "ok" ? (
              <p className="text-muted-foreground">
                Logo yüklendi; kurum yöneticisi ve koçların panelinde görünecek.
              </p>
            ) : done.logo === "failed" ? (
              <p className="text-rose-700">
                Logo yüklenemedi. Kurum sayfasındaki logo kartından tekrar deneyebilirsin.
              </p>
            ) : null}
            {done.res.temp_password ? (
              <div className="space-y-2 rounded-md border border-border p-3">
                <p className="font-medium">Kurum yöneticisinin giriş bilgileri</p>
                <p className="break-all">
                  <span className="text-muted-foreground">E-posta:</span> {done.res.admin_email}
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">Geçici şifre:</span>
                  <code
                    className="rounded bg-amber-100 px-2 py-1 font-mono font-semibold text-amber-900"
                    data-testid="admin-temp-password"
                  >
                    {done.res.temp_password}
                  </code>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={async () => {
                      try {
                        await navigator.clipboard.writeText(done.res.temp_password ?? "");
                        setCopied(true);
                      } catch {
                        setCopied(false);
                      }
                    }}
                  >
                    {copied ? "Kopyalandı" : "Kopyala"}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  {done.res.credentials_emailed
                    ? "Giriş bilgileri yöneticiye e-postayla gönderildi."
                    : done.res.credentials_emailed === false
                      ? "E-posta gönderilemedi — bilgileri yöneticiye kendin ilet."
                      : "E-posta gönderilmedi — bilgileri yöneticiye kendin ilet."}{" "}
                  Şifre bu pencere kapanınca tekrar gösterilmez; ilk girişte yönetici kendi
                  şifresini belirler.
                </p>
              </div>
            ) : null}
            <DialogFooter className="gap-2">
              {done.res.institution ? (
                <Button asChild variant="outline">
                  <Link href={`/admin/institutions/${done.res.institution.id}`}>
                    Kurum sayfasına git
                  </Link>
                </Button>
              ) : null}
              <Button
                type="button"
                onClick={() => {
                  reset();
                  onOpenChange(false);
                }}
              >
                Kapat
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-5">
            <fieldset className="space-y-3">
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Kurum
              </legend>
              <div>
                <Label htmlFor="name">
                  Kurum Adı <span className="text-rose-500">*</span>
                </Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  autoFocus
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="plan">Paket</Label>
                <select
                  id="plan"
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                  className="mt-1 w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
                >
                  {planOptions.map((p) => (
                    <option key={p.value} value={p.value}>
                      {p.label} — {p.coaches}
                    </option>
                  ))}
                </select>
                {selectedPlan ? (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{selectedPlan.coaches}.</span>{" "}
                    {selectedPlan.desc}
                  </p>
                ) : null}
              </div>
              <details className="text-sm">
                <summary className="cursor-pointer text-xs text-muted-foreground">
                  Gelişmiş: kısa ad (slug)
                </summary>
                <Input
                  id="slug"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="boş bırakırsan kurum adından üretilir"
                  className="mt-2 font-mono"
                />
              </details>
            </fieldset>

            <fieldset className="space-y-3">
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Kurum sorumlusu
              </legend>
              <div>
                <Label htmlFor="admin_name">
                  Ad Soyad {createAdmin ? <span className="text-rose-500">*</span> : null}
                </Label>
                <Input
                  id="admin_name"
                  value={adminName}
                  onChange={(e) => setAdminName(e.target.value)}
                  placeholder="Kurumu yönetecek kişi"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="contact_email">
                  E-posta {createAdmin ? <span className="text-rose-500">*</span> : null}
                </Label>
                <Input
                  id="contact_email"
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  className="mt-1"
                />
              </div>
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4"
                  checked={createAdmin}
                  onChange={(e) => setCreateAdmin(e.target.checked)}
                />
                <span>
                  Kurum yöneticisi hesabını şimdi oluştur
                  <span className="block text-xs text-muted-foreground">
                    Geçici şifre üretilir; ilk girişte yönetici kendi şifresini belirler.
                  </span>
                </span>
              </label>
              {createAdmin ? (
                <label className="flex items-start gap-2 pl-6 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5 size-4"
                    checked={sendCreds}
                    onChange={(e) => setSendCreds(e.target.checked)}
                  />
                  <span>Giriş bilgilerini yöneticiye e-postayla gönder</span>
                </label>
              ) : null}
            </fieldset>

            <fieldset className="space-y-2">
              <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Logo <span className="normal-case font-normal">(isteğe bağlı)</span>
              </legend>
              <div className="flex flex-wrap items-center gap-3">
                <div
                  className="grid h-20 w-40 place-items-center overflow-hidden rounded-md border border-dashed border-border bg-muted/40"
                  data-testid="logo-preview"
                >
                  {logoUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element -- yerel önizleme (blob URL)
                    <img
                      src={logoUrl}
                      alt="Logo önizleme"
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <ImageIcon className="size-6 text-muted-foreground" aria-hidden />
                  )}
                </div>
                <div className="space-y-1">
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
                    <Upload className="size-4" aria-hidden />
                    {logoFile ? "Değiştir" : "Logo seç"}
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/webp"
                      className="sr-only"
                      data-testid="logo-input"
                      onChange={(e) => pickLogo(e.target.files?.[0] ?? null)}
                    />
                  </label>
                  {logoFile ? (
                    <button
                      type="button"
                      onClick={() => pickLogo(null)}
                      className="block text-xs text-muted-foreground underline-offset-2 hover:underline"
                    >
                      Kaldır
                    </button>
                  ) : null}
                  <p className="text-xs text-muted-foreground">
                    PNG, JPEG veya WebP · en fazla 2 MB
                  </p>
                  {logoError ? <p className="text-xs text-rose-600">{logoError}</p> : null}
                </div>
              </div>
            </fieldset>

            <DialogFooter className="gap-2 pt-1">
              <Button
                type="button"
                variant="ghost"
                onClick={() => onOpenChange(false)}
                disabled={busy}
              >
                İptal
              </Button>
              <Button
                type="submit"
                disabled={busy || name.trim().length === 0 || !adminReady}
                className="bg-indigo-600 hover:bg-indigo-700 text-white"
              >
                {busy ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <CheckCircle2 className="size-4" aria-hidden />
                )}
                {uploading ? "Logo yükleniyor…" : "Oluştur"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
