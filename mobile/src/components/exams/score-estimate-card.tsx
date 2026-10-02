import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { examProgressKeys, fmtNet, fmtSigned, getScoreEstimate } from "@/lib/exam-progress";
import { cn } from "@/lib/utils";

/** Deneme Faz 3 (mobil) — tahmini YKS/LGS puanı (koç + öğrenci). */
export function ScoreEstimateCard({
  studentId,
  parentStudentId = null,
}: {
  studentId: number | null;
  parentStudentId?: number | null;
}) {
  const q = useQuery({
    queryKey: examProgressKeys.score(studentId, parentStudentId),
    queryFn: () => getScoreEstimate(studentId, parentStudentId),
  });
  const d = q.data;
  if (!d || !d.scores.length) return null;
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name="calculator-outline" size={16} color="#0e7490" />
        <Text className="text-sm font-semibold text-slate-800">
          {d.kind === "lgs" ? "Tahmini LGS puanı" : "Tahmini YKS puanları"}
        </Text>
      </View>
      <View className="mt-3 gap-2">
        {d.scores.map((s) => (
          <View
            key={s.key}
            className={cn("rounded-xl border p-3", s.is_student_track ? "border-brand-600 bg-brand-50" : "border-slate-200")}
          >
            <View className="flex-row items-center justify-between">
              <Text className="text-xs text-slate-500">{s.label}</Text>
              {s.is_student_track ? (
                <Text className="overflow-hidden rounded bg-brand-700 px-1.5 py-0.5 text-[10px] font-bold text-white">
                  {parentStudentId != null ? "çocuğunuzun alanı" : studentId != null ? "öğrencinin alanı" : "alanın"}
                </Text>
              ) : null}
            </View>
            <Text className="mt-0.5 text-2xl font-extrabold text-slate-900">~{fmtNet(s.score)}</Text>
            <View className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <View className="h-full rounded-full bg-brand-600" style={{ width: `${Math.min(100, (s.score / s.max) * 100)}%` }} />
            </View>
            {s.detail ? <Text className="mt-1 text-[11px] text-slate-500">{s.detail}</Text> : null}
          </View>
        ))}
      </View>
      {d.calibration.length ? (
        <View className="mt-3 gap-1">
          <Text className="text-xs font-semibold text-slate-600">Tahmin ile karne puanı</Text>
          {d.calibration.slice(0, 3).map((c) => (
            <Text key={c.exam_id} className="text-xs text-slate-500">
              {c.title}: karne {fmtNet(c.karne_score)} · tahmin {fmtNet(c.estimate)} ({fmtSigned(c.diff)})
            </Text>
          ))}
        </View>
      ) : null}
      {d.warnings.map((w) => (
        <Text key={w} className="mt-2 text-xs text-amber-800">
          {w}
        </Text>
      ))}
      <Text className="mt-2 text-[11px] leading-4 text-slate-400">{d.disclaimer}</Text>
    </View>
  );
}
