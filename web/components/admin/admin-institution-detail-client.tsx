"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowUpRight,
  Check,
  Download,
  FileText,
  Gem,
  ImageIcon,
  Loader2,
  Save,
  ShieldAlert,
  Trash2,
  Upload,
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
import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import {
  useDeleteInstitution,
  useDeleteInstitutionLogo,
  useEditInstitution,
  useUploadInstitutionLogo,
} from "@/lib/hooks/use-admin-mutations";
import { buildInstitutionPlanOptions, institutionPlanLabel } from "@/lib/institution-plans";
import type { InstitutionDetailResponse, PendingUpgradeInfo } from "@/lib/types/admin";
import type { PricingCatalog } from "@/lib/types/pricing";

interface Props {
  initial: InstitutionDetailResponse;
  institutionId: number;
}

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
              {institutionPlanLabel(inst.plan)}
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

      <PlanCard
        institutionId={inst.id}
        currentPlan={inst.plan}
        name={inst.name}
        contactEmail={inst.contact_email}
        isActive={inst.is_active}
        pending={data.pending_upgrade ?? null}
      />

      <LogoCard
        institutionId={inst.id}
        name={inst.name}
        hasLogo={!!inst.has_logo}
        logoUrl={inst.logo_url ?? null}
      />

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
// Kurum logosu (co-branding) — süper admin yükler; kurum yöneticisi + bağlı
// öğretmen panellerinde gösterilir. PNG/JPEG/WebP, ≤2 MB.
// ============================================================================

