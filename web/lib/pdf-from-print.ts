/** Yazdırma sayfasını görünmez çerçevede yükleyip A4 PDF'e çevirir. */
export async function buildPdfFromPrint(url: string, orientation: "landscape" | "portrait"): Promise<Blob> {
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

    const { toJpeg } = await import("html-to-image");
    // JPEG: PNG'ye göre ~20 kat küçük dosya (WhatsApp'a gönderilecek); metin okunurluğu korunur.
    const dataUrl = await toJpeg(main, {
      quality: 0.88,
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
      pdf.addImage(dataUrl, "JPEG", margin, margin, w, h);
    } else {
      // Uzun içerik: aynı görüntü sayfa sayfa kaydırılarak basılır.
      let offset = 0;
      let first = true;
      while (offset < h) {
        if (!first) pdf.addPage();
        pdf.addImage(dataUrl, "JPEG", margin, margin - offset, w, h);
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
