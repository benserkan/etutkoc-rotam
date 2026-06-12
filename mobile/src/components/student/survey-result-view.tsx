import { Text, View } from "react-native";

import type { SurveyResultModel } from "@/lib/surveys";
import { cn } from "@/lib/utils";

/**
 * Anket sonucu görünümü (mobil) — öğrenci + koç ekranları ORTAK.
 * Web SurveyResultView ile aynı mantık: boyut barları + seviye rozetleri +
 * SWOT kadranları + açık uç cevaplar + sabit konumlandırma ibaresi.
 */

function toneFor(level: string, highIsGood: boolean): "good" | "warn" | "bad" {
  if (level === "mid") return "warn";
  const strong = level === "high";
  if (highIsGood) return strong ? "good" : "bad";
  return strong ? "bad" : "good";
}

const BAR_TONE: Record<string, string> = {
  good: "bg-emerald-500",
  warn: "bg-amber-500",
  bad: "bg-rose-500",
};
const PILL_TONE: Record<string, string> = {
  good: "border-emerald-300 bg-emerald-50",
  warn: "border-amber-300 bg-amber-50",
  bad: "border-rose-300 bg-rose-50",
};
const PILL_TEXT: Record<string, string> = {
  good: "text-emerald-900",
  warn: "text-amber-900",
  bad: "text-rose-900",
};
const QUAD_TONE: Record<string, { card: string; title: string }> = {
  guclu: { card: "border-emerald-300 bg-emerald-50", title: "text-emerald-900" },
  zayif: { card: "border-amber-300 bg-amber-50", title: "text-amber-900" },
  firsat: { card: "border-sky-300 bg-sky-50", title: "text-sky-900" },
  tehdit: { card: "border-rose-300 bg-rose-50", title: "text-rose-900" },
};

export function SurveyResultView({ result }: { result: SurveyResultModel }) {
  const topSet = new Set(result.top_dimensions);
  return (
    <View className="gap-3">
      {result.dimensions.map((d) => {
        const tone = toneFor(d.level, d.high_is_good);
        return (
          <View key={d.key} className="rounded-2xl border border-slate-200 bg-white p-3.5">
            <View className="flex-row items-center justify-between gap-2">
              <View className="flex-1 flex-row items-center gap-1.5">
                <Text className="text-[14px] font-semibold text-slate-900" numberOfLines={1}>
                  {d.label}
                </Text>
                {topSet.has(d.key) && result.scoring_type === "dimensions" ? (
                  <View className="rounded-md border border-cyan-300 bg-cyan-50 px-1.5 py-0.5">
                    <Text className="text-[9px] font-semibold text-cyan-900">öne çıkan</Text>
                  </View>
                ) : null}
              </View>
              <View className={cn("rounded-md border px-1.5 py-0.5", PILL_TONE[tone])}>
                <Text className={cn("text-[11px] font-semibold", PILL_TEXT[tone])}>
                  %{Math.round(d.score_pct)} · {d.level_label}
                </Text>
              </View>
            </View>
            <View className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <View
                className={cn("h-full rounded-full", BAR_TONE[tone])}
                style={{ width: `${Math.max(2, Math.min(100, d.score_pct))}%` }}
              />
            </View>
            {d.description ? (
              <Text className="mt-1.5 text-[11px] text-slate-500">{d.description}</Text>
            ) : null}
            {d.comment ? (
              <View className={cn("mt-2 rounded-lg border px-2.5 py-1.5", PILL_TONE[tone])}>
                <Text className={cn("text-xs", PILL_TEXT[tone])}>{d.comment}</Text>
              </View>
            ) : null}
          </View>
        );
      })}

      {result.qualitative.map((b) => {
        const t = QUAD_TONE[b.key] ?? { card: "border-slate-200 bg-white", title: "text-slate-900" };
        return (
          <View key={b.key} className={cn("rounded-2xl border p-3.5", t.card)}>
            <Text className={cn("text-[14px] font-bold", t.title)}>{b.label}</Text>
            {b.description ? (
              <Text className="mt-0.5 text-[11px] text-slate-600">{b.description}</Text>
            ) : null}
            <View className="mt-2 gap-2">
              {b.entries.map((e, i) => (
                <View key={i}>
                  <Text className="text-[11px] text-slate-500">{e.question}</Text>
                  <Text className="mt-0.5 text-[13px] text-slate-900">
                    {e.answer || "— boş bırakıldı"}
                  </Text>
                </View>
              ))}
            </View>
          </View>
        );
      })}

      {result.open_answers.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-3.5">
          <Text className="text-xs font-bold uppercase tracking-wide text-slate-500">
            Öğrencinin kendi cümleleri
          </Text>
          <View className="mt-2 gap-2">
            {result.open_answers.map((e, i) => (
              <View key={i}>
                <Text className="text-[11px] text-slate-500">{e.question}</Text>
                <Text className="mt-0.5 text-[13px] text-slate-900">{e.answer}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {result.report_note ? (
        <View className="rounded-2xl border border-cyan-200 bg-cyan-50 p-3.5">
          <Text className="text-xs font-bold text-cyan-900">Koçluk yorumu için çerçeve</Text>
          <Text className="mt-1 text-xs leading-5 text-cyan-900">{result.report_note}</Text>
        </View>
      ) : null}

      <View className="border-t border-slate-200 pt-2">
        <Text className="text-[10px] leading-4 text-slate-400">{result.disclaimer}</Text>
        {result.source_attribution ? (
          <Text className="mt-1 text-[10px] leading-4 text-slate-400">
            {result.source_attribution}
          </Text>
        ) : null}
      </View>
    </View>
  );
}
