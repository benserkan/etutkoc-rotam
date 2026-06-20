"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  CheckCircle2,
  Clipboard,
  FlaskConical,
  Filter,
  Loader2,
  Lock,
  Plus,
  Users,
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
import { adminKeys, getAdminUsers } from "@/lib/api/admin";
import { useCreateAdminUser } from "@/lib/hooks/use-admin-mutations";
import type {
  AdminRole,
  AdminUserCreateResult,
  AdminUserListItem,
  AdminUserListResponse,
  InstitutionRefBrief,
} from "@/lib/types/admin";

interface Props {
  initial: AdminUserListResponse;
  initialRole: string | null;
  initialInstitutionId: number | null;
  initialQ: string | null;
}

const ROLE_OPTIONS: { value: AdminRole; label: string }[] = [
  { value: "super_admin", label: "Süper Admin" },
  { value: "institution_admin", label: "Kurum Yöneticisi" },
  { value: "teacher", label: "Öğretmen" },
  { value: "student", label: "Öğrenci" },
  { value: "parent", label: "Veli" },
];

const ROLE_COLOR: Record<AdminRole, string> = {
  super_admin: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  institution_admin: "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
  teacher: "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/30 dark:text-indigo-200",
  student: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  parent: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
};

/**
 * Kullanıcılar listesi — Jinja `users_list.html` feature parity.
 *
 * Filter form (URL-based) + 500-cap table + Yeni Kullanıcı Dialog.
 * Yeni kullanıcı oluşunca tek seferlik geçici şifre dialog'da "Kopyala" ile gösterilir.
 */
