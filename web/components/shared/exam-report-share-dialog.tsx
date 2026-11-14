"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ExternalLink, Loader2, MessageCircle } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { buildShareLink, getShareTargets, messagingKeys } from "@/lib/api/messaging";
import {
  downloadExamParentReportPdf,
  downloadStudentParentReportPdf,
  getExamParentReportLink,
  getStudentParentReportLink,
  type ExamParentReportLink,
} from "@/lib/api/teacher";
import type { ShareReportKind } from "@/lib/types/messaging";
import { SELF, ShareRecipients } from "@/components/shared/share-report-dialog";

/**
 * Deneme analiz raporunu veliye WhatsApp'tan gönder (2026-11-13, koç kararı).
 *
 * Dosya yerine BAĞLANTI gider: WhatsApp, bağlantıyla açılan sohbete dosya
 * eklemeye izin vermez — bilgisayarda iki adım, telefonda iki düğme kafa
 * karıştırıyordu, iPhone'da tarayıcıda PDF üretimi ara ara düşüyordu. Bağlantı
 * hem telefonda hem bilgisayarda TEK adımda gider; veli sayfada analizi okur,
 * Rota'nın sesiyle dinler ve isterse PDF'i indirir (PDF'i sunucu üretir).
 */
export function ExamReportShareDialog({
  open,
  onClose,
  examId,
  studentId,
  title,
  message,
}: {
  open: boolean;
  onClose: () => void;
  examId: number;
  studentId: number;
  title: string;
  message: string;
}) {
  if (!open) return null;
  return (
    <ParentReportShareInner
      onClose={onClose}
      studentId={studentId}
      title={title}
      message={message}
      shareKind="exam_card"
      refId={examId}
      linkKey={["teacher", "me", "exams", examId, "parent-report-link"]}
      getLink={() => getExamParentReportLink(examId)}
      downloadPdf={() => downloadExamParentReportPdf(examId)}
    />
  );
}

/** Gelişim / haftalık raporu veliye WhatsApp'tan gönder (aynı pencere). */
export function StudentReportShareDialog({
  open,
  onClose,
  studentId,
  kind,
  series,
  weekStart,
  title,
  message,
}: {
  open: boolean;
  onClose: () => void;
  studentId: number;
  kind: "progress" | "weekly";
  series?: string | null;
  weekStart?: string | null;
  title: string;
  message: string;
}) {
  if (!open) return null;
  const body = { kind, series: series ?? null, week_start: weekStart ?? null };
  return (
    <ParentReportShareInner
      onClose={onClose}
      studentId={studentId}
      title={title}
      message={message}
      shareKind={kind === "weekly" ? "parent_weekly" : "exam_progress"}
      refId={null}
      linkKey={["teacher", "me", "students", studentId, "parent-report-link", kind, series ?? "", weekStart ?? ""]}
      getLink={() => getStudentParentReportLink(studentId, body)}
      downloadPdf={() => downloadStudentParentReportPdf(studentId, body)}
    />
  );
}

