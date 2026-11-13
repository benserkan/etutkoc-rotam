"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, Loader2, MessageCircle, Phone, Send } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api";
import { buildShareLink, getShareTargets, messagingKeys } from "@/lib/api/messaging";
import type { ShareReportKind, ShareTargetItem } from "@/lib/types/messaging";
import { buildPdfFromPrint } from "@/lib/pdf-from-print";
import { cn } from "@/lib/utils";

/**
 * Raporu PDF olarak veliye WhatsApp'tan gönder (2026-11-12).
 *
 * PDF yazdırma sayfasından tarayıcıda üretilir (öğrenci programındaki yöntem —
 * çıktı yazdırma sayfasıyla birebir). Koç kişiyi seçer:
 *  - telefonda: PDF dosyası sistem paylaşımıyla doğrudan WhatsApp'a gider;
 *  - bilgisayarda: PDF iner, seçilen velinin sohbeti mesaj hazır açılır,
 *    dosya ataç simgesinden eklenir.
 * Her gönderim denetim kaydına düşer (kim, hangi öğrencinin hangi raporu, kime).
 */
export function ShareReportDialog({
  open,
  onClose,
  studentId,
  kind,
  refId,
  printUrl,
  fileName,
  title,
  message,
  orientation = "portrait",
}: {
  open: boolean;
  onClose: () => void;
  studentId: number;
  kind: ShareReportKind;
  refId?: number | null;
  /** Veliye uygun yazdırma sayfası (koça özel içerik içermemeli). */
  printUrl: string;
  fileName: string;
  title: string;
  /** Mesaj metninin önerilen hâli — koç düzenleyebilir. */
  message: string;
  orientation?: "portrait" | "landscape";
}) {
  if (!open) return null;
  return (
    <Inner
      onClose={onClose}
      studentId={studentId}
      kind={kind}
      refId={refId ?? null}
      printUrl={printUrl}
      fileName={fileName}
      title={title}
      message={message}
      orientation={orientation}
    />
  );
}

export const SELF = 0; // "kişiyi WhatsApp'ta kendim seçeceğim"

/** "Kime?" listesi — veliler + öğrencinin kendisi + "kişiyi kendim seçeceğim". */
export function ShareRecipients({
  loading,
  error,
  targets,
  selected,
  onPick,
}: {
  loading: boolean;
  error: boolean;
  targets: ShareTargetItem[];
  selected: number;
  onPick: (id: number) => void;
}) {
  return (
  <section className="grid gap-2" data-testid="share-recipients">
    <h3 className="text-sm font-semibold text-slate-900">Kime?</h3>
    {loading ? (
      <p className="text-sm text-muted-foreground">Kişiler yükleniyor…</p>
    ) : error ? (
      <p className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-800">
        Kişiler yüklenemedi.
      </p>
    ) : (
      <div className="grid gap-1.5">
        {targets.map((t) => {
          const disabled = !t.can_message;
          return (
            <label
              key={t.user_id}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 text-sm",
                selected === t.user_id ? "border-emerald-600 bg-emerald-50" : "border-border",
                disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="radio"
                name="share-target"
                className="mt-1"
                checked={selected === t.user_id}
                disabled={disabled}
                onChange={() => onPick(t.user_id)}
              />
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-slate-900">
                  {t.full_name} <span className="font-normal text-slate-600">· {t.relation_label}</span>
                </span>
                <span className="flex items-center gap-1 text-xs text-slate-600">
                  <Phone className="size-3" aria-hidden />
                  {t.phone_masked ?? "Telefon numarası kayıtlı değil"}
                </span>
              </span>
            </label>
          );
        })}
        <label
          className={cn(
            "flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2 text-sm",
            selected === SELF ? "border-emerald-600 bg-emerald-50" : "border-border",
          )}
        >
          <input
            type="radio"
            name="share-target"
            className="mt-1"
            checked={selected === SELF}
            onChange={() => onPick(SELF)}
          />
          <span className="text-slate-900">Kişiyi WhatsApp&apos;ta kendim seçeceğim</span>
        </label>
      </div>
    )}
  </section>
  );
}

