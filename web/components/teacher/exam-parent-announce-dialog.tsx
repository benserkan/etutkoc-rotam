"use client";

/**
 * Deneme sonucu veli duyurusu — ÖNİZLE, DÜZENLE, GÖNDER (2026-09-10).
 *
 * KOÇ İSTEĞİ (birebir): "bir denemenin sonuç bilgileri veliye mail olarak
 * gönderilirken mail içeriğinin ne olduğu önizlenmeli, düzenlenebilmeli —
 * örneğin kullanılan bazı ifadeler koç tarafından kaldırılma ihtiyacı
 * hissedilebilir; düzenleme yapılıp gönderilebilse daha iyi olurdu."
 *
 * ÖNCESİ: `window.confirm` — koç neyin gideceğini görmeden onaylıyordu.
 * ŞİMDİ: mailin gerçek içeriği (net şeridi + koç yorumu + ders tablosu +
 * alıcı veliler) gösterilir; koç YORUM CÜMLELERİNİ tek tek düzenler/siler,
 * kendi cümlesini ekler, ders tablosunu isterse çıkarır, sonra gönderir.
 *
 * NE DÜZENLENEBİLİR / NE DÜZENLENEMEZ (bilinçli sınır):
 *   · Düzenlenir → yorum cümleleri (koçun taahhüdü/dili) + ders tablosu var/yok
 *   · Düzenlenmez → net, D/Y/B, ders sayıları. Bunlar ÖLÇÜM; koç düzeltmek
 *     isterse denemenin kendisini düzenler ("Satırları düzelt"), maili değil.
 *     Veliye giden sayı ile paneldeki sayı ayrışamaz.
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Info,
  Loader2,
  Mail,
  MailX,
  Plus,
  Printer,
  RotateCcw,
  Send,
  Trash2,
} from "lucide-react";

import {
  getExamParentPreview,
  getExamParentPreviewHtml,
  teacherKeys,
} from "@/lib/api/teacher";
import type { ExamParentPreviewResponse } from "@/lib/types/teacher";
import { useNotifyParentsExam } from "@/lib/hooks/use-teacher-mutations";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const DELTA_TONE: Record<string, string> = {
  up: "text-emerald-700 dark:text-emerald-300",
  down: "text-amber-700 dark:text-amber-300",
  flat: "text-slate-600 dark:text-slate-300",
};

function deltaText(d: ExamParentPreviewResponse): string | null {
  if (!d.delta_direction || !d.delta_text) return null;
  if (d.delta_direction === "up")
    return `▲ Bir önceki denemeye göre ${d.delta_text} net artış`;
  if (d.delta_direction === "down")
    return `▼ Bir önceki denemeye göre ${d.delta_text} net geride`;
  return "● Bir önceki denemeyle aynı seviyede";
}

export function ExamParentAnnounceDialog({
  examId,
  studentId,
  open,
  onOpenChange,
}: {
  examId: number;
  studentId: number;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const notifyMut = useNotifyParentsExam(studentId);

  const q = useQuery<ExamParentPreviewResponse>({
    queryKey: teacherKeys.examParentPreview(examId),
    queryFn: () => getExamParentPreview(examId),
    enabled: open,
    staleTime: 15_000,
  });
  const data = q.data;

  // Düzenlenen metin. Önizleme geldiğinde bir kez tohumlanır; koç yazdıkça
  // korunur (effect'te setState React Compiler kuralına takılır → tohumlama
  // render sırasında "hangi exam için yüklendi" işaretiyle yapılır).
  const [draft, setDraft] = React.useState<string[] | null>(null);
  // Tohumlama anahtarı exam + "gönderilmiş mi" — duyurudan sonra yanıt
  // GÖNDERİLEN metne döner, taslak yeniden tohumlanmalı.
  const [seededFor, setSeededFor] = React.useState<string | null>(null);
  const [includeSubjects, setIncludeSubjects] = React.useState(true);
  // Geçmişle karşılaştırma + net fırsatı bölümleri (koç isteği 2026-09-10)
  const [includeHistory, setIncludeHistory] = React.useState(true);
  const [includeOpportunities, setIncludeOpportunities] = React.useState(true);
  const [printing, setPrinting] = React.useState(false);

  const seedKey = data ? `${data.exam_id}:${data.is_sent_snapshot}` : null;
  if (data && seedKey && seededFor !== seedKey) {
    setSeededFor(seedKey);
    setDraft(data.narrative);
    // Gönderilmiş mailde bölümler yanıttaki içerikten türetilir (koç o gün
    // neyi kapattıysa önizleme de öyle görünsün).
    setIncludeSubjects(!data.already_notified || data.subjects.length > 0);
    setIncludeHistory(
      !data.already_notified || Boolean(data.history?.has_data),
    );
    setIncludeOpportunities(
      !data.already_notified || data.opportunities.length > 0,
    );
  }

  // Duyurulmuş deneme: içerik veliye GİDEN mailden okunur, düzenlenmez —
  // koç yalnız görüntüler ve PDF'ler.
  const sentMode = Boolean(data?.already_notified);
  const lines = draft ?? data?.narrative ?? [];
  const maxLines = data?.max_lines ?? 12;
  const maxLen = data?.max_line_length ?? 500;
  const edited =
    data != null &&
    (JSON.stringify(lines) !== JSON.stringify(data.narrative) ||
      !includeSubjects || !includeHistory || !includeOpportunities);

  function setLine(i: number, value: string) {
    setLines(lines.map((l, idx) => (idx === i ? value.slice(0, maxLen) : l)));
  }
  function setLines(next: string[]) {
    setDraft(next);
  }
  function removeLine(i: number) {
    setLines(lines.filter((_, idx) => idx !== i));
  }
  function addLine() {
    if (lines.length >= maxLines) return;
    setLines([...lines, ""]);
  }
  /** Gönderim ve PDF çıktısı AYNI gövdeyi kullanır — ikisi ayrışamaz. */
  function currentBody() {
    return {
      narrative: lines.map((l) => l.trim()).filter(Boolean),
      include_subjects: includeSubjects,
      include_history: includeHistory,
      include_opportunities: includeOpportunities,
    };
  }

  function reset() {
    setLines(data?.narrative ?? []);
    setIncludeSubjects(true);
    setIncludeHistory(true);
    setIncludeOpportunities(true);
  }

  /** Modaldaki güncel içerikle mailin yazdırılabilir hâlini aç.
   *
   * Gizli iframe'e yazılır ve print() çağrılır → tarayıcının yazdırma
   * penceresinde "PDF olarak kaydet" ile dosya elde edilir (WhatsApp'tan
   * paylaşmak için). PDF kütüphanesi eklemedik: çıktı gerçek mail
   * şablonundan üretildiği için mail ile PDF ayrışamıyor ve sunucuda ek
   * bağımlılık/yük oluşmuyor.
   */
  async function downloadPdf() {
    if (printing) return;
    setPrinting(true);
    try {
      const html = await getExamParentPreviewHtml(examId, currentBody());
      const frame = document.createElement("iframe");
      frame.setAttribute("aria-hidden", "true");
      frame.style.cssText =
        "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
      document.body.appendChild(frame);
      const doc = frame.contentDocument;
      if (!doc) throw new Error("no_frame");
      doc.open();
      doc.write(html);
      doc.close();
      // Yazdırma penceresi kapanınca iframe'i topla (sayfada iz bırakmasın).
      window.setTimeout(() => {
        try {
          frame.contentWindow?.focus();
        } catch {
          /* yoksay */
        }
        window.setTimeout(() => frame.remove(), 60_000);
      }, 400);
    } catch {
      toast.error("Yazdırma önizlemesi hazırlanamadı.");
    } finally {
      setPrinting(false);
    }
  }

  function send() {
    const cleaned = lines.map((l) => l.trim()).filter(Boolean);
    notifyMut.mutate(
      { examId, body: { ...currentBody(), narrative: cleaned } },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  const blocked = data?.recipients.filter((r) => r.blocked) ?? [];
  const deliverable = data?.recipients.filter((r) => !r.blocked) ?? [];
  const dt = data ? deltaText(data) : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="inline-flex items-center gap-2">
            <Mail className="size-5 text-teal-600" aria-hidden />
            {sentMode
              ? "Veliye gönderilen mail"
              : "Veliye duyur — önizle ve düzenle"}
          </DialogTitle>
          <DialogDescription>
            {sentMode
              ? "Bu içerik veliye gönderildi. Aşağıdaki hâliyle PDF olarak indirip WhatsApp'tan paylaşabilirsiniz."
              : "Aşağıdaki içerik bağlı velilere e-posta olarak gidecek. Yorum cümlelerini düzenleyebilir, istemediklerinizi silebilirsiniz."}
          </DialogDescription>
        </DialogHeader>

        {q.isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Önizleme
            hazırlanıyor…
          </div>
        ) : q.isError || !data ? (
          <p className="py-6 text-sm text-destructive">
            Önizleme yüklenemedi. Lütfen tekrar deneyin.
          </p>
        ) : (
          <div className="space-y-4 text-sm">
            {data.already_notified ? (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  Bu deneme{data.notified_at
                    ? ` ${data.notified_at.slice(8, 10)}.${data.notified_at.slice(5, 7)}.${data.notified_at.slice(0, 4)} tarihinde`
                    : ""}{" "}
                  veliye duyuruldu — tekrar gönderilemez.{" "}
                  {data.is_sent_snapshot
                    ? "Aşağıdaki içerik o gün gönderilen mailin aynısıdır."
                    : ""}
                </span>
              </div>
            ) : null}

            {/* --- Mailin görünümü (velinin göreceği sıra) --- */}
            <div className="rounded-xl border border-border bg-muted/30 p-3">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Velinin göreceği e-posta
              </p>

              <div className="rounded-lg border border-border bg-background p-3">
                <p className="text-[13px] font-semibold text-foreground">
                  {data.student_name} · deneme sonucu
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {data.exam_title} · {data.exam_date_tr}
                  {data.section_label ? ` · ${data.section_label}` : ""}
                </p>

                {/* Net şeridi — ÖLÇÜM, düzenlenmez */}
                <div className="mt-2.5 rounded-lg border border-teal-200 bg-teal-50/70 px-3 py-2.5 dark:border-teal-500/30 dark:bg-teal-500/10">
                  <p className="text-2xl font-bold leading-none tabular-nums text-teal-800 dark:text-teal-200">
                    {data.net_text}
                  </p>
                  <p className="text-[10px] uppercase tracking-wide text-teal-700 dark:text-teal-300">
                    net
                  </p>
                  <p className="mt-1.5 text-xs text-slate-700 dark:text-slate-200">
                    {data.total_questions} soruda{" "}
                    <b className="text-emerald-700 dark:text-emerald-300">
                      {data.correct} doğru
                    </b>{" "}
                    ·{" "}
                    <b className="text-rose-700 dark:text-rose-300">
                      {data.wrong} yanlış
                    </b>{" "}
                    · <span className="text-muted-foreground">{data.blank} boş</span>
                  </p>
                  {dt ? (
                    <p
                      className={cn(
                        "mt-1 text-xs font-semibold",
                        DELTA_TONE[data.delta_direction ?? "flat"],
                      )}
                    >
                      {dt}
                    </p>
                  ) : null}
                  {data.prev_title ? (
                    <p className="mt-0.5 text-[10.5px] text-muted-foreground">
                      Karşılaştırma: {data.prev_title}
                      {data.prev_date_tr ? ` (${data.prev_date_tr})` : ""} ·{" "}
                      {data.prev_net_text} net
                    </p>
                  ) : null}
                </div>

                {/* Koç yorumu — DÜZENLENEBİLİR bölüm */}
                <div className="mt-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[12.5px] font-semibold text-foreground">
                      Bu deneme ne anlatıyor?
                    </p>
                    <div className={cn("flex items-center gap-1", sentMode && "hidden")}>
                      {edited ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 px-1.5 text-[11px]"
                          onClick={reset}
                          title="Sistemin önerdiği metne dön"
                        >
                          <RotateCcw className="mr-1 size-3" aria-hidden />
                          Sıfırla
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-6 px-1.5 text-[11px]"
                        onClick={addLine}
                        disabled={lines.length >= maxLines}
                        title={
                          lines.length >= maxLines
                            ? `En fazla ${maxLines} cümle`
                            : "Kendi cümleni ekle"
                        }
                      >
                        <Plus className="mr-1 size-3" aria-hidden />
                        Cümle ekle
                      </Button>
                    </div>
                  </div>

                  {lines.length === 0 ? (
                    <p className="mt-1.5 rounded-md border border-dashed border-border px-2.5 py-2 text-[11.5px] italic text-muted-foreground">
                      Yorum yok — mail yalnız sayılarla gidecek. İsterseniz
                      &quot;Cümle ekle&quot; ile kendi mesajınızı yazın.
                    </p>
                  ) : (
                    <ul className="mt-1.5 space-y-1.5">
                      {lines.map((line, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <textarea
                            value={line}
                            readOnly={sentMode}
                            onChange={(e) => setLine(i, e.target.value)}
                            rows={Math.min(4, Math.ceil((line.length || 1) / 70))}
                            maxLength={maxLen}
                            placeholder="Veliye gidecek cümle…"
                            aria-label={`Yorum cümlesi ${i + 1}`}
                            className="min-h-[38px] w-full resize-y rounded-md border border-border bg-background px-2 py-1.5 text-[12.5px] leading-relaxed text-foreground focus:border-teal-400 focus:outline-none focus:ring-1 focus:ring-teal-300"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className={cn(
                              "mt-0.5 h-7 shrink-0 px-1.5 text-muted-foreground hover:text-rose-600",
                              sentMode && "hidden",
                            )}
                            onClick={() => removeLine(i)}
                            aria-label={`${i + 1}. cümleyi kaldır`}
                            title="Bu cümleyi maile koyma"
                          >
                            <Trash2 className="size-3.5" aria-hidden />
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                {/* Ders kırılımı — gitsin/gitmesin */}
                <div className="mt-3">
                  <label className="flex cursor-pointer items-center gap-2 text-[12.5px] font-semibold text-foreground">
                    <input
                      type="checkbox"
                      checked={includeSubjects}
                      disabled={sentMode}
                      onChange={(e) => setIncludeSubjects(e.target.checked)}
                      className="size-3.5 accent-teal-600"
                    />
                    Ders bazında tabloyu da gönder
                  </label>
                  {includeSubjects && data.subjects.length > 0 ? (
                    <table className="mt-1.5 w-full text-[11.5px]">
                      <thead>
                        <tr className="text-[10px] text-muted-foreground">
                          <th className="py-0.5 text-left font-medium">Ders</th>
                          <th className="py-0.5 text-right font-medium">D</th>
                          <th className="py-0.5 text-right font-medium">Y</th>
                          <th className="py-0.5 text-right font-medium">B</th>
                          <th className="py-0.5 text-right font-medium">Net</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.subjects.map((s, i) => (
                          <tr key={i} className="border-t border-border/60">
                            <td className="py-1 pr-1 text-foreground">
                              <span className="whitespace-normal break-words">
                                {s.name}
                              </span>
                              {s.unmatched ? (
                                <span
                                  className="ml-1 rounded bg-amber-500 px-1 py-px text-[9px] font-semibold uppercase text-white"
                                  title="Bu satır müfredat dersine bağlanmadı — 'Satırları düzelt' ile bağlayabilirsiniz"
                                >
                                  bağlanmadı
                                </span>
                              ) : null}
                            </td>
                            <td className="py-1 text-right tabular-nums text-emerald-700 dark:text-emerald-300">
                              {s.correct}
                            </td>
                            <td className="py-1 text-right tabular-nums text-rose-700 dark:text-rose-300">
                              {s.wrong}
                            </td>
                            <td className="py-1 text-right tabular-nums text-muted-foreground">
                              {s.blank}
                            </td>
                            <td className="py-1 text-right font-semibold tabular-nums text-foreground">
                              {s.net.toFixed(2).replace(".", ",")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : null}
                </div>

                {/* Geçmiş denemelerle karşılaştırma — aynı tür, eskiden yeniye
                    (koç isteği 2026-09-10: "önceki denemelerle karşılaştırma
                    fırsatı olsun") */}
                {data.history?.has_data ? (
                  <div className="mt-3">
                    <label className="flex cursor-pointer items-center gap-2 text-[12.5px] font-semibold text-foreground">
                      <input
                        type="checkbox"
                        checked={includeHistory}
                        disabled={sentMode}
                        onChange={(e) => setIncludeHistory(e.target.checked)}
                        className="size-3.5 accent-teal-600"
                      />
                      Önceki denemelerle karşılaştırmayı da gönder
                    </label>
                    {includeHistory ? (
                      <div className="mt-1.5 overflow-x-auto">
                        <table className="w-full text-[11.5px]">
                          <thead>
                            <tr className="text-[10px] text-muted-foreground">
                              <th className="py-0.5 text-left font-medium">Ders</th>
                              {data.history.exams.map((e, i) => (
                                <th
                                  key={i}
                                  className={cn(
                                    "whitespace-nowrap py-0.5 text-right font-medium",
                                    e.is_current &&
                                      "text-teal-700 dark:text-teal-300",
                                  )}
                                  title={e.title}
                                >
                                  {e.date_tr.slice(0, 5)}
                                  {e.is_current ? " *" : ""}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {data.history.rows.map((r, i) => (
                              <tr key={i} className="border-t border-border/60">
                                <td className="py-1 pr-1 text-foreground">
                                  <span className="whitespace-normal break-words">
                                    {r.subject}
                                  </span>
                                  {r.direction === "up" ? (
                                    <span className="ml-1 text-[10px] text-emerald-700 dark:text-emerald-300">
                                      &#9650;
                                    </span>
                                  ) : r.direction === "down" ? (
                                    <span className="ml-1 text-[10px] text-amber-700 dark:text-amber-300">
                                      &#9660;
                                    </span>
                                  ) : null}
                                </td>
                                {r.nets.map((n, j) => (
                                  <td
                                    key={j}
                                    className={cn(
                                      "whitespace-nowrap py-1 text-right tabular-nums",
                                      j === r.nets.length - 1
                                        ? "font-semibold text-foreground"
                                        : "text-muted-foreground",
                                    )}
                                  >
                                    {n ?? "-"}
                                  </td>
                                ))}
                              </tr>
                            ))}
                            <tr className="border-t-2 border-border">
                              <td className="py-1 font-semibold text-foreground">
                                Toplam net
                              </td>
                              {data.history.totals.map((t, j) => (
                                <td
                                  key={j}
                                  className={cn(
                                    "py-1 text-right font-semibold tabular-nums",
                                    j === (data.history?.totals.length ?? 0) - 1
                                      ? "text-teal-700 dark:text-teal-300"
                                      : "text-muted-foreground",
                                  )}
                                >
                                  {t}
                                </td>
                              ))}
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {/* Net fırsatı — koç panelindeki tabloyla AYNI servis */}
                {data.opportunities.length > 0 ? (
                  <div className="mt-3">
                    <label className="flex cursor-pointer items-center gap-2 text-[12.5px] font-semibold text-foreground">
                      <input
                        type="checkbox"
                        checked={includeOpportunities}
                        disabled={sentMode}
                        onChange={(e) =>
                          setIncludeOpportunities(e.target.checked)
                        }
                        className="size-3.5 accent-teal-600"
                      />
                      &quot;Nerede net kazanabilir?&quot; tablosunu da gönder
                    </label>
                    {includeOpportunities ? (
                      <ul className="mt-1.5 space-y-0.5">
                        {data.opportunities.map((o, i) => (
                          <li
                            key={i}
                            className="flex items-baseline justify-between gap-2 border-t border-border/60 py-1 text-[11.5px]"
                          >
                            <span className="min-w-0 whitespace-normal break-words text-foreground">
                              {o.topic}
                              <span className="text-muted-foreground">
                                {" - "}
                                {o.subject}
                              </span>
                            </span>
                            <span className="shrink-0 whitespace-nowrap font-semibold tabular-nums text-emerald-700 dark:text-emerald-300">
                              +{o.gain_text}
                              <span className="font-normal text-muted-foreground">
                                {" "}
                                net
                              </span>
                            </span>
                          </li>
                        ))}
                        {data.opportunity_total_text ? (
                          <li className="flex items-baseline justify-between gap-2 border-t-2 border-border py-1 text-[11.5px]">
                            <span className="font-semibold text-foreground">
                              Hepsi kapanırsa
                            </span>
                            <span className="shrink-0 whitespace-nowrap font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
                              +{data.opportunity_total_text}
                              <span className="font-normal text-muted-foreground">
                                {" "}
                                net/deneme
                              </span>
                            </span>
                          </li>
                        ) : null}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
              </div>

              <p className="mt-2 flex items-start gap-1.5 text-[11px] text-muted-foreground">
                <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
                <span>
                  Net ve D/Y/B ölçümdür, buradan değiştirilmez — düzeltme
                  gerekiyorsa denemenin kendisini düzenleyin. Koça özel notlar
                  ve soru-satırı detayları hiçbir durumda gönderilmez.
                </span>
              </p>
            </div>

            {/* --- Alıcılar --- */}
            <div>
              <h3 className="mb-1.5 font-semibold text-foreground">
                Alıcı veliler
              </h3>
              {deliverable.length === 0 && blocked.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Bağlı veli yok — duyuru gönderilemez.
                </p>
              ) : (
                <ul className="space-y-1">
                  {deliverable.map((r) => (
                    <li
                      key={r.parent_id}
                      className="flex items-center gap-2 text-xs"
                    >
                      <Mail className="size-3 text-teal-600" aria-hidden />
                      <span className="font-medium text-foreground">{r.name}</span>
                      <span className="text-muted-foreground">· gidecek</span>
                    </li>
                  ))}
                  {blocked.map((r) => (
                    <li
                      key={r.parent_id}
                      className="flex items-center gap-2 text-xs"
                    >
                      <MailX className="size-3 text-muted-foreground" aria-hidden />
                      <span className="text-muted-foreground line-through">
                        {r.name}
                      </span>
                      <span className="text-amber-700 dark:text-amber-300">
                        · {r.blocked_label}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        <DialogFooter className="gap-2 sm:justify-between">
          {/* PDF: mailin aynısını yazdır → WhatsApp'tan paylaşılabilir dosya */}
          <Button
            type="button"
            variant="outline"
            onClick={downloadPdf}
            disabled={printing || !data}
            title="Mailin aynısını yazdır — 'PDF olarak kaydet' ile dosya elde edip WhatsApp'tan paylaşabilirsiniz"
            className="sm:mr-auto"
          >
            {printing ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Printer className="size-4" aria-hidden />
            )}
            PDF olarak indir
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            {sentMode ? "Kapat" : "Vazgeç"}
          </Button>
          {sentMode ? null : (
          <Button
            type="button"
            onClick={send}
            disabled={
              notifyMut.isPending ||
              !data ||
              data.already_notified ||
              (data.deliverable_count ?? 0) === 0
            }
            className="bg-teal-600 text-white hover:bg-teal-700"
            title={
              data && data.deliverable_count === 0
                ? "Gidecek veli yok"
                : "Bu içerikle velilere gönder"
            }
          >
            {notifyMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Send className="size-4" aria-hidden />
            )}
            {data && data.deliverable_count > 0
              ? `${data.deliverable_count} veliye gönder`
              : "Gönder"}
          </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
