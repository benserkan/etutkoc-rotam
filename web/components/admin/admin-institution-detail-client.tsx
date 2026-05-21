"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  Download,
  FileText,
  Loader2,
  Save,
  ShieldAlert,
  Trash2,
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
  adminInstitutionBackupDownloadUrl,
  adminKeys,
  getAdminInstitution,
} from "@/lib/api/admin";
import {
  useDeleteInstitution,
  useEditInstitution,
} from "@/lib/hooks/use-admin-mutations";
import type { InstitutionDetailResponse } from "@/lib/types/admin";

interface Props {
  initial: InstitutionDetailResponse;
  institutionId: number;
}

const PLAN_OPTIONS = ["free", "starter", "professional"];

/**
 * Kurum detayı — Jinja `institution_detail.html` feature parity.
 *
 * Bölümler:
 *  - Header (ad + status + plan + slug + account-history butonu)
 *  - Health card (skor + 4 stat + indicators)
 *  - 2 sütun: edit form / (sayım + backup + danger zone)
 *  - 2 sütun: admins list / teachers list
 */
export function AdminInstitutionDetailClient({
  initial,
  institutionId,
}: Props) {
  const q = useQuery<InstitutionDetailResponse>({
    queryKey: adminKeys.institution(institutionId),
    queryFn: () => getAdminInstitution(institutionId),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;
  const inst = data.institution;

  return (
    <div className="space-y-5">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <Link
            href="/admin/institutions"
            className="text-sm text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Kurumlar
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 flex items-center gap-3 flex-wrap">
            {inst.name}
            {inst.is_active ? (
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                Aktif
              </span>
            ) : (
              <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                Pasif
              </span>
            )}
            <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
              {inst.plan}
            </span>
          </h1>
          <div className="text-sm text-muted-foreground mt-1 font-mono">
            {inst.slug}
          </div>
        </div>
        <Button asChild variant="outline" className="border-indigo-200 bg-indigo-50 text-indigo-700 hover:bg-indigo-100">
          <Link href={`/admin/institutions/${inst.id}/account-history`}>
            <FileText className="size-4" aria-hidden />
            Hesap Hareketleri
          </Link>
        </Button>
      </header>

      <HealthCard health={data.health} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <EditInstitutionForm
          institutionId={inst.id}
          initialValues={{
            name: inst.name,
            contact_email: inst.contact_email,
            plan: inst.plan,
            is_active: inst.is_active,
          }}
        />
        <div className="space-y-4">
          <CountsCard
            adminCount={data.institution_admins.length}
            teacherCount={data.teachers.length}
            studentCount={data.student_count}
          />
          <BackupCard institutionId={inst.id} />
          <DangerZone
            institutionId={inst.id}
            institutionName={inst.name}
            teacherCount={data.teachers.length}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <UserListCard
          title="Kurum Yöneticileri"
          users={data.institution_admins}
          emptyHref={`/admin/users?institution_id=${inst.id}&role=institution_admin`}
          emptyText="Bu kurumda henüz yönetici yok."
        />
        <UserListCard
          title="Öğretmenler"
          users={data.teachers}
          emptyText="Henüz öğretmen yok."
        />
      </div>
    </div>
  );
}

// ============================================================================
// Health card
// ============================================================================

function HealthCard({ health }: { health: InstitutionDetailResponse["health"] }) {
  const tone = colorToTone(health.level_color);
  return (
    <Card className={cn("border", tone.border)}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4">
            <div className="text-5xl">{health.level_emoji}</div>
            <div>
              <div className="text-xs uppercase tracking-wider text-muted-foreground">
                Sağlık Skoru
              </div>
              <div className="flex items-baseline gap-2 mt-0.5">
                <span className={cn("text-4xl font-bold tabular-nums", tone.text)}>
                  {health.score}
                </span>
                <span className="text-base text-muted-foreground">/ 100</span>
                <span
                  className={cn(
                    "ml-2 text-base px-2.5 py-0.5 rounded font-semibold border",
                    tone.pill,
                  )}
                >
                  {health.level_label}
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Yüksek puan = kurumun sistemi terk etme (ayrılma) riski yüksek.
                <br />
                0-29 sağlıklı · 30-49 göz at · 50-69 ilgi göster · 70+ acil müdahale.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
            <HealthStat
              label="Öğretmen"
              value={health.teacher_count}
              sub={
                health.teacher_active_pct != null
                  ? `7g aktif: %${health.teacher_active_pct}`
                  : "—"
              }
            />
            <HealthStat
              label="Öğrenci"
              value={health.student_count}
              sub={
                health.student_active_pct != null
                  ? `7g aktif: %${health.student_active_pct}`
                  : "—"
              }
            />
            <HealthStat
              label="Tamamlama"
              value={
                health.weekly_completion_rate != null
                  ? `%${health.weekly_completion_rate}`
                  : "—"
              }
              sub="bu hafta"
            />
            <HealthStat
              label="Son giriş"
              value={
                health.last_teacher_login
                  ? formatDayShort(health.last_teacher_login)
                  : "—"
              }
              sub="öğretmen"
            />
          </div>
        </div>

        {health.indicators.length > 0 ? (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs font-medium mb-2 inline-flex items-center gap-1.5">
              <AlertTriangle className="size-3.5 text-amber-500" aria-hidden />
              Bu Skoru Yükselten Sebepler ({health.indicators.length})
            </p>
            <ul className="space-y-1.5">
              {health.indicators.map((ind) => (
                <li
                  key={ind.code}
                  className="flex items-start gap-2 text-sm"
                >
                  <span className="text-rose-600 mt-0.5">●</span>
                  <div className="flex-1">
                    <div className="font-medium inline-flex items-baseline gap-1.5">
                      {ind.title}
                      <span className="text-xs text-muted-foreground font-mono">
                        +{ind.weight} puan
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {ind.detail}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <div className="mt-4 pt-4 border-t border-border text-sm text-emerald-700 inline-flex items-center gap-2">
            <span>✓</span>
            <span>Bu kurum aktif kullanılıyor — herhangi bir risk uyarısı yok.</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HealthStat({
  label,
  value,
  sub,
}: {
  label: string;
  value: number | string;
  sub?: string;
}) {
  return (
    <div className="px-3 py-2 bg-muted/40 rounded">
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
        {label}
      </div>
      <div className="text-lg font-semibold mt-0.5 tabular-nums">{value}</div>
      {sub && (
        <div className="text-[10px] text-muted-foreground">{sub}</div>
      )}
    </div>
  );
}

// ============================================================================
// Edit form
// ============================================================================

function EditInstitutionForm({
  institutionId,
  initialValues,
}: {
  institutionId: number;
  initialValues: {
    name: string;
    contact_email: string | null;
    plan: string;
    is_active: boolean;
  };
}) {
  const router = useRouter();
  const mut = useEditInstitution(institutionId);
  const [name, setName] = React.useState(initialValues.name);
  const [contactEmail, setContactEmail] = React.useState(
    initialValues.contact_email ?? "",
  );
  const [plan, setPlan] = React.useState(initialValues.plan);
  const [isActive, setIsActive] = React.useState(initialValues.is_active);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        name: name.trim(),
        contact_email: contactEmail.trim() || null,
        plan,
        is_active: isActive,
      },
      {
        onSuccess: () => router.refresh(),
      },
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-medium mb-3">Kurum Bilgileri</h2>
        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <Label
              htmlFor="edit-name"
              className="text-xs uppercase tracking-wide"
            >
              Ad
            </Label>
            <Input
              id="edit-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="mt-1"
            />
          </div>
          <div>
            <Label
              htmlFor="edit-email"
              className="text-xs uppercase tracking-wide"
            >
              İletişim E-posta
            </Label>
            <Input
              id="edit-email"
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label
              htmlFor="edit-plan"
              className="text-xs uppercase tracking-wide"
            >
              Plan
            </Label>
            <select
              id="edit-plan"
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
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="accent-indigo-600"
            />
            <span>Aktif (pasif yapılırsa kullanıcılar giriş yapamaz)</span>
          </label>
          <div className="pt-2 flex justify-end">
            <Button
              type="submit"
              disabled={mut.isPending || name.trim().length === 0}
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
// Counts
// ============================================================================

function CountsCard({
  adminCount,
  teacherCount,
  studentCount,
}: {
  adminCount: number;
  teacherCount: number;
  studentCount: number;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="font-medium mb-3">Kurumdaki Kullanıcılar</h2>
        <dl className="grid grid-cols-3 gap-3 text-center">
          <CountBlock value={adminCount} label="Yönetici" />
          <CountBlock value={teacherCount} label="Öğretmen" />
          <CountBlock value={studentCount} label="Öğrenci" />
        </dl>
      </CardContent>
    </Card>
  );
}

function CountBlock({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
      <dt className="text-xs text-muted-foreground mt-0.5">{label}</dt>
    </div>
  );
}

// ============================================================================
// Backup
// ============================================================================

function BackupCard({ institutionId }: { institutionId: number }) {
  return (
    <Card className="border-violet-200 bg-violet-50/40">
      <CardContent className="p-5">
        <h2 className="font-medium text-violet-900 mb-2 inline-flex items-center gap-1.5">
          <Download className="size-4" aria-hidden />
          Kurum Yedeği İndir
        </h2>
        <p className="text-xs text-violet-800 mb-3 leading-relaxed">
          Bu kuruma ait tüm verileri (kullanıcılar, kitaplar, görevler, geçmiş
          bildirimler ve son 90 günün etkinlik geçmişi) tek bir{" "}
          <code>.json</code> dosyası olarak indirir. Şifreler güvenlik nedeniyle
          gizli tutulur (REDACTED). KVKK madde 11 (veri taşıma) için kullanılır.
        </p>
        <Button
          asChild
          size="sm"
          className="bg-violet-600 hover:bg-violet-700 text-white"
        >
          <a
            href={adminInstitutionBackupDownloadUrl(institutionId)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Download className="size-3.5" aria-hidden />
            Yedeği İndir (.json)
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Danger zone
// ============================================================================

function DangerZone({
  institutionId,
  institutionName,
  teacherCount,
}: {
  institutionId: number;
  institutionName: string;
  teacherCount: number;
}) {
  const router = useRouter();
  const mut = useDeleteInstitution(institutionId);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function onDelete() {
    mut.mutate(undefined, {
      onSuccess: () => {
        setConfirmOpen(false);
        router.push("/admin/institutions");
      },
    });
  }

  return (
    <Card className="border-rose-200 bg-rose-50/40">
      <CardContent className="p-5">
        <h2 className="font-medium text-rose-900 mb-2 inline-flex items-center gap-1.5">
          <ShieldAlert className="size-4" aria-hidden />
          Tehlikeli Bölge
        </h2>
        <p className="text-xs text-rose-800 mb-3 leading-relaxed">
          Kurumu silersen kullanıcılar <strong>silinmez</strong> — kurumdan
          ayrılırlar. Öğretmenler bağımsız öğretmen olarak sisteme devam eder,
          başka bir kuruma katılabilir veya kendi başına çalışabilir. Bu işlem
          geri alınamaz.
        </p>
        <Button
          size="sm"
          variant="outline"
          className="border-rose-300 text-rose-700 hover:bg-rose-100"
          onClick={() => setConfirmOpen(true)}
        >
          <Trash2 className="size-3.5" aria-hidden />
          Kurumu Sil
        </Button>

        <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Kurumu Sil</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              <strong>{institutionName}</strong> kurumunu silmek istediğine emin
              misin? <strong className="tabular-nums">{teacherCount}</strong>{" "}
              öğretmen bağımsız olacak.
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
                onClick={onDelete}
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
// User list (admin/teacher)
// ============================================================================

function UserListCard({
  title,
  users,
  emptyHref,
  emptyText,
}: {
  title: string;
  users: InstitutionDetailResponse["teachers"];
  emptyHref?: string;
  emptyText: string;
}) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <h2 className="font-medium">{title}</h2>
        <span className="text-xs text-muted-foreground tabular-nums">
          {users.length}
        </span>
      </div>
      {users.length === 0 ? (
        <p className="px-4 py-6 text-center text-sm text-muted-foreground italic">
          {emptyText}
          {emptyHref && (
            <>
              <br />
              <Link
                href={emptyHref}
                className="text-indigo-700 hover:underline mt-1 inline-block"
              >
                Yönetici ekle →
              </Link>
            </>
          )}
        </p>
      ) : (
        <ul className="divide-y divide-border text-sm">
          {users.map((u) => (
            <li
              key={u.id}
              className="px-4 py-2 flex items-center justify-between gap-2"
            >
              <span className="min-w-0 truncate">
                <strong>{u.full_name}</strong>
                <span className="text-muted-foreground font-mono text-xs ml-2">
                  {u.email}
                </span>
              </span>
              <span className="text-xs text-muted-foreground whitespace-nowrap shrink-0">
                {u.last_login_at
                  ? `son: ${formatDateTime(u.last_login_at)}`
                  : !u.is_active
                    ? "(pasif)"
                    : "hiç giriş yok"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function colorToTone(color: string) {
  const map: Record<
    string,
    { border: string; text: string; pill: string }
  > = {
    rose: {
      border: "border-rose-300",
      text: "text-rose-700",
      pill: "bg-rose-50 text-rose-700 border-rose-200",
    },
    amber: {
      border: "border-amber-300",
      text: "text-amber-700",
      pill: "bg-amber-50 text-amber-700 border-amber-200",
    },
    yellow: {
      border: "border-yellow-300",
      text: "text-yellow-700",
      pill: "bg-yellow-50 text-yellow-700 border-yellow-200",
    },
    emerald: {
      border: "border-emerald-300",
      text: "text-emerald-700",
      pill: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
  };
  return (
    map[color] ?? {
      border: "border-slate-300",
      text: "text-slate-700",
      pill: "bg-slate-50 text-slate-700 border-slate-200",
    }
  );
}

function formatDayShort(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
