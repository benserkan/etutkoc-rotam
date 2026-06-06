"use client";

import * as React from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowUpCircle,
  Brain,
  CalendarRange,
  CheckCircle2,
  Dna,
  Loader2,
  MessageSquare,
  Pencil,
  RefreshCw,
  Target,
  Timer,
} from "lucide-react";

import { teacherKeys } from "@/lib/api/teacher";
import { useTeacherStudent } from "@/lib/hooks/use-teacher-queries";
import { useSetWeekAnchor, usePatchStudent } from "@/lib/hooks/use-teacher-mutations";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { GorevBreakdown, TeacherStudentDetailResponse } from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { StudentBooksPanel } from "@/components/teacher/student-books-panel";
import { StudentAnalyticsPanel } from "@/components/teacher/student-analytics-panel";
import { StudentExamsPanel } from "@/components/teacher/student-exams-panel";
import { StudentSessionsPanel } from "@/components/teacher/student-sessions-panel";
import { StudentParentsPanel } from "@/components/teacher/student-parents-panel";
import { WaSendDialog } from "@/components/messaging/wa-send-dialog";
import { TopicPerformancePanel } from "@/components/shared/topic-performance-panel";

type TabKey = "summary" | "analytics" | "topics" | "exams" | "sessions" | "books" | "parents";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "summary", label: "Genel" },
  { key: "analytics", label: "Analitik" },
  { key: "topics", label: "Konu Performansı" },
  { key: "exams", label: "Denemeler" },
  { key: "sessions", label: "Seanslar" },
  { key: "books", label: "Kitaplar" },
  { key: "parents", label: "Veliler" },
];

function isValidTab(v: string): v is TabKey {
  return (
    v === "summary" ||
    v === "analytics" ||
    v === "exams" ||
    v === "sessions" ||
    v === "books" ||
    v === "parents"
  );
}

interface Props {
  studentId: number;
  initial: TeacherStudentDetailResponse;
}

/**
 * Öğrenci detay paneli — Jinja `student_detail.html` parite.
 *
 * Header: ad + worst-warning nokta + zengin badge şeridi (track/curriculum/
 * exam/graduate/alan-eksik/academic year/active phase) + 7 quick-action.
 * Tab şeridi: Genel / Analitik / Kitaplar / Veliler.
 * Genel tab: 5 KPI + uyarı listesi + hızlı bilgi + Koçluk Takvimi (anchor edit).
 *
 * Hash-bazlı tab kontrol (#summary default). React 19 useSyncExternalStore ile
 * dış kaynak senkron.
 */
