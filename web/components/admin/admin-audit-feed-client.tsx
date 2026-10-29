"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Circle,
  ClipboardList,
  Loader2,
  MousePointerClick,
  Search,
  ShieldAlert,
  UserRound,
  Users,
  VenetianMask,
  X,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminKeys, auditFeedQueryString, getAdminAuditFeed } from "@/lib/api/admin";
import type { AuditCategory, AuditFeedItem, AuditFeedQuery, AuditFeedResponse } from "@/lib/types/admin";

const PERIODS = [
  { days: 1, label: "Son 24 saat" },
  { days: 7, label: "7 gün" },
  { days: 30, label: "30 gün" },
  { days: 90, label: "90 gün" },
];

const CATEGORIES: { key: "all" | AuditCategory; label: string; hint: string }[] = [
  { key: "all", label: "Tümü", hint: "Tüm olaylar" },
  { key: "security", label: "Güvenlik ve giriş", hint: "Giriş/çıkış, başarısız giriş, kilitlenme, şifre, sahte oturum" },
  { key: "coaching", label: "Koçluk", hint: "Deneme yükleme, öğrenci ekleme, program yayınlama, seans, kitap, veli daveti" },
  { key: "student", label: "Öğrenci", hint: "Görev işaretleme, koça talep, yanlış soru arşivi" },
  { key: "admin", label: "Yönetim", hint: "Kullanıcı/kurum oluşturma-silme, rol, ayar, destek talepleri" },
  { key: "commercial", label: "Ticari", hint: "Ödeme, teklif, iletişim talepleri" },
  { key: "system", label: "Sistem", hint: "Otomatik işlemler, vitrin kartları, katalog" },
];

const SEVERITY_STYLE = {
  critical: { icon: ShieldAlert, cls: "bg-rose-700 text-white", row: "border-l-rose-600", label: "Kritik" },
  warn: { icon: AlertTriangle, cls: "bg-amber-600 text-white", row: "border-l-amber-500", label: "Dikkat" },
  info: { icon: Circle, cls: "bg-muted text-muted-foreground", row: "border-l-transparent", label: "Bilgi" },
} as const;

const ROLE_TONE: Record<string, string> = {
  super_admin: "bg-rose-700 text-white",
  institution_admin: "bg-violet-700 text-white",
  teacher: "bg-indigo-700 text-white",
  student: "bg-emerald-700 text-white",
  parent: "bg-sky-700 text-white",
};

function dayHeading(d: Date): string {
  const tr = (x: Date) => x.toLocaleDateString("tr-TR", { timeZone: "Europe/Istanbul" });
  const now = new Date();
  if (tr(d) === tr(now)) return "Bugün";
  if (tr(d) === tr(new Date(now.getTime() - 86_400_000))) return "Dün";
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", weekday: "long", timeZone: "Europe/Istanbul" });
}

function hm(iso: string) {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });
}

