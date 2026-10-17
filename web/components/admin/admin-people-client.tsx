"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  GraduationCap,
  KeyRound,
  Loader2,
  Lock,
  MessageSquare,
  MoreHorizontal,
  Plus,
  Power,
  Search,
  ShieldCheck,
  UserCog,
  Users,
  UserRound,
  VenetianMask,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { api, type MutationResponse } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { WaSendDialog } from "@/components/messaging/wa-send-dialog";
import { adminKeys, getAdminPeople, peopleQueryString } from "@/lib/api/admin";
import { useImpersonateUser, useResetUserPassword } from "@/lib/hooks/use-admin-mutations";
import type {
  AdminUserCreateResult,
  PeopleActivity,
  PeopleQuery,
  PeopleResponse,
  PeopleRole,
  PeopleSort,
  PersonRow,
} from "@/lib/types/admin";
import { CreateUserDialog, DemoEcosystemDialog, TempPasswordDialog } from "./admin-users-client";

const ROLE_TABS: { key: PeopleRole; label: string; icon: React.ElementType }[] = [
  { key: "teacher", label: "Koçlar", icon: UserCog },
  { key: "student", label: "Öğrenciler", icon: GraduationCap },
  { key: "parent", label: "Veliler", icon: UserRound },
  { key: "institution_admin", label: "Kurum yöneticileri", icon: Users },
  { key: "super_admin", label: "Süper admin", icon: ShieldCheck },
];

const ACTIVITY: { key: PeopleActivity; label: string; hint: string; dot: string }[] = [
  { key: "all", label: "Tümü", hint: "Bu roldeki herkes", dot: "bg-slate-400" },
  { key: "today", label: "Bugün aktif", hint: "Bugün (TR saati) sistemde görüldü", dot: "bg-emerald-500" },
  { key: "week", label: "Bu hafta", hint: "Son 7 günde görüldü, bugün değil", dot: "bg-sky-500" },
  { key: "silent", label: "7+ gün sessiz", hint: "Son görülme 7 günden eski", dot: "bg-amber-500" },
  { key: "never", label: "Hiç girmedi", hint: "Hesap açıldı, hiç giriş yapılmadı", dot: "bg-rose-500" },
];

const PLAN_TONE: Record<string, string> = {
  trial: "bg-sky-700 text-white",
  active: "bg-emerald-700 text-white",
  past_due: "bg-rose-700 text-white",
  payment_pending: "bg-amber-700 text-white",
  free: "bg-slate-600 text-white",
  institution: "bg-violet-700 text-white",
};

function activityOf(iso: string | null): { key: PeopleActivity; text: string } {
  if (!iso) return { key: "never", text: "hiç girmedi" };
  const d = new Date(iso);
  const now = new Date();
  const sameDay = d.toLocaleDateString("tr-TR", { timeZone: "Europe/Istanbul" })
    === now.toLocaleDateString("tr-TR", { timeZone: "Europe/Istanbul" });
  const hm = d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" });
  if (sameDay) return { key: "today", text: `bugün ${hm}` };
  const days = Math.max(1, Math.floor((now.getTime() - d.getTime()) / 86_400_000));
  if (days < 7) return { key: "week", text: days === 1 ? `dün ${hm}` : `${days} gün önce` };
  return { key: "silent", text: `${days} gün önce` };
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toLocaleUpperCase("tr")).join("");
}

