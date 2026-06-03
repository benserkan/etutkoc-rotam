"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
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
  Video,
} from "lucide-react";

import type { TaskPeriod } from "@/lib/types/teacher";

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
import { useTeacherStudent } from "@/lib/hooks/use-teacher-queries";
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

// ---------------------------------------------------------------------------
// Deneme presetleri — öğrencinin sınav hedefi ve sınıf seviyesine göre
// gösterilen deneme türleri. Tıklanınca title + planlanan soru sayısı doldurur.
// ---------------------------------------------------------------------------

interface DenemePreset {
  title: string;
  count: number;
}

interface DenemePresetGroup {
  group: string;
  items: DenemePreset[];
}

// LGS hazırlık öğrencisi (8. sınıf)
const DENEME_LGS: DenemePresetGroup[] = [
  {
    group: "LGS",
    items: [
      { title: "LGS Tam Deneme", count: 90 },
      { title: "LGS Sözel Bölüm", count: 50 },
      { title: "LGS Sayısal Bölüm", count: 40 },
    ],
  },
];

// YKS hazırlık öğrencisi (11-12 + mezun)
const DENEME_YKS: DenemePresetGroup[] = [
  {
    group: "TYT",
    items: [
      { title: "TYT Genel Deneme", count: 120 },
      { title: "TYT Türkçe Branş", count: 40 },
      { title: "TYT Sosyal Branş", count: 20 },
      { title: "TYT Matematik Branş", count: 40 },
      { title: "TYT Fen Bilimleri Branş", count: 20 },
    ],
  },
  {
    group: "AYT",
    items: [
      { title: "AYT Genel Deneme", count: 80 },
      { title: "AYT Matematik Branş", count: 40 },
      { title: "AYT Fizik Branş", count: 14 },
      { title: "AYT Kimya Branş", count: 13 },
      { title: "AYT Biyoloji Branş", count: 13 },
      { title: "AYT Türk Dili-Edebiyatı Branş", count: 24 },
      { title: "AYT Tarih Branş", count: 21 },
      { title: "AYT Coğrafya Branş", count: 17 },
    ],
  },
  {
    group: "YDT",
    items: [{ title: "YDT (Yabancı Dil) Deneme", count: 80 }],
  },
];

// 9-10 ara sınıf (sınav hedefi henüz yok)
const DENEME_LISE_ARA: DenemePresetGroup[] = [
  {
    group: "Sınıf Denemesi",
    items: [
      { title: "Sınıf Genel Deneme", count: 40 },
      { title: "Sınıf Sözel Bölüm", count: 20 },
      { title: "Sınıf Sayısal Bölüm", count: 20 },
    ],
  },
];

function pickPresetGroups(
  examTarget: string | null | undefined,
  gradeLevel: number | null | undefined,
): DenemePresetGroup[] {
  // Öncelikle exam_target — kesin sınav hedefi varsa onu kullan
  if (examTarget === "LGS" || examTarget === "lgs") return DENEME_LGS;
  if (examTarget === "YKS" || examTarget === "yks") return DENEME_YKS;
  // Mezun (graduate) genelde YKS hedefli
  // 8. sınıf default LGS
  if (gradeLevel === 8) return DENEME_LGS;
  // 11-12 default YKS
  if (gradeLevel === 11 || gradeLevel === 12) return DENEME_YKS;
  // 9-10 ara
  if (gradeLevel === 9 || gradeLevel === 10) return DENEME_LISE_ARA;
  // Bilinmiyor → tüm grupları göster (LGS + YKS) — kullanıcı seçer
  return [...DENEME_LGS, ...DENEME_YKS];
}

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
}

