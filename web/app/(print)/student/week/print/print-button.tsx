"use client";

import { Printer } from "lucide-react";

/**
 * Yazdırma ekranında "Yazdır" butonu — window.print() çağırır (yatay A4).
 * `.no-print` ile çıktıda gizlenir.
 */
export function PrintButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="no-print inline-flex items-center gap-2 rounded-md bg-stone-800 px-4 py-2 text-sm font-semibold text-white hover:bg-stone-700 transition"
    >
      <Printer className="size-4" aria-hidden />
      Yazdır
    </button>
  );
}
