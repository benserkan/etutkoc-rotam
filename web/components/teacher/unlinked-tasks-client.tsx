"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Info, Link2, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  getSubjectTopics,
  getUnlinkedTestTasks,
  taskTopicKeys,
  topicOptionLabel,
  useConvertUnlinkedTasks,
  type TopicOption,
  type UnlinkedTask,
} from "@/lib/api/task-topic-link";

interface RowState {
  topicId: number | null;
  count: number;
  checked: boolean;
}

function defaultRow(t: UnlinkedTask): RowState {
  const s = t.suggestion;
  const topicId = s.confident && s.topic ? s.topic.topic_id : null;
  return { topicId, count: s.test_count ?? 2, checked: topicId !== null };
}

const DATE_FMT = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", weekday: "short" });

export function UnlinkedTasksClient() {
  const [studentFilter, setStudentFilter] = React.useState<number | null>(null);
  const q = useQuery({
    queryKey: taskTopicKeys.unlinked(null),
    queryFn: () => getUnlinkedTestTasks(null),
  });
  const convert = useConvertUnlinkedTasks();
  const [rows, setRows] = React.useState<Record<number, RowState>>({});

  const items = React.useMemo(() => q.data?.items ?? [], [q.data]);
  const students = React.useMemo(() => {
    const m = new Map<number, string>();
    for (const it of items) m.set(it.student_id, it.student_name);
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1], "tr"));
  }, [items]);
  const visible = studentFilter === null ? items : items.filter((i) => i.student_id === studentFilter);

  const rowOf = (t: UnlinkedTask) => rows[t.task_id] ?? defaultRow(t);
  const patch = (t: UnlinkedTask, p: Partial<RowState>) =>
    setRows((prev) => ({ ...prev, [t.task_id]: { ...(prev[t.task_id] ?? defaultRow(t)), ...p } }));

  const selected = visible.filter((t) => {
    const r = rowOf(t);
    return r.checked && r.topicId !== null && r.count >= 1;
  });

  const groups = React.useMemo(() => {
    const m = new Map<number, UnlinkedTask[]>();
    for (const t of visible) m.set(t.student_id, [...(m.get(t.student_id) ?? []), t]);
    return [...m.entries()];
  }, [visible]);

  function submit() {
    convert.mutate({
      items: selected.map((t) => {
        const r = rowOf(t);
        return { task_id: t.task_id, topic_id: r.topicId as number, planned_count: r.count };
      }),
    });
  }

  return (
    <div className="space-y-5 pb-24">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display">Konusuz test görevleri</h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Bu görevlere test sayısı yazılmış (ör. &ldquo;2 test&rdquo;) ama &ldquo;Diğer&rdquo; etkinliği
          olarak verildikleri için bir konuya ya da kaynağa bağlı değiller. Bu yüzden içlerindeki
          testler müfredat ilerlemesine, konu performansına, analitiğe ve kurum tablolarına
          giremiyor. Konuyu onayladığın görev &ldquo;konuya bağlı test&rdquo; olur ve tüm tablolara
          geriye dönük yansır. Öğrencinin tamamladığı görevler çözülmüş test sayılır.
        </p>
      </header>

      {q.isLoading ? (
        <p className="inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Görevler taranıyor…
        </p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="p-6 flex items-center gap-3 text-sm">
            <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
            Konusuz test görevi yok — tüm test görevlerin bir konuya ya da kaynağa bağlı.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="rounded-md bg-muted px-2.5 py-1">
              <strong>{q.data?.total}</strong> görev · <strong>{q.data?.students}</strong> öğrenci ·{" "}
              <strong>{q.data?.completed}</strong> tamamlanmış
            </span>
            <label className="inline-flex items-center gap-2">
              <span className="text-muted-foreground">Öğrenci</span>
              <select
                aria-label="Öğrenci filtresi"
                value={studentFilter === null ? "" : String(studentFilter)}
                onChange={(e) => setStudentFilter(e.target.value === "" ? null : Number(e.target.value))}
                className="rounded-md border border-input bg-background px-2 py-1 text-sm"
              >
                <option value="">Tümü</option>
                {students.map(([id, name]) => (
                  <option key={id} value={id}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="inline-flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="size-3.5 shrink-0 mt-0.5" aria-hidden />
            Sistemin emin olduğu konular işaretli gelir. &ldquo;Tahmin&rdquo; ya da &ldquo;seç&rdquo;
            yazan satırlarda konuyu kontrol et; tema/ünite yazılmışsa alt konusunu seç. Konu listesinde
            yoksa &ldquo;Tüm konular&rdquo;a bas.
          </p>

          {groups.map(([sid, list]) => (
            <Card key={sid}>
              <CardContent className="p-0">
                <div className="flex items-center justify-between px-4 py-2.5 border-b border-border">
                  <Link href={`/teacher/students/${sid}`} className="font-medium hover:underline">
                    {list[0].student_name}
                  </Link>
                  <span className="text-xs text-muted-foreground">{list.length} görev</span>
                </div>
                <ul className="divide-y divide-border">
                  {list.map((t) => (
                    <UnlinkedRow key={t.task_id} task={t} row={rowOf(t)} onPatch={(p) => patch(t, p)} />
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}

          <div className="fixed bottom-0 inset-x-0 z-30 border-t border-border bg-background/95 backdrop-blur px-4 py-3">
            <div className="mx-auto max-w-5xl flex flex-wrap items-center gap-3 pr-40">
              <span className="text-sm">
                <strong>{selected.length}</strong> görev seçili
              </span>
              <Button
                type="button"
                disabled={selected.length === 0 || convert.isPending}
                onClick={submit}
                className="bg-cyan-700 text-white hover:bg-cyan-800"
              >
                {convert.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Link2 className="size-4" aria-hidden />}
                Seçilenleri konuya bağla ({selected.length})
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function UnlinkedRow({
  task,
  row,
  onPatch,
}: {
  task: UnlinkedTask;
  row: RowState;
  onPatch: (p: Partial<RowState>) => void;
}) {
  const s = task.suggestion;
  const [showAll, setShowAll] = React.useState(false);
  const allQ = useQuery({
    queryKey: taskTopicKeys.subjectTopics(task.student_id, task.subject_id ?? 0),
    queryFn: () => getSubjectTopics(task.student_id, task.subject_id ?? 0),
    enabled: showAll && task.subject_id !== null,
    staleTime: 5 * 60_000,
  });
  const base: TopicOption[] = [...(s.topic ? [s.topic] : []), ...s.options];
  const extra = showAll ? allQ.data?.topics ?? [] : [];
  const seen = new Set<number>();
  const options = [...base, ...extra].filter((o) => (seen.has(o.topic_id) ? false : (seen.add(o.topic_id), true)));
  const noSubject = task.subject_id === null;
  const done = task.status === "completed";
  const badge = s.confident && row.topicId === s.topic?.topic_id
    ? { text: "kesin", cls: "bg-emerald-700 text-white" }
    : s.topic
      ? { text: "tahmin", cls: "bg-amber-600 text-white" }
      : { text: "seç", cls: "bg-slate-600 text-white" };

  return (
    <li className={cn("px-4 py-3 grid grid-cols-[minmax(0,1fr)] gap-2", noSubject && "opacity-70")}>
      <div className="flex items-start gap-3">
        <input
          type="checkbox"
          aria-label={`${task.title} görevini seç`}
          className="mt-1 size-4"
          checked={row.checked && row.topicId !== null}
          disabled={row.topicId === null || noSubject}
          onChange={(e) => onPatch({ checked: e.target.checked })}
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium break-words">{task.title}</p>
          <p className="text-xs text-muted-foreground break-words">
            {DATE_FMT.format(new Date(task.date + "T12:00:00"))}
            {task.notes ? ` · not: ${task.notes}` : ""}
            {" · "}
            <span className={done ? "text-emerald-700 dark:text-emerald-300 font-medium" : ""}>
              {done ? "tamamlandı" : task.is_draft ? "taslak" : "bekliyor"}
            </span>
          </p>
        </div>
        <span className={cn("shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase", badge.cls)}>
          {badge.text}
        </span>
      </div>
      {noSubject ? (
        <p className="pl-7 text-xs text-muted-foreground">
          Başlıktaki ders anlaşılamadı — bu görevi haftalık programdan düzenle.
        </p>
      ) : (
        <div className="pl-7 flex flex-wrap items-center gap-2 min-w-0">
          <select
            aria-label="Konu"
            value={row.topicId === null ? "" : String(row.topicId)}
            onChange={(e) => {
              const v = e.target.value === "" ? null : Number(e.target.value);
              onPatch({ topicId: v, checked: v !== null });
            }}
            className="w-full min-w-0 sm:w-auto sm:flex-1 rounded-md border border-input bg-background px-2 py-1 text-sm"
          >
            <option value="">— konu seç —</option>
            {options.map((o) => (
              <option key={o.topic_id} value={o.topic_id}>
                {topicOptionLabel(o)}
                {o.parent_name ? ` (${o.parent_name})` : ""}
              </option>
            ))}
          </select>
          {!showAll ? (
            <button type="button" onClick={() => setShowAll(true)} className="text-xs underline underline-offset-2">
              Tüm konular
            </button>
          ) : allQ.isLoading ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : null}
          <label className="inline-flex items-center gap-1.5 text-xs">
            <input
              type="number"
              min={1}
              max={30}
              aria-label="Test sayısı"
              value={row.count}
              onChange={(e) => onPatch({ count: Math.max(1, Math.min(30, Number(e.target.value) || 1)) })}
              className="w-14 rounded-md border border-input bg-background px-1.5 py-1 text-sm tabular-nums"
            />
            test
          </label>
          {s.reason ? <span className="basis-full text-[11px] text-muted-foreground">{s.reason}</span> : null}
        </div>
      )}
    </li>
  );
}
