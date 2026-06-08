import { Ionicons } from "@expo/vector-icons";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import type {
  WeeklyReportComparison,
  WeeklyReportDaily,
  WeeklyReportExam,
  WeeklyReportResponse,
  WeeklyReportSubject,
  WeeklyVerdictLevel,
} from "@/lib/parent";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

function shortDate(iso: string | null): string {
  if (!iso) return "";
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}
function fmtNet(n: number): string {
  return n % 1 === 0 ? String(n) : n.toFixed(2);
}

type Dir = "up" | "down" | "flat";
function dirOf(delta: number | null): Dir {
  if (delta == null || delta === 0) return "flat";
  return delta > 0 ? "up" : "down";
}
const DIR_ICON: Record<Dir, keyof typeof Ionicons.glyphMap> = {
  up: "trending-up",
  down: "trending-down",
  flat: "remove",
};
function dirColor(dir: Dir): string {
  return dir === "up" ? "#047857" : dir === "down" ? "#be123c" : "#64748b";
}

function verdictTone(level: WeeklyVerdictLevel) {
  if (level === "good")
    return { wrap: "border-emerald-300 bg-emerald-50", text: "text-emerald-900", sub: "text-emerald-700", label: "Yolunda" };
  if (level === "warn")
    return { wrap: "border-amber-300 bg-amber-50", text: "text-amber-900", sub: "text-amber-700", label: "Dikkat" };
  return { wrap: "border-rose-300 bg-rose-50", text: "text-rose-900", sub: "text-rose-700", label: "Acil" };
}