function ParentReportShareInner({
  onClose,
  studentId,
  title,
  message,
  shareKind,
  refId,
  linkKey,
  getLink,
  downloadPdf,
}: {
  onClose: () => void;
  studentId: number;
  title: string;
  message: string;
  shareKind: ShareReportKind;
  refId: number | null;
  linkKey: readonly unknown[];
  getLink: () => Promise<ExamParentReportLink>;
  downloadPdf: () => Promise<void>;
}) {
  const [text, setText] = React.useState(message);
  const [picked, setPicked] = React.useState<number | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [pdfBusy, setPdfBusy] = React.useState(false);

  const targetsQ = useQuery({
    queryKey: messagingKeys.shareTargets(studentId),
    queryFn: () => getShareTargets(studentId),
  });
  const linkQ = useQuery({
    queryKey: linkKey,
    queryFn: getLink,
    staleTime: 5 * 60_000,
  });
  const targets = React.useMemo(() => targetsQ.data?.targets ?? [], [targetsQ.data]);
  const defaultPick = React.useMemo(() => {
    const p = targets.find((t) => t.can_message && t.relation_label !== "Öğrencinin kendisi");
    return p ? p.user_id : SELF;
  }, [targets]);
  const selected = picked ?? defaultPick;
  const selectedTarget = targets.find((t) => t.user_id === selected) ?? null;
  const url = linkQ.data?.url ?? null;
  const fullText = url ? `${text.trim()}\n\nRaporu açmak ve sesli dinlemek için:\n${url}` : text;

  async function send() {
    if (!url) return;
    const isTouch = window.matchMedia?.("(pointer: coarse)").matches === true;
    // Bilgisayarda panel açık kalsın diye yeni sekme tıklama anında açılır (açılır pencere engeli).
    const win = isTouch ? null : window.open("about:blank", "_blank");
    setBusy(true);
    try {
      const res = await buildShareLink({
        student_id: studentId,
        kind: shareKind,
        text: fullText,
        target_user_id: selected === SELF ? null : selected,
        ref_id: refId,
      });
      if (win) win.location.href = res.wa_url;
      else window.location.href = res.wa_url;
      toast.success(
        res.target_name ? `${res.target_name} ile sohbet açıldı — gönder tuşuna basman yeterli.` : "WhatsApp açıldı — kişiyi seçip gönder.",
      );
      onClose();
    } catch (e) {
      win?.close();
      toast.error(e instanceof ApiError && e.message ? e.message : "WhatsApp açılamadı.");
    } finally {
      setBusy(false);
    }
  }

  async function pdf() {
    setPdfBusy(true);
    try {
      await downloadPdf();
    } catch {
      toast.error("PDF hazırlanamadı, biraz sonra tekrar dene.");
    } finally {
      setPdfBusy(false);
    }
  }

  const sendLabel =
    selected === SELF || !selectedTarget
      ? "WhatsApp'ta gönder"
      : `${selectedTarget.full_name.trim().split(/\s+/)[0]} ile WhatsApp'ta gönder`;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-h-[92vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Veliye WhatsApp&apos;tan gönder</DialogTitle>
          <DialogDescription>
            {`${title}: veli raporu bir bağlantıyla açar, Rota'nın sesiyle dinleyebilir ve isterse PDF olarak indirir.`}
          </DialogDescription>
        </DialogHeader>

        <ShareRecipients
          loading={targetsQ.isLoading}
          error={targetsQ.isError}
          targets={targets}
          selected={selected}
          onPick={setPicked}
        />

        <section className="grid gap-1.5">
          <label htmlFor="report-share-text" className="text-sm font-semibold text-slate-900">
            Mesaj
          </label>
          <textarea
            id="report-share-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            maxLength={1200}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
          <div className="rounded-md bg-slate-100 px-3 py-2 text-xs text-slate-700">
            {linkQ.isLoading ? (
              <span className="inline-flex items-center gap-1.5">
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
                Rapor bağlantısı hazırlanıyor…
              </span>
            ) : linkQ.isError || !url ? (
              <span className="text-rose-800">Rapor bağlantısı hazırlanamadı. Pencereyi kapatıp yeniden dene.</span>
            ) : (
              <>
                Mesajın sonuna rapor bağlantısı eklenir:{" "}
                <a href={url} target="_blank" rel="noopener" className="break-all font-medium text-cyan-800 underline">
                  {url}
                </a>
                <span className="mt-1 block text-slate-500">
                  Bağlantı 60 gün açık kalır; veli giriş yapmadan açar.
                </span>
              </>
            )}
          </div>
        </section>

        <div className="grid gap-2">
          <Button
            type="button"
            onClick={send}
            disabled={busy || !url}
            className="h-auto min-h-11 whitespace-normal bg-emerald-700 py-2 text-white hover:bg-emerald-800 hover:text-white"
            data-testid="report-share-send"
          >
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <MessageCircle className="size-4 shrink-0" aria-hidden />}
            {sendLabel}
          </Button>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noopener"
                className="inline-flex items-center gap-1.5 py-1.5 text-sm font-medium text-cyan-800 hover:underline"
              >
                <ExternalLink className="size-4" aria-hidden />
                Raporu önizle
              </a>
            ) : null}
            <button
              type="button"
              onClick={pdf}
              disabled={pdfBusy}
              className="inline-flex items-center gap-1.5 py-1.5 text-sm font-medium text-slate-700 hover:underline disabled:opacity-60"
            >
              {pdfBusy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Download className="size-4" aria-hidden />}
              PDF&apos;i indir
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
