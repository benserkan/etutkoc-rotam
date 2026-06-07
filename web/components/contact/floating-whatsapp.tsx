"use client";

import { MessageCircle } from "lucide-react";

/**
 * Public sayfalarda (landing / pricing / iletisim) sağ-altta sabit WhatsApp
 * butonu. Numara (catalog.contact.whatsapp) boşsa hiç render edilmez.
 * Mesaj ASCII-güvenli (emoji yok — bazı cihazlarda tofu).
 */
export function FloatingWhatsApp({
  phone,
  message = "Merhaba, ETÜTKOÇ Rotam hakkında bilgi almak istiyorum.",
}: {
  phone?: string | null;
  message?: string;
}) {
  const digits = (phone ?? "").replace(/[^0-9]/g, "");
  if (!digits) return null;
  const href = `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="WhatsApp ile yazın"
      className="fixed bottom-5 right-5 z-50 inline-flex items-center gap-2 rounded-full bg-[#25D366] px-4 py-3 font-semibold text-white shadow-lg shadow-emerald-900/20 ring-1 ring-black/5 transition hover:scale-105 hover:bg-[#20bd5a] active:scale-95"
    >
      <MessageCircle className="size-6" aria-hidden />
      <span className="hidden pr-1 text-sm sm:inline">WhatsApp</span>
    </a>
  );
}