function Inner({
  onClose, studentId, kind, refId, printUrl, fileName, title, message, orientation,
}: {
  onClose: () => void;
  studentId: number;
  kind: ShareReportKind;
  refId: number | null;
  printUrl: string;
  fileName: string;
  title: string;
  message: string;
  orientation: "portrait" | "landscape";
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [pdfError, setPdfError] = React.useState(false);
  const [text, setText] = React.useState(message);
  const [picked, setPicked] = React.useState<number | null>(null);
  const [busy, setBusy] = React.useState(false);

  const targetsQ = useQuery({
    queryKey: messagingKeys.shareTargets(studentId),
    queryFn: () => getShareTargets(studentId),
  });
  const targets = React.useMemo(() => targetsQ.data?.targets ?? [], [targetsQ.data]);
  // Varsayılan: numarası kayıtlı ilk veli; yoksa kişiyi WhatsApp'ta seç.
  const defaultPick = React.useMemo(() => {
    const p = targets.find((t) => t.can_message && t.relation_label !== "Öğrencinin kendisi");
    return p ? p.user_id : SELF;
  }, [targets]);
  const selected = picked ?? defaultPick;
  const selectedTarget = targets.find((t) => t.user_id === selected) ?? null;

  React.useEffect(() => {
    let alive = true;
    buildPdfFromPrint(printUrl, orientation)
      .then((blob) => {
        if (alive) setFile(new File([blob], fileName, { type: "application/pdf" }));
      })
      .catch(() => {
        if (alive) setPdfError(true);
      });
    return () => {
      alive = false;
    };
  }, [printUrl, orientation, fileName]);

  // Telefonda tek yol: dosya paylaşımı (WhatsApp'a PDF doğrudan gider). Bilgisayarda tek yol:
  // PDF iner + sohbet açılır. WhatsApp bağlantıyla dosya eklemeye izin vermez; iki düğme
  // aynı anda gösterilince koç hangisinin dosyayı ekleyeceğini bilemiyordu (2026-11-13).
  const isTouch =
    typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches === true;
  const canShareFile =
    isTouch &&
    file != null &&
    typeof navigator !== "undefined" &&
    typeof navigator.canShare === "function" &&
    navigator.canShare({ files: [file] });

  function download() {
    if (!file) return;
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }

  async function record(targetId: number | null) {
    return buildShareLink({
      student_id: studentId,
      kind,
      text,
      target_user_id: targetId,
      ref_id: refId,
    });
  }

  function errorText(e: unknown): string {
    if (e instanceof ApiError && e.message) return e.message;
    return "Bağlantı hazırlanamadı.";
  }

  /** Telefon: PDF sistem paylaşımıyla (WhatsApp seçilir). */
  async function shareFile() {
    if (!file) return;
    setBusy(true);
    try {
      await record(selectedTarget?.can_message ? selectedTarget.user_id : null).catch(() => null);
      await navigator.share({ files: [file], title, text });
      toast.success("Paylaşım açıldı.");
      onClose();
    } catch (e) {
      if ((e as Error)?.name !== "AbortError") toast.error("Paylaşım açılamadı — PDF'i indirip WhatsApp'tan ekleyebilirsin.");
    } finally {
      setBusy(false);
    }
  }

  /** Bilgisayar (ya da telefonda sohbet): PDF iner, seçilen kişinin sohbeti açılır. */
  async function openChat() {
    // Açılır pencere engelini aşmak için pencere tıklama anında açılır.
    const win = window.open("about:blank", "_blank");
    setBusy(true);
    try {
      const res = await record(selected === SELF ? null : selected);
      if (file) download();
      if (win) win.location.href = res.wa_url;
      else window.open(res.wa_url, "_blank", "noopener");
      toast.success(
        !file
          ? "WhatsApp açıldı — mesaj hazır. PDF'i yazdırma sayfasından kaydedip ekleyebilirsin."
          : res.target_name
            ? `PDF indirildi. ${res.target_name} ile sohbet açıldı — dosyayı ataç simgesinden ekle.`
            : "PDF indirildi. WhatsApp'ta kişiyi seç, dosyayı ataç simgesinden ekle.",
      );
      onClose();
    } catch (e) {
      win?.close();
      toast.error(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const chatLabel =
    selected === SELF || !selectedTarget
      ? "PDF'i indir ve WhatsApp'ı aç"
      : `PDF'i indir, ${firstName(selectedTarget.full_name)} ile sohbeti aç`;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-h-[92vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Veliye WhatsApp&apos;tan gönder</DialogTitle>
          <DialogDescription>
            {`${title}, PDF olarak hazırlanır ve senin WhatsApp'ından gönderilir.`}
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
          <label htmlFor="share-text" className="text-sm font-semibold text-slate-900">
            Mesaj
          </label>
          <textarea
            id="share-text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={4}
            maxLength={1500}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
          />
        </section>

        {pdfError ? (
          <div className="grid gap-2">
            <p className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-800">
              PDF hazırlanamadı. Mesajı yine de gönderebilir, karneyi yazdırma sayfasından
              “PDF olarak kaydet” ile kaydedip ekleyebilirsin.
            </p>
            <Button
              type="button"
              onClick={openChat}
              disabled={busy}
              className="h-auto min-h-11 whitespace-normal bg-emerald-700 py-2 text-white hover:bg-emerald-800 hover:text-white"
              data-testid="share-open-chat"
            >
              <MessageCircle className="size-4 shrink-0" aria-hidden />
              {selected === SELF || !selectedTarget
                ? "Mesajı WhatsApp'ta aç"
                : `Mesajı ${firstName(selectedTarget.full_name)} ile sohbette aç`}
            </Button>
            <a
              href={printUrl}
              target="_blank"
              rel="noopener"
              className="text-center text-sm font-medium text-cyan-800 underline"
            >
              Yazdırma sayfasını aç
            </a>
          </div>
        ) : !file ? (
          <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-3 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            PDF hazırlanıyor…
          </div>
        ) : (
          <div className="grid gap-2">
            {canShareFile ? (
              <Button
                type="button"
                onClick={shareFile}
                disabled={busy}
                className="h-11 bg-emerald-700 text-white hover:bg-emerald-800 hover:text-white"
                data-testid="share-file"
              >
                <Send className="size-4" aria-hidden />
                PDF&apos;i WhatsApp&apos;ta paylaş
              </Button>
            ) : (
              <>
                <Button
                  type="button"
                  onClick={openChat}
                  disabled={busy}
                  className="h-auto min-h-11 whitespace-normal bg-emerald-700 py-2 text-white hover:bg-emerald-800 hover:text-white"
                  data-testid="share-open-chat"
                >
                  <MessageCircle className="size-4 shrink-0" aria-hidden />
                  {chatLabel}
                </Button>
                <p className="rounded-md bg-amber-500/10 px-3 py-2 text-xs text-amber-900">
                  WhatsApp, bağlantıyla açılan sohbete dosyayı kendiliğinden eklemez. Sohbet açılınca
                  indirilen PDF&apos;i pencereye sürükle ya da ataç simgesinden ekle.
                </p>
              </>
            )}
            <Button type="button" variant="ghost" onClick={download} className="h-10" data-testid="share-download">
              <Download className="size-4" aria-hidden />
              Yalnız PDF&apos;i indir
            </Button>
            <p className="text-center text-[11px] text-muted-foreground">
              {fileName} · {Math.max(1, Math.round(file.size / 1024))} KB
              {canShareFile && selectedTarget && selected !== SELF
                ? ` · paylaşımda ${firstName(selectedTarget.full_name)} kişisini seç`
                : ""}
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function firstName(full: string): string {
  return (full || "").trim().split(/\s+/)[0] || full;
}
