"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Drama,
  FileText,
  KeyRound,
  Loader2,
  Lock,
  Save,
  ShieldCheck,
  Trash2,
  UserCog,
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
import { adminKeys, getAdminUser } from "@/lib/api/admin";
import {
  useActivateUserPlan,
  useChangeUserRole,
  useDeleteAdminUser,
  useEditAdminUser,
  useImpersonateUser,
  useResetUserPassword,
} from "@/lib/hooks/use-admin-mutations";
import type {
  AdminRole,
  AdminUserDetailResponse,
  AdminUserListItem,
} from "@/lib/types/admin";
import { TempPasswordDialog } from "@/components/admin/admin-users-client";

interface Props {
  initial: AdminUserDetailResponse;
  userId: number;
}

const ROLE_OPTIONS: { value: AdminRole; label: string }[] = [
  { value: "super_admin", label: "Süper Admin" },
  { value: "institution_admin", label: "Kurum Yöneticisi" },
  { value: "teacher", label: "Öğretmen" },
  { value: "student", label: "Öğrenci" },
  { value: "parent", label: "Veli" },
];

const ROLE_COLOR: Record<AdminRole, string> = {
  super_admin: "bg-rose-50 text-rose-700 border-rose-200",
  institution_admin: "bg-violet-50 text-violet-700 border-violet-200",
  teacher: "bg-indigo-50 text-indigo-700 border-indigo-200",
  student: "bg-emerald-50 text-emerald-700 border-emerald-200",
  parent: "bg-sky-50 text-sky-700 border-sky-200",
};

/**
 * Kullanıcı detayı — Jinja `user_detail.html` feature parity.
 *
 * Bölümler:
 *  - Header (ad + rol + kurum + locked/pasif rozetleri + hesap hareketleri buton)
 *  - 2 sütun: bilgi formu + (güvenlik / rol değişimi / impersonate / delete)
 *  - Son aktivite tablosu (audit)
 */
