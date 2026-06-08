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
  Target,
  Zap,
} from "lucide-react";

import { getTeacherStudentReview, teacherKeys } from "@/lib/api/teacher";
import { useReviewSeedSubject } from "@/lib/hooks/use-teacher-mutations";
import type {
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <SeedForm studentId={studentId} subjects={d.subjects} />
        <CardListPanel d={d} />
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
                Aşağıdaki <b>Ders Konularını Ekle</b> formundan müfredata uygun
                bir ders seç.
              </li>
              <li>
                <b>Konuları Kart Olarak Ekle</b> butonuna bas — tüm konular yeni
                kart olarak açılır.
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
              Öğrenci kartları Tekrar / Zor / İyi / Kolay olarak puanlar. Sistem
              zorlanılan konuları üstteki <b>Müdahale Önerileri</b> panelinde
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
    { label: "Toplam", value: d.breakdown.total, tone: "text-foreground" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
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
          <span className="ml-auto text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-500">
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
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-rose-500/15 text-rose-500 inline-flex items-center gap-1">
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
            className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-500/10 text-amber-500 ring-1 ring-inset ring-amber-500/20"
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
}: {
  studentId: number;
  subjects: ReviewSubjectOption[];
}) {
  const [subjectId, setSubjectId] = React.useState<number | "">("");
  const mut = useReviewSeedSubject(studentId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (subjectId === "") return;
    mut.mutate(
      { body: { subject_id: subjectId } },
      {
        onSuccess: () => setSubjectId(""),
      },
    );
  }

  return (
    <Card className="lg:col-span-1">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold inline-flex items-center gap-2">
          <Plus className="size-4" aria-hidden /> Ders Konularını Ekle
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
          Seçilen dersin kataloğundaki tüm konular bu öğrenciye yeni kart olarak
          açılır. Zaten ekli olan konular atlanır.
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm text-foreground mb-1.5">Ders</label>
            <select
              value={subjectId}
              onChange={(e) =>
                setSubjectId(e.target.value === "" ? "" : Number(e.target.value))
              }
              required
              className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background"
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
          <Button
            type="submit"
            disabled={mut.isPending || subjectId === ""}
            className="w-full"
          >
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Konuları Kart Olarak Ekle
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function CardListPanel({ d }: { d: TeacherReviewResponse }) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">
          Kartlar ({d.cards.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        {d.cards.length === 0 ? (
          <div className="text-center text-sm text-muted-foreground py-10 italic">
            Henüz tekrar kartı yok. Soldaki formdan bir ders ekleyin.
          </div>
        ) : (
          <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
            {d.cards.map((c) => (
              <div
                key={c.id}
                className="border border-border rounded-lg p-3 hover:bg-muted/30 transition"
              >
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <StateLabel state={c.state} label={c.state_label} />
                      <span className="text-xs text-muted-foreground">
                        {c.subject_name ?? "—"}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-foreground truncate mt-1">
                      {c.topic_name}
                    </div>
                  </div>
                  <div className="text-right text-xs text-muted-foreground flex-shrink-0">
                    {c.due_at ? (
                      <>Vade: {formatShortDate(c.due_at)}</>
                    ) : (
                      "Henüz çalışılmadı"
                    )}
                    <div className="mt-0.5 tabular-nums">
                      {c.review_count} tekrar
                      {c.lapse_count > 0 ? (
                        <>
                          {" · "}
                          <span className="text-rose-500">
                            {c.lapse_count} unutma
                          </span>
                        </>
                      ) : null}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const STATE_PILL: Record<ReviewState, string> = {
  new: "bg-muted text-foreground/80 ring-1 ring-inset ring-border",
  learning: "bg-amber-500/10 text-amber-500 ring-1 ring-inset ring-amber-500/20",
  relearning: "bg-rose-500/10 text-rose-500 ring-1 ring-inset ring-rose-500/20",
  review:
    "bg-emerald-500/10 text-emerald-500 ring-1 ring-inset ring-emerald-500/20",
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
