"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileStack,
  GraduationCap,
  LayoutGrid,
  LayoutTemplate,
  Library as LibraryIcon,
  ListChecks,
  Plus,
  Rows3,
  Search,
  SearchX,
  Users,
  X,
} from "lucide-react";

import {
  getLibraryBooks,
  getLibrarySubjects,
  libraryKeys,
  type LibraryBooksListParams,
} from "@/lib/api/library";
import type {
  CurriculumModel,
  LibraryBookListItem,
  LibraryBookListResponse,
  LibraryBookType,
  SubjectListResponse,
  SubjectRef,
} from "@/lib/types/library";
import {
  CURRICULUM_MODEL_LABELS_TR,
  CURRICULUM_MODEL_ORDER,
  LIBRARY_BOOK_TYPE_LABELS_TR,
} from "@/lib/types/library";
import { isExamSubject } from "@/lib/utils/subjects";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ColumnHint } from "@/components/ui/column-hint";
import { DemoHint } from "@/components/demos/demo-hint";
import { cn } from "@/lib/utils";

// Sınav (TYT/AYT) kanonik dersleri model-bağımsız (curriculum_model=null +
// exam_section) → müfredat filtresinde kendi kategorisi.
const EXAM_CURRICULUM_KEY = "exam";
const EXAM_CURRICULUM_LABEL = "Sınav (TYT / AYT)";

// =============================================================================
// Görsel sabitler (purge-safe statik sınıflar)
// =============================================================================

const TYPE_TONE: Record<LibraryBookType, { bar: string; dot: string; badge: string }> = {
  soru_bankasi: {
    bar: "bg-indigo-500",
    dot: "bg-indigo-500",
    badge: "bg-indigo-600 text-white",
  },
  fasikul: {
    bar: "bg-emerald-500",
    dot: "bg-emerald-500",
    badge: "bg-emerald-600 text-white",
  },
  konu_anlatimli: {
    bar: "bg-amber-500",
    dot: "bg-amber-500",
    badge: "bg-amber-600 text-white",
  },
  brans_denemesi: {
    bar: "bg-rose-500",
    dot: "bg-rose-500",
    badge: "bg-rose-600 text-white",
  },
  genel_deneme: {
    bar: "bg-violet-500",
    dot: "bg-violet-500",
    badge: "bg-violet-600 text-white",
  },
};

const SUBJECT_TONES: Array<{ dot: string; text: string }> = [
  { dot: "bg-indigo-500", text: "text-indigo-700 dark:text-indigo-300" },
  { dot: "bg-emerald-500", text: "text-emerald-700 dark:text-emerald-300" },
  { dot: "bg-amber-500", text: "text-amber-700 dark:text-amber-300" },
  { dot: "bg-rose-500", text: "text-rose-700 dark:text-rose-300" },
  { dot: "bg-violet-500", text: "text-violet-700 dark:text-violet-300" },
  { dot: "bg-cyan-500", text: "text-cyan-700 dark:text-cyan-300" },
  { dot: "bg-fuchsia-500", text: "text-fuchsia-700 dark:text-fuchsia-300" },
  { dot: "bg-sky-500", text: "text-sky-700 dark:text-sky-300" },
];

function subjectTone(subjectId: number) {
  return SUBJECT_TONES[Math.abs(subjectId) % SUBJECT_TONES.length];
}

const BOOK_TYPES: LibraryBookType[] = [
  "soru_bankasi",
  "fasikul",
  "konu_anlatimli",
  "brans_denemesi",
  "genel_deneme",
];

const DENEME_TYPES = new Set<LibraryBookType>(["brans_denemesi", "genel_deneme"]);

const GRADE_LEVELS: number[] = [5, 6, 7, 8, 9, 10, 11, 12];

type SortKey = "name" | "recent" | "students";
const SORT_LABELS: Record<SortKey, string> = {
  name: "Ada göre (A–Z)",
  recent: "Son eklenen önce",
  students: "En çok öğrencide",
};

type StateKey = "" | "attention" | "unassigned" | "assigned";
const STATE_LABELS: Record<Exclude<StateKey, "">, string> = {
  attention: "Eksiği olanlar",
  unassigned: "Öğrenciye atanmamış",
  assigned: "Öğrencide kullanılan",
};

// =============================================================================
// Tipler + yardımcılar
// =============================================================================

interface InitialFilters {
  q: string;
  type: string;
  subject_id: number | undefined;
  grade_level: number | undefined;
}

interface Props {
  initial: LibraryBookListResponse;
  initialFilters: InitialFilters;
}

interface SubjectGroup {
  subject_id: number;
  subject_name: string;
  items: LibraryBookListItem[];
  total_sections: number;
  total_tests: number;
  total_denemes: number;
}