export function AdminUsersClient({
  initial,
  initialRole,
  initialInstitutionId,
  initialQ,
}: Props) {
  const router = useRouter();
  const q = useQuery<AdminUserListResponse>({
    queryKey: adminKeys.users(initialRole, initialInstitutionId, initialQ),
    queryFn: () =>
      getAdminUsers(initialRole, initialInstitutionId, initialQ),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const [createOpen, setCreateOpen] = React.useState(false);
  const [demoOpen, setDemoOpen] = React.useState(false);
  const [tempPwResult, setTempPwResult] =
    React.useState<AdminUserCreateResult | null>(null);

  // Filter form state
  const [searchQ, setSearchQ] = React.useState(initialQ ?? "");
  const [filterRole, setFilterRole] = React.useState(initialRole ?? "");
  const [filterInst, setFilterInst] = React.useState(
    initialInstitutionId != null ? String(initialInstitutionId) : "",
  );

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (searchQ.trim()) params.set("q", searchQ.trim());
    if (filterRole) params.set("role", filterRole);
    if (filterInst) params.set("institution_id", filterInst);
    router.push(`/admin/users${params.toString() ? "?" + params.toString() : ""}`);
  }

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
            <Users className="size-6 text-indigo-700" aria-hidden />
            Kullanıcılar
          </h1>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            onClick={() => setDemoOpen(true)}
            className="border-amber-300 text-amber-900 hover:bg-amber-50"
            title="Tanıtım için hazır kurum/koç/öğrenci/veli ekosistemi oluştur"
          >
            <FlaskConical className="size-4" aria-hidden />
            Demo Aç
          </Button>
          <Button
            onClick={() => setCreateOpen(true)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            <Plus className="size-4" aria-hidden />
            Yeni Kullanıcı
          </Button>
        </div>
      </header>
      <DemoEcosystemDialog open={demoOpen} onClose={() => setDemoOpen(false)} />

      {/* Filter form */}
      <Card>
        <CardContent className="p-3">
          <form
            onSubmit={applyFilters}
            className="flex items-end gap-3 flex-wrap"
          >
            <div className="flex-1 min-w-[200px]">
              <Label htmlFor="q" className="text-[11px] uppercase tracking-wide">
                Arama
              </Label>
              <Input
                id="q"
                value={searchQ}
                onChange={(e) => setSearchQ(e.target.value)}
                placeholder="ad veya e-posta"
                className="mt-1"
              />
            </div>
            <div>
              <Label
                htmlFor="role"
                className="text-[11px] uppercase tracking-wide"
              >
                Rol
              </Label>
              <select
                id="role"
                value={filterRole}
                onChange={(e) => setFilterRole(e.target.value)}
                className="mt-1 px-3 py-2 border border-input rounded text-sm bg-card"
              >
                <option value="">— Tümü —</option>
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label
                htmlFor="inst"
                className="text-[11px] uppercase tracking-wide"
              >
                Kurum
              </Label>
              <select
                id="inst"
                value={filterInst}
                onChange={(e) => setFilterInst(e.target.value)}
                className="mt-1 px-3 py-2 border border-input rounded text-sm bg-card"
              >
                <option value="">— Tümü —</option>
                {data.institutions.map((i) => (
                  <option key={i.id} value={String(i.id)}>
                    {i.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <Button type="submit" className="bg-slate-700 hover:bg-slate-800 text-white">
                <Filter className="size-4" aria-hidden />
                Filtrele
              </Button>
              <Link
                href="/admin/users"
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Temizle
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Table */}
      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Filtreyle eşleşen kullanıcı yok.
          </CardContent>
        </Card>
      ) : (
        <UsersTable items={data.items} truncated={data.truncated} />
      )}

      <CreateUserDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        institutions={data.institutions}
        onCreated={(result) => {
          setCreateOpen(false);
          setTempPwResult(result);
        }}
      />

      <TempPasswordDialog
        result={tempPwResult}
        onClose={() => {
          setTempPwResult(null);
          router.refresh();
        }}
      />
    </div>
  );
}

function UsersTable({
  items,
  truncated,
}: {
  items: AdminUserListItem[];
  truncated: boolean;
}) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Ad</th>
              <th className="text-left px-4 py-2 font-medium">E-posta</th>
              <th className="text-left px-4 py-2 font-medium">Rol</th>
              <th className="text-left px-4 py-2 font-medium">Kurum</th>
              <th className="text-left px-4 py-2 font-medium">Son Giriş</th>
              <th className="text-left px-4 py-2 font-medium">Durum</th>
              <th className="text-right px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((u) => (
              <UserRow key={u.id} user={u} />
            ))}
          </tbody>
        </table>
      </div>
      {truncated && (
        <div className="px-4 py-2 text-xs text-muted-foreground italic border-t border-border">
          İlk 500 kullanıcı gösteriliyor — daha dar filtre uygula.
        </div>
      )}
    </Card>
  );
}

function UserRow({ user }: { user: AdminUserListItem }) {
  return (
    <tr className={cn(!user.is_active && "bg-muted/30 text-muted-foreground")}>
      <td className="px-4 py-2 font-medium">
        <Link
          href={`/admin/users/${user.id}`}
          className="hover:text-indigo-700"
        >
          {user.full_name}
        </Link>
        {user.is_demo ? (
          <span
            className="ml-2 inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-900"
            title={user.demo_label ? `Demo: ${user.demo_label}` : "Demo hesap"}
          >
            <FlaskConical className="size-2.5" aria-hidden />
            Demo{user.demo_label ? ` · ${user.demo_label}` : ""}
          </span>
        ) : null}
      </td>
      <td className="px-4 py-2 font-mono text-xs">{user.email}</td>
      <td className="px-4 py-2">
        <span
          className={cn(
            "text-[10px] px-1.5 py-0.5 rounded border",
            ROLE_COLOR[user.role],
          )}
        >
          {user.role_label}
        </span>
      </td>
      <td className="px-4 py-2 text-muted-foreground">
        {user.institution ? (
          user.institution.name
        ) : (
          <span className="italic">bağımsız</span>
        )}
      </td>
      <td className="px-4 py-2 text-muted-foreground text-xs tabular-nums">
        {user.last_login_at ? formatDateTime(user.last_login_at) : "—"}
      </td>
      <td className="px-4 py-2">
        {user.locked_until ? (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 inline-flex items-center gap-0.5">
            <Lock className="size-2.5" aria-hidden />
            kilitli
          </span>
        ) : user.is_active ? (
          <span className="text-emerald-700 text-[10px]">●</span>
        ) : (
          <span className="text-muted-foreground/70 text-[10px]">pasif</span>
        )}
      </td>
      <td className="px-4 py-2 text-right">
        <Link
          href={`/admin/users/${user.id}`}
          className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-0.5"
        >
          Detay
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      </td>
    </tr>
  );
}