function LogoCard({
  institutionId,
  name,
  hasLogo,
  logoUrl,
}: {
  institutionId: number;
  name: string;
  hasLogo: boolean;
  logoUrl: string | null;
}) {
  const upload = useUploadInstitutionLogo(institutionId);
  const remove = useDeleteInstitutionLogo(institutionId);
  const inputRef = React.useRef<HTMLInputElement>(null);
  // logo değişince <img> önbelleğini kır
  const [bust, setBust] = React.useState(0);
  const busy = upload.isPending || remove.isPending;

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    upload.mutate(file, { onSuccess: () => setBust((n) => n + 1) });
  }

  const src = logoUrl ? `${logoUrl}?v=${bust}` : null;

  return (
    <Card className="border-amber-200">
      <CardContent className="p-5">
        <div className="flex items-center gap-2 mb-1">
          <ImageIcon className="size-4 text-amber-600" aria-hidden />
          <h2 className="font-semibold">Kurum logosu</h2>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Kurum yöneticisi ve bağlı öğretmenlerin panel başlığında platform
          markasının yanında gösterilir. PNG, JPEG veya WebP · en fazla 2 MB.
        </p>

        <div className="flex items-center gap-4">
          <div className="flex size-16 shrink-0 items-center justify-center rounded-xl border border-border bg-card overflow-hidden">
            {hasLogo && src ? (
              <Image
                src={src}
                alt={name}
                width={56}
                height={56}
                unoptimized
                className="size-14 object-contain"
              />
            ) : (
              <ImageIcon className="size-7 text-muted-foreground/40" aria-hidden />
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={inputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={onPick}
            />
            <Button
              variant="outline"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
            >
              {upload.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Upload className="size-4" aria-hidden />
              )}
              {hasLogo ? "Logoyu değiştir" : "Logo yükle"}
            </Button>
            {hasLogo ? (
              <Button
                variant="ghost"
                className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                onClick={() => remove.mutate()}
                disabled={busy}
              >
                <Trash2 className="size-4" aria-hidden />
                Kaldır
              </Button>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Üyelik Planı — kurum yöneticisi yükseltme talebinin VARIŞ noktası (#plan).
// İletişim Talepleri → "Kurum sayfasına git (planı değiştir)" buraya çıpalanır.
// ============================================================================

// Kurum tier detayları (Google Workspace tarzı detaylı kart için).
interface InstTierDetails {
  monthly: number | null;       // ₺/ay — null = "Görüşme" (Enterprise)
  credits: number;              // aylık AI kredi (PLAN_ALLOCATIONS backend)
  coaches: string;              // koç sınırı kısa metni
  features: string[];
  badge?: string;
}

const INSTITUTION_TIER_DETAILS: Record<string, InstTierDetails> = {
  institution_free: {
    monthly: 0,
    credits: 200,
    coaches: "2 koç, 20 öğrenci",
    features: [
      "Kurumu tanımak için ücretsiz başlangıç",
      "200 aylık AI kredisi (sembolik — yoğun kullanım için yetersiz)",
      "Kuruluş paneli + müdahale merkezi",
      "Veli güveni paneli",
      "Akademik çıktı raporu",
    ],
  },
  etut_standart: {
    monthly: 10_000,
    credits: 10_000,
    coaches: "≤10 koç",
    badge: "En popüler",
    features: [
      "10 koça kadar bireysel koçluk",
      "Aylık 10.000 AI kredisi",
      "Program uyum panosu",
      "Müdahale merkezi + öğretmen karnesi",
      "Akademik çıktı + veli güveni",
      "Tüm bireysel koç özellikleri",
    ],
  },
  dershane_pro: {
    monthly: 30_000,
    credits: 40_000,
    coaches: "≤50 koç",
    features: [
      "Etüt Standart'ın tüm özellikleri",
      "50 koça kadar",
      "Aylık 40.000 AI kredisi (~4×)",
      "Çoklu şube/sınıf yönetimi",
      "Toplu kampanya gönderim",
      "Yıllık akademik yıl peşin (2 ay bedava)",
    ],
  },
  enterprise: {
    monthly: null,
    credits: 150_000,
    coaches: "50+ koç",
    features: [
      "Dershane Pro'nun tüm özellikleri",
      "Sınırsız koç + özel SLA",
      "Aylık 150.000 AI kredisi (~15×)",
      "White-label (kurum kendi markası)",
      "Özel entegrasyon + API erişimi",
      "Öncelikli destek + Account Manager",
    ],
  },
};

function PlanCard({
  institutionId,
  currentPlan,
  name,
  contactEmail,
  isActive,
  pending,
}: {
  institutionId: number;
  currentPlan: string;
  name: string;
  contactEmail: string | null;
  isActive: boolean;
  pending: PendingUpgradeInfo | null;
}) {
  const router = useRouter();
  const mut = useEditInstitution(institutionId);
  const catalogQ = useQuery<PricingCatalog>({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 60_000,
  });

  const planOptions = buildInstitutionPlanOptions(catalogQ.data);
  const hasCurrent = planOptions.some((p) => p.value === currentPlan);
  const allOptions = hasCurrent
    ? planOptions
    : [...planOptions, { value: currentPlan, label: institutionPlanLabel(currentPlan), coaches: "", desc: "" }];

  // Kurumun TALEP ETTİĞİ paket varsa onu ön-seç (admin tekrar seçmesin) —
  // yoksa mevcut plan. Talep edilen kod kataloğda mevcutsa ve mevcut plandan
  // farklıysa ön-seçim anlamlı.
  const requestedCode =
    pending?.requested_plan_code &&
    allOptions.some((o) => o.value === pending.requested_plan_code)
      ? pending.requested_plan_code
      : null;
  const initialSel = requestedCode && requestedCode !== currentPlan ? requestedCode : currentPlan;

  const [plan, setPlan] = React.useState(initialSel);
  // Sunucudan gelen güncel plan / talep değişince seçimi senkronla.
  const [prevKey, setPrevKey] = React.useState(`${currentPlan}|${requestedCode ?? ""}`);
  const curKey = `${currentPlan}|${requestedCode ?? ""}`;
  if (curKey !== prevKey) {
    setPrevKey(curKey);
    setPlan(initialSel);
  }

  const dirty = plan !== currentPlan;
  const selected = allOptions.find((p) => p.value === plan);

  // Talep var + belirli (ve mevcuttan farklı) bir paket istenmişse: ODAKLI ONAY
  // modu — admin diğer paketleri görüp tekrar SEÇMEZ; sadece talebi onaylar.
  // Aksi halde (talep yok / paket belirtilmemiş / istenen=mevcut): seçici modu.
  const requestedOption = requestedCode ? allOptions.find((o) => o.value === requestedCode) : undefined;
  const focusedConfirm = !!requestedCode && requestedCode !== currentPlan;
  const [showPicker, setShowPicker] = React.useState(false);
  const currentOption = allOptions.find((o) => o.value === currentPlan);

  function apply(target?: string) {
    mut.mutate(
      { name, contact_email: contactEmail, plan: target ?? plan, is_active: isActive },
      { onSuccess: () => router.refresh() },
    );
  }

  return (
    <Card id="plan" className="scroll-mt-20 border-cyan-200">
      <div className="h-1 w-full bg-gradient-to-r from-cyan-600 to-cyan-800" aria-hidden />
      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700">
            <Gem className="size-5" aria-hidden />
          </span>
          <div className="min-w-0">
            <h2 className="font-medium">Üyelik Planı</h2>
            <p className="text-xs text-muted-foreground">
              Kurumun planını buradan değiştir. Mevcut plan:{" "}
              <strong className="text-foreground">{institutionPlanLabel(currentPlan)}</strong>.
            </p>
          </div>
        </div>

        {focusedConfirm && !showPicker ? (
          /* ODAKLI ONAY — kurum paketi seçti, admin yalnızca onaylar */
          <div className="mt-3 space-y-3">
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
              <p className="flex items-center gap-2 font-semibold">
                <ArrowUpRight className="size-4 shrink-0" aria-hidden />
                Bu kurum <strong>{requestedOption?.label}</strong> paketine geçmek için talepte bulundu.
              </p>
              {pending?.note ? <p className="mt-1 text-amber-800">Kurumun notu: {pending.note}</p> : null}
            </div>

            {/* Mevcut → Talep edilen karşılaştırması */}
            <div className="flex items-center gap-3 text-sm">
              <div className="flex-1 rounded-lg border border-slate-200 bg-white p-3">
                <p className="text-[11px] uppercase tracking-wide text-slate-500">Mevcut</p>
                <p className="font-bold text-slate-900">{institutionPlanLabel(currentPlan)}</p>
                {currentOption?.coaches ? <p className="text-xs text-slate-600">{currentOption.coaches}</p> : null}
              </div>
              <ArrowUpRight className="size-5 shrink-0 text-cyan-600" aria-hidden />
              <div className="flex-1 rounded-lg border border-cyan-600 bg-cyan-50 p-3 ring-1 ring-cyan-600">
                <p className="text-[11px] uppercase tracking-wide text-cyan-700">Talep edilen</p>
                <p className="font-bold text-slate-900">{requestedOption?.label}</p>
                {requestedOption?.coaches ? <p className="text-xs text-slate-700">{requestedOption.coaches}</p> : null}
                {requestedOption?.desc ? <p className="text-[11px] text-slate-600">{requestedOption.desc}</p> : null}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <button
                type="button"
                onClick={() => setShowPicker(true)}
                className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                Başka bir plana geçir
              </button>
              <Button
                onClick={() => apply(requestedCode!)}
                disabled={mut.isPending}
                className="bg-cyan-700 hover:bg-cyan-800 text-white"
              >
                {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                {requestedOption?.label} paketine yükselt
              </Button>
            </div>
          </div>
        ) : (
          /* SEÇİCİ — talep yok / paket belirtilmemiş / admin elle yönetiyor */
          <>
            {pending && !requestedCode ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-900">
                Bu kurum yükseltme talebinde bulundu ama belirli bir paket belirtmedi —
                uygun kademeyi seç.
                {pending.note ? <><br /><span className="text-amber-800">Not: {pending.note}</span></> : null}
              </div>
            ) : null}

            {/* 4 BÜYÜK detaylı paket kartı yan yana (Google Workspace tarzı) */}
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {allOptions.map((p) => {
                const isSel = p.value === plan;
                const isCur = p.value === currentPlan;
                const details = INSTITUTION_TIER_DETAILS[p.value];
                return (
                  <div
                    key={p.value}
                    className={cn(
                      "relative flex flex-col rounded-2xl border-2 bg-white p-4 transition",
                      isSel
                        ? "border-cyan-600 shadow-lg ring-2 ring-cyan-100"
                        : "border-slate-200 hover:border-cyan-300",
                    )}
                  >
                    {/* Üst rozetler */}
                    {details?.badge ? (
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-amber-400 px-3 py-0.5 text-[11px] font-bold text-cyan-950 shadow-sm">
                        {details.badge}
                      </span>
                    ) : null}
                    {isCur ? (
                      <span className="absolute right-2 top-2 rounded-full bg-slate-700 px-2 py-0.5 text-[10px] font-bold text-white">
                        Mevcut paket
                      </span>
                    ) : null}

                    {/* Başlık */}
                    <div className="mb-3">
                      <h3 className="font-display text-lg font-extrabold text-slate-900">{p.label}</h3>
                      <p className="text-xs text-slate-600">{details?.coaches ?? p.coaches ?? "—"}</p>
                    </div>

                    {/* Fiyat */}
                    <div className="mb-3">
                      {details && details.monthly != null ? (
                        details.monthly === 0 ? (
                          <div className="flex items-baseline gap-1">
                            <span className="font-display text-2xl font-extrabold text-slate-900">Ücretsiz</span>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-baseline gap-1">
                              <span className="font-display text-2xl font-extrabold text-slate-900">
                                {details.monthly.toLocaleString("tr-TR")}
                              </span>
                              <span className="text-sm text-slate-500">₺/ay</span>
                            </div>
                            <p className="text-[11px] text-slate-500">
                              yıllık {(details.monthly * 10).toLocaleString("tr-TR")} ₺ (2 ay bedava)
                            </p>
                          </>
                        )
                      ) : (
                        <div className="flex items-baseline gap-1">
                          <span className="font-display text-xl font-extrabold text-slate-900">Özel teklif</span>
                        </div>
                      )}
                    </div>

                    {/* AI kredi ön plana çıkar */}
                    {details ? (
                      <div className="mb-3 rounded-lg border border-cyan-200 bg-cyan-50/70 px-3 py-2">
                        <p className="text-[10px] font-bold uppercase tracking-wide text-cyan-800">
                          Aylık yapay zekâ kredisi
                        </p>
                        <p className="font-display text-xl font-extrabold text-cyan-900">
                          {details.credits.toLocaleString("tr-TR")}{" "}
                          <span className="text-xs font-medium text-cyan-700">kredi</span>
                        </p>
                      </div>
                    ) : null}

                    {/* Özellik listesi */}
                    {details ? (
                      <ul className="mb-4 space-y-1.5 text-xs">
                        {details.features.map((f) => (
                          <li key={f} className="flex items-start gap-1.5">
                            <Check className="mt-0.5 size-3.5 shrink-0 text-emerald-600" aria-hidden />
                            <span className="text-slate-700">{f}</span>
                          </li>
                        ))}
                      </ul>
                    ) : p.desc ? (
                      <p className="mb-4 text-xs text-slate-600">{p.desc}</p>
                    ) : null}

                    {/* CTA */}
                    <div className="mt-auto">
                      <Button
                        size="sm"
                        className={cn(
                          "w-full whitespace-normal text-xs",
                          isCur
                            ? "border border-slate-300 bg-slate-100 text-slate-600 hover:bg-slate-100"
                            : isSel
                              ? "bg-cyan-700 text-white hover:bg-cyan-800"
                              : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
                        )}
                        disabled={isCur}
                        onClick={() => {
                          if (isCur) return;
                          if (isSel) {
                            apply();
                          } else {
                            setPlan(p.value);
                          }
                        }}
                      >
                        {isCur ? "Aktif paket" : isSel ? "Bu pakete geç" : "Bu paketi seç"}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              {focusedConfirm ? (
                <button
                  type="button"
                  onClick={() => { setShowPicker(false); setPlan(requestedCode!); }}
                  className="underline-offset-2 hover:text-foreground hover:underline"
                >
                  ← Talep edilen pakete dön
                </button>
              ) : (
                <p>
                  {dirty
                    ? <>Seçilen: <strong className="text-foreground">{selected?.label}</strong>. Kartın altındaki <strong>&quot;Bu pakete geç&quot;</strong> ile onayla.</>
                    : "Plan değiştirmek için kart seç → tekrar tıklayıp uygula."}
                </p>
              )}
              {mut.isPending ? (
                <span className="inline-flex items-center gap-1"><Loader2 className="size-3 animate-spin" aria-hidden /> Uygulanıyor…</span>
              ) : null}
            </div>
          </>
        )}
      </CardContent>
    </Card>
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
  const [isActive, setIsActive] = React.useState(initialValues.is_active);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    // plan GÖNDERİLMEZ → backend mevcut planı korur. Plan değişimi ayrı
    // "Üyelik Planı" kartından yapılır (akış: talep → kurum sayfası #plan).
    mut.mutate(
      {
        name: name.trim(),
        contact_email: contactEmail.trim() || null,
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