export function ParentChildReportView({
  report,
  refreshing = false,
  onRefresh,
}: {
  report: WeeklyReportResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const v = verdictTone(report.verdict_level);

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 pb-10 pt-1 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <View>
        <Text className="text-xs font-semibold uppercase tracking-wide text-slate-400">Haftalık ilerleme raporu</Text>
        <Text className="mt-0.5 text-lg font-bold text-slate-900">{report.student.full_name}</Text>
        <DemoHint contextKey="weekly-report" role="parent" className="mt-2" />
      </View>

      {/* Değerlendirme */}
      <View className={cn("rounded-2xl border-2 px-4 py-3.5", v.wrap)}>
        <Text className={cn("text-[11px] font-bold uppercase tracking-wide", v.sub)}>
          Bu haftanın değerlendirmesi · {v.label}
        </Text>
        <Text className={cn("mt-1 text-[15px] font-semibold leading-snug", v.text)}>{report.verdict_text}</Text>
      </View>

      {/* Geçen haftaya göre */}
      <ComparisonCard comparison={report.comparison} activeDays={report.active_days} gorevDone={report.gorev_done} gorevTotal={report.gorev_total} />

      {/* Ders kırılımı */}
      <SubjectCard
        subjects={report.subjects}
        mostCompleted={report.most_completed_subject}
        mostNeglected={report.most_neglected_subject}
        mostNeglectedPct={report.most_neglected_pct}
      />

      {/* Deneme performansı */}
      <ExamCard exams={report.exams} trendDelta={report.exam_trend_delta} trendSection={report.exam_trend_section} />

      {/* Gün gün */}
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <Text className="mb-1 text-sm font-semibold text-slate-700">Gün gün</Text>
        <Text className="mb-3 text-xs text-slate-400">Her gün tamamlanan görev oranı + çözülen test.</Text>
        <View className="gap-2.5">
          {report.daily.map((d) => (
            <DayBar key={d.date} day={d} />
          ))}
        </View>
      </View>

      {/* Koç notları */}
      {report.teacher_notes.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4">
          <View className="mb-3 flex-row items-center gap-1.5">
            <Ionicons name="chatbubble-ellipses-outline" size={16} color="#0e7490" />
            <Text className="text-sm font-semibold text-slate-700">Koçtan notlar</Text>
          </View>
          <View className="gap-3">
            {report.teacher_notes.map((n, i) => (
              <View key={i} className="rounded-r-lg border-l-4 border-brand-600 bg-brand-50/60 py-2 pl-3 pr-2">
                <Text className="mb-1 text-[11px] font-medium text-slate-500">
                  {n.teacher_name ?? "Koç"}
                  {n.created_at ? ` · ${n.created_at.slice(0, 10).replaceAll("-", ".")}` : ""}
                </Text>
                <Text className="text-sm leading-relaxed text-slate-700">{n.body}</Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      <Text className="px-1 text-[11px] leading-relaxed text-slate-400">
        Konu bazında doğru-yanlış kırılımı ve koçluk notlarının tamamı, öğrenci ile koç arasındaki çalışma alanına aittir.
      </Text>
    </ScrollView>
  );
}

function ComparisonCard({
  comparison,
  activeDays,
  gorevDone,
  gorevTotal,
}: {
  comparison: WeeklyReportComparison;
  activeDays: number;
  gorevDone: number;
  gorevTotal: number;
}) {
  const c = comparison;
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="mb-1 flex-row items-center gap-1.5">
        <Ionicons name="trending-up" size={16} color="#0e7490" />
        <Text className="text-sm font-semibold text-slate-700">Geçen haftaya göre</Text>
      </View>
      <Text className="mb-3 text-xs text-slate-400">Bu haftaki tempo, bir önceki haftayla kıyaslanır.</Text>
      <View className="flex-row">
        <CompareCol
          label="Tamamlama"
          value={`%${c.this_completion_pct}`}
          prev={c.last_completion_pct != null ? `geçen %${c.last_completion_pct}` : "geçen veri yok"}
          delta={c.completion_delta}
          suffix=" puan"
        />
        <CompareCol
          label="Çözülen test"
          value={`${c.this_test_completed}`}
          prev={c.last_test_completed != null ? `geçen ${c.last_test_completed}` : "—"}
          delta={c.test_delta}
          suffix=""
        />
        <CompareCol
          label="Çalışılan gün"
          value={`${activeDays}/7`}
          prev={`${gorevDone}/${gorevTotal} görev`}
          delta={null}
          suffix=""
        />
      </View>
    </View>
  );
}

function CompareCol({
  label,
  value,
  prev,
  delta,
  suffix,
}: {
  label: string;
  value: string;
  prev: string;
  delta: number | null;
  suffix: string;
}) {
  const dir = dirOf(delta);
  return (
    <View className="flex-1 items-center">
      <Text className="text-[10px] uppercase tracking-wide text-slate-400">{label}</Text>
      <Text className="mt-0.5 text-2xl font-extrabold text-slate-900">{value}</Text>
      {delta != null ? (
        <View className="mt-0.5 flex-row items-center gap-0.5">
          <Ionicons name={DIR_ICON[dir]} size={13} color={dirColor(dir)} />
          <Text className="text-[11px] font-semibold" style={{ color: dirColor(dir) }}>
            {delta > 0 ? "+" : ""}
            {delta}
            {suffix}
          </Text>
        </View>
      ) : (
        <View className="h-[15px]" />
      )}
      <Text className="mt-0.5 text-[10px] text-slate-400">{prev}</Text>
    </View>
  );
}

function SubjectCard({
  subjects,
  mostCompleted,
  mostNeglected,
  mostNeglectedPct,
}: {
  subjects: WeeklyReportSubject[];
  mostCompleted: string | null;
  mostNeglected: string | null;
  mostNeglectedPct: number | null;
}) {
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <Text className="mb-3 text-sm font-semibold text-slate-700">Bu hafta dersler</Text>
      {subjects.length === 0 ? (
        <Text className="text-xs italic text-slate-400">Bu hafta planlanmış test görevi yok.</Text>
      ) : (
        <>
          <View className="mb-3 gap-2">
            {mostCompleted ? (
              <View className="flex-row items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2">
                <Ionicons name="trophy-outline" size={16} color="#047857" />
                <Text className="text-xs font-semibold uppercase tracking-wide text-emerald-700">En çok çözülen:</Text>
                <Text className="text-sm font-bold text-emerald-900">{mostCompleted}</Text>
              </View>
            ) : null}
            {mostNeglected ? (
              <View className="flex-row items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                <Ionicons name="warning-outline" size={16} color="#b45309" />
                <Text className="text-xs font-semibold uppercase tracking-wide text-amber-700">En çok aksatılan:</Text>
                <Text className="text-sm font-bold text-amber-900">
                  {mostNeglected}
                  {mostNeglectedPct != null ? ` (%${mostNeglectedPct})` : ""}
                </Text>
              </View>
            ) : null}
          </View>
          <View className="gap-2.5">
            {subjects.map((s) => (
              <View key={s.subject_name}>
                <View className="flex-row items-center justify-between">
                  <Text className="text-xs font-medium text-slate-700">{s.subject_name}</Text>
                  <Text className="text-xs text-slate-400">
                    {s.completed}/{s.planned} test · %{s.pct}
                  </Text>
                </View>
                <View className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100">
                  <View
                    className={cn("h-full rounded-full", s.pct >= 70 ? "bg-emerald-500" : s.pct >= 40 ? "bg-amber-400" : "bg-rose-500")}
                    style={{ width: `${Math.min(100, s.pct)}%` }}
                  />
                </View>
              </View>
            ))}
          </View>
        </>
      )}
    </View>
  );
}

function ExamCard({
  exams,
  trendDelta,
  trendSection,
}: {
  exams: WeeklyReportExam[];
  trendDelta: number | null;
  trendSection: string | null;
}) {
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="mb-3 flex-row items-center gap-1.5">
        <Ionicons name="school-outline" size={16} color="#0e7490" />
        <Text className="text-sm font-semibold text-slate-700">Deneme performansı</Text>
      </View>
      {exams.length === 0 ? (
        <Text className="text-xs italic text-slate-400">Son 60 günde girilmiş bir deneme sonucu yok.</Text>
      ) : (
        <>
          <View className="flex-row items-center justify-between rounded-xl border border-brand-100 bg-brand-50/60 px-3 py-2.5">
            <View className="mr-2 flex-1">
              <Text className="text-sm font-semibold text-slate-800" numberOfLines={1}>
                {exams[0].title}
              </Text>
              <View className="mt-1 flex-row items-center gap-2">
                <Text className="rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-brand-700">{exams[0].section_label}</Text>
                <Text className="text-[11px] text-slate-400">{shortDate(exams[0].exam_date)}</Text>
                <Text className="text-[11px] text-slate-400">
                  D{exams[0].total_correct} · Y{exams[0].total_wrong} · B{exams[0].total_blank}
                </Text>
              </View>
            </View>
            <View className="items-end">
              <Text className="text-[10px] uppercase tracking-wide text-slate-400">Net</Text>
              <Text className="text-3xl font-extrabold leading-none text-brand-700">{fmtNet(exams[0].net)}</Text>
              {trendDelta != null && trendSection ? (
                <View className="mt-0.5 flex-row items-center gap-0.5">
                  <Ionicons name={DIR_ICON[dirOf(trendDelta)]} size={13} color={dirColor(dirOf(trendDelta))} />
                  <Text className="text-[11px] font-semibold" style={{ color: dirColor(dirOf(trendDelta)) }}>
                    {trendDelta > 0 ? "+" : ""}
                    {fmtNet(trendDelta)} net
                  </Text>
                </View>
              ) : null}
            </View>
          </View>
          {trendDelta != null && trendSection ? (
            <Text className="mt-2 text-[11px] text-slate-400">
              {trendSection} türündeki bir önceki denemeye göre {trendDelta > 0 ? "yükseliş" : trendDelta < 0 ? "düşüş" : "değişim yok"}.
            </Text>
          ) : null}
          {exams.length > 1 ? (
            <View className="mt-3 border-t border-slate-100">
              {exams.slice(1).map((e, i) => (
                <View key={i} className="flex-row items-center justify-between border-b border-slate-100 py-2">
                  <View className="mr-2 flex-1">
                    <Text className="text-sm font-medium text-slate-700" numberOfLines={1}>
                      {e.title}
                    </Text>
                    <Text className="text-[11px] text-slate-400">
                      {e.section_label} · {shortDate(e.exam_date)}
                    </Text>
                  </View>
                  <Text className="text-sm font-semibold text-slate-800">{fmtNet(e.net)} net</Text>
                </View>
              ))}
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function DayBar({ day }: { day: WeeklyReportDaily }) {
  const empty = day.gorev_total === 0;
  return (
    <View className="flex-row items-center gap-3">
      <Text className="w-9 text-xs font-medium text-slate-500">{DAYS[day.weekday] ?? ""}</Text>
      <View className="flex-1 overflow-hidden rounded-full bg-slate-100" style={{ height: 8 }}>
        {!empty ? (
          <View
            className={cn("rounded-full", day.pct >= 100 ? "bg-emerald-500" : day.pct > 0 ? "bg-amber-400" : "bg-slate-200")}
            style={{ height: 8, width: `${Math.min(100, day.pct)}%` }}
          />
        ) : null}
      </View>
      <Text className="w-[112px] text-right text-[11px] text-slate-500">
        {empty ? (
          <Text className="italic text-slate-300">program yok</Text>
        ) : (
          <Text>
            <Text className="font-bold text-slate-700">%{day.pct}</Text> · {day.gorev_done}/{day.gorev_total} görev
            {day.test_completed > 0 ? ` · ${day.test_completed} test` : ""}
          </Text>
        )}
      </Text>
    </View>
  );
}