// ============================================================================
// Create dialog
// ============================================================================

function CreateUserDialog({
  open,
  onOpenChange,
  institutions,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  institutions: InstitutionRefBrief[];
  onCreated: (result: AdminUserCreateResult) => void;
}) {
  const mut = useCreateAdminUser();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [role, setRole] = React.useState<AdminRole>("teacher");
  const [instId, setInstId] = React.useState("");

  function reset() {
    setFullName("");
    setEmail("");
    setRole("teacher");
    setInstId("");
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        full_name: fullName.trim(),
        email: email.trim(),
        role,
        institution_id: instId ? Number(instId) : null,
      },
      {
        onSuccess: (res) => {
          reset();
          onCreated(res.data);
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
          <DialogTitle>Yeni Kullanıcı</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label htmlFor="cu-name">
              Ad Soyad <span className="text-rose-500">*</span>
            </Label>
            <Input
              id="cu-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              autoFocus
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="cu-email">
              E-posta <span className="text-rose-500">*</span>
            </Label>
            <Input
              id="cu-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-1"
            />
          </div>
          <div>
            <Label htmlFor="cu-role">
              Rol <span className="text-rose-500">*</span>
            </Label>
            <select
              id="cu-role"
              value={role}
              onChange={(e) => setRole(e.target.value as AdminRole)}
              className="mt-1 w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
            >
              {ROLE_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="cu-inst">
              Kurum{" "}
              <span className="text-muted-foreground text-xs">
                (kurum yöneticisi için zorunlu)
              </span>
            </Label>
            <select
              id="cu-inst"
              value={instId}
              onChange={(e) => setInstId(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
            >
              <option value="">— Bağımsız —</option>
              {institutions.map((i) => (
                <option key={i.id} value={String(i.id)}>
                  {i.name}
                </option>
              ))}
            </select>
          </div>
          <div className="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-xs text-amber-900">
            🔐 <strong>Şifre güvenliği:</strong> Sistem rol-bazlı güçlü geçici
            şifre üretir. Kullanıcı <strong>ilk girişte kendi şifresini
            belirlemek zorundadır</strong>.
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
              disabled={
                mut.isPending ||
                fullName.trim().length === 0 ||
                email.trim().length === 0
              }
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

// ============================================================================
// Temp password dialog (re-usable for create & reset)
// ============================================================================

export function TempPasswordDialog({
  result,
  onClose,
}: {
  result: AdminUserCreateResult | { user: { full_name: string } | null; temp_password: string } | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = React.useState(false);
  if (!result) return null;
  const fullName =
    "user" in result && result.user ? result.user.full_name : "Kullanıcı";
  const pwd = result.temp_password;

  function copy() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(pwd).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  }

  return (
    <Dialog open={true} onOpenChange={(v) => !v && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Geçici Şifre Üretildi</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          <strong>{fullName}</strong> için tek seferlik geçici şifre:
        </p>
        <div className="rounded-md border border-amber-300 bg-amber-50 p-4 my-2 flex items-center justify-between gap-3">
          <code className="font-mono text-lg font-semibold text-amber-900 tracking-wider break-all">
            {pwd}
          </code>
          <Button
            size="sm"
            variant="outline"
            onClick={copy}
            className="border-amber-300 text-amber-800 hover:bg-amber-100"
          >
            {copied ? (
              <>
                <CheckCircle2 className="size-3.5" aria-hidden />
                Kopyalandı
              </>
            ) : (
              <>
                <Clipboard className="size-3.5" aria-hidden />
                Kopyala
              </>
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          ⚠️ Bu şifre <strong>bu pencereyi kapattıktan sonra bir daha
          gösterilmez</strong>. Kullanıcıya güvenli kanaldan iletin. Kullanıcı
          ilk girişte kendi şifresini belirleyecek.
        </p>
        <DialogFooter className="pt-2">
          <Button onClick={onClose}>Tamam</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}

// =============================================================================
// M5 — Demo Ekosistem Dialog
// =============================================================================

import type { DemoKind, DemoSeedResult } from "@/lib/types/admin";
import { useCreateDemoEcosystem } from "@/lib/hooks/use-admin-mutations";

const DEMO_KINDS: Array<{
  key: DemoKind;
  label: string;
  description: string;
  members: string;
}> = [
  {
    key: "institution",
    label: "Kurum (tam ekosistem)",
    description: "Etüt/dershane satışı için ideal — kurum yöneticisi + koç + öğrenci + veli.",
    members: "1 yönetici + 1 koç + 1 öğr + 1 veli",
  },
  {
    key: "solo_coach",
    label: "Bağımsız Koç",
    description: "Solo paket tanıtımı — koç + 2 öğrenci + 2 veli. AI özellikleri açık.",
    members: "1 koç + 2 öğr + 2 veli",
  },
  {
    key: "institution_teacher",
    label: "Kuruma Bağlı Öğretmen",
    description: "Tek öğretmen-öğrenci akışı (kurum yöneticisi gerekmez).",
    members: "1 öğretmen + 1 öğr + 1 veli",
  },
];

function DemoEcosystemDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  // Outer kapı — kapalıyken inner render edilmez → her açılışta state
  // yeniden init olur (set-state-in-effect deseninden kaçınma).
  if (!open) return null;
  return <DemoEcosystemDialogInner onClose={onClose} />;
}

function DemoEcosystemDialogInner({ onClose }: { onClose: () => void }) {
  const [selectedKind, setSelectedKind] = React.useState<DemoKind>("institution");
  const [label, setLabel] = React.useState("");
  const [result, setResult] = React.useState<DemoSeedResult | null>(null);
  const create = useCreateDemoEcosystem();

  function handleCreate() {
    create.mutate(
      { kind: selectedKind, label: label.trim() || null },
      {
        onSuccess: (data) => setResult(data),
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FlaskConical className="size-5 text-amber-700" aria-hidden />
            Demo Ekosistem Oluştur
          </DialogTitle>
        </DialogHeader>

        {!result ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Tanıtım/satış için hazır kullanıcı ekosistemi yaratır. Email
              <code className="mx-1 px-1 py-0.5 bg-muted rounded text-[11px]">demo-XXXXXXXX-rol@etutkoc.com</code>
              formatında, şifre standart <code className="mx-1 px-1 py-0.5 bg-muted rounded text-[11px]">Demo123!@</code>.
              Görüşme bitince <b>Kullanıcılar/Kurumlar</b> sayfalarından silinir.
            </p>

            <div className="space-y-2">
              {DEMO_KINDS.map((k) => {
                const active = selectedKind === k.key;
                return (
                  <button
                    key={k.key}
                    type="button"
                    onClick={() => setSelectedKind(k.key)}
                    className={cn(
                      "w-full text-left px-4 py-3 rounded-lg border-2 transition",
                      active
                        ? "border-amber-500 bg-amber-50"
                        : "border-border bg-card hover:bg-muted/50",
                    )}
                  >
                    <div className="flex items-baseline justify-between gap-2">
                      <h3 className="font-semibold text-foreground">{k.label}</h3>
                      <span className="text-[11px] text-muted-foreground">{k.members}</span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">{k.description}</p>
                  </button>
                );
              })}
            </div>

            {/* Etiket (opsiyonel) — Demo Hesaplar sayfasında görünür */}
            <div>
              <Label htmlFor="demo-label" className="text-xs">
                Etiket (opsiyonel)
              </Label>
              <Input
                id="demo-label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="örn. ABC Etüt için demo"
                maxLength={120}
                className="mt-1"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                Demo Hesaplar sayfasında bu etiket görünür — birden fazla
                seansı ayırt etmek için kullan.
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Vazgeç
              </Button>
              <Button
                onClick={handleCreate}
                disabled={create.isPending}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {create.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <FlaskConical className="size-4" aria-hidden />
                )}
                Oluştur
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <DemoResultPanel result={result} onClose={onClose} />
        )}
      </DialogContent>
    </Dialog>
  );
}

function DemoResultPanel({
  result,
  onClose,
}: {
  result: DemoSeedResult;
  onClose: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border-2 border-emerald-200 bg-emerald-50 p-3">
        <p className="text-sm font-semibold text-emerald-900">
          <CheckCircle2 className="inline size-4 mr-1" aria-hidden />
          Demo ekosistem hazır!
        </p>
        <p className="text-xs text-emerald-800 mt-1">{result.summary}</p>
        {result.institution_name ? (
          <p className="text-[11px] text-emerald-700 mt-1">
            Kurum: <b>{result.institution_name}</b>
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
          Kimlik Bilgileri (kopyala-yapıştır)
        </p>
        {result.credentials.map((c) => (
          <DemoCredentialCard key={c.user_id} cred={c} />
        ))}
      </div>

      <p className="text-[11px] text-muted-foreground italic">
        Şifreler aynıdır: <code className="px-1 py-0.5 bg-muted rounded">Demo123!@</code>
        — kopyala-yapıştır kolay. Görüşme bitince hesapları sil.
      </p>

      <DialogFooter>
        <Button onClick={onClose}>Kapat</Button>
      </DialogFooter>
    </div>
  );
}

function DemoCredentialCard({
  cred,
}: {
  cred: DemoSeedResult["credentials"][number];
}) {
  const [copied, setCopied] = React.useState<"email" | "password" | null>(null);

  async function copy(value: string, kind: "email" | "password") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(kind);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // Fallback boş
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-amber-700">
          {cred.role_label}
        </span>
        <span className="text-[11px] text-muted-foreground">
          {cred.full_name}
        </span>
      </div>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase text-muted-foreground w-14">
            Email
          </span>
          <code className="flex-1 text-xs font-mono bg-muted px-2 py-1 rounded">
            {cred.email}
          </code>
          <button
            type="button"
            onClick={() => copy(cred.email, "email")}
            className="px-2 py-1 text-[11px] rounded border border-border hover:bg-muted transition inline-flex items-center gap-1"
            title="Email dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200'i panoya kopyala"
          >
            {copied === "email" ? (
              <CheckCircle2 className="size-3 text-emerald-600" aria-hidden />
            ) : (
              <Clipboard className="size-3" aria-hidden />
            )}
            {copied === "email" ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase text-muted-foreground w-14">
            Şifre
          </span>
          <code className="flex-1 text-xs font-mono bg-muted px-2 py-1 rounded">
            {cred.password}
          </code>
          <button
            type="button"
            onClick={() => copy(cred.password, "password")}
            className="px-2 py-1 text-[11px] rounded border border-border hover:bg-muted transition inline-flex items-center gap-1"
          >
            {copied === "password" ? (
              <CheckCircle2 className="size-3 text-emerald-600" aria-hidden />
            ) : (
              <Clipboard className="size-3" aria-hidden />
            )}
            {copied === "password" ? "Kopyalandı" : "Kopyala"}
          </button>
        </div>
      </div>
    </div>
  );
}
