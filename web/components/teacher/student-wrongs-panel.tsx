"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookX,
  CheckCircle2,
  ImageIcon,
  Loader2,
  MessageSquarePlus,
  RotateCcw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getTeacherStudentWrongQuestions,
  getTeacherStudentWrongSummary,
  teacherWrongImageUrl,
  wrongQuestionKeys,
} from "@/lib/api/wrong-questions";
import { useSetCoachNote } from "@/lib/hooks/use-wrong-question-mutations";
import type { WrongQuestionItem } from "@/lib/types/wrong-question";
import { cn } from "@/lib/utils";

/**
 * Koç — öğrenci detayı "Yanlışlar" sekmesi.
 *
 * Tanı panosu: en çok biriken konular + hata türü dağılımı + kapanış hızı.
 * Koç her yanlışa "çözüm yaklaşımı" açıklaması yazar; öğrenci yeniden
 * çözerken görür. (Koç adına kayıt açma + AI etiketleme Faz 3.)
 */
export function StudentWrongsPanel({ studentId }: { studentId: number }) {
  const [statusFilter, setStatusFilter] = React.useState<"" | "acik" | "kapandi">("acik");
  const [detailId, setDetailId] = React.useState<number | null>(null);

  const summaryQ = useQuery({
    queryKey: [...wrongQuestionKeys.teacherList("me", studentId), "summary"],
    queryFn: () => getTeacherStudentWrongSummary(studentId),
    staleTime: 30_000,
  });
  const listQ = useQuery({
    queryKey: wrongQuestionKeys.teacherList("me", studentId),
    queryFn: () => getTeacherStudentWrongQuestions(studentId),
    staleTime: 15_000,
  });

  const s = summaryQ.data;
  const items = (listQ.data?.items ?? []).filter(
    (it) => !statusFilter || it.status === statusFilter,
  );
  // Detay kaydı listeden TÜRETİLİR — liste tazelenince dialog kendiliğinden
  // güncel kalır (state kopyası + effect senkronu gerekmez)
  const detail =
    (detailId != null &&
      (listQ.data?.items ?? []).find((it) => it.id === detailId)) ||
    null;

  if (summaryQ.isLoading || listQ.isLoading) {
    return (
      <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Yükleniyor…
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Özet şeridi */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Açık yanlış" value={s?.counts.open ?? 0} tone="amber"
             hint="Henüz kapanmamış — tekrar döngüsünde" />
        <Kpi label="Yeniden çözme vakti gelen" value={s?.counts.due ?? 0} tone="rose"
             hint="Öğrencinin bugün karşısına çıkacaklar" />
        <Kpi label="Son 30 günde eklenen" value={s?.added_last_30d ?? 0} tone="slate"
             hint="Arşive yeni giren yanlışlar" />
        <Kpi label="Son 30 günde KAPANAN" value={s?.closed_last_30d ?? 0} tone="emerald"
             hint="Aralıklı 2 doğru çözümle kapatıldı" />
      </div>

      {(s?.counts.total ?? 0) === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
          <BookX className="mx-auto size-8 text-muted-foreground/50" aria-hidden />
          <p className="mt-3 text-sm text-muted-foreground max-w-md mx-auto">
            Bu öğrenci henüz yanlış arşivlemedi. Öğrenci panelindeki
            <b> Yanlışlarım</b> ekranından fotoğrafla ekleyebilir; görev
            kartındaki menüde de &quot;Yanlışı arşivle&quot; kısayolu var.
          </p>
        </div>
      ) : (
        <>
          {/* En çok biriken konular + hata türü */}
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="rounded-lg border border-border bg-card p-4">
              <h3 className="text-sm font-semibold text-foreground">
                En çok biriken konular
              </h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Açık yanlışı en fazla olan konular — program ve seans önceliği.
              </p>
              <ul className="mt-3 space-y-2">
                {(s?.by_topic ?? []).slice(0, 8).map((t) => (
                  <li key={t.topic_id} className="flex items-center gap-2 text-sm">
                    <span className="min-w-0 flex-1 truncate text-foreground">
                      {t.topic_name}
                      {t.subject_name ? (
                        <span className="text-muted-foreground"> · {t.subject_name}</span>
                      ) : null}
                    </span>
                    <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs font-semibold tabular-nums text-amber-800 dark:bg-amber-500/10 dark:text-amber-300">
                      {t.open_count} açık
                    </span>
                    {t.closed_count > 0 ? (
                      <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-xs font-semibold tabular-nums text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
                        {t.closed_count} kapandı
                      </span>
                    ) : null}
                  </li>
                ))}
                {(s?.by_topic ?? []).length === 0 ? (
                  <li className="text-xs italic text-muted-foreground">
                    Konu etiketi olan kayıt yok — öğrenci kitap/bölüm seçerek
                    eklerse konu kendiliğinden etiketlenir.
                  </li>
                ) : null}
              </ul>
            </section>
            <section className="rounded-lg border border-border bg-card p-4">
              <h3 className="text-sm font-semibold text-foreground">
                Hata türü dağılımı
              </h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                &quot;Neden yanlış?&quot; — seansta konuşulacak asıl şey.
              </p>
              <ul className="mt-3 space-y-2">
                {Object.entries(s?.by_error_type ?? {})
                  .sort((a, b) => b[1] - a[1])
                  .map(([k, v]) => {
                    const total = Object.values(s?.by_error_type ?? {}).reduce(
                      (a, b) => a + b, 0,
                    );
                    const pct = total ? Math.round((100 * v) / total) : 0;
                    return (
                      <li key={k} className="text-sm">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-foreground">
                            {s?.error_type_labels[k] ?? k}
                          </span>
                          <span className="tabular-nums text-muted-foreground">
                            {v} · %{pct}
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 w-full overflow-hidden rounded bg-muted">
                          <div
                            className="h-full rounded bg-rose-400"
                            style={{ width: `${pct}%` }}
                            aria-hidden
                          />
                        </div>
                      </li>
                    );
                  })}
                {Object.keys(s?.by_error_type ?? {}).length === 0 ? (
                  <li className="text-xs italic text-muted-foreground">
                    Hata türü işaretlenmiş kayıt yok.
                  </li>
                ) : null}
              </ul>
            </section>
          </div>

          {/* Liste */}
          <section>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">Kayıtlar</h3>
              <div className="ml-auto flex gap-1.5">
                {(
                  [
                    ["acik", "Açık"],
                    ["kapandi", "Kapanan"],
                    ["", "Tümü"],
                  ] as const
                ).map(([val, label]) => (
                  <button
                    key={val || "all"}
                    type="button"
                    onClick={() => setStatusFilter(val)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition",
                      statusFilter === val
                        ? "border-cyan-600 bg-cyan-600 text-white"
                        : "border-border bg-card text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {items.length === 0 ? (
              <p className="rounded-md border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
                Bu filtreyle kayıt yok.
              </p>
            ) : (
              <ul className="divide-y divide-border rounded-lg border border-border bg-card">
                {items.map((it) => (
                  <li key={it.id}>
                    <button
                      type="button"
                      onClick={() => setDetailId(it.id)}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition hover:bg-muted/40"
                    >
                      <span className="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded bg-muted">
                        {it.images[0] ? (
                          // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                          <img
                            src={teacherWrongImageUrl(it.id, it.images[0].id)}
                            alt=""
                            className="h-full w-full object-cover"
                            loading="lazy"
                          />
                        ) : (
                          <ImageIcon className="size-4 text-muted-foreground/50" aria-hidden />
                        )}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {it.topic_name ?? it.section_label ?? "Etiketsiz"}
                        </span>
                        <span className="block truncate text-xs text-muted-foreground">
                          {[it.subject_name, it.book_name].filter(Boolean).join(" · ") || "—"}
                        </span>
                      </span>
                      {it.error_type_label ? (
                        <span className="hidden rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-800 dark:bg-rose-500/10 dark:text-rose-300 sm:inline">
                          {it.error_type_label}
                        </span>
                      ) : null}
                      {it.coach_note ? (
                        <MessageSquarePlus
                          className="size-3.5 text-cyan-600"
                          aria-hidden
                        />
                      ) : null}
                      {it.status === "kapandi" ? (
                        <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
                      ) : it.is_due ? (
                        <RotateCcw className="size-4 text-amber-600" aria-hidden />
                      ) : (
                        <span className="text-[10px] tabular-nums text-muted-foreground">
                          {it.correct_streak}/2
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      <CoachDetailDialog item={detail} onClose={() => setDetailId(null)} />
    </div>
  );
}

function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint: string;
  tone: "amber" | "rose" | "emerald" | "slate";
}) {
  const toneCls = {
    amber: "text-amber-700 dark:text-amber-300",
    rose: "text-rose-700 dark:text-rose-300",
    emerald: "text-emerald-700 dark:text-emerald-300",
    slate: "text-foreground",
  }[tone];
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-0.5 text-2xl font-semibold tabular-nums", toneCls)}>
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-muted-foreground">{hint}</div>
    </div>
  );
}

function CoachDetailDialog({
  item,
  onClose,
}: {
  item: WrongQuestionItem | null;
  onClose: () => void;
}) {
  const setNote = useSetCoachNote();
  const [draft, setDraft] = React.useState("");
  const [lastId, setLastId] = React.useState<number | null>(null);
  // Dialog yeni kayıtla açılınca taslağı o kaydın notuyla başlat
  // (React'in belgelediği "prop değişince render'da state sıfırla" deseni)
  if (item && item.id !== lastId) {
    setLastId(item.id);
    setDraft(item.coach_note ?? "");
  }
  if (!item) return null;

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-base">
            {item.topic_name ?? item.section_label ?? "Etiketsiz soru"}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {[item.subject_name, item.book_name].filter(Boolean).join(" · ")}
            </span>
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 text-xs">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 font-medium",
                item.status === "kapandi"
                  ? "bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300"
                  : "bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-300",
              )}
            >
              {item.status === "kapandi" ? "Kapandı" : `Açık · seri ${item.correct_streak}/2`}
            </span>
            {item.error_type_label ? (
              <span className="rounded bg-rose-50 px-1.5 py-0.5 font-medium text-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
                {item.error_type_label}
              </span>
            ) : null}
            <span className="text-muted-foreground">
              {item.attempts_count} deneme · {new Date(item.created_at).toLocaleDateString("tr-TR")}
            </span>
          </div>

          {item.images.filter((im) => im.kind === "question").map((im) => (
            // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
            <img
              key={im.id}
              src={teacherWrongImageUrl(item.id, im.id)}
              alt="Soru fotoğrafı"
              className="w-full rounded-md border border-border"
            />
          ))}
          {item.note ? (
            <p className="text-sm text-muted-foreground">
              <b className="text-foreground">Öğrencinin notu:</b> {item.note}
            </p>
          ) : null}
          {item.images.filter((im) => im.kind === "solution").length > 0 ? (
            <div>
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Öğrencinin çözüm fotoğrafı
              </div>
              {item.images.filter((im) => im.kind === "solution").map((im) => (
                // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                <img
                  key={im.id}
                  src={teacherWrongImageUrl(item.id, im.id)}
                  alt="Çözüm fotoğrafı"
                  className="mt-1 w-full rounded-md border border-border"
                />
              ))}
            </div>
          ) : null}

          {/* Koç açıklaması */}
          <div>
            <label
              htmlFor={`coach-note-${item.id}`}
              className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted-foreground"
            >
              Çözüm yaklaşımın (öğrenci yeniden çözerken görür)
            </label>
            <textarea
              id={`coach-note-${item.id}`}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={3}
              maxLength={4000}
              placeholder="Örn: Önce paydaları eşitle; işaret hatasına dikkat — geçen sefer 2. adımda karışmıştı."
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60"
            />
            <div className="mt-2 flex justify-end">
              <Button
                size="sm"
                disabled={setNote.isPending || draft === (item.coach_note ?? "")}
                onClick={() =>
                  setNote.mutate({ id: item.id, coach_note: draft.trim() || null })
                }
                className="gap-1.5"
              >
                {setNote.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" aria-hidden />
                ) : (
                  <MessageSquarePlus className="size-3.5" aria-hidden />
                )}
                Açıklamayı kaydet
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
