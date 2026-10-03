"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Camera,
  Check,
  Copy,
  Library,
  CheckCircle2,
  ListChecks,
  Loader2,
  PenLine,
  Sparkles,
  Users,
  Wand2,
} from "lucide-react";

import {
  getBookMappingSuggestions,
  getLibraryBook,
  getLibraryTopics,
  libraryKeys,
} from "@/lib/api/library";
import {
  useAiSuggestSections,
  useApplyMapping,
  useAssignBookToStudents,
  useBulkSectionsFromCatalog,
  useCreateSection,
} from "@/lib/hooks/use-library-mutations";
import type {
  BookTemplateListItem,
  LibraryBookDetailResponse,
  MappingSuggestionsResponse,
  SubjectRef,
  TopicListResponse,
} from "@/lib/types/library";
import type { TeacherStudentListItem } from "@/lib/types/teacher";
import { isExamSubject } from "@/lib/utils/subjects";

import { BookCreateForm } from "@/components/teacher/book-create-form";
import {
  BookScanUpload,
  CatalogBrowser,
  useCatalogApply,
  useCatalogBrowse,
} from "@/components/book-catalog/catalog-quick-start";
import { PhotoReadPanel } from "@/components/book-catalog/photo-read-panel";
import { useContributeCatalog } from "@/lib/hooks/use-book-catalog-mutations";
import type { BookScanResult, StructureReadResult } from "@/lib/types/book-catalog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

/**
 * Kitap Ekleme Sihirbazı — koçu adım adım yönlendiren akış.
 *
 * 1 Bilgiler → 2 Üniteler (AI / Katalog / Elle) → 3 Müfredat eşleştirme →
 * 4 Öğrenci atama → Özet. Sistem her adımda ne yaptığını anlatır ve önerilen
 * yolu vurgular. Tüm uçlar mevcut (oluştur/ai-suggest/katalog/eşleştir/ata) —
 * sihirbaz yalnız orkestrasyon. Sekmeli kitap detayı düzenleme için durur.
 */

const STEPS = [
  { n: 1, label: "Başlangıç", icon: BookOpen },
  { n: 2, label: "Üniteler", icon: ListChecks },
  { n: 3, label: "Eşleştirme", icon: Sparkles },
  { n: 4, label: "Öğrenci", icon: Users },
] as const;

interface Props {
  subjects: SubjectRef[];
  templates: BookTemplateListItem[];
  students: TeacherStudentListItem[];
}

