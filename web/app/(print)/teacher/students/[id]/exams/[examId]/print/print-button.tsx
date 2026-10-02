"use client";

import { Printer } from "lucide-react";

/** Yazdır / PDF olarak kaydet — çıktıda gizli (.no-print). */
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print inline-flex items-center gap-2 rounded-md bg-stone-800 px-4 py-2 text-sm font-semibold text-white transition hover:bg-stone-700"
    >
      <Printer className="size-4" aria-hidden />
      Yazdır / PDF olarak kaydet
    </button>
  );
}