function activeStudents(b: LibraryBookListItem): number {
  return b.active_student_count ?? b.assigned_student_count;
}

/** Kitabın eksikleri — sade dille, koçun ne yapacağını söyler. */
function bookIssues(b: LibraryBookListItem): string[] {
  const out: string[] = [];
  if (b.section_count === 0) {
    out.push("Ünite eklenmemiş — göreve verilemez");
    return out;
  }
  const mapped = b.mapped_section_count;
  if (mapped !== undefined && !DENEME_TYPES.has(b.type) && mapped < b.section_count) {
    out.push(
      `${b.section_count - mapped} ünite müfredata bağlı değil — konu analizlerinde sayılmaz`,
    );
  }
  return out;
}

function sortItems(items: LibraryBookListItem[], sort: SortKey): LibraryBookListItem[] {
  const arr = [...items];
  if (sort === "recent") {
    arr.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  } else if (sort === "students") {
    arr.sort(
      (a, b) =>
        activeStudents(b) - activeStudents(a) || a.name.localeCompare(b.name, "tr"),
    );
  } else {
    arr.sort((a, b) => a.name.localeCompare(b.name, "tr"));
  }
  return arr;
}

function groupBySubject(items: LibraryBookListItem[]): SubjectGroup[] {
  const map = new Map<number, SubjectGroup>();
  for (const it of items) {
    const g = map.get(it.subject_id);
    if (g) {
      g.items.push(it);
      g.total_sections += it.section_count;
      if (DENEME_TYPES.has(it.type)) g.total_denemes += it.total_tests;
      else g.total_tests += it.total_tests;
    } else {
      map.set(it.subject_id, {
        subject_id: it.subject_id,
        subject_name: it.subject_name ?? "Diğer",
        items: [it],
        total_sections: it.section_count,
        total_tests: DENEME_TYPES.has(it.type) ? 0 : it.total_tests,
        total_denemes: DENEME_TYPES.has(it.type) ? it.total_tests : 0,
      });
    }
  }
  return Array.from(map.values()).sort((a, b) =>
    a.subject_name.localeCompare(b.subject_name, "tr"),
  );
}

function gradeLabel(b: LibraryBookListItem): string | null {
  const { target_grade_min: lo, target_grade_max: hi, target_graduate: grad } = b;
  if (lo === null && hi === null && !grad) return null;
  const parts: string[] = [];
  if (lo !== null && hi !== null) {
    parts.push(lo === hi ? `${lo}. sınıf` : `${lo}–${hi}. sınıf`);
  } else if (lo !== null) {
    parts.push(`${lo}. sınıf ve üstü`);
  } else if (hi !== null) {
    parts.push(`${hi}. sınıfa kadar`);
  }
  if (grad) parts.push("Mezun");
  return parts.join(" · ");
}

function bookCoversGrade(b: LibraryBookListItem, grade: number): boolean {
  const { target_grade_min: lo, target_grade_max: hi, target_graduate: grad } = b;
  if (lo === null && hi === null && !grad) return true;
  const min = lo ?? 5;
  const max = hi ?? 12;
  return grade >= min && grade <= max;
}

function fmtDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

// =============================================================================
// Ana bileşen
// =============================================================================