export function AdminPeopleClient({ initial, initialQuery }: { initial: PeopleResponse; initialQuery: PeopleQuery }) {
  const router = useRouter();
  const pathname = usePathname();
  const [query, setQuery] = React.useState<PeopleQuery>(initialQuery);
  const [searchText, setSearchText] = React.useState(initialQuery.q);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [demoOpen, setDemoOpen] = React.useState(false);
  const [tempPw, setTempPw] = React.useState<AdminUserCreateResult | { user: { full_name: string } | null; temp_password: string } | null>(null);

  const q = useQuery<PeopleResponse>({
    queryKey: adminKeys.people(query),
    queryFn: () => getAdminPeople(query),
    initialData: query === initialQuery ? initial : undefined,
    placeholderData: keepPreviousData,
    staleTime: 20_000,
  });
  const data = q.data ?? initial;

  function update(patch: Partial<PeopleQuery>) {
    const next = { ...query, ...patch, page: patch.page ?? 1 };
    setQuery(next);
    router.replace(`${pathname}?${peopleQueryString(next)}`, { scroll: false });
  }

  // Arama: yazmayı bitirince (400 ms) uygula
  React.useEffect(() => {
    if (searchText === query.q) return;
    const t = setTimeout(() => update({ q: searchText }), 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText]);

  const from = data.total === 0 ? 0 : (data.page - 1) * data.page_size + 1;
  const to = Math.min(data.total, data.page * data.page_size);
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/admin" className="text-sm text-muted-foreground hover:text-foreground">← Panel</Link>
          <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Users className="size-6 text-indigo-700 dark:text-indigo-300" aria-hidden />
            Kullanıcılar
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Rol seç, aktiviteye göre süz. Liste varsayılan olarak en son görülen kişiden başlar.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => setDemoOpen(true)}
                  className="border-amber-300 text-amber-900 hover:bg-amber-50 dark:text-amber-200 dark:hover:bg-amber-500/25">
            <FlaskConical className="size-4" aria-hidden /> Demo Aç
          </Button>
          <Button onClick={() => setCreateOpen(true)} className="bg-indigo-700 text-white hover:bg-indigo-800">
            <Plus className="size-4" aria-hidden /> Yeni Kullanıcı
          </Button>
        </div>
      </header>

      {/* Rol sekmeleri */}
      <nav aria-label="Rol" className="flex flex-wrap gap-1 rounded-xl border bg-card p-1" data-section="people:roles">
        {ROLE_TABS.map((t) => {
          const Icon = t.icon;
          const active = query.role === t.key;
          return (
            <button key={t.key} type="button" onClick={() => update({ role: t.key, activity: "all" })}
                    aria-pressed={active}
                    className={cn(
                      "inline-flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors sm:flex-none",
                      active ? "bg-indigo-700 text-white shadow-sm" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}>
              <Icon className="size-4" aria-hidden />
              {t.label}
              <span className={cn("rounded-full px-1.5 text-xs tabular-nums", active ? "bg-white/20" : "bg-muted")}>
                {data.role_counts[t.key] ?? 0}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Araçlar + aktivite çipleri */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
            <Input value={searchText} onChange={(e) => setSearchText(e.target.value)}
                   placeholder="Ad veya e-posta ara" aria-label="Kişi ara" className="h-9 pl-8" />
          </div>
          <select aria-label="Kurum" value={query.institutionId ?? ""}
                  onChange={(e) => update({ institutionId: e.target.value ? Number(e.target.value) : null })}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            <option value="">Tüm kurumlar</option>
            {data.institutions.map((i) => <option key={i.id} value={i.id}>{i.name}</option>)}
          </select>
          <select aria-label="Sıralama" value={query.sort}
                  onChange={(e) => update({ sort: e.target.value as PeopleSort })}
                  className="h-9 rounded-md border border-input bg-card px-2 text-sm">
            <option value="activity">Son aktivite</option>
            <option value="name">Ada göre</option>
            <option value="created">Yeni kayıt</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Aktivite" data-section="people:activity">
          {ACTIVITY.map((a) => {
            const active = query.activity === a.key;
            return (
              <button key={a.key} type="button" role="radio" aria-checked={active} title={a.hint}
                      onClick={() => update({ activity: a.key })}
                      className={cn(
                        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium",
                        active ? "border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-900"
                               : "bg-card text-foreground hover:bg-muted",
                      )}>
                <span className={cn("size-2 rounded-full", a.dot)} aria-hidden />
                {a.label}
                <span className="tabular-nums opacity-70">{data.activity_counts[a.key] ?? 0}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Liste */}
      <section className="overflow-hidden rounded-xl border bg-card" data-section="people:list" aria-busy={q.isFetching}>
        <div className="flex items-center justify-between border-b px-4 py-2 text-xs text-muted-foreground">
          <span>{data.total === 0 ? "Kayıt yok" : `${from}–${to} / ${data.total}`}</span>
          {q.isFetching && <Loader2 className="size-4 animate-spin" aria-label="Yükleniyor" />}
        </div>
        {data.items.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-muted-foreground">Bu süzgeçle eşleşen kişi yok.</p>
        ) : (
          <ul className="divide-y">
            {data.items.map((p) => <PersonItem key={p.id} p={p} onTempPw={setTempPw} />)}
          </ul>
        )}
        {pages > 1 && (
          <div className="flex items-center justify-between border-t px-4 py-2 text-sm">
            <Button variant="outline" size="sm" disabled={data.page <= 1} onClick={() => update({ page: data.page - 1 })}>
              <ChevronLeft className="size-4" aria-hidden /> Önceki
            </Button>
            <span className="text-xs text-muted-foreground">Sayfa {data.page} / {pages}</span>
            <Button variant="outline" size="sm" disabled={data.page >= pages} onClick={() => update({ page: data.page + 1 })}>
              Sonraki <ChevronRight className="size-4" aria-hidden />
            </Button>
          </div>
        )}
      </section>

      <DemoEcosystemDialog open={demoOpen} onClose={() => setDemoOpen(false)} />
      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} institutions={data.institutions}
                        onCreated={(r) => { setCreateOpen(false); setTempPw(r); }} />
      <TempPasswordDialog result={tempPw} onClose={() => { setTempPw(null); void q.refetch(); }} />
    </div>
  );
}

const ACT_RING: Record<PeopleActivity, string> = {
  all: "ring-slate-300", today: "ring-emerald-500", week: "ring-sky-500", silent: "ring-amber-500", never: "ring-rose-500",
};

function PersonItem({ p, onTempPw }: {
  p: PersonRow;
  onTempPw: (r: { user: { full_name: string } | null; temp_password: string }) => void;
}) {
  const act = activityOf(p.last_active_at);
  return (
    <li className={cn("grid gap-x-4 gap-y-2 px-4 py-3 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1.6fr)_auto]", !p.is_active && "bg-muted/40")}
        data-person-id={p.id}>
      {/* Kim */}
      <div className="flex min-w-0 items-start gap-3">
        <span className={cn("mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold ring-2", ACT_RING[act.key])}
              aria-hidden>{initials(p.full_name)}</span>
        <div className="min-w-0">
          <Link href={`/admin/users/${p.id}`} className="break-words font-medium hover:underline">{p.full_name}</Link>
          <div className="break-all text-xs text-muted-foreground">{p.email}</div>
          <div className="mt-1 flex flex-wrap gap-1">
            {!p.is_active && <Badge className="bg-slate-600 text-white">pasif</Badge>}
            {p.locked_now && <Badge className="bg-rose-700 text-white"><Lock className="size-3" aria-hidden /> kilitli</Badge>}
            {p.must_change_password && <Badge className="bg-amber-700 text-white">geçici şifrede</Badge>}
            {p.is_demo && <Badge className="bg-amber-200 text-amber-950">Demo{p.demo_label ? ` · ${p.demo_label}` : ""}</Badge>}
            {p.program_mode === "havuz" && <Badge className="bg-cyan-700 text-white">havuz</Badge>}
          </div>
        </div>
      </div>

      {/* Role özgü bağlam */}
      <div className="min-w-0 text-sm">
        <RoleContext p={p} />
      </div>

      {/* Aktivite + işlemler */}
      <div className="flex items-center justify-between gap-3 sm:justify-end">
        <span className="whitespace-nowrap text-xs text-muted-foreground" title={p.last_active_at ? new Date(p.last_active_at).toLocaleString("tr-TR") : undefined}>
          {act.text}
        </span>
        <RowActions p={p} onTempPw={onTempPw} />
      </div>
    </li>
  );
}

function Badge({ className, children }: { className: string; children: React.ReactNode }) {
  return <span className={cn("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium", className)}>{children}</span>;
}

function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-muted-foreground">{children}</span>;
}

function RoleContext({ p }: { p: PersonRow }) {
  if (p.role === "student") {
    const pct = p.gorev_7d_total ? Math.round(((p.gorev_7d_done ?? 0) / p.gorev_7d_total) * 100) : null;
    return (
      <div className="space-y-1">
        <div className="break-words">
          {p.institution_name ?? <Muted>Bağımsız</Muted>}
          {p.coach && <> · koç <Link href={`/admin/users/${p.coach.id}`} className="text-indigo-700 hover:underline dark:text-indigo-300">{p.coach.name}</Link></>}
          {p.grade_label && p.grade_label !== "—" && <Muted> · {p.grade_label}</Muted>}
        </div>
        <div className="flex items-center gap-2 text-xs" title="Son 7 gün görev tamamlama (bugünün açık görevleri sayılmaz)">
          {pct == null ? <Muted>son 7 gün: program yok</Muted> : (
            <>
              <span className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                <span className={cn("block h-full", pct >= 70 ? "bg-emerald-600" : pct >= 40 ? "bg-amber-500" : "bg-rose-600")} style={{ width: `${pct}%` }} />
              </span>
              <span className="tabular-nums">son 7 gün %{pct} · {p.gorev_7d_done}/{p.gorev_7d_total} görev</span>
            </>
          )}
        </div>
      </div>
    );
  }
  if (p.role === "teacher") {
    return (
      <div className="space-y-1">
        <div className="break-words">
          {p.institution_name ?? <Muted>Bağımsız koç</Muted>}
          <Muted> · {p.student_count ?? 0} aktif öğrenci</Muted>
        </div>
        {p.plan_state && p.plan_state !== "institution" && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <Badge className={PLAN_TONE[p.plan_state] ?? "bg-slate-600 text-white"}>{p.plan_label ?? "—"}</Badge>
            {p.plan_note && <Muted>{p.plan_note}</Muted>}
          </div>
        )}
      </div>
    );
  }
  if (p.role === "parent") {
    if (!p.children.length) return <span className="text-amber-800 dark:text-amber-300">Çocuğa bağlı değil</span>;
    return (
      <ul className="space-y-0.5">
        {p.children.map((c) => (
          <li key={c.id} className="break-words">
            <Muted>Velisi: </Muted>
            <Link href={`/admin/users/${c.id}`} className="text-indigo-700 hover:underline dark:text-indigo-300">{c.name}</Link>
            {c.grade_label && c.grade_label !== "—" && <Muted> ({c.grade_label})</Muted>}
            <Muted> · {c.institution_name ?? "bağımsız"}{c.coach_name ? ` · koç ${c.coach_name}` : ""}</Muted>
          </li>
        ))}
      </ul>
    );
  }
  if (p.role === "institution_admin") return <div className="break-words">{p.institution_name ?? <Muted>Kurum yok</Muted>}</div>;
  return <Muted>Platform yöneticisi</Muted>;
}

function RowActions({ p, onTempPw }: {
  p: PersonRow;
  onTempPw: (r: { user: { full_name: string } | null; temp_password: string }) => void;
}) {
  const qc = useQueryClient();
  const [impOpen, setImpOpen] = React.useState(false);
  const [resetOpen, setResetOpen] = React.useState(false);
  const [activeOpen, setActiveOpen] = React.useState(false);
  const [waOpen, setWaOpen] = React.useState(false);
  const reset = useResetUserPassword(p.id);
  const setActive = useMutation<MutationResponse<{ is_active: boolean; message: string }>, Error, boolean>({
    mutationFn: (v) => api(`/api/v2/admin/users/${p.id}/set-active`, { method: "POST", body: JSON.stringify({ is_active: v }) }),
    onSuccess: (res) => { applyInvalidate(qc, res.invalidate); toast.success(res.data.message); setActiveOpen(false); },
    onError: () => toast.error("İşlem yapılamadı"),
  });
  const isAdmin = p.role === "super_admin";

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 w-8 p-0" aria-label={`${p.full_name} işlemleri`}>
            <MoreHorizontal className="size-4" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem asChild><Link href={`/admin/users/${p.id}`}><UserRound className="size-4" aria-hidden /> Detay</Link></DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled={isAdmin || !p.is_active} onSelect={() => setImpOpen(true)}>
            <VenetianMask className="size-4" aria-hidden /> Sahte oturum aç
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setResetOpen(true)}>
            <KeyRound className="size-4" aria-hidden /> {p.locked_now ? "Şifre sıfırla + kilidi aç" : "Şifre sıfırla"}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setWaOpen(true)}>
            <MessageSquare className="size-4" aria-hidden /> WhatsApp gönder
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled={isAdmin} onSelect={() => setActiveOpen(true)}
                            className={p.is_active ? "text-rose-700 dark:text-rose-300" : undefined}>
            <Power className="size-4" aria-hidden /> {p.is_active ? "Pasife al" : "Aktif et"}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ImpersonateDialog open={impOpen} onOpenChange={setImpOpen} p={p} />

      <Dialog open={resetOpen} onOpenChange={setResetOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Şifre sıfırlansın mı?</DialogTitle>
            <DialogDescription>
              {p.full_name} için tek seferlik geçici şifre üretilir; ilk girişte değiştirmesi istenir.
              {p.locked_now ? " Hesap kilidi de açılır." : ""} Diğer cihazlardaki oturumları kapanır.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetOpen(false)}>Vazgeç</Button>
            <Button className="bg-indigo-700 text-white hover:bg-indigo-800" disabled={reset.isPending}
                    onClick={() => reset.mutate(undefined, {
                      onSuccess: (res) => {
                        setResetOpen(false);
                        if (res.data.temp_password) onTempPw({ user: { full_name: p.full_name }, temp_password: res.data.temp_password });
                      },
                    })}>
              {reset.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />} Sıfırla
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={activeOpen} onOpenChange={setActiveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{p.is_active ? "Hesap pasife alınsın mı?" : "Hesap aktif edilsin mi?"}</DialogTitle>
            <DialogDescription>
              {p.is_active
                ? `${p.full_name} giriş yapamaz; verisi silinmez, istediğinde yeniden aktif edebilirsin.`
                : `${p.full_name} yeniden giriş yapabilir.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActiveOpen(false)}>Vazgeç</Button>
            <Button disabled={setActive.isPending} onClick={() => setActive.mutate(!p.is_active)}
                    className={p.is_active ? "bg-rose-700 text-white hover:bg-rose-800" : "bg-emerald-700 text-white hover:bg-emerald-800"}>
              {setActive.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />}
              {p.is_active ? "Pasife al" : "Aktif et"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <WaSendDialog open={waOpen} onOpenChange={setWaOpen} targetUserId={p.id} targetNameFallback={p.full_name}
                    defaultCategory="admin_yonetici" />
    </>
  );
}

function ImpersonateDialog({ open, onOpenChange, p }: { open: boolean; onOpenChange: (v: boolean) => void; p: PersonRow }) {
  const mut = useImpersonateUser(p.id);
  const [reason, setReason] = React.useState("");
  const ok = reason.trim().length >= 10;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Sahte oturum: {p.full_name}</DialogTitle>
          <DialogDescription>
            Bu kişinin paneline onun gözünden girersin (30 dakika). Gerekçe denetim kaydına yazılır; üstteki
            mor banttan “Admin&apos;e dön” ile çıkarsın.
          </DialogDescription>
        </DialogHeader>
        <label htmlFor={`imp-${p.id}`} className="text-sm font-medium">Gerekçe (en az 10 karakter)</label>
        <textarea id={`imp-${p.id}`} value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
                  className="w-full rounded-md border border-input bg-card px-3 py-2 text-sm"
                  placeholder="Örn. koçun bildirdiği program görünmeme sorununu yerinde incelemek" />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Vazgeç</Button>
          <Button disabled={!ok || mut.isPending} className="bg-violet-700 text-white hover:bg-violet-800"
                  onClick={() => mut.mutate({ reason: reason.trim() }, {
                    onSuccess: (data) => { window.location.href = data.redirect_url; },
                  })}>
            {mut.isPending && <Loader2 className="size-4 animate-spin" aria-hidden />} Oturumu aç
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