export function StudentTabs({ studentId, initial }: Props) {
  const q = useTeacherStudent(studentId, initial);
  const data = q.data ?? initial;
  const active = useHashTab();
  const qc = useQueryClient();

  function selectTab(key: TabKey) {
    if (typeof window !== "undefined") {
      const url = `${window.location.pathname}${window.location.search}#${key}`;
      window.history.replaceState(null, "", url);
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    }
  }

  function refreshAll() {
    qc.invalidateQueries({ queryKey: teacherKeys.student(studentId) });
    qc.invalidateQueries({ queryKey: teacherKeys.studentSummary(studentId) });
    qc.invalidateQueries({ queryKey: teacherKeys.studentWeek(studentId, "") });
  }

  const s = data.student;
  // Bugün/Hafta KPI'ları görev-bazlı (etkinlik/"Diğer" dahil); Hız/Tutarlılık/
  // Hedef Tutturma soru-hacmi (volume) olarak kalır.
  const today = Math.round((data.program_summary.today_task_pct ?? 0) * 100);
  const week = Math.round((data.program_summary.week_task_pct ?? 0) * 100);
  const consistency = Math.round((data.program_summary.consistency_7d ?? 0) * 100);
  const hitRate = Math.round((data.program_summary.hit_rate_7d ?? 0) * 100);
  const rate7d = data.program_summary.rate_7d ?? 0;

  return (
    <div className="space-y-6">
      {/* === Header === */}
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              <Link href="/teacher/students" className="hover:underline">
                ← Öğrenciler
              </Link>
              {" · "}
              {s.is_active ? "Aktif" : "Pasif"}
            </p>
            <h1 className="text-2xl font-semibold tracking-tight font-display flex items-center gap-3 mt-1">
              <span className="truncate">{s.full_name}</span>
              <WorstWarningDot level={data.worst_warning_level} />
            </h1>
            <BadgeRow profile={s} activePhase={data.active_phase ?? null} />
          </div>

          <QuickActions
            studentId={studentId}
            studentName={s.full_name}
            studentEmail={s.email}
            isGraduate={s.is_graduate}
            onRefresh={refreshAll}
            isRefreshing={q.isFetching}
          />
        </div>
      </header>

      {/* === Tab şeridi === */}
      <div
        role="tablist"
        aria-label="Öğrenci paneli sekmeleri"
        className="flex items-center gap-1 border-b border-border overflow-x-auto"
      >
        {TABS.map((t) => {
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`tab-panel-${t.key}`}
              id={`tab-${t.key}`}
              onClick={() => selectTab(t.key)}
              className={cn(
                "px-3 py-2 -mb-px text-sm border-b-2 transition-colors whitespace-nowrap",
                isActive
                  ? "border-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {active === "summary" ? (
        <div
          role="tabpanel"
          id="tab-panel-summary"
          aria-labelledby="tab-summary"
          className="space-y-4"
        >
          <MetricsStrip
            today={today}
            todayCompleted={data.program_summary.today_tasks_done ?? 0}
            todayPlanned={data.program_summary.today_tasks_total ?? 0}
            week={week}
            weekCompleted={data.program_summary.week_tasks_done ?? 0}
            weekPlanned={data.program_summary.week_tasks_total ?? 0}
            rate7d={rate7d}
            consistency={consistency}
            hitRate={hitRate}
            studentId={studentId}
          />

          <StatusSummary studentId={studentId} data={data} />

          <GorevBreakdownCard
            today={data.gorev_today ?? null}
            week={data.gorev_week ?? null}
          />

          {/* Hafta Anchor'ı yalnız aktif (explicit) program YOKKEN anlamlı —
              fallback hizalama mekanizması. Aktif program varsa kart gizlenir
              ("yeni program oluştur" akışı anchor'ı geçersiz kılar). */}
          {!data.has_active_program ? (
            <AnchorEditCard
              studentId={studentId}
              weekAnchor={data.week_anchor ?? null}
              isManual={data.anchor_is_manual ?? false}
            />
          ) : null}

          <section className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <Card>
              <CardContent className="p-4">
                <p className="font-medium">Talepler</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {data.pending_request_count > 0
                    ? `${data.pending_request_count} bekleyen talep var.`
                    : "Bekleyen talep yok."}
                </p>
                <Link
                  href={`/teacher/requests?student_id=${studentId}`}
                  className="mt-2 inline-block text-xs underline-offset-4 hover:underline text-foreground"
                >
                  Tüm taleplere git →
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <p className="font-medium">Haftalık plan</p>
                <p className="text-xs text-muted-foreground mt-1">
                  7 günlük programı düzenle, görev ekle, ders bazlı görünümü
                  incele.
                </p>
                <Link
                  href={`/teacher/students/${studentId}/week`}
                  className="mt-2 inline-block text-xs underline-offset-4 hover:underline text-foreground"
                >
                  Haftalık plana git →
                </Link>
              </CardContent>
            </Card>
          </section>
        </div>
      ) : null}

      {active === "analytics" ? (
        <div
          role="tabpanel"
          id="tab-panel-analytics"
          aria-labelledby="tab-analytics"
        >
          <StudentAnalyticsPanel studentId={studentId} />
        </div>
      ) : null}

      {active === "topics" ? (
        <div role="tabpanel" id="tab-panel-topics" aria-labelledby="tab-topics">
          <TopicPerformancePanel source="teacher" studentId={studentId} />
        </div>
      ) : null}

      {active === "exams" ? (
        <div role="tabpanel" id="tab-panel-exams" aria-labelledby="tab-exams">
          <StudentExamsPanel studentId={studentId} />
        </div>
      ) : null}

      {active === "sessions" ? (
        <div role="tabpanel" id="tab-panel-sessions" aria-labelledby="tab-sessions">
          <StudentSessionsPanel studentId={studentId} />
        </div>
      ) : null}

      {active === "books" ? (
        <div role="tabpanel" id="tab-panel-books" aria-labelledby="tab-books">
          <StudentBooksPanel studentId={studentId} />
        </div>
      ) : null}

      {active === "parents" ? (
        <div role="tabpanel" id="tab-panel-parents" aria-labelledby="tab-parents">
          <StudentParentsPanel studentId={studentId} />
        </div>
      ) : null}
    </div>
  );
}

// =============================================================================
// Header parçaları
// =============================================================================

function WorstWarningDot({ level }: { level: "green" | "amber" | "red" }) {
  const cls =
    level === "red"
      ? "bg-rose-500"
      : level === "amber"
        ? "bg-amber-500"
        : "bg-emerald-500";
  const title =
    level === "red"
      ? "Kritik uyarı var"
      : level === "amber"
        ? "Dikkat gereken durumlar var"
        : "Yolunda";
  return (
    <span
      className={cn("inline-block size-3 rounded-full flex-shrink-0", cls)}
      title={title}
      aria-label={title}
    />
  );
}

function BadgeRow({
  profile,
  activePhase,
}: {
  profile: TeacherStudentDetailResponse["student"];
  activePhase: TeacherStudentDetailResponse["active_phase"];
}) {
  const phaseTone: Record<string, string> = {
    winter_break: "border-sky-200 bg-sky-50 text-sky-700",
    summer_camp: "border-amber-200 bg-amber-50 text-amber-800",
    exam_prep: "border-rose-200 bg-rose-50 text-rose-700",
    regular: "border-border bg-muted text-muted-foreground",
  };
  const curriculumTone: Record<string, string> = {
    lgs: "border-sky-200 bg-sky-50 text-sky-700",
    klasik_lise: "border-amber-200 bg-amber-50 text-amber-800",
    maarif_lise: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
  return (
    <div className="text-sm text-muted-foreground mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1.5">
      <span className="font-mono text-xs">{profile.email}</span>
      {profile.display_grade_label ? (
        <>
          <span className="text-muted-foreground/40">·</span>
          <span>{profile.display_grade_label}</span>
        </>
      ) : null}

      {profile.track_label ? (
        <Pill tone="indigo">{profile.track_label}</Pill>
      ) : null}

      {profile.curriculum_label && profile.curriculum_model ? (
        <span
          className={cn(
            "inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border",
            curriculumTone[profile.curriculum_model] ??
              "border-border bg-muted text-muted-foreground",
          )}
        >
          {profile.curriculum_label}
        </span>
      ) : null}

      {profile.exam_target ? (
        <Pill tone="violet">
          <Target className="size-3" aria-hidden />
          {profile.exam_target}
        </Pill>
      ) : null}

      {profile.is_graduate && profile.graduate_mode ? (
        <Pill tone="rose">
          {profile.graduate_mode === "full_time" ? "Tam-zamanlı" : "Dershane"}
        </Pill>
      ) : null}

      {profile.track_required && profile.track_missing ? (
        <Pill tone="amber">
          <AlertTriangle className="size-3" aria-hidden />
          Alan eksik
        </Pill>
      ) : null}

      {profile.academic_year_name ? (
        <>
          <span className="text-muted-foreground/40">·</span>
          <span>
            {profile.academic_year_name}
            {profile.exam_date ? (
              <>
                {" "}
                <span className="text-muted-foreground/70">
                  ({profile.exam_label}: {formatTRDate(profile.exam_date)})
                </span>
              </>
            ) : null}
          </span>
        </>
      ) : null}

      {activePhase && activePhase.kind !== "regular" ? (
        <span
          className={cn(
            "inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border",
            phaseTone[activePhase.kind] ?? phaseTone.regular,
          )}
          title={`${activePhase.name}: ${formatTRDate(activePhase.start_date)} – ${formatTRDate(activePhase.end_date)}`}
        >
          {activePhase.kind_badge} · {activePhase.name}
        </span>
      ) : null}
    </div>
  );
}

type PillTone = "indigo" | "violet" | "rose" | "amber" | "emerald" | "muted";

function Pill({
  tone,
  children,
}: {
  tone: PillTone;
  children: React.ReactNode;
}) {
  const toneClass: Record<PillTone, string> = {
    indigo: "border-indigo-200 bg-indigo-50 text-indigo-700",
    violet: "border-violet-200 bg-violet-50 text-violet-700",
    rose: "border-rose-200 bg-rose-50 text-rose-700",
    amber: "border-amber-200 bg-amber-50 text-amber-800",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    muted: "border-border bg-muted text-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border",
        toneClass[tone],
      )}
    >
      {children}
    </span>
  );
}

function QuickActions({
  studentId,
  studentName,
  studentEmail,
  isGraduate,
  onRefresh,
  isRefreshing,
}: {
  studentId: number;
  studentName: string;
  studentEmail: string;
  isGraduate: boolean;
  onRefresh: () => void;
  isRefreshing: boolean;
}) {
  const [waOpen, setWaOpen] = React.useState(false);
  const [editOpen, setEditOpen] = React.useState(false);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => setEditOpen(true)}
        title="Öğrenci ad ve e-posta bilgisini düzenle"
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs hover:bg-muted transition"
      >
        <Pencil className="size-3.5" aria-hidden />
        Profili Düzenle
      </button>
      <EditStudentProfileDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        studentId={studentId}
        initialFullName={studentName}
        initialEmail={studentEmail}
      />
      <button
        type="button"
        onClick={() => setWaOpen(true)}
        title="Öğrenciye WhatsApp gönder"
        className="inline-flex items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 text-emerald-800 px-2.5 py-1.5 text-xs hover:bg-emerald-100 transition"
      >
        <MessageSquare className="size-3.5" aria-hidden />
        WA Gönder
      </button>
      <WaSendDialog
        open={waOpen}
        onOpenChange={setWaOpen}
        targetUserId={studentId}
        targetNameFallback={studentName}
        title={`${studentName} (Öğrenci) — WhatsApp Mesajı`}
        defaultCategory="ogrenci"
      />
      <button
        type="button"
        onClick={onRefresh}
        disabled={isRefreshing}
        title="Veriyi yeniden çek"
        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted disabled:opacity-50 transition"
      >
        {isRefreshing ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <RefreshCw className="size-3.5" aria-hidden />
        )}
        Yenile
      </button>
      <ActionLink
        href={`/teacher/students/${studentId}/promote`}
        icon={<ArrowUpCircle className="size-3.5" aria-hidden />}
        label={isGraduate ? "Yeni Yıl" : "Sınıf Yükselt"}
        title={
          isGraduate
            ? "Yeni öğretim yılı için akademik yıl, alan ve çalışma şeklini güncelle"
            : "Akademik yıl başında öğrenciyi bir sonraki sınıfa taşı"
        }
        tone="violet"
      />
      <ActionLink
        href={`/teacher/students/${studentId}/goals`}
        icon={<Target className="size-3.5" aria-hidden />}
        label="Hedefler"
        title="Sınav, ders ve operasyonel hedef ağacını yönet"
        tone="amber"
      />
      <ActionLink
        href={`/teacher/students/${studentId}/review`}
        icon={<Brain className="size-3.5" aria-hidden />}
        label="Tekrar"
        title="Aralıklı tekrar (FSRS) kartlarını yönet"
        tone="emerald"
      />
      <ActionLink
        href={`/teacher/students/${studentId}/dna`}
        icon={<Dna className="size-3.5" aria-hidden />}
        label="DNA"
        title="Çalışma DNA profili + tükenmişlik analizi"
        tone="sky"
      />
      <ActionLink
        href={`/teacher/students/${studentId}/focus`}
        icon={<Timer className="size-3.5" aria-hidden />}
        label="Odak"
        title="Pomodoro istatistikleri + rozetler"
        tone="rose"
      />
      <Link
        href={`/teacher/students/${studentId}/week`}
        className="inline-flex items-center gap-1.5 rounded-md bg-foreground text-background px-3 py-1.5 text-xs font-medium hover:bg-foreground/90 transition"
      >
        <CalendarRange className="size-3.5" aria-hidden />
        Haftalık Program
      </Link>
    </div>
  );
}

