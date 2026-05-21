"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  KeyRound,
  Loader2,
  MoreHorizontal,
  PauseCircle,
  PlayCircle,
  Copy,
  Check,
} from "lucide-react";

import { useTeacherStudents } from "@/lib/hooks/use-teacher-queries";
import type { TeacherStudentsListParams } from "@/lib/api/teacher";
import {
  useDeactivateStudent,
  useReactivateStudent,
  useResetStudentPassword,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  StudentResetPasswordResult,
  TeacherStudentListItem,
  TeacherStudentListResponse,
  WarningLevel,
} from "@/lib/types/teacher";
import { WARNING_LABELS_TR } from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  StudentsFilterBar,
  type FilterValues,
} from "@/components/teacher/students-filter-bar";
import { StudentCreateButton } from "@/components/teacher/student-create-modal";
import { cn } from "@/lib/utils";

interface Props {
  initial: TeacherStudentListResponse;
  initialFilters: FilterValues;
  initialPage: number;
}

export function StudentsListClient({ initial, initialFilters, initialPage }: Props) {
  const searchParams = useSearchParams();

  const filters = readFilters(searchParams, initialFilters);
  const page = readPage(searchParams, initialPage);

  const params: TeacherStudentsListParams = React.useMemo(
    () => ({
      q: filters.q || undefined,
      grade_level: filters.grade_level
        ? Number(filters.grade_level)
        : undefined,
      risk: filters.risk,
      page,
      page_size: filters.page_size,
    }),
    [filters.q, filters.grade_level, filters.risk, filters.page_size, page],
  );

  const q = useTeacherStudents(
    params,
    isSameAsInitial(filters, initialFilters, page, initialPage) ? initial : undefined,
  );
  const data = q.data;
  const isLoading = q.isLoading && !data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Öğrenciler
          </h1>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {isLoading
              ? "Yükleniyor…"
              : `Toplam ${data?.total ?? 0} sonuç · sayfa ${data?.page ?? page}`}
            {q.isFetching && !isLoading ? (
              <span className="ml-2 text-xs text-muted-foreground/70">
                · güncelleniyor…
              </span>
            ) : null}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <a
            href="/api/v2/teacher/csv/export/students"
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
            aria-label="Öğrencileri CSV olarak dışa aktar"
          >
            CSV indir
          </a>
          <Link
            href="/teacher/students/import"
            className="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted inline-flex items-center gap-1.5"
          >
            CSV ile ekle
          </Link>
          <StudentCreateButton />
        </div>
      </header>

      <StudentsFilterBar initial={filters} />

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <p className="p-6 text-sm text-muted-foreground">Yükleniyor…</p>
          ) : !data || data.items.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              Sonuç yok. Filtreyi gevşetmeyi deneyebilirsin.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {data.items.map((s) => (
                <StudentRow key={s.id} s={s} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Pager
        page={data?.page ?? page}
        hasNext={data?.has_next ?? false}
      />
    </div>
  );
}

function StudentRow({ s }: { s: TeacherStudentListItem }) {
  const weekPct = Math.round((s.week_pct ?? 0) * 100);
  const dim = !s.is_active;
  return (
    <li className="group">
      <div
        className={cn(
          "grid grid-cols-12 items-center gap-3 px-4 py-3 hover:bg-muted transition-colors",
          dim && "opacity-60",
        )}
      >
        <Link
          href={`/teacher/students/${s.id}`}
          className="col-span-12 sm:col-span-4 min-w-0 hover:underline"
        >
          <span className="flex items-center gap-2">
            <WarningDot level={s.worst_warning_level} />
            <span className="font-medium truncate">{s.full_name}</span>
            {!s.is_active ? (
              <span className="text-[10px] uppercase tracking-wide rounded bg-muted px-1.5 py-0.5 text-muted-foreground">
                pasif
              </span>
            ) : null}
            {s.has_pending_request ? (
              <span className="text-[10px] uppercase tracking-wide rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 px-1.5 py-0.5">
                talep
              </span>
            ) : null}
          </span>
          <span className="block text-xs text-muted-foreground truncate">
            {s.email}
          </span>
        </Link>
        <span className="hidden sm:block sm:col-span-2 text-sm text-muted-foreground">
          {s.grade_level !== null ? `${s.grade_level}. sınıf` : "Mezun"}
        </span>
        <span className="hidden sm:block sm:col-span-2 text-sm tabular-nums">
          Bugün: {s.today_completed}/{s.today_planned}
        </span>
        <span className="hidden sm:block sm:col-span-1 text-sm tabular-nums">
          Hafta: %{weekPct}
        </span>
        <span className="col-span-12 sm:col-span-3 flex items-center justify-end gap-2 text-xs">
          <Link
            href={`/teacher/students/${s.id}/day`}
            className="rounded-md border border-border px-2 py-1 hover:bg-background"
          >
            Plan
          </Link>
          <Link
            href={`/teacher/requests?student_id=${s.id}`}
            className="rounded-md border border-border px-2 py-1 hover:bg-background"
          >
            Talep
          </Link>
          <StudentRowActions student={s} />
        </span>
      </div>
    </li>
  );
}

function StudentRowActions({ student }: { student: TeacherStudentListItem }) {
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [resetOpen, setResetOpen] = React.useState(false);
  const [resetResult, setResetResult] = React.useState<StudentResetPasswordResult | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (!menuOpen) return;
    function onClick(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const deactivate = useDeactivateStudent(student.id);
  const reactivate = useReactivateStudent(student.id);
  const resetPwd = useResetStudentPassword(student.id);

  function onToggleActive() {
    setMenuOpen(false);
    if (student.is_active) deactivate.mutate();
    else reactivate.mutate();
  }

  function onResetPassword() {
    setMenuOpen(false);
    setResetOpen(true);
    setResetResult(null);
  }

  function confirmReset() {
    resetPwd.mutate(
      {},
      {
        onSuccess: (res) => setResetResult(res.data),
      },
    );
  }

  return (
    <>
      <div ref={containerRef} className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label="Öğrenci eylemleri"
          className="rounded-md border border-border px-2 py-1 hover:bg-background inline-flex items-center"
        >
          <MoreHorizontal className="size-3.5" aria-hidden />
        </button>
        {menuOpen ? (
          <div
            role="menu"
            className="absolute right-0 z-20 mt-1 w-48 rounded-md border border-border bg-popover text-popover-foreground shadow-md py-1 text-sm"
          >
            <button
              type="button"
              role="menuitem"
              onClick={onToggleActive}
              disabled={deactivate.isPending || reactivate.isPending}
              className="w-full text-left px-3 py-2 hover:bg-muted inline-flex items-center gap-2 disabled:opacity-60"
            >
              {student.is_active ? (
                <>
                  <PauseCircle className="size-4 text-amber-500" aria-hidden />
                  Pasife al
                </>
              ) : (
                <>
                  <PlayCircle className="size-4 text-emerald-500" aria-hidden />
                  Aktif et
                </>
              )}
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={onResetPassword}
              className="w-full text-left px-3 py-2 hover:bg-muted inline-flex items-center gap-2"
            >
              <KeyRound className="size-4 text-indigo-500" aria-hidden />
              Şifre sıfırla
            </button>
          </div>
        ) : null}
      </div>

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
            <DialogTitle>
              {resetResult ? "Geçici şifre oluşturuldu" : "Şifreyi sıfırla"}
            </DialogTitle>
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
              <Button
                variant="ghost"
                onClick={() => setResetOpen(false)}
                disabled={resetPwd.isPending}
              >
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
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCopy}
          aria-label="Şifreyi kopyala"
        >
          {copied ? (
            <Check className="size-4 text-emerald-500" aria-hidden />
          ) : (
            <Copy className="size-4" aria-hidden />
          )}
          {copied ? "Kopyalandı" : "Kopyala"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        E-posta: {result.email} · Öğrenci ilk girişte parolasını değiştirmek
        zorunda kalacak.
      </p>
      <div className="flex items-center justify-end pt-2">
        <Button onClick={onDone}>Tamam</Button>
      </div>
    </div>
  );
}

function WarningDot({ level }: { level: WarningLevel }) {
  const cls =
    level === "red"
      ? "bg-rose-500"
      : level === "amber"
        ? "bg-amber-500"
        : "bg-emerald-500";
  return (
    <span
      className={"inline-block size-2 rounded-full " + cls}
      aria-label={WARNING_LABELS_TR[level]}
    />
  );
}

function Pager({ page, hasNext }: { page: number; hasNext: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = React.useTransition();

  function withPage(p: number): string {
    const sp = new URLSearchParams(searchParams.toString());
    if (p <= 1) sp.delete("page");
    else sp.set("page", String(p));
    const qs = sp.toString();
    return qs ? `${pathname}?${qs}` : pathname;
  }

  function go(p: number) {
    startTransition(() => {
      router.replace(withPage(p), { scroll: false });
    });
  }

  return (
    <nav
      className="flex items-center justify-end gap-2 text-sm"
      aria-label="Sayfalama"
    >
      {page > 1 ? (
        <button
          type="button"
          onClick={() => go(page - 1)}
          className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
        >
          ← Önceki
        </button>
      ) : null}
      <span className="text-muted-foreground">Sayfa {page}</span>
      {hasNext ? (
        <button
          type="button"
          onClick={() => go(page + 1)}
          className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
        >
          Sonraki →
        </button>
      ) : null}
    </nav>
  );
}

function readFilters(
  sp: URLSearchParams,
  fallback: FilterValues,
): FilterValues {
  const q = sp.get("q") ?? "";
  const grade = sp.get("grade_level") ?? "";
  const risk = (sp.get("risk") ?? "all") as FilterValues["risk"];
  const ps = Number(sp.get("page_size") ?? fallback.page_size);
  const pageSize = (ps === 50 || ps === 100 ? ps : 25) as 25 | 50 | 100;
  return { q, grade_level: grade, risk, page_size: pageSize };
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
    filters.page_size === initialFilters.page_size &&
    page === initialPage
  );
}
