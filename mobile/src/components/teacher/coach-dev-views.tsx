import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type {
  CoachingInsightCache,
  TeacherDnaResponse,
  TeacherFocusResponse,
  TeacherGoalCreateBody,
  TeacherGoalNode,
  TeacherGoalsResponse,
  TeacherReviewResponse,
  TeacherReviewSubjectOption,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

const CHRONO: Record<string, string> = { morning: "Sabahçı", afternoon: "Öğlenci", evening: "Akşamcı", night: "Gececi", unknown: "Belirsiz" };

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <View className="flex-row items-center gap-2">
      <Text className="w-16 text-xs text-slate-500">{label}</Text>
      <View className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <View className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </View>
      <Text className="w-8 text-right text-xs text-slate-500">{value}</Text>
    </View>
  );
}

// ---------- DNA ----------
export function CoachDnaView({ d }: { d: TeacherDnaResponse }) {
  if (!d.has_enough_data) {
    return <Text className="px-1 text-sm text-slate-400">Bu öğrenci için yeterli çalışma verisi yok.</Text>;
  }
  const maxP = Math.max(1, d.morning_count, d.afternoon_count, d.evening_count, d.night_count);
  const up = d.trend && (d.trend.delta_pct ?? 0) >= 0;
  return (
    <View className="gap-4">
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <Text className="text-sm font-semibold text-slate-800">{CHRONO[d.chronotype] ?? "Belirsiz"}</Text>
        {d.peak_day_name ? (
          <Text className="text-xs text-slate-400">En verimli {d.peak_day_name}{d.peak_hour != null ? ` ~${d.peak_hour}:00` : ""}</Text>
        ) : null}
        <View className="mt-3 gap-2">
          <Bar label="Sabah" value={d.morning_count} max={maxP} />
          <Bar label="Öğlen" value={d.afternoon_count} max={maxP} />
          <Bar label="Akşam" value={d.evening_count} max={maxP} />
          <Bar label="Gece" value={d.night_count} max={maxP} />
        </View>
        <Text className="mt-3 text-xs text-slate-400">Son {d.window_days} gün · hafta içi {d.weekday_count} / hafta sonu {d.weekend_count}</Text>
        {d.trend ? (
          <View className="mt-2 flex-row items-center gap-1">
            <Ionicons name={up ? "trending-up" : "trending-down"} size={14} color={up ? "#059669" : "#e11d48"} />
            <Text className={cn("text-xs font-medium", up ? "text-emerald-700" : "text-rose-600")}>
              Bu hafta {d.trend.this_week_completed} · geçen hafta {d.trend.last_week_completed}
            </Text>
          </View>
        ) : null}
      </View>
      {d.by_subject.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-2.5">
          <View>
            <Text className="text-sm font-semibold text-slate-800">Derslere göre tamamlama</Text>
            <Text className="text-[11px] text-slate-400">Her derste verilen görevlerin ne kadarını bitirdi (yüzde). Düşük olan derse ağırlık ver.</Text>
          </View>
          {d.by_subject.slice(0, 10).map((s) => {
            const pct = Math.round(s.completion_rate * 100);
            const label = s.subject_name === "(diğer)" ? "Deneme / etkinlik (derssiz)" : s.subject_name;
            const tone = pct >= 70 ? "text-emerald-600" : pct >= 40 ? "text-amber-600" : "text-rose-600";
            return (
              <View key={s.subject_name} className="gap-1">
                <View className="flex-row items-center justify-between">
                  <Text className="flex-1 text-[13px] text-slate-700" numberOfLines={1}>{label}</Text>
                  <Text className={cn("text-xs font-semibold", tone)}>%{pct}</Text>
                </View>
                <View className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <View className={cn("h-full rounded-full", pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-rose-500")} style={{ width: `${Math.min(100, pct)}%` }} />
                </View>
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

// ---------- Odak ----------
export function CoachFocusView({ d }: { d: TeacherFocusResponse }) {
  return (
    <View className="gap-4">
      <View className="flex-row justify-around rounded-2xl border border-slate-200 bg-white p-4">
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{d.streak_days}</Text><Text className="text-[11px] text-slate-400">gün seri</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{d.longest_streak}</Text><Text className="text-[11px] text-slate-400">en uzun</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{d.today_work_minutes}</Text><Text className="text-[11px] text-slate-400">bugün dk</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-amber-600">{d.points_total}</Text><Text className="text-[11px] text-slate-400">puan</Text></View>
      </View>
      {d.recent_sessions.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-2">
          <Text className="text-sm font-semibold text-slate-800">Son oturumlar</Text>
          {d.recent_sessions.slice(0, 8).map((s) => (
            <View key={s.id} className="flex-row items-center justify-between">
              <Text className="flex-1 text-[13px] text-slate-700" numberOfLines={1}>{s.label || "Odak"}</Text>
              <Text className={cn("text-xs font-medium", s.interrupted ? "text-amber-600" : "text-emerald-600")}>
                {s.actual_minutes} dk{s.interrupted ? " (yarım)" : ""}
              </Text>
            </View>
          ))}
        </View>
      ) : (
        <Text className="px-1 text-sm text-slate-400">Henüz odak oturumu yok.</Text>
      )}
    </View>
  );
}

// ---------- Tekrar ----------
export function CoachReviewView({ d, busy, onSeed }: { d: TeacherReviewResponse; busy: boolean; onSeed: (subjectId: number) => void }) {
  const [seedOpen, setSeedOpen] = React.useState(false);
  const b = d.breakdown;
  return (
    <View className="gap-4">
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-row items-end justify-between">
          <View><Text className="text-3xl font-extrabold text-slate-900">{b.due_now}</Text><Text className="text-[11px] text-slate-400">şimdi tekrar</Text></View>
          <Text className="text-xs text-slate-500">{b.review} öğrenildi · {b.learning} öğreniliyor · {b.new} yeni</Text>
        </View>
      </View>

      {d.struggle_cards.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-2">
          <Text className="text-sm font-semibold text-slate-800">Zorlandığı konular</Text>
          {d.struggle_cards.slice(0, 8).map((c) => (
            <View key={c.topic_id} className="flex-row items-center justify-between gap-2">
              <View className="flex-1">
                <Text className="text-[13px] text-slate-800" numberOfLines={1}>{c.topic_name}</Text>
                <Text className="text-[11px] text-slate-400">{c.subject_name} · {c.state_label}</Text>
              </View>
              {c.lapse_count > 0 ? (
                <View className="rounded-full bg-rose-50 px-2 py-0.5"><Text className="text-[11px] font-semibold text-rose-600">{c.lapse_count}× unuttu</Text></View>
              ) : null}
            </View>
          ))}
        </View>
      ) : (
        <Text className="px-1 text-sm text-slate-400">Zorlanılan konu işareti yok.</Text>
      )}

      {d.subjects.length > 0 ? (
        <Pressable onPress={() => setSeedOpen(true)} className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3 active:bg-brand-100">
          <Ionicons name="add-circle-outline" size={18} color="#0e7490" />
          <Text className="text-[15px] font-semibold text-brand-700">Bir dersten tekrar kartları ekle</Text>
        </Pressable>
      ) : null}

      <FormSheet visible={seedOpen} title="Tekrar kartı ekle" onClose={() => setSeedOpen(false)}>
        <View className="gap-2 pb-2">
          <Text className="text-sm text-slate-600">Hangi dersin konularını tekrar takibine al?</Text>
          {d.subjects.map((s: TeacherReviewSubjectOption) => (
            <Pressable
              key={s.id}
              onPress={() => { onSeed(s.id); setSeedOpen(false); }}
              disabled={busy}
              className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
            >
              <Text className="text-[14px] font-medium text-slate-900">{s.name}</Text>
            </Pressable>
          ))}
        </View>
      </FormSheet>
    </View>
  );
}

// ---------- Hedefler ----------
function GoalNodeView({ g, depth = 0 }: { g: TeacherGoalNode; depth?: number }) {
  const pct = g.aggregated_pct ?? g.progress_pct;
  const achieved = g.status === "achieved";
  return (
    <View style={{ marginLeft: depth * 12 }} className="gap-1">
      <View className="flex-row items-center justify-between gap-2">
        <Text className={cn("flex-1 text-[13px]", achieved ? "text-slate-400 line-through" : "text-slate-800")} numberOfLines={1}>
          {g.title}
        </Text>
        <Text className="text-[11px] text-slate-400">{g.kind_label}{pct != null ? ` · %${pct}` : ""}</Text>
      </View>
      {pct != null ? (
        <View className="h-1.5 overflow-hidden rounded-full bg-slate-100">
          <View className={cn("h-full rounded-full", pct >= 100 ? "bg-emerald-500" : "bg-brand-500")} style={{ width: `${Math.min(100, pct)}%` }} />
        </View>
      ) : null}
      {g.children.length > 0 ? (
        <View className="mt-1 gap-1.5">
          {g.children.slice(0, 6).map((c) => <GoalNodeView key={c.id} g={c} depth={depth + 1} />)}
        </View>
      ) : null}
    </View>
  );
}

export function CoachGoalsView({ d, busy, onCreate }: { d: TeacherGoalsResponse; busy: boolean; onCreate: (b: TeacherGoalCreateBody) => void }) {
  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState("");
  const [target, setTarget] = React.useState("");
  const [unit, setUnit] = React.useState("");
  return (
    <View className="gap-4">
      <View className="flex-row gap-3 rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-slate-900">{d.summary.active}</Text><Text className="text-[11px] text-slate-400">aktif</Text></View>
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-emerald-600">{d.summary.achieved}</Text><Text className="text-[11px] text-slate-400">başarıldı</Text></View>
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-slate-900">%{d.overall_pct}</Text><Text className="text-[11px] text-slate-400">genel</Text></View>
      </View>

      <Pressable onPress={() => setOpen(true)} className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3 active:bg-brand-100">
        <Ionicons name="flag-outline" size={18} color="#0e7490" />
        <Text className="text-[15px] font-semibold text-brand-700">Öğrenciye hedef ekle</Text>
      </Pressable>

      {d.roots.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-3">
          {d.roots.map((g) => <GoalNodeView key={g.id} g={g} />)}
        </View>
      ) : (
        <Text className="px-1 text-sm text-slate-400">Henüz hedef yok.</Text>
      )}

      <FormSheet visible={open} title="Hedef ekle" onClose={() => setOpen(false)}>
        <View className="gap-4 pb-2">
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Hedef</Text>
            <TextInput value={title} onChangeText={setTitle} placeholder="örn. Bu ay 4 deneme çöz" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
          </View>
          <View className="flex-row gap-3">
            <View className="flex-1 gap-1">
              <Text className="text-xs font-medium text-slate-600">Hedef sayı</Text>
              <TextInput value={target} onChangeText={(v) => setTarget(v.replace(/[^0-9]/g, "").slice(0, 5))} keyboardType="number-pad" placeholder="opsiyonel" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
            </View>
            <View className="flex-1 gap-1">
              <Text className="text-xs font-medium text-slate-600">Birim</Text>
              <TextInput value={unit} onChangeText={setUnit} placeholder="test / deneme" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
            </View>
          </View>
          <Pressable
            onPress={() => { onCreate({ title: title.trim(), kind: "custom", target_value: target ? Number(target) : null, unit: unit.trim() || null }); setOpen(false); setTitle(""); setTarget(""); setUnit(""); }}
            disabled={busy || title.trim().length < 2}
            className={cn("items-center rounded-xl py-3.5", busy || title.trim().length < 2 ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
          >
            <Text className="text-base font-semibold text-white">Hedefi ekle</Text>
          </Pressable>
        </View>
      </FormSheet>
    </View>
  );
}

// ---------- AI Koçluk İçgörüsü (KS4) ----------
function InsightList({ icon, color, title, items }: { icon: keyof typeof Ionicons.glyphMap; color: string; title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <View className="gap-2">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name={icon} size={16} color={color} />
        <Text className="text-sm font-semibold text-slate-700">{title}</Text>
      </View>
      <View className="gap-1.5">
        {items.map((s, i) => (
          <View key={i} className="flex-row gap-2">
            <Text className="text-slate-400">•</Text>
            <Text className="flex-1 text-sm leading-5 text-slate-700">{s}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export function CoachInsightView({ cache, busy, onGenerate }: { cache: CoachingInsightCache; busy: boolean; onGenerate: () => void }) {
  const ins = cache.insight;

  if (!ins) {
    return (
      <View className="gap-4">
        <View className="items-center gap-2 rounded-2xl border border-dashed border-violet-200 bg-violet-50/40 px-6 py-8">
          <Ionicons name="sparkles" size={30} color="#7c3aed" />
          <Text className="text-center text-base font-semibold text-slate-800">AI Koçluk İçgörüsü</Text>
          <Text className="text-center text-sm leading-5 text-slate-500">
            Seans kayıtları ve akademik durumdan yola çıkarak bir sonraki seans için özet, önerilen gündem ve
            psikolojik ipuçları hazırlar.
          </Text>
        </View>
        <Pressable onPress={onGenerate} disabled={busy} className={cn("flex-row items-center justify-center gap-2 rounded-xl py-3.5", busy ? "bg-violet-300" : "bg-violet-600 active:bg-violet-700")}>
          <Ionicons name="sparkles" size={18} color="#fff" />
          <Text className="text-base font-semibold text-white">{busy ? "Oluşturuluyor…" : "İçgörü oluştur (kredi)"}</Text>
        </Pressable>
        <Text className="text-center text-[11px] text-slate-400">Yapay zekâ özelliği — kullanımı kredinden düşer. Yalnız sen görürsün.</Text>
      </View>
    );
  }

  return (
    <View className="gap-4">
      {cache.is_stale ? (
        <View className="flex-row items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <Ionicons name="time-outline" size={16} color="#b45309" />
          <Text className="flex-1 text-xs text-amber-800">
            Bu içgörü {ins.based_on_sessions} seansa dayanıyor; sonrasında yeni kayıt eklendi. Güncel öneri için yenile.
          </Text>
        </View>
      ) : null}

      <View className="rounded-2xl border border-violet-200 bg-violet-50/50 p-4">
        <View className="mb-1.5 flex-row items-center gap-1.5">
          <Ionicons name="sparkles" size={16} color="#7c3aed" />
          <Text className="text-sm font-semibold text-violet-700">Özet</Text>
        </View>
        <Text className="text-sm leading-6 text-slate-800">{ins.summary}</Text>
      </View>

      <InsightList icon="list-outline" color="#0e7490" title="Bu seans konuş" items={ins.agenda_suggestions} />
      <InsightList icon="heart-outline" color="#059669" title="Psikolojik ipuçları" items={ins.psychological_tips} />
      <InsightList icon="alert-circle-outline" color="#be123c" title="Dikkat" items={ins.watch_outs} />

      <View className="flex-row items-center justify-between border-t border-slate-100 pt-3">
        <Text className="text-[11px] text-slate-400">{ins.based_on_sessions} seansa dayanıyor</Text>
        <Pressable onPress={onGenerate} disabled={busy} className={cn("flex-row items-center gap-1.5 rounded-lg border px-3 py-2", busy ? "border-slate-200" : "border-violet-300 active:bg-violet-50")}>
          <Ionicons name="refresh" size={15} color="#7c3aed" />
          <Text className="text-sm font-semibold text-violet-700">{busy ? "Yenileniyor…" : "Yenile (kredi)"}</Text>
        </Pressable>
      </View>
      <Text className="text-center text-[11px] text-slate-400">Öneri amaçlıdır; klinik teşhis değildir. Yalnız sen görürsün.</Text>
    </View>
  );
}
