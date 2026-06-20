"use client";

/**
 * Görev tamamlama bottom-sheet'i — "Akıllı Onay".
 *
 * Mobil-öncelikli tasarım:
 *  - "Çözdüm" stepper (büyük +/- tuşları, planlanan sayı default)
 *  - "Doğru" / "Yanlış" iki opsiyonel input (akıllı tamamlama: birini gir →
 *    diğeri otomatik hesap)
 *  - "Kaydet" (D/Y dahil) veya "Sadece tamamla" (D/Y atla)
 *  - Deneme görevlerinde "Sadece tamamla" linki gizlenir — D/Y daha kritik
 *
 * Kullanım hem öğrenci (kendi görevini tamamlar) hem koç (sonradan düzenler):
 *  - Öğrenci: ilk açılış default (completed=planned, D/Y null)
 *  - Koç: edit mode — mevcut değerlerle pre-fill
 */

import * as React from "react";
import { createPortal } from "react-dom";
import { Check, Minus, Plus, X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface CompleteSheetResult {
  completed: number;
  correct: number | null;
  wrong: number | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (r: CompleteSheetResult) => void;
  // Görev/kalem bilgisi (header'da gösterilir)
  taskTitle: string;
  itemLabel?: string | null;     // "Matematik · Türev" vb.
  planned: number;
  // İlk değerler — koç edit modunda mevcut değerleri pre-fill için.
  initialCompleted?: number;
  initialCorrect?: number | null;
  initialWrong?: number | null;
  // Deneme tipi mi? (Sadece tamamla linkini gizlemek için)
  // Aynı zamanda completed birimini belirler:
  //   - true (kitapsız deneme): completed = soru sayısı, D/Y aynı birim → c+w ≤ completed
  //   - false (kitaplı görev): completed = test sayısı, D/Y = soru sayısı (bağımsız) → kural yok
  isDeneme?: boolean;
  // "Sadece tamamla" — D/Y atla seçeneği gösterilsin mi? (default: true; deneme'de false)
  allowSkipResult?: boolean;
  // pending state
  saving?: boolean;
}

export function CompleteSheet(props: Props) {
  // Outer wrapper sadece visibility kontrol eder; inner component her açılışta
  // remount olur → useState initial values her seferinde props'tan doğru başlar
  // (set-state-in-effect kuralından kaçınma deseni).
  //
  // KRİTİK: Portal ile <body>'e render edilir — aksi halde sortable item
  // (dnd-kit useSortable) `transform` stili "fixed" konumlanmayı viewport'tan
  // koparır ve sheet ata kapsayıcıya göre konumlanır → mobil'de alta düşer.
  if (!props.open) return null;
  if (typeof document === "undefined") return null; // SSR guard
  return createPortal(<CompleteSheetInner {...props} />, document.body);
}

function CompleteSheetInner({
  onClose,
  onSubmit,
  taskTitle,
  itemLabel,
  planned,
  initialCompleted,
  initialCorrect,
  initialWrong,
  isDeneme = false,
  allowSkipResult,
  saving = false,
}: Props) {
  const skipEnabled = allowSkipResult ?? !isDeneme;

  const [completed, setCompleted] = React.useState<number>(
    initialCompleted ?? planned,
  );
  const [correctStr, setCorrectStr] = React.useState<string>(
    initialCorrect != null ? String(initialCorrect) : "",
  );
  const [wrongStr, setWrongStr] = React.useState<string>(
    initialWrong != null ? String(initialWrong) : "",
  );

  // Body scroll lock — arka plan kaymasın. Sheet kapanınca eski overflow geri.
  React.useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    const prevTouchAction = document.body.style.touchAction;
    document.body.style.overflow = "hidden";
    document.body.style.touchAction = "none";
    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.touchAction = prevTouchAction;
    };
  }, []);

  // ESC ile kapat (masaüstü erişilebilirlik)
  React.useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Birim:
  //   - Kitapsız deneme (isDeneme=true): completed = soru sayısı, D/Y aynı birim
  //     → c + w ≤ completed kuralı geçerli; akıllı tamamla aktif
  //   - Kitaplı görev (isDeneme=false): completed = test sayısı, D/Y = soru sayısı
  //     → c + w üst sınır YOK (bağımsız metric); akıllı tamamla mantıksız
  const completedLabel = isDeneme ? "Çözdüğüm soru" : "Çözdüğüm test";
  const tamButtonLabel = isDeneme ? `Tam (${planned})` : `Tam (${planned} test)`;

  const correct = correctStr === "" ? null : Number(correctStr);
  const wrong = wrongStr === "" ? null : Number(wrongStr);

  // Akıllı tamamla yalnız Deneme'de (aynı birim) — kitaplı testte completed=3
  // ise "yanlış = 3 - 0 = 3" önerisi yanlış olur.
  function onCorrectChange(v: string) {
    setCorrectStr(v);
    if (!isDeneme) return;
    const n = Number(v);
    if (v !== "" && Number.isFinite(n) && n >= 0 && n <= completed) {
      if (wrongStr === "") {
        setWrongStr(String(Math.max(0, completed - n)));
      }
    }
  }

  function onWrongChange(v: string) {
    setWrongStr(v);
    if (!isDeneme) return;
    const n = Number(v);
    if (v !== "" && Number.isFinite(n) && n >= 0 && n <= completed) {
      if (correctStr === "") {
        setCorrectStr(String(Math.max(0, completed - n)));
      }
    }
  }

  function adjustCompleted(delta: number) {
    setCompleted((c) => Math.max(0, c + delta));
  }

  // Validation
  //   - c ≥ 0, w ≥ 0 (her durumda)
  //   - c + w ≤ completed (yalnız Deneme'de — aynı birim)
  const totalAnswered = (correct ?? 0) + (wrong ?? 0);
  const negativeInput =
    (correct != null && correct < 0) || (wrong != null && wrong < 0);
  const denemeOverflow = isDeneme && totalAnswered > completed;
  const invalidDistribution = negativeInput || denemeOverflow;

  function handleSave() {
    if (invalidDistribution || saving) return;
    onSubmit({ completed, correct, wrong });
  }

  function handleSkipResult() {
    if (saving) return;
    onSubmit({ completed, correct: null, wrong: null });
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label="Görev tamamlama"
    >
      {/* Backdrop */}
      <button
        type="button"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-label="Kapat"
        tabIndex={-1}
      />
      {/* Sheet — her ekranda CENTER (mobilde de). p-3 dış margin ile sheet
          her zaman ekrandan en az 0.75rem boşluk bırakır → DevTools/alt-chrome
          (mobil tarayıcı UI) hesaba katılır.
          Flex column: header (shrink-0) + body (flex-1, scroll) + footer (shrink-0).
          Yükseklik: dvh (dynamic viewport, iOS Safari adres çubuğu hesabıyla)
          - dış padding payı (üst+alt = 1.5rem mobilde, 3rem masaüstünde). */}
      <div
        className={cn(
          "relative w-full max-w-md bg-card rounded-2xl shadow-2xl",
          "border border-border flex flex-col",
          "max-h-[calc(100dvh-1.5rem)] sm:max-h-[calc(100dvh-3rem)]",
        )}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-border/60 bg-card flex items-start justify-between gap-3 shrink-0">
          <div className="flex-1 min-w-0">
            <h2 className="text-base font-semibold text-foreground truncate">
              {taskTitle}
            </h2>
            {itemLabel ? (
              <p className="text-xs text-muted-foreground truncate mt-0.5">
                {itemLabel}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex-shrink-0 size-8 inline-flex items-center justify-center rounded-md hover:bg-muted transition"
            aria-label="Kapat"
          >
            <X className="size-4" aria-hidden />
          </button>
        </div>

        {/* Body — flex-1 + overflow-y-auto: alanın ortasında kaydırılır.
            Üst/alt sabit kalır, içerik klavye açılınca taşmaz. */}
        <div className="px-5 py-4 space-y-5 flex-1 overflow-y-auto">
          {/* Çözdüm — büyük stepper */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-medium mb-2">
              {completedLabel}
            </label>
            <div className="flex items-center gap-3 justify-center">
              <button
                type="button"
                onClick={() => adjustCompleted(-1)}
                className="size-12 rounded-lg border border-border bg-card hover:bg-muted transition disabled:opacity-30 inline-flex items-center justify-center"
                disabled={completed <= 0}
                aria-label="Bir azalt"
              >
                <Minus className="size-5" aria-hidden />
              </button>
              <div className="flex-1 max-w-[160px]">
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={completed}
                  onChange={(e) => {
                    const n = Number(e.target.value);
                    setCompleted(Number.isFinite(n) ? Math.max(0, n) : 0);
                  }}
                  className="w-full text-3xl font-bold text-center tabular-nums py-3 border border-input bg-background rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>
              <button
                type="button"
                onClick={() => adjustCompleted(1)}
                className="size-12 rounded-lg border border-border bg-card hover:bg-muted transition inline-flex items-center justify-center"
                aria-label="Bir artır"
              >
                <Plus className="size-5" aria-hidden />
              </button>
            </div>
            <div className="mt-1.5 flex justify-center gap-1.5">
              {planned > 0 ? (
                <button
                  type="button"
                  onClick={() => setCompleted(planned)}
                  className={cn(
                    "text-[11px] px-2 py-0.5 rounded border transition",
                    completed === planned
                      ? "bg-foreground text-background border-foreground"
                      : "border-border text-muted-foreground hover:bg-muted",
                  )}
                >
                  {tamButtonLabel}
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setCompleted(0)}
                className={cn(
                  "text-[11px] px-2 py-0.5 rounded border transition",
                  completed === 0
                    ? "bg-foreground text-background border-foreground"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                Sıfır
              </button>
            </div>
          </div>

          {/* D/Y — opsiyonel; her zaman SORU sayısı (test sayısından bağımsız) */}
          <div>
            <label className="block text-xs uppercase tracking-wider text-muted-foreground font-medium mb-1">
              Sorularda sonuç{" "}
              <span className="text-[10px] normal-case text-muted-foreground/70">
                (opsiyonel)
              </span>
            </label>
            <p className="text-[11px] text-muted-foreground mb-2">
              {isDeneme
                ? "Çözdüğün sorulardan kaçı doğru / yanlış?"
                : "Çözdüğün testlerdeki toplam doğru / yanlış soru sayısı."}
            </p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="block text-[11px] text-emerald-700 font-medium mb-1">
                  Doğru
                </span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={correctStr}
                  onChange={(e) => onCorrectChange(e.target.value)}
                  placeholder="—"
                  className="w-full text-2xl font-bold text-center tabular-nums py-2.5 border border-emerald-200 bg-emerald-50/50 rounded-lg text-emerald-900 placeholder:text-emerald-300 focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
              <div>
                <span className="block text-[11px] text-rose-700 font-medium mb-1">
                  Yanlış
                </span>
                <input
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={wrongStr}
                  onChange={(e) => onWrongChange(e.target.value)}
                  placeholder="—"
                  className="w-full text-2xl font-bold text-center tabular-nums py-2.5 border border-rose-200 bg-rose-50/50 rounded-lg text-rose-900 placeholder:text-rose-300 focus:outline-none focus:ring-2 focus:ring-rose-500"
                />
              </div>
            </div>
            {/* Boş soru hesabı — yalnız Deneme dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200'de (aynı birim) anlamlı */}
            {isDeneme &&
            correct != null &&
            wrong != null &&
            (correct + wrong) < completed ? (
              <p className="text-[11px] text-muted-foreground mt-2 text-center">
                Boş bıraktığın:{" "}
                <span className="font-medium tabular-nums">
                  {completed - correct - wrong}
                </span>
              </p>
            ) : null}
            {negativeInput ? (
              <p className="text-[11px] text-rose-700 mt-2 text-center font-medium">
                Doğru ve yanlış sayıları negatif olamaz
              </p>
            ) : denemeOverflow ? (
              <p className="text-[11px] text-rose-700 mt-2 text-center font-medium">
                Doğru + Yanlış ({totalAnswered}) çözdüğünden ({completed} soru) fazla olamaz
              </p>
            ) : null}
          </div>
        </div>

        {/* Footer — sabit; iOS home-indicator safe-area dahil */}
        <div
          className="px-5 py-4 border-t border-border/60 bg-card shrink-0 flex flex-col gap-2"
          style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
        >
          <button
            type="button"
            onClick={handleSave}
            disabled={invalidDistribution || saving}
            className="w-full inline-flex items-center justify-center gap-2 py-3 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-700 disabled:opacity-40 transition"
          >
            <Check className="size-4" aria-hidden />
            {saving ? "Kaydediliyor..." : "Kaydet"}
          </button>
          {skipEnabled ? (
            <button
              type="button"
              onClick={handleSkipResult}
              disabled={saving}
              className="w-full py-2 text-sm text-muted-foreground hover:text-foreground transition disabled:opacity-40"
            >
              Sadece tamamla (sonuç girme)
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
