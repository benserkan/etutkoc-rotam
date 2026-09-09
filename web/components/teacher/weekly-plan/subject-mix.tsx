"use client";

/**
 * Haftanın Ders Dengesi — emeğin hangi derse gittiği (2026-09-09)
 *
 * ADLANDIRMA: gün kartında zaten "DERS DAĞILIMI" şeridi var (o GÜNÜN ders
 * özeti). Bu bölüm HAFTA bütününü gösterir; iki başlık karışmasın diye
 * "Haftanın Ders Dengesi" adını taşır.
 *
 * KOÇ İHTİYACI (birebir): "programı hazırlarken ders bazında (TYT ve AYT ayrı
 * olarak) görev yüzdelerini görmek istiyorum. Örneğin AYT Matematik %35."
 *
 * NEDEN: koç günleri tek tek doldururken haftanın BÜTÜNÜNÜ göremiyordu; ders
 * dengesi ancak hafta bitince (ya da hiç) fark ediliyordu. Saha vakası: bir
 * öğrencide emeğin ~%85'i TYT'ye giderken TYT neti zaten doygundu, sıralamayı
 * belirleyen AYT bloğu ise neredeyse boştu. Bu şerit o dengesizliği program
 * KURULURKEN gösterir.
 *
 * İKİ METRİK, TEK YÜZDE (karışmasın diye toggle):
 *   · Test  → planlanan test hacmi (emek). Deneme kitapları ve kitapsız
 *             denemeler SAYILMAZ (DENEME≠TEST kuralı, gorev_stats ile aynı).
 *   · Görev → görev adedi (koçun "kaç madde yazdım" bakışı).
 * Çipte her iki sayı da yazılı — hangi mod açık olursa olsun bilgi kaybolmaz.
 *
 * Gruplama week-grid ile AYNI (taskSubjKey + toneForKey): aynı ders aynı renk,
 * branş denemesi/video görevi de adından doğru derse düşer.
 */

import * as React from "react";
import { ChevronDown, PieChart } from "lucide-react";

import type { TeacherStudentWeekDay } from "@/lib/types/teacher";
import type { SubjectRef } from "@/lib/subject-match";
import { cn } from "@/lib/utils";
import { DENEME_TYPES, taskSubjKey, toneForKey } from "./week-grid";

type Metric = "test" | "task";

interface MixRow {
  key: string;
  name: string;
  /** "TYT" | "AYT" | null — ders adının önekinden */
  block: string | null;
  tasks: number;
  tests: number;
  tone: { text: string; dot: string };
}

/** Ders adı öneki → sınav bloğu. "AYT Matematik" → AYT. */
function blockOf(name: string): string | null {
  const up = name.trim().toLocaleUpperCase("tr");
  if (up.startsWith("TYT")) return "TYT";
  if (up.startsWith("AYT")) return "AYT";
  if (up.startsWith("YDT")) return "YDT";
  return null;
}

function pct(part: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((100 * part) / total);
}

