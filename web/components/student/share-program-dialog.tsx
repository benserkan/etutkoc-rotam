"use client";

import * as React from "react";
import { Download, Loader2, MessageCircle, Share2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

/**
 * Programı PDF olarak paylaş / indir (2026-10-21).
 *
 * PDF, yazdırma sayfasının (`printUrl`) görünmez bir çerçevede çizilip resme
 * çevrilmesiyle tarayıcıda üretilir — çıktı yazdırma sayfasıyla birebir aynıdır,
 * sunucuya iş düşmez. Telefonda sistem paylaşım menüsü (WhatsApp dahil) dosyayla
 * açılır; bilgisayarda dosya iner ve WhatsApp Web açılır (dosya oradan eklenir).
 *
 * Paylaşım menüsü kullanıcı dokunuşu ister: PDF önce hazırlanır, paylaş düğmesi
 * hazır dosyayla ikinci dokunuşta çalışır (uzun işlem dokunuş iznini düşürür).
 */
export function ShareProgramButton({
  printUrl,
  fileName,
  title,
  orientation = "landscape",
  label = "Paylaş",
}: {
  printUrl: string;
  fileName: string;
  title: string;
  orientation?: "landscape" | "portrait";
  label?: string;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        aria-label="Programı paylaş ya da PDF indir"
        data-testid="share-program"
      >
        <Share2 className="size-4" aria-hidden />
        {label}
      </Button>
      {open ? (
        <ShareDialog
          printUrl={printUrl}
          fileName={fileName}
          title={title}
          orientation={orientation}
          onClose={() => setOpen(false)}
        />
      ) : null}
    </>
  );
}

function ShareDialog({
  printUrl,
  fileName,
  title,
  orientation,
  onClose,
}: {
  printUrl: string;
  fileName: string;
  title: string;
  orientation: "landscape" | "portrait";
  onClose: () => void;
}) {
  const [file, setFile] = React.useState<File | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let alive = true;
    buildPdf(printUrl, orientation)
      .then((blob) => {
        if (alive) setFile(new File([blob], fileName, { type: "application/pdf" }));
      })
      .catch(() => {
        if (alive) setError("PDF hazırlanamadı. Yazdır menüsünden açıp “PDF olarak kaydet” seçebilirsin.");
      });
    return () => {
      alive = false;
    };
  }, [printUrl, orientation, fileName]);

  const canShareFile =
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

  async function share() {
    if (!file) return;
    if (canShareFile) {
      try {
        await navigator.share({ files: [file], title, text: title });
        onClose();
      } catch (e) {
        if ((e as Error)?.name !== "AbortError") toast.error("Paylaşım açılamadı — PDF'i indirip WhatsApp'tan ekleyebilirsin.");
      }
      return;
    }
    // Bilgisayar: dosya iner, WhatsApp Web açılır — dosya ataç simgesinden eklenir.
    download();
    window.open(`https://wa.me/?text=${encodeURIComponent(title)}`, "_blank", "noopener");
    toast.success("PDF indirildi — WhatsApp'ta ataç simgesinden ekleyebilirsin.");
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Programı paylaş</DialogTitle>
          <DialogDescription>
            Programın PDF olarak hazırlanır. WhatsApp&apos;ta paylaşabilir ya da cihazına indirebilirsin.
          </DialogDescription>
        </DialogHeader>
        {error ? (
          <p className="rounded-md bg-rose-500/10 px-3 py-2 text-sm text-rose-800 dark:text-rose-200">{error}</p>
        ) : !file ? (
          <div className="flex items-center gap-2 rounded-md bg-muted px-3 py-3 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden />
            PDF hazırlanıyor…
          </div>
        ) : (
          <div className="grid gap-2">
            <Button
              type="button"
              onClick={share}
              className="h-11 bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
              data-testid="share-whatsapp"
            >
              <MessageCircle className="size-4" aria-hidden />
              {canShareFile ? "WhatsApp'ta paylaş" : "WhatsApp'ta paylaş (PDF iner)"}
            </Button>
            <Button type="button" variant="outline" onClick={download} className="h-11" data-testid="share-download">
              <Download className="size-4" aria-hidden />
              PDF olarak indir
            </Button>
            <p className="text-center text-[11px] text-muted-foreground">
              {fileName} · {Math.max(1, Math.round(file.size / 1024))} KB
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Yazdırma sayfasını görünmez çerçevede yükleyip A4 PDF'e çevirir. */
async function buildPdf(url: string, orientation: "landscape" | "portrait"): Promise<Blob> {
  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.cssText = `position:fixed;left:-12000px;top:0;width:${orientation === "landscape" ? 1180 : 860}px;height:1000px;border:0;`;
  iframe.src = url;
  document.body.appendChild(iframe);
  try {
    await new Promise<void>((resolve, reject) => {
      const t = setTimeout(() => reject(new Error("timeout")), 30_000);
      iframe.onload = () => {
        clearTimeout(t);
        resolve();
      };
    });
    const doc = iframe.contentDocument;
    if (!doc) throw new Error("no document");
    await Promise.all(
      Array.from(doc.images).map((img) =>
        img.complete
          ? Promise.resolve()
          : new Promise<void>((r) => {
              img.onload = () => r();
              img.onerror = () => r();
            }),
      ),
    );
    await doc.fonts?.ready;
    const main = doc.querySelector("main") as HTMLElement | null;
    if (!main) throw new Error("no main");

    const { toPng } = await import("html-to-image");
    const dataUrl = await toPng(main, {
      pixelRatio: 2,
      backgroundColor: "#ffffff",
      skipFonts: true,
      filter: (node) => !((node as Element).classList?.contains("no-print") ?? false),
    });
    const img = await loadImage(dataUrl);

    const { jsPDF } = await import("jspdf");
    const pdf = new jsPDF({ orientation, unit: "mm", format: "a4" });
    const pageW = pdf.internal.pageSize.getWidth();
    const pageH = pdf.internal.pageSize.getHeight();
    const margin = 6;
    const w = pageW - margin * 2;
    const h = (img.height * w) / img.width;
    const usable = pageH - margin * 2;
    if (h <= usable) {
      pdf.addImage(dataUrl, "PNG", margin, margin, w, h);
    } else {
      // Uzun içerik: aynı görüntü sayfa sayfa kaydırılarak basılır.
      let offset = 0;
      let first = true;
      while (offset < h) {
        if (!first) pdf.addPage();
        pdf.addImage(dataUrl, "PNG", margin, margin - offset, w, h);
        offset += usable;
        first = false;
      }
    }
    return pdf.output("blob");
  } finally {
    iframe.remove();
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}