export function AdminAuditFeedClient({ initial, initialQuery }: { initial: AuditFeedResponse; initialQuery: AuditFeedQuery }) {
  const router = useRouter();
  const [query, setQuery] = React.useState<AuditFeedQuery>(initialQuery);
  const [searchText, setSearchText] = React.useState(initialQuery.q);
  const q = useQuery<AuditFeedResponse>({
    queryKey: adminKeys.auditFeed(query),
    queryFn: () => getAdminAuditFeed(query),
    initialData: query === initialQuery ? initial : undefined,
    placeholderData: keepPreviousData,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  function update(patch: Partial<AuditFeedQuery>) {
    const next = { ...query, ...patch, page: patch.page ?? 1 };
    setQuery(next);
    router.replace(`/admin/audit?${auditFeedQueryString(next)}`, { scroll: false });
  }

  React.useEffect(() => {
    if (searchText === query.q) return;
    const t = setTimeout(() => update({ q: searchText, actorId: null }), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText]);

  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const groups: { day: string; items: AuditFeedItem[] }[] = [];
  for (const it of data.items) {
    const day = dayHeading(new Date(it.at));
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.items.push(it);
    else groups.push({ day, items: [it] });
  }

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">← Panel</Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <ClipboardList className="size-6 text-indigo-700" aria-hidden />
          Denetim — kim, ne zaman, ne yaptı
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Girişler ve güvenlik olaylarıyla birlikte deneme yükleme, öğrenci ekleme, program yayınlama, görev işaretleme gibi
          işler tek akışta. Bir kişinin adına tıklayınca yalnız onun hareketleri ve gezdiği sayfalar görünür.
        </p>
      </header>

      {/* Özet */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-section="audit:kpi">
        <Kpi tone="rose" label="Kritik olay" value={data.counts.severity.critical}
             hint="Hesap kilitlenmesi, yetkisiz erişim denemesi, kullanıcı/kurum silme"
             onClick={() => update({ severity: "critical" })} />
        <Kpi tone="amber" label="Dikkat gerektiren" value={data.counts.severity.warn}
             hint="Başarısız giriş, sahte oturum, şifre sıfırlama, rol/ayar değişikliği, başarısız ödeme"
             onClick={() => update({ severity: "warn" })} />
        <Kpi tone="slate" label="Başarısız giriş denemesi" value={data.counts.failed_logins}
             hint="Yanlış şifre, kayıtlı olmayan e-posta ve kilitlenmeler" onClick={() => update({ category: "security", severity: "warn" })} />
        <Kpi tone="indigo" label="İşlem yapan kişi" value={data.counts.actors_active}
             hint="Seçili dönemde en az bir olay üreten farklı kişi sayısı" />
      </div>

      {/* Süzgeçler */}
      <div className="space-y-3 rounded-xl border bg-card p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border p-0.5" role="radiogroup" aria-label="Dönem">
            {PERIODS.map((p) => (
              <button key={p.days} type="button" role="radio" aria-checked={query.days === p.days}
                      onClick={() => update({ days: p.days })}
                      className={cn("rounded-md px-3 py-1.5 text-sm",
                        query.days === p.days ? "bg-indigo-700 font-medium text-white" : "text-muted-foreground hover:text-foreground")}>
                {p.label}
              </button>
            ))}
          </div>
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={searchText} onChange={(e) => setSearchText(e.target.value)} className="h-9 pl-8"
                   placeholder="Kişi ara (ad veya e-posta)" aria-label="Kişi ara" />
          </div>
          <select aria-label="Rol" value={query.role} onChange={(e) => update({ role: e.target.value, actorId: null })}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            <option value="">Tüm roller</option>
            <option value="teacher">Koçlar</option>
            <option value="student">Öğrenciler</option>
            <option value="parent">Veliler</option>
            <option value="institution_admin">Kurum yöneticileri</option>
            <option value="super_admin">Süper adminler</option>
          </select>
          <select aria-label="Önem" value={query.severity}
                  onChange={(e) => update({ severity: e.target.value as AuditFeedQuery["severity"] })}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            <option value="all">Tüm önem düzeyleri</option>
            <option value="warn">Dikkat ve kritik</option>
            <option value="critical">Yalnız kritik</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Kategori" data-section="audit:categories">
          {CATEGORIES.map((c) => {
            const active = query.category === c.key;
            const n = c.key === "all" ? data.counts.all : data.counts.categories[c.key] ?? 0;
            return (
              <button key={c.key} type="button" role="radio" aria-checked={active} title={c.hint}
                      onClick={() => update({ category: c.key })}
                      className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                        active ? "border-slate-900 bg-slate-900 text-white"
                               : "bg-card hover:bg-muted")}>
                {c.label}<span className="tabular-nums opacity-70">{n}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Kritik olaylar — her zaman en üstte */}
      {data.recent_critical.length > 0 && query.severity !== "critical" && (
        <section className="overflow-hidden rounded-xl border border-rose-300 bg-card" data-section="audit:critical">
          <div className="flex items-center justify-between gap-2 bg-rose-700 px-4 py-2 text-sm font-semibold text-white">
            <span className="inline-flex items-center gap-2"><ShieldAlert className="size-4" aria-hidden /> Son kritik olaylar</span>
            <button type="button" onClick={() => update({ severity: "critical" })} className="text-xs font-medium underline-offset-2 hover:underline">
              Tümünü gör ({data.counts.severity.critical})
            </button>
          </div>
          <ul className="divide-y">
            {data.recent_critical.map((it) => <FeedRow key={it.key} it={it} onActor={(id) => update({ actorId: id })} />)}
          </ul>
        </section>
      )}

      {/* Kişi odağı / en hareketliler */}
      {data.focus ? (
        <section className="rounded-xl border bg-card p-4" data-section="audit:focus">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              <span className="grid size-10 place-items-center rounded-full bg-indigo-700 text-white"><UserRound className="size-5" aria-hidden /></span>
              <div>
                <div className="font-semibold">
                  <Link href={`/admin/users/${data.focus.id}`} className="hover:underline">{data.focus.name}</Link>
                  <span className={cn("ml-2 rounded px-1.5 py-0.5 text-[11px] font-medium", ROLE_TONE[data.focus.role])}>{data.focus.role_label}</span>
                </div>
                <div className="text-xs text-muted-foreground">
                  {data.focus.email}
                  {data.focus.last_active_at && <> · son görülme {new Date(data.focus.last_active_at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })}</>}
                </div>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => { setSearchText(""); update({ actorId: null, q: "" }); }}>
              <X className="size-4" aria-hidden /> Kişi süzgecini kaldır
            </Button>
          </div>
          <div className="mt-3">
            <div className="mb-1.5 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <MousePointerClick className="size-3.5" aria-hidden /> Gezdiği sayfalar (seçili dönem)
            </div>
            {data.focus.pages.length === 0 ? (
              <p className="text-sm text-muted-foreground">Bu dönemde sayfa ziyareti kaydı yok (3 saniyeden kısa ziyaretler sayılmaz).</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {data.focus.pages.map((p) => (
                  <span key={p.route_key} className="rounded-lg border bg-muted/40 px-2.5 py-1 text-xs"
                        title={p.last_at ? `Son: ${new Date(p.last_at).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" })}` : undefined}>
                    <span className="font-medium">{p.label}</span>
                    <span className="text-muted-foreground"> · {p.visits} kez · {p.minutes.toLocaleString("tr-TR")} dk</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </section>
      ) : data.top_actors.length > 0 && (
        <section className="rounded-xl border bg-card p-3" data-section="audit:top">
          <div className="mb-2 inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <Users className="size-3.5" aria-hidden /> En çok işlem yapanlar — tıkla, yalnız onu izle
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.top_actors.map((a) => (
              <button key={a.id} type="button" onClick={() => update({ actorId: a.id })}
                      className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-sm hover:bg-muted">
                <span className={cn("size-2 rounded-full", ROLE_TONE[a.role]?.split(" ")[0])} aria-hidden />
                {a.name}<span className="text-xs text-muted-foreground">{a.role_label} · {a.count}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Akış */}
      <section className="overflow-hidden rounded-xl border bg-card" data-section="audit:feed" aria-busy={q.isFetching}>
        <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-muted-foreground">
          <span>{data.total} olay</span>
          {q.isFetching && <Loader2 className="size-4 animate-spin" aria-label="Yükleniyor" />}
        </div>
        {data.items.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">Bu süzgeçle eşleşen olay yok.</p>
        ) : groups.map((g) => (
          <div key={g.day}>
            <div className="sticky top-0 z-10 border-y bg-muted/80 px-4 py-1.5 text-xs font-semibold backdrop-blur">{g.day}</div>
            <ul className="divide-y">
              {g.items.map((it) => <FeedRow key={it.key} it={it} onActor={(id) => update({ actorId: id })} />)}
            </ul>
          </div>
        ))}
        {pages > 1 && (
          <div className="flex items-center justify-between border-t px-4 py-2 text-sm">
            <Button variant="outline" size="sm" disabled={data.page <= 1} onClick={() => update({ page: data.page - 1 })}>
              <ChevronLeft className="size-4" aria-hidden /> Daha yeni
            </Button>
            <span className="text-xs text-muted-foreground">Sayfa {data.page} / {pages}</span>
            <Button variant="outline" size="sm" disabled={data.page >= pages} onClick={() => update({ page: data.page + 1 })}>
              Daha eski <ChevronRight className="size-4" aria-hidden />
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}

function Kpi({ tone, label, value, hint, onClick }: {
  tone: "rose" | "amber" | "slate" | "indigo"; label: string; value: number; hint: string; onClick?: () => void;
}) {
  const t = {
    rose: "text-rose-700",
    amber: "text-amber-700",
    slate: "text-foreground",
    indigo: "text-indigo-700",
  }[tone];
  const Comp = onClick ? "button" : "div";
  return (
    <Comp type={onClick ? "button" : undefined} onClick={onClick} title={hint}
          className={cn("rounded-xl border bg-card p-3 text-left", onClick && "hover:bg-muted/50")}>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-2xl font-semibold tabular-nums", t)}>{value}</div>
      <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{hint}</div>
    </Comp>
  );
}

function FeedRow({ it, onActor }: { it: AuditFeedItem; onActor: (id: number) => void }) {
  const [open, setOpen] = React.useState(false);
  const sev = SEVERITY_STYLE[it.severity];
  const Icon = sev.icon;
  return (
    <li className={cn("border-l-4 px-4 py-2.5", sev.row)} data-severity={it.severity}>
      <div className="flex items-start gap-3">
        <span className="w-11 shrink-0 pt-0.5 text-xs tabular-nums text-muted-foreground">{hm(it.at)}</span>
        <span className={cn("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full", sev.cls)} title={sev.label}>
          <Icon className={cn(it.severity === "info" ? "size-2" : "size-3")} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="break-words text-sm">
            {it.actor ? (
              <>
                <button type="button" onClick={() => onActor(it.actor!.id)} className="font-semibold hover:underline">{it.actor.name}</button>
                <span className={cn("ml-1.5 rounded px-1 py-0.5 align-middle text-[10px] font-medium", ROLE_TONE[it.actor.role])}>{it.actor.role_label}</span>
              </>
            ) : (
              <span className="font-semibold">{it.actor_text ?? "Sistem"}</span>
            )}
            <span> · {it.title}</span>
            {it.target_name && (
              <>
                <span className="text-muted-foreground"> → </span>
                {it.target_url ? (
                  <Link href={it.target_url} className="text-indigo-700 hover:underline">{it.target_name}</Link>
                ) : <span>{it.target_name}</span>}
                {it.target_role_label && <span className="text-xs text-muted-foreground"> ({it.target_role_label})</span>}
                {it.target_extra && <span className="text-muted-foreground"> {it.target_extra}</span>}
              </>
            )}
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
            <span>{it.category_label}</span>
            {it.device && <span>· {it.device}</span>}
            {it.ip && <span className="font-mono">· {it.ip}</span>}
            {it.via_admin && (
              <span className="inline-flex items-center gap-1 rounded bg-violet-700 px-1.5 py-0.5 font-medium text-white">
                <VenetianMask className="size-3" aria-hidden /> sahte oturumda: {it.via_admin.name}
              </span>
            )}
            {it.details.length > 0 && (
              <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
                      className="inline-flex items-center gap-0.5 hover:text-foreground">
                <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} aria-hidden />
                Ayrıntılar
              </button>
            )}
          </div>
          {open && (
            <dl className="mt-2 grid gap-x-4 gap-y-1 rounded-lg border bg-muted/30 p-2.5 text-xs sm:grid-cols-[max-content_1fr]">
              {it.details.map((d, i) => (
                <React.Fragment key={i}>
                  <dt className="text-muted-foreground">{d.label}</dt>
                  <dd className="break-words font-medium">{d.value}</dd>
                </React.Fragment>
              ))}
            </dl>
          )}
        </div>
      </div>
    </li>
  );
}
