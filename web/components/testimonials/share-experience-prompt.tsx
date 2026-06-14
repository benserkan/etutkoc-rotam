"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Star, MessageSquareHeart, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  getTestimonialPrompt,
  submitTestimonial,
  testimonialKeys,
} from "@/lib/api/testimonials";

const DISMISS_KEY = "etk_share_experience_dismissed_v1";

const SELECT_CLS =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring";

/**
 * "Deneyimini paylaş" istemi — öğrenci/veli/koç/kurum yöneticisi ana ekranlarına
 * konulan kendi-kendini-gizleyen kart. Sunucu uygunluğu (rol + hesap yaşı ≥7 gün +
 * daha önce gönderim yok) + tarayıcı dismiss kontrolü. Gönderilince/kapatılınca
 * bir daha çıkmaz. Yorum `pending` düşer, süper admin yayınlar.
 */
export function ShareExperiencePrompt() {
  // Lazy initializer: localStorage'ı render'da bir kez oku (effect'te setState
  // yok → set-state-in-effect lint'i geçer). Kart zaten `eligible` (client-only
  // useQuery) sonucuna bağlı olduğundan SSR'da görünmez → hidrasyon uyuşmazlığı yok.
  const [dismissed, setDismissed] = React.useState<boolean>(() => {
    try {
      return typeof window !== "undefined" && window.localStorage.getItem(DISMISS_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [open, setOpen] = React.useState(false);
  const [done, setDone] = React.useState(false);

  const q = useQuery({
    queryKey: testimonialKeys.prompt(),
    queryFn: getTestimonialPrompt,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const eligible = q.data?.eligible === true;
  const defaultName = q.data?.default_name ?? "";

  function dismiss() {
    try {
      window.localStorage.setItem(DISMISS_KEY, "1");
    } catch {
      /* yoksay */
    }
    setDismissed(true);
  }

  if (dismissed || done || !eligible) return null;

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-cyan-200 bg-cyan-50/70 p-4 dark:border-cyan-900/50 dark:bg-cyan-950/30">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300">
          <MessageSquareHeart className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">Deneyimini paylaşır mısın?</p>
          <p className="text-xs text-muted-foreground">
            ETÜTKOÇ sana nasıl yardımcı oldu? Birkaç cümlelik yorumun yeni kullanıcılara yol gösterir.
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <Button size="sm" onClick={() => setOpen(true)}>
            Yorum yaz
          </Button>
          <button
            type="button"
            onClick={dismiss}
            aria-label="Kapat"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>
      </div>

      {open ? (
        <ShareDialog
          defaultName={defaultName}
          onClose={() => setOpen(false)}
          onDone={() => {
            setDone(true);
            setOpen(false);
          }}
        />
      ) : null}
    </>
  );
}

function ShareDialog({
  defaultName,
  onClose,
  onDone,
}: {
  defaultName: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [rating, setRating] = React.useState(0);
  const [content, setContent] = React.useState("");
  const [name, setName] = React.useState(defaultName);
  const [consent, setConsent] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const canSubmit = content.trim().length >= 10 && name.trim().length >= 2 && consent;

  async function submit() {
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    try {
      await submitTestimonial({
        content: content.trim(),
        rating: rating || null,
        author_name: name.trim(),
        consent_public: consent,
      });
      onDone();
    } catch {
      setError("Gönderilemedi. Lütfen tekrar dene.");
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deneyimini paylaş</DialogTitle>
          <DialogDescription>
            Yorumun incelendikten sonra anasayfada yayınlanabilir. Teşekkürler!
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Puanın</label>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-label={`${n} yıldız`}
                  onClick={() => setRating(n)}
                  className="p-0.5"
                >
                  <Star
                    className={cn(
                      "size-7 transition-colors",
                      n <= rating ? "fill-amber-400 text-amber-400" : "text-slate-300 hover:text-amber-300",
                    )}
                    aria-hidden
                  />
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Yorumun</label>
            <textarea
              className={cn(SELECT_CLS, "min-h-[110px] resize-y")}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="ETÜTKOÇ sana nasıl yardımcı oldu? (en az 10 karakter)"
              maxLength={2000}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium">Görünen adın</label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Örn. Zeynep A."
              maxLength={160}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              İstersen yalnız adının baş harfini yazabilirsin (örn. “Zeynep A.”).
            </p>
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5 size-4"
            />
            <span>
              Yorumumun ve görünen adımın <strong>anasayfada yayınlanmasına</strong> onay
              veriyorum (KVKK).
            </span>
          </label>

          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button onClick={submit} disabled={!canSubmit || busy}>
            {busy ? "Gönderiliyor…" : "Gönder"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
