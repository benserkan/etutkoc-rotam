"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
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
  { n: 1, label: "Bilgiler", icon: BookOpen },
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
          Sistem seni adım adım yönlendirecek — her adımda ne yapıldığını
          açıklar, önerilen yolu vurgular.
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
        />
      ) : null}

      {step >= 2 && book ? (
        <>
          {step === 2 ? (
            <StepSections
              book={book}
              isExam={isExam}
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
// 1) Bilgiler
// =============================================================================

function StepInfo({
  subjects,
  templates,
  onCreated,
}: {
  subjects: SubjectRef[];
  templates: BookTemplateListItem[];
  onCreated: (book: LibraryBookDetailResponse) => void;
}) {
  return (
    <div className="space-y-3">
      <StepNarration>
        <strong>1. Adım — Kitap bilgileri.</strong> Ders, tip ve hedef sınıfı
        seç. YKS kitabı için <strong>“Sınav Müfredatı (TYT / AYT)”</strong>{" "}
        grubundan dersi seçmen, sonraki adımları kolaylaştırır.
      </StepNarration>
      <BookCreateForm
        subjects={subjects}
        templates={templates}
        onCreated={onCreated}
        submitLabel="Oluştur ve devam et"
        hideCancel
      />
    </div>
  );
}

// =============================================================================
// 2) Üniteler
// =============================================================================

function StepSections({
  book,
  isExam,
  onBack,
  onNext,
}: {
  book: LibraryBookDetailResponse;
  isExam: boolean;
  onBack: (() => void) | null;
  onNext: () => void;
}) {
  const hasSections = book.sections.length > 0;
  const [method, setMethod] = React.useState<"catalog" | "ai" | "manual" | null>(
    null,
  );

  const catalogMut = useBulkSectionsFromCatalog(book.id);
  const aiMut = useAiSuggestSections(book.id);

  const topicsQ = useQuery<TopicListResponse>({
    queryKey: ["library", "subject-topics", book.subject_id],
    queryFn: () => getLibraryTopics(book.subject_id),
    staleTime: 60_000,
  });
  const topicCount = topicsQ.data?.items.length ?? 0;
  const defaultCount = book.avg_questions_per_test ?? 10;

  function addCatalog() {
    const items = (topicsQ.data?.items ?? []).map((t) => ({
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
              <Check className="inline size-4 text-emerald-600" aria-hidden />{" "}
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
        <div className="grid gap-3 sm:grid-cols-3">
          {/* Katalog */}
          <MethodCard
            recommended={isExam}
            active={method === "catalog"}
            icon={ListChecks}
            title="Resmi konulardan ekle"
            desc={
              isExam
                ? `Bu ders için ${topicCount || "resmi"} konu hazır — tek tıkla ekle, müfredata otomatik eşli gelir (eşleştirme adımı atlanır).`
                : `Bu dersin resmi konularını (${topicCount || "—"}) hazır ekle.`
            }
            onClick={() => setMethod("catalog")}
          />
          {/* AI */}
          <MethodCard
            recommended={!isExam}
            active={method === "ai"}
            icon={Wand2}
            title="Yapay zekâ önersin"
            desc="Kitap adı ve yayınevinden ünite listesini yapay zekâ oluştursun (ücretli pakette)."
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

      {!hasSections && method === "catalog" ? (
        <Card>
          <CardContent className="p-4 space-y-3">
            <p className="text-sm text-muted-foreground">
              {topicsQ.isLoading
                ? "Konular yükleniyor…"
                : topicCount > 0
                  ? `${topicCount} resmi konu, her biri ${defaultCount} test ile eklenecek. Sonra fazlalıkları çıkarabilirsin.`
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
                                "border-amber-400 bg-amber-50 text-amber-900",
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
  onBack,
  onDone,
}: {
  book: LibraryBookDetailResponse;
  students: TeacherStudentListItem[];
  onBack: () => void;
  onDone: () => void;
}) {
  const active = React.useMemo(
    () => students.filter((s) => s.is_active),
    [students],
  );
  const [sel, setSel] = React.useState<Set<number>>(new Set());
  const assignMut = useAssignBookToStudents(book.id);

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
      { onSuccess: onDone },
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

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ArrowLeft className="size-4" aria-hidden /> Geri
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onDone}>
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
