"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Brain,
  FileText,
  Flame,
  Info,
  ListChecks,
  Loader2,
  Plus,
  Repeat,
  Video,
} from "lucide-react";

import {
  getStudentBookSections,
  getStudentBooksBySubject,
  getStudentReviewChips,
  getStudentSectionStats,
  getStudentSidebar,
  teacherKeys,
} from "@/lib/api/teacher";
import { useCreateTask } from "@/lib/hooks/use-teacher-mutations";
import type {
  BookOptionsResponse,
  ReviewStruggleResponse,
  SectionOptionsResponse,
  SectionStatsResponse,
  SidebarResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";

type TaskType = "test" | "video" | "ozet" | "tekrar" | "other";

const TYPE_TILES: Array<{
  key: TaskType;
  label: string;
  Icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}> = [
  { key: "test", label: "Test", Icon: FileText },
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

  const allSidebarQ = useQuery<SidebarResponse>({
    queryKey: teacherKeys.studentSidebar(studentId, null),
    queryFn: () => getStudentSidebar(studentId, null),
    staleTime: 60_000,
  });
  const subjects = (allSidebarQ.data?.subjects ?? []).map((s) => ({
    id: s.id,
    name: s.name,
  }));

  return (
    <div className="px-4 py-4 border-t border-border/60 bg-card">
      <div className="mb-3">
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium mb-2">
          Görev tipi
        </p>
        <div className="grid grid-cols-5 gap-1.5">
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

      {type === "test" ? (
        <TestForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={subjects}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "video" ? (
        <VideoForm
          studentId={studentId}
          dayDate={dayDate}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "ozet" ? (
        <OzetForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={subjects}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "tekrar" ? (
        <TekrarForm
          studentId={studentId}
          dayDate={dayDate}
          subjects={subjects}
          onFocusSubject={onFocusSubject}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
      {type === "other" ? (
        <OtherForm
          studentId={studentId}
          dayDate={dayDate}
          onAfterAdd={onAfterAdd}
        />
      ) : null}
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
  onFocusSubject,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
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
// VIDEO TİPİ
// =============================================================================

function VideoForm({
  studentId,
  dayDate,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [linkUrl, setLinkUrl] = React.useState("");
  const [notes, setNotes] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!linkUrl.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "video",
          title: notes.trim() || "Video",
          scheduled_hour: scheduledHour,
          notes: notes.trim() || null,
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
        <div className="md:col-span-7">
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
            disabled={!linkUrl.trim()}
          />
        </div>
      </div>
      <p className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground italic">
        <Info className="size-3" aria-hidden />
        Öğrenci linke tıklayarak videoyu açar; kısa açıklama konuyu netleştirir.
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
  onFocusSubject,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
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
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "ozet",
          title: `${subjectName} özet`,
          scheduled_hour: scheduledHour,
          notes: notes.trim(),
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
  onFocusSubject,
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  subjects: { id: number; name: string }[];
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
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "tekrar",
          title: `${subjectName} tekrar`,
          scheduled_hour: scheduledHour,
          notes: notes.trim(),
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
  onAfterAdd,
}: {
  studentId: number;
  dayDate: string;
  onAfterAdd: () => void;
}) {
  const create = useCreateTask(studentId);
  const [hour, setHour] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [notes, setNotes] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    const scheduledHour = hour === "" ? null : Number(hour);
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "other",
          title: title.trim(),
          scheduled_hour: scheduledHour,
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
        <div className="md:col-span-4">
          <Label>Başlık</Label>
          <Input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Görev başlığı"
          />
        </div>
        <div className="md:col-span-6">
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
          <SubmitButton pending={create.isPending} disabled={!title.trim()} />
        </div>
      </div>
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