export function AddTaskForm({
  studentId,
  dayDate,
  onFocusSubject,
  onAfterAdd,
}: Props) {
  const [type, setType] = React.useState<TaskType>("test");
  // M6 — opsiyonel periyot. Null = atanmamış (default).
  const [period, setPeriod] = React.useState<TaskPeriod | null>(null);

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

  return (
    <div className="px-4 py-4 border-t border-border/60 bg-card">
      <div className="mb-3">
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
          Görev tipi
        </p>
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
                    ? "border-foreground bg-foreground text-background shadow-sm"
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
          studentId={studentId}
          dayDate={dayDate}
          subjects={bookedSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
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
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "ozet" ? (
        <OzetForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "tekrar" ? (
        <TekrarForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "other" ? (
        <OtherForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={allSubjects}
          period={period}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
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
  const [hour, setHour] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [bookId, setBookId] = React.useState<number | "">("");
  const [sectionId, setSectionId] = React.useState<number | "">("");
  const [plannedCount, setPlannedCount] = React.useState<string>("");

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

  const sectionsQ = useQuery<SectionOptionsResponse>({
    queryKey: teacherKeys.studentBookSections(
      studentId,
      bookId === "" ? 0 : bookId,
    ),
    queryFn: () => getStudentBookSections(studentId, bookId === "" ? 0 : bookId),
    enabled: bookId !== "",
    staleTime: 60_000,
  });

  const statsQ = useQuery<SectionStatsResponse>({
    queryKey: teacherKeys.studentSectionStats(
      studentId,
      sectionId === "" ? 0 : sectionId,
    ),
    queryFn: () =>
      getStudentSectionStats(studentId, sectionId === "" ? 0 : sectionId),
    enabled: sectionId !== "",
    staleTime: 30_000,
  });

  function onSubjectChange(v: string) {
    const num = v === "" ? "" : Number(v);
    setSubjectId(num as number | "");
    setBookId("");
    setSectionId("");
    onFocusSubject(num === "" ? null : num);
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (bookId === "" || sectionId === "") return;
    const count = Number(plannedCount);
    if (!Number.isFinite(count) || count < 1) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "test",
          title: "Görev",
          scheduled_hour: scheduledHour,
          period: period,
          items: [
            { book_id: bookId, section_id: sectionId, planned_count: count },
          ],
        },
      },
      {
        onSuccess: () => {
          setBookId("");
          setSectionId("");
          setPlannedCount("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-2">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={onSubjectChange}
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-3">
          <Label>Kitap</Label>
          <Select
            value={bookId === "" ? "" : String(bookId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setBookId(num as number | "");
              setSectionId("");
            }}
            disabled={subjectId === ""}
          >
            <option value="">
              {subjectId === "" ? "— önce ders seç —" : "— kitap seç —"}
            </option>
            {(booksQ.data?.items ?? []).map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-3">
          <Label>Ünite / Deneme</Label>
          <Select
            value={sectionId === "" ? "" : String(sectionId)}
            onChange={(v) =>
              setSectionId(v === "" ? "" : (Number(v) as number))
            }
            disabled={bookId === ""}
          >
            <option value="">
              {bookId === "" ? "— önce kitap seç —" : "— ünite seç —"}
            </option>
            {(sectionsQ.data?.items ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
                {s.topic_name ? ` (${s.topic_name})` : ""} · kalan {s.remaining}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-2">
          <Label>Adet</Label>
          <Input
            type="number"
            min={1}
            value={plannedCount}
            onChange={(e) => setPlannedCount(e.target.value)}
            className="text-right tabular-nums"
          />
        </div>
        <div className="md:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={bookId === "" || sectionId === "" || !plannedCount}
          />
        </div>
      </div>
      {statsQ.data ? <SectionStatsMini stats={statsQ.data} /> : null}
    </form>
  );
}

// =============================================================================
// DENEME TİPİ (kitapsız, soru sayılı) — tam LGS/TYT denemesi
// =============================================================================

function DenemeForm({
  studentId,
  dayDate,
  period,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  period: TaskPeriod | null;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [count, setCount] = React.useState("");

  // Öğrencinin sınav hedefi + sınıf seviyesini cache'ten al (student detail
  // sayfası zaten bu query'yi yüklemiş; useTeacherStudent 30s stale).
  const studentQ = useTeacherStudent(studentId);
  const profile = studentQ.data?.student;
  const examTarget = profile?.exam_target ?? null;
  const gradeLevel = profile?.grade_level ?? null;

  const presetGroups = React.useMemo(
    () => pickPresetGroups(examTarget, gradeLevel),
    [examTarget, gradeLevel],
  );

  function applyPreset(preset: DenemePreset) {
    setTitle(preset.title);
    setCount(String(preset.count));
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = title.trim();
    const n = Number(count);
    if (!name || !Number.isFinite(n) || n < 1) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "other", // backend: kitapsız kalem; tasktype enum'una deneme eklenmedi
          title: name,
          scheduled_hour: scheduledHour,
          period: period,
          // Kitapsız "deneme" kalemi: ders/kitap yok, sadece etiket + soru sayısı.
          items: [{ book_id: null, section_id: null, label: name, planned_count: n }],
        },
      },
      {
        onSuccess: () => {
          setTitle("");
          setCount("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-6">
          <Label>Deneme adı</Label>
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Örn. Mebi LGS Tam Deneme 7"
          />
        </div>
        <div className="md:col-span-3">
          <Label>Soru sayısı</Label>
          <Input
            type="number"
            min={1}
            value={count}
            onChange={(e) => setCount(e.target.value)}
            placeholder="örn. 90"
            className="text-right tabular-nums"
          />
        </div>
        <div className="md:col-span-2 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={!title.trim() || !count || Number(count) < 1}
          />
        </div>
      </div>

      <DenemePresetDropdown
        groups={presetGroups}
        onPick={applyPreset}
      />

      <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
        <Info className="size-3" aria-hidden />
        Tam deneme ders/kitap seçmeden eklenir; çözülen soru sayısına sayar.
        Sonuç/net girişi için öğrenci profilindeki &quot;Denemeler&quot; sekmesini kullan.
      </p>
    </form>
  );
}

/**
 * Tek native `<select>` dropdown — mobil-uyumlu (iOS/Android native picker).
 * 13 chip yan yana yerine tek tıkla seçim + optgroup ile sınav kategorisi.
 * Seçim yan etkisi: title + count doldurur; sonra reset (kullanıcı tekrar
 * "hazır seç" yapabilir).
 */
function DenemePresetDropdown({
  groups,
  onPick,
}: {
  groups: DenemePresetGroup[];
  onPick: (preset: DenemePreset) => void;
}) {
  const [value, setValue] = React.useState("");

  function onSelect(v: string) {
    setValue(v);
    if (!v) return;
    // value formatı: "{group_idx}:{item_idx}"
    const [gi, ii] = v.split(":").map(Number);
    const preset = groups[gi]?.items[ii];
    if (preset) onPick(preset);
    // Dropdown'u sıfırla — kullanıcı tekrar seçebilsin
    setTimeout(() => setValue(""), 0);
  }

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-[11px] text-muted-foreground inline-flex items-center gap-1">
        <Info className="size-3" aria-hidden />
        Hızlı seç:
      </span>
      <select
        value={value}
        onChange={(e) => onSelect(e.target.value)}
        className="px-2.5 py-1 border border-input bg-background rounded-md text-xs focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring transition min-w-[240px]"
      >
        <option value="">— hazır deneme türü seç —</option>
        {groups.map((g, gi) => (
          <optgroup key={g.group} label={g.group}>
            {g.items.map((it, ii) => (
              <option key={it.title} value={`${gi}:${ii}`}>
                {it.title} · {it.count} soru
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </div>
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
          <div className="rounded-md border border-indigo-200 dark:border-indigo-900 bg-indigo-50/60 dark:bg-indigo-950/25 px-3 py-2 text-[12px] text-indigo-800 dark:text-indigo-200 flex items-center justify-between gap-2">
            <span className="truncate">
              <b>{selectedBlock.title}</b>
              {selectedBlock.subject_name ? ` · ${selectedBlock.subject_name}` : ""}
            </span>
            <span className="whitespace-nowrap tabular-nums font-medium">
              kalan {selectedBlock.remaining}/{selectedBlock.total_count} {selectedBlock.unit}
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
            <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
            <div className="md:col-span-6">
              <Label>Bu görevin konusu / etiketi (opsiyonel)</Label>
              <Input
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                maxLength={200}
                placeholder={`örn. Bölüm 1 · boş bırakılırsa "${selectedBlock.title}"`}
              />
            </div>
            <div className="md:col-span-3">
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
            <div className="md:col-span-2 flex justify-end">
              <SubmitButton
                pending={create.isPending}
                disabled={!count || Number(count) < 1}
              />
            </div>
          </div>
          {count && Number(count) > selectedBlock.remaining ? (
            <p className="inline-flex items-center gap-1.5 text-[11px] text-amber-700 dark:text-amber-300">
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
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [linkUrl, setLinkUrl] = React.useState("");
  const [notes, setNotes] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !linkUrl.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık formatı her zaman "{ders} · {içerik}" — render tarafı ders adını
    // parse edip rozet olarak gösterir (Test ile görsel simetri).
    const trimmedNotes = notes.trim();
    const title = trimmedNotes
      ? `${subjectName} · ${trimmedNotes}`
      : `${subjectName} · video`;
    // Video URL'i notes alanına eklenir (mevcut backend kontrat — kitapsız tip
    // için ayrı URL alanı yok; URL açıklamayla birlikte saklanır).
    const fullNotes = trimmedNotes
      ? `${trimmedNotes}\n${linkUrl.trim()}`
      : linkUrl.trim();
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "video",
          title,
          scheduled_hour: scheduledHour,
          period: period,
          notes: fullNotes,
          items: [],
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
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-2">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-5">
          <Label>Video bağlantısı</Label>
          <Input
            type="url"
            value={linkUrl}
            onChange={(e) => setLinkUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            className="font-mono"
          />
        </div>
        <div className="md:col-span-3">
          <Label>Açıklama</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Trigonometri giriş"
          />
        </div>
        <div className="md:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !linkUrl.trim()}
          />
        </div>
      </div>
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
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [notes, setNotes] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !notes.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
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
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-3">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-7">
          <Label>Özet çıkarılacak konu</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Atatürk ilkelerinin sınıflandırılması"
          />
        </div>
        <div className="md:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !notes.trim()}
          />
        </div>
      </div>
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
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [notes, setNotes] = React.useState("");

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
    const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
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
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-3">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              setNotes("");
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-7">
          <Label>Tekrar edilecek konu</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={200}
            placeholder="Örn. Üçgenlerde benzerlik"
          />
        </div>
        <div className="md:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !notes.trim()}
          />
        </div>
      </div>
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
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
  period: TaskPeriod | null;
  onFocusSubject: (id: number | null) => void;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const [title, setTitle] = React.useState("");
  const [notes, setNotes] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "" || !title.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
    // Başlık formatı: "{ders} · {başlık}"
    const fullTitle = `${subjectName} · ${title.trim()}`;
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
        },
      },
      {
        onSuccess: () => {
          setTitle("");
          setNotes("");
          onAfterAdd();
        },
      },
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-2">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        <HourInput value={hour} onChange={setHour} className="md:col-span-1" />
        <div className="md:col-span-2">
          <Label>Ders</Label>
          <Select
            value={subjectId === "" ? "" : String(subjectId)}
            onChange={(v) => {
              const num = v === "" ? "" : Number(v);
              setSubjectId(num as number | "");
              onFocusSubject(num === "" ? null : num);
            }}
          >
            <option value="">— ders seç —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
        </div>
        <div className="md:col-span-3">
          <Label>Başlık</Label>
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Örn. Konu özeti hazırla"
          />
        </div>
        <div className="md:col-span-5">
          <Label>Açıklama (opsiyonel)</Label>
          <Input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={300}
            placeholder="Detay açıklama"
          />
        </div>
        <div className="md:col-span-1 flex justify-end">
          <SubmitButton
            pending={create.isPending}
            disabled={subjectId === "" || !title.trim()}
          />
        </div>
      </div>
      <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
        <Info className="size-3" aria-hidden />
        Ders seçimi zorunlu — programa &quot;{`{ders}`} · {`{başlık}`}&quot;
        olarak düşer.
      </p>
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
      className="inline-flex items-center justify-center gap-1.5 w-full px-3 py-1.5 rounded-md bg-foreground text-background text-sm font-medium hover:bg-foreground/90 disabled:opacity-40 transition"
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