export function LibraryListClient({ initial, initialFilters }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  const urlQ = sp.get("q") ?? "";
  const urlType = sp.get("type") ?? "";
  const urlSubject = sp.get("subject_id") ?? "";
  const urlGrade = sp.get("grade_level") ?? "";
  const urlCurriculum = sp.get("curriculum") ?? "";
  const urlSort = (sp.get("sort") as SortKey | null) ?? "name";
  const sort: SortKey = urlSort in SORT_LABELS ? urlSort : "name";
  const urlState = (sp.get("durum") ?? "") as StateKey;
  const state: StateKey = urlState in STATE_LABELS ? urlState : "";
  const view: "grid" | "list" = sp.get("view") === "list" ? "list" : "grid";

  const [qInput, setQInput] = React.useState(initialFilters.q);
  const [lastSyncedQ, setLastSyncedQ] = React.useState(initialFilters.q);
  if (urlQ !== lastSyncedQ) {
    setLastSyncedQ(urlQ);
    setQInput(urlQ);
  }
  const [, startTransition] = React.useTransition();
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);

  // Sınıf filtresi backend'de yalnız sayısal (5-12); "Mezun" frontend'de süzülür.
  const backendGrade = urlGrade && urlGrade !== "graduate" ? Number(urlGrade) : undefined;
  const params: LibraryBooksListParams = React.useMemo(
    () => ({
      q: urlQ || undefined,
      type: urlType || undefined,
      subject_id: urlSubject ? Number(urlSubject) : undefined,
      grade_level: backendGrade,
    }),
    [urlQ, urlType, urlSubject, backendGrade],
  );

  const isSameAsInitial =
    urlQ === initialFilters.q &&
    urlType === initialFilters.type &&
    Number(urlSubject || 0) === (initialFilters.subject_id ?? 0) &&
    (backendGrade ?? 0) === (initialFilters.grade_level ?? 0);

  const booksQ = useQuery<LibraryBookListResponse>({
    queryKey: libraryKeys.books(params),
    queryFn: () => getLibraryBooks(params),
    initialData: isSameAsInitial ? initial : undefined,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const subjectsQ = useQuery<SubjectListResponse>({
    queryKey: libraryKeys.subjects(),
    queryFn: () => getLibrarySubjects(),
    staleTime: 60_000 * 5,
  });

  const data = booksQ.data;
  const apiItems = React.useMemo(() => data?.items ?? [], [data]);
  const allSubjects = React.useMemo(() => subjectsQ.data?.items ?? [], [subjectsQ.data]);
  const subjectById = React.useMemo(() => {
    const m = new Map<number, SubjectRef>();
    for (const s of allSubjects) m.set(s.id, s);
    return m;
  }, [allSubjects]);

  const curriculumOf = React.useCallback(
    (s: SubjectRef | undefined): string => {
      if (!s) return "other";
      if (isExamSubject(s)) return EXAM_CURRICULUM_KEY;
      return (s.curriculum_model as CurriculumModel | null) ?? "other";
    },
    [],
  );
  const bookCurriculum = React.useCallback(
    (b: LibraryBookListItem) => curriculumOf(subjectById.get(b.subject_id)),
    [curriculumOf, subjectById],
  );

  const curriculumCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const b of apiItems) {
      const k = bookCurriculum(b);
      c[k] = (c[k] ?? 0) + 1;
    }
    return c;
  }, [apiItems, bookCurriculum]);

  const curriculumOptions = React.useMemo(() => {
    const opts: Array<{ key: string; label: string }> = [];
    for (const cm of CURRICULUM_MODEL_ORDER) {
      opts.push({ key: cm, label: CURRICULUM_MODEL_LABELS_TR[cm] });
    }
    opts.push({ key: EXAM_CURRICULUM_KEY, label: EXAM_CURRICULUM_LABEL });
    opts.push({ key: "other", label: "Diğer" });
    return opts;
  }, []);

  const effectiveCurriculum: string = React.useMemo(() => {
    if (urlCurriculum) return urlCurriculum;
    for (const o of curriculumOptions) {
      if ((curriculumCounts[o.key] ?? 0) > 0) return o.key;
    }
    return CURRICULUM_MODEL_ORDER[0];
  }, [urlCurriculum, curriculumCounts, curriculumOptions]);

  // Müfredat + mezun süzgeci (öncesi: durum kartları bunun üstünden sayar)
  const curriculumItems = React.useMemo(
    () =>
      apiItems.filter(
        (b) =>
          bookCurriculum(b) === effectiveCurriculum &&
          (urlGrade !== "graduate" || b.target_graduate),
      ),
    [apiItems, bookCurriculum, effectiveCurriculum, urlGrade],
  );

  const stats = React.useMemo(() => {
    let sections = 0;
    let tests = 0;
    let denemes = 0;
    let assigned = 0;
    let attention = 0;
    for (const b of curriculumItems) {
      sections += b.section_count;
      if (DENEME_TYPES.has(b.type)) denemes += b.total_tests;
      else tests += b.total_tests;
      if (activeStudents(b) > 0) assigned += 1;
      if (bookIssues(b).length > 0) attention += 1;
    }
    return {
      books: curriculumItems.length,
      sections,
      tests,
      denemes,
      assigned,
      unassigned: curriculumItems.length - assigned,
      attention,
    };
  }, [curriculumItems]);

  const items = React.useMemo(() => {
    const filtered = curriculumItems.filter((b) => {
      if (state === "attention") return bookIssues(b).length > 0;
      if (state === "unassigned") return activeStudents(b) === 0;
      if (state === "assigned") return activeStudents(b) > 0;
      return true;
    });
    return sortItems(filtered, sort);
  }, [curriculumItems, state, sort]);

  const groups = React.useMemo(() => groupBySubject(items), [items]);

  const typeCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const it of curriculumItems) c[it.type] = (c[it.type] ?? 0) + 1;
    return c;
  }, [curriculumItems]);

  const gradeCounts = React.useMemo(() => {
    const c: Record<string, number> = { graduate: 0 };
    for (const it of curriculumItems) {
      if (it.target_graduate) c.graduate += 1;
      for (const g of GRADE_LEVELS) {
        if (bookCoversGrade(it, g)) c[String(g)] = (c[String(g)] ?? 0) + 1;
      }
    }
    return c;
  }, [curriculumItems]);

  const visibleSubjects = React.useMemo(
    () =>
      allSubjects
        .filter((s) => curriculumOf(s) === effectiveCurriculum)
        .sort((a, b) => a.name.localeCompare(b.name, "tr")),
    [allSubjects, curriculumOf, effectiveCurriculum],
  );

  function applyParams(mutate: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(sp.toString());
    mutate(next);
    const qs = next.toString();
    startTransition(() => {
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    });
  }

  function setParam(key: string, value: string) {
    applyParams((p) => {
      if (value) p.set(key, value);
      else p.delete(key);
    });
  }

  function onChangeQ(v: string) {
    setQInput(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      applyParams((p) => {
        const t = v.trim();
        if (t) p.set("q", t);
        else p.delete("q");
      });
    }, 300);
  }

  function clearChip(param: string) {
    if (param === "q") onChangeQ("");
    else setParam(param, "");
  }

  function resetFilters() {
    setQInput("");
    applyParams((p) => {
      for (const k of ["q", "type", "subject_id", "grade_level", "durum"]) p.delete(k);
    });
  }

  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement | null)?.tagName ?? "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  React.useEffect(
    () => () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    },
    [],
  );

  const activeChips: Array<{ key: string; label: string; param: string }> = [];
  if (urlQ) {
    activeChips.push({ key: "q", label: `“${urlQ}”`, param: "q" });
  }
  if (urlSubject) {
    const s = subjectById.get(Number(urlSubject));
    activeChips.push({
      key: "subject",
      label: s?.name ?? "Ders",
      param: "subject_id",
    });
  }
  if (urlType) {
    activeChips.push({
      key: "type",
      label: LIBRARY_BOOK_TYPE_LABELS_TR[urlType as LibraryBookType] ?? urlType,
      param: "type",
    });
  }
  if (urlGrade) {
    activeChips.push({
      key: "grade",
      label: urlGrade === "graduate" ? "Mezun" : `${urlGrade}. sınıf`,
      param: "grade_level",
    });
  }
  if (state) {
    activeChips.push({
      key: "state",
      label: STATE_LABELS[state],
      param: "durum",
    });
  }

  const shownCurriculum = curriculumOptions.filter(
    (o) => (curriculumCounts[o.key] ?? 0) > 0 || o.key === effectiveCurriculum,
  );

  return (
    <div className="space-y-5">
      {/* ---------------------------------------------------------- başlık */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight font-display">Kütüphane</h1>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Öğrencilerine görev verdiğin kitaplar burada. Bir kitabın üniteleri ve test
            sayıları ne kadar doğruysa programdaki “kalan test” de o kadar doğru olur.
          </p>
          <DemoHint contextKey="library" role="teacher" />
        </div>
        <Button asChild>
          <Link href="/teacher/library/new">
            <Plus className="size-4" aria-hidden />
            Yeni kitap
          </Link>
        </Button>
      </header>

      <LibraryTabs />

      {/* ------------------------------------------------------ durum kartları */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="library-stats">
        <StatTile
          icon={<BookOpen className="size-4" aria-hidden />}
          tone="slate"
          value={stats.books}
          unit="kitap"
          caption={`${stats.sections} ünite · ${stats.tests} test${stats.denemes ? ` · ${stats.denemes} deneme` : ""}`}
          hint="Seçili müfredattaki kitap sayısı ile bu kitaplardaki toplam ünite ve test. Deneme kitaplarındaki denemeler teste katılmaz, ayrı yazılır."
          active={state === ""}
          onClick={() => setParam("durum", "")}
        />
        <StatTile
          icon={<Users className="size-4" aria-hidden />}
          tone="emerald"
          value={stats.assigned}
          unit="kitap"
          caption="en az bir öğrencide kullanılıyor"
          hint="En az bir aktif öğrenciye atanmış kitaplar. Tıkla: yalnız bunları göster."
          active={state === "assigned"}
          onClick={() => setParam("durum", state === "assigned" ? "" : "assigned")}
        />
        <StatTile
          icon={<ListChecks className="size-4" aria-hidden />}
          tone="sky"
          value={stats.unassigned}
          unit="kitap"
          caption="henüz öğrenciye atanmamış"
          hint="Kütüphanende duran ama hiçbir aktif öğrencine atanmamış kitaplar. Tıkla: yalnız bunları göster."
          active={state === "unassigned"}
          onClick={() => setParam("durum", state === "unassigned" ? "" : "unassigned")}
        />
        <StatTile
          icon={<AlertTriangle className="size-4" aria-hidden />}
          tone={stats.attention > 0 ? "amber" : "slate"}
          value={stats.attention}
          unit="kitap"
          caption={stats.attention > 0 ? "eksiği var — tamamla" : "eksik yok"}
          hint="Ünitesi eklenmemiş ya da bazı üniteleri müfredat konusuna bağlanmamış kitaplar. Tıkla: yalnız bunları göster."
          active={state === "attention"}
          onClick={() => setParam("durum", state === "attention" ? "" : "attention")}
          testId="stat-attention"
        />
      </div>

      {/* ---------------------------------------------------------- araç çubuğu */}
      <Card>
        <CardContent className="space-y-3 p-3 sm:p-4">
          {shownCurriculum.length > 1 ? (
            <div
              role="radiogroup"
              aria-label="Müfredat"
              className="flex flex-wrap gap-1 rounded-lg bg-muted p-1"
            >
              {shownCurriculum.map((o) => {
                const on = o.key === effectiveCurriculum;
                return (
                  <button
                    key={o.key}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    data-testid={`curriculum-${o.key}`}
                    onClick={() =>
                      applyParams((p) => {
                        p.set("curriculum", o.key);
                        const sid = p.get("subject_id");
                        if (sid) {
                          const s = subjectById.get(Number(sid));
                          if (!s || curriculumOf(s) !== o.key) p.delete("subject_id");
                        }
                      })
                    }
                    className={cn(
                      "flex-1 rounded-md px-3 py-1.5 text-sm transition-colors sm:flex-none",
                      on
                        ? "bg-background font-medium text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {o.label}
                    <span className="ml-1.5 tabular-nums text-xs opacity-70">
                      {curriculumCounts[o.key] ?? 0}
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_repeat(4,minmax(0,1fr))_auto]">
            <label className="relative sm:col-span-2 lg:col-span-1">
              <span className="sr-only">Kitap ara</span>
              <Search
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <input
                ref={searchRef}
                type="search"
                value={qInput}
                onChange={(e) => onChangeQ(e.target.value)}
                placeholder="Kitap veya yayınevi ara…"
                className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-10 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                data-testid="library-search"
              />
              <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border px-1.5 text-[10px] text-muted-foreground sm:inline">
                /
              </kbd>
            </label>
            <ToolbarSelect
              label="Ders"
              value={urlSubject}
              onChange={(v) => setParam("subject_id", v)}
              testId="filter-subject"
            >
              <option value="">Tüm dersler</option>
              {visibleSubjects.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </ToolbarSelect>
            <ToolbarSelect
              label="Kitap türü"
              value={urlType}
              onChange={(v) => setParam("type", v)}
              testId="filter-type"
            >
              <option value="">Tüm türler</option>
              {BOOK_TYPES.map((t) => (
                <option key={t} value={t}>
                  {LIBRARY_BOOK_TYPE_LABELS_TR[t]} ({typeCounts[t] ?? 0})
                </option>
              ))}
            </ToolbarSelect>
            <ToolbarSelect
              label="Sınıf"
              value={urlGrade}
              onChange={(v) => setParam("grade_level", v)}
              testId="filter-grade"
            >
              <option value="">Tüm sınıflar</option>
              {GRADE_LEVELS.map((g) => (
                <option key={g} value={String(g)}>
                  {g}. sınıf ({gradeCounts[String(g)] ?? 0})
                </option>
              ))}
              <option value="graduate">Mezun ({gradeCounts.graduate ?? 0})</option>
            </ToolbarSelect>
            <ToolbarSelect
              label="Sıralama"
              value={sort === "name" ? "" : sort}
              onChange={(v) => setParam("sort", v)}
              testId="filter-sort"
            >
              {(Object.keys(SORT_LABELS) as SortKey[]).map((k) => (
                <option key={k} value={k === "name" ? "" : k}>
                  {SORT_LABELS[k]}
                </option>
              ))}
            </ToolbarSelect>
            <div
              role="radiogroup"
              aria-label="Görünüm"
              className="flex h-9 items-center gap-0.5 rounded-md border border-input p-0.5"
            >
              <ViewButton
                on={view === "grid"}
                label="Kart görünümü"
                onClick={() => setParam("view", "")}
              >
                <LayoutGrid className="size-4" aria-hidden />
              </ViewButton>
              <ViewButton
                on={view === "list"}
                label="Liste görünümü"
                onClick={() => setParam("view", "list")}
                testId="view-list"
              >
                <Rows3 className="size-4" aria-hidden />
              </ViewButton>
            </div>
          </div>

          {activeChips.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
              <span className="text-xs text-muted-foreground">
                <span className="font-medium tabular-nums text-foreground">{items.length}</span>{" "}
                kitap gösteriliyor ·
              </span>
              {activeChips.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => clearChip(c.param)}
                  className="inline-flex items-center gap-1 rounded-full bg-foreground px-2.5 py-1 text-xs text-background hover:opacity-90"
                  aria-label={`${c.label} filtresini kaldır`}
                >
                  {c.label}
                  <X className="size-3" aria-hidden />
                </button>
              ))}
              <button
                type="button"
                onClick={resetFilters}
                className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                Tümünü temizle
              </button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* ---------------------------------------------------------- içerik */}
      {booksQ.isLoading && !data ? (
        <EmptyShell
          icon={<LibraryIcon className="size-8 text-muted-foreground/60" aria-hidden />}
          title="Yükleniyor…"
        />
      ) : items.length === 0 ? (
        activeChips.length > 0 ? (
          <EmptyShell
            icon={<SearchX className="size-8 text-muted-foreground/60" aria-hidden />}
            title="Eşleşen kitap yok"
            description="Filtreleri gevşetmeyi ya da başka bir kelime aramayı deneyebilirsin."
            action={
              <Button size="sm" variant="outline" onClick={resetFilters}>
                Filtreleri temizle
              </Button>
            }
          />
        ) : (
          <EmptyShell
            icon={<LibraryIcon className="size-8 text-muted-foreground/60" aria-hidden />}
            title="Henüz kitap eklenmedi"
            description="Yeni kitap ekle: adını yaz, ortak katalogda varsa üniteleri ve test sayıları tek tıkla gelir."
            action={
              <Button size="sm" asChild>
                <Link href="/teacher/library/new">
                  <Plus className="size-4" aria-hidden />
                  Yeni kitap
                </Link>
              </Button>
            }
          />
        )
      ) : view === "list" ? (
        <BookTable items={items} />
      ) : (
        <div className="space-y-7">
          {groups.map((g) => (
            <SubjectSection key={g.subject_id} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Parçalar
// =============================================================================

const STAT_TONE = {
  slate: {
    icon: "bg-slate-100 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
    ring: "ring-slate-400/60",
  },
  emerald: {
    icon: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-200",
    ring: "ring-emerald-500/70",
  },
  sky: {
    icon: "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-200",
    ring: "ring-sky-500/70",
  },
  amber: {
    icon: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200",
    ring: "ring-amber-500/70",
  },
} as const;

function StatTile({
  icon,
  tone,
  value,
  unit,
  caption,
  hint,
  active,
  onClick,
  testId,
}: {
  icon: React.ReactNode;
  tone: keyof typeof STAT_TONE;
  value: number;
  unit: string;
  caption: string;
  hint: string;
  active: boolean;
  onClick: () => void;
  testId?: string;
}) {
  const t = STAT_TONE[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      title={hint}
      aria-pressed={active}
      data-testid={testId}
      className={cn(
        "flex items-start gap-3 rounded-xl border border-border bg-card p-3 text-left transition-shadow hover:shadow-sm",
        active && `ring-2 ${t.ring}`,
      )}
    >
      <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg", t.icon)}>
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block">
          <span className="text-xl font-semibold tabular-nums">{value}</span>{" "}
          <span className="text-sm text-muted-foreground">{unit}</span>
        </span>
        <span className="block text-xs text-muted-foreground">{caption}</span>
      </span>
    </button>
  );
}

function ToolbarSelect({
  label,
  value,
  onChange,
  children,
  testId,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <label className="block min-w-0">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        data-testid={testId}
        className={cn(
          "h-9 w-full rounded-md border border-input bg-background px-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring",
          value ? "font-medium text-foreground" : "text-muted-foreground",
        )}
      >
        {children}
      </select>
    </label>
  );
}

function ViewButton({
  on,
  label,
  onClick,
  children,
  testId,
}: {
  on: boolean;
  label: string;
  onClick: () => void;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={on}
      aria-label={label}
      title={label}
      onClick={onClick}
      data-testid={testId}
      className={cn(
        "grid h-full flex-1 place-items-center rounded px-2 transition-colors",
        on ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function EmptyShell({
  icon,
  title,
  description,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="space-y-2 p-10 text-center">
        <div className="flex justify-center">{icon}</div>
        <p className="text-sm font-medium">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        ) : null}
        {action ? <div className="pt-2">{action}</div> : null}
      </CardContent>
    </Card>
  );
}

function SubjectSection({ group }: { group: SubjectGroup }) {
  const tone = subjectTone(group.subject_id);
  return (
    <section className="space-y-3" data-testid="subject-section">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-border pb-2">
        <span className="flex items-center gap-2">
          <span className={cn("inline-block size-2.5 rounded-full", tone.dot)} aria-hidden />
          <h2 className={cn("text-base font-semibold", tone.text)}>{group.subject_name}</h2>
        </span>
        <span className="text-xs text-muted-foreground">
          <b className="font-medium tabular-nums text-foreground">{group.items.length}</b> kitap ·{" "}
          <b className="font-medium tabular-nums text-foreground">{group.total_sections}</b> ünite ·{" "}
          <b className="font-medium tabular-nums text-foreground">{group.total_tests}</b> test
          {group.total_denemes > 0 ? (
            <>
              {" · "}
              <b className="font-medium tabular-nums text-foreground">{group.total_denemes}</b> deneme
            </>
          ) : null}
        </span>
      </header>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {group.items.map((b) => (
          <li key={b.id}>
            <BookCard book={b} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function MappingBar({ book }: { book: LibraryBookListItem }) {
  const mapped = book.mapped_section_count;
  if (mapped === undefined || book.section_count === 0 || DENEME_TYPES.has(book.type)) {
    return null;
  }
  const pct = Math.round((100 * mapped) / book.section_count);
  const full = mapped >= book.section_count;
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">Müfredata bağlı ünite</span>
        <span
          className={cn(
            "tabular-nums font-medium",
            full ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300",
          )}
        >
          {mapped}/{book.section_count}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full", full ? "bg-emerald-500" : "bg-amber-500")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function BookCard({ book }: { book: LibraryBookListItem }) {
  const tone = TYPE_TONE[book.type];
  const grade = gradeLabel(book);
  const issues = bookIssues(book);
  const students = activeStudents(book);

  return (
    <Link
      href={`/teacher/library/books/${book.id}`}
      className="group block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-testid="book-card"
    >
      <article className="relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card transition-all group-hover:-translate-y-0.5 group-hover:shadow-md">
        <span className={cn("absolute inset-y-0 left-0 w-1", tone.bar)} aria-hidden />
        <div className="flex flex-1 flex-col gap-3 p-4 pl-5">
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[11px] font-medium",
                tone.badge,
              )}
            >
              {LIBRARY_BOOK_TYPE_LABELS_TR[book.type]}
            </span>
            {grade ? (
              <span className="rounded-full bg-slate-700 px-2 py-0.5 text-[11px] font-medium text-white dark:bg-slate-600">
                {grade}
              </span>
            ) : null}
            {book.source_kind === "catalog" ? (
              <span
                className="rounded-full bg-cyan-700 px-2 py-0.5 text-[11px] font-medium text-white"
                title="Ünite ve test sayıları ortak katalogdan birebir geldi."
              >
                Katalogdan
              </span>
            ) : null}
          </div>

          <div className="space-y-0.5">
            <h3 className="font-semibold leading-snug break-words group-hover:underline">
              {book.name}
            </h3>
            <p className="text-xs text-muted-foreground break-words">
              {book.publisher ?? "Yayınevi belirtilmemiş"}
            </p>
          </div>

          <dl className="grid grid-cols-2 gap-2 text-center">
            <div className="rounded-lg bg-muted/60 px-2 py-1.5">
              <dt className="text-[11px] text-muted-foreground">Ünite</dt>
              <dd className="text-sm font-semibold tabular-nums">{book.section_count}</dd>
            </div>
            <div className="rounded-lg bg-muted/60 px-2 py-1.5">
              <dt className="text-[11px] text-muted-foreground">
                {DENEME_TYPES.has(book.type) ? "Deneme" : "Test"}
              </dt>
              <dd className="text-sm font-semibold tabular-nums">{book.total_tests}</dd>
            </div>
          </dl>

          <MappingBar book={book} />

          {issues.length > 0 ? (
            <ul className="space-y-1 rounded-lg bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-500/10 dark:text-amber-200">
              {issues.map((m) => (
                <li key={m} className="flex gap-1.5">
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                  <span>{m}</span>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="mt-auto flex items-center justify-between gap-2 border-t border-border pt-2 text-xs">
            {students > 0 ? (
              <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300">
                <Users className="size-3.5" aria-hidden />
                <b className="tabular-nums">{students}</b> öğrencide kullanılıyor
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <Users className="size-3.5" aria-hidden />
                Henüz öğrenciye atanmadı
              </span>
            )}
            <span className="text-muted-foreground">{fmtDate(book.created_at)}</span>
          </div>
        </div>
      </article>
    </Link>
  );
}

function BookTable({ items }: { items: LibraryBookListItem[] }) {
  return (
    <Card>
      <div className="relative overflow-x-auto" data-testid="book-table">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Kitap</th>
              <th className="px-3 py-2 text-left font-medium">Ders</th>
              <th className="px-3 py-2 text-left font-medium">Tür</th>
              <th className="px-3 py-2 text-left font-medium">
                <ColumnHint label="Sınıf" hint="Kitabın hedeflediği sınıf aralığı. Boşsa tüm sınıflara uygundur." />
              </th>
              <th className="px-3 py-2 text-right font-medium">
                <ColumnHint label="Ünite" hint="Kitaptaki ünite (bölüm) sayısı. Görevler ünite bazında verilir." />
              </th>
              <th className="px-3 py-2 text-right font-medium">
                <ColumnHint label="Test" hint="Tüm ünitelerdeki test sayılarının toplamı. Deneme kitaplarında deneme sayısı." />
              </th>
              <th className="px-3 py-2 text-right font-medium">
                <ColumnHint
                  label="Müfredata bağlı"
                  hint="Resmi müfredat konusuna bağlı ünite sayısı. Bağlı olmayan ünite konu analizlerinde ve müfredat ilerlemesinde sayılmaz."
                />
              </th>
              <th className="px-3 py-2 text-right font-medium">
                <ColumnHint label="Öğrenci" hint="Bu kitabın atandığı aktif öğrenci sayısı." />
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((b) => {
              const tone = TYPE_TONE[b.type];
              const mapped = b.mapped_section_count;
              const deneme = DENEME_TYPES.has(b.type);
              const students = activeStudents(b);
              return (
                <tr key={b.id} className="hover:bg-muted/40" data-testid="book-row">
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/teacher/library/books/${b.id}`}
                      className="font-medium break-words hover:underline"
                    >
                      {b.name}
                    </Link>
                    <div className="text-xs text-muted-foreground break-words">
                      {b.publisher ?? "Yayınevi belirtilmemiş"}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">{b.subject_name ?? "—"}</td>
                  <td className="px-3 py-2.5">
                    <span className="inline-flex items-center gap-1.5">
                      <span className={cn("size-2 rounded-full", tone.dot)} aria-hidden />
                      {LIBRARY_BOOK_TYPE_LABELS_TR[b.type]}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-muted-foreground">{gradeLabel(b) ?? "Tümü"}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {b.section_count === 0 ? (
                      <span className="font-medium text-amber-700 dark:text-amber-300">0 — ekle</span>
                    ) : (
                      b.section_count
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{b.total_tests}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {deneme || mapped === undefined || b.section_count === 0 ? (
                      <span className="text-muted-foreground">—</span>
                    ) : mapped >= b.section_count ? (
                      <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300">
                        <CheckCircle2 className="size-3.5" aria-hidden />
                        {mapped}/{b.section_count}
                      </span>
                    ) : (
                      <span className="font-medium text-amber-700 dark:text-amber-300">
                        {mapped}/{b.section_count}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums">
                    {students > 0 ? students : <span className="text-muted-foreground">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// =============================================================================
// Kütüphane sekmeleri (Kitaplar / Setler / Kitap şablonları / Görev şablonları)
// =============================================================================

const TABS: Array<{
  href: string;
  title: string;
  hint: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}> = [
  {
    href: "/teacher/library",
    title: "Kitaplar",
    hint: "Tüm kitapların — ara, süz, yeni ekle.",
    icon: BookOpen,
  },
  {
    href: "/teacher/library/book-sets",
    title: "Kitap setleri",
    hint: "Birkaç kitabı paket yap, öğrencilere tek seferde ata.",
    icon: FileStack,
  },
  {
    href: "/teacher/library/templates",
    title: "Kitap şablonları",
    hint: "Bir kitabın ünite yapısını kaydet, başka kitaba uygula.",
    icon: LayoutTemplate,
  },
  {
    href: "/teacher/library/task-templates",
    title: "Görev şablonları",
    hint: "Sık verdiğin görevleri kaydet, programa tek tıkla ekle.",
    icon: GraduationCap,
  },
];

export function LibraryTabs() {
  const pathname = usePathname();
  return (
    <nav aria-label="Kütüphane bölümleri">
      <ul className="grid grid-cols-2 gap-1 border-b border-border sm:flex sm:flex-wrap">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active =
            t.href === "/teacher/library"
              ? pathname === "/teacher/library"
              : pathname.startsWith(t.href);
          return (
            <li key={t.href}>
              <Link
                href={t.href}
                title={t.hint}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm transition-colors",
                  active
                    ? "border-foreground font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden />
                {t.title}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
