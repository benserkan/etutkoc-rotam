"use client";

import { useQuery } from "@tanstack/react-query";
import { GraduationCap, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface ReadinessBook {
  name: string;
  remaining: number;
}
interface ReadinessSubject {
  subject_id: number;
  subject_name: string;
  status: "ok" | "late" | "stalled" | "early" | "done";
  active_books: ReadinessBook[];
  dropped_books: string[];
  finished_books: string[];
  remaining_tests: number;
  remaining_topics: number;
  pace: number;
  pace_days: number;
  solved_window: number;
  finish_date: string | null;
  target_date: string | null;
  days_late: number | null;
  required_pace: number | null;
}
interface ReadinessResponse {
  exam_date: string | null;
  target_date: string | null;
  days_to_exam: number | null;
  subjects: ReadinessSubject[];
}

const MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function fmt(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[(m ?? 1) - 1]} ${y}`;
}

const STATUS: Record<ReadinessSubject["status"], { label: string; cls: string }> = {
  late: { label: "Geride", cls: "bg-rose-600 text-white" },
  stalled: { label: "İlerlemiyor", cls: "bg-amber-500 text-slate-950" },
  ok: { label: "Yetişiyor", cls: "bg-emerald-600 text-white" },
  early: { label: "Tahmin için erken", cls: "bg-slate-500 text-white" },
  done: { label: "Aktif kaynaklar bitti", cls: "bg-cyan-700 text-white" },
};

/**
 * Sınava hazırlık — ders bazlı, AKTİF kaynak modeli. Kalan iş yalnız son 21 günde
 * (ya da önümüzdeki 14 günde) görev verilen kaynaklardan; hiç kullanılmayan ya da
 * bırakılan kaynak hesaba girmez.
 */
export function ExamReadinessCard({ studentId }: { studentId: number }) {
  const q = useQuery<ReadinessResponse>({
    queryKey: ["teacher", "me", "students", String(studentId), "exam-readiness"],
    queryFn: () => api<ReadinessResponse>(`/api/v2/teacher/students/${studentId}/exam-readiness`),
    staleTime: 60_000,
  });

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm" data-testid="exam-readiness">
      <h3 className="inline-flex items-center gap-2 text-base font-semibold">
        <GraduationCap className="size-4 text-indigo-500" aria-hidden />
        Sınava hazırlık — ders bazlı
      </h3>
      {q.data?.exam_date ? (
        <p className="mt-0.5 text-sm text-muted-foreground">
          Sınav {fmt(q.data.exam_date)} ({q.data.days_to_exam} gün) · hedef {fmt(q.data.target_date)}:
          aktif kaynakların sınavdan 6 hafta önce bitmesi (son haftalar deneme ve tekrar).
        </p>
      ) : null}
      <p className="mt-2 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
        Kalan iş yalnız öğrencinin şu an ilerlediği kaynaklardan hesaplanır: son 21 günde ya da
        önümüzdeki 14 günde görev verilen kitaplar. Hiç kullanılmayan ya da bırakılan kaynak ve
        kapattığın konular sayılmaz. Hız, o dersin son 21 günde gerçekten çözülen testidir.
      </p>

      {q.isLoading ? (
        <p className="mt-3 inline-flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
        </p>
      ) : !q.data || !q.data.exam_date ? (
        <p className="mt-3 text-sm text-muted-foreground">Sınav tarihi belirlenemedi.</p>
      ) : q.data.subjects.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Son 21 günde görev verilen test kaynağı yok — tahmin için önce program gerekiyor.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border">
          {q.data.subjects.map((s) => {
            const st = STATUS[s.status];
            return (
              <li key={s.subject_id} className="py-3" data-testid="readiness-row">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold">{s.subject_name}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", st.cls)}>
                    {st.label}
                    {s.status === "late" && s.days_late ? ` · ${s.days_late} gün` : ""}
                  </span>
                </div>
                <dl className="mt-1.5 grid grid-cols-1 gap-x-4 gap-y-0.5 text-xs sm:grid-cols-[auto_1fr]">
                  <dt className="text-muted-foreground">Aktif kaynak</dt>
                  <dd className="break-words">
                    {s.active_books.length > 0
                      ? s.active_books.map((b) => `${b.name} (kalan ${b.remaining})`).join(" · ")
                      : "—"}
                  </dd>
                  {s.finished_books.length > 0 ? (
                    <>
                      <dt className="text-muted-foreground">Biten</dt>
                      <dd className="break-words">{s.finished_books.join(" · ")}</dd>
                    </>
                  ) : null}
                  {s.dropped_books.length > 0 ? (
                    <>
                      <dt className="text-muted-foreground">Bırakılan</dt>
                      <dd className="break-words">{s.dropped_books.join(" · ")} (21+ gündür görev yok)</dd>
                    </>
                  ) : null}
                  <dt className="text-muted-foreground">Kalan</dt>
                  <dd>
                    {s.remaining_tests} test{s.remaining_topics ? ` · ${s.remaining_topics} konu` : ""}
                  </dd>
                  <dt className="text-muted-foreground">Hız</dt>
                  <dd>
                    {s.pace.toFixed(1)} test/gün (son {s.pace_days} günde {s.solved_window} test)
                    {s.required_pace != null ? ` · gereken ${s.required_pace.toFixed(1)} test/gün` : ""}
                  </dd>
                  {s.finish_date ? (
                    <>
                      <dt className="text-muted-foreground">Tahmini bitiş</dt>
                      <dd>
                        {fmt(s.finish_date)} (hedef {fmt(s.target_date)})
                      </dd>
                    </>
                  ) : null}
                </dl>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
