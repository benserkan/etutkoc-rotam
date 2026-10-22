"use client";

/**
 * Havuza kalem ekle — rehber editörü (2026-10-13; kurallar K14/K16/K24–K28).
 *
 * İki yol, üstte sekme:
 *  · Adım adım — üç adım, her adım seçilince tek satırlık özete katlanır ("Değiştir" ile geri açılır):
 *      1 Ders     → müfredattaki yerinde (okul / TYT / AYT); kitabı olan derste çipte "2 kitap" rozeti
 *      2 Nereden? → [Öğrencinin kitapları] kitabın KENDİ bölümleri (kalan · havuzda bekleyen · SON) — konu
 *                   eşleştirmesine bakılmaz; kitaptan verilen kalem kap/seans işaretiyle KİTAP SAYACINI ilerletir.
 *                   [Müfredat konusu] kitabı sistemde olmayan öğrenci için: resmi konu, sayıyı rehber yazar
 *                   (öğrenciye kalanı sorarak), kitap adı yalnız NOT. Konu öğrencinin bir kitabında varsa
 *                   "kitaptan ver" önerisi çıkar (kitap takibi kaçmasın).
 *      3 Miktar   → birim · 1-5/başka/kalanı ver · ek seçenekler katlı · "Havuza ekle · N test"
 *    Ekledikten sonra ders + yol seçili kalır (aynı kitaptan art arda ekleme hızlı).
 *  · Hızlı yaz — tek satır serbest metin (K28 deterministik ayrıştırma; sonuç önce gösterilir, sessizce yazılmaz).
 *
 * Ders seçimi editörde tutulur (eksik ders şeridinden tıklanınca bu panel o derse atlar).
 */

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  BookMarked, BookOpen, Check, ChevronDown, ClipboardCheck, Layers, ListTree, Lock, NotebookPen, PenLine, Plus, Search, Sparkles, Wand2,
} from "lucide-react";

import { DenemeForm } from "@/components/teacher/weekly-plan/deneme-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { getPageSuggestion, teacherKeys } from "@/lib/api/teacher";
import type { PageSuggestionResponse } from "@/lib/types/teacher";
import {
  getPoolBooks, getPoolTopics, parsePoolText, poolBooksKey, poolKeys, UNIT_LABELS, useAddPoolItem,
  useSetClassPosition,
  type ParseOption, type ParseResponse, type PoolBookOut, type PoolBookSectionOut, type PoolBundleResponse, type PoolItemBody,
  type PoolSubjectOut, type PoolTopicOut, type PoolTopicsResponse, type PoolUnit,
} from "@/lib/api/pool";

type Choice =
  | { kind: "book"; book: PoolBookOut; section: PoolBookSectionOut }
  | { kind: "topic"; topic: PoolTopicOut }
  | { kind: "none" };

/** Son seçilen yer — ekledikten sonra liste baştan değil buradan açılır (koç art arda aynı bölgeden verir). */
type Anchor = { tab: "books" | "topics"; bookId?: number; sectionId?: number; topicId?: number; grade?: number | null };

/** Kaydırılabilir listede işaretli satırı görünür yap (yalnız listeyi kaydırır, sayfayı değil). */
function useScrollToAnchor(ref: React.RefObject<HTMLElement | null>, selector: string | null, ready: boolean) {
  const doneRef = React.useRef(false);
  React.useLayoutEffect(() => {
    if (doneRef.current || !ready || !selector || !ref.current) return;
    const box = ref.current;
    const el = box.querySelector<HTMLElement>(selector);
    if (!el) return;
    doneRef.current = true;
    const top = el.getBoundingClientRect().top - box.getBoundingClientRect().top + box.scrollTop;
    box.scrollTop = Math.max(0, top - 44);
  });
}

function trLower(s: string): string {
  return s.toLocaleLowerCase("tr-TR");
}

function sourceCountLabel(s: PoolSubjectOut): string | null {
  const parts = [];
  if (s.book_count) parts.push(`${s.book_count} kitap`);
  if (s.deneme_count) parts.push(`${s.deneme_count} deneme`);
  return parts.length ? parts.join(" · ") : null;
}

