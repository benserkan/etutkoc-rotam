"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  AlertOctagon,
  AlertTriangle,
  CalendarRange,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  FileSpreadsheet,
  Inbox,
  KeyRound,
  Loader2,
  MessageSquareMore,
  MoreHorizontal,
  PauseCircle,
  PlayCircle,
  UserRound,
  Users,
  X,
} from "lucide-react";

import { useTeacherStudents } from "@/lib/hooks/use-teacher-queries";
import type { TeacherStudentsListParams } from "@/lib/api/teacher";
import {
  useDeactivateStudent,
  useReactivateStudent,
  useResetStudentPassword,
  useSetStudentsClassGroup,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  StudentListSummary,
  StudentResetPasswordResult,
  TeacherStudentListItem,
  TeacherStudentListResponse,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
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
import {
  Select,
  StudentsFilterBar,
  useApplyParam,
  type FilterValues,
} from "@/components/teacher/students-filter-bar";
import { StudentCreateButton } from "@/components/teacher/student-create-modal";
import { cn } from "@/lib/utils";

interface Props {
  initial: TeacherStudentListResponse;
  initialFilters: FilterValues;
  initialPage: number;
}

// Masaüstü tablo kolonları — başlık satırı ile satırlar AYNI şablonu kullanır.
const COLS =
  "md:grid md:grid-cols-[minmax(0,2.6fr)_minmax(0,1fr)_minmax(0,1.1fr)_minmax(0,1.1fr)_minmax(0,0.9fr)_9.5rem] md:items-center md:gap-4";

export function StudentsListClient({ initial, initialFilters, initialPage }: Props) {
  const searchParams = useSearchParams();

  const filters = readFilters(searchParams, initialFilters);
  const page = readPage(searchParams, initialPage);

  const params: TeacherStudentsListParams = React.useMemo(
    () => ({
      q: filters.q || undefined,
      grade_level: filters.grade_level ? Number(filters.grade_level) : undefined,
      risk: filters.risk,
      status: filters.status,
      class_group: filters.class_group || undefined,
      page,
      page_size: filters.page_size,
    }),
    [filters.q, filters.grade_level, filters.risk, filters.status, filters.class_group, filters.page_size, page],
  );

  const q = useTeacherStudents(
    params,
    isSameAsInitial(filters, initialFilters, page, initialPage) ? initial : undefined,
  );
  const data = q.data;
  const isLoading = q.isLoading && !data;
  const [selected, setSelected] = React.useState<Set<number>>(new Set());
  const pageIds = (data?.items ?? []).map((s) => s.id);
  const allOnPage = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const someOnPage = pageIds.some((id) => selected.has(id));
  const groupNames = (data?.class_groups ?? [])
    .map((g) => g.class_group)
    .filter((g): g is string => !!g);

  function toggle(id: number, on: boolean) {
    const next = new Set(selected);
    if (on) next.add(id);
    else next.delete(id);
    setSelected(next);
  }

  function toggleAll(on: boolean) {
    const next = new Set(selected);
    for (const id of pageIds) {
      if (on) next.add(id);
      else next.delete(id);
    }
    setSelected(next);
  }

  const total = data?.total ?? 0;

  return (
    <div className={cn("space-y-5", selected.size > 0 && "pb-24")}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight font-display">Öğrenciler</h1>
          <p className="mt-0.5 text-sm text-muted-foreground" aria-live="polite">
            {isLoading
              ? "Yükleniyor…"
              : `${total} öğrenci ${statusWord(filters.status)}`}
            {q.isFetching && !isLoading ? (
              <Loader2 className="ml-2 inline size-3.5 animate-spin align-[-2px]" aria-label="güncelleniyor" />
            ) : null}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <FileSpreadsheet className="size-4" aria-hidden />
                Toplu işlemler
                <ChevronDown className="size-4 opacity-60" aria-hidden />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64">
              <DropdownMenuItem asChild>
                <Link href="/teacher/students/import" className="flex items-start gap-2">
                  <Users className="mt-0.5" aria-hidden />
                  <span>
                    <span className="block font-medium">Listeden toplu ekle</span>
                    <span className="block text-xs text-muted-foreground">
                      Excel/CSV dosyasıyla çok sayıda öğrenci
                    </span>
                  </span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a href="/api/v2/teacher/csv/export/students" className="flex items-start gap-2">
                  <Download className="mt-0.5" aria-hidden />
                  <span>
                    <span className="block font-medium">Öğrenci listesini indir</span>
                    <span className="block text-xs text-muted-foreground">Excel&apos;de açılır (CSV)</span>
                  </span>
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <StudentCreateButton />
        </div>
      </header>

      {filters.status !== "pasif" && data?.summary ? (
        <StatusTiles summary={data.summary} risk={filters.risk} />
      ) : null}

      <StudentsFilterBar initial={filters} classGroups={data?.class_groups ?? []} />

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {isLoading ? (
          <SkeletonRows />
        ) : !data || data.items.length === 0 ? (
          <EmptyState status={filters.status} filtered={hasFilter(filters)} />
        ) : (
          <>
            <div
              className={cn(
                "hidden border-b border-border bg-muted/50 px-4 py-2.5 text-xs font-medium text-muted-foreground",
                COLS,
                "md:grid",
              )}
            >
              <label className="flex items-center gap-3">
                <input
                  type="checkbox"
                  className="size-4 accent-cyan-700"
                  checked={allOnPage}
                  ref={(el) => {
                    if (el) el.indeterminate = !allOnPage && someOnPage;
                  }}
                  onChange={(e) => toggleAll(e.target.checked)}
                  aria-label="Bu sayfadaki tüm öğrencileri seç"
                />
                Öğrenci
              </label>
              <span>Sınıf · Şube</span>
              <span title="Bugün tamamlanan / toplam görev (etkinlik dahil)">Bugün</span>
              <span title="Son 7 günde (bugün dahil) tamamlanan görev oranı">Son 7 gün</span>
              <span>Son görülme</span>
              <span className="sr-only">İşlemler</span>
            </div>
            <label className="flex items-center gap-3 border-b border-border px-4 py-2 text-xs text-muted-foreground md:hidden">
              <input
                type="checkbox"
                className="size-4 accent-cyan-700"
                checked={allOnPage}
                onChange={(e) => toggleAll(e.target.checked)}
                aria-label="Bu sayfadaki tüm öğrencileri seç"
              />
              Tümünü seç
            </label>
            <ul className="divide-y divide-border">
              {data.items.map((s) => (
                <StudentRow
                  key={s.id}
                  s={s}
                  checked={selected.has(s.id)}
                  onCheck={(on) => toggle(s.id, on)}
                />
              ))}
            </ul>
          </>
        )}
      </section>

      {data && data.items.length > 0 ? (
        <Pager
          page={data.page}
          pageSize={filters.page_size}
          total={data.total}
          hasNext={data.has_next}
        />
      ) : null}

      {selected.size > 0 ? (
        <ClassGroupBar
          selectedIds={Array.from(selected)}
          groupNames={groupNames}
          onDone={() => setSelected(new Set())}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- Özet kutuları

function StatusTiles({
  summary,
  risk,
}: {
  summary: StudentListSummary;
  risk: FilterValues["risk"];
}) {
  const { apply } = useApplyParam();
  const setRisk = (v: FilterValues["risk"]) =>
    apply((sp) => {
      if (v === "all" || v === risk) sp.delete("risk");
      else sp.set("risk", v);
    });

  const tiles: Array<{
    key: "critical" | "medium" | "ok";
    count: number;
    title: string;
    hint: string;
    icon: React.ComponentType<{ className?: string }>;
    tone: string;
    active: string;
  }> = [
    {
      key: "critical",
      count: summary.critical,
      title: "Kritik",
      hint: "Hemen ilgilen",
      icon: AlertOctagon,
      tone: "text-rose-700 dark:text-rose-300",
      active: "border-rose-500 ring-2 ring-rose-500/30 bg-rose-50 dark:bg-rose-500/10",
    },
    {
      key: "medium",
      count: summary.warning,
      title: "Uyarı",
      hint: "Yakından takip et",
      icon: AlertTriangle,
      tone: "text-amber-700 dark:text-amber-300",
      active: "border-amber-500 ring-2 ring-amber-500/30 bg-amber-50 dark:bg-amber-500/10",
    },
    {
      key: "ok",
      count: summary.ok,
      title: "Yolunda",
      hint: summary.paused > 0 ? `${summary.paused} öğrenci molada` : "Programı yürüyor",
      icon: CheckCircle2,
      tone: "text-emerald-700 dark:text-emerald-300",
      active: "border-emerald-500 ring-2 ring-emerald-500/30 bg-emerald-50 dark:bg-emerald-500/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="status-tiles">
      {tiles.map((t) => {
        const on =
          risk === t.key ||
          (t.key === "medium" && (risk === "high" || risk === "at_risk")) ||
          (t.key === "critical" && risk === "at_risk");
        const Icon = t.icon;
        return (
          <button
            key={t.key}
            type="button"
            onClick={() => setRisk(t.key)}
            aria-pressed={on}
            data-testid={`status-tile-${t.key}`}
            className={cn(
              "group rounded-xl border bg-card p-3.5 text-left transition-colors hover:border-foreground/30",
              on ? t.active : "border-border",
            )}
          >
            <span className={cn("flex items-center gap-1.5 text-sm font-medium", t.tone)}>
              <Icon className="size-4" aria-hidden />
              {t.title}
            </span>
            <span className="mt-1 flex items-baseline gap-1.5">
              <span className="text-2xl font-semibold tabular-nums text-foreground">{t.count}</span>
              <span className="text-xs text-muted-foreground">öğrenci</span>
            </span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
              {on ? "Süzgeç açık · kaldırmak için tıkla" : t.hint}
            </span>
          </button>
        );
      })}
      <Link
        href="/teacher/requests"
        data-testid="status-tile-requests"
        className="rounded-xl border border-border bg-card p-3.5 transition-colors hover:border-foreground/30"
      >
        <span className="flex items-center gap-1.5 text-sm font-medium text-cyan-700 dark:text-cyan-300">
          <MessageSquareMore className="size-4" aria-hidden />
          Bekleyen talep
        </span>
        <span className="mt-1 flex items-baseline gap-1.5">
          <span className="text-2xl font-semibold tabular-nums text-foreground">
            {summary.pending_requests}
          </span>
          <span className="text-xs text-muted-foreground">öğrenci</span>
        </span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {summary.pending_requests > 0 ? "Yanıtlamak için aç" : "Yanıt bekleyen yok"}
        </span>
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------- Satır

function StudentRow({
  s,
  checked,
  onCheck,
}: {
  s: TeacherStudentListItem;
  checked: boolean;
  onCheck: (on: boolean) => void;
}) {
  const wTot = s.week_gorev_total ?? 0;
  const wDone = s.week_gorev_done ?? 0;
  const weekPct = wTot > 0 ? Math.round((wDone / wTot) * 100) : null;
  const dim = !s.is_active;
  const risk = s.risk_level ?? null;
  const done = s.today_gorev_done ?? 0;
  const tot = s.today_gorev_total ?? 0;
  const showReason =
    s.is_active && !s.is_paused && s.worst_warning_level !== "green" && !!s.worst_warning_title;

  return (
    <li
      className={cn(
        "group relative px-4 py-3 transition-colors hover:bg-muted/50",
        checked && "bg-cyan-50/60 dark:bg-cyan-500/10",
        COLS,
      )}
      data-risk={risk ?? "inactive"}
    >
      {/* Risk şeridi — kutular ve süzgeçle AYNI seviye */}
      {risk === "critical" || risk === "warning" ? (
        <span
          aria-hidden
          className={cn(
            "absolute inset-y-0 left-0 w-1",
            risk === "critical" ? "bg-rose-500" : "bg-amber-500",
          )}
        />
      ) : null}

      {/* Öğrenci */}
      <div className="flex min-w-0 items-start gap-3">
        <input
          type="checkbox"
          className="mt-2.5 size-4 shrink-0 accent-cyan-700"
          checked={checked}
          onChange={(e) => onCheck(e.target.checked)}
          aria-label={`${s.full_name} seç`}
          data-testid="student-select"
        />
        <Avatar name={s.full_name} risk={risk} dim={dim} />
        <div className={cn("min-w-0 flex-1", dim && "opacity-60")}>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link
              href={`/teacher/students/${s.id}`}
              className="font-medium text-foreground break-words hover:underline"
            >
              {s.full_name}
            </Link>
            {!s.is_active ? (
              <Badge className="bg-slate-500">pasif</Badge>
            ) : s.is_paused ? (
              <Badge className="bg-amber-700">molada</Badge>
            ) : null}
            {s.has_pending_request ? (
              <Link href={`/teacher/requests?student_id=${s.id}`}>
                <Badge className="bg-cyan-700 hover:bg-cyan-800">talep bekliyor</Badge>
              </Link>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground break-all">{s.email}</p>
          {showReason ? (
            <p
              className={cn(
                "mt-0.5 text-xs font-medium break-words",
                s.worst_warning_level === "red"
                  ? "text-rose-700 dark:text-rose-300"
                  : "text-amber-700 dark:text-amber-300",
              )}
              title={s.worst_warning_detail ?? undefined}
            >
              {s.worst_warning_title}
            </p>
          ) : null}
        </div>
      </div>

      {/* Sınıf · Şube */}
      <div
        className={cn(
          "mt-2 flex flex-wrap items-center gap-1.5 pl-[4.25rem] text-sm text-muted-foreground md:mt-0 md:pl-0",
          dim && "opacity-60",
        )}
      >
        <span>{s.grade_level !== null ? `${s.grade_level}. sınıf` : "Mezun"}</span>
        {s.class_group ? (
          <span
            className="rounded-md bg-slate-700 px-1.5 py-0.5 text-[11px] font-medium text-white"
            data-testid="class-group-badge"
          >
            {s.class_group}
          </span>
        ) : null}
      </div>

      {/* Bugün + Son 7 gün + son giriş: mobilde tek satırda mini istatistik */}
      <div className={cn("mt-2 grid grid-cols-3 gap-3 pl-[4.25rem] md:contents", dim && "opacity-60")}>
        <Metric label="Bugün">
          {tot > 0 ? (
            <>
              <span className="text-sm tabular-nums text-foreground">
                {done}/{tot} <span className="text-muted-foreground">görev</span>
              </span>
              <Bar pct={Math.round((done / tot) * 100)} />
            </>
          ) : (
            <span className="text-sm text-muted-foreground">Görev yok</span>
          )}
        </Metric>
        <Metric label="Son 7 gün">
          {weekPct !== null ? (
            <>
              <span className="text-sm tabular-nums text-foreground" title={`${wDone}/${wTot} görev tamamlandı`}>
                %{weekPct}{" "}
                <span className="hidden text-muted-foreground md:inline">
                  · {wDone}/{wTot}<span className="hidden lg:inline"> görev</span>
                </span>
              </span>
              <Bar pct={weekPct} />
            </>
          ) : (
            <span className="text-sm text-muted-foreground">Program yok</span>
          )}
        </Metric>
        <Metric label="Son görülme">
          <span className="text-sm text-foreground" title={s.last_login_at ?? undefined}>
            {lastLoginLabel(s.last_login_at)}
          </span>
        </Metric>
      </div>

      {/* İşlemler */}
      <div className="mt-3 flex items-center justify-end gap-2 md:mt-0">
        <Button asChild variant="outline" size="sm">
          <Link href={`/teacher/students/${s.id}/day`}>
            <CalendarRange className="size-4" aria-hidden />
            Program
          </Link>
        </Button>
        <StudentRowActions student={s} />
      </div>
    </li>
  );
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <span className="block text-[11px] text-muted-foreground md:hidden">{label}</span>
      {children}
    </div>
  );
}

function Bar({ pct }: { pct: number }) {
  const w = Math.max(0, Math.min(100, pct));
  const tone = w >= 70 ? "bg-emerald-500" : w >= 40 ? "bg-amber-500" : "bg-rose-500";
  return (
    <span className="mt-1 block h-1.5 w-full max-w-[8rem] overflow-hidden rounded-full bg-muted">
      <span className={cn("block h-full rounded-full", tone)} style={{ width: `${w}%` }} />
    </span>
  );
}

function Badge({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-block rounded-full px-2 py-0.5 text-[11px] font-medium leading-4 text-white",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Avatar({
  name,
  risk,
  dim,
}: {
  name: string;
  risk: "critical" | "warning" | "ok" | null;
  dim: boolean;
}) {
  const initials = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toLocaleUpperCase("tr-TR"))
    .join("");
  const ring =
    risk === "critical"
      ? "ring-rose-500"
      : risk === "warning"
        ? "ring-amber-500"
        : risk === "ok"
          ? "ring-emerald-500"
          : "ring-slate-300 dark:ring-slate-600";
  return (
    <span
      aria-hidden
      className={cn(
        "grid size-9 shrink-0 place-items-center rounded-full bg-slate-700 text-xs font-semibold text-white ring-2 ring-offset-2 ring-offset-card",
        ring,
        dim && "opacity-60",
      )}
    >
      {initials || "?"}
    </span>
  );
}

function StudentRowActions({ student }: { student: TeacherStudentListItem }) {
  const [resetOpen, setResetOpen] = React.useState(false);
  const [resetResult, setResetResult] = React.useState<StudentResetPasswordResult | null>(null);
  const [endOpen, setEndOpen] = React.useState(false);

  const deactivate = useDeactivateStudent(student.id);
  const reactivate = useReactivateStudent(student.id);
  const resetPwd = useResetStudentPassword(student.id);

  function confirmEnd() {
    deactivate.mutate(undefined, { onSuccess: () => setEndOpen(false) });
  }

  function confirmReset() {
    resetPwd.mutate({}, { onSuccess: (res) => setResetResult(res.data) });
  }

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" aria-label="Öğrenci eylemleri" className="px-2">
            <MoreHorizontal className="size-4" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem asChild>
            <Link href={`/teacher/students/${student.id}`}>
              <UserRound aria-hidden />
              Profili aç
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/teacher/students/${student.id}/day`}>
              <CalendarRange aria-hidden />
              Haftalık program
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/teacher/requests?student_id=${student.id}`}>
              <Inbox aria-hidden />
              Talepleri
            </Link>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => {
              setResetResult(null);
              setResetOpen(true);
            }}
          >
            <KeyRound className="text-indigo-500" aria-hidden />
            Şifre sıfırla
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={deactivate.isPending || reactivate.isPending}
            onSelect={() => {
              if (student.is_active) setEndOpen(true); // onaylı "Koçluğu sonlandır"
              else reactivate.mutate(); // yeniden başlatma benign → direkt
            }}
          >
            {student.is_active ? (
              <>
                <PauseCircle className="text-amber-500" aria-hidden />
                Koçluğu sonlandır
              </>
            ) : (
              <>
                <PlayCircle className="text-emerald-500" aria-hidden />
                Koçluğu yeniden başlat
              </>
            )}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <Dialog
        open={resetOpen}
        onOpenChange={(o) => {
          if (resetPwd.isPending) return;
          setResetOpen(o);
          if (!o) setResetResult(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{resetResult ? "Geçici şifre oluşturuldu" : "Şifreyi sıfırla"}</DialogTitle>
            <DialogDescription>
              {resetResult
                ? "Bu şifre yalnızca bu kez gösterilir — öğrenciye güvenli bir kanaldan iletin."
                : `${student.full_name} için yeni bir geçici şifre üretilecek. Öğrencinin mevcut şifresi geçersiz olur ve ilk girişte değişiklik istenir.`}
            </DialogDescription>
          </DialogHeader>
          {resetResult ? (
            <TempPasswordPanel
              result={resetResult}
              onDone={() => {
                setResetOpen(false);
                setResetResult(null);
              }}
            />
          ) : (
            <DialogFooter>
              <Button variant="ghost" onClick={() => setResetOpen(false)} disabled={resetPwd.isPending}>
                Vazgeç
              </Button>
              <Button onClick={confirmReset} disabled={resetPwd.isPending}>
                {resetPwd.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <KeyRound className="size-4" aria-hidden />
                )}
                Şifreyi sıfırla
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={endOpen} onOpenChange={(o) => { if (deactivate.isPending) return; setEndOpen(o); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Koçluğu sonlandır</DialogTitle>
            <DialogDescription>
              {student.full_name} ile koçluk sürecini sonlandırmak üzeresiniz.
            </DialogDescription>
          </DialogHeader>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex gap-2"><span className="text-cyan-600">•</span><span>Veliye bildirim (haftalık rapor, uyarılar) <b className="text-foreground">gönderilmez</b>.</span></li>
            <li className="flex gap-2"><span className="text-cyan-600">•</span><span>Öğrenci <b className="text-foreground">giriş yapamaz</b> (erişimi kapanır).</span></li>
            <li className="flex gap-2"><span className="text-cyan-600">•</span><span>Koç ve kurum <b className="text-foreground">istatistiklerinden çıkar</b> — ortalamanı düşürmez.</span></li>
            <li className="flex gap-2"><span className="text-emerald-600">•</span><span>Tüm verisi <b className="text-foreground">korunur</b>; istediğin an &ldquo;Koçluğu yeniden başlat&rdquo; ile geri açılır.</span></li>
          </ul>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEndOpen(false)} disabled={deactivate.isPending}>Vazgeç</Button>
            <Button onClick={confirmEnd} disabled={deactivate.isPending}>
              {deactivate.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <PauseCircle className="size-4" aria-hidden />}
              Koçluğu sonlandır
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function TempPasswordPanel({
  result,
  onDone,
}: {
  result: StudentResetPasswordResult;
  onDone: () => void;
}) {
  const [copied, setCopied] = React.useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(result.temp_password);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <strong>{result.full_name}</strong> için yeni geçici şifre:
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 rounded-md border border-border bg-muted px-3 py-2 font-mono text-sm break-all">
          {result.temp_password}
        </code>
        <Button type="button" variant="outline" size="sm" onClick={onCopy} aria-label="Şifreyi kopyala">
          {copied ? <Check className="size-4 text-emerald-500" aria-hidden /> : <Copy className="size-4" aria-hidden />}
          {copied ? "Kopyalandı" : "Kopyala"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        E-posta: {result.email} · Öğrenci ilk girişte parolasını değiştirmek zorunda kalacak.
      </p>
      <div className="flex items-center justify-end pt-2">
        <Button onClick={onDone}>Tamam</Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Boş/yükleme

function SkeletonRows() {
  return (
    <ul className="divide-y divide-border" aria-label="Yükleniyor">
      {Array.from({ length: 5 }).map((_, i) => (
        <li key={i} className="flex items-center gap-3 px-4 py-4">
          <span className="size-9 animate-pulse rounded-full bg-muted" />
          <span className="flex-1 space-y-2">
            <span className="block h-3 w-40 animate-pulse rounded bg-muted" />
            <span className="block h-2.5 w-56 animate-pulse rounded bg-muted" />
          </span>
        </li>
      ))}
    </ul>
  );
}

function EmptyState({ status, filtered }: { status: FilterValues["status"]; filtered: boolean }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
      <span className="grid size-12 place-items-center rounded-full bg-muted">
        <Users className="size-6 text-muted-foreground" aria-hidden />
      </span>
      {filtered ? (
        <>
          <p className="font-medium">Bu süzgeçlere uyan öğrenci yok</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            Süzgeçleri gevşetmeyi ya da üstteki “Tümünü temizle” bağlantısını dene.
          </p>
        </>
      ) : status === "aktif" ? (
        <>
          <p className="font-medium">Henüz aktif öğrencin yok</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            “Yeni öğrenci” ile tek tek ekleyebilir ya da “Toplu işlemler → Listeden toplu ekle”
            ile bir sınıfı tek seferde kaydedebilirsin. Koçluğu sonlandırılmış öğrenciler
            “Pasif” sekmesinde.
          </p>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">Bu durumda öğrenci yok.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- Sayfalama

function Pager({
  page,
  pageSize,
  total,
  hasNext,
}: {
  page: number;
  pageSize: number;
  total: number;
  hasNext: boolean;
}) {
  const { apply } = useApplyParam();
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  const go = (p: number) =>
    apply((sp) => {
      if (p <= 1) sp.delete("page");
      else sp.set("page", String(p));
    }, false);

  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3 text-sm"
      aria-label="Sayfalama"
    >
      <span className="text-muted-foreground tabular-nums">
        {from}–{to} / {total} öğrenci
      </span>
      <div className="flex items-center gap-2">
        <Select
          value={String(pageSize)}
          onChange={(v) =>
            apply((sp) => {
              if (v === "25") sp.delete("page_size");
              else sp.set("page_size", v);
            })
          }
          options={[
            { value: "25", label: "25 / sayfa" },
            { value: "50", label: "50 / sayfa" },
            { value: "100", label: "100 / sayfa" },
          ]}
          ariaLabel="Sayfa boyutu"
          className="h-9"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={page <= 1}
          onClick={() => go(page - 1)}
          aria-label="Önceki sayfa"
        >
          <ChevronLeft className="size-4" aria-hidden />
        </Button>
        <span className="tabular-nums text-muted-foreground">Sayfa {page}</span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasNext}
          onClick={() => go(page + 1)}
          aria-label="Sonraki sayfa"
        >
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}

// ---------------------------------------------------------------- Toplu şube

function ClassGroupBar({
  selectedIds,
  groupNames,
  onDone,
}: {
  selectedIds: number[];
  groupNames: string[];
  onDone: () => void;
}) {
  const [value, setValue] = React.useState("");
  const [mismatch, setMismatch] = React.useState<{
    message: string;
    students: { id: number; name: string; grade_label: string | null }[];
  } | null>(null);
  const mut = useSetStudentsClassGroup();
  const listId = "class-group-options";
  function apply(v: string, force = false) {
    mut.mutate(
      { studentIds: selectedIds, classGroup: v, force },
      {
        onSuccess: () => {
          setMismatch(null);
          onDone();
        },
        onError: (e) => {
          if (e.detail?.code === "grade_mismatch") {
            const det = (e.detail as { details?: { students?: { id: number; name: string; grade_label: string | null }[] } }).details;
            setMismatch({ message: e.message, students: det?.students ?? [] });
          }
        },
      },
    );
  }
  return (
    <div className="fixed inset-x-0 bottom-4 z-40 flex justify-center px-4">
      <div
        className="w-full max-w-3xl space-y-2 rounded-xl bg-slate-900 px-4 py-3 text-sm text-white shadow-xl ring-1 ring-black/10"
        data-testid="class-group-bar"
      >
        {mismatch ? (
          <div
            className="rounded-lg bg-amber-500 px-3 py-2 text-slate-950"
            role="alert"
            data-testid="class-group-mismatch"
          >
            <p className="font-semibold">Sınıf uyuşmuyor</p>
            <p className="mt-0.5">{mismatch.message}</p>
            {mismatch.students.length > 0 ? (
              <ul className="mt-1 list-disc pl-5">
                {mismatch.students.map((st) => (
                  <li key={st.id}>
                    {st.name} — {st.grade_label ?? "sınıf girilmemiş"}
                  </li>
                ))}
              </ul>
            ) : null}
            <p className="mt-1">
              Öğrencinin sınıfını değiştirmek istiyorsan profilinden ya da Sınıf
              Yükseltme sayfasından yap. Bilerek karma bir grup kuruyorsan yine de atayabilirsin.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => apply(value, true)}
                disabled={mut.isPending}
                data-testid="class-group-force"
                className="h-8 rounded-md bg-slate-900 px-3 font-medium text-white hover:bg-slate-800 disabled:opacity-50"
              >
                Yine de bu şubeye al
              </button>
              <button
                type="button"
                onClick={() => setMismatch(null)}
                className="h-8 rounded-md px-3 font-medium text-slate-950 hover:bg-amber-400"
              >
                Vazgeç, adı düzelteyim
              </button>
            </div>
          </div>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{selectedIds.length} öğrenci seçili</span>
          <span className="text-slate-300">· şubeye al:</span>
          <input
            list={listId}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setMismatch(null);
            }}
            placeholder="örn. 10-A"
            maxLength={60}
            className="h-9 w-40 rounded-md border border-slate-600 bg-slate-800 px-2 text-sm text-white placeholder:text-slate-400"
            aria-label="Şube adı"
          />
          <datalist id={listId}>
            {groupNames.map((g) => (
              <option key={g} value={g} />
            ))}
          </datalist>
          <button
            type="button"
            disabled={!value.trim() || mut.isPending}
            onClick={() => apply(value)}
            data-testid="class-group-apply"
            className="inline-flex h-9 items-center gap-1.5 rounded-md bg-cyan-600 px-3 font-medium text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            {mut.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : null}
            Şubeye al
          </button>
          <button
            type="button"
            disabled={mut.isPending}
            onClick={() => apply("")}
            className="h-9 rounded-md px-3 text-slate-200 hover:bg-slate-800 disabled:opacity-50"
          >
            Şubeyi kaldır
          </button>
          <button
            type="button"
            onClick={onDone}
            className="ml-auto inline-flex h-9 items-center gap-1 rounded-md px-2 text-slate-300 hover:bg-slate-800 hover:text-white"
            aria-label="Seçimi temizle"
          >
            <X className="size-4" aria-hidden />
            Seçimi temizle
          </button>
        </div>
        <p className="text-xs text-slate-300" data-testid="class-group-help">
          Şube, öğrencileri gruplamak için kullandığın bir etikettir (örnek: 10-A,
          12 Sayısal, Hafta sonu grubu). Öğrencinin sınıfını değiştirmez. Ad bir
          sınıfla başlıyorsa (12-A gibi) sistem, seçili öğrencilerin o sınıfta olup
          olmadığını kontrol eder.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Yardımcılar

function statusWord(s: FilterValues["status"]): string {
  return s === "aktif" ? "· aktif" : s === "pasif" ? "· koçluğu sonlandırılmış" : "· tüm durumlar";
}

function hasFilter(f: FilterValues): boolean {
  return !!f.q || !!f.grade_level || !!f.class_group || f.risk !== "all";
}

function lastLoginLabel(iso: string | null): string {
  if (!iso) return "Hiç girmedi";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const now = new Date();
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOf(now) - startOf(d)) / 86_400_000);
  if (days <= 0) return "Bugün";
  if (days === 1) return "Dün";
  if (days < 7) return `${days} gün önce`;
  if (days < 30) return `${Math.floor(days / 7)} hafta önce`;
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "short" });
}

function readFilters(sp: URLSearchParams, fallback: FilterValues): FilterValues {
  const q = sp.get("q") ?? "";
  const grade = sp.get("grade_level") ?? "";
  const risk = (sp.get("risk") ?? "all") as FilterValues["risk"];
  const rawStatus = sp.get("status");
  const status = (
    rawStatus === "pasif" || rawStatus === "tum" ? rawStatus : "aktif"
  ) as FilterValues["status"];
  const ps = Number(sp.get("page_size") ?? fallback.page_size);
  const pageSize = (ps === 50 || ps === 100 ? ps : 25) as 25 | 50 | 100;
  const classGroup = (sp.get("class_group") ?? "").slice(0, 60);
  return { q, grade_level: grade, risk, status, class_group: classGroup, page_size: pageSize };
}

function readPage(sp: URLSearchParams, fallback: number): number {
  const p = Number(sp.get("page") ?? fallback);
  return Number.isFinite(p) && p > 0 ? p : 1;
}

function isSameAsInitial(
  filters: FilterValues,
  initialFilters: FilterValues,
  page: number,
  initialPage: number,
): boolean {
  return (
    filters.q === initialFilters.q &&
    filters.grade_level === initialFilters.grade_level &&
    filters.risk === initialFilters.risk &&
    filters.status === initialFilters.status &&
    filters.class_group === initialFilters.class_group &&
    filters.page_size === initialFilters.page_size &&
    page === initialPage
  );
}