function ActionLink({
  href,
  icon,
  label,
  title,
  tone,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  title: string;
  tone: "violet" | "amber" | "emerald" | "sky" | "rose";
}) {
  const toneClass: Record<typeof tone, string> = {
    violet: "border-violet-200 text-violet-700 hover:bg-violet-50",
    amber: "border-amber-200 text-amber-800 hover:bg-amber-50",
    emerald: "border-emerald-200 text-emerald-700 hover:bg-emerald-50",
    sky: "border-sky-200 text-sky-700 hover:bg-sky-50",
    rose: "border-rose-200 text-rose-700 hover:bg-rose-50",
  };
  return (
    <Link
      href={href}
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs transition",
        toneClass[tone],
      )}
    >
      {icon}
      {label}
    </Link>
  );
}

// =============================================================================
// Durum Özeti — bir bakışta program durumu + linkli uyarılar (kanıt sayfaları)
// =============================================================================

// Açık-zemin ton sınıfları (koyu temada da okunur — explicit, purge-safe)
const SUMMARY_TONE: Record<string, { card: string; title: string; text: string; icon: string }> = {
  red: { card: "border-rose-300 bg-rose-50 hover:bg-rose-100", title: "text-rose-900", text: "text-rose-800", icon: "text-rose-600" },
  amber: { card: "border-amber-300 bg-amber-50 hover:bg-amber-100", title: "text-amber-900", text: "text-amber-800", icon: "text-amber-600" },
  green: { card: "border-emerald-300 bg-emerald-50 hover:bg-emerald-100", title: "text-emerald-900", text: "text-emerald-800", icon: "text-emerald-600" },
};