export function AddPanel({ studentId, data, subjectId, onSubject }: {
  studentId: number;
  data: PoolBundleResponse;
  subjectId: number | null;
  onSubject: (id: number | null) => void;
}) {
  const [mode, setMode] = React.useState<"steps" | "free" | "deneme">("steps");
  const [choice, setChoice] = React.useState<Choice | null>(null);
  // "tyt" = TYT (Maarif) çipinden seçildi → konular yalnız 9-10. sınıf (Maarif 11+)
  const [scope, setScope] = React.useState<"all" | "tyt">("all");
  const [anchor, setAnchor] = React.useState<Anchor | null>(null);
  const [lastSubject, setLastSubject] = React.useState(subjectId);
  // Ders dışarıdan (eksik ders şeridi) değişince seçim sıfırlanır — render sırasında (effect değil)
  if (lastSubject !== subjectId) {
    setLastSubject(subjectId);
    setChoice(null);
    setAnchor(null);
    setScope("all");
    if (subjectId != null) setMode("steps");
  }
  const subj = data.subjects.find((s) => s.id === subjectId) ?? null;
  const tytMax = data.tyt_maarif_max_grade ?? 10;
  const maxGrade = scope === "tyt" ? tytMax : null;
  const booksQ = useQuery({
    queryKey: poolBooksKey(studentId, subj?.id ?? 0),
    queryFn: () => getPoolBooks(studentId, subj!.id),
    enabled: subj != null,
  });
  const books = booksQ.data?.books ?? [];

  const choiceSummary = !choice ? null
    : choice.kind === "book" ? `${choice.book.name} › ${choice.section.label}`
    : choice.kind === "topic" ? `Müfredat konusu › ${choice.topic.name}`
    : "Konusuz kalem (kendi etiketin)";

  function bookFromSource(bookId: number, sectionId: number): Choice | null {
    const b = books.find((x) => x.book_id === bookId);
    const sec = b?.sections.find((x) => x.section_id === sectionId);
    return b && sec ? { kind: "book", book: b, section: sec } : null;
  }

  return (
    <section className="overflow-hidden rounded-xl border bg-card shadow-sm" data-section="pool:add">
      <header className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
        <span className="grid size-9 place-items-center rounded-lg bg-cyan-700 text-white" aria-hidden>
          <Plus className="size-4" />
        </span>
        <div className="min-w-[12rem] flex-1">
          <h2 className="text-base font-semibold text-foreground">Havuza kalem ekle</h2>
          <p className="text-xs text-muted-foreground">Ders → kaynak ya da konu → miktar. Ya da tek satırda yaz.</p>
        </div>
        <div className="flex w-full rounded-lg bg-muted p-0.5 text-xs font-medium sm:w-auto [&>button]:flex-1 sm:[&>button]:flex-none" role="tablist" aria-label="Ekleme yolu">
          <TabBtn active={mode === "steps"} onClick={() => setMode("steps")} icon={<ListTree className="size-3.5" aria-hidden />}>Adım adım</TabBtn>
          <TabBtn active={mode === "free"} onClick={() => setMode("free")} icon={<Wand2 className="size-3.5" aria-hidden />}>Hızlı yaz</TabBtn>
          <TabBtn active={mode === "deneme"} onClick={() => setMode("deneme")} icon={<ClipboardCheck className="size-3.5" aria-hidden />}>Deneme</TabBtn>
        </div>
      </header>

      {mode === "deneme" ? (
        <div className="@container px-4 py-4">
          <DenemeForm studentId={studentId} target="pool" onAfterAdd={() => undefined} />
        </div>
      ) : mode === "free" ? (
        <FreeText studentId={studentId} data={data} subjectId={subjectId} />
      ) : (
        <ol className="divide-y">
          {/* 1 — Ders */}
          <Step n={1} title="Ders" done={!!subj}
                summary={subj ? `${subj.name}${scope === "tyt" ? ` · TYT (Maarif) · ${tytMax - 1}-${tytMax}. sınıf konuları` : subj.group === "sinav" ? " · sınav dersi" : data.curriculum_label ? ` · ${data.curriculum_label}` : ""}${sourceCountLabel(subj) ? ` · ${sourceCountLabel(subj)}` : ""}` : null}
                onEdit={subj ? () => onSubject(null) : undefined}>
            <SubjectPicker data={data} studentId={studentId}
                           onPick={(id, sc) => { onSubject(id); setLastSubject(id); setChoice(null); setAnchor(null); setScope(sc); }} />
          </Step>

          {/* 2 — Nereden? */}
          <Step n={2} title="Nereden?" disabled={!subj} done={choice != null} summary={choiceSummary}
                onEdit={choice != null ? () => setChoice(null) : undefined}>
            {subj && (
              <SourcePicker
                key={`${subj.id}-${scope}`}
                studentId={studentId}
                subject={subj}
                maxGrade={maxGrade}
                studentGrade={data.student.is_graduate ? null : data.student.grade_level}
                books={books}
                booksLoading={booksQ.isLoading}
                anchor={anchor}
                onPick={(c) => {
                  setChoice(c);
                  setAnchor(c.kind === "book" ? { tab: "books", bookId: c.book.book_id, sectionId: c.section.section_id }
                    : c.kind === "topic" ? { tab: "topics", topicId: c.topic.topic_id, grade: c.topic.grade_level }
                    : { tab: "topics" });
                }}
              />
            )}
          </Step>

          {/* 3 — Miktar */}
          <Step n={3} title="Miktar" disabled={!subj || choice == null} done={false}>
            {subj && choice != null && (
              <Composer
                key={choice.kind === "book" ? `b${choice.section.section_id}` : choice.kind === "topic" ? `t${choice.topic.topic_id}` : "none"}
                studentId={studentId}
                data={data}
                subjectId={subj.id}
                subjectName={subj.name}
                choice={choice}
                onSwitch={(bookId, sectionId) => { const c = bookFromSource(bookId, sectionId); if (c) setChoice(c); }}
                onDone={() => setChoice(null)}
              />
            )}
          </Step>
        </ol>
      )}
    </section>
  );
}

