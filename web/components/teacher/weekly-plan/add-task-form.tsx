"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  extractCount,
  itemUnit,
  getSubjectTopics,
  taskTopicKeys,
  type SubjectTopicsResponse,
} from "@/lib/api/task-topic-link";
import { TopicLinkPanel, useTopicLink } from "./topic-link-panel";
import { TopicPickerPanel } from "./topic-picker-panel";
import {
  AlertTriangle,
  ChevronDown,
  BookOpen,
  Boxes,
  Brain,
  ClipboardCheck,
  FileText,
  Flame,
  Info,
  ListChecks,
  Loader2,
  Moon,
  Plus,
  Repeat,
  Sun,
  Sunrise,
  TriangleAlert,
  Video,
} from "lucide-react";

import type { ItemUnit, PageSuggestionResponse, TaskPeriod } from "@/lib/types/teacher";

import {
  getStudentAllSubjects,
  getStudentBookSections,
  getStudentBooksBySubject,
  getStudentReviewChips,
  getStudentSectionStats,
  getStudentSidebar,
  getTeacherWorkBlocks,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useCreateTask,
  useCreateWorkBlock,
} from "@/lib/hooks/use-teacher-mutations";
import { TaskQuickAdd } from "./task-quick-add";
import {
  LinkedTopicChip,
  PageSuggestionLine,
  usePageSuggestion,
  type TaskSeed,
} from "./task-seed";
import { DenemeForm } from "./deneme-form";
import type {
  BookOptionsResponse,
  ReviewStruggleResponse,
  SectionOptionsResponse,
  SectionStatsResponse,
  SidebarResponse,
  SubjectListResponse,
  WorkBlock,
  WorkBlockListResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

// "deneme" yalnız UI sekmesi; backend'e type="other" + kitapsız kalem gönderir
// (tasktype enum'una değer eklemeden — ikinci migration gerekmez).
type TaskType =
  | "test"
  | "deneme"
  | "blok"
  | "video"
  | "ozet"
  | "tekrar"
  | "other";

/** Konuyla açılabilen etkinlik tipleri (görev konuya bağlanır, test sayılmaz). */
const ACTIVITY_TYPES = new Set<TaskType>(["video", "ozet", "tekrar", "other"]);

const TYPE_TILES: Array<{
  key: TaskType;
  label: string;
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}> = [
  { key: "test", label: "Test", Icon: FileText },
  { key: "deneme", label: "Deneme", Icon: ClipboardCheck },
  { key: "blok", label: "Blok", Icon: Boxes },
  { key: "video", label: "Video", Icon: Video },
  { key: "ozet", label: "Özet", Icon: BookOpen },
  { key: "tekrar", label: "Tekrar", Icon: Repeat },
  { key: "other", label: "Diğer", Icon: ListChecks },
];

interface Props {
  studentId: number;
  dayDate: string;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
  /** Periyot bölgesinden açıldıysa ön-seçili periyot */
  initialPeriod?: TaskPeriod | null;
}

export function AddTaskForm({
  studentId,
  dayDate,
  onFocusSubject,
  onAfterAdd,
  initialPeriod = null,
}: Props) {
  const [type, setType] = React.useState<TaskType>("test");
  // M6 — opsiyonel periyot. Null = atanmamış (default). Periyot bölgesinin
  // altındaki "+ Sabaha ekle" ile açıldıysa o periyot seçili gelir (2026-09-07)
  // — koç periyot çipini ayrıca seçmez.
  const [period, setPeriod] = React.useState<TaskPeriod | null>(initialPeriod);
  // P4 (2026-09-07): varsayılan HIZLI KUTU. Eski ayrıntılı form kaldırılmadı —
  // "Ayrıntılı form" ile açılır (geri dönüş yolu korunur, koç zorlanmaz).
  // Canlı veride görevlerin %78'i TEST; kutu tam onu 3 tıka indiriyor.
  const [detailed, setDetailed] = React.useState(false);
  // Hızlı kutudaki seçim (2026-10-22): ayrıntılı forma / tip formlarına geçerken
  // kaybolmasın — koç "DNA ve Genetik Kod"u seçip Özet'e basınca form dolu açılır.
  const [seed, setSeed] = React.useState<TaskSeed | null>(null);
  // Ayrıntılı form her açılışta seçimi YENİDEN okusun (key ile yeniden kurulur).
  const [formKey, setFormKey] = React.useState(0);
  function openDetailed(t: TaskType) {
    setType(t);
    setFormKey((k) => k + 1);
    setDetailed(true);
  }

  // TEST için: sidebar — yalnız kitap atanmış dersler (cascade ders→kitap→ünite)
  const allSidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, null),
    queryFn: () => getStudentSidebar(studentId, null),
    staleTime: 60_000,
  });
  const bookedSubjects = (allSidebarQ.data?.subjects ?? []).map((s) => ({
    id: s.id,
    name: s.name,
  }));

  // VIDEO / ÖZET / TEKRAR / DİĞER için: müfredat-tam ders havuzu (kitap zorunlu YOK).
  // Koç bir derste kitap atamamış olsa bile video/özet/tekrar/diğer atayabilmeli.
  const allSubjectsQ = useQuery<SubjectListResponse>({
    queryKey: teacherKeys.studentAllSubjects(studentId),
    queryFn: () => getStudentAllSubjects(studentId),
    staleTime: 5 * 60_000,
  });
  const allSubjects = (allSubjectsQ.data?.items ?? []).map((s) => ({
    id: s.id,
    name: s.name,
  }));

  // TEST: kitabı olan dersler önde + müfredatın diğer dersleri (kaynaksız test, 2026-10-16).
  // Eskiden yalnız kitabı olan dersler listeleniyordu → kitabı yüklenmemiş öğrencide
  // ders listesi BOŞTU, test verilemiyordu.
  const bookedIds = new Set(bookedSubjects.map((s) => s.id));
  const testSubjects = [
    ...bookedSubjects,
    ...allSubjects.filter((s) => !bookedIds.has(s.id)),
  ];

  if (!detailed) {
    return (
      <div className="@container px-4 py-4 border-t border-border bg-card space-y-2.5">
        <TaskQuickAdd
          studentId={studentId}
          dayDate={dayDate}
          period={period}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
          initialSeed={seed}
          onSeedChange={setSeed}
          onPeriodChange={setPeriod}
          secondary={
            seed ? (
              // Konu seçiliyken ikincil eylemler kartın altbilgisinde (birincil Ekle sağda)
              <div
                className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[12px]"
                data-section="quick-add:types"
              >
                <span className="text-muted-foreground">Bu konuyla:</span>
                {TYPE_TILES.filter((t) => ACTIVITY_TYPES.has(t.key)).map(({ key, label, Icon }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => openDetailed(key)}
                    title={`${seed.topic.topic_name} için ${label.toLocaleLowerCase("tr")} görevi`}
                    className="inline-flex items-center gap-1 font-medium text-foreground underline-offset-2 hover:underline"
                  >
                    <Icon className="size-3.5 text-muted-foreground" aria-hidden />
                    {label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => openDetailed("test")}
                  title="Kitap/ünite elle seçmek için — seçimin forma taşınır"
                  className="text-muted-foreground underline underline-offset-2 hover:text-foreground"
                >
                  Ayrıntılı forma aktar
                </button>
              </div>
            ) : null
          }
        />
        {!seed ? (
          <div className="flex flex-wrap items-center gap-1.5" data-section="quick-add:types">
            {/* Nadir tipler ana ekranı doldurmasın: canlı veride Video %3,3,
                Özet/Tekrar %0,3. Konu seçilince kartın altbilgisine taşınırlar. */}
            {TYPE_TILES.filter((t) => t.key !== "test").map(({ key, label, Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => openDetailed(key)}
                className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[11.5px] text-foreground hover:bg-muted/60"
              >
                <Icon className="size-3" aria-hidden />
                {label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => openDetailed("test")}
              title="Kitap ve üniteyi elle seçmek için"
              className="ml-auto text-[11.5px] font-medium text-muted-foreground underline underline-offset-2 hover:text-foreground"
            >
              Ayrıntılı form
            </button>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="@container px-4 py-4 border-t border-border bg-card">
      <div className="mb-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">
            Görev tipi
          </p>
          <button
            type="button"
            onClick={() => setDetailed(false)}
            className="text-[11.5px] text-muted-foreground underline underline-offset-2 hover:text-foreground"
          >
            {seed ? "← Hızlı eklemeye dön (seçim korunur)" : "Hızlı ekleme"}
          </button>
        </div>
        <div className="grid grid-cols-4 sm:grid-cols-7 gap-1.5">
          {TYPE_TILES.map(({ key, label, Icon }) => {
            const active = type === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => setType(key)}
                className={cn(
                  "px-2 py-2.5 rounded-md text-[12px] font-medium border transition-all flex flex-col items-center gap-1",
                  active
                    ? "border-foreground bg-foreground text-background"
                    : "border-border bg-card text-foreground hover:border-foreground/30 hover:bg-muted/50",
                )}
              >
                <Icon className="size-4" aria-hidden />
                <span>{label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* M6 — opsiyonel periyot chip-bar (sabah/öğle/akşam). Boş = atanmamış. */}
      <PeriodChips value={period} onChange={setPeriod} />

      {type === "test" ? (
        <TestForm
          key={formKey}
          seed={seed}
          studentId={studentId}
          dayDate={dayDate}
          subjects={testSubjects}
          bookedSubjectIds={bookedIds}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
        />
      ) : null}
      {type === "deneme" ? (
        <DenemeForm
          studentId={studentId}
          dayDate={dayDate}
          period={period}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "blok" ? (
        <BlockForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "video" ? (
        <VideoForm
          key={formKey}
          seed={seed}
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
        />
      ) : null}
      {type === "ozet" ? (
        <OzetForm
          key={formKey}
          seed={seed}
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
        />
      ) : null}
      {type === "tekrar" ? (
        <TekrarForm
          key={formKey}
          seed={seed}
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
        />
      ) : null}
      {type === "other" ? (
        <OtherForm
          key={formKey}
          seed={seed}
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={() => {
            setSeed(null);
            onAfterAdd();
          }}
        />
      ) : null}
    </div>
  );
}

/**
 * Periyot chip-bar (M6) — Yok/Sabah/Öğle/Akşam.
 * Tek tıkla seçim; mobil-dostu (büyük dokunma alanı). Opsiyonel:
 * "Yok" → null gönderilir; backend görev period=NULL kaydeder.
 */
function PeriodChips({
  value,
  onChange,
}: {
  value: TaskPeriod | null;
  onChange: (v: TaskPeriod | null) => void;
}) {
  const opts: Array<{ key: TaskPeriod | null; label: string; Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }> | null }> = [
    { key: null, label: "—", Icon: null },
    { key: "morning", label: "Sabah", Icon: Sunrise },
    { key: "noon", label: "Öğle", Icon: Sun },
    { key: "evening", label: "Akşam", Icon: Moon },
  ];
  return (
    <div className="mb-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1.5">
        Periyot{" "}
        <span className="text-[10px] normal-case text-muted-foreground/70">
          (opsiyonel — günün hangi diliminde)
        </span>
      </p>
      <div className="flex flex-wrap gap-1.5">
        {opts.map(({ key, label, Icon }) => {
          const active = value === key;
          return (
            <button
              key={key ?? "none"}
              type="button"
              onClick={() => onChange(key)}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium border transition-all inline-flex items-center gap-1.5",
                active
                  ? "border-foreground bg-foreground text-background"
                  : "border-border bg-card text-foreground hover:border-foreground/30 hover:bg-muted/50",
              )}
            >
              {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// TEST TİPİ
// =============================================================================

function TestForm({
  studentId,
  dayDate,
  subjects,
  bookedSubjectIds,
  period,
  onFocusSubject,
  onAfterAdd,
  seed = null,
}: {
  seed?: TaskSeed | null;
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  /** Öğrencinin kitabı olan dersler — listede önde; diğerlerinde kaynaksız verilir */
  bookedSubjectIds: Set<number>;
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  // Hızlı kutudan taşınan seçim (2026-10-22) — form kaldığı yerden açılır.
  const [subjectId, setSubjectId] = React.useState<number | "">(seed?.topic.subject_id ?? "");
  // "none" = kaynaksız (müfredat konusuna bağlı) test — 2026-10-16: kitabı
  // yüklenmemiş öğrenciye de test verilebilsin.
  const [bookId, setBookId] = React.useState<number | "" | "none">(
    seed ? (seed.source ? seed.source.book_id : "none") : "",
  );
  const [sectionId, setSectionId] = React.useState<number | "">(seed?.source?.section_id ?? "");
  const [topicId, setTopicId] = React.useState<number | "">(seed?.topic.topic_id ?? "");
  const [topicOpen, setTopicOpen] = React.useState(false);
  const [plannedCount, setPlannedCount] = React.useState<string>(seed?.count ?? "");
  // Kaynaksız konulu görevde birim + kitap notu + sayfa aralığı (2026-10-22)
  const [unit, setUnit] = React.useState<ItemUnit>(seed?.unit ?? "test");
  const [note, setNote] = React.useState(seed?.note ?? "");
  const [pageFrom, setPageFrom] = React.useState(seed?.pageFrom ?? "");
  const [pageTo, setPageTo] = React.useState(seed?.pageTo ?? "");
  const seedTopicName = seed && !seed.source ? seed.topic.topic_name : null;

  const booksQ = useQuery<BookOptionsResponse>({
    queryKey: teacherKeys.studentBooksBySubject(
      studentId,
      subjectId === "" ? null : subjectId,
    ),
    queryFn: () =>
      getStudentBooksBySubject(
        studentId,
        subjectId === "" ? null : subjectId,
      ),
    enabled: subjectId !== "",
    staleTime: 60_000,
  });
  const books = booksQ.data?.items ?? [];
  const noBooks = subjectId !== "" && booksQ.isSuccess && books.length === 0;
  // Kitabı olmayan derste kaynaksız otomatik seçilir (koç ayrıca seçmez)
  const sourceless = bookId === "none" || (bookId === "" && noBooks);
  const realBookId = typeof bookId === "number" ? bookId : null;

  const sectionsQ = useQuery<SectionOptionsResponse>({
    queryKey: teacherKeys.studentBookSections(studentId, realBookId ?? 0),
    queryFn: () => getStudentBookSections(studentId, realBookId ?? 0),
    enabled: realBookId !== null,
    staleTime: 60_000,
  });

  const topicsQ = useQuery<SubjectTopicsResponse>({
    queryKey: taskTopicKeys.subjectTopics(studentId, subjectId === "" ? 0 : subjectId),
    queryFn: () => getSubjectTopics(studentId, subjectId === "" ? 0 : subjectId),
    enabled: sourceless && subjectId !== "",
    staleTime: 5 * 60_000,
  });

  // Sayfa görevinde "kaldığı yer": kitap notuna (yoksa konuya) göre son verilen aralık.
  const pageSugQ = usePageSuggestion(studentId, topicId === "" ? null : topicId, note, sourceless);

  const statsQ = useQuery<SectionStatsResponse>({
    queryKey: teacherKeys.studentSectionStats(
      studentId,
      sectionId === "" ? 0 : sectionId,
    ),
    queryFn: () =>
      getStudentSectionStats(studentId, sectionId === "" ? 0 : sectionId),
    enabled: sectionId !== "" && !sourceless,
    staleTime: 30_000,
  });

  function onSubjectChange(v: string) {
    const num = v === "" ? "" : Number(v);
    setSubjectId(num as number | "");
    setBookId("");
    setSectionId("");
    setTopicId("");
    setTopicOpen(false);
    setUnit("test");
    setPageFrom("");
    setPageTo("");
    onFocusSubject(num === "" ? null : num);
  }

  // Seçili bölümde kayıtlı kapasite yetiyor mu? (yetmiyorsa engel değil, uyarı)
  const selectedSection = React.useMemo(
    () =>
      sectionId === "" || sourceless
        ? undefined
        : (sectionsQ.data?.items ?? []).find((s) => s.id === sectionId),
    [sectionsQ.data, sectionId, sourceless],
  );
  // Sayfa biriminde adet aralıktan hesaplanır (bitiş − başlangıç + 1).
  const pf = Number(pageFrom);
  const pt = Number(pageTo);
  const pageMode = sourceless && unit === "sayfa";
  const rangeValid = pageMode && pageFrom !== "" && pageTo !== "" && pf >= 1 && pt >= pf;
  const rangeCount = rangeValid ? pt - pf + 1 : 0;
  const wanted = pageMode ? rangeCount : Number(plannedCount);
  const overflow =
    selectedSection && Number.isFinite(wanted) && wanted > 0
      ? Math.max(0, wanted - selectedSection.remaining)
      : 0;
  // Kutu TEST sayısıdır; 15'ten büyük sayı çoğu zaman soru sayısıdır.
  // Deneme kitabında birim DENEME (1 kalem = 1 deneme; backend her denemeyi ayrı açar).
  const isDenemeBook = !sourceless && Boolean(sectionsQ.data?.is_deneme);
  const unitWord = isDenemeBook ? "deneme" : sourceless ? unit : "test";
  const looksLikeQuestions =
    !isDenemeBook && unitWord === "test" && Number.isFinite(wanted) && wanted > 15;

  const topics = topicsQ.data?.topics ?? [];
  const selectedTopic = topicId === "" ? undefined : topics.find((t) => t.topic_id === topicId);
  const topicLabel = selectedTopic?.name ?? (topicId === seed?.topic.topic_id ? seedTopicName : null);
  const ready = sourceless ? topicId !== "" : realBookId !== null && sectionId !== "";

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready) return;
    const count = pageMode ? rangeCount : Number(plannedCount);
    if (!Number.isFinite(count) || count < 1) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const item = sourceless
      ? {
          // Kaynaksız görev: kitap yok, müfredat konusu var
          book_id: null,
          section_id: null,
          topic_id: topicId as number,
          // Kitap notu (sistemde kayıtlı değilse) görevde kaynak adı olarak görünür
          label: note.trim() || topicLabel || "Konu",
          planned_count: count,
          unit,
          page_from: pageMode ? pf : null,
          page_to: pageMode ? pt : null,
        }
      : {
          book_id: realBookId as number,
          section_id: sectionId as number,
          planned_count: count,
          // Kayıtlı kapasite yetmiyorsa engel çıkarma: koç aşımı formda
          // amber uyarı olarak zaten GÖRÜYOR ve bilerek gönderiyor.
          allow_over_capacity: overflow > 0,
        };
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "test",
          title: "Görev",
          scheduled_hour: scheduledHour,
          period: period,
          items: [item],
        },
      },
      {
        onSuccess: () => {
          setBookId("");
          setSectionId("");
          setTopicId("");
          setPlannedCount("");
          setPageFrom("");
          setPageTo("");
          onAfterAdd();
        },
      },
    );
  }

  const booked = subjects.filter((s) => bookedSubjectIds.has(s.id));
  const others = subjects.filter((s) => !bookedSubjectIds.has(s.id));

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      {/* YENİDEN SIRALAMA (2026-10-22): seçim alanları → (kaynaksızda) birim/not/aralık →
          EN ALTTA adet + Ekle. Eskiden Adet + Ekle birim panelinin ÜSTÜNDEYDİ; birim Ekle'den
          sonra seçiliyormuş gibi okunuyordu. */}
      <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="@2xl:col-span-2" />
        <div className="@2xl:col-span-3">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={onSubjectChange}
          >
            <option value="">— ders seç —</option>
            {/* Tüm dersler tek listede (2026-10-22): kitabı olan derste de kaynaksız
                görev verilebilir — Kitap kutusunda "Kaynaksız" her zaman var. */}
            {[...booked, ...others].map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {bookedSubjectIds.has(s.id) ? " · kitabı var" : ""}
              </option>
            ))}
          </Select>
        </div>
        <div className="@2xl:col-span-3">
          <Label>Kitap</Label>
          <Select
            value={sourceless ? "none" : bookId === "" ? "" : String(bookId)}
            onChange={(v) => {
              setBookId(v === "" ? "" : v === "none" ? "none" : Number(v));
              setSectionId("");
              setTopicId("");
              setTopicOpen(v === "none");
            }}
            disabled={subjectId === ""}
          >
            {subjectId === "" ? (
              <option value="">— önce ders seç —</option>
            ) : noBooks ? null : (
              <option value="">— kitap seç —</option>
            )}
            {books.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
            {/* Kısa etiket: dar kutuda kırpılmasın (açıklaması aşağıda) */}
            {subjectId !== "" ? <option value="none">Kaynaksız</option> : null}
          </Select>
        </div>
        <div className="@2xl:col-span-4">
          <Label>{sourceless ? "Müfredat konusu" : "Ünite / Deneme"}</Label>
          {sourceless ? (
            <button
              type="button"
              onClick={() => setTopicOpen((o) => !o)}
              aria-expanded={topicOpen}
              aria-label="Müfredat konusu seç"
              className={cn(
                "flex min-h-9 w-full items-center justify-between gap-2 rounded-md border bg-background px-3 py-1.5 text-left text-sm",
                topicOpen ? "border-cyan-600 ring-1 ring-cyan-600" : "border-input",
              )}
            >
              <span className={cn("min-w-0 break-words", !selectedTopic && "text-muted-foreground")}>
                {topicLabel ?? "— konu ara / seç —"}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            </button>
          ) : (
            <Select
              value={sectionId === "" ? "" : String(sectionId)}
              onChange={(v) => setSectionId(v === "" ? "" : (Number(v) as number))}
              disabled={realBookId === null}
            >
              <option value="">
                {realBookId === null ? "— önce kitap seç —" : "— ünite seç —"}
              </option>
              {(sectionsQ.data?.items ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                  {s.topic_name ? ` (${s.topic_name})` : ""} · kalan {s.remaining}
                </option>
              ))}
            </Select>
          )}
        </div>
      </div>
      {sourceless && subjectId !== "" && topicOpen ? (
        <TopicPickerPanel
          topics={topics}
          loading={topicsQ.isLoading}
          selectedId={topicId === "" ? null : topicId}
          onSelect={(t) => {
            setTopicId(t.topic_id);
            setTopicOpen(false);
          }}
          onClose={() => setTopicOpen(false)}
        />
      ) : null}
      {sourceless && topicId !== "" ? (
        <SourcelessOptions
          unit={unit}
          onUnit={(u) => {
            setUnit(u);
            if (u !== "sayfa") {
              setPageFrom("");
              setPageTo("");
            }
          }}
          note={note}
          onNote={setNote}
          pageFrom={pageFrom}
          pageTo={pageTo}
          onPageFrom={setPageFrom}
          onPageTo={setPageTo}
          rangeInvalid={pageMode && pageFrom !== "" && pageTo !== "" && !rangeValid}
          suggestion={pageSugQ.data}
        />
      ) : null}
      {sourceless && subjectId !== "" && noBooks ? (
        <p className="flex items-start gap-1.5 text-[11.5px] leading-snug text-muted-foreground">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Öğrencinin bu derste kitabı yok — görev seçtiğin müfredat konusuna bağlanır.</span>
        </p>
      ) : null}
      {/* Miktar + birincil eylem en altta */}
      <div className="flex flex-wrap items-end justify-end gap-3" data-section="task-form:submit-row">
        <div className="w-40">
          <Label>Adet ({unitWord})</Label>
          {pageMode ? (
            <div
              className="flex h-9 items-center justify-end rounded-md border border-dashed border-input px-3 text-sm tabular-nums text-muted-foreground"
              aria-label="Sayfa adedi"
              title="Sayfa aralığından hesaplanır"
            >
              {rangeValid ? `${rangeCount} sayfa` : "aralıktan"}
            </div>
          ) : (
            <Input
              type="number"
              min={1}
              value={plannedCount}
              onChange={(e) => setPlannedCount(e.target.value)}
              className="text-right tabular-nums"
              aria-label={
                isDenemeBook ? "Deneme sayısı" : unitWord === "soru" ? "Soru sayısı" : "Test sayısı"
              }
            />
          )}
        </div>
        <div className="w-40">
          <SubmitButton
            pending={create.isPending}
            disabled={!ready || (pageMode ? !rangeValid : !plannedCount)}
          />
        </div>
      </div>
      {looksLikeQuestions ? (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[12px] leading-snug text-amber-900">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Bu kutu <b>test sayısıdır</b> — {wanted} test yazdın. Soru sayısı yazdıysan test
            sayısına çevir (bir test genelde 10–15 soru).
          </span>
        </p>
      ) : null}
      {overflow > 0 && selectedSection ? (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[12px] leading-snug text-amber-900">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            <b>{selectedSection.label}</b> bölümünde kayıtlı kapasite{" "}
            {selectedSection.remaining === 0 ? "kalmadı" : `${selectedSection.remaining} ${unitWord}`}
            {" "}— <b>{overflow} {unitWord}</b> aşılacak. Görev yine de oluşturulur; kitaptaki
            sayı gerçeği her zaman yansıtmaz.
          </span>
        </p>
      ) : null}
      {statsQ.data && !sourceless ? <SectionStatsMini stats={statsQ.data} /> : null}
    </form>
  );
}

// =============================================================================
// BLOK TİPİ (serbest iş bloğu — Katman 3)
// Sistemde olmayan kaynak (özel ders / başka öğretmen ödevi). Koç bir blok
// seçer (veya oluşturur) + bu güne kaç dağıtacağını girer → bağlı görev oluşur,
// blok "dağıtılan/kalan"ı günceller. Backend'e type="other" + kitapsız kalem +
// work_block_id gönderir.
// =============================================================================

function BlockForm({
  studentId,
  dayDate,
  subjects,
  period,
  onFocusSubject,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const createBlock = useCreateWorkBlock(studentId);
  const blocksQ = useQuery<WorkBlockListResponse>({
    queryKey: teacherKeys.studentWorkBlocks(studentId),
    queryFn: () => getTeacherWorkBlocks(studentId),
    staleTime: 30_000,
  });
  const blocks = blocksQ.data?.items ?? [];

  const [selected, setSelected] = React.useState<string>(""); // "" | id | "new"
  const [hour, setHour] = React.useState("");
  const [count, setCount] = React.useState("");
  const [label, setLabel] = React.useState("");

  // Yeni blok alanları
  const [nbTitle, setNbTitle] = React.useState("");
  const [nbTotal, setNbTotal] = React.useState("");
  const [nbUnit, setNbUnit] = React.useState("test");
  const [nbSubject, setNbSubject] = React.useState<number | "">("");

  const selectedBlock: WorkBlock | undefined =
    selected !== "" && selected !== "new"
      ? blocks.find((b) => b.id === Number(selected))
      : undefined;

  function onCreateBlock(e: React.FormEvent) {
    e.preventDefault();
    const t = nbTitle.trim();
    const n = Number(nbTotal);
    if (!t || !Number.isFinite(n) || n < 1) return;
    createBlock.mutate(
      {
        body: {
          title: t,
          total_count: n,
          unit: nbUnit,
          subject_id: nbSubject === "" ? null : Number(nbSubject),
        },
      },
      {
        onSuccess: (res) => {
          // Oluşan bloğu seç + alanları sıfırla
          setSelected(String(res.data.id));
          setNbTitle("");
          setNbTotal("");
          setNbSubject("");
        },
      },
    );
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedBlock) return;
    const n = Number(count);
    if (!Number.isFinite(n) || n < 1) return;
    const itemLabel = label.trim() || selectedBlock.title;
    // Ders varsa "{Ders} · {etiket}" → editör/ızgara ders grubuna sokar.
    const title = selectedBlock.subject_name
      ? `${selectedBlock.subject_name} · ${itemLabel}`
      : itemLabel;
    const scheduledHour = hour === "" ? null : Number(hour);
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "other",
          title,
          scheduled_hour: scheduledHour,
          period,
          work_block_id: selectedBlock.id,
          items: [
            {
              book_id: null,
              section_id: null,
              label: itemLabel,
              planned_count: n,
            },
          ],
        },
      },
      {
        onSuccess: () => {
          setCount("");
          setLabel("");
          onFocusSubject(selectedBlock.subject_id ?? null);
          onAfterAdd();
        },
      },
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <Label>İş bloğu</Label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring transition"
        >
          <option value="">— blok seç —</option>
          {blocks.map((b) => (
            <option key={b.id} value={b.id}>
              {b.title} — kalan {b.remaining}/{b.total_count} {b.unit}
            </option>
          ))}
          <option value="new">+ Yeni blok oluştur</option>
        </select>
      </div>

      {selected === "new" ? (
        <form
          onSubmit={onCreateBlock}
          className="rounded-lg border border-border bg-muted/30 p-3 space-y-2"
        >
          <p className="text-[11px] text-muted-foreground">
            Yeni serbest blok — örn. özel ders öğretmeninin hazırladığı 10 test.
          </p>
          <Input
            type="text"
            value={nbTitle}
            onChange={(e) => setNbTitle(e.target.value)}
            maxLength={200}
            placeholder="Blok adı — örn. Özel Ders Mat ödevi"
          />
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <Label>Toplam</Label>
              <Input
                type="number"
                min={1}
                value={nbTotal}
                onChange={(e) => setNbTotal(e.target.value)}
                placeholder="10"
                className="w-24 text-right tabular-nums"
              />
            </div>
            <div>
              <Label>Birim</Label>
              <select
                value={nbUnit}
                onChange={(e) => setNbUnit(e.target.value)}
                className="px-2 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="test">test</option>
                <option value="soru">soru</option>
                <option value="deneme">deneme</option>
              </select>
            </div>
            <div className="min-w-[140px]">
              <Label>Ders (opsiyonel)</Label>
              <Select
                value={nbSubject === "" ? "" : String(nbSubject)}
                onChange={(v) => setNbSubject(v === "" ? "" : Number(v))}
              >
                <option value="">— ders —</option>
                {subjects.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </div>
            <button
              type="submit"
              disabled={createBlock.isPending || !nbTitle.trim() || !nbTotal}
              className="ml-auto inline-flex items-center gap-1.5 rounded-md bg-foreground px-3 py-1.5 text-sm font-medium text-background hover:bg-foreground/90 disabled:opacity-40 transition"
            >
              {createBlock.isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <Plus className="size-3.5" aria-hidden />
              )}
              Oluştur ve seç
            </button>
          </div>
        </form>
      ) : null}

      {selectedBlock ? (
        <form onSubmit={onSubmit} className="space-y-2">
          <div className="rounded-md border border-indigo-200 bg-indigo-50/60 px-3 py-2 text-[12px] text-indigo-800 flex items-center justify-between gap-2">
            <span className="truncate">
              <b>{selectedBlock.title}</b>
              {selectedBlock.subject_name ? ` · ${selectedBlock.subject_name}` : ""}
            </span>
            <span className="whitespace-nowrap tabular-nums font-medium">
              kalan {selectedBlock.remaining}/{selectedBlock.total_count} {selectedBlock.unit}
            </span>
          </div>
          <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
            <HourInput value={hour} onChange={setHour} className="@2xl:col-span-1" />
            <div className="@2xl:col-span-6">
              <Label>Bu görevin konusu / etiketi (opsiyonel)</Label>
              <Input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                maxLength={200}
                placeholder={`örn. Bölüm 1 · boş bırakılırsa "${selectedBlock.title}"`}
              />
            </div>
            <div className="@2xl:col-span-3">
              <Label>Bu güne kaç {selectedBlock.unit}</Label>
              <Input
                type="number"
                min={1}
                value={count}
                onChange={(e) => setCount(e.target.value)}
                placeholder="örn. 3"
                className="text-right tabular-nums"
              />
            </div>
            <div className="@2xl:col-span-2 flex justify-end">
              <SubmitButton
                pending={create.isPending}
                disabled={!count || Number(count) < 1}
              />
            </div>
          </div>
          {count && Number(count) > selectedBlock.remaining ? (
            <p className="inline-flex items-center gap-1.5 text-[11px] text-amber-700">
              <AlertTriangle className="size-3" aria-hidden />
              Kalan {selectedBlock.remaining} {selectedBlock.unit}; daha fazla
              dağıtıyorsun (engellenmez — bloğun toplamı aşılır).
            </p>
          ) : (
            <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
              <Info className="size-3" aria-hidden />
              Bu görev bloğun “dağıtılan”ına sayar; programda{" "}
              {selectedBlock.unit} olarak görünür.
            </p>
          )}
        </form>
      ) : null}
    </div>
  );
}

// =============================================================================
// VIDEO TİPİ
// =============================================================================

function VideoForm({
  studentId,
  dayDate,
  subjects,
  period,
  onFocusSubject,
  onAfterAdd,
  seed = null,
}: {
  seed?: TaskSeed | null;
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  // Hızlı kutudan taşınan konu (2026-10-22): ders + metin dolu gelir, görev konuya bağlanır.
  const [subjectId, setSubjectId] = React.useState<number | "">(seed?.topic.subject_id ?? "");
  const [linked, setLinked] = React.useState<{ id: number; name: string; subjectId: number } | null>(
    seed ? { id: seed.topic.topic_id, name: seed.topic.topic_name, subjectId: seed.topic.subject_id } : null,
  );
  const subjectOptions = withSeedSubject(subjects, seed);
  const [linkUrl, setLinkUrl] = React.useState("");
  const [notes, setNotes] = React.useState(seed?.topic.topic_name ?? "");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !linkUrl.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjectOptions.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık formatı her zaman "{ders} · {içerik}" — render tarafı ders adını
    // parse edip rozet olarak gösterir (Test ile görsel simetri).
    const trimmedNotes = notes.trim();
    const title = trimmedNotes
      ? `${subjectName} · ${trimmedNotes}`
      : `${subjectName} · video`;
    // Video URL'i ayrı alanda gider (link_url, 2026-09-16); notes yalnız
    // açıklama taşır. Öğrenci/koç yüzeyleri "Videoyu izle" düğmesini bundan kurar.
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "video",
          title,
          scheduled_hour: scheduledHour,
          period: period,
          notes: trimmedNotes || null,
          link_url: linkUrl.trim(),
          items: [],
          topic_id: linked?.id ?? null,
        },
      },
      {
        onSuccess: () => {
          setLinkUrl("");
          setNotes("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="@2xl:col-span-1" />
        <div className="@2xl:col-span-2">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              if (linked && num !== linked.subjectId) setLinked(null);
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjectOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="@2xl:col-span-5">
          <Label>Video bağlantısı</Label>
          <Input
            type="url"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="font-mono"
          />
        </div>
        <div className="@2xl:col-span-3">
          <Label>Açıklama</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Trigonometri giriş"
          />
        </div>
        <div className="@2xl:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !linkUrl.trim()}
          />
        </div>
      </div>
      {linked ? <LinkedTopicChip name={linked.name} onRemove={() => setLinked(null)} /> : null}
      <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
        <Info className="size-3" aria-hidden />
        Ders seçimi zorunlu — programa &quot;{`{ders}`} videosu&quot; olarak
        düşer. Öğrenci linke tıklayarak videoyu açar.
      </p>
    </form>
  );
}

// =============================================================================
// ÖZET TİPİ
// =============================================================================

function OzetForm({
  studentId,
  dayDate,
  subjects,
  period,
  onFocusSubject,
  onAfterAdd,
  seed = null,
}: {
  seed?: TaskSeed | null;
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  // Hızlı kutudan taşınan konu (2026-10-22): ders + metin dolu gelir, görev konuya bağlanır.
  const [subjectId, setSubjectId] = React.useState<number | "">(seed?.topic.subject_id ?? "");
  const [linked, setLinked] = React.useState<{ id: number; name: string; subjectId: number } | null>(
    seed ? { id: seed.topic.topic_id, name: seed.topic.topic_name, subjectId: seed.topic.subject_id } : null,
  );
  const subjectOptions = withSeedSubject(subjects, seed);
  const [notes, setNotes] = React.useState(seed?.topic.topic_name ?? "");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !notes.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjectOptions.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık: "{ders} · {konu}" — render parse'ı ders rozetine çevirir
    // (görsel olarak Test/Video/Tekrar/Diğer ile aynı düzen).
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "ozet",
          title: `${subjectName} · ${notes.trim()}`,
          scheduled_hour: scheduledHour,
          period: period,
          notes: null,
          items: [],
          topic_id: linked?.id ?? null,
        },
      },
      {
        onSuccess: () => {
          setNotes("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="@2xl:col-span-1" />
        <div className="@2xl:col-span-3">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              if (linked && num !== linked.subjectId) setLinked(null);
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjectOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="@2xl:col-span-7">
          <Label>Özet çıkarılacak konu</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Atatürk ilkelerinin sınıflandırılması"
          />
        </div>
        <div className="@2xl:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !notes.trim()}
          />
        </div>
      </div>
      {linked ? <LinkedTopicChip name={linked.name} onRemove={() => setLinked(null)} /> : null}
    </form>
  );
}

// =============================================================================
// TEKRAR TİPİ
// =============================================================================

function TekrarForm({
  studentId,
  dayDate,
  subjects,
  period,
  onFocusSubject,
  onAfterAdd,
  seed = null,
}: {
  seed?: TaskSeed | null;
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  // Hızlı kutudan taşınan konu (2026-10-22): ders + metin dolu gelir, görev konuya bağlanır.
  const [subjectId, setSubjectId] = React.useState<number | "">(seed?.topic.subject_id ?? "");
  const [linked, setLinked] = React.useState<{ id: number; name: string; subjectId: number } | null>(
    seed ? { id: seed.topic.topic_id, name: seed.topic.topic_name, subjectId: seed.topic.subject_id } : null,
  );
  const subjectOptions = withSeedSubject(subjects, seed);
  const [notes, setNotes] = React.useState(seed?.topic.topic_name ?? "");

  const chipsQ = useQuery<ReviewStruggleResponse>({
    queryKey: teacherKeys.studentReviewChips(
      studentId,
      subjectId === "" ? 0 : subjectId,
      dayDate,
    ),
    queryFn: () =>
      getStudentReviewChips(studentId, subjectId === "" ? 0 : subjectId, dayDate),
    enabled: subjectId !== "",
    staleTime: 30_000,
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !notes.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjectOptions.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık: "{ders} · {konu}" — render parse'ı ders rozetine çevirir.
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "tekrar",
          title: `${subjectName} · ${notes.trim()}`,
          scheduled_hour: scheduledHour,
          period: period,
          notes: null,
          items: [],
          topic_id: linked?.id ?? null,
        },
      },
      {
        onSuccess: () => {
          setNotes("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="@2xl:col-span-1" />
        <div className="@2xl:col-span-3">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              if (linked && num !== linked.subjectId) setLinked(null);
              setNotes("");
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjectOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="@2xl:col-span-7">
          <Label>Tekrar edilecek konu</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Üçgenlerde benzerlik"
          />
        </div>
        <div className="@2xl:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !notes.trim()}
          />
        </div>
      </div>
      {linked ? <LinkedTopicChip name={linked.name} onRemove={() => setLinked(null)} /> : null}
      {subjectId !== "" && chipsQ.data ? (
        <ReviewChips
          data={chipsQ.data}
          onChipClick={(topic) => setNotes(topic)}
          selectedNotes={notes}
        />
      ) : null}
    </form>
  );
}

function ReviewChips({
  data,
  onChipClick,
  selectedNotes,
}: {
  data: ReviewStruggleResponse;
  onChipClick: (topic: string) => void;
  selectedNotes: string;
}) {
  if (data.items.length === 0) {
    return (
      <div className="mt-2 px-3 py-2 rounded-md border border-border bg-muted/30 text-xs italic text-muted-foreground">
        Bu derste bugün vadesi gelen tekrar kartı yok — konuyu elle yazabilirsin.
      </div>
    );
  }
  return (
    <div className="mt-2 px-3 py-2.5 rounded-md border border-border bg-muted/30">
      <div className="flex items-center gap-2 mb-2">
        <Brain className="size-3.5 text-foreground" aria-hidden />
        <span className="text-[11px] font-semibold text-foreground">
          Bugün vadesi gelen tekrar kartları
        </span>
        <span className="text-[10px] text-muted-foreground">
          ({data.items.length})
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {data.items.map((it) => {
          const selected = selectedNotes === it.topic_name;
          const StateIcon =
            it.state === "relearning"
              ? Flame
              : it.lapse_count >= 2
                ? AlertTriangle
                : Brain;
          const scoreTone =
            it.score >= 60
              ? "bg-rose-100 text-rose-800"
              : it.score >= 30
                ? "bg-amber-100 text-amber-800"
                : "bg-muted text-muted-foreground";
          return (
            <button
              key={it.card_id}
              type="button"
              onClick={() => onChipClick(it.topic_name)}
              className={cn(
                "inline-flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-md text-[11px] font-medium border bg-card transition hover:bg-muted",
                selected
                  ? "border-foreground ring-1 ring-foreground"
                  : "border-border",
              )}
              title={`${it.reasons.join(" · ")} · skor ${it.score}/100`}
            >
              <StateIcon className="size-3 text-muted-foreground" aria-hidden />
              <span className="text-foreground">{it.topic_name}</span>
              <span
                className={cn(
                  "text-[9px] font-bold px-1 py-0.5 rounded tabular-nums",
                  scoreTone,
                )}
              >
                {it.score}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// DİĞER TİPİ
// =============================================================================

function OtherForm({
  studentId,
  dayDate,
  subjects,
  period,
  onFocusSubject,
  onAfterAdd,
  seed = null,
}: {
  seed?: TaskSeed | null;
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  // Hızlı kutudan taşınan konu (2026-10-22): ders + metin dolu gelir, görev konuya bağlanır.
  const [subjectId, setSubjectId] = React.useState<number | "">(seed?.topic.subject_id ?? "");
  const [linked, setLinked] = React.useState<{ id: number; name: string; subjectId: number } | null>(
    seed ? { id: seed.topic.topic_id, name: seed.topic.topic_name, subjectId: seed.topic.subject_id } : null,
  );
  const subjectOptions = withSeedSubject(subjects, seed);
  const [title, setTitle] = React.useState(seed?.topic.topic_name ?? "");
  const [notes, setNotes] = React.useState("");
  // 2026-10-16: metinde "N test" varsa konuya bağlama önerisi (Açı saha bulgusu —
  // serbest metinli test görevleri hiçbir tabloya girmiyordu). Öneri sorgusu
  // yazım bitince (yarım saniye) çalışır.
  const [probe, setProbe] = React.useState({ title: "", notes: "" });
  const probeTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  function scheduleProbe(nextTitle: string, nextNotes: string) {
    if (probeTimer.current) clearTimeout(probeTimer.current);
    probeTimer.current = setTimeout(
      () => setProbe({ title: nextTitle.trim(), notes: nextNotes.trim() }),
      500,
    );
  }
  // 2026-10-30: "N test" kadar "30 soru", "4 sayfa" da algılanır (birimiyle).
  const found = extractCount(probe.notes, probe.title);
  const testCount = found?.count ?? null;
  const countUnit = found?.unit ?? "test";
  const link = useTopicLink(
    studentId,
    subjectId === "" ? null : subjectId,
    probe.title,
    probe.notes,
    testCount,
  );
  const linking = link.enabled && link.topicId !== null && testCount !== null;

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !title.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjectOptions.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık formatı: "{ders} · {başlık}"
    const fullTitle = `${subjectName} · ${title.trim()}`;
    if (linking && link.topicId !== null && testCount !== null) {
      // Konuya bağlı test görevi: kaynaksız konu kalemi → müfredat, konu
      // performansı ve kurum tablolarına girer (rezerv/kapasite yok).
      create.mutate(
        {
          body: {
            date: dayDate,
            type: "test",
            title: fullTitle,
            scheduled_hour: scheduledHour,
            period: period,
            notes: notes.trim() || null,
            items: [
              {
                book_id: null,
                section_id: null,
                topic_id: link.topicId,
                planned_count: testCount,
                unit: itemUnit(countUnit),
              },
            ],
          },
        },
        {
          onSuccess: () => {
            setTitle("");
            setNotes("");
            setProbe({ title: "", notes: "" });
            link.reset();
            onAfterAdd();
          },
        },
      );
      return;
    }

    create.mutate(
      {
        body: {
          date: dayDate,
          type: "other",
          title: fullTitle,
          scheduled_hour: scheduledHour,
          period: period,
          notes: notes.trim() || null,
          items: [],
          topic_id: linked?.id ?? null,
        },
      },
      {
        onSuccess: () => {
          setTitle("");
          setNotes("");
          setProbe({ title: "", notes: "" });
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 @md:grid-cols-2 @2xl:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="@2xl:col-span-1" />
        <div className="@2xl:col-span-2">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              if (linked && num !== linked.subjectId) setLinked(null);
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjectOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="@2xl:col-span-3">
          <Label>Başlık</Label>
          <Input
            type="text"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              scheduleProbe(e.target.value, notes);
            }}
            maxLength={200}
            placeholder="Örn. Konu özeti hazırla"
          />
        </div>
        <div className="@2xl:col-span-5">
          <Label>Açıklama (opsiyonel)</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => {
              setNotes(e.target.value);
              scheduleProbe(title, e.target.value);
            }}
            maxLength={300}
            placeholder="Detay açıklama"
          />
        </div>
        <div className="@2xl:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !title.trim()}
          />
        </div>
      </div>
      {link.enabled && subjectId !== "" && testCount !== null ? (
        <TopicLinkPanel
          studentId={studentId}
          subjectId={subjectId}
          count={testCount}
          unit={countUnit}
          suggestion={link.suggestion}
          loading={link.loading}
          value={link.topicId}
          onChange={link.setTopicId}
        />
      ) : null}
      {linking ? (
        <p className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700">
          <Info className="size-3" aria-hidden />
          Görev &quot;{testCount} {countUnit}&quot; olarak seçilen konuya bağlı kaydedilecek.
        </p>
      ) : (
        <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
          <Info className="size-3" aria-hidden />
          Ders seçimi zorunlu — programa &quot;{`{ders}`} · {`{başlık}`}&quot;
          olarak düşer.
        </p>
      )}
      {linked ? <LinkedTopicChip name={linked.name} onRemove={() => setLinked(null)} /> : null}
    </form>
  );
}

// =============================================================================
// Form input yardımcıları
// =============================================================================

function Label({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-1">
      {children}
    </label>
  );
}

function Input({
  className,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={cn(
        "w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring transition",
        className,
      )}
    />
  );
}

function Select({
  value,
  onChange,
  disabled,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="w-full px-2.5 py-1.5 border border-input bg-background rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring disabled:opacity-50 transition"
    >
      {children}
    </select>
  );
}

function HourInput({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label>Saat</Label>
      <Input
        type="number"
        min={0}
        max={23}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="—"
        className="text-center font-mono tabular-nums"
      />
    </div>
  );
}

function SubmitButton({
  pending,
  disabled,
}: {
  pending: boolean;
  disabled: boolean;
}) {
  return (
    <button
      type="submit"
      disabled={pending || disabled}
      className="inline-flex h-9 items-center justify-center gap-1.5 w-full px-3 py-1.5 rounded-md bg-foreground text-background text-sm font-medium hover:bg-foreground/90 disabled:opacity-40 transition"
    >
      {pending ? (
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      ) : (
        <Plus className="size-3.5" aria-hidden />
      )}
      Ekle
    </button>
  );
}

function SectionStatsMini({ stats }: { stats: SectionStatsResponse }) {
  return (
    <div className="mt-3 rounded-lg border border-border bg-muted/30 p-3">
      <div className="grid grid-cols-3 gap-2">
        <StatCell
          label="Bölümde"
          value={stats.total}
          subtitle="test toplam"
          tone="neutral"
        />
        <StatCell
          label="Çözülmüş"
          value={stats.completed}
          subtitle={
            stats.reserved > 0 ? `+${stats.reserved} rezerv` : "—"
          }
          tone={stats.completed > 0 ? "info" : "neutral"}
        />
        <StatCell
          label="Kalan"
          value={stats.remaining}
          subtitle={stats.remaining === 0 ? "bölüm tamam" : "test boş"}
          tone={stats.remaining > 0 ? "success" : "danger"}
        />
      </div>
      <p className="text-[11px] text-muted-foreground mt-2 px-0.5">
        <span className="font-medium text-foreground">{stats.book_name}</span> ·{" "}
        {stats.section_label}
        {stats.topic_name ? (
          <span className="text-muted-foreground/70"> ({stats.topic_name})</span>
        ) : null}{" "}
        · <span className="tabular-nums">{stats.remaining}</span> kapasite kaldı
      </p>
    </div>
  );
}

function StatCell({
  label,
  value,
  subtitle,
  tone,
}: {
  label: string;
  value: number;
  subtitle: string;
  tone: "neutral" | "info" | "success" | "danger";
}) {
  const toneClass = {
    neutral: "text-foreground",
    info: "text-indigo-700",
    success: "text-emerald-700",
    danger: "text-rose-700",
  }[tone];
  return (
    <div className="px-2 py-1.5 rounded-md bg-background border border-border text-center">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
        {label}
      </div>
      <div className={cn("text-lg font-bold tabular-nums mt-0.5", toneClass)}>
        {value}
      </div>
      <div className="text-[10px] text-muted-foreground/80">{subtitle}</div>
    </div>
  );
}


const UNIT_OPTIONS: { value: ItemUnit; label: string; hint: string }[] = [
  { value: "test", label: "Test", hint: "test sayısına girer" },
  { value: "soru", label: "Soru", hint: "D/Y/B girilir" },
  { value: "sayfa", label: "Sayfa", hint: "sayfa aralığı" },
];

/** Kaynaksız konulu görev seçenekleri: birim · kitap notu · sayfa aralığı (2026-10-22). */
export function SourcelessOptions({
  unit,
  onUnit,
  note,
  onNote,
  pageFrom,
  pageTo,
  onPageFrom,
  onPageTo,
  rangeInvalid,
  suggestion,
}: {
  unit: ItemUnit;
  onUnit: (u: ItemUnit) => void;
  note: string;
  onNote: (v: string) => void;
  pageFrom: string;
  pageTo: string;
  onPageFrom: (v: string) => void;
  onPageTo: (v: string) => void;
  rangeInvalid: boolean;
  suggestion: PageSuggestionResponse | undefined;
}) {
  const listId = React.useId();
  return (
    <div
      className="@container space-y-3 rounded-lg border border-cyan-600/30 bg-cyan-500/5 p-3"
      data-section="task-form:sourceless-options"
    >
      <div className="grid grid-cols-1 gap-3 @xl:grid-cols-2">
        <div>
          <Label>Birim</Label>
          <div className="flex gap-1.5" role="radiogroup" aria-label="Birim">
            {UNIT_OPTIONS.map((o) => (
              <button
                key={o.value}
                type="button"
                role="radio"
                aria-checked={unit === o.value}
                onClick={() => onUnit(o.value)}
                className={cn(
                  "flex-1 rounded-md border px-2 py-1.5 text-left transition",
                  unit === o.value
                    ? "border-cyan-700 bg-cyan-700 text-white"
                    : "border-input bg-background text-foreground hover:bg-muted",
                )}
              >
                <span className="block text-sm font-semibold">{o.label}</span>
                <span
                  className={cn(
                    "block text-[10.5px] leading-tight",
                    unit === o.value ? "text-cyan-50" : "text-muted-foreground",
                  )}
                >
                  {o.hint}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <Label>Kitap adı (not · isteğe bağlı)</Label>
          <Input
            value={note}
            onChange={(e) => onNote(e.target.value)}
            list={listId}
            maxLength={120}
            placeholder="örn. Hız Fen"
            aria-label="Kitap adı notu"
          />
          <datalist id={listId}>
            {(suggestion?.notes ?? []).map((n) => (
              <option key={n} value={n} />
            ))}
          </datalist>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            Görevde kaynak adı olarak görünür; kitabın test sayaçlarına dokunmaz.
          </p>
        </div>
      </div>
      {unit === "sayfa" ? (
        <div className="space-y-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="w-28">
              <Label>İlk sayfa</Label>
              <Input
                type="number"
                min={1}
                value={pageFrom}
                onChange={(e) => onPageFrom(e.target.value)}
                className="text-right tabular-nums"
                aria-label="Başlangıç sayfası"
              />
            </div>
            <span className="pb-2 text-muted-foreground">–</span>
            <div className="w-28">
              <Label>Son sayfa</Label>
              <Input
                type="number"
                min={1}
                value={pageTo}
                onChange={(e) => onPageTo(e.target.value)}
                className="text-right tabular-nums"
                aria-label="Bitiş sayfası"
              />
            </div>
          </div>
          {rangeInvalid ? (
            <p className="text-[12px] text-rose-700">
              Bitiş sayfası başlangıçtan küçük olamaz.
            </p>
          ) : null}
          <PageSuggestionLine data={suggestion} pageFrom={pageFrom} onPageFrom={onPageFrom} />
        </div>
      ) : null}
    </div>
  );
}


/** Taşınan konunun dersi etkinlik ders listesinde yoksa listeye eklenir (seçili gelsin). */
function withSeedSubject(
  subjects: { id: number; name: string }[],
  seed: TaskSeed | null,
): { id: number; name: string }[] {
  if (!seed || subjects.some((x) => x.id === seed.topic.subject_id)) return subjects;
  return [...subjects, { id: seed.topic.subject_id, name: seed.topic.subject_name }];
}
