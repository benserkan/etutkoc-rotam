/**
 * Programdaki denemeler — görevde girilen D/Y'den açılan kayıtlar (import_source="task").
 * Konu analizi taşımadıkları için deneme analizine karışmaz; ayrı listede durur
 * (web components/shared/program-exams-section.tsx ile aynı kural, 2026-10-20).
 */
import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, View } from "react-native";

import type { ExamRow } from "@/lib/student";

function shortDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return d && m && y ? `${d}.${m}.${y}` : iso;
}

export function ProgramExamsCard({
  rows,
  audience,
}: {
  rows: ExamRow[] | undefined;
  audience: "coach" | "student" | "parent";
}) {
  const [open, setOpen] = React.useState(true);
  const list = rows ?? [];
  if (list.length === 0) return null;

  const groups: { label: string; rows: ExamRow[] }[] = [];
  for (const r of list) {
    const label = r.series_label || r.section_label;
    const g = groups.find((x) => x.label === label);
    if (g) g.rows.push(r);
    else groups.push({ label, rows: [r] });
  }
  const hint =
    audience === "coach"
      ? "Sonuç programdaki görevden girilir."
      : audience === "student"
        ? "Sonucu Bugün ekranındaki deneme görevinden girersin."
        : "Sonuçları öğrenci programdaki görevden girer.";

  return (
    <View className="rounded-2xl border border-indigo-200 bg-white">
      <Pressable onPress={() => setOpen((v) => !v)} className="flex-row items-start gap-3 p-4">
        <Ionicons name="clipboard-outline" size={20} color="#4338ca" />
        <View className="flex-1">
          <Text className="text-[15px] font-semibold text-slate-900">
            Programdaki denemeler ({list.length})
          </Text>
          <Text className="mt-0.5 text-xs text-slate-500">
            Deneme görevlerinde girilen doğru/yanlış sonuçları. Soru soru konu bilgisi olmadığı
            için deneme analizine katılmaz. {hint}
          </Text>
        </View>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={16} color="#94a3b8" />
      </Pressable>
      {open ? (
        <View className="gap-3 border-t border-slate-100 p-4">
          {groups.map((g) => (
            <View key={g.label} className="gap-1.5">
              <Text className="text-[11px] font-semibold text-slate-500">
                {g.label} · {g.rows.length} deneme
              </Text>
              {g.rows.map((r) => (
                <View key={r.id} className="rounded-xl bg-slate-50 px-3 py-2">
                  <View className="flex-row items-start justify-between gap-2">
                    <Text className="flex-1 text-sm text-slate-900">{r.title}</Text>
                    <Text className="text-sm font-bold text-slate-900">{r.net} net</Text>
                  </View>
                  <Text className="mt-0.5 text-xs text-slate-500">
                    {shortDate(r.exam_date)} ·{" "}
                    <Text className="font-semibold text-emerald-700">D {r.total_correct}</Text>{" "}
                    <Text className="font-semibold text-rose-700">Y {r.total_wrong}</Text>{" "}
                    B {r.total_blank} · {r.total_questions} soru
                  </Text>
                </View>
              ))}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/**
 * Deneme ekranlarının üstündeki seçici: karne/elle girilen denemelerin analizi
 * ile programdaki branş denemeleri AYRI görünür (web ExamKindSwitch karşılığı).
 */
export function ExamKindToggle({
  value,
  onChange,
  karneCount,
  programCount,
}: {
  value: "karne" | "program";
  onChange: (v: "karne" | "program") => void;
  karneCount: number;
  programCount: number;
}) {
  const items: { key: "karne" | "program"; label: string; count: number }[] = [
    { key: "karne", label: "Karne denemeleri", count: karneCount },
    { key: "program", label: "Branş denemeleri", count: programCount },
  ];
  return (
    <View className="flex-row gap-1 rounded-2xl border border-slate-200 bg-white p-1">
      {items.map((it) => {
        const on = value === it.key;
        return (
          <Pressable
            key={it.key}
            onPress={() => onChange(it.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: on }}
            className={on ? "min-h-11 flex-1 items-center justify-center rounded-xl bg-cyan-700 px-2" : "min-h-11 flex-1 items-center justify-center rounded-xl px-2"}
          >
            <Text className={on ? "text-sm font-semibold text-white" : "text-sm font-semibold text-slate-600"}>
              {it.label} ({it.count})
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
