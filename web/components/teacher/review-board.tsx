"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  Brain,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  Loader2,
  PlayCircle,
  Plus,
  RotateCcw,
  Target,
  Trash2,
  Zap,
} from "lucide-react";

import {
  getTeacherStudentReview,
  getTeacherStudentReviewCandidates,
  teacherKeys,
} from "@/lib/api/teacher";
import {
  useDeleteReviewCards,
  useReopenReviewCards,
  useReviewSeedSubject,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  ReviewCandidateRow,
  ReviewCandidatesResponse,
  ReviewState,
  ReviewSubjectOption,
  StruggleCardRow,
  TeacherReviewResponse,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

interface Props {
  studentId: number;
}

export function ReviewBoard({ studentId }: Props) {
  const q = useQuery<TeacherReviewResponse>({
    queryKey: teacherKeys.studentReview(studentId),
    queryFn: () => getTeacherStudentReview(studentId),
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
      <div className="text-sm text-rose-500">Tekrar verileri yüklenemedi.</div>
    );
  }
  return <Body studentId={studentId} d={q.data} />;
}

function Body({ studentId, d }: { studentId: number; d: TeacherReviewResponse }) {
  return (
    <div className="space-y-6 max-w-6xl">
      <header className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link
              href={`/teacher/students/${studentId}`}
              className="hover:underline"
            >
              ← {d.student_name}
            </Link>
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
            <Brain className="size-6 text-emerald-500" aria-hidden />
            Tekrar Kartları
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {d.grade_label}
            {d.exam_label ? ` · ${d.exam_label}` : ""} için aralıklı tekrar (FSRS)
            sistemi.
          </p>
          <DemoHint contextKey="review" role="teacher" className="mt-1.5" />
        </div>
        <Button asChild variant="ghost" size="sm">
          <Link href="/teacher/review">
            Tüm öğrencilerin tekrar yükü
            <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </Button>
      </header>

      <VideoGuideScaffold />

      <BreakdownStrip d={d} />

      {d.struggle_cards.length > 0 ? (
        <StrugglePanel studentId={studentId} cards={d.struggle_cards} />
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 items-start">
        <SeedForm
          studentId={studentId}
          subjects={d.subjects}
          newPerDay={d.breakdown.new_per_day ?? 10}
        />
        <CardListPanel studentId={studentId} d={d} />
      </div>
    </div>
  );
}

/**
 * Video kılavuz scaffold — Jinja'daki 9-sahne TTS slideshow yapısının Next.js
 * iskeleti. Şu an placeholder; gerçek sesli sahne dizisi ileride buraya inşa
 * edilecek (yapı korunmuş).
 */
function VideoGuideScaffold() {
  const [open, setOpen] = React.useState(false);
  return (
    <Card className="border-l-4 border-l-amber-500">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-muted/40 transition rounded-t-md"
      >
        <PlayCircle className="size-5 text-amber-500" aria-hidden />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-foreground">
            Video Kılavuz — Aralıklı Tekrar: Ne işe yarar, nasıl kullanılır?
          </div>
          <div className="text-xs text-muted-foreground">
            3 bölüm · 9 sahne · ileride interaktif tur eklenecek
          </div>
        </div>
        {open ? (
          <ChevronUp className="size-4 text-muted-foreground" aria-hidden />
        ) : (
          <ChevronDown className="size-4 text-muted-foreground" aria-hidden />
        )}
      </button>
      {open ? (
        <CardContent className="pt-0 pb-4 space-y-3 text-sm">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              1. Bölüm — Ne işe yarar?
            </div>
            <p className="text-foreground/90 leading-relaxed">
              Yeni öğrenilen bir konu, tekrar edilmediği takdirde 1 günde
              %50&apos;den fazlası, 1 haftada %80&apos;den fazlası unutulur.
              Aralıklı tekrar bu eğriyi hesaba katarak konuyu{" "}
              <b>tam unutmadan</b> tekrar gündeme getirir. ETÜTKOÇ Rotam bunu
              FSRS algoritmasıyla otomatik yapar.
            </p>
            <ul className="mt-2 text-xs text-muted-foreground space-y-0.5 list-disc list-inside">
              <li>Kalıcı bilgi — sınava kadar taze kalır</li>
              <li>
                Zorlanılan konular ders programı önerisine otomatik beslenir
              </li>
              <li>
                Az manuel iş — sistem ne zaman neyi göstereceğini kendisi planlar
              </li>
            </ul>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              2. Bölüm — Nasıl kullanılır?
            </div>
            <ol className="text-foreground/90 leading-relaxed space-y-1 list-decimal list-inside text-sm">
              <li>
                Aşağıdaki formdan bir ders seç; öğrencinin çalıştığı konular
                işaretli gelir.
              </li>
              <li>
                İstediğin konuları işaretleyip ekle. Öğrencinin önüne günde en
                fazla 10 yeni kart gelir, gerisi sonraki günlere kalır.
              </li>
              <li>
                Üstteki sayım kartlarından (Bugün/Yeni/Öğreniyor/Pekiştirme)
                öğrencinin yükünü oku.
              </li>
            </ol>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
              3. Bölüm — Sonuçta ne olur?
            </div>
            <p className="text-foreground/90 leading-relaxed text-sm">
              Öğrenci kartları Hatırlamadım / Zor / İyi / Kolay olarak puanlar.
              &quot;Hatırlamadım&quot; denen konu bir hafta sonra yeniden gelir (o hafta
              çalışılsın diye); &quot;İyi&quot; denen konu en erken bir hafta sonra.
              Üst üste aralıklı &quot;İyi&quot;lerle kart <b>Kalıcı</b> olur ve kuyruktan
              çıkar. Sistem zorlanılan konuları üstteki <b>Müdahale Önerileri</b> panelinde
              0-100 skorla size getirir; aynı veriler haftalık ders programı
              önerilerine de otomatik beslenir.
            </p>
          </div>
          <p className="text-[11px] text-muted-foreground italic">
            Bu bölümün interaktif sesli versiyonu ileride eklenecek; yapı yer
            tutucu.
          </p>
        </CardContent>
      ) : null}
    </Card>
  );
}

function BreakdownStrip({ d }: { d: TeacherReviewResponse }) {
  const items: { label: string; value: number; tone: string }[] = [
    { label: "Bugün vade", value: d.breakdown.due_now, tone: "text-rose-500" },
    { label: "Yeni", value: d.breakdown.new, tone: "text-foreground" },
    { label: "Öğreniyor", value: d.breakdown.learning, tone: "text-amber-500" },
    {
      label: "Pekiştirme",
      value: d.breakdown.review,
      tone: "text-emerald-500",
    },
    { label: "Kalıcı", value: d.breakdown.mastered ?? 0, tone: "text-cyan-600" },
    { label: "Toplam", value: d.breakdown.total, tone: "text-foreground" },
  ];
  return (
    <div className="space-y-2">
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {items.map((it) => (
        <Card key={it.label}>
          <CardContent className="p-4">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
              {it.label}
            </div>
            <div className={cn("text-2xl font-bold mt-1 tabular-nums", it.tone)}>
              {it.value}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
    {(d.breakdown.new_waiting ?? 0) > 0 ? (
      <p className="text-xs text-muted-foreground">
        &quot;Bugün vade&quot; günlük sınırı da hesaba katar: {d.breakdown.new_waiting} yeni
        kart sonraki günlerde sırayla gelecek (günde en fazla {d.breakdown.new_per_day}).
      </p>
    ) : null}
    </div>
  );
}

function StrugglePanel({
  studentId,
  cards,
}: {
  studentId: number;
  cards: StruggleCardRow[];
}) {
  return (
    <Card className="border-l-4 border-l-amber-500 ring-1 ring-inset ring-amber-500/10">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2 flex-wrap">
          <Target className="size-5 text-amber-500" aria-hidden />
          Müdahale Önerileri — Öğrencinin Zorlandığı Konular
          <span className="ml-auto text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-700">
            {cards.length} konu
          </span>
        </CardTitle>
        <p className="text-xs text-muted-foreground mt-0.5">
          FSRS algoritmasının &quot;zor&quot; sınıflandırdığı + öğrencinin unutup
          tekrar geldiği konular. Yerleştirme kararı sizde.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {cards.map((c) => (
            <StruggleCard key={c.card_id} studentId={studentId} card={c} />
          ))}
        </div>
        <div className="mt-4 pt-3 border-t border-border text-xs text-muted-foreground inline-flex items-start gap-2">
          <Lightbulb
            className="size-3.5 text-amber-500 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <span>
            Bu konular AI öneri motoruna da otomatik beslenir — haftalık programda
            &quot;Tekrar kartında zorlanılan konu&quot; rozetiyle önceliklendirilir.
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

function StruggleCard({
  studentId,
  card,
}: {
  studentId: number;
  card: StruggleCardRow;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const scoreColor =
    card.score >= 50
      ? "text-rose-500"
      : card.score >= 30
        ? "text-orange-500"
        : "text-amber-500";
  return (
    <div className="rounded-lg border border-border bg-background/40 p-3 hover:bg-background/60 transition">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-1.5">
            <span className="text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
              {card.subject_name}
            </span>
            <StateLabel state={card.state} label={card.state_label} />
            {card.lapse_count >= 2 ? (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-700 inline-flex items-center gap-1">
                <AlertTriangle className="size-3" aria-hidden />
                {card.lapse_count}× unutma
              </span>
            ) : null}
          </div>
          <div className="font-semibold text-foreground text-sm leading-snug">
            {card.topic_name}
          </div>
        </div>
        <div className="flex-shrink-0 text-right">
          <div className="text-[10px] uppercase tracking-wider font-bold text-muted-foreground">
            Zorlanma
          </div>
          <div className={cn("font-bold text-lg leading-none mt-0.5", scoreColor)}>
            {Math.round(card.score)}
            <span className="text-xs text-muted-foreground/70 ml-0.5">/100</span>
          </div>
        </div>
      </div>

      <div className="h-1.5 bg-muted rounded-full overflow-hidden mt-2.5 mb-2.5">
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${Math.min(100, Math.round(card.score))}%`,
            background:
              "linear-gradient(90deg, rgb(252 211 77) 0%, rgb(249 115 22) 50%, rgb(220 38 38) 100%)",
          }}
        />
      </div>

      <div className="flex flex-wrap gap-1 mb-2">
        {card.reasons.map((r) => (
          <span
            key={r}
            className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-700 ring-1 ring-inset ring-amber-500/20"
          >
            {r}
          </span>
        ))}
      </div>

      {card.sections.length > 0 ? (
        <>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-xs font-semibold text-amber-500 hover:text-amber-400 inline-flex items-center gap-1"
          >
            <Zap className="size-3" aria-hidden />
            Hızlı görev oluştur ({card.sections.length} bölüm uygun)
            {expanded ? (
              <ChevronUp className="size-3" aria-hidden />
            ) : (
              <ChevronDown className="size-3" aria-hidden />
            )}
          </button>
          {expanded ? (
            <ul className="mt-2 space-y-1.5">
              {card.sections.map((s) => (
                <li
                  key={s.id}
                  className="flex items-center justify-between gap-2 text-[11px]"
                >
                  <span className="text-foreground/80 truncate flex-1 inline-flex items-center gap-1.5">
                    <BookOpen
                      className="size-3 text-muted-foreground flex-shrink-0"
                      aria-hidden
                    />
                    {s.book_name} · {s.label}
                  </span>
                  <Button asChild size="sm" variant="outline">
                    <Link href={`/teacher/students/${studentId}/week`}>
                      Programa git
                      <ArrowRight className="size-3" aria-hidden />
                    </Link>
                  </Button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <p className="text-[11px] text-muted-foreground italic">
          Bu konuyu içeren atanmış kitap yok. Önce kitap atayın.
        </p>
      )}
    </div>
  );
}

function SeedForm({
  studentId,
  subjects,
  newPerDay,
}: {
  studentId: number;
  subjects: ReviewSubjectOption[];
  newPerDay: number;
}) {
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  // Koçun seçimi; null = henüz dokunulmadı → önerilenler varsayılan.
  const [pick, setPick] = React.useState<{ subjectId: number; ids: Set<number> } | null>(null);
  const mut = useReviewSeedSubject(studentId);

  const cq = useQuery<ReviewCandidatesResponse>({
    queryKey: teacherKeys.studentReviewCandidates(studentId, Number(subjectId || 0)),
    queryFn: () => getTeacherStudentReviewCandidates(studentId, Number(subjectId)),
    enabled: subjectId !== "",
    staleTime: 15_000,
  });
  const topics = React.useMemo(
    () => (subjectId !== "" && cq.data ? cq.data.topics : []),
    [subjectId, cq.data],
  );
  const addable = topics.filter((t) => t.card_id === null);
  const defaults = React.useMemo(
    () => new Set(topics.filter((t) => t.recommended && t.card_id === null).map((t) => t.topic_id)),
    [topics],
  );
  const selected = pick && pick.subjectId === subjectId ? pick.ids : defaults;

  function setSel(next: Set<number>) {
    if (subjectId === "") return;
    setPick({ subjectId, ids: next });
  }
  function toggle(id: number) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSel(next);
  }

  function submit() {
    if (subjectId === "" || selected.size === 0) return;
    mut.mutate(
      { body: { subject_id: subjectId, topic_ids: [...selected] } },
      { onSuccess: () => setPick(null) },
    );
  }

  // Sınıfa göre grupla (öğrencinin kendi sınıfı önce)
  const ownGrade = cq.data?.student_grade ?? null;
  const groups = React.useMemo(() => {
    const m = new Map<string, ReviewCandidateRow[]>();
    for (const t of topics) {
      const k = t.grade_level == null ? "Sınav konuları" : `${t.grade_level}. sınıf`;
      const arr = m.get(k) ?? [];
      arr.push(t);
      m.set(k, arr);
    }
    const own = ownGrade != null ? `${ownGrade}. sınıf` : null;
    return [...m.entries()].sort((a, b) => {
      if (a[0] === own) return -1;
      if (b[0] === own) return 1;
      return b[0].localeCompare(a[0], "tr", { numeric: true });
    });
  }, [topics, ownGrade]);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Plus className="size-4" aria-hidden /> Konuları kart olarak ekle
        </CardTitle>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Tekrar kartı <b>öğrenilmiş</b> bir konunun unutulmaması içindir. Öğrencinin
          çalıştığı, denemede yanlış yaptığı, arşivde açık yanlışı olan ya da senin
          kapattığın konular işaretli gelir; hiç görmediği konuyu eklemen gerekmez.
          Öğrencinin önüne günde en fazla {newPerDay} yeni kart gelir.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <label className="block text-sm text-foreground mb-1.5" htmlFor="review-subject">
            Ders
          </label>
          <select
            id="review-subject"
            value={subjectId}
            onChange={(e) => {
              setSubjectId(e.target.value === "" ? "" : Number(e.target.value));
              setPick(null);
            }}
            className="w-full sm:w-80 px-3 py-2 border border-border rounded-md text-sm bg-background"
          >
            <option value="">— Ders seçin —</option>
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {subjects.length === 0 ? (
            <p className="text-[11px] text-muted-foreground mt-1 italic">
              Öğrencinin sınıf seviyesine uygun ders bulunamadı.
            </p>
          ) : null}
        </div>

        {subjectId === "" ? null : cq.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Konular yükleniyor…
          </div>
        ) : topics.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">Bu derste konu bulunamadı.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Button type="button" size="sm" variant="outline" onClick={() => setSel(new Set(defaults))}>
                Önerilenleri seç ({defaults.size})
              </Button>
              <Button
                type="button" size="sm" variant="outline"
                onClick={() => setSel(new Set(addable.map((t) => t.topic_id)))}
              >
                Tümünü seç ({addable.length})
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setSel(new Set())}>
                Temizle
              </Button>
            </div>
            <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1" data-testid="review-candidates">
              {groups.map(([label, rows]) => (
                <div key={label}>
                  <div className="sticky top-0 z-10 bg-card py-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    {label}
                    {ownGrade != null && label === `${ownGrade}. sınıf` ? " · kendi sınıfı" : ""}
                  </div>
                  <ul className="space-y-1">
                    {rows.map((t) => {
                      const has = t.card_id !== null;
                      return (
                        <li key={t.topic_id}>
                          <label
                            className={cn(
                              "flex items-start gap-2.5 rounded-md border border-border px-2.5 py-2 text-sm",
                              has ? "opacity-60" : "cursor-pointer hover:bg-muted/40",
                            )}
                          >
                            <input
                              type="checkbox"
                              className="mt-0.5 size-4"
                              disabled={has}
                              checked={has || selected.has(t.topic_id)}
                              onChange={() => toggle(t.topic_id)}
                              aria-label={t.name}
                            />
                            <span className="flex-1 min-w-0">
                              <span className="font-medium text-foreground break-words">{t.name}</span>
                              {t.unit_name ? (
                                <span className="block text-[11px] text-muted-foreground">{t.unit_name}</span>
                              ) : null}
                              <span className="mt-1 flex flex-wrap gap-1">
                                {has ? (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-slate-700 text-white">
                                    kartı var
                                  </span>
                                ) : null}
                                {t.reasons.map((r) => (
                                  <span
                                    key={r}
                                    className="text-[10px] px-1.5 py-0.5 rounded-md bg-emerald-700 text-white"
                                  >
                                    {r}
                                  </span>
                                ))}
                                {!has && t.reasons.length === 0 ? (
                                  <span className="text-[10px] text-muted-foreground">
                                    henüz çalışma kaydı yok
                                  </span>
                                ) : null}
                              </span>
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
              <p className="text-xs text-muted-foreground">
                {selected.size} konu seçili
                {selected.size > newPerDay
                  ? ` · öğrenci bunları ${Math.ceil(selected.size / newPerDay)} güne yayılmış görecek`
                  : ""}
              </p>
              <Button
                type="button"
                onClick={submit}
                disabled={mut.isPending || selected.size === 0}
                className="bg-cyan-700 text-white hover:bg-cyan-800"
              >
                {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                {selected.size} konuyu kart olarak ekle
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function CardListPanel({ studentId, d }: { studentId: number; d: TeacherReviewResponse }) {
  const [subjectFilter, setSubjectFilter] = React.useState<number | "">("");
  const [sel, setSel] = React.useState<Set<number>>(new Set());
  const [confirming, setConfirming] = React.useState(false);
  const del = useDeleteReviewCards(studentId);
  const reopen = useReopenReviewCards(studentId);

  const subjectsInCards = React.useMemo(() => {
    const m = new Map<number, string>();
    for (const c of d.cards) if (c.subject_id != null) m.set(c.subject_id, c.subject_name ?? "—");
    return [...m.entries()];
  }, [d.cards]);
  const visible = d.cards.filter((c) => subjectFilter === "" || c.subject_id === subjectFilter);
  const visibleIds = visible.map((c) => c.id);
  const selVisible = visibleIds.filter((id) => sel.has(id));
  const allSelected = visible.length > 0 && selVisible.length === visible.length;

  function toggle(id: number) {
    const next = new Set(sel);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSel(next);
    setConfirming(false);
  }

  function doDelete() {
    if (!confirming) {
      setConfirming(true);
      return;
    }
    del.mutate(
      { cardIds: selVisible },
      { onSuccess: () => { setSel(new Set()); setConfirming(false); } },
    );
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold flex flex-wrap items-center gap-2">
          Kartlar ({d.cards.length})
          {subjectsInCards.length > 1 ? (
            <select
              aria-label="Kartları derse göre süz"
              value={subjectFilter}
              onChange={(e) => {
                setSubjectFilter(e.target.value === "" ? "" : Number(e.target.value));
                setSel(new Set());
                setConfirming(false);
              }}
              className="ml-auto text-sm font-normal px-2 py-1 border border-border rounded-md bg-background"
            >
              <option value="">Tüm dersler</option>
              {subjectsInCards.map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {d.cards.length === 0 ? (
          <div className="text-center text-sm text-muted-foreground py-10 italic">
            Henüz tekrar kartı yok. Yukarıdaki formdan konu ekleyin.
          </div>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-2 mb-2 text-xs">
              <label className="inline-flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  className="size-4"
                  checked={allSelected}
                  onChange={() => {
                    setSel(allSelected ? new Set() : new Set(visibleIds));
                    setConfirming(false);
                  }}
                  aria-label="Görünen kartların tümünü seç"
                />
                Tümünü seç
              </label>
              {selVisible.length > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  onClick={doDelete}
                  disabled={del.isPending}
                  className={confirming ? "bg-rose-700 text-white hover:bg-rose-800" : "bg-slate-700 text-white hover:bg-slate-800"}
                >
                  {del.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Trash2 className="size-3.5" aria-hidden />}
                  {confirming
                    ? `Eminim, ${selVisible.length} kartı sil`
                    : `Seçilenleri sil (${selVisible.length})`}
                </Button>
              ) : null}
              {confirming ? (
                <span className="text-muted-foreground">
                  Kartlar tekrar geçmişiyle birlikte silinir; konuyu sonra yeniden ekleyebilirsin.
                </span>
              ) : null}
            </div>
            <div className="space-y-2 max-h-[520px] overflow-y-auto pr-1">
              {visible.map((c) => (
                <div
                  key={c.id}
                  className="border border-border rounded-lg p-3 hover:bg-muted/30 transition flex items-start gap-3"
                >
                  <input
                    type="checkbox"
                    className="mt-1 size-4"
                    checked={sel.has(c.id)}
                    onChange={() => toggle(c.id)}
                    aria-label={`${c.topic_name} kartını seç`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <StateLabel state={c.state} label={c.state_label} />
                      <span className="text-xs text-muted-foreground">{c.subject_name ?? "—"}</span>
                    </div>
                    <div className="text-sm font-medium text-foreground break-words mt-1">
                      {c.topic_name}
                    </div>
                  </div>
                  <div className="text-right text-xs text-muted-foreground flex-shrink-0">
                    {c.state === "mastered" ? (
                      <Button
                        type="button" size="sm" variant="outline"
                        disabled={reopen.isPending}
                        onClick={() => reopen.mutate({ cardIds: [c.id] })}
                      >
                        <RotateCcw className="size-3.5" aria-hidden /> Yeniden aç
                      </Button>
                    ) : c.due_at ? (
                      <>Sıradaki tekrar: {formatShortDate(c.due_at)}</>
                    ) : (
                      "Henüz çalışılmadı"
                    )}
                    <div className="mt-0.5 tabular-nums">
                      {c.review_count} tekrar
                      {c.lapse_count > 0 ? (
                        <>
                          {" · "}
                          <span className="text-rose-500">{c.lapse_count} unutma</span>
                        </>
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

const STATE_PILL: Record<ReviewState, string> = {
  new: "bg-muted text-foreground/80 ring-1 ring-inset ring-border",
  learning: "bg-amber-500/10 text-amber-700 ring-1 ring-inset ring-amber-500/20",
  relearning: "bg-rose-500/10 text-rose-700 ring-1 ring-inset ring-rose-500/20",
  review:
    "bg-emerald-500/10 text-emerald-700 ring-1 ring-inset ring-emerald-500/20",
  mastered: "bg-cyan-700 text-white",
};

function StateLabel({ state, label }: { state: ReviewState; label: string }) {
  return (
    <span
      className={cn(
        "text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-md",
        STATE_PILL[state],
      )}
    >
      {label}
    </span>
  );
}

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
}