function ParseOptions({ options, base, pending, onPick }: {
  options: ParseOption[]; base: { quantity: number | null; unit: PoolUnit } | null; pending: boolean;
  onPick: (o: ParseOption) => void;
}) {
  const noQty = !base || (base.unit !== "etkinlik" && !base.quantity);
  const qtyText = base?.quantity ? `${base.quantity} ${UNIT_LABELS[base.unit] ?? base.unit}` : null;
  return (
    <div className="space-y-1.5" data-section="pool:add:parse-options">
      <div className="text-xs font-semibold text-foreground">Bunu mu demek istedin?</div>
      <div className="space-y-1">
        {options.map((o) => (
          <button key={`${o.subject_id}-${o.topic_id ?? "s"}`} type="button" disabled={pending || noQty} onClick={() => onPick(o)}
                  className="flex w-full items-start gap-2 rounded-lg border bg-background px-3 py-2 text-left text-sm transition hover:border-cyan-600 hover:bg-cyan-500/10 disabled:opacity-60">
            <Plus className="mt-0.5 size-4 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
            <span className="min-w-0 flex-1 break-words">
              <span className="font-medium text-foreground">{o.topic_name ?? o.subject_name}</span>
              <span className="mt-0.5 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-muted-foreground">
                <span className="rounded bg-muted px-1.5 font-medium text-foreground">{o.subject_name}</span>
                {o.grade_level != null && <span>{o.grade_level}. sınıf</span>}
                {o.unit_name && <span>· {o.unit_name}</span>}
                {o.section_id != null && <span className="rounded bg-cyan-700 px-1.5 font-semibold text-white">kitapta var</span>}
                {o.label && <span>· not: {o.label}</span>}
              </span>
            </span>
            {qtyText && <span className="shrink-0 rounded-md bg-cyan-700 px-1.5 py-0.5 text-[11px] font-semibold text-white">{qtyText}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function TabBtn({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <button type="button" role="tab" aria-selected={active} onClick={onClick}
            className={cn("inline-flex items-center justify-center gap-1.5 rounded-md px-3 py-1.5 transition",
              active ? "bg-cyan-700 text-white shadow-sm" : "text-muted-foreground hover:text-foreground")}>
      {icon}{children}
    </button>
  );
}

function Step({ n, title, done, disabled, summary, onEdit, children }: {
  n: number; title: string; done: boolean; disabled?: boolean; summary?: string | null; onEdit?: () => void;
  children?: React.ReactNode;
}) {
  const collapsed = done && !!summary;
  return (
    <li className={cn("px-4 py-3", disabled && "opacity-60")} data-step={n}>
      <div className="flex items-center gap-3">
        <span className={cn("grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold",
          done ? "bg-emerald-700 text-white" : disabled ? "bg-muted text-muted-foreground" : "bg-cyan-700 text-white")}
              aria-hidden>
          {done ? <Check className="size-3.5" /> : n}
        </span>
        <span className="text-sm font-semibold text-foreground">{title}</span>
        {collapsed && <span className="min-w-0 flex-1 break-words text-sm text-muted-foreground">{summary}</span>}
        {collapsed && onEdit && (
          <button type="button" onClick={onEdit} className="ml-auto shrink-0 text-xs font-medium text-cyan-700 underline-offset-2 hover:underline dark:text-cyan-300">
            Değiştir
          </button>
        )}
      </div>
      {!collapsed && !disabled && children && <div className="mt-3 sm:pl-9">{children}</div>}
    </li>
  );
}

// ---------------------------------------------------------------- 1 ders

function SubjectPicker({ data, studentId, onPick }: {
  data: PoolBundleResponse; studentId: number; onPick: (id: number, scope: "all" | "tyt") => void;
}) {
  if (data.subjects.length === 0) return <p className="text-xs text-muted-foreground">Öğrencinin dersi bulunamadı.</p>;
  // Tek yapı: her ders müfredattaki yerinde (okul / TYT / AYT) — kitabı olan ders de burada, çipteki rozetle.
  // Kitaplı dersi ayrı gruba çekmek onu müfredat listesinden düşürüyordu (koç kaynaksız görev için dersi bulamıyordu).
  const school = data.subjects.filter((s) => s.group !== "sinav");
  const tyt = data.subjects.filter((s) => s.group === "sinav" && !s.is_ayt);
  const ayt = data.subjects.filter((s) => s.group === "sinav" && s.is_ayt);
  // Maarif 11+: TYT konuları = 9-10. sınıf Maarif konuları (eski TYT taksonomisi değil); AYT = kendi sınıf müfredatı
  const tytMaarifIds = new Set(data.tyt_maarif_subject_ids ?? []);
  const tytMaarif = data.subjects.filter((s) => tytMaarifIds.has(s.id));
  const tytMax = data.tyt_maarif_max_grade ?? 10;
  const groups: Array<[string, string, PoolSubjectOut[]]> = [];
  // Klasik 11-12/mezun (sınav omurgası): okul grubunda yalnız kitabı olan dersler kalır (sunucu süzer)
  const examBackbone = tytMaarif.length === 0 && tyt.length + ayt.length > 0;
  const schoolTitle = examBackbone
    ? `Kitabı olan diğer dersler${data.curriculum_label ? ` · ${data.curriculum_label}` : ""}`
    : (data.curriculum_label ?? "Okul dersleri");
  if (school.length) groups.push(["okul", schoolTitle, school]);
  if (tytMaarif.length) groups.push(["tyt-maarif", `Sınav dersleri — TYT (Maarif) · ${tytMax - 1}-${tytMax}. sınıf konuları`, tytMaarif]);
  if (tyt.length) groups.push(["tyt", "Sınav dersleri — TYT", tyt]);
  if (ayt.length) groups.push(["ayt", "Sınav dersleri — AYT", ayt]);
  const titled = groups.length > 1;
  const anySource = data.subjects.some((s) => s.book_count + s.deneme_count > 0);
  return (
    <div className="space-y-3">
      {groups.map(([key, title, list]) => (
        <div key={key} data-subject-group={key}>
          {titled && (
            <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>
          )}
          <div className="flex flex-wrap gap-1.5">
            {list.map((s) => {
              const src = sourceCountLabel(s);
              return (
                <button key={s.id} type="button" onClick={() => onPick(s.id, key === "tyt-maarif" ? "tyt" : "all")}
                        className={cn("inline-flex items-center gap-1.5 rounded-lg border bg-background px-3 py-1.5 text-sm text-foreground transition hover:border-cyan-600 hover:bg-cyan-500/10",
                          src && "border-cyan-700/50", s.item_count > 0 && "border-amber-500 ring-1 ring-amber-500/40")}>
                  {src && <BookOpen className="size-3.5 text-cyan-700 dark:text-cyan-300" aria-hidden />}
                  {s.name}
                  {src && <span className="rounded-md bg-cyan-700 px-1.5 text-[10px] font-semibold text-white">{src}</span>}
                  {s.item_count > 0 && (
                    <span className="inline-flex items-center gap-1 rounded-md bg-amber-400 px-1.5 py-0.5 text-[11px] font-bold text-amber-950 ring-1 ring-amber-600"
                          title="Bu dönemin havuzunda bu dersten verilmiş kalem sayısı">
                      <Layers className="size-3" aria-hidden />havuzda {s.item_count} kalem
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {anySource && (
        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <BookOpen className="mt-0.5 size-3.5 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
          <span>Rozetli derslerde öğrencinin sistemde kitabı var. Her ders hem kitaptan hem müfredat konusundan (kaynaksız) verilebilir.</span>
        </p>
      )}
      {data.ayt_locked && (
        <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
          <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            Alan girilmedi — AYT dersleri ({data.locked_ayt_names.join(", ")}) kapalı. Öğrencinin alanını
            profilden seç; AYT kalemi ondan sonra eklenir.{" "}
            <Link href={`/teacher/students/${studentId}`} className="underline">Profili aç</Link>
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- 2 nereden?

function SourcePicker({ studentId, subject, maxGrade, studentGrade, books, booksLoading, anchor, onPick }: {
  studentId: number; subject: PoolSubjectOut; maxGrade: number | null; studentGrade: number | null; books: PoolBookOut[]; booksLoading: boolean;
  anchor: Anchor | null; onPick: (c: Choice) => void;
}) {
  const hasBooks = subject.book_count + subject.deneme_count > 0;
  const [tab, setTab] = React.useState<"books" | "topics">(anchor?.tab ?? (hasBooks ? "books" : "topics"));
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2" role="tablist" aria-label="Kalem nereden">
        <SourceOption active={tab === "books"} onClick={() => setTab("books")}
                      icon={<BookOpen className="size-4" aria-hidden />}
                      title={`Öğrencinin kitabından${hasBooks ? ` (${subject.book_count + subject.deneme_count})` : ""}`}
                      hint={hasBooks ? "Kitabın bölümünden ver — kitap sayacı ilerler" : "Bu derste kayıtlı kitap yok"} />
        <SourceOption active={tab === "topics"} onClick={() => setTab("topics")}
                      icon={<NotebookPen className="size-4" aria-hidden />}
                      title="Müfredat konusundan (kaynaksız)"
                      hint={maxGrade ? `${maxGrade - 1}-${maxGrade}. sınıf Maarif konuları (TYT) — sayıyı sen yaz` : "Resmi konu seç, sayıyı sen yaz"} />
      </div>
      {tab === "books" ? (
        hasBooks ? (
          <BookList books={books} loading={booksLoading} anchorBook={anchor?.bookId ?? null}
                    anchorSection={anchor?.sectionId ?? null} onPick={(book, section) => onPick({ kind: "book", book, section })} />
        ) : (
          <div className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
            Bu derste öğrencinin sistemde kayıtlı kitabı yok. Kitap atamak için öğrencinin Kitaplar sekmesini kullan ya da
            <button type="button" onClick={() => setTab("topics")} className="ml-1 font-medium text-cyan-700 underline-offset-2 hover:underline dark:text-cyan-300">
              müfredat konusundan ver
            </button>.
          </div>
        )
      ) : (
        <>
          {!hasBooks && (
            <p className="text-xs text-muted-foreground">
              Bu derste sistemde kayıtlı kaynak yok — konudan ver; öğrenciye o konudan kaç test kaldığını sorup sayıyı
              sen yaz, kitabın adını not olarak ekleyebilirsin.
            </p>
          )}
          <TopicPicker studentId={studentId} subjectId={subject.id} subjectName={subject.name} maxGrade={maxGrade}
                       studentGrade={studentGrade} examSubject={subject.group === "sinav"}
                       anchorTopic={anchor?.topicId ?? null} anchorGrade={anchor?.topicId != null ? anchor.grade ?? null : undefined}
                       onPick={(t) => onPick(t === "none" ? { kind: "none" } : { kind: "topic", topic: t })} />
        </>
      )}
    </div>
  );
}

export function SourceOption({ active, onClick, icon, title, hint }: {
  active: boolean; onClick: () => void; icon: React.ReactNode; title: string; hint: string;
}) {
  return (
    <button type="button" role="tab" aria-selected={active} onClick={onClick}
            className={cn("flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition",
              active ? "border-cyan-700 bg-cyan-700 text-white shadow-sm"
                : "bg-background text-foreground hover:border-cyan-600 hover:bg-cyan-500/10")}>
      <span className={cn("mt-0.5 shrink-0", active ? "text-white" : "text-cyan-700 dark:text-cyan-300")}>{icon}</span>
      <span className="min-w-0">
        <span className="block break-words text-sm font-semibold">{title}</span>
        <span className={cn("block break-words text-xs", active ? "text-cyan-50" : "text-muted-foreground")}>{hint}</span>
      </span>
    </button>
  );
}

export function BookList({ books, loading, anchorBook, anchorSection, onPick }: {
  books: PoolBookOut[]; loading: boolean; anchorBook: number | null; anchorSection: number | null;
  onPick: (b: PoolBookOut, s: PoolBookSectionOut) => void;
}) {
  const [open, setOpen] = React.useState<number | null>(anchorBook);
  const listRef = React.useRef<HTMLUListElement | null>(null);
  useScrollToAnchor(listRef, anchorSection != null ? `[data-section-id="${anchorSection}"]` : null, !loading);
  if (loading) return <p className="text-xs text-muted-foreground">Kitaplar yükleniyor…</p>;
  const openId = open ?? books[0]?.book_id ?? null;
  return (
    <div className="space-y-2" data-section="pool:add:books">
      {books.map((b) => {
        const isOpen = openId === b.book_id;
        const pct = b.total_tests ? Math.round((100 * b.completed) / b.total_tests) : 0;
        return (
          <div key={b.book_id} className="overflow-hidden rounded-lg border bg-background" data-book={b.book_id}>
            <button type="button" onClick={() => setOpen(isOpen ? -1 : b.book_id)} aria-expanded={isOpen}
                    className="flex w-full items-start gap-3 px-3 py-2.5 text-left hover:bg-cyan-500/10">
              <BookMarked className="mt-0.5 size-4 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block break-words text-sm font-medium text-foreground">{b.name}</span>
                <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                  <span>{b.type_label}</span>
                  <span>· {b.completed}/{b.total_tests} {b.is_deneme ? "deneme" : "test"} çözüldü</span>
                </span>
                <span className="mt-1 block h-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                  <span className="block h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
                </span>
              </span>
              <ChevronDown className={cn("mt-0.5 size-4 shrink-0 text-muted-foreground transition", isOpen && "rotate-180")} aria-hidden />
            </button>
            {isOpen && (
              <ul ref={b.book_id === anchorBook ? listRef : undefined} className="max-h-80 overflow-y-auto border-t p-1">
                {b.sections.length === 0 && <li className="px-2 py-3 text-xs text-muted-foreground">Kitabın bölümü yok — kitap detayından bölüm ekle.</li>}
                {b.sections.map((s) => {
                  const full = s.available <= 0;
                  return (
                    <li key={s.section_id}>
                      <button type="button" onClick={() => onPick(b, s)} data-section-id={s.section_id}
                              className={cn("flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-sm transition hover:bg-cyan-500/10",
                                s.section_id === anchorSection && b.book_id === anchorBook && "bg-cyan-500/10 ring-1 ring-cyan-600/50")}>
                        <span className="min-w-0 flex-1">
                          <span className={cn("block break-words", full ? "text-muted-foreground" : "text-foreground")}>{s.label}</span>
                          {s.topic_name && s.topic_name !== s.label && (
                            <span className="block break-words text-[11px] text-muted-foreground">müfredat: {s.topic_name}</span>
                          )}
                          <SectionTally s={s} unit={b.is_deneme ? "deneme" : "test"} />
                        </span>
                        {s.is_last && <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">SON</span>}
                        <span className={cn("shrink-0 rounded-md px-1.5 py-0.5 text-xs tabular-nums",
                          full ? "text-muted-foreground" : "bg-muted text-foreground")}>
                          {full ? (s.remaining > 0 ? "hepsi havuzda" : "bitti") : `${s.available} kaldı`}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Bölüm sayacı: toplam · çözülen · havuzda (· gün gün programda) + üç parçalı çubuk. */
function SectionTally({ s, unit }: { s: PoolBookSectionOut; unit: string }) {
  const total = s.test_count;
  if (!total) return null;
  const reserved = Math.max(0, total - s.completed - s.remaining);
  const w = (n: number) => `${Math.min(100, (100 * n) / total)}%`;
  return (
    <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground" data-section-tally>
      <span className="flex h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-muted" aria-hidden>
        <span className="bg-emerald-600" style={{ width: w(s.completed) }} />
        <span className="bg-sky-600" style={{ width: w(s.in_pool) }} />
        <span className="bg-amber-500" style={{ width: w(reserved) }} />
      </span>
      <span className="tabular-nums"><span className="font-medium text-foreground">{total}</span> {unit}</span>
      <span className="tabular-nums">· <span className="font-medium text-emerald-700 dark:text-emerald-300">{s.completed}</span> çözüldü</span>
      {s.in_pool > 0 && <span className="tabular-nums">· <span className="font-medium text-sky-700 dark:text-sky-300">{s.in_pool}</span> havuzda</span>}
      {reserved > 0 && <span className="tabular-nums" title="Gün gün programda verilmiş, henüz çözülmemiş">· <span className="font-medium text-amber-700 dark:text-amber-300">{reserved}</span> programda</span>}
    </span>
  );
}

export function TopicPicker({ studentId, subjectId, subjectName, maxGrade = null, studentGrade = null, examSubject = false,
  anchorTopic = null, anchorGrade, onPick, topicsQuery, audience = "coach" }: {
  studentId: number; subjectId: number; subjectName: string; maxGrade?: number | null;
  studentGrade?: number | null; examSubject?: boolean;
  anchorTopic?: number | null; anchorGrade?: number | null;
  onPick: (t: PoolTopicOut | "none") => void;
  /** Öğrenci penceresi kendi ucundan çeker (2026-10-22); yoksa koç ucu. */
  topicsQuery?: { key: readonly unknown[]; fn: () => Promise<PoolTopicsResponse> };
  audience?: "coach" | "student";
}) {
  const listRef = React.useRef<HTMLDivElement | null>(null);
  const q = useQuery({
    queryKey: topicsQuery?.key ?? poolKeys.topics(studentId, subjectId),
    queryFn: topicsQuery?.fn ?? (() => getPoolTopics(studentId, subjectId)),
  });
  const [term, setTerm] = React.useState("");
  const allTopics = q.data?.topics ?? [];
  // TYT (Maarif) kapsamı: yalnız 9-10. sınıf konuları
  const topics = maxGrade == null ? allTopics : allTopics.filter((x) => x.grade_level != null && x.grade_level <= maxGrade);
  const t = trLower(term.trim());
  // Sınıf çipleri: okul dersinde varsayılan öğrencinin kendi sınıfı (en büyük), TYT (Maarif) kapsamında "Tümü".
  // Arama yazılınca çip süzgeci devre dışı (konu hangi sınıfta olursa olsun bulunur).
  const gradeCounts = new Map<number | null, number>();
  for (const x of topics) gradeCounts.set(x.grade_level, (gradeCounts.get(x.grade_level) ?? 0) + 1);
  const grades = [...gradeCounts.keys()].sort((a, b) => (b ?? -1) - (a ?? -1));
  const multiGrade = grades.length > 1;
  // son seçilen konunun sınıfı açık gelir (yoksa o konu süzgeç dışında kalır)
  const [gradeSel, setGradeSel] = React.useState<number | "all" | null>(
    anchorGrade === undefined ? null : anchorGrade ?? "all");
  useScrollToAnchor(listRef, anchorTopic != null ? `[data-topic-id="${anchorTopic}"]` : null, !!q.data);
  // "Kendi sınıfı" = öğrencinin GERÇEK sınıfı (listedeki en büyük sınıf değil). Sınav dersinde (TYT/AYT)
  // sınıf ayrımı yapılmaz: 12. sınıf öğrencide TYT konuları 9-10. sınıfa ait olsa da "kendi sınıfı" sayılmaz.
  const ownGrade = !examSubject && maxGrade == null && studentGrade != null && gradeCounts.has(studentGrade) ? studentGrade : null;
  const activeGrade: number | "all" = gradeSel ?? (multiGrade && ownGrade != null ? ownGrade : "all");
  const shown = (t ? topics.filter((x) => trLower(x.name).includes(t) || trLower(x.unit_name ?? "").includes(t)) : topics)
    .filter((x) => t || activeGrade === "all" || x.grade_level === activeGrade);
  // Sınıf → ünite/tema gruplaması (Maarif'te ünite adları sınıflar arasında tekrar eder)
  const gradeMap = new Map<number | null, Map<string, PoolTopicOut[]>>();
  for (const x of shown) {
    const units = gradeMap.get(x.grade_level) ?? new Map<string, PoolTopicOut[]>();
    const u = x.unit_name ?? "";
    units.set(u, [...(units.get(u) ?? []), x]);
    gradeMap.set(x.grade_level, units);
  }
  const byGrade = [...gradeMap.entries()].sort((a, b) => (b[0] ?? -1) - (a[0] ?? -1));
  return (
    <div className="space-y-2" data-section="pool:add:topics">
      <p className="text-xs text-muted-foreground">
        {subjectName}{maxGrade ? ` (TYT · ${maxGrade - 1}-${maxGrade}. sınıf Maarif konuları)` : ""} — konu seç.{" "}
        {audience === "student"
          ? <>Konu müfredatına bağlanır; koçun onaylayınca ilerlemene işlenir. <span className="font-semibold">SON</span> = en son çalıştığın konu.</>
          : <><span className="font-semibold">SON</span> = en son görev verilen, <span className="font-semibold">ŞUBE</span> = dershanede işlenen.</>}
      </p>
      {multiGrade && (
        <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Sınıf">
          {grades.map((g) => (
            <GradeChip key={g ?? "none"} active={!t && activeGrade === g} grade={g} count={gradeCounts.get(g) ?? 0}
                       own={g != null && g === ownGrade} onClick={() => setGradeSel(g ?? "all")} />
          ))}
          <GradeChip active={!t && activeGrade === "all"} grade="all" count={topics.length} own={false}
                     onClick={() => setGradeSel("all")} />
        </div>
      )}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Konu ara (tüm sınıflarda)…" className="h-9 pl-8" aria-label="Konu ara" />
        </div>
        <Button type="button" variant="outline" size="sm" className="h-9" onClick={() => onPick("none")} title="Konuya bağlı olmayan kalem: video, sayfa, serbest ödev (test/soru kalemi konu ister)">
          <PenLine className="size-4" aria-hidden /> Konusuz
        </Button>
      </div>
      <div ref={listRef} className="max-h-96 space-y-3 overflow-y-auto rounded-lg border bg-background p-1.5">
        {q.isLoading && <p className="px-2 py-3 text-xs text-muted-foreground">Konular yükleniyor…</p>}
        {byGrade.map(([g, units]) => {
          const tone = gradeTone(g);
          const n = [...units.values()].reduce((a, l) => a + l.length, 0);
          return (
            <section key={g ?? "none"} data-topic-grade={g ?? ""} className={cn("rounded-lg border-l-4 bg-card", tone.border)}>
              {(multiGrade || byGrade.length > 1) && (
                <div className={cn("sticky top-0 z-10 flex items-center gap-2 rounded-tr-lg px-3 py-1.5 text-xs font-semibold text-white shadow-sm", tone.band)}>
                  <span>{g ? `${g}. sınıf` : "Sınıfsız konular"}</span>
                  {g != null && g === ownGrade && <span className="rounded bg-white/25 px-1.5 text-[10px]">kendi sınıfı</span>}
                  <span className="ml-auto font-normal opacity-90">{n} konu</span>
                </div>
              )}
              <div className="divide-y divide-border/60">
                {[...units.entries()].map(([u, list]) => (
                  <div key={u || "-"} className="py-1">
                    {u && <div className="px-3 pb-0.5 pt-1 text-[11px] font-semibold text-muted-foreground">{u}</div>}
                    {list.map((x) => <TopicRow key={x.topic_id} t={x} showUnit={false} marked={x.topic_id === anchorTopic} onPick={() => onPick(x)} />)}
                  </div>
                ))}
              </div>
            </section>
          );
        })}
        {q.data && shown.length === 0 && (
          <p className="px-2 py-3 text-xs text-muted-foreground">
            {topics.length === 0 ? "Bu derste konu listesi yok — “Konusuz” ile ya da Hızlı yaz ile ekle." : "Aramayla eşleşen konu yok."}
          </p>
        )}
      </div>
    </div>
  );
}

// Sınıf tonu — dolgulu bant beyaz yazıyla (≥4,5 kontrast, 700 tonları)
const GRADE_TONES: Record<number, { band: string; border: string; dot: string }> = {
  9: { band: "bg-orange-700", border: "border-l-orange-700", dot: "bg-orange-700" },
  10: { band: "bg-violet-700", border: "border-l-violet-700", dot: "bg-violet-700" },
  11: { band: "bg-cyan-700", border: "border-l-cyan-700", dot: "bg-cyan-700" },
  12: { band: "bg-emerald-700", border: "border-l-emerald-700", dot: "bg-emerald-700" },
};
function gradeTone(g: number | null) {
  return (g != null && GRADE_TONES[g]) || { band: "bg-slate-700", border: "border-l-slate-700", dot: "bg-slate-700" };
}

function GradeChip({ active, grade, count, own, onClick }: {
  active: boolean; grade: number | null | "all"; count: number; own: boolean; onClick: () => void;
}) {
  const label = grade === "all" ? "Tümü" : grade == null ? "Sınıfsız" : `${grade}. sınıf`;
  const tone = grade === "all" ? null : gradeTone(grade);
  return (
    <button type="button" role="radio" aria-checked={active} onClick={onClick}
            className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition",
              active ? cn("border-transparent text-white", tone?.band ?? "bg-slate-700")
                : "bg-background text-foreground hover:bg-muted")}>
      {tone && !active && <span className={cn("size-2 rounded-full", tone.dot)} aria-hidden />}
      {label}{own && " · kendi sınıfı"}
      <span className={cn("rounded-full px-1.5 text-[10px] font-semibold", active ? "bg-white/25" : "bg-muted")}>{count}</span>
    </button>
  );
}

function TopicRow({ t, showUnit = true, marked = false, onPick }: { t: PoolTopicOut; showUnit?: boolean; marked?: boolean; onPick: () => void }) {
  const done = t.status === "kapali";
  return (
    <button type="button" onClick={onPick} data-topic-id={t.topic_id}
            className={cn("flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm transition hover:bg-cyan-500/10",
              marked && "bg-cyan-500/10 ring-1 ring-cyan-600/50")}>
      <span className="min-w-0 flex-1 break-words">
        <span className={cn("text-foreground", done && "text-muted-foreground")}>{t.name}</span>
        {showUnit && t.unit_name && <span className="ml-1 text-xs text-muted-foreground">· {t.unit_name}</span>}
      </span>
      {t.is_class_position && <span className="rounded bg-violet-600 px-1.5 py-0.5 text-[10px] font-semibold text-white" title="Şube bu konuda">ŞUBE</span>}
      {t.is_last && <span className="rounded bg-cyan-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">SON</span>}
      {done && <span className="rounded bg-emerald-700 px-1.5 py-0.5 text-[10px] font-semibold text-white">bitirdi</span>}
      {t.status === "planlandi" && (
        <span className="rounded bg-sky-700 px-1.5 py-0.5 text-[10px] font-semibold text-white" title="Bu dönemin havuzunda bekleyen kalemi var">havuzda</span>
      )}
      {t.sources.length > 0 && (
        <span className="shrink-0 rounded-md bg-muted px-1.5 py-0.5 text-[11px] text-foreground" title="Bu konu öğrencinin kitabında da var">
          kitapta var
        </span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------- 3 miktar

function Composer({ studentId, data, subjectId, subjectName, choice, onSwitch, onDone }: {
  studentId: number; data: PoolBundleResponse; subjectId: number; subjectName: string; choice: Choice;
  onSwitch: (bookId: number, sectionId: number) => void; onDone: () => void;
}) {
  const add = useAddPoolItem(studentId);
  const setPos = useSetClassPosition(studentId);
  const book = choice.kind === "book" ? choice : null;
  const topic = choice.kind === "topic" ? choice.topic : null;
  const fixedUnit: PoolUnit | null = book ? (book.book.is_deneme ? "deneme" : "test") : null;
  // Konusuz kalem test/soru olamaz (konu zorunlu, 2026-10-14) → varsayılan birim sayfa
  const [unit, setUnit] = React.useState<PoolUnit>(fixedUnit ?? (choice.kind === "none" ? "sayfa" : "test"));
  const defaultQty = book ? Math.max(1, Math.min(book.book.is_deneme ? 1 : 3, book.section.available || (book.book.is_deneme ? 1 : 3))) : 3;
  const [qty, setQty] = React.useState<number | null>(defaultQty);
  const [custom, setCustom] = React.useState("");
  const [moreOpen, setMoreOpen] = React.useState(false);
  const [dayHint, setDayHint] = React.useState("");
  const [homework, setHomework] = React.useState(false);
  const [label, setLabel] = React.useState("");
  // Sayfa aralığı (2026-10-22): konulu kaynaksız kalemde "s. 51–55" — miktar aralıktan.
  const [pageFrom, setPageFrom] = React.useState("");
  const [pageTo, setPageTo] = React.useState("");
  const pageMode = choice.kind === "topic" && unit === "sayfa";
  const pf = Number(pageFrom);
  const pt = Number(pageTo);
  const rangeTyped = pageFrom !== "" || pageTo !== "";
  const rangeValid = pageFrom !== "" && pageTo !== "" && pf >= 1 && pt >= pf;
  const noteKey = useDebouncedValue(label.trim(), 400);
  const pageSug = useQuery<PageSuggestionResponse>({
    queryKey: teacherKeys.pageSuggestion(studentId, topic?.topic_id ?? null, noteKey),
    queryFn: () => getPageSuggestion(studentId, topic?.topic_id ?? null, noteKey),
    enabled: choice.kind === "topic",
    staleTime: 30_000,
  });

  const isActivity = unit === "etkinlik";
  const needsLabel = choice.kind === "none" && !isActivity;
  const effQty = pageMode && rangeTyped ? (rangeValid ? pt - pf + 1 : null) : qty;
  const qtyOk = isActivity || (effQty ?? 0) > 0;
  const labelOk = !needsLabel || !!label.trim();
  // KONU ZORUNLULUĞU: test/soru kalemi kitapsızsa bir konuya bağlı olmalı (konu performansı + harita)
  const topicNeeded = choice.kind === "none" && (unit === "test" || unit === "soru");
  const extras = (dayHint ? 1 : 0) + (homework ? 1 : 0);
  const unitLabel = UNIT_LABELS[unit];
  const cta = isActivity
    ? "Havuza ekle · 1 etkinlik"
    : pageMode && rangeValid
      ? `Havuza ekle · s. ${pf}–${pt}`
      : `Havuza ekle${effQty ? ` · ${effQty} ${unitLabel}` : ""}`;
  const over = book && qty != null && qty > book.section.available;
  const bookSuggestion = topic?.sources.find((s) => s.recommended) ?? topic?.sources[0] ?? null;

  function submit() {
    if (!qtyOk || !labelOk || topicNeeded) return;
    const body: PoolItemBody = book
      ? {
          subject_id: subjectId, book_id: book.book.book_id, section_id: book.section.section_id, topic_id: null,
          label: null, quantity: qty, unit, day_hint: dayHint || null, teacher_homework: homework,
        }
      : {
          subject_id: subjectId, topic_id: topic?.topic_id ?? null, book_id: null, section_id: null,
          label: label.trim() || null, quantity: isActivity ? 1 : effQty, unit, day_hint: dayHint || null,
          teacher_homework: homework,
          page_from: pageMode && rangeValid ? pf : null,
          page_to: pageMode && rangeValid ? pt : null,
        };
    add.mutate(body, { onSuccess: onDone });
  }

  return (
    <div className="space-y-4">
      {/* seçim özeti */}
      {book ? (
        <div className="rounded-lg bg-muted/60 px-3 py-2 text-sm" data-section="pool:add:book-summary">
          <div className="flex flex-wrap items-center gap-2">
            <BookMarked className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
            <span className="font-medium text-foreground">{book.book.name}</span>
            <span className="text-muted-foreground" aria-hidden>›</span>
            <span className="font-medium text-foreground">{book.section.label}</span>
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            Bölümde {book.section.test_count} {fixedUnit === "deneme" ? "deneme" : "test"} · {book.section.completed} çözüldü
            {book.section.in_pool > 0 ? ` · ${book.section.in_pool} havuzda bekliyor` : ""} · <span className="font-semibold text-foreground">{book.section.available} verilebilir</span>.
            Öğrenci işaretledikçe kitaptaki ilerleme bu bölümde görünür.
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-sm">
          <span className="text-muted-foreground">{subjectName}</span>
          <span className="text-muted-foreground" aria-hidden>›</span>
          <span className="font-medium text-foreground">{topic ? topic.name : "Konusuz kalem"}</span>
          {topic && !topic.is_class_position && data.class_group && (
            <button type="button" onClick={() => setPos.mutate({ subject_id: subjectId, topic_id: topic.topic_id })}
                    className="ml-auto text-xs text-violet-700 underline-offset-2 hover:underline dark:text-violet-300"
                    title="Şube şu an bu konuda (öğrenciden gelen cevapla)">
              Şube bu konuda
            </button>
          )}
        </div>
      )}

      {/* müfredat konusu öğrencinin kitabında da varsa: kitaptan ver önerisi (kitap takibi kaçmasın) */}
      {bookSuggestion && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-900 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100" data-section="pool:add:book-hint">
          <BookOpen className="size-4 shrink-0" aria-hidden />
          <span className="min-w-0 flex-1">
            Bu konu öğrencinin kitabında var: <strong>{bookSuggestion.book_name}</strong> · {bookSuggestion.section_label} ({bookSuggestion.remaining} kaldı).
            Kitaptan verirsen kitaptaki ilerleme takip edilir.
          </span>
          <Button type="button" size="sm" className="h-7 bg-sky-700 text-white hover:bg-sky-800 hover:text-white"
                  onClick={() => onSwitch(bookSuggestion.book_id, bookSuggestion.section_id)}>
            Kitaptan ver
          </Button>
        </div>
      )}

      {choice.kind !== "book" && (
        <Field label={choice.kind === "topic" ? "Kitap adı" : isActivity ? "Ne yapılacak? (isteğe bağlı)" : "Ne çalışılacak?"}
               hint={choice.kind === "topic" ? "not, isteğe bağlı — sistemde kayıtlı değilse" : undefined}>
          <Input value={label} onChange={(e) => setLabel(e.target.value)}
                 list={choice.kind === "topic" ? "pool-note-suggestions" : undefined}
                 placeholder={choice.kind === "topic" ? "örn. Palme · Yayın Denizi" : "örn. Palme sayfa 45'e kadar · Optik videosu"} />
          {choice.kind === "topic" && (
            <datalist id="pool-note-suggestions">
              {(pageSug.data?.notes ?? []).map((n) => <option key={n} value={n} />)}
            </datalist>
          )}
          {choice.kind === "topic" && (
            <p className="text-[11px] text-muted-foreground">Öğrenciye bu konudan kaç test kaldığını sor, sayıyı aşağıda sen belirle.</p>
          )}
        </Field>
      )}

      {/* birim */}
      {fixedUnit ? (
        <div className="text-xs text-muted-foreground">Birim: <span className="font-semibold text-foreground">{UNIT_LABELS[fixedUnit]}</span> (kitaptan)</div>
      ) : (
        <Field label="Birim">
          <div className="flex flex-wrap gap-1 rounded-lg bg-muted p-0.5" role="radiogroup" aria-label="Birim">
            {data.units.map((u) => {
              const locked = choice.kind === "none" && (u === "test" || u === "soru");
              return (
                <button key={u} type="button" role="radio" aria-checked={unit === u} onClick={() => setUnit(u)}
                        disabled={locked}
                        title={locked ? "Test ve soru kalemi bir konuya bağlanmalı — geri dönüp konu seç" : undefined}
                        className={cn("rounded-md px-3 py-1 text-sm transition disabled:cursor-not-allowed disabled:opacity-40",
                          unit === u ? "bg-background font-semibold text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                  {UNIT_LABELS[u]}
                </button>
              );
            })}
          </div>
        </Field>
      )}

      {pageMode && (
        <Field label="Sayfa aralığı" hint="isteğe bağlı — girersen miktar aralıktan hesaplanır">
          <div className="flex flex-wrap items-center gap-2" data-section="pool:add:page-range">
            <Input value={pageFrom} inputMode="numeric" aria-label="Başlangıç sayfası" placeholder="başlangıç"
                   className="h-9 w-24 text-center tabular-nums" onChange={(e) => setPageFrom(e.target.value)} />
            <span className="text-muted-foreground" aria-hidden>–</span>
            <Input value={pageTo} inputMode="numeric" aria-label="Bitiş sayfası" placeholder="bitiş"
                   className="h-9 w-24 text-center tabular-nums" onChange={(e) => setPageTo(e.target.value)} />
            {rangeValid && <span className="text-sm tabular-nums text-foreground">{pt - pf + 1} sayfa</span>}
          </div>
          {rangeTyped && !rangeValid && (
            <p className="text-xs text-rose-700 dark:text-rose-300">Başlangıç ≤ bitiş olacak şekilde iki sayfayı da gir.</p>
          )}
          {pageSug.data?.last ? (
            <div className="flex flex-wrap items-center gap-2 text-xs" data-section="pool:add:page-suggestion">
              <span className="text-foreground">
                Son verilen{pageSug.data.last.note ? ` (${pageSug.data.last.note})` : ""}:{" "}
                <b className="tabular-nums">s. {pageSug.data.last.page_from}–{pageSug.data.last.page_to}</b>
              </span>
              {pageSug.data.next_from !== null && pageFrom !== String(pageSug.data.next_from) && (
                <button type="button" onClick={() => setPageFrom(String(pageSug.data!.next_from))}
                        className="rounded-md bg-cyan-700 px-2 py-1 text-[11px] font-semibold text-white hover:bg-cyan-800">
                  {pageSug.data.next_from}. sayfadan devam et
                </button>
              )}
            </div>
          ) : null}
        </Field>
      )}

      {!isActivity && !(pageMode && rangeTyped) && (
        <Field label="Miktar">
          <div className="flex flex-wrap items-center gap-1.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <button key={n} type="button" onClick={() => { setQty(n); setCustom(""); }}
                      className={cn("size-9 rounded-lg border text-sm font-medium transition",
                        qty === n && !custom ? "border-cyan-700 bg-cyan-700 text-white" : "bg-background text-foreground hover:border-cyan-600")}>
                {n}
              </button>
            ))}
            <Input value={custom} inputMode="numeric" placeholder="başka" aria-label="Başka miktar" className="h-9 w-20 text-center"
                   onChange={(e) => { setCustom(e.target.value); const n = Number(e.target.value); setQty(Number.isInteger(n) && n > 0 ? n : null); }} />
            {book && book.section.available > 0 && (
              <button type="button" onClick={() => { setQty(book.section.available); setCustom(String(book.section.available)); }}
                      className="rounded-lg border border-dashed px-2.5 py-1.5 text-xs font-medium text-cyan-700 hover:bg-cyan-500/10 dark:text-cyan-300">
                kalanı ver ({book.section.available})
              </button>
            )}
          </div>
          {over && (
            <p className="text-xs text-amber-800 dark:text-amber-200">
              Bölümde {book!.section.available} verilebilir kaldı; fazlası kitap sayacını aşar (yine de eklenebilir).
            </p>
          )}
        </Field>
      )}

      {/* ek seçenekler */}
      <div className="rounded-lg border">
        <button type="button" onClick={() => setMoreOpen((v) => !v)} aria-expanded={moreOpen}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground hover:text-foreground">
          <ChevronDown className={cn("size-4 transition", moreOpen && "rotate-180")} aria-hidden />
          Ek seçenekler
          {extras > 0 && <span className="rounded-full bg-cyan-700 px-1.5 text-[10px] font-semibold text-white">{extras}</span>}
          <span className="ml-auto hidden font-normal sm:inline">gün etiketi · ders öğretmeni ödevi</span>
        </button>
        {moreOpen && (
          <div className="flex flex-wrap items-center gap-4 border-t px-3 py-2.5 text-sm">
            <label className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Gün etiketi</span>
              <Input type="date" value={dayHint} onChange={(e) => setDayHint(e.target.value)} className="h-8 w-40" />
            </label>
            <label className="flex items-center gap-2 text-foreground">
              <input type="checkbox" checked={homework} onChange={(e) => setHomework(e.target.checked)} className="size-4 accent-violet-600" />
              ders öğretmeninin ödevi
            </label>
          </div>
        )}
      </div>

      <div className="space-y-1">
        <Button type="button" onClick={submit} disabled={!qtyOk || !labelOk || topicNeeded || add.isPending}
                className="h-10 w-full bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white" data-testid="pool-add-submit">
          <Plus className="size-4" aria-hidden /> {cta}
        </Button>
        {topicNeeded && (
          <p className="text-center text-xs text-amber-800 dark:text-amber-200">
            Test ve soru kalemi bir konuya bağlanmalı — yoksa çözülen testler konu performansına ve müfredat haritasına
            işlenmez. Geri dönüp konu seç; video, sayfa ya da serbest ödev için Sayfa / Etkinlik birimi kullan.
          </p>
        )}
        {!labelOk && <p className="text-center text-xs text-muted-foreground">Konusuz kalemde ne çalışılacağını yaz.</p>}
        {!qtyOk && <p className="text-center text-xs text-muted-foreground">Miktar seç.</p>}
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-semibold text-foreground">
        {label} {hint && <span className="font-normal text-muted-foreground">· {hint}</span>}
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------- hızlı yaz

function FreeText({ studentId, data, subjectId }: { studentId: number; data: PoolBundleResponse; subjectId: number | null }) {
  const add = useAddPoolItem(studentId);
  const [text, setText] = React.useState("");
  const [res, setRes] = React.useState<ParseResponse | null>(null);
  const [busy, setBusy] = React.useState(false);
  const subj = data.subjects.find((s) => s.id === subjectId) ?? null;

  async function parse(subjectOverride?: number) {
    if (!text.trim()) return;
    setBusy(true);
    try {
      setRes(await parsePoolText(studentId, { text, subject_id: subjectOverride ?? subjectId }));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3 px-4 py-4">
      <div className="flex items-start gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        <Sparkles className="mt-0.5 size-4 shrink-0 text-cyan-700 dark:text-cyan-300" aria-hidden />
        <span>
          Doğal yaz, ayraç gerekmez: <span className="font-medium text-foreground">kitap · ders · konu · sayı birim</span> —
          örn. “345 matematik üslü sayılar 4 test”, “tyt fizik basınç 3 test”, “paragraf 10 soru”.
          Sonuç önce sana gösterilir, onaylamadan yazılmaz; birden çok konuya uyarsa seçersin.
          {subj && <> Konu adı <span className="font-medium text-foreground">{subj.name}</span> içinde aranır.</>}
        </span>
      </div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void parse(); }}>
        <Input value={text} onChange={(e) => { setText(e.target.value); setRes(null); }} placeholder="345 matematik üslü sayılar 4 test" className="h-10" />
        <Button type="submit" variant="outline" className="h-10" disabled={busy || !text.trim()}>Ayrıştır</Button>
      </form>
      {res && (
        <div className="space-y-2 rounded-lg border p-3">
          <div className="text-xs font-semibold text-foreground">Okunan</div>
          <div className="flex flex-wrap gap-1.5">
            {res.chips.map((c, i) => (
              <span key={i} title={c.kind}
                    className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", c.confident ? "bg-cyan-700 text-white" : "bg-amber-400 text-amber-950")}>
                {c.kind === "unit" ? UNIT_LABELS[c.label as PoolUnit] ?? c.label : c.label}
              </span>
            ))}
          </div>
          {res.warning && <p className="text-xs text-amber-800 dark:text-amber-200">{res.warning}</p>}
          {res.options && res.options.length > 0 && (
            <ParseOptions options={res.options} base={res.base ?? null} pending={add.isPending}
                          onPick={(o) => {
                            const b = res.base;
                            if (!b || (b.unit !== "etkinlik" && !b.quantity)) return;
                            // Konu zorunluluğu: yalnız ders seçildiyse (konu yok) test/soru kalemi eklenmez —
                            // o dersin konularında yeniden ayrıştır.
                            if (!o.topic_id && !o.book_id && (b.unit === "test" || b.unit === "soru")) {
                              void parse(o.subject_id);
                              return;
                            }
                            add.mutate({
                              subject_id: o.subject_id, topic_id: o.topic_id, book_id: o.book_id, section_id: o.section_id,
                              label: o.label, quantity: b.quantity, unit: b.unit,
                            }, { onSuccess: () => { setText(""); setRes(null); } });
                          }} />
          )}
          {res.draft && (
            <Button type="button" size="sm" disabled={add.isPending}
                    className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white"
                    onClick={() => add.mutate(res.draft!, { onSuccess: () => { setText(""); setRes(null); } })}>
              <Plus className="size-4" aria-hidden /> Böyle ekle
            </Button>
          )}
        </div>
      )}
    </div>
  );
}


function useDebouncedValue<T>(value: T, ms: number): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}
