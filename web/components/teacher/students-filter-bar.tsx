"use client";

import * as React from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Search, X } from "lucide-react";

import { cn } from "@/lib/utils";

export interface FilterValues {
  q: string;
  grade_level: string; // "" | "5" .. "12" | "graduate"
  risk: "all" | "ok" | "medium" | "high" | "critical" | "at_risk";
  /** Varsayılan "aktif" — pasifler (pratik/eski kayıtlar) listeyi
   *  kalabalıklaştırmasın; filtreyle açılır (2026-08-11 saha isteği). */
  status: "aktif" | "pasif" | "tum";
  /** "" = tüm şubeler · "__none__" = şubesiz · diğer = şube adı */
  class_group: string;
  page_size: 25 | 50 | 100;
}

interface Props {
  initial: FilterValues;
  classGroups?: { class_group: string | null; count: number }[];
}

const STATUS_OPTIONS: Array<{ value: FilterValues["status"]; label: string }> = [
  { value: "aktif", label: "Aktif" },
  { value: "pasif", label: "Pasif" },
  { value: "tum", label: "Tümü" },
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

const RISK_CHIP: Record<Exclude<FilterValues["risk"], "all">, string> = {
  critical: "Kritik",
  medium: "Uyarı",
  high: "Yüksek risk",
  at_risk: "Risk altı (uyarı + kritik)",
  ok: "Yolunda",
};

/**
 * URL search param güncelleyici — filtre çubuğu, durum kutuları ve sayfalama
 * aynı yolu kullanır. Filtre değişince sayfa 1'e döner.
 */
export function useApplyParam() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [pending, startTransition] = React.useTransition();
  const apply = React.useCallback(
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
  return { apply, pending };
}

/**
 * Öğrenci listesi araç çubuğu — URL search params ile senkron.
 * Arama 300ms debounce + transition (yazarken input bloklanmaz).
 * Risk süzgeci üstteki durum kutularındadır; burada yalnız etkin çip görünür.
 */
export function StudentsFilterBar({ initial, classGroups = [] }: Props) {
  const searchParams = useSearchParams();
  const { apply } = useApplyParam();

  const urlQ = searchParams.get("q") ?? "";
  const [qInput, setQInput] = React.useState(initial.q);
  const [lastSyncedUrlQ, setLastSyncedUrlQ] = React.useState(initial.q);
  const debounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // URL → input yeniden sync (geri/ileri). Effect içinde setState yerine
  // "render sırasında ayarla" deseni (react-hooks/set-state-in-effect).
  if (urlQ !== lastSyncedUrlQ) {
    setLastSyncedUrlQ(urlQ);
    setQInput(urlQ);
  }

  function onChangeQ(v: string) {
    setQInput(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      apply((sp) => {
        const trimmed = v.trim();
        if (trimmed) sp.set("q", trimmed);
        else sp.delete("q");
      });
    }, 300);
  }

  React.useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const setParam = (key: string, v: string, def = "") =>
    apply((sp) => {
      if (v && v !== def) sp.set(key, v);
      else sp.delete(key);
    });

  function onClear() {
    setQInput("");
    if (debounceRef.current) clearTimeout(debounceRef.current);
    apply((sp) => {
      for (const k of ["q", "grade_level", "class_group", "risk", "status", "page_size"]) sp.delete(k);
    });
  }

  const hasAnyFilter =
    !!initial.q ||
    !!initial.grade_level ||
    !!initial.class_group ||
    initial.risk !== "all" ||
    initial.status !== "aktif";

  const showGroups = classGroups.some((g) => g.class_group) || !!initial.class_group;

  return (
    <div className="space-y-2">
      <div className="flex flex-col gap-2 lg:flex-row lg:items-center">
        <div className="relative lg:w-80">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden
          />
          <input
            type="search"
            placeholder="Ad veya e-posta ile ara"
            value={qInput}
            onChange={(e) => onChangeQ(e.target.value)}
            aria-label="Öğrenci ara"
            className={cn(
              "h-10 w-full rounded-lg border border-input bg-background pl-9 pr-3 text-sm",
              "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={initial.grade_level}
            onChange={(v) => setParam("grade_level", v)}
            options={GRADE_OPTIONS}
            ariaLabel="Sınıf filtresi"
          />
          {showGroups ? (
            <Select
              value={initial.class_group}
              onChange={(v) => setParam("class_group", v)}
              options={[
                { value: "", label: "Tüm şubeler" },
                ...classGroups.map((g) => ({
                  value: g.class_group ?? "__none__",
                  label: `${g.class_group ?? "Şubesiz"} (${g.count})`,
                })),
                ...(initial.class_group &&
                !classGroups.some((g) => (g.class_group ?? "__none__") === initial.class_group)
                  ? [{ value: initial.class_group, label: initial.class_group === "__none__" ? "Şubesiz" : initial.class_group }]
                  : []),
              ]}
              ariaLabel="Şube filtresi"
            />
          ) : null}
          <div
            role="radiogroup"
            aria-label="Durum filtresi"
            className="inline-flex h-10 items-center rounded-lg border border-input bg-muted/60 p-1"
          >
            {STATUS_OPTIONS.map((o) => {
              const on = initial.status === o.value;
              return (
                <button
                  key={o.value}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  onClick={() => setParam("status", o.value, "aktif")}
                  className={cn(
                    "h-8 rounded-md px-3 text-sm transition-colors",
                    on
                      ? "bg-background font-medium text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {o.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {hasAnyFilter ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Etkin süzgeçler:</span>
          {initial.q ? <Chip label={`“${initial.q}”`} onRemove={() => { setQInput(""); setParam("q", ""); }} /> : null}
          {initial.grade_level ? (
            <Chip
              label={GRADE_OPTIONS.find((g) => g.value === initial.grade_level)?.label ?? initial.grade_level}
              onRemove={() => setParam("grade_level", "")}
            />
          ) : null}
          {initial.class_group ? (
            <Chip
              label={`Şube: ${initial.class_group === "__none__" ? "Şubesiz" : initial.class_group}`}
              onRemove={() => setParam("class_group", "")}
            />
          ) : null}
          {initial.risk !== "all" ? (
            <Chip label={RISK_CHIP[initial.risk]} onRemove={() => setParam("risk", "")} />
          ) : null}
          {initial.status !== "aktif" ? (
            <Chip
              label={initial.status === "pasif" ? "Pasifler" : "Tüm durumlar"}
              onRemove={() => setParam("status", "")}
            />
          ) : null}
          <button
            type="button"
            onClick={onClear}
            className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Tümünü temizle
          </button>
        </div>
      ) : null}
    </div>
  );
}

function Chip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-700 py-0.5 pl-2.5 pr-1 font-medium text-white">
      {label}
      <button
        type="button"
        onClick={onRemove}
        aria-label={`${label} süzgecini kaldır`}
        className="rounded-full p-0.5 hover:bg-white/20"
      >
        <X className="size-3" aria-hidden />
      </button>
    </span>
  );
}

export function Select({
  value,
  onChange,
  options,
  ariaLabel,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
  ariaLabel: string;
  className?: string;
}) {
  return (
    <select
      aria-label={ariaLabel}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        "h-10 rounded-lg border border-input bg-background px-3 text-sm",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        className,
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