export function AdminUserDetailClient({ initial, userId }: Props) {
  const q = useQuery<AdminUserDetailResponse>({
    queryKey: adminKeys.user(userId),
    queryFn: () => getAdminUser(userId),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const t = data.target;

  return (
    <div className="space-y-5">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link
            href="/admin/users"
            className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Kullanıcılar
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 flex items-center gap-3 flex-wrap">
            {t.full_name}
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded border",
                ROLE_COLOR[t.role],
              )}
            >
              {t.role_label}
            </span>
            {t.institution ? (
              <span className="text-xs text-muted-foreground">
                {t.institution.name}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground italic">
                bağımsız
              </span>
            )}
            {t.locked_until && (
              <span className="text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-300 inline-flex items-center gap-1">
                <Lock className="size-3" aria-hidden />
                kilitli
              </span>
            )}
            {!t.is_active && (
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                pasif
              </span>
            )}
          </h1>
          <div className="text-sm text-muted-foreground mt-1 font-mono">
            {t.email}
          </div>
        </div>
        {["teacher", "institution_admin", "super_admin"].includes(t.role) && (
          <Button asChild variant="outline" className="border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">
            <Link href={`/admin/users/${t.id}/account-history`}>
              <FileText className="size-4" aria-hidden />
              Hesap Hareketleri
            </Link>
          </Button>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <EditUserForm
          userId={t.id}
          target={t}
          institutions={data.institutions}
        />
        <div className="space-y-4">
          <SecurityCard
            target={t}
            passwordChangedAt={data.password_changed_at}
          />
          {t.role === "teacher" && !t.institution && (
            <SubscriptionCard userId={t.id} currentPlan={t.plan ?? "solo_free"} />
          )}
          {!data.is_self && (
            <>
              <ChangeRoleCard
                userId={t.id}
                target={t}
                institutions={data.institutions}
              />
              {t.role !== "super_admin" && t.is_active && (
                <ImpersonateCard
                  userId={t.id}
                  targetName={t.full_name}
                />
              )}
              <DangerZone
                userId={t.id}
                targetName={t.full_name}
              />
            </>
          )}
          {data.is_self && (
            <Card className="border-amber-200 bg-amber-50/40">
              <CardContent className="p-5 text-xs text-amber-900">
                ℹ Bu sayfa <strong>kendi profilin</strong>. Rol değişimi,
                impersonate ve hesap silme buradan yapılamaz (kilitlenme riski).
                Şifre sıfırlama için <Link href="/me/account" className="underline">/me/account</Link>{" "}
                kullanın.
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      <RecentActivityCard audits={data.recent_audits} />
    </div>
  );
}

// ============================================================================
// Abonelik aktivasyonu (solo koç — manuel ödeme sonrası)
// ============================================================================

const SOLO_PLAN_OPTIONS: { value: string; label: string }[] = [
  { value: "solo_pro", label: "Solo Pro" },
  { value: "solo_elite", label: "Solo Elite" },
  { value: "solo_free", label: "Solo Ücretsiz" },
];

const SOLO_PLAN_LABELS: Record<string, string> = {
  solo_trial: "14 Günlük Deneme",
  solo_free: "Solo Ücretsiz",
  solo_pro: "Solo Pro",
  solo_elite: "Solo Elite",
};

function SubscriptionCard({ userId, currentPlan }: { userId: number; currentPlan: string }) {
  const mut = useActivateUserPlan(userId);
  const [plan, setPlan] = React.useState("solo_pro");
  return (
    <Card className="border-cyan-200">
      <CardContent className="space-y-3 p-5">
        <h3 className="text-sm font-medium">Abonelik aktivasyonu</h3>
        <p className="text-xs text-muted-foreground">
          Koçun &quot;öde ve devam et&quot; talebi <strong>İletişim Talepleri</strong>&apos;nde
          görünür. Ödeme alındıktan sonra planı buradan aktive et.
        </p>
        <p className="text-xs">
          Mevcut plan:{" "}
          <span className="font-medium">{SOLO_PLAN_LABELS[currentPlan] ?? currentPlan}</span>
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={plan}
            onChange={(e) => setPlan(e.target.value)}
            className="rounded border border-input bg-card px-3 py-2 text-sm"
          >
            {SOLO_PLAN_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <Button
            onClick={() => mut.mutate({ plan })}
            disabled={mut.isPending}
            className="bg-cyan-700 text-white hover:bg-cyan-800"
          >
            {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            Aktive et
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Edit form
// ============================================================================

function EditUserForm({
  userId,
  target,
  institutions,
}: {
  userId: number;
  target: AdminUserListItem;
  institutions: AdminUserDetailResponse["institutions"];
}) {
  const router = useRouter();
  const mut = useEditAdminUser(userId);
  const [fullName, setFullName] = React.useState(target.full_name);
  const [email, setEmail] = React.useState(target.email);
  const [instId, setInstId] = React.useState(
    target.institution ? String(target.institution.id) : "",
  );
  const [isActive, setIsActive] = React.useState(target.is_active);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        full_name: fullName.trim(),
        email: email.trim(),
        institution_id: instId ? Number(instId) : null,
        is_active: isActive,
      },
      { onSuccess: () => router.refresh() },
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-medium mb-3 inline-flex items-center gap-1.5">
          <UserCog className="size-4 text-indigo-700" aria-hidden />
          Bilgiler
        </h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label
              htmlFor="eu-name"
              className="text-xs uppercase tracking-wide"
            >
              Ad Soyad
            </Label>
            <Input
              id="eu-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              className="mt-1"
            />
          </div>
          <div>
            <Label
              htmlFor="eu-email"
              className="text-xs uppercase tracking-wide"
            >
              E-posta
            </Label>
            <Input
              id="eu-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-1"
            />
          </div>
          <div>
            <Label
              htmlFor="eu-inst"
              className="text-xs uppercase tracking-wide"
            >
              Kurum
            </Label>
            <select
              id="eu-inst"
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
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="accent-indigo-600"
            />
            <span>Aktif (kapatılırsa giriş yapamaz)</span>
          </label>
          <div className="pt-2 flex justify-end">
            <Button
              type="submit"
              disabled={mut.isPending}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Save className="size-4" aria-hidden />
              )}
              Güncelle
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Security card (reset password)
// ============================================================================

function SecurityCard({
  target,
  passwordChangedAt,
}: {
  target: AdminUserListItem;
  passwordChangedAt: string | null;
}) {
  const mut = useResetUserPassword(target.id);
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  const [tempPw, setTempPw] = React.useState<{
    user: { full_name: string };
    temp_password: string;
  } | null>(null);

  function doReset() {
    mut.mutate(undefined, {
      onSuccess: (res) => {
        setConfirmOpen(false);
        if (res.data.temp_password) {
          setTempPw({
            user: { full_name: target.full_name },
            temp_password: res.data.temp_password,
          });
        }
      },
    });
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-medium mb-3 inline-flex items-center gap-1.5">
          <ShieldCheck className="size-4 text-indigo-700" aria-hidden />
          Güvenlik
        </h2>
        <dl className="text-xs text-muted-foreground space-y-1.5 mb-3">
          <DRow label="Son giriş">
            {target.last_login_at
              ? formatFullDateTime(target.last_login_at)
              : "—"}
          </DRow>
          <DRow label="Son IP">
            <span className="font-mono">{target.last_login_ip ?? "—"}</span>
          </DRow>
          <DRow label="Başarısız giriş sayısı">
            <span className="tabular-nums">{target.failed_login_count}</span>
          </DRow>
          <DRow label="Kilit bitişi">
            {target.locked_until
              ? formatDateTime(target.locked_until)
              : "yok"}
          </DRow>
          <DRow label="Şifre değişimi">
            {passwordChangedAt ? formatDate(passwordChangedAt) : "—"}
          </DRow>
        </dl>
        <Button
          size="sm"
          onClick={() => setConfirmOpen(true)}
          className="bg-amber-500 hover:bg-amber-600 text-white"
        >
          <KeyRound className="size-3.5" aria-hidden />
          Şifre Sıfırla
        </Button>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Şifre Sıfırla</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              <strong>{target.full_name}</strong> için güçlü geçici şifre
              üretilsin mi? Kullanıcı ilk girişte kendi şifresini belirleyecek.
              Mevcut kilit varsa açılacak.
            </p>
            <DialogFooter className="gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                disabled={mut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                onClick={doReset}
                disabled={mut.isPending}
                className="bg-amber-500 hover:bg-amber-600 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <KeyRound className="size-4" aria-hidden />
                )}
                Şifre Sıfırla
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <TempPasswordDialog
          result={tempPw}
          onClose={() => setTempPw(null)}
        />
      </CardContent>
    </Card>
  );
}

function DRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between">
      <dt>{label}:</dt>
      <dd>{children}</dd>
    </div>
  );
}

// ============================================================================
// Change role card
// ============================================================================

function ChangeRoleCard({
  userId,
  target,
  institutions,
}: {
  userId: number;
  target: AdminUserListItem;
  institutions: AdminUserDetailResponse["institutions"];
}) {
  const router = useRouter();
  const mut = useChangeUserRole(userId);
  const [newRole, setNewRole] = React.useState<AdminRole>(target.role);
  const [instId, setInstId] = React.useState(
    target.institution ? String(target.institution.id) : "",
  );
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setConfirmOpen(true);
  }

  function doChange() {
    mut.mutate(
      {
        new_role: newRole,
        institution_id: instId ? Number(instId) : null,
      },
      {
        onSuccess: () => {
          setConfirmOpen(false);
          router.refresh();
        },
      },
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-medium mb-3 inline-flex items-center gap-1.5">
          <UserCog className="size-4 text-violet-700" aria-hidden />
          Rol Değişimi
        </h2>
        <form onSubmit={onSubmit} className="space-y-2">
          <select
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as AdminRole)}
            className="w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <select
            value={instId}
            onChange={(e) => setInstId(e.target.value)}
            className="w-full px-3 py-2 border border-input rounded-md text-sm bg-card"
          >
            <option value="">— Bağımsız —</option>
            {institutions.map((i) => (
              <option key={i.id} value={String(i.id)}>
                {i.name}
              </option>
            ))}
          </select>
          <div className="flex justify-end pt-1">
            <Button
              type="submit"
              size="sm"
              disabled={mut.isPending}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              Rolü Değiştir
            </Button>
          </div>
        </form>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Rol Değişimi Onayı</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Rol değişimi <strong>audit log&apos;a kaydedilir</strong>. Devam
              edilsin mi?
            </p>
            <DialogFooter className="gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                disabled={mut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                onClick={doChange}
                disabled={mut.isPending}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Onayla
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Impersonate card
// ============================================================================

function ImpersonateCard({
  userId,
  targetName,
}: {
  userId: number;
  targetName: string;
}) {
  const mut = useImpersonateUser(userId);
  const [reason, setReason] = React.useState("");
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function onStart(e: React.FormEvent) {
    e.preventDefault();
    if (reason.trim().length < 10) return;
    setConfirmOpen(true);
  }

  function doImpersonate() {
    mut.mutate(
      { reason: reason.trim() },
      {
        onSuccess: (data) => {
          setConfirmOpen(false);
          // Backend session set'i yaptı; Next.js sayfasına yönlendir
          window.location.href = data.redirect_url;
        },
      },
    );
  }

  return (
    <Card className="border-violet-200 bg-violet-50/40">
      <CardContent className="p-5">
        <h2 className="font-medium text-violet-900 mb-2 inline-flex items-center gap-1.5">
          <Drama className="size-4" aria-hidden />
          Sahte Oturum
        </h2>
        <p className="text-xs text-violet-800 mb-3 leading-relaxed">
          <strong>{targetName}</strong> olarak sisteme giriş yapmış gibi
          görüntüle. Tüm aksiyonların target adı altında çalışır; üst banner
          ile gerçek admin&apos;e dönebilirsin. <strong>Audit log&apos;a
          kaydedilir.</strong>
        </p>
        <p className="text-[11px] text-violet-700 mb-2">
          ⏱ 30 dakika sonra otomatik kapanır. Gerekçe zorunlu (10-200
          karakter).
        </p>
        <form onSubmit={onStart} className="space-y-2">
          <Label
            htmlFor="imp-reason"
            className="text-[11px] text-violet-800 font-medium"
          >
            Gerekçe (zorunlu)
          </Label>
          <textarea
            id="imp-reason"
            rows={2}
            maxLength={200}
            minLength={10}
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="örn. 'Ödevler görünmüyor şikayetini yerinde inceleme'"
            className="block w-full px-2 py-1.5 text-xs border border-violet-300 rounded bg-white focus:border-violet-500 focus:ring-1 focus:ring-violet-300"
          />
          <Button
            type="submit"
            size="sm"
            disabled={reason.trim().length < 10}
            className="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Drama className="size-3.5" aria-hidden />
            Sahte oturum başlat
          </Button>
        </form>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Sahte Oturum Başlat</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              <strong>{targetName}</strong> olarak sahte oturum başlat? Bu
              işlem audit log&apos;a kaydedilir ve 30 dk sonra otomatik
              kapanır.
            </p>
            <div className="rounded-md border border-violet-200 bg-violet-50 p-2 text-xs text-violet-900">
              <strong>Gerekçe:</strong> {reason}
            </div>
            <DialogFooter className="gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                disabled={mut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                onClick={doImpersonate}
                disabled={mut.isPending}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Drama className="size-4" aria-hidden />
                )}
                Başlat
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Danger zone (delete)
// ============================================================================

function DangerZone({
  userId,
  targetName,
}: {
  userId: number;
  targetName: string;
}) {
  const router = useRouter();
  const mut = useDeleteAdminUser(userId);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function doDelete() {
    mut.mutate(undefined, {
      onSuccess: () => {
        setConfirmOpen(false);
        router.push("/admin/users");
      },
    });
  }

  return (
    <Card className="border-rose-200 bg-rose-50/40">
      <CardContent className="p-5">
        <h2 className="font-medium text-rose-900 mb-2 inline-flex items-center gap-1.5">
          <Trash2 className="size-4" aria-hidden />
          Tehlikeli
        </h2>
        <p className="text-xs text-rose-800 mb-3 leading-relaxed">
          Kullanıcıyı tamamen siler. CASCADE ile bağlı veriler de silinir
          (öğrenci silinirse görevleri/ilerlemesi gider).
        </p>
        <Button
          size="sm"
          variant="outline"
          className="border-rose-300 text-rose-700 hover:bg-rose-100"
          onClick={() => setConfirmOpen(true)}
        >
          <Trash2 className="size-3.5" aria-hidden />
          Hesabı Sil
        </Button>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Kullanıcıyı Sil</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              <strong>{targetName}</strong> hesabını ve tüm verisini{" "}
              <strong>SİLMEK</strong> istediğine emin misin? Geri alınamaz.
            </p>
            <DialogFooter className="gap-2 pt-2">
              <Button
                variant="ghost"
                onClick={() => setConfirmOpen(false)}
                disabled={mut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                onClick={doDelete}
                disabled={mut.isPending}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Trash2 className="size-4" aria-hidden />
                )}
                Sil
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Recent activity
// ============================================================================

function RecentActivityCard({
  audits,
}: {
  audits: AdminUserDetailResponse["recent_audits"];
}) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border">
        <h2 className="font-medium inline-flex items-center gap-1.5">
          <FileText className="size-4 text-violet-700" aria-hidden />
          Son Aktivitesi
        </h2>
      </div>
      {audits.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground italic">
          Henüz aktivite kaydı yok.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Zaman</th>
                <th className="text-left px-4 py-2 font-medium">Olay</th>
                <th className="text-left px-4 py-2 font-medium">Hedef</th>
                <th className="text-left px-4 py-2 font-medium">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {audits.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-2 text-muted-foreground tabular-nums">
                    {formatDateTime(a.created_at)}
                  </td>
                  <td className="px-4 py-2 font-medium">{a.action}</td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {a.target_type
                      ? `${a.target_type}${a.target_id != null ? ` #${a.target_id}` : ""}`
                      : "—"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground font-mono">
                    {a.ip_address ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}

function formatFullDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
