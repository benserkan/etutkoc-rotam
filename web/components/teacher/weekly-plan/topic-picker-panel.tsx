"use client";

/**
 * Kaynaksız test için müfredat konusu seçici (2026-10-16).
 *
 * Native <select> 40-60 konuluk listede kullanışsızdı (koç tek tek aşağı
 * okuyordu). Burada: arama kutusu (Türkçe harf + sözcük sırasından bağımsız,
 * sözcük başı eşleşmesi) + sınıf → tema/ünite başlıklarıyla gruplu liste.
 * Tema adı da aranır: "trigonometri" yazınca o temanın tüm konuları gelir.
 */

import * as React from "react";
import { Search, X } from "lucide-react";

import type { TopicOption } from "@/lib/api/task-topic-link";
import { cn } from "@/lib/utils";

const TR_MAP: Record<string, string> = {
  ı: "i", İ: "i", ş: "s", Ş: "s", ğ: "g", Ğ: "g", ü: "u", Ü: "u",
  ö: "o", Ö: "o", ç: "c", Ç: "c", â: "a", Â: "a", î: "i", û: "u",
};

export function normTr(s: string): string {
  return s
    .replace(/[ıİşŞğĞüÜöÖçÇâÂîû]/g, (c) => TR_MAP[c] ?? c)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Her sorgu sözcüğü, konu adı / tema / ders sözcüklerinden birinin başında geçmeli. */
export function topicMatches(t: TopicOption, query: string): boolean {
  const q = normTr(query);
  if (!q) return true;
  const hay = normTr([t.name, t.parent_name ?? "", t.subject_name ?? ""].join(" ")).split(" ");
  return q.split(" ").every((w) => hay.some((h) => h.startsWith(w)));
}

type Group = { key: string; grade: number | null; theme: string | null; items: TopicOption[] };

function groupTopics(topics: TopicOption[]): Group[] {
  const out: Group[] = [];
  const byKey = new Map<string, Group>();
  for (const t of topics) {
    const key = `${t.grade_level ?? "-"}|${t.parent_name ?? ""}|${t.subject_name ?? ""}`;
    let g = byKey.get(key);
    if (!g) {
      g = { key, grade: t.grade_level, theme: t.parent_name, items: [] };
      byKey.set(key, g);
      out.push(g);
    }
    g.items.push(t);
  }
  return out;
}

export function TopicPickerPanel({
  topics,
  loading,
  selectedId,
  onSelect,
  onClose,
}: {
  topics: TopicOption[];
  loading: boolean;
  selectedId: number | null;
  onSelect: (t: TopicOption) => void;
  onClose: () => void;
}) {
  const [q, setQ] = React.useState("");
  const filtered = React.useMemo(() => topics.filter((t) => topicMatches(t, q)), [topics, q]);
  const groups = React.useMemo(() => groupTopics(filtered), [filtered]);

  return (
    <div
      className="rounded-lg border border-cyan-600/40 bg-card"
      data-testid="topic-picker-panel"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          onClose();
        }
      }}
    >
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Search className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (filtered[0]) onSelect(filtered[0]);
            }
          }}
          placeholder="Konu ya da ünite ara — örn. trigonometri, olasılık, obeb"
          aria-label="Konu ara"
          className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        <span className="shrink-0 text-xs text-muted-foreground">
          {loading ? "yükleniyor…" : `${filtered.length} konu`}
        </span>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Kapat"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="max-h-80 overflow-y-auto py-1">
        {!loading && filtered.length === 0 ? (
          <p className="px-3 py-4 text-sm text-muted-foreground">
            “{q}” ile eşleşen konu yok. Daha kısa yaz ya da ünite adını dene.
          </p>
        ) : null}
        {groups.map((g) => (
          <div key={g.key}>
            <div className="sticky top-0 z-10 flex flex-wrap items-baseline gap-x-2 bg-muted px-3 py-1 text-xs font-semibold text-foreground">
              {g.grade ? <span className="text-cyan-700">{g.grade}. sınıf</span> : null}
              <span className="break-words">{g.theme ?? "Konular"}</span>
              {g.items[0]?.subject_name ? (
                <span className="font-normal text-muted-foreground">· {g.items[0].subject_name}</span>
              ) : null}
            </div>
            {g.items.map((t) => {
              const active = t.topic_id === selectedId;
              return (
                <button
                  key={t.topic_id}
                  type="button"
                  onClick={() => onSelect(t)}
                  className={cn(
                    "block w-full px-3 py-1.5 pl-6 text-left text-sm break-words",
                    active
                      ? "bg-cyan-700 text-white"
                      : "text-foreground hover:bg-cyan-500/15",
                  )}
                >
                  {t.name}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