export function SubjectMix({
  days,
  subjects,
}: {
  days: TeacherStudentWeekDay[];
  subjects: SubjectRef[];
}) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [metric, setMetric] = React.useState<Metric>("test");

  const { rows, totalTasks, totalTests } = React.useMemo(() => {
    const map = new Map<string, MixRow>();
    let tTasks = 0;
    let tTests = 0;
    for (const d of days) {
      for (const task of d.tasks) {
        const { key, name } = taskSubjKey(task, subjects);
        const row =
          map.get(key) ??
          ({
            key,
            name,
            block: blockOf(name),
            tasks: 0,
            tests: 0,
            tone: toneForKey(key, name),
          } satisfies MixRow);
        row.tasks += 1;
        tTasks += 1;
        for (const it of task.items) {
          // Kitapsız kalem (tam deneme) ve deneme kitabı test hacmine girmez.
          if (it.book_id == null) continue;
          if (it.book_type && DENEME_TYPES.has(it.book_type)) continue;
          const n = it.planned_count ?? 0;
          row.tests += n;
          tTests += n;
        }
        map.set(key, row);
      }
    }
    const value = (r: MixRow) => (metric === "test" ? r.tests : r.tasks);
    const list = Array.from(map.values()).sort(
      (a, b) => value(b) - value(a) || a.name.localeCompare(b.name, "tr"),
    );
    return { rows: list, totalTasks: tTasks, totalTests: tTests };
  }, [days, subjects, metric]);

  const total = metric === "test" ? totalTests : totalTasks;

  // Blok özeti (TYT / AYT) — koçun asıl sorduğu denge.
  const blocks = React.useMemo(() => {
    const acc = new Map<string, number>();
    for (const r of rows) {
      const b = r.block ?? "Diğer";
      acc.set(b, (acc.get(b) ?? 0) + (metric === "test" ? r.tests : r.tasks));
    }
    return ["TYT", "AYT", "YDT", "Diğer"]
      .filter((b) => (acc.get(b) ?? 0) > 0)
      .map((b) => ({ name: b, value: acc.get(b) ?? 0 }));
  }, [rows, metric]);

  if (rows.length === 0) return null;

  return (
    <section
      className="rounded-xl border border-border bg-card"
      data-section="week:subject-mix"
    >
      <div className="flex items-center gap-2 px-4 py-2.5">
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
          aria-expanded={!collapsed}
        >
          <PieChart
            className="size-4 shrink-0 text-muted-foreground"
            aria-hidden
          />
          <span className="text-sm font-semibold text-foreground">
            Haftanın Ders Dengesi
          </span>
          <span className="min-w-0 truncate text-[11px] text-muted-foreground">
            — emeğin hangi derse gittiği
            {blocks.length > 1 ? (
              <>
                {" · "}
                {blocks
                  .map((b) => `${b.name} %${pct(b.value, total)}`)
                  .join(" · ")}
              </>
            ) : null}
          </span>
          <ChevronDown
            className={cn(
              "ml-auto size-4 shrink-0 text-muted-foreground transition-transform",
              collapsed ? "" : "rotate-180",
            )}
            aria-hidden
          />
        </button>
      </div>

      {collapsed ? null : (
        <div className="space-y-2 px-4 pb-3">
          {/* Metrik seçici — tek tık, iki bakış */}
          <div className="flex items-center gap-2">
            <div
              className="inline-flex overflow-hidden rounded-md border border-border"
              role="group"
              aria-label="Yüzde neye göre"
            >
              {(
                [
                  ["test", "Test"],
                  ["task", "Görev"],
                ] as const
              ).map(([m, label]) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMetric(m)}
                  aria-pressed={metric === m}
                  className={cn(
                    "px-2 py-0.5 text-[11px] font-medium transition",
                    metric === m
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              toplam {metric === "test" ? `${totalTests} test` : `${totalTasks} görev`}
              {metric === "test" && totalTests === 0
                ? " — bu hafta kitaplı test yok"
                : ""}
            </span>
          </div>

          {/* Tek satır yığılmış çubuk */}
          {total > 0 ? (
            <div
              className="flex h-2.5 w-full overflow-hidden rounded-full bg-muted"
              role="img"
              aria-label={rows
                .map((r) => `${r.name} %${pct(metric === "test" ? r.tests : r.tasks, total)}`)
                .join(", ")}
            >
              {rows.map((r) => {
                const v = metric === "test" ? r.tests : r.tasks;
                if (v <= 0) return null;
                return (
                  <span
                    key={r.key}
                    className={cn("h-full", r.tone.dot)}
                    style={{ width: `${(100 * v) / total}%` }}
                    title={`${r.name} — %${pct(v, total)}`}
                  />
                );
              })}
            </div>
          ) : null}

          {/* Ders çipleri — yüzde + iki sayı birden (bilgi kaybı yok) */}
          <ul className="flex flex-wrap gap-x-3 gap-y-1.5">
            {rows.map((r) => {
              const v = metric === "test" ? r.tests : r.tasks;
              return (
                <li
                  key={r.key}
                  className="flex items-center gap-1.5 text-[11.5px] leading-tight"
                >
                  <span
                    className={cn("size-2 shrink-0 rounded-full", r.tone.dot)}
                    aria-hidden
                  />
                  <span className="whitespace-normal break-words font-medium text-foreground">
                    {r.name}
                  </span>
                  <span className="font-semibold tabular-nums text-foreground">
                    %{pct(v, total)}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    ({r.tasks} görev · {r.tests} test)
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
