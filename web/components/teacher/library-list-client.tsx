"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  FileStack,
  GraduationCap,
  LayoutTemplate,
  Library as LibraryIcon,
  Plus,
  SearchX,
  Users,
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

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// =============================================================================
// Görsel sabit haritalar
// =============================================================================

/**
 * Kitap tipi → kart sol şeridi + ince badge tonları.
 *
 * Jinja'daki TYPE_COLOR ile aynı semantik (indigo/emerald/amber/rose/violet),
 * shadcn-flavored — açık background değil `ring-1 ring-inset {tone}/10` koyu mod
 * uyumlu.
 */
const TYPE_TONE: Record<
  LibraryBookType,
  {
    border: string;
    ring: string;
    dot: string;
    badge: string;
  }
> = {
  soru_bankasi: {
    border: "border-l-indigo-500",
    ring: "ring-indigo-500/10",
    dot: "bg-indigo-500",
    badge: "text-indigo-700 dark:text-indigo-300 ring-indigo-500/30",
  },
  fasikul: {
    border: "border-l-emerald-500",
    ring: "ring-emerald-500/10",
    dot: "bg-emerald-500",
    badge: "text-emerald-700 dark:text-emerald-300 ring-emerald-500/30",
  },
  konu_anlatimli: {
    border: "border-l-amber-500",
    ring: "ring-amber-500/10",
    dot: "bg-amber-500",
    badge: "text-amber-700 dark:text-amber-300 ring-amber-500/30",
  },
  brans_denemesi: {
    border: "border-l-rose-500",
    ring: "ring-rose-500/10",
    dot: "bg-rose-500",
    badge: "text-rose-700 dark:text-rose-300 ring-rose-500/30",
  },
  genel_deneme: {
    border: "border-l-violet-500",
    ring: "ring-violet-500/10",
    dot: "bg-violet-500",
    badge: "text-violet-700 dark:text-violet-300 ring-violet-500/30",
  },
};