interface SummaryRow {
  tone: "red" | "amber" | "green";
  title: string;
  detail: string;
  link: string;
  linkLabel: string;
  good?: boolean;
}

function StatusSummary({
  studentId,
  data,
}: {
  studentId: number;
  data: TeacherStudentDetailResponse;
}) {
  const ps = data.program_summary;
  const base = `/teacher/students/${studentId}`;
  // GÖREV-BAZLI (etkinlik/"Diğer" dahil) — "X/Y görev" tamamlanan/toplam görev.
  const todayTotal = ps.today_tasks_total ?? 0;
  const todayDone = ps.today_tasks_done ?? 0;
  const weekTotal = ps.week_tasks_total ?? 0;
  const weekDone = ps.week_tasks_done ?? 0;
  const todayPct = todayTotal > 0 ? Math.round((ps.today_task_pct ?? 0) * 100) : null;
  const weekPct = weekTotal > 0 ? Math.round((ps.week_task_pct ?? 0) * 100) : null;
  const consistency = Math.round((ps.consistency_7d ?? 0) * 100);
  const hitRate = Math.round((ps.hit_rate_7d ?? 0) * 100);
  const items = data.warning_items ?? [];
  const lvl = data.worst_warning_level;

  // İyi giden (başarı) sinyalleri — program_summary'den türetilir, linkli.
  const positives: SummaryRow[] = [];
  if (todayTotal > 0 && todayDone >= todayTotal) {
    positives.push({ tone: "green", title: "Bugünkü programı tamamladı",
      detail: `${todayDone}/${todayTotal} görev bitti`,
      link: `${base}/day`, linkLabel: "Günü gör", good: true });
  } else if (todayTotal > 0 && (todayPct ?? 0) >= 50) {
    positives.push({ tone: "green", title: "Bugün iyi gidiyor",
      detail: `${todayDone}/${todayTotal} görev (%${todayPct})`,
      link: `${base}/day`, linkLabel: "Günü gör", good: true });
  }
  if (weekTotal > 0 && (weekPct ?? 0) >= 70) {
    positives.push({ tone: "green", title: `Haftalık tempo iyi (%${weekPct})`,
      detail: `${weekDone}/${weekTotal} görev tamamlandı`,
      link: `${base}/week`, linkLabel: "Haftalık planı gör", good: true });
  }
  if (consistency >= 80) {
    positives.push({ tone: "green", title: `Tutarlı çalışıyor (%${consistency})`,
      detail: "Son 7 günün çoğunda aktif", link: `${base}/dna`, linkLabel: "Analizi gör", good: true });
  }
  if (hitRate >= 80) {
    positives.push({ tone: "green", title: `Hedefleri tutturuyor (%${hitRate})`,
      detail: "Planlanan görevlerin büyük kısmı tamamlanıyor", link: `${base}/week`, linkLabel: "Planı gör", good: true });
  }

  const warnings: SummaryRow[] = items.map((w) => ({
    tone: (w.level === "red" ? "red" : w.level === "amber" ? "amber" : "green"),
    title: w.title, detail: w.detail, link: w.link, linkLabel: w.link_label,
  }));

  const verdict = {
    red: { cls: "border-rose-300 bg-rose-50 text-rose-900", title: "Acil müdahale gerekiyor" },
    amber: { cls: "border-amber-300 bg-amber-50 text-amber-900", title: "Dikkat gerekiyor" },
    green: { cls: "border-emerald-300 bg-emerald-50 text-emerald-900", title: "Program yolunda" },
  }[lvl] ?? { cls: "border-slate-300 bg-slate-50 text-slate-900", title: "Durum" };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Durum Özeti</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className={cn("rounded-lg border p-3", verdict.cls)}>
          <p className="font-semibold">{verdict.title}</p>
          <p className="mt-0.5 text-sm opacity-90">
            Bugün <strong>{todayDone}/{todayTotal}</strong> görev
            {todayPct != null ? ` (%${todayPct})` : ""} ·{" "}
            Son 7 gün <strong>{weekDone}/{weekTotal}</strong> görev
            {weekPct != null ? ` (%${weekPct})` : ""} ·{" "}
            Tutarlılık %{consistency}
          </p>
        </div>

        {warnings.length > 0 ? (
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Dikkat gerektirenler
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {warnings.map((w, i) => <SummaryCard key={`w-${i}`} row={w} />)}
            </div>
          </div>
        ) : null}

        {positives.length > 0 ? (
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              İyi giden
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {positives.map((p, i) => <SummaryCard key={`p-${i}`} row={p} />)}
            </div>
          </div>
        ) : null}

        {warnings.length === 0 && positives.length === 0 ? (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
            Henüz yeterli veri yok — program oluşturuldukça durum burada özetlenir.{" "}
            <Link href={`${base}/week`} className="font-medium underline underline-offset-4">
              Haftalık planı aç →
            </Link>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SummaryCard({ row }: { row: SummaryRow }) {
  const t = SUMMARY_TONE[row.tone] ?? SUMMARY_TONE.amber;
  const Icon = row.good ? CheckCircle2 : AlertTriangle;
  return (
    <Link href={row.link} className={cn("block rounded-lg border p-3 transition", t.card)}>
      <div className="flex items-start gap-2">
        <Icon className={cn("mt-0.5 size-4 shrink-0", t.icon)} aria-hidden />
        <div className="min-w-0">
          <p className={cn("text-sm font-semibold", t.title)}>{row.title}</p>
          <p className={cn("mt-0.5 text-xs", t.text)}>{row.detail}</p>
          <p className={cn("mt-1.5 text-xs font-medium", t.title)}>{row.linkLabel} →</p>
        </div>
      </div>
    </Link>
  );
}

// =============================================================================
// Görev / Test / Deneme dağılımı — gorev_stats çekirdeğinden
// Görev birincil (manşet); test (soru bankası) ile deneme AYRI; etkinlik ayrı.
// =============================================================================

function GorevBreakdownCard({
  today,
  week,
}: {
  today: GorevBreakdown | null;
  week: GorevBreakdown | null;
}) {
  const [scope, setScope] = React.useState<"today" | "week">("today");
  const g = scope === "today" ? today : week;
  if (!g) return null;

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base">Görev / Test / Deneme</CardTitle>
        <div className="inline-flex rounded-md border border-border overflow-hidden text-xs">
          <button
            type="button"
            onClick={() => setScope("today")}
            className={cn(
              "px-2.5 py-1",
              scope === "today"
                ? "bg-[#117A86] text-white"
                : "bg-background text-muted-foreground hover:bg-muted",
            )}
          >
            Bugün
          </button>
          <button
            type="button"
            onClick={() => setScope("week")}
            className={cn(
              "px-2.5 py-1 border-l border-border",
              scope === "week"
                ? "bg-[#117A86] text-white"
                : "bg-background text-muted-foreground hover:bg-muted",
            )}
          >
            Son 7 gün
          </button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Manşet — GÖREV (etkinlik dahil) */}
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-sm">
            <strong className="tabular-nums">
              {g.gorev_done}/{g.gorev_total}
            </strong>{" "}
            görev tamamlandı{" "}
            <span className="text-muted-foreground">(%{g.gorev_pct})</span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            <strong className="text-foreground tabular-nums">
              {g.test_completed}/{g.test_planned}
            </strong>{" "}
            test çözüldü
            {g.deneme_count > 0 && (
              <>
                {" · "}
                <strong className="text-foreground tabular-nums">
                  {g.deneme_done}/{g.deneme_count}
                </strong>{" "}
                deneme
              </>
            )}
            {g.etkinlik_count > 0 && (
              <>
                {" · "}
                <strong className="text-foreground tabular-nums">
                  {g.etkinlik_done}/{g.etkinlik_count}
                </strong>{" "}
                etkinlik
              </>
            )}
          </p>
        </div>

        {/* Ders bazında TEST görevleri */}
        {g.subjects.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Ders bazında (test görevleri)
            </p>
            <ul className="space-y-1">
              {g.subjects.map((s) => (
                <li
                  key={s.subject_name}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <span className="truncate">{s.subject_name}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    <strong
                      className={cn(
                        s.pct >= 70
                          ? "text-emerald-700"
                          : s.pct >= 40
                            ? "text-amber-700"
                            : "text-rose-700",
                      )}
                    >
                      {s.gorev_done}/{s.gorev_total} görev
                    </strong>{" "}
                    · {s.test_completed}/{s.test_planned} test
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Denemeler — AYRI başlık (testlerle karışmaz) */}
        {g.denemeler.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Denemeler
            </p>
            <ul className="space-y-1">
              {g.denemeler.map((d, i) => (
                <li
                  key={`${d.title}-${i}`}
                  className="flex items-center justify-between gap-2 text-sm"
                >
                  <span className="truncate">
                    {d.done ? "✓ " : ""}
                    {d.title}
                    {d.subject ? (
                      <span className="text-muted-foreground"> · {d.subject}</span>
                    ) : null}
                  </span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                    {d.completed}/{d.planned}{" "}
                    {d.category === "tam_deneme" ? "soru" : "deneme"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {g.gorev_total === 0 && (
          <p className="text-sm text-muted-foreground italic">
            {scope === "today"
              ? "Bugün için planlanmış görev yok."
              : "Son 7 günde planlanmış görev yok."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Metrik şeridi (5 KPI — Jinja metrics_strip.html parite)
// =============================================================================

function MetricsStrip({
  today,
  todayCompleted,
  todayPlanned,
  week,
  weekCompleted,
  weekPlanned,
  rate7d,
  consistency,
  hitRate,
  studentId,
}: {
  today: number;
  todayCompleted: number;
  todayPlanned: number;
  week: number;
  weekCompleted: number;
  weekPlanned: number;
  rate7d: number;
  consistency: number;
  hitRate: number;
  studentId: number;
}) {
  const base = `/teacher/students/${studentId}`;
  return (
    <section className="grid grid-cols-2 lg:grid-cols-5 gap-3">
      <Kpi
        label="Bugün"
        value={`%${today}`}
        sub={`${todayCompleted}/${todayPlanned}`}
        href={`${base}/day`}
      />
      <Kpi
        label="Son 7 Gün"
        value={`%${week}`}
        sub={`${weekCompleted}/${weekPlanned}`}
        href={`${base}/week`}
      />
      <Kpi
        label="Hız (7g)"
        value={rate7d.toFixed(1)}
        sub="test / gün"
        icon={<Activity className="size-3.5 text-muted-foreground" aria-hidden />}
        href={`${base}/dna`}
      />
      <Kpi
        label="Tutarlılık"
        value={`%${consistency}`}
        sub="son 7 günün kaçında aktif"
        emphasize={
          consistency >= 80 ? "good" : consistency >= 50 ? "warn" : "bad"
        }
        href={`${base}/dna`}
      />
      <Kpi
        label="Hedef Tutturma"
        value={`%${hitRate}`}
        sub="planlanan→tamamlanan (7g)"
        emphasize={hitRate >= 80 ? "good" : hitRate >= 50 ? "warn" : "bad"}
        href={`${base}/week`}
      />
    </section>
  );
}

function Kpi({
  label,
  value,
  sub,
  emphasize,
  icon,
  href,
}: {
  label: string;
  value: string | number;
  sub?: string;
  emphasize?: "good" | "warn" | "bad";
  icon?: React.ReactNode;
  href?: string;
}) {
  const valueClass = {
    good: "text-emerald-600",
    warn: "text-amber-600",
    bad: "text-rose-600",
  }[emphasize ?? ("none" as never)];
  const inner = (
    <CardContent className="p-4 space-y-1">
      <p className="text-xs uppercase tracking-wide text-muted-foreground inline-flex items-center gap-1.5">
        {icon}
        {label}
      </p>
      <p className={cn("text-2xl font-semibold tabular-nums", valueClass)}>{value}</p>
      {sub ? <p className="text-xs text-muted-foreground">{sub}</p> : null}
    </CardContent>
  );
  if (href) {
    return (
      <Card className="transition hover:border-cyan-300 hover:shadow-sm">
        <Link href={href} className="block">{inner}</Link>
      </Card>
    );
  }
  return <Card>{inner}</Card>;
}

// =============================================================================
// Koçluk Takvimi — Anchor edit kartı
// =============================================================================

function AnchorEditCard({
  studentId,
  weekAnchor,
  isManual,
}: {
  studentId: number;
  weekAnchor: string | null;
  isManual: boolean;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base inline-flex items-center gap-2">
          <CalendarRange className="size-4 text-muted-foreground" aria-hidden />
          Koçluk Takvimi — Hafta Anchor&apos;ı
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground leading-relaxed">
          Öğrencinin 7 günlük programı bu tarihten itibaren her hafta tekrar
          başlar. Koçluk gününüz değiştiyse buradan güncelleyin — haftalık
          görünüm bir sonraki açılışta otomatik yeni güne hizalanır.
        </p>
        {weekAnchor ? (
          <p className="text-sm">
            <span className="text-muted-foreground">Mevcut:</span>{" "}
            <b>{formatTRDate(weekAnchor)}</b>{" "}
            <span className="text-muted-foreground">
              ({TR_WEEKDAYS[weekdayFromIso(weekAnchor)]})
            </span>
            {isManual ? (
              <Pill tone="indigo">manuel ayarlı</Pill>
            ) : (
              <Pill tone="muted">otomatik</Pill>
            )}
          </p>
        ) : (
          <p className="text-sm italic text-muted-foreground">
            Henüz görev yok — anchor da yok.
          </p>
        )}
        {/* Sıfır mount: AnchorEditForm yalnızca aktif kart açıkken state taşır */}
        <AnchorEditForm
          key={weekAnchor ?? "empty"}
          studentId={studentId}
          weekAnchor={weekAnchor}
          isManual={isManual}
        />
      </CardContent>
    </Card>
  );
}

function AnchorEditForm({
  studentId,
  weekAnchor,
  isManual,
}: {
  studentId: number;
  weekAnchor: string | null;
  isManual: boolean;
}) {
  const [date, setDate] = React.useState(weekAnchor ?? "");
  const mut = useSetWeekAnchor(studentId);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!date) return;
    if (
      !window.confirm(
        `Hafta anchor'ı ${formatTRDate(date)} olarak ayarlansın? Tüm haftalık bloklar buradan itibaren yeniden hesaplanır.`,
      )
    ) {
      return;
    }
    mut.mutate({ body: { anchor: date } });
  }
  function onClear() {
    if (
      !window.confirm(
        "Manuel anchor silinsin? Otomatik (en eski görev tarihi) fallback devreye girer.",
      )
    ) {
      return;
    }
    mut.mutate({ body: { anchor: "clear" } });
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-[11px] text-muted-foreground mb-0.5">
            Yeni anchor tarihi
          </label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
            className="px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <button
          type="submit"
          disabled={mut.isPending || !date}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-foreground text-background text-xs font-medium hover:bg-foreground/90 disabled:opacity-50 transition"
        >
          {mut.isPending ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : null}
          Anchor&apos;ı bu tarihe ayarla
        </button>
      </form>
      {isManual ? (
        <button
          type="button"
          onClick={onClear}
          disabled={mut.isPending}
          className="px-3 py-1.5 rounded-md border border-border text-xs text-muted-foreground hover:bg-muted disabled:opacity-50 transition"
        >
          Sıfırla
        </button>
      ) : null}
    </div>
  );
}

// =============================================================================
// Yardımcı: hash tab + tarih
// =============================================================================

function subscribeHash(callback: () => void): () => void {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}

function getHashTab(): TabKey {
  const h = window.location.hash.replace(/^#/, "");
  return isValidTab(h) ? h : "summary";
}

function useHashTab(): TabKey {
  return React.useSyncExternalStore(subscribeHash, getHashTab, () => "summary");
}

const TR_WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function formatTRDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${String(d).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

function weekdayFromIso(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return 0;
  // JS getDay: 0=Sun..6=Sat → istediğimiz 0=Mon..6=Sun
  const jsDow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return jsDow === 0 ? 6 : jsDow - 1;
}

// =============================================================================
// EditStudentProfileDialog — koç ad + e-posta düzenleme
// (M2: koç öğrenci e-postasını güncelleyebilir; şifre dokunulmaz)
// =============================================================================

function EditStudentProfileDialog({
  open,
  onClose,
  studentId,
  initialFullName,
  initialEmail,
}: {
  open: boolean;
  onClose: () => void;
  studentId: number;
  initialFullName: string;
  initialEmail: string;
}) {
  if (!open) return null;
  return (
    <EditStudentProfileDialogInner
      onClose={onClose}
      studentId={studentId}
      initialFullName={initialFullName}
      initialEmail={initialEmail}
    />
  );
}

function EditStudentProfileDialogInner({
  onClose,
  studentId,
  initialFullName,
  initialEmail,
}: {
  onClose: () => void;
  studentId: number;
  initialFullName: string;
  initialEmail: string;
}) {
  const [fullName, setFullName] = React.useState(initialFullName);
  const [email, setEmail] = React.useState(initialEmail);
  const mut = usePatchStudent(studentId);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body: { full_name?: string; email?: string } = {};
    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();
    if (trimmedName !== initialFullName.trim()) body.full_name = trimmedName;
    if (trimmedEmail.toLowerCase() !== initialEmail.toLowerCase())
      body.email = trimmedEmail;
    if (Object.keys(body).length === 0) {
      onClose();
      return;
    }
    mut.mutate(
      { body },
      {
        onSuccess: () => onClose(),
      },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Profili Düzenle</DialogTitle>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-medium mb-1.5">
              Ad Soyad
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full px-3 py-2 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              required
            />
          </div>
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-medium mb-1.5">
              E-posta
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-input bg-background rounded-md text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
              required
            />
            <p className="text-[11px] text-muted-foreground mt-1.5">
              E-posta değişirse öğrencinin yeni adresi sistem tarafından
              doğrulanmamış sayılır. Şifre değişmez, oturum kesilmez.
            </p>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm rounded-md border border-border hover:bg-muted transition"
            >
              Vazgeç
            </button>
            <button
              type="submit"
              disabled={mut.isPending}
              className="px-4 py-2 text-sm rounded-md bg-foreground text-background font-medium hover:bg-foreground/90 disabled:opacity-40 transition inline-flex items-center gap-2"
            >
              {mut.isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : null}
              Kaydet
            </button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
