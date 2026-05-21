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
  Loader2,
  Plus,
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
import { adminKeys, getAdminInstitutions } from "@/lib/api/admin";
import { useCreateInstitution } from "@/lib/hooks/use-admin-mutations";
import type {
  InstitutionFilterLevel,
  InstitutionListItem,
  InstitutionListResponse,
  InstitutionSort,
} from "@/lib/types/admin";

interface Props {
  initial: InstitutionListResponse;
  sort: InstitutionSort;
  filterLevel: InstitutionFilterLevel | null;
}

const SORT_OPTIONS: { value: InstitutionSort; label: string }[] = [
  { value: "health", label: "Sağlık Durumu" },
  { value: "name", label: "Ada Göre" },
  { value: "created", label: "En Yeniler Üstte" },
];

const FILTER_OPTIONS: {
  value: InstitutionFilterLevel | null;
  label: string;
}[] = [
  { value: null, label: "Hepsi" },
  { value: "unhealthy", label: "Sorunlu Olanlar" },
  { value: "critical", label: "Sadece Acil" },
];

const PLAN_OPTIONS = ["free", "starter", "professional"];

/**
 * Kurumlar listesi — Jinja `institutions_list.html` feature parity.
 *
 * 4 health KPI + sort/filter chip-bar + table (sağlık/ad/plan/öğretmen/öğrenci/
 * aktif%/durum/aksiyonlar) + Yeni Kurum dialog. shadcn flavored.
 */
