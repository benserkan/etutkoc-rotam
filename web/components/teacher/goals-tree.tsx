"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Bookmark,
  BookOpen,
  Bot,
  Calendar,
  CalendarRange,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleSlash,
  GitBranch,
  Info,
  Loader2,
  Plus,
  Sparkles,
  Star,
  Target,
  Trash2,
  Trophy,
  type LucideIcon,
} from "lucide-react";

import { getTeacherStudentGoals, teacherKeys } from "@/lib/api/teacher";
import {
  useAbandonGoal,
  useAchieveGoal,
  useCreateGoal,
  useDeleteGoal,
  useSeedExamGoals,
  useUpdateGoal,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  GoalKind,
  GoalNodeRow,
  GoalSubjectProgressRow,
  TeacherGoalsResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Props {
  studentId: number;
}

const KIND_ICON: Record<GoalKind, LucideIcon> = {
  exam_target: Trophy,
  subject: BookOpen,
  topic: Bookmark,
  weekly: CalendarRange,
  daily: Calendar,
  custom: Star,
};
const KIND_TONE: Record<GoalKind, string> = {
  exam_target: "text-amber-500",
  subject: "text-indigo-500",
  topic: "text-violet-500",
  weekly: "text-sky-500",
  daily: "text-emerald-500",
  custom: "text-amber-400",
};

export function GoalsTree({ studentId }: Props) {
  const q = useQuery<TeacherGoalsResponse>({
    queryKey: teacherKeys.studentGoals(studentId),
    queryFn: () => getTeacherStudentGoals(studentId),
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground py-12">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="text-sm text-rose-500">Hedef verileri yüklenemedi.</div>
    );
  }
  return <Body studentId={studentId} d={q.data} />;
}

function Body({ studentId, d }: { studentId: number; d: TeacherGoalsResponse }) {
  return (
    <div className="space-y-6 max-w-6xl">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link
            href={`/teacher/students/${studentId}`}
            className="hover:underline"
          >
            ← {d.student_name}
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <Target className="size-6 text-amber-500" aria-hidden />
          Hedef Paneli
        </h1>
        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">
          <b>Müfredat ilerlemesi</b> kitap envanterinden otomatik beslenir;{" "}
          <b>kişisel hedefler</b> elle koyduğun haftalık/günlük/özel hedeflerdir.
          Sınav netleri için ayrı bir sayfa kullan.
        </p>
      </header>

      <Card className="border-l-4 border-l-sky-500">
        <CardContent className="p-3 text-xs text-foreground/90 leading-relaxed inline-flex items-start gap-2">
          <Info
            className="size-4 text-sky-500 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <div>
            <b>Müfredat ilerlemesi:</b> test havuzu tamamlama yüzdesi — sınav
            neti tahmini değildir. Her bölüm için varsayılan hedef{" "}
            <b>5 test</b> (kitap envanteri varsa onun sayısı).
          </div>
        </CardContent>
      </Card>

      <ProgressKpis d={d} />

      {d.subjects.length > 0 ? (
        <CurriculumProgress subjects={d.subjects} />
      ) : (
        <Card className="border-dashed">
          <CardContent className="text-center py-10">
            <BookOpen
              className="size-8 mx-auto text-muted-foreground/60 mb-2"
              aria-hidden
            />
            <p className="text-sm font-medium text-foreground">
              Henüz aktif konu yok
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Kitap ataması yapıp günlük programa görev koyduğunda burası
              otomatik dolacak.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-lg font-semibold text-foreground inline-flex items-center gap-2">
            <Star className="size-5 text-amber-500" aria-hidden />
            Kişisel Hedefler
          </h2>
          <p className="text-xs text-muted-foreground -mt-1">
            Haftalık (50 test çöz), günlük (4 saat çalış) ya da serbest hedefler.
            Üstte müfredat ilerlemesi zaten otomatik; burası elle koyduğun
            hedefler için.
          </p>

          {d.roots.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="text-center py-10">
                <Star
                  className="size-8 mx-auto text-muted-foreground/60 mb-2"
                  aria-hidden
                />
                <p className="text-sm font-medium text-foreground">
                  Henüz kişisel hedef yok
                </p>
                <p className="text-xs text-muted-foreground mt-1 max-w-md mx-auto">
                  Sağdaki formla &quot;Bu hafta 50 test çöz&quot; veya &quot;Bu
                  ay deneme ortalamasını 5 yükselt&quot; gibi operasyonel
                  hedefler ekleyebilirsin.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {d.roots.map((root) => (
                <GoalNode key={root.id} node={root} depth={0} />
              ))}
            </div>
          )}
        </div>

        <aside>
          <NewGoalForm studentId={studentId} response={d} />
        </aside>
      </div>
    </div>
  );
}

function ProgressKpis({ d }: { d: TeacherGoalsResponse }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Kpi label="Aktif Ders" value={String(d.subjects.length)} />
      <Kpi label="Aktif Konu" value={String(d.topic_count)} />
      <Kpi
        label="Bitmiş Konu"
        value={String(d.finished_topic_count)}
        tone="text-emerald-500"
      />
      <Kpi
        label="Genel İlerleme"
        value={`%${d.overall_pct}`}
        tone="text-indigo-500"
      />
    </div>
  );
}

function Kpi({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <div
          className={cn(
            "text-2xl font-bold mt-1 tabular-nums",
            tone ?? "text-foreground",
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}

function CurriculumProgress({ subjects }: { subjects: GoalSubjectProgressRow[] }) {
  return (
    <div className="space-y-2">
      {subjects.map((s) => (
        <SubjectAccordion key={s.subject_id} subject={s} />
      ))}
    </div>
  );
}

function SubjectAccordion({ subject }: { subject: GoalSubjectProgressRow }) {
  const [open, setOpen] = React.useState(subject.progress_pct < 100);
  const pct = subject.progress_pct;
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-muted/30 transition rounded-md"
      >
        {open ? (
          <ChevronDown
            className="size-4 text-muted-foreground flex-shrink-0"
            aria-hidden
          />
        ) : (
          <ChevronRight
            className="size-4 text-muted-foreground flex-shrink-0"
            aria-hidden
          />
        )}
        <BookOpen
          className="size-5 text-indigo-500 flex-shrink-0"
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="font-semibold text-foreground">
              {subject.subject_name}
            </span>
            <span className={cn("text-sm font-bold tabular-nums", pctColor(pct))}>
              %{pct}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className={cn("h-full transition-all", barColor(pct))}
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="text-[11px] text-muted-foreground mt-1">
            {subject.total_completed} / {subject.total_target} test ·{" "}
            {subject.topics.length} aktif konu
          </div>
        </div>
      </button>
      {open ? (
        <div className="border-t border-border bg-muted/20 px-3 py-3 space-y-2">
          {subject.topics.map((t) => (
            <div
              key={t.section_id}
              className="rounded-md border border-border bg-card px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2 flex-wrap">
                <span className="text-sm font-medium text-foreground truncate">
                  {t.section_label}
                </span>
                <span
                  className={cn(
                    "text-xs font-semibold whitespace-nowrap tabular-nums inline-flex items-center gap-1",
                    pctColor(t.progress_pct),
                  )}
                >
                  {t.completed_tests}/{t.target_tests}
                  <span className="text-[10px] text-muted-foreground">
                    %{t.progress_pct}
                  </span>
                  {t.progress_pct >= 100 ? (
                    <CheckCircle2
                      className="size-3.5 text-emerald-500"
                      aria-hidden
                    />
                  ) : null}
                </span>
              </div>
              <div className="mt-1.5 h-1 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn("h-full transition-all", barColor(t.progress_pct))}
                  style={{ width: `${t.progress_pct}%` }}
                />
              </div>
              <div className="text-[10px] text-muted-foreground/80 mt-1">
                {t.book_name}
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}

function pctColor(pct: number): string {
  if (pct >= 80) return "text-emerald-500";
  if (pct >= 50) return "text-indigo-500";
  if (pct >= 25) return "text-amber-500";
  return "text-rose-500";
}
function barColor(pct: number): string {
  if (pct >= 100) return "bg-emerald-500";
  if (pct >= 60) return "bg-indigo-500";
  if (pct >= 30) return "bg-amber-500";
  return "bg-rose-500";
}

function GoalNode({ node, depth }: { node: GoalNodeRow; depth: number }) {
  const [open, setOpen] = React.useState(node.status === "active");
  const [editing, setEditing] = React.useState(false);

  const isLeaf = node.children.length === 0;
  const pct = node.aggregated_pct;
  const KindIcon = KIND_ICON[node.kind];
  const kindTone = KIND_TONE[node.kind];

  return (
    <Card
      className={cn(
        "transition",
        node.status === "achieved" &&
          "border-l-4 border-l-emerald-500 ring-1 ring-inset ring-emerald-500/10",
        node.status === "abandoned" && "opacity-60",
        node.status === "active" && "border-l-4 border-l-amber-500/40",
      )}
    >
      <div className="p-3 flex items-start gap-3">
        {!isLeaf ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex-shrink-0 text-muted-foreground hover:text-foreground"
            aria-label={open ? "Daralt" : "Genişlet"}
          >
            {open ? (
              <ChevronDown className="size-4" aria-hidden />
            ) : (
              <ChevronRight className="size-4" aria-hidden />
            )}
          </button>
        ) : (
          <div className="w-4" />
        )}
        <KindIcon
          className={cn("size-5 flex-shrink-0 mt-0.5", kindTone)}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-foreground">{node.title}</span>
            <span className="text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground">
              {node.kind_label}
            </span>
            {node.status === "achieved" ? (
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-500 inline-flex items-center gap-1">
                <Check className="size-3" aria-hidden />
                Tamamlandı
              </span>
            ) : null}
            {node.status === "abandoned" ? (
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-muted text-muted-foreground">
                Bırakıldı
              </span>
            ) : null}
            {node.is_auto_generated ? (
              <span
                className="text-muted-foreground inline-flex items-center"
                title="Sistem türetti"
              >
                <Bot className="size-3" aria-hidden />
              </span>
            ) : null}
          </div>
          {node.description ? (
            <p className="text-sm text-muted-foreground mt-1">
              {node.description}
            </p>
          ) : null}
          <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
            {node.target_value !== null ? (
              <span className="tabular-nums">
                <b className="text-foreground">
                  {formatNum(node.current_value ?? 0)}
                </b>{" "}
                / <b>{formatNum(node.target_value)}</b>{" "}
                {node.unit ? <span>{node.unit}</span> : null}
              </span>
            ) : null}
            {node.target_date ? (
              <span className="inline-flex items-center gap-1">
                <Calendar className="size-3" aria-hidden />
                {formatDateLong(node.target_date)}
              </span>
            ) : null}
            {node.total_count > 1 ? (
              <span className="inline-flex items-center gap-1">
                <GitBranch className="size-3" aria-hidden />
                {node.achieved_count}/{node.total_count} alt hedef tamam
              </span>
            ) : null}
          </div>
          {pct !== null ? (
            <div className="mt-2">
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className={cn("h-full transition-all", barColor(pct))}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5">
                İlerleme: <b className="text-foreground">%{pct}</b>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {node.status === "active" ? (
        <GoalActions
          node={node}
          editing={editing}
          onToggleEdit={() => setEditing((v) => !v)}
        />
      ) : null}

      {open && node.children.length > 0 ? (
        <div className="ml-6 pl-3 border-l-2 border-border pb-3 pr-3 space-y-2">
          {node.children.map((c) => (
            <GoalNode key={c.id} node={c} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </Card>
  );
}

function GoalActions({
  node,
  editing,
  onToggleEdit,
}: {
  node: GoalNodeRow;
  editing: boolean;
  onToggleEdit: () => void;
}) {
  const achieve = useAchieveGoal();
  const abandon = useAbandonGoal();
  const del = useDeleteGoal();
  const update = useUpdateGoal();

  const [currentVal, setCurrentVal] = React.useState<string>(
    node.current_value !== null ? String(node.current_value) : "",
  );

  if (editing && node.target_value !== null && node.children.length === 0) {
    return (
      <div className="border-t border-border bg-muted/20 px-3 py-2 flex items-center gap-2 text-sm flex-wrap">
        <label className="text-xs text-muted-foreground">Güncel değeri:</label>
        <input
          type="text"
          inputMode="decimal"
          value={currentVal}
          onChange={(e) => setCurrentVal(e.target.value)}
          className="px-2 py-1 border border-border rounded-md text-sm w-24 bg-background"
        />
        {node.unit ? (
          <span className="text-xs text-muted-foreground">{node.unit}</span>
        ) : null}
        <Button
          size="sm"
          onClick={() =>
            update.mutate(
              {
                goalId: node.id,
                body: {
                  current_value: currentVal === "" ? null : Number(currentVal),
                },
              },
              { onSuccess: () => onToggleEdit() },
            )
          }
          disabled={update.isPending}
        >
          Kaydet
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onToggleEdit}
          disabled={update.isPending}
        >
          Vazgeç
        </Button>
      </div>
    );
  }

  return (
    <div className="border-t border-border bg-muted/20 px-3 py-2 flex items-center gap-2 flex-wrap">
      {node.target_value !== null && node.children.length === 0 ? (
        <Button size="sm" variant="outline" onClick={onToggleEdit}>
          Güncelle
        </Button>
      ) : null}
      <Button
        size="sm"
        onClick={() => {
          if (!confirm("Bu hedefi tamamlandı olarak işaretle?")) return;
          achieve.mutate({ goalId: node.id });
        }}
        disabled={achieve.isPending}
      >
        <Check className="size-3.5" aria-hidden /> Tamamlandı
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          if (!confirm("Bu hedefi bırakıldı olarak işaretle?")) return;
          abandon.mutate({ goalId: node.id });
        }}
        disabled={abandon.isPending}
      >
        <CircleSlash className="size-3.5" aria-hidden /> Bırak
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => {
          if (
            !confirm(
              "Bu hedefi tamamen silmek istiyor musunuz? Alt hedefler de silinir.",
            )
          )
            return;
          del.mutate({ goalId: node.id });
        }}
        disabled={del.isPending}
        className="text-rose-500 hover:text-rose-400"
      >
        <Trash2 className="size-3.5" aria-hidden /> Sil
      </Button>
    </div>
  );
}

function NewGoalForm({
  studentId,
  response,
}: {
  studentId: number;
  response: TeacherGoalsResponse;
}) {
  const [kind, setKind] = React.useState<GoalKind>("custom");
  const [parentId, setParentId] = React.useState<string>("");
  const [title, setTitle] = React.useState("");
  const [desc, setDesc] = React.useState("");
  const [targetValue, setTargetValue] = React.useState("");
  const [currentValue, setCurrentValue] = React.useState("");
  const [unit, setUnit] = React.useState("");
  const [targetDate, setTargetDate] = React.useState("");

  const create = useCreateGoal(studentId);
  const seedExam = useSeedExamGoals(studentId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    create.mutate(
      {
        body: {
          title,
          kind,
          parent_id: parentId === "" ? null : Number(parentId),
          description: desc || null,
          target_value: targetValue === "" ? null : Number(targetValue),
          current_value: currentValue === "" ? null : Number(currentValue),
          unit: unit || null,
          target_date: targetDate || null,
        },
      },
      {
        onSuccess: () => {
          setTitle("");
          setDesc("");
          setTargetValue("");
          setCurrentValue("");
          setUnit("");
          setTargetDate("");
        },
      },
    );
  }

  const parentOptions = React.useMemo(
    () => flattenGoals(response.roots, 0),
    [response.roots],
  );

  return (
    <Card className="lg:sticky lg:top-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Plus className="size-4" aria-hidden /> Yeni Hedef Ekle
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-3 text-sm">
          <Field label="Hedef türü">
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value as GoalKind)}
              className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
            >
              {response.kind_options.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Üst hedef (opsiyonel)">
            <select
              value={parentId}
              onChange={(e) => setParentId(e.target.value)}
              className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
            >
              <option value="">— Kök hedef —</option>
              {parentOptions.map((o) => (
                <option key={o.id} value={o.id}>
                  {"— ".repeat(o.depth)}
                  {o.title}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Başlık" required>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={200}
              placeholder="Ör. Matematik 36/40 net"
              className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
            />
          </Field>
          <Field label="Açıklama">
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
              maxLength={500}
              className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Hedef">
              <input
                type="text"
                inputMode="decimal"
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                placeholder="36"
                className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
              />
            </Field>
            <Field label="Şu an">
              <input
                type="text"
                inputMode="decimal"
                value={currentValue}
                onChange={(e) => setCurrentValue(e.target.value)}
                placeholder="0"
                className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
              />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Field label="Birim">
              <input
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                maxLength={20}
                placeholder="net / % / saat"
                className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
              />
            </Field>
            <Field label="Hedef tarih">
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="w-full px-2 py-1.5 border border-border rounded-md text-sm bg-background"
              />
            </Field>
          </div>
          <Button type="submit" disabled={create.isPending} className="w-full">
            {create.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Hedefi Oluştur
          </Button>
        </form>

        <div className="mt-4 pt-3 border-t border-border">
          <p className="text-[11px] text-muted-foreground mb-2">
            Öğrencinin sınav hedefinden otomatik bir ders ağacı kurmak istersen:
          </p>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            size="sm"
            onClick={() => seedExam.mutate({})}
            disabled={seedExam.isPending}
          >
            {seedExam.isPending ? (
              <Loader2 className="size-3 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="size-3.5" aria-hidden />
            )}
            Sınav hedefinden otomatik ağaç türet
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-foreground mb-1">
        {label}
        {required ? <span className="text-rose-500 ml-0.5">*</span> : null}
      </label>
      {children}
    </div>
  );
}

interface FlatNode {
  id: number;
  title: string;
  depth: number;
}

function flattenGoals(roots: GoalNodeRow[], depth: number): FlatNode[] {
  const out: FlatNode[] = [];
  for (const r of roots) {
    out.push({ id: r.id, title: r.title, depth });
    if (r.children.length > 0) {
      out.push(...flattenGoals(r.children, depth + 1));
    }
  }
  return out;
}

function formatNum(n: number): string {
  if (Number.isInteger(n)) return String(n);
  return String(Math.round(n * 100) / 100);
}

function formatDateLong(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return iso;
  const months = [
    "Oca",
    "Şub",
    "Mar",
    "Nis",
    "May",
    "Haz",
    "Tem",
    "Ağu",
    "Eyl",
    "Eki",
    "Kas",
    "Ara",
  ];
  return `${String(d.getUTCDate()).padStart(2, "0")} ${months[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}