const SUBJECT_TONES: Array<{ dot: string; text: string }> = [
  { dot: "bg-indigo-500",  text: "text-indigo-600 dark:text-indigo-400" },
  { dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
  { dot: "bg-amber-500",   text: "text-amber-600 dark:text-amber-400" },
  { dot: "bg-rose-500",    text: "text-rose-600 dark:text-rose-400" },
  { dot: "bg-violet-500",  text: "text-violet-600 dark:text-violet-400" },
  { dot: "bg-cyan-500",    text: "text-cyan-600 dark:text-cyan-400" },
  { dot: "bg-fuchsia-500", text: "text-fuchsia-600 dark:text-fuchsia-400" },
  { dot: "bg-sky-500",     text: "text-sky-600 dark:text-sky-400" },
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

const GRADE_LEVELS: number[] = [5, 6, 7, 8, 9, 10, 11, 12];

// =============================================================================
// Tipler
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
}

// =============================================================================
// Yardımcılar
// =============================================================================

function groupBySubject(items: LibraryBookListItem[]): SubjectGroup[] {
  const map = new Map<number, SubjectGroup>();
  for (const it of items) {
    const sid = it.subject_id;
    const sname = it.subject_name ?? "Diğer";
    const g = map.get(sid);
    if (g) {
      g.items.push(it);
      g.total_sections += it.section_count;
      g.total_tests += it.total_tests;
    } else {
      map.set(sid, {
        subject_id: sid,
        subject_name: sname,
        items: [it],
        total_sections: it.section_count,
        total_tests: it.total_tests,
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
    parts.push(lo === hi ? `${lo}. sınıf` : `${lo}–${hi}`);
  } else if (lo !== null) {
    parts.push(`${lo}+`);
  } else if (hi !== null) {
    parts.push(`≤${hi}`);
  }
  if (grad) parts.push("Mezun");
  return parts.join(" · ");
}

/** Bir kitap belirli bir sınıf seviyesini kapsıyor mu? */
function bookCoversGrade(b: LibraryBookListItem, grade: number): boolean {
  const { target_grade_min: lo, target_grade_max: hi, target_graduate: grad } = b;
  if (lo === null && hi === null && !grad) return true; // belirtilmemiş → tüm seviyeler
  const min = lo ?? 5;
  const max = hi ?? 12;
  return grade >= min && grade <= max;
}

// =============================================================================
// Ana component
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

  const [qInput, setQInput] = React.useState(initialFilters.q);
  const [lastSyncedQ, setLastSyncedQ] = React.useState(initialFilters.q);
  if (urlQ !== lastSyncedQ) {
    setLastSyncedQ(urlQ);
    setQInput(urlQ);
  }
  const [, startTransition] = React.useTransition();
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchRef = React.useRef<HTMLInputElement>(null);

  const params: LibraryBooksListParams = React.useMemo(
    () => ({
      q: urlQ || undefined,
      type: urlType || undefined,
      subject_id: urlSubject ? Number(urlSubject) : undefined,
      grade_level: urlGrade ? Number(urlGrade) : undefined,
    }),
    [urlQ, urlType, urlSubject, urlGrade],
  );

  const isSameAsInitial =
    urlQ === initialFilters.q &&
    urlType === initialFilters.type &&
    Number(urlSubject || 0) === (initialFilters.subject_id ?? 0) &&
    Number(urlGrade || 0) === (initialFilters.grade_level ?? 0);

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

  // Backend filter'i (q/type/subject_id/grade_level) zaten uygulanmış kitaplar.
  // Müfredat filtresi backend'de yok — frontend'de subject.curriculum_model
  // üzerinden hard-filter uygulanır.
  const data = booksQ.data;
  const apiItems = React.useMemo(() => data?.items ?? [], [data]);

  const allSubjects = React.useMemo(
    () => subjectsQ.data?.items ?? [],
    [subjectsQ.data],
  );
  const subjectById = React.useMemo(() => {
    const m = new Map<number, SubjectRef>();
    for (const s of allSubjects) m.set(s.id, s);
    return m;
  }, [allSubjects]);

  function bookCurriculum(b: LibraryBookListItem): CurriculumModel | "other" {
    const s = subjectById.get(b.subject_id);
    return (s?.curriculum_model as CurriculumModel | null) ?? "other";
  }

  // Müfredat sayımları: KİTAP sayısı (subject sayısı değil) — kullanıcı
  // "Maarif'te kaç kitabım var" diye düşünür, "kaç ders" değil.
  // Backend filter'i sonrası kalan kitaplardan hesaplanır.
  const curriculumCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const cm of CURRICULUM_MODEL_ORDER) c[cm] = 0;
    c.other = 0;
    for (const b of apiItems) {
      const k = bookCurriculum(b);
      c[k] = (c[k] ?? 0) + 1;
    }
    return c;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiItems, subjectById]);

  // Default müfredat: URL'de yoksa, en dolu olan ilk müfredat
  // (LGS → Maarif → Klasik → Diğer sırasında ilk count>0).
  const effectiveCurriculum: string = React.useMemo(() => {
    if (urlCurriculum) return urlCurriculum;
    for (const cm of CURRICULUM_MODEL_ORDER) {
      if ((curriculumCounts[cm] ?? 0) > 0) return cm;
    }
    if ((curriculumCounts.other ?? 0) > 0) return "other";
    return CURRICULUM_MODEL_ORDER[0]; // LGS — tüm sayımlar 0 ise
  }, [urlCurriculum, curriculumCounts]);

  // Müfredat hard-filter — kitap subject'inin curriculum_model'i aktif
  // müfredatla eşleşmeli. Bu bug fix: 8. sınıf LGS kitabı Maarif filtresinde
  // görünmemeli.
  const items = React.useMemo(() => {
    return apiItems.filter((b) => bookCurriculum(b) === effectiveCurriculum);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiItems, effectiveCurriculum, subjectById]);

  const groups = React.useMemo(() => groupBySubject(items), [items]);

  const overall = React.useMemo(() => {
    let sections = 0;
    let tests = 0;
    for (const it of items) {
      sections += it.section_count;
      tests += it.total_tests;
    }
    return { books: items.length, sections, tests };
  }, [items]);

  // Tip + Sınıf sayımları aktif müfredat içinde
  const typeCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of BOOK_TYPES) c[t] = 0;
    for (const it of items) c[it.type] = (c[it.type] ?? 0) + 1;
    return c;
  }, [items]);

  const gradeCounts = React.useMemo(() => {
    const c: Record<string, number> = {};
    for (const g of GRADE_LEVELS) c[String(g)] = 0;
    c.graduate = 0;
    for (const it of items) {
      if (it.target_graduate) c.graduate += 1;
      for (const g of GRADE_LEVELS) {
        if (bookCoversGrade(it, g)) c[String(g)] += 1;
      }
    }
    return c;
  }, [items]);

  function applyParams(mutate: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(sp.toString());
    mutate(next);
    const qs = next.toString();
    startTransition(() => {
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
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

  function resetFilters() {
    setQInput("");
    applyParams((p) => {
      p.delete("q");
      p.delete("type");
      p.delete("subject_id");
      p.delete("grade_level");
      p.delete("curriculum");
    });
  }

  // Klavye: `/` ile arama focus, Esc ile temizle / blur
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName ?? "";
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        searchRef.current?.focus();
      } else if (
        e.key === "Escape" &&
        document.activeElement === searchRef.current
      ) {
        if (qInput) {
          onChangeQ("");
        } else {
          searchRef.current?.blur();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput]);

  React.useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // "Aktif filtre" göstergesi: müfredat default ise sayılmaz (her zaman seçili)
  const hasActiveFilter = Boolean(urlQ || urlType || urlSubject || urlGrade);

  // Aktif müfredata göre subject chip-bar filtresi
  const visibleSubjects: SubjectRef[] = React.useMemo(() => {
    if (effectiveCurriculum === "other") {
      return allSubjects.filter((s) => !s.curriculum_model);
    }
    return allSubjects.filter((s) => s.curriculum_model === effectiveCurriculum);
  }, [allSubjects, effectiveCurriculum]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Kütüphane
          </h1>
          <p
            className="text-sm text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1"
            aria-live="polite"
          >
            <KpiSpan label="kitap" value={overall.books} />
            <span className="text-muted-foreground/40" aria-hidden>·</span>
            <KpiSpan label="ünite" value={overall.sections} />
            <span className="text-muted-foreground/40" aria-hidden>·</span>
            <KpiSpan label="test" value={overall.tests} />
            {booksQ.isFetching && !booksQ.isLoading ? (
              <span className="text-xs text-muted-foreground/70">
                · güncelleniyor…
              </span>
            ) : null}
          </p>
        </div>
        <Button asChild>
          <Link href="/teacher/library/new">
            <Plus className="size-4" aria-hidden />
            Yeni kitap
          </Link>
        </Button>
      </header>

      <LibraryNav />

      <FilterBar
        searchRef={searchRef}
        qInput={qInput}
        onChangeQ={onChangeQ}
        urlSubject={urlSubject}
        urlType={urlType}
        urlGrade={urlGrade}
        effectiveCurriculum={effectiveCurriculum}
        subjects={visibleSubjects}
        curriculumCounts={curriculumCounts}
        typeCounts={typeCounts}
        gradeCounts={gradeCounts}
        totalBooks={overall.books}
        onSubject={(v) =>
          applyParams((p) => {
            if (v) p.set("subject_id", v);
            else p.delete("subject_id");
          })
        }
        onType={(v) =>
          applyParams((p) => {
            if (v) p.set("type", v);
            else p.delete("type");
          })
        }
        onGrade={(v) =>
          applyParams((p) => {
            if (v) p.set("grade_level", v);
            else p.delete("grade_level");
          })
        }
        onCurriculum={(v) =>
          applyParams((p) => {
            p.set("curriculum", v);
            // Müfredat değişince seçili ders artık görünmüyorsa onu da düşür
            const sid = p.get("subject_id");
            if (sid) {
              const s = allSubjects.find((x) => String(x.id) === sid);
              if (!s) {
                p.delete("subject_id");
              } else if (v !== "other" && s.curriculum_model !== v) {
                p.delete("subject_id");
              } else if (v === "other" && s.curriculum_model) {
                p.delete("subject_id");
              }
            }
          })
        }
        onReset={resetFilters}
        hasActiveFilter={hasActiveFilter}
      />

      {booksQ.isLoading && !data ? (
        <EmptyShell
          icon={<LibraryIcon className="size-8 text-muted-foreground/60" aria-hidden />}
          title="Yükleniyor…"
        />
      ) : items.length === 0 ? (
        hasActiveFilter ? (
          <EmptyShell
            icon={<SearchX className="size-8 text-muted-foreground/60" aria-hidden />}
            title="Eşleşen kitap yok"
            description="Filtreyi gevşetmeyi veya başka bir kelime aramayı deneyebilirsin."
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
            description="Üstteki Yeni Kitap butonuyla kütüphaneni oluşturmaya başla."
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
      ) : (
        <div className="space-y-6">
          {groups.map((g) => (
            <SubjectSection key={g.subject_id} group={g} />
          ))}
        </div>
      )}
    </div>
  );
}

function KpiSpan({ label, value }: { label: string; value: number }) {
  return (
    <span>
      <span className="font-medium text-foreground tabular-nums">{value}</span>{" "}
      {label}
    </span>
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
      <CardContent className="p-10 text-center space-y-2">
        <div className="flex justify-center">{icon}</div>
        <p className="text-sm font-medium">{title}</p>
        {description ? (
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            {description}
          </p>
        ) : null}
        {action ? <div className="pt-2">{action}</div> : null}
      </CardContent>
    </Card>
  );
}

// =============================================================================
// Filter bar
// =============================================================================

interface SubjectRefLike {
  id: number;
  name: string;
}

function FilterBar({
  searchRef,
  qInput,
  onChangeQ,
  urlSubject,
  urlType,
  urlGrade,
  effectiveCurriculum,
  subjects,
  curriculumCounts,
  typeCounts,
  gradeCounts,
  totalBooks,
  onSubject,
  onType,
  onGrade,
  onCurriculum,
  onReset,
  hasActiveFilter,
}: {
  searchRef: React.RefObject<HTMLInputElement | null>;
  qInput: string;
  onChangeQ: (v: string) => void;
  urlSubject: string;
  urlType: string;
  urlGrade: string;
  effectiveCurriculum: string;
  subjects: SubjectRefLike[];
  curriculumCounts: Record<string, number>;
  typeCounts: Record<string, number>;
  gradeCounts: Record<string, number>;
  totalBooks: number;
  onSubject: (v: string) => void;
  onType: (v: string) => void;
  onGrade: (v: string) => void;
  onCurriculum: (v: string) => void;
  onReset: () => void;
  hasActiveFilter: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <div className="px-4 py-3 border-b border-border">
          <div className="relative">
            <Input
              ref={searchRef}
              type="search"
              placeholder="Kitap, yayınevi veya ünite ara…  (/  ile odakla)"
              value={qInput}
              onChange={(e) => onChangeQ(e.target.value)}
              aria-label="Kitap ara"
              className="w-full"
            />
          </div>
        </div>

        <ChipRow label="Müfredat">
          {CURRICULUM_MODEL_ORDER.map((cm) => {
            const count = curriculumCounts[cm] ?? 0;
            if (count === 0 && effectiveCurriculum !== cm) return null;
            return (
              <FilterChip
                key={cm}
                active={effectiveCurriculum === cm}
                onClick={() => onCurriculum(cm)}
                label={CURRICULUM_MODEL_LABELS_TR[cm]}
                count={count}
              />
            );
          })}
          {(curriculumCounts.other ?? 0) > 0 || effectiveCurriculum === "other" ? (
            <FilterChip
              active={effectiveCurriculum === "other"}
              onClick={() => onCurriculum("other")}
              label="Diğer"
              count={curriculumCounts.other ?? 0}
            />
          ) : null}
        </ChipRow>

        <ChipRow label="Ders">
          <FilterChip
            active={!urlSubject}
            onClick={() => onSubject("")}
            label="Tümü"
            count={totalBooks}
          />
          {subjects.map((s) => {
            const tone = subjectTone(s.id);
            return (
              <FilterChip
                key={s.id}
                active={urlSubject === String(s.id)}
                onClick={() => onSubject(String(s.id))}
                label={s.name}
                dotClassName={tone.dot}
              />
            );
          })}
        </ChipRow>

        <ChipRow label="Tip">
          <FilterChip
            active={!urlType}
            onClick={() => onType("")}
            label="Tümü"
          />
          {BOOK_TYPES.map((t) => {
            const count = typeCounts[t] ?? 0;
            if (count === 0 && urlType !== t) return null;
            const tone = TYPE_TONE[t];
            return (
              <FilterChip
                key={t}
                active={urlType === t}
                onClick={() => onType(t)}
                label={LIBRARY_BOOK_TYPE_LABELS_TR[t]}
                dotClassName={tone.dot}
                count={count}
              />
            );
          })}
        </ChipRow>

        <ChipRow label="Sınıf" trailing={hasActiveFilter ? (
          <button
            type="button"
            onClick={onReset}
            className="ml-auto text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
          >
            Filtreleri temizle
          </button>
        ) : null}>
          <FilterChip
            active={!urlGrade}
            onClick={() => onGrade("")}
            label="Tümü"
          />
          {GRADE_LEVELS.map((g) => {
            const count = gradeCounts[String(g)] ?? 0;
            if (count === 0 && urlGrade !== String(g)) return null;
            return (
              <FilterChip
                key={g}
                active={urlGrade === String(g)}
                onClick={() => onGrade(String(g))}
                label={`${g}. sınıf`}
                count={count}
              />
            );
          })}
          {gradeCounts.graduate > 0 || urlGrade === "graduate" ? (
            <FilterChip
              active={urlGrade === "graduate"}
              onClick={() => onGrade("graduate")}
              label="Mezun"
              icon={<GraduationCap className="size-3" aria-hidden />}
              count={gradeCounts.graduate}
            />
          ) : null}
        </ChipRow>
      </CardContent>
    </Card>
  );
}

function ChipRow({
  label,
  children,
  trailing,
}: {
  label: string;
  children: React.ReactNode;
  trailing?: React.ReactNode;
}) {
  return (
    <div className="px-4 py-2.5 border-b border-border last:border-b-0 flex items-center gap-2 flex-wrap">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mr-1 shrink-0">
        {label}
      </span>
      {children}
      {trailing}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
  dotClassName,
  count,
  icon,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  dotClassName?: string;
  count?: number;
  icon?: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 border text-xs transition-colors",
        active
          ? "border-foreground bg-foreground text-background"
          : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {dotClassName ? (
        <span
          className={cn("inline-block size-1.5 rounded-full", dotClassName)}
          aria-hidden
        />
      ) : null}
      {icon}
      <span>{label}</span>
      {count !== undefined ? (
        <span className={cn("tabular-nums", active ? "opacity-70" : "opacity-60")}>
          {count}
        </span>
      ) : null}
    </button>
  );
}

// =============================================================================
// Ders bölümü + kart
// =============================================================================

function SubjectSection({ group }: { group: SubjectGroup }) {
  const tone = subjectTone(group.subject_id);
  return (
    <section className="space-y-3">
      <header className="flex items-baseline gap-2">
        <span
          className={cn("inline-block size-2 rounded-full", tone.dot)}
          aria-hidden
        />
        <h2
          className={cn(
            "text-sm font-semibold uppercase tracking-wider",
            tone.text,
          )}
        >
          {group.subject_name}
        </h2>
        <span className="text-xs text-muted-foreground">
          <span className="tabular-nums font-medium text-foreground">
            {group.items.length}
          </span>{" "}
          kitap
          <span className="text-muted-foreground/40 mx-1.5" aria-hidden>·</span>
          <span className="tabular-nums font-medium text-foreground">
            {group.total_sections}
          </span>{" "}
          ünite
          <span className="text-muted-foreground/40 mx-1.5" aria-hidden>·</span>
          <span className="tabular-nums font-medium text-foreground">
            {group.total_tests}
          </span>{" "}
          test
        </span>
      </header>
      <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {group.items.map((b) => (
          <li key={b.id}>
            <BookCard book={b} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function BookCard({ book }: { book: LibraryBookListItem }) {
  const tone = TYPE_TONE[book.type];
  const grade = gradeLabel(book);

  return (
    <Link
      href={`/teacher/library/books/${book.id}`}
      className="group block h-full"
    >
      <Card
        className={cn(
          "h-full border-l-4 ring-1 ring-inset transition-colors hover:border-foreground/30",
          tone.border,
          tone.ring,
        )}
      >
        <CardContent className="p-4 flex flex-col h-full gap-2">
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium leading-snug line-clamp-2 group-hover:underline">
              {book.name}
            </p>
            {grade ? (
              <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground whitespace-nowrap">
                {grade}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground truncate">
            {book.publisher ?? (
              <span className="italic text-muted-foreground/70">
                Yayınevi belirtilmemiş
              </span>
            )}
          </p>
          <div className="mt-auto pt-2 border-t border-border flex items-center justify-between gap-2">
            <span
              className={cn(
                "text-[10px] font-medium px-2 py-0.5 rounded-full ring-1 ring-inset inline-flex items-center gap-1",
                tone.badge,
              )}
            >
              <span
                className={cn("inline-block size-1.5 rounded-full", tone.dot)}
                aria-hidden
              />
              {LIBRARY_BOOK_TYPE_LABELS_TR[book.type]}
            </span>
            <span className="text-[11px] text-muted-foreground">
              <span className="tabular-nums font-medium text-foreground">
                {book.section_count}
              </span>{" "}
              ünite
              <span className="text-muted-foreground/40 mx-1" aria-hidden>·</span>
              <span className="tabular-nums font-medium text-foreground">
                {book.total_tests}
              </span>{" "}
              test
            </span>
          </div>
          {book.assigned_student_count > 0 ? (
            <p className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
              <Users className="size-3" aria-hidden />
              <span className="tabular-nums font-medium text-foreground">
                {book.assigned_student_count}
              </span>{" "}
              öğrenciye atalı
            </p>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}

// =============================================================================
// LibraryNav (Kitaplar / Setler / Şablonlar üst kartları — 3.5d.2)
// =============================================================================

const NAV_ITEMS: Array<{
  href: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  tone: "indigo" | "amber" | "emerald";
}> = [
  {
    href: "/teacher/library",
    title: "Kitaplar",
    description:
      "Tüm kitapları, fasikül ve denemeleri tek listede ara, filtrele ve yeni ekle.",
    icon: BookOpen,
    tone: "indigo",
  },
  {
    href: "/teacher/library/book-sets",
    title: "Kitap setleri",
    description:
      "Sınıf/alan bazlı hazır paketler — tek atamayla bir öğrenciye birkaç kitabı bir arada ver.",
    icon: FileStack,
    tone: "amber",
  },
  {
    href: "/teacher/library/templates",
    title: "Kitap şablonları",
    description:
      "Bir kitabın ünite/bölüm yapısını kaydet, başka kitaplara tek tıkla uygula.",
    icon: LayoutTemplate,
    tone: "emerald",
  },
  {
    href: "/teacher/library/task-templates",
    title: "Görev şablonları",
    description:
      "Sık kullandığın görev kalıpları (kitap+bölüm+test sayısı). Plana eklerken tek tıkla aynı görevi uygula.",
    icon: LayoutTemplate,
    tone: "indigo",
  },
];

const NAV_TONE_CLASSES: Record<
  "indigo" | "amber" | "emerald",
  { border: string; ring: string; icon: string; accent: string }
> = {
  indigo: {
    border: "border-l-indigo-500",
    ring: "ring-indigo-500/10",
    icon: "text-indigo-500",
    accent: "group-hover:text-indigo-500",
  },
  amber: {
    border: "border-l-amber-500",
    ring: "ring-amber-500/10",
    icon: "text-amber-500",
    accent: "group-hover:text-amber-500",
  },
  emerald: {
    border: "border-l-emerald-500",
    ring: "ring-emerald-500/10",
    icon: "text-emerald-500",
    accent: "group-hover:text-emerald-500",
  },
};

function LibraryNav() {
  return (
    <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const t = NAV_TONE_CLASSES[item.tone];
        return (
          <li key={item.href}>
            <Link href={item.href} className="group block">
              <Card
                className={cn(
                  "border-l-4 ring-1 ring-inset h-full transition-colors hover:border-foreground/30",
                  t.border,
                  t.ring,
                )}
              >
                <CardContent className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className={cn("size-5", t.icon)} aria-hidden />
                      <p
                        className={cn(
                          "font-medium leading-tight transition-colors",
                          t.accent,
                        )}
                      >
                        {item.title}
                      </p>
                    </div>
                    <ArrowRight
                      className="size-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
                      aria-hidden
                    />
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {item.description}
                  </p>
                </CardContent>
              </Card>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