export function BookWizardClient({ subjects, templates, students }: Props) {
  const [step, setStep] = React.useState(1);
  const [bookId, setBookId] = React.useState<number | null>(null);
  // Katalogdan oluşturulan kitap TEKRAR kataloğa önerilmez (mükerrer katkı yok)
  const [fromCatalog, setFromCatalog] = React.useState(false);
  // 1. adımda "Kapak + içindekiler" ile okunan taslak — form ön-dolumu + 2. adım
  const [scanned, setScanned] = React.useState<BookScanResult | null>(null);

  const bookQ = useQuery<LibraryBookDetailResponse>({
    queryKey: bookId ? libraryKeys.book(bookId) : ["library", "book", "none"],
    queryFn: () => getLibraryBook(bookId as number),
    enabled: bookId != null,
    staleTime: 10_000,
  });
  const book = bookQ.data;
  const subject = React.useMemo(
    () => (book ? subjects.find((s) => s.id === book.subject_id) : undefined),
    [book, subjects],
  );
  const isExam = subject ? isExamSubject(subject) : false;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Yeni kitap
        </h1>
        <p className="text-sm text-muted-foreground">
          Birkaç soruyla kitabını kütüphanene ekleyelim — yolu sen seç, gerisini
          sistem adım adım gösterir.
        </p>
      </header>

      <Stepper current={step} />

      {step === 1 ? (
        <StepInfo
          subjects={subjects}
          templates={templates}
          onCreated={(b) => {
            setBookId(b.id);
            setStep(2);
          }}
          scanned={scanned}
          onScanned={setScanned}
          onCreatedFromCatalog={(b) => {
            setScanned(null);
            setFromCatalog(true);
            setBookId(b.id);
            setStep(2);
          }}
        />
      ) : null}

      {step >= 2 && book ? (
        <>
          {step === 2 ? (
            <StepSections
              book={book}
              isExam={isExam}
              scanned={scanned?.structure ?? null}
              onBack={null}
              onNext={() => setStep(3)}
            />
          ) : null}
          {step === 3 ? (
            <StepMapping
              book={book}
              onBack={() => setStep(2)}
              onNext={() => setStep(4)}
            />
          ) : null}
          {step === 4 ? (
            <StepAssign
              book={book}
              students={students}
              canContribute={!fromCatalog}
              onBack={() => setStep(3)}
              onDone={() => setStep(5)}
            />
          ) : null}
          {step === 5 ? <StepSummary book={book} /> : null}
        </>
      ) : null}

      {step >= 2 && bookQ.isLoading ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

// =============================================================================
// Stepper
// =============================================================================

function Stepper({ current }: { current: number }) {
  return (
    <ol className="flex items-center gap-1 sm:gap-2" aria-label="Adımlar">
      {STEPS.map((s, i) => {
        const done = current > s.n;
        const active = current === s.n || (current === 5 && s.n === 4);
        const Icon = s.icon;
        return (
          <li key={s.n} className="flex items-center gap-1 sm:gap-2 min-w-0">
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium border",
                done
                  ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200"
                  : active
                    ? "border-cyan-400 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-200"
                    : "border-border bg-muted/40 text-muted-foreground",
              )}
            >
              {done ? (
                <Check className="size-3.5" aria-hidden />
              ) : (
                <Icon className="size-3.5" aria-hidden />
              )}
              <span className="hidden sm:inline">{s.label}</span>
              <span className="sm:hidden">{s.n}</span>
            </div>
            {i < STEPS.length - 1 ? (
              <div
                className={cn(
                  "h-px w-3 sm:w-6",
                  done ? "bg-emerald-300" : "bg-border",
                )}
                aria-hidden
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function StepNarration({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border-l-4 border-l-cyan-500 border border-cyan-200 bg-cyan-50 px-4 py-2.5 text-sm text-cyan-900 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-100">
      {children}
    </div>
  );
}

// =============================================================================
// 1) Başlangıç — "Ne yapmak istiyorsun?" + seçilen yol
// =============================================================================

type StartPath = "catalog" | "scan" | "manual" | "template";

const PATH_TITLES: Record<StartPath, string> = {
  catalog: "Hazır bir kitap ekle",
  scan: "Kitabım elimde, tarat",
  manual: "Kitabı kendim tanımlayacağım",
  template: "Kendi şablonumdan başla",
};

function StepInfo({
  subjects,
  templates,
  scanned,
  onScanned,
  onCreated,
  onCreatedFromCatalog,
}: {
  subjects: SubjectRef[];
  templates: BookTemplateListItem[];
  scanned: BookScanResult | null;
  onScanned: (r: BookScanResult | null) => void;
  onCreated: (book: LibraryBookDetailResponse) => void;
  onCreatedFromCatalog: (book: LibraryBookDetailResponse) => void;
}) {
  const [path, setPath] = React.useState<StartPath | null>(scanned ? "scan" : null);
  const browseQ = useCatalogBrowse();
  const catalog = useCatalogApply(onCreatedFromCatalog);

  const choose = (p: StartPath | null) => {
    if (p !== "scan") onScanned(null);
    setPath(p);
  };

  if (path === null) {
    return (
      <StartChoice
        catalogCount={browseQ.data?.total ?? null}
        templateCount={templates.length}
        onChoose={choose}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid={`path-${path}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={() => choose(null)}>
          <ArrowLeft className="size-4" aria-hidden /> Başka yol seç
        </Button>
        <span className="text-sm text-muted-foreground">
          Seçimin: <strong className="text-foreground">{PATH_TITLES[path]}</strong>
        </span>
      </div>

      {path === "catalog" ? (
        <Card>
          <CardContent className="space-y-4 p-4 sm:p-5">
            <div>
              <h2 className="text-lg font-semibold">Kitabını katalogda bul</h2>
              <p className="text-sm text-muted-foreground">
                Kitaba dokunup üniteleri ve test sayılarını görebilirsin. Doğruysa{" "}
                <strong>Kütüphaneme ekle</strong> — üniteler, test sayıları ve müfredat
                eşleşmesi hazır gelir.
              </p>
            </div>
            <CatalogBrowser onApply={catalog.apply} busy={catalog.isPending} />
            <NotFoundFooter
              text="Aradığın kitap katalogda yok mu?"
              actions={[
                { label: "Kitabı tarat", onClick: () => choose("scan") },
                { label: "Kendim tanımlayacağım", onClick: () => choose("manual") },
              ]}
            />
          </CardContent>
        </Card>
      ) : null}

      {path === "scan" ? (
        <>
          <Card>
            <CardContent className="space-y-4 p-4 sm:p-5">
              <div>
                <h2 className="text-lg font-semibold">Kapağı ve içindekileri yükle</h2>
                <p className="text-sm text-muted-foreground">
                  Sistem kapaktan kitabı tanır. Katalogda varsa yapısı hazır gelir; yoksa
                  içindekiler iki kez okunur ve test sayıları kitaptan alınır (yazmıyorsa
                  sayfa aralığından tahmin edilir).
                </p>
              </div>
              <BookScanUpload
                onApply={catalog.apply}
                onScanned={onScanned}
                busy={catalog.isPending}
              />
            </CardContent>
          </Card>
          {scanned?.structure ? (
            <div className="space-y-2">
              <h2 className="text-lg font-semibold">Kitap bilgilerini tamamla</h2>
              <p className="text-sm text-muted-foreground">
                Ad ve yayınevi kitaptan okundu — kontrol et, <strong>ders</strong> ve{" "}
                <strong>sınıf</strong> seç.
              </p>
              <BookCreateForm
                key={`scan-${scanned.book_title ?? ""}-${scanned.structure.sections.length}`}
                initialName={scanned.book_title}
                initialPublisher={scanned.publisher}
                subjects={subjects}
                templates={templates}
                templateMode="hide"
                onCreated={onCreated}
                submitLabel="Oluştur ve bölümlere geç"
                hideCancel
              />
            </div>
          ) : (
            <NotFoundFooter
              text="Kitap elinde değil mi?"
              actions={[
                { label: "Katalogda göz at", onClick: () => choose("catalog") },
                { label: "Kendim tanımlayacağım", onClick: () => choose("manual") },
              ]}
            />
          )}
        </>
      ) : null}

      {path === "manual" || path === "template" ? (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">
            {path === "template" ? "Şablonu seç, kitabı adlandır" : "Kitabın bilgileri"}
          </h2>
          <p className="text-sm text-muted-foreground">
            {path === "template"
              ? "Ünite yapısı ve test sayıları seçtiğin şablondan gelir."
              : "Üniteleri bir sonraki adımda resmi konulardan, yapay zekâyla, içindekiler fotoğrafından ya da elle eklersin."}
          </p>
          <BookCreateForm
            subjects={subjects}
            templates={templates}
            templateMode={path === "template" ? "required" : "hide"}
            onCreated={onCreated}
            submitLabel="Oluştur ve devam et"
            hideCancel
          />
        </div>
      ) : null}
    </div>
  );
}

function StartChoice({
  catalogCount,
  templateCount,
  onChoose,
}: {
  catalogCount: number | null;
  templateCount: number;
  onChoose: (p: StartPath) => void;
}) {
  const options: {
    path: StartPath;
    icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
    title: string;
    desc: string;
    meta: string;
    badge?: string;
    tone: string;
  }[] = [
    {
      path: "catalog",
      icon: Library,
      title: PATH_TITLES.catalog,
      desc:
        catalogCount != null
          ? `Katalogda ${catalogCount} kitap var. Üniteleri ve test sayıları hazır — bul, tek dokunuşla kütüphanene ekle.`
          : "Katalogdaki kitaplardan seç; üniteleri ve test sayıları hazır gelir.",
      meta: "Yaklaşık 10 saniye",
      badge: "En hızlı",
      tone: "bg-emerald-600",
    },
    {
      path: "scan",
      icon: Camera,
      title: PATH_TITLES.scan,
      desc: "Kapağın ve içindekilerin fotoğrafını ya da kitabın PDF’ini yükle. Sistem kitabı tanır; katalogda yoksa içindekilerden oluşturur.",
      meta: "Yaklaşık 1 dakika",
      tone: "bg-violet-600",
    },
    {
      path: "manual",
      icon: PenLine,
      title: PATH_TITLES.manual,
      desc: "Adını, dersini ve sınıfını gir. Üniteleri sonra resmi konulardan, yapay zekâyla ya da elle eklersin.",
      meta: "Yaklaşık 3-5 dakika",
      tone: "bg-slate-700",
    },
  ];
  if (templateCount > 0) {
    options.push({
      path: "template",
      icon: Copy,
      title: PATH_TITLES.template,
      desc: `Kayıtlı ${templateCount} kitap şablonun var — ünite yapısı şablondan gelir, yalnız adı ve dersi seçersin.`,
      meta: "Yaklaşık 1 dakika",
      tone: "bg-amber-600",
    });
  }
  return (
    <div className="space-y-4" data-testid="start-choice">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Ne yapmak istiyorsun?</h2>
        <p className="text-sm text-muted-foreground">
          Seçimine göre sana uygun adımlar açılacak. İstediğin an geri dönüp başka yol seçebilirsin.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {options.map((o) => {
          const Icon = o.icon;
          return (
            <button
              key={o.path}
              type="button"
              onClick={() => onChoose(o.path)}
              className="group relative flex h-full flex-col gap-3 rounded-2xl border border-border bg-card p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-cyan-500 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
              data-testid={`choose-${o.path}`}
            >
              {o.badge ? (
                <span className="absolute right-4 top-4 rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] font-semibold text-white">
                  {o.badge}
                </span>
              ) : null}
              <span className={cn("inline-flex size-11 items-center justify-center rounded-xl text-white", o.tone)}>
                <Icon className="size-5" aria-hidden />
              </span>
              <span className="text-base font-semibold">{o.title}</span>
              <span className="text-sm text-muted-foreground">{o.desc}</span>
              <span className="mt-auto flex items-center justify-between pt-1 text-xs text-muted-foreground">
                <span>{o.meta}</span>
                <ArrowRight
                  className="size-4 text-cyan-700 transition group-hover:translate-x-0.5 dark:text-cyan-300"
                  aria-hidden
                />
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function NotFoundFooter({
  text,
  actions,
}: {
  text: string;
  actions: { label: string; onClick: () => void }[];
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-muted/60 px-4 py-3">
      <span className="text-sm font-medium">{text}</span>
      <span className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <Button key={a.label} type="button" size="sm" variant="outline" onClick={a.onClick}>
            {a.label}
          </Button>
        ))}
      </span>
    </div>
  );
}

// =============================================================================
// 2) Üniteler
// =============================================================================

function StepSections({
  book,
  isExam,
  scanned,
  onBack,
  onNext,
}: {
  book: LibraryBookDetailResponse;
  isExam: boolean;
  scanned: StructureReadResult | null;
  onBack: (() => void) | null;
  onNext: () => void;
}) {
  const hasSections = book.sections.length > 0;
  const [method, setMethod] = React.useState<
    "photo" | "catalog" | "ai" | "manual" | null
  >(scanned ? "photo" : null);

  const catalogMut = useBulkSectionsFromCatalog(book.id);
  const aiMut = useAiSuggestSections(book.id);

  const topicsQ = useQuery<TopicListResponse>({
    queryKey: ["library", "subject-topics", book.subject_id],
    queryFn: () => getLibraryTopics(book.subject_id),
    staleTime: 60_000,
  });
  const allTopics = React.useMemo(() => topicsQ.data?.items ?? [], [topicsQ.data]);
  const defaultCount = book.avg_questions_per_test ?? 10;

  // Sınıf-yayılan derslerde (LGS/Maarif) "hepsini ekle" yanlış sınıf konularını da
  // ekler → sınıf çipleriyle daralt. Varsayılan = kitabın hedef sınıf aralığı.
  const grades = React.useMemo(
    () =>
      Array.from(
        new Set(
          allTopics
            .map((t) => t.grade_level)
            .filter((g): g is number => g != null),
        ),
      ).sort((a, b) => a - b),
    [allTopics],
  );
  const defaultGrades = React.useMemo(() => {
    const lo = book.target_grade_min;
    const hi = book.target_grade_max;
    if (lo != null && hi != null) {
      const inRange = grades.filter((g) => g >= lo && g <= hi);
      if (inRange.length) return new Set(inRange);
    }
    return new Set(grades);
  }, [grades, book.target_grade_min, book.target_grade_max]);
  const [gradeSel, setGradeSel] = React.useState<Set<number> | null>(null);
  const selGrades = gradeSel ?? defaultGrades;
  const selectedTopics = allTopics.filter(
    (t) => t.grade_level == null || selGrades.has(t.grade_level),
  );
  const topicCount = selectedTopics.length;

  function toggleGrade(g: number) {
    setGradeSel((prev) => {
      const base = prev ?? defaultGrades;
      const n = new Set(base);
      if (n.has(g)) n.delete(g);
      else n.add(g);
      return n;
    });
  }
  function addCatalog() {
    const items = selectedTopics.map((t) => ({
      topic_id: t.id,
      test_count: defaultCount,
    }));
    if (items.length === 0) return;
    catalogMut.mutate({ body: { items } });
  }
  function runAi() {
    aiMut.mutate({ body: {} });
  }

  return (
    <div className="space-y-4">
      <StepNarration>
        <strong>2. Adım — Üniteleri oluştur.</strong> Kitabın bölümlerini
        (ünitelerini) ekleyelim. Aşağıdan bir yol seç; sistem önerileni vurguladı.
      </StepNarration>

      {method !== "manual" && hasSections ? (
        <Card>
          <CardContent className="p-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm">
              <Check className="inline size-4 text-emerald-600 dark:text-emerald-300" aria-hidden />{" "}
              <strong>{book.sections.length} ünite</strong> eklendi
              {" · "}
              {book.sections.filter((s) => s.topic_id).length} müfredata eşli
            </p>
            <Button onClick={onNext}>
              Devam <ArrowRight className="size-4" aria-hidden />
            </Button>
          </CardContent>
        </Card>
      ) : method !== "manual" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {/* Fotoğraftan oku — birebir test sayıları (YENİ, önerilen) */}
          <MethodCard
            recommended
            active={method === "photo"}
            icon={Camera}
            title="Fotoğraftan oku"
            desc="Kitabın İçindekiler sayfasını çek — üniteler ve test sayıları KİTAPTAN birebir okunur (kredi harcamaz)."
            onClick={() => setMethod("photo")}
          />
          {/* Katalog */}
          <MethodCard
            recommended={false}
            active={method === "catalog"}
            icon={ListChecks}
            title="Resmi konulardan ekle"
            desc={
              isExam
                ? `Bu ders için ${topicCount || "resmi"} konu hazır — müfredata otomatik eşli gelir; test sayılarını sonra düzeltirsin.`
                : `Bu dersin resmi konularını (${topicCount || "—"}) hazır ekle; test sayılarını sonra düzeltirsin.`
            }
            onClick={() => setMethod("catalog")}
          />
          {/* AI */}
          <MethodCard
            recommended={false}
            active={method === "ai"}
            icon={Wand2}
            title="Yapay zekâ önersin"
            desc="Kitap adı ve yayınevinden tipik ünite yapısını yapay zekâ tahmin etsin (ücretli pakette; birebir değildir)."
            onClick={() => setMethod("ai")}
          />
          {/* Manuel — bu dalda method asla "manual" değil (seçilince ayrı panel) */}
          <MethodCard
            recommended={false}
            active={false}
            icon={PenLine}
            title="Elle gir"
            desc="Üniteleri tek tek kendin ekle."
            onClick={() => setMethod("manual")}
          />
        </div>
      ) : null}

      {!hasSections && method === "photo" ? (
        <PhotoReadPanel book={book} initial={scanned} />
      ) : null}

      {!hasSections && method === "catalog" ? (
        <Card>
          <CardContent className="p-4 space-y-3">
            {grades.length > 1 ? (
              <div className="space-y-1.5">
                <div className="text-[11px] font-semibold text-muted-foreground">
                  Sınıf seç (kitabın hedefine göre ön-seçili):
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {grades.map((g) => {
                    const on = selGrades.has(g);
                    const cnt = allTopics.filter((t) => t.grade_level === g).length;
                    return (
                      <button
                        key={g}
                        type="button"
                        onClick={() => toggleGrade(g)}
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-xs font-medium transition",
                          on
                            ? "border-cyan-500 bg-cyan-50 text-cyan-900 dark:bg-cyan-500/10 dark:border-cyan-500/30 dark:text-cyan-200"
                            : "border-border text-muted-foreground hover:bg-muted/50",
                        )}
                        aria-pressed={on}
                      >
                        {g}. sınıf ({cnt})
                      </button>
                    );
                  })}
                </div>
              </div>
            ) : null}
            <p className="text-sm text-muted-foreground">
              {topicsQ.isLoading
                ? "Konular yükleniyor…"
                : topicCount > 0
                  ? `${topicCount} resmi konu, her biri ${defaultCount} test ile eklenecek. Sonra fazlalıkları çıkarabilirsin.`
                  : grades.length > 1
                    ? "Seçili sınıfta resmi konu yok — başka sınıf seç ya da yapay zekâ/elle gir."
                    : "Bu derste resmi konu bulunamadı — yapay zekâ veya elle gir."}
            </p>
            <Button
              onClick={addCatalog}
              disabled={catalogMut.isPending || topicCount === 0}
            >
              {catalogMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <ListChecks className="size-4" aria-hidden />
              )}
              {topicCount} konuyu ekle
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {!hasSections && method === "ai" ? (
        <Card>
          <CardContent className="p-4 space-y-3">
            <p className="text-sm text-muted-foreground">
              Yapay zekâ kitabın tipik ünite yapısını önerecek. Sonra gözden
              geçirip düzeltebilirsin.
            </p>
            <Button onClick={runAi} disabled={aiMut.isPending}>
              {aiMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Wand2 className="size-4" aria-hidden />
              )}
              Yapay zekâ ile öner
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {method === "manual" ? (
        <div className="space-y-3">
          <ManualSections book={book} />
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setMethod(null)}>
              <ArrowLeft className="size-4" aria-hidden /> Yöntem seç
            </Button>
            <Button onClick={onNext} disabled={book.sections.length === 0}>
              Devam <ArrowRight className="size-4" aria-hidden />
            </Button>
          </div>
        </div>
      ) : null}

      {onBack ? (
        <div>
          <Button variant="ghost" onClick={onBack}>
            <ArrowLeft className="size-4" aria-hidden /> Geri
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function MethodCard({
  recommended,
  active,
  icon: Icon,
  title,
  desc,
  onClick,
}: {
  recommended: boolean;
  active: boolean;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative rounded-lg border p-3 text-left transition-colors h-full",
        active
          ? "border-cyan-500 bg-cyan-50 dark:bg-cyan-500/10"
          : recommended
            ? "border-cyan-300 hover:bg-muted/50"
            : "border-border hover:bg-muted/50",
      )}
      aria-pressed={active}
    >
      {recommended ? (
        <span className="absolute -top-2 right-2 rounded-full bg-cyan-600 px-2 py-0.5 text-[10px] font-medium text-white">
          Önerilen
        </span>
      ) : null}
      <Icon className="size-5 text-cyan-700 dark:text-cyan-300" aria-hidden />
      <p className="mt-1.5 text-sm font-semibold">{title}</p>
      <p className="mt-0.5 text-[11px] text-muted-foreground">{desc}</p>
    </button>
  );
}

function ManualSections({ book }: { book: LibraryBookDetailResponse }) {
  const [label, setLabel] = React.useState("");
  const [count, setCount] = React.useState("10");
  const createMut = useCreateSection(book.id);

  function add() {
    const l = label.trim();
    if (!l) return;
    createMut.mutate(
      { body: { label: l, test_count: Number(count) || 1 } },
      { onSuccess: () => setLabel("") },
    );
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {book.sections.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {book.sections.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between rounded border border-border px-2 py-1"
              >
                <span>{s.label}</span>
                <span className="text-xs text-muted-foreground">
                  {s.test_count} test
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Henüz ünite yok.</p>
        )}
        <div className="flex items-end gap-2">
          <div className="flex-1 space-y-1">
            <Label htmlFor="ms-label" className="text-xs">
              Ünite adı
            </Label>
            <Input
              id="ms-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="örn. 1. Ünite — Temel Kavramlar"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add();
                }
              }}
            />
          </div>
          <div className="w-20 space-y-1">
            <Label htmlFor="ms-count" className="text-xs">
              Test
            </Label>
            <Input
              id="ms-count"
              type="number"
              min={1}
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </div>
          <Button onClick={add} disabled={createMut.isPending || !label.trim()}>
            {createMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              "Ekle"
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================================
// 3) Müfredat eşleştirme
// =============================================================================

function StepMapping({
  book,
  onBack,
  onNext,
}: {
  book: LibraryBookDetailResponse;
  onBack: () => void;
  onNext: () => void;
}) {
  const total = book.sections.length;
  const mappedAll = total > 0 && book.sections.every((s) => s.topic_id != null);

  const [ai, setAi] = React.useState(false);
  const [sel, setSel] = React.useState<Record<number, number | "">>({});
  const q = useQuery<MappingSuggestionsResponse>({
    queryKey: libraryKeys.mappingSuggestions(book.id, ai),
    queryFn: () => getBookMappingSuggestions(book.id, ai),
    enabled: !mappedAll,
    staleTime: 30_000,
  });
  const applyMut = useApplyMapping(book.id);
  const data = q.data;
  const topics = data?.candidate_topics ?? [];

  type Row = MappingSuggestionsResponse["rows"][number];
  function valueFor(r: Row): number | "" {
    if (r.section_id in sel) return sel[r.section_id];
    return r.current_topic_id ?? r.suggested_topic_id ?? "";
  }

  function onApply() {
    if (!data) {
      onNext();
      return;
    }
    const items = data.rows
      .map((r) => {
        const v = valueFor(r);
        return { section_id: r.section_id, topic_id: v === "" ? null : Number(v) };
      })
      .filter((it) => {
        const r = data.rows.find((x) => x.section_id === it.section_id)!;
        return it.topic_id !== (r.current_topic_id ?? null);
      });
    if (items.length === 0) {
      onNext();
      return;
    }
    applyMut.mutate({ items }, { onSuccess: onNext });
  }

  if (mappedAll) {
    return (
      <div className="space-y-4">
        <StepNarration>
          <strong>3. Adım — Müfredat eşleştirme.</strong> Üniteler resmi
          konulardan eklendiği için <strong>hepsi otomatik eşlendi</strong> —
          bu adımda yapacak bir şey yok.
        </StepNarration>
        <Card>
          <CardContent className="p-4 flex items-center justify-between gap-3">
            <p className="text-sm text-emerald-700 dark:text-emerald-300">
              <CheckCircle2 className="inline size-4" aria-hidden /> {total}/{total}{" "}
              ünite müfredata eşli
            </p>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onBack}>
                <ArrowLeft className="size-4" aria-hidden /> Geri
              </Button>
              <Button onClick={onNext}>
                Devam <ArrowRight className="size-4" aria-hidden />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const mapped = data ? data.mapped_count : 0;
  const pending = data
    ? data.rows.filter((r) => {
        const v = valueFor(r);
        const tid = v === "" ? null : Number(v);
        return tid !== (r.current_topic_id ?? null);
      }).length
    : 0;

  return (
    <div className="space-y-4">
      <StepNarration>
        <strong>3. Adım — Müfredat eşleştirme.</strong> Her ünitenin hangi resmi
        konu olduğunu işaretliyoruz (öğrencinin müfredatta nerede olduğunu görmek
        için). <strong>Sistem çoğunu otomatik eşledi</strong> — kontrol et,
        gerekirse değiştir, sonra devam et.
      </StepNarration>

      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-muted-foreground">
              {q.isLoading
                ? "Eşleştiriliyor…"
                : `${mapped}/${total} eşli${pending > 0 ? ` · ${pending} öneri uygulanacak` : ""}`}
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setAi(true)}
              disabled={ai && q.isFetching}
            >
              {ai && q.isFetching ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Wand2 className="size-3.5" aria-hidden />
              )}
              Yapay zekâ ile öner
            </Button>
          </div>

          <div className="max-h-[45vh] overflow-y-auto rounded-md border border-border">
            {q.isLoading ? (
              <div className="p-6 text-center">
                <Loader2 className="mx-auto size-5 animate-spin" aria-hidden />
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-xs text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Ünite</th>
                    <th className="px-3 py-2 text-left font-medium">Resmi konu</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {(data?.rows ?? []).map((r) => {
                    const suggested = r.source === "auto" || r.source === "ai";
                    return (
                      <tr key={r.section_id}>
                        <td className="px-3 py-2 align-top">
                          <span className="font-medium text-foreground">
                            {r.label}
                          </span>
                        </td>
                        <td className="px-3 py-2 align-top">
                          <select
                            value={
                              valueFor(r) === "" ? "" : String(valueFor(r))
                            }
                            onChange={(e) =>
                              setSel((p) => ({
                                ...p,
                                [r.section_id]:
                                  e.target.value === ""
                                    ? ""
                                    : Number(e.target.value),
                              }))
                            }
                            className={cn(
                              "w-full rounded-md border border-input bg-background px-2 py-1 text-sm",
                              suggested &&
                                valueFor(r) === r.suggested_topic_id &&
                                "border-amber-400 bg-amber-50 dark:bg-amber-500/15 dark:border-amber-500/30 text-amber-900 dark:text-amber-200",
                            )}
                          >
                            <option value="">— eşleşmemiş —</option>
                            {topics.map((t) => (
                              <option key={t.id} value={t.id}>
                                {t.name}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden /> Geri
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onNext}>
            Atla
          </Button>
          <Button onClick={onApply} disabled={applyMut.isPending || q.isLoading}>
            {applyMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Check className="size-4" aria-hidden />
            )}
            Eşleştir ve devam
          </Button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// 4) Öğrenci atama
// =============================================================================

function StepAssign({
  book,
  students,
  canContribute,
  onBack,
  onDone,
}: {
  book: LibraryBookDetailResponse;
  students: TeacherStudentListItem[];
  canContribute: boolean;
  onBack: () => void;
  onDone: () => void;
}) {
  const active = React.useMemo(
    () => students.filter((s) => s.is_active),
    [students],
  );
  const [sel, setSel] = React.useState<Set<number>>(new Set());
  const [share, setShare] = React.useState(true);
  const assignMut = useAssignBookToStudents(book.id);
  const contribute = useContributeCatalog();

  // Katkı yalnız anlamlı yapıda önerilir (katalogdan gelmemiş + ≥2 bölüm)
  const showShare = canContribute && book.sections.length >= 2;

  function maybeContribute() {
    if (!showShare || !share) return;
    // Best-effort — koçun akışını asla bloklamaz; mükerrerse sunucu sessizce geçer.
    contribute.mutate({
      name: book.name,
      publisher: book.publisher,
      type: book.type,
      subject_id: book.subject_id,
      target_grade_min: book.target_grade_min,
      target_grade_max: book.target_grade_max,
      target_graduate: book.target_graduate,
      sections: book.sections.map((s) => ({
        label: s.label,
        test_count: s.test_count,
        topic_id: s.topic_id,
      })),
    });
  }
  function finish() {
    maybeContribute();
    onDone();
  }
  function toggle(id: number) {
    setSel((p) => {
      const n = new Set(p);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }
  function assign() {
    assignMut.mutate(
      { body: { student_ids: Array.from(sel) } },
      { onSuccess: finish },
    );
  }

  return (
    <div className="space-y-4">
      <StepNarration>
        <strong>4. Adım — Öğrenci ata.</strong> Bu kitabı hangi öğrencilere
        atayalım? (Atamadan da bitirebilirsin; sonra kitap detayından
        ekleyebilirsin.)
      </StepNarration>

      <Card>
        <CardContent className="p-4">
          {active.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aktif öğrenci yok.</p>
          ) : (
            <ul className="max-h-[45vh] overflow-y-auto divide-y divide-border">
              {active.map((s) => (
                <li key={s.id}>
                  <label className="flex items-center gap-3 px-1 py-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={sel.has(s.id)}
                      onChange={() => toggle(s.id)}
                    />
                    <span className="text-sm">{s.full_name}</span>
                    {s.grade_level ? (
                      <span className="text-xs text-muted-foreground">
                        {s.grade_level}. sınıf
                      </span>
                    ) : null}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {showShare ? (
        <label className="flex cursor-pointer items-start gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-sm">
          <input
            type="checkbox"
            checked={share}
            onChange={(e) => setShare(e.target.checked)}
            className="mt-0.5"
          />
          <span className="text-muted-foreground">
            Bu kitabın yapısını (ünite + test sayıları){" "}
            <strong className="text-foreground">ortak kataloğa öner</strong> —
            onaylanırsa diğer koçlar tek tıkla kullanır.{" "}
            <span className="text-xs">Adın görünmez; öğrenci verisi paylaşılmaz.</span>
          </span>
        </label>
      ) : null}

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden /> Geri
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={finish}>
            Atla
          </Button>
          <Button
            onClick={assign}
            disabled={assignMut.isPending || sel.size === 0}
          >
            {assignMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Users className="size-4" aria-hidden />
            )}
            {sel.size > 0 ? `${sel.size} öğrenciye ata ve bitir` : "Ata ve bitir"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// 5) Özet
// =============================================================================

function StepSummary({ book }: { book: LibraryBookDetailResponse }) {
  const total = book.sections.length;
  const mapped = book.sections.filter((s) => s.topic_id != null).length;
  const assigned = book.assigned_students.length;

  return (
    <Card>
      <CardContent className="p-6 space-y-4 text-center">
        <CheckCircle2
          className="mx-auto size-12 text-emerald-500"
          aria-hidden
        />
        <div>
          <h2 className="text-lg font-semibold">Kitap hazır 🎉</h2>
          <p className="text-sm text-muted-foreground mt-1">{book.name}</p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm">
          <span>
            <strong>{total}</strong> ünite
          </span>
          <span className="text-muted-foreground/40" aria-hidden>·</span>
          <span>
            <strong>{mapped}</strong> müfredata eşli
          </span>
          <span className="text-muted-foreground/40" aria-hidden>·</span>
          <span>
            <strong>{assigned}</strong> öğrenciye atalı
          </span>
        </div>
        <div className="flex items-center justify-center gap-2 pt-2">
          <Button asChild variant="outline">
            <Link href="/teacher/library">Kütüphaneye dön</Link>
          </Button>
          <Button asChild>
            <Link href={`/teacher/library/books/${book.id}`}>
              Kitaba git <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
