"use client";

import * as React from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface FilterValues {
  q: string;
  grade_level: string; // "" | "5" .. "12" | "graduate"
  risk: "all" | "ok" | "medium" | "high" | "critical";
  page_size: 25 | 50 | 100;
}

interface Props {
  initial: FilterValues;
}

const RISK_OPTIONS: Array<{ value: FilterValues["risk"]; label: string }> = [
  { value: "all", label: "Tüm risk seviyeleri" },
  { value: "ok", label: "Yolunda" },
  { value: "medium", label: "Orta" },
  { value: "high", label: "Yüksek" },
  { value: "critical", label: "Kritik" },
];

const GRADE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "Tüm sınıflar" },
  { value: "5", label: "5. sınıf" },
  { value: "6", label: "6. sınıf" },
  { value: "7", label: "7. sınıf" },
  { value: "8", label: "8. sınıf (LGS)" },
  { value: "9", label: "9. sınıf" },
  { value: "10", label: "10. sınıf" },
  { value: "11", label: "11. sınıf" },
  { value: "12", label: "12. sınıf" },
];

const PAGE_SIZE_OPTIONS: Array<{ value: 25 | 50 | 100; label: string }> = [
  { value: 25, label: "25 / sayfa" },
  { value: 50, label: "50 / sayfa" },
  { value: 100, label: "100 / sayfa" },
];

/**
 * Öğrenci listesi filtre çubuğu — URL search params ile senkron.
 *
 * Arama metni `useTransition` ile yumuşatılır: tetiklenen `router.replace`
 * non-urgent transition içinde — kullanıcı yazarken input bloklamaz.
 * `useDeferredValue` 300ms debounce için uygun değil; `setTimeout` ile
 * gerçek debounce uygulanır, transition input responsiveness'i korur.
 *
 * Filtre değişimleri `page` paramını silmez — `students-list-client`
 * sayfayı 1'e döndürmek için kendi mantığını kullanır (queryKey değişimi
 * pagination yi 1 yapar; client'ta `page` querystring'i temizleyenmiyoruz
 * çünkü kullanıcı geri tuşunda eski sayfaya dönebilsin).
 */
export function StudentsFilterBar({ initial }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const urlQ = searchParams.get("q") ?? "";
  const [qInput, setQInput] = React.useState(initial.q);
  const [lastSyncedUrlQ, setLastSyncedUrlQ] = React.useState(initial.q);
  const [, startTransition] = React.useTransition();
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // URL → input yeniden sync (geri/ileri tuşu). React 19 önerisi: "adjust
  // state during rendering" — effect içinde setState yasak (R19 lint rule
  // `react-hooks/set-state-in-effect`). Önceki URL değerini bir state'te
  // tutuyoruz; sadece gerçekten değiştiğinde setQInput tetiklenir.
  if (urlQ !== lastSyncedUrlQ) {
    setLastSyncedUrlQ(urlQ);
    setQInput(urlQ);
  }

  const applyParam = React.useCallback(
    (mutate: (sp: URLSearchParams) => void, resetPage = true) => {
      const sp = new URLSearchParams(searchParams.toString());
      mutate(sp);
      if (resetPage) sp.delete("page");
      const qs = sp.toString();
      startTransition(() => {
        router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
      });
    },
    [pathname, router, searchParams],
  );

  // Arama input — debounced (300ms) + transition
  const onChangeQ = React.useCallback(
    (v: string) => {
      setQInput(v);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        applyParam((sp) => {
          const trimmed = v.trim();
          if (trimmed) sp.set("q", trimmed);
          else sp.delete("q");
        });
      }, 300);
    },
    [applyParam],
  );

  React.useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  function onChangeGrade(v: string) {
    applyParam((sp) => {
      if (v) sp.set("grade_level", v);
      else sp.delete("grade_level");
    });
  }

  function onChangeRisk(v: FilterValues["risk"]) {
    applyParam((sp) => {
      if (v && v !== "all") sp.set("risk", v);
      else sp.delete("risk");
    });
  }

  function onChangePageSize(v: number) {
    applyParam((sp) => {
      if (v === 25) sp.delete("page_size");
      else sp.set("page_size", String(v));
    });
  }

  function onClear() {
    setQInput("");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    startTransition(() => {
      router.replace(pathname, { scroll: false });
    });
  }

  const hasAnyFilter =
    !!initial.q ||
    !!initial.grade_level ||
    initial.risk !== "all" ||
    initial.page_size !== 25;

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Input
        type="search"
        placeholder="Ad veya e-posta…"
        value={qInput}
        onChange={(e) => onChangeQ(e.target.value)}
        className="w-full sm:w-64"
        aria-label="Öğrenci ara"
      />
      <Select
        value={initial.grade_level}
        onChange={onChangeGrade}
        options={GRADE_OPTIONS}
        ariaLabel="Sınıf filtresi"
      />
      <Select
        value={initial.risk}
        onChange={(v) => onChangeRisk(v as FilterValues["risk"])}
        options={RISK_OPTIONS as Array<{ value: string; label: string }>}
        ariaLabel="Risk filtresi"
      />
      <Select
        value={String(initial.page_size)}
        onChange={(v) => onChangePageSize(Number(v))}
        options={PAGE_SIZE_OPTIONS.map((o) => ({ value: String(o.value), label: o.label }))}
        ariaLabel="Sayfa boyutu"
      />
      {hasAnyFilter ? (
        <button
          type="button"
          onClick={onClear}
          className="text-xs text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
        >
          Filtreleri temizle
        </button>
      ) : null}
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  ariaLabel: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-9 rounded-md border border-input bg-background px-2 text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