export function AdminInstitutionsClient({
  initial,
  sort,
  filterLevel,
}: Props) {
  const q = useQuery<InstitutionListResponse>({
    queryKey: adminKeys.institutions(sort, filterLevel),
    queryFn: () => getAdminInstitutions(sort, filterLevel),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const [createOpen, setCreateOpen] = React.useState(false);

  return (
    <div className="space-y-5">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link
            href="/admin"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
            <Building2 className="size-6 text-indigo-700" aria-hidden />
            Kurumlar
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Risk durumu ve son 7 günlük aktivite özetiyle. Ayrılma riski yüksek
            olanlar üstte.
          </p>
        </div>
        <Button
          onClick={() => setCreateOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white"
        >
          <Plus className="size-4" aria-hidden />
          Yeni Kurum
        </Button>
      </header>

      {/* Health KPI rozetleri */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <HealthKpi
          label="Sağlıklı"
          value={data.summary.healthy}
          tone="emerald"
          emoji="🟢"
        />
        <HealthKpi
          label="Gözlem"
          value={data.summary.watch}
          tone="yellow"
          emoji="🟡"
        />
        <HealthKpi
          label="Risk Altında"
          value={data.summary.risk}
          tone="amber"
          emoji="🟠"
        />
        <HealthKpi
          label="Acil İlgi"
          value={data.summary.critical}
          tone="rose"
          emoji="🔴"
        />
      </div>

      {/* Sort + Filter chip-bar */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground font-semibold uppercase tracking-wider">
          Sırala:
        </span>
        {SORT_OPTIONS.map((opt) => {
          const params = new URLSearchParams();
          params.set("sort", opt.value);
          if (filterLevel) params.set("filter_level", filterLevel);
          return (
            <Link
              key={opt.value}
              href={`/admin/institutions?${params.toString()}`}
              className={cn(
                "px-2 py-1 rounded border transition",
                sort === opt.value
                  ? "bg-indigo-50 text-indigo-700 border-indigo-200 font-medium"
                  : "bg-card text-muted-foreground border-border hover:border-foreground/40",
              )}
            >
              {opt.label}
            </Link>
          );
        })}
        <span className="text-muted-foreground/40 mx-2">|</span>
        <span className="text-muted-foreground font-semibold uppercase tracking-wider">
          Filtre:
        </span>
        {FILTER_OPTIONS.map((opt) => {
          const params = new URLSearchParams();
          params.set("sort", sort);
          if (opt.value) params.set("filter_level", opt.value);
          return (
            <Link
              key={opt.label}
              href={`/admin/institutions?${params.toString()}`}
              className={cn(
                "px-2 py-1 rounded border transition",
                filterLevel === opt.value
                  ? "bg-rose-50 text-rose-700 border-rose-200 font-medium"
                  : "bg-card text-muted-foreground border-border hover:border-foreground/40",
              )}
            >
              {opt.label}
            </Link>
          );
        })}
      </div>

      {/* Table veya empty */}
      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            {filterLevel
              ? "Bu filtreye uyan kurum yok."
              : "Henüz kurum yok. Sağ üstten ekle."}
          </CardContent>
        </Card>
      ) : (
        <InstitutionsTable items={data.items} />
      )}

      <CreateInstitutionDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </div>
  );
}

function HealthKpi({
  label,
  value,
  tone,
  emoji,
}: {
  label: string;
  value: number;
  tone: "emerald" | "yellow" | "amber" | "rose";
  emoji: string;
}) {
  const borderClass = {
    emerald: "border-emerald-200",
    yellow: "border-yellow-200",
    amber: "border-amber-200",
    rose: "border-rose-200",
  }[tone];
  const textClass = {
    emerald: "text-emerald-700",
    yellow: "text-yellow-700",
    amber: "text-amber-700",
    rose: "text-rose-700",
  }[tone];
  return (
    <Card className={cn("border", borderClass)}>
      <CardContent className="p-3">
        <div className="text-[11px] text-muted-foreground uppercase tracking-wider inline-flex items-center gap-1">
          <span>{emoji}</span> {label}
        </div>
        <div className={cn("text-2xl font-semibold tabular-nums mt-1", textClass)}>
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function InstitutionsTable({ items }: { items: InstitutionListItem[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Sağlık</th>
              <th className="text-left px-4 py-2 font-medium">Ad</th>
              <th className="text-left px-4 py-2 font-medium">Plan</th>
              <th className="text-right px-4 py-2 font-medium">Öğretmen</th>
              <th className="text-right px-4 py-2 font-medium">Öğrenci</th>
              <th className="text-left px-4 py-2 font-medium">
                Son 7 Gün Aktivite
              </th>
              <th className="text-left px-4 py-2 font-medium">Durum</th>
              <th className="text-right px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((item) => (
              <InstitutionRow key={item.institution.id} item={item} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function InstitutionRow({ item }: { item: InstitutionListItem }) {
  const [open, setOpen] = React.useState(false);
  const inst = item.institution;
  return (
    <tr>
      <td className="px-4 py-3 align-top">
        <div className="inline-flex items-center gap-1.5 flex-wrap">
          <span className="text-base">{item.level_emoji}</span>
          <ScoreBadge score={item.score} color={item.level_color} />
          <span className="text-[11px] text-muted-foreground">
            {item.level_label}
          </span>
        </div>
        {item.indicators.length > 0 && (
          <details
            className="mt-1"
            open={open}
            onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
          >
            <summary className="text-[10px] text-muted-foreground/70 cursor-pointer hover:text-muted-foreground list-none inline-flex items-center gap-0.5">
              <ChevronDown
                className={cn(
                  "size-3 transition-transform",
                  open && "rotate-180",
                )}
                aria-hidden
              />
              {item.indicators.length} sebep
            </summary>
            <ul className="mt-1 text-[11px] text-foreground/80 space-y-0.5 pl-1">
              {item.indicators.map((ind) => (
                <li key={ind.code} title={ind.detail}>
                  <span className="text-rose-600">●</span> {ind.title}
                  <span className="text-muted-foreground/70 ml-1">
                    +{ind.weight} puan
                  </span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </td>
      <td className="px-4 py-3 align-top">
        <Link
          href={`/admin/institutions/${inst.id}`}
          className="font-medium hover:text-indigo-700"
        >
          {inst.name}
        </Link>
        <div className="text-[11px] text-muted-foreground font-mono">
          {inst.slug}
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
          {inst.plan ?? "free"}
        </span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums align-top">
        {item.teacher_count}
      </td>
      <td className="px-4 py-3 text-right tabular-nums align-top">
        {item.student_count}
      </td>
      <td className="px-4 py-3 align-top text-xs">
        {item.teacher_active_pct != null && (
          <ActivityBar
            label="Ö"
            pct={item.teacher_active_pct}
            tone="indigo"
            title="Son 7 günde giriş yapan öğretmen oranı"
          />
        )}
        {item.student_active_pct != null && (
          <ActivityBar
            label="Ö"
            pct={item.student_active_pct}
            tone="emerald"
            title="Son 7 günde giriş yapan öğrenci oranı"
          />
        )}
        {item.teacher_active_pct == null &&
          item.student_active_pct == null && (
            <span className="text-muted-foreground/60">—</span>
          )}
      </td>
      <td className="px-4 py-3 align-top">
        {inst.is_active ? (
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            Aktif
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
            Pasif
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right whitespace-nowrap align-top">
        <Link
          href={`/admin/revenue/institutions/${inst.id}`}
          className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-0.5"
        >
          Ticari 360
          <ArrowRight className="size-3" aria-hidden />
        </Link>
        <Link
          href={`/admin/institutions/${inst.id}`}
          className="ml-3 text-xs text-muted-foreground hover:text-foreground"
        >
          Yönetim
        </Link>
      </td>
    </tr>
  );
}

function ActivityBar({
  label,
  pct,
  tone,
  title,
}: {
  label: string;
  pct: number;
  tone: "indigo" | "emerald";
  title: string;
}) {
  const barColor = tone === "indigo" ? "bg-indigo-500" : "bg-emerald-500";
  return (
    <div className="flex items-center gap-1.5 mb-0.5" title={title}>
      <span className="text-[10px] text-muted-foreground w-4">{label}</span>
      <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
        <div
          className={cn("h-full", barColor)}
          style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
        />
      </div>
      <span className="text-[10px] text-muted-foreground tabular-nums">
        %{pct}
      </span>
    </div>
  );
}

function ScoreBadge({ score, color }: { score: number; color: string }) {
  const map: Record<string, string> = {
    rose: "bg-rose-50 text-rose-700 border-rose-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    yellow: "bg-yellow-50 text-yellow-700 border-yellow-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
  };
  return (
    <span
      className={cn(
        "text-xs px-1.5 py-0.5 rounded font-mono font-semibold border tabular-nums",
        map[color] ?? "bg-slate-50 text-slate-700 border-slate-200",
      )}
    >
      {score}
    </span>
  );
}

function CreateInstitutionDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const mut = useCreateInstitution();
  const [name, setName] = React.useState("");
  const [slug, setSlug] = React.useState("");
  const [contactEmail, setContactEmail] = React.useState("");
  const [plan, setPlan] = React.useState("free");

  function reset() {
    setName("");
    setSlug("");
    setContactEmail("");
    setPlan("free");
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        name: name.trim(),
        slug: slug.trim() || null,
        contact_email: contactEmail.trim() || null,
        plan,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
          reset();
          router.refresh();
        },
      },
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) reset();
        onOpenChange(v);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni Kurum</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
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
            <Label htmlFor="slug">
              Slug{" "}
              <span className="text-muted-foreground text-xs">
                (boş = ad&apos;dan üretilir)
              </span>
            </Label>
            <Input
              id="slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="ankara-koc-akademi"
              className="mt-1 font-mono"
            />
            <p className="text-[11px] text-muted-foreground mt-1">
              URL/handle. Sadece a-z, 0-9, -
            </p>
          </div>
          <div>
            <Label htmlFor="contact_email">İletişim E-posta</Label>
            <Input
              id="contact_email"
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="plan">Plan</Label>
            <select
              id="plan"
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
            >
              {PLAN_OPTIONS.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={mut.isPending}
            >
              İptal
            </Button>
            <Button
              type="submit"
              disabled={mut.isPending || name.trim().length === 0}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <CheckCircle2 className="size-4" aria-hidden />
              )}
              Oluştur
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
