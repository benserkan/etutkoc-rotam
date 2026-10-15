import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import {
  Badge,
  Empty,
  InfoNote,
  InstitutionScreen,
  Kpi,
  KpiGrid,
  MiniBars,
  ProgressBar,
  Section,
  pctText,
  rateTone,
} from "@/components/institution/ui";
import {
  getInstitutionPoolOverview,
  institutionKeys,
  type InstitutionPoolOverviewResponse,
  type PoolCoachLoadRow,
  type PoolGroupRow,
  type PoolLateSessionRow,
} from "@/lib/institution";
import { subjectColors } from "@/lib/subject-colors";
import { cn } from "@/lib/utils";

function fmtDay(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

/** Yığılmış yatay çubuk (katılım / tempo dağılımı). */
function StackBar({ parts }: { parts: { value: number; color: string; label: string }[] }) {
  const total = parts.reduce((a, p) => a + p.value, 0);
  return (
    <View className="gap-2 rounded-2xl border border-slate-200 bg-white p-3">
      <View className="h-3 w-full flex-row overflow-hidden rounded-full bg-slate-100">
        {total > 0
          ? parts.map((p, i) =>
              p.value > 0 ? <View key={i} className={p.color} style={{ width: `${(p.value / total) * 100}%` }} /> : null,
            )
          : null}
      </View>
      <View className="flex-row flex-wrap gap-x-3 gap-y-1">
        {parts.map((p, i) => (
          <View key={i} className="flex-row items-center gap-1">
            <View className={cn("size-2 rounded-full", p.color)} />
            <Text className="text-[11px] text-slate-600">
              {p.label} <Text className="font-bold text-slate-900">{p.value}</Text>
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function GroupRow({ g }: { g: PoolGroupRow }) {
  const t = rateTone(g.last_pct ?? g.open_pct);
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", t.border)}>
      <View className="flex-row items-center justify-between">
        <Text className="flex-1 text-sm font-semibold text-slate-900">{g.class_group}</Text>
        <Text className={cn("text-base font-extrabold", t.text)}>{pctText(g.last_pct)}</Text>
      </View>
      <View className="mt-1">
        <ProgressBar pct={g.last_pct} tone={t.bar} />
      </View>
      <Text className="mt-1 text-[11px] text-slate-500">
        {g.students} öğrenci · açık dönem {pctText(g.open_pct)}
        {g.late_sessions > 0 ? ` · ${g.late_sessions} geciken seans` : ""}
        {g.red > 0 ? ` · ${g.red} kırmızı` : ""}
        {g.amber > 0 ? ` · ${g.amber} sarı` : ""}
      </Text>
      {!g.lessons_set ? <Text className="mt-1 text-[11px] text-amber-700">Ders programı girilmemiş</Text> : null}
    </View>
  );
}

function LateRow({ r }: { r: PoolLateSessionRow }) {
  const red = r.level === "red";
  return (
    <View className={cn("rounded-xl border border-l-4 bg-white p-3", red ? "border-slate-200 border-l-rose-500" : "border-slate-200 border-l-amber-400")}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-sm font-semibold text-slate-900">{r.student_name}</Text>
        <Badge label={`${r.late_days} gün gecikti`} tone={red ? "rose" : "amber"} />
      </View>
      <Text className="mt-1 text-[11px] text-slate-500">
        {r.coach_name}
        {r.class_group ? ` · ${r.class_group}` : ""} · dönem açılışı {fmtDay(r.opened_on)} ({r.days_open} gündür açık) · beklenen{" "}
        {fmtDay(r.expected_next_on)} · havuz {pctText(r.pct)}
      </Text>
    </View>
  );
}

function CoachRow({ c }: { c: PoolCoachLoadRow }) {
  return (
    <Pressable
      onPress={() => router.push({ pathname: "/institution-teacher", params: { id: String(c.coach_id) } } as never)}
      className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
    >
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-sm font-semibold text-slate-900">{c.coach_name}</Text>
        <View className="rounded-full bg-slate-800 px-2 py-0.5">
          <Text className="text-[11px] font-bold text-white">yük {c.load}</Text>
        </View>
      </View>
      <Text className="mt-1 text-[11px] text-slate-500">
        {c.students} öğrenci · açık dönem {pctText(c.avg_open_pct)} · bugün {c.today_sessions} görüşme
      </Text>
      <View className="mt-2 flex-row flex-wrap gap-1">
        {c.late_sessions > 0 ? <Badge label={`${c.late_sessions} geciken seans`} tone="amber" /> : null}
        {c.red > 0 ? <Badge label={`${c.red} kırmızı`} tone="rose" /> : null}
        {c.amber > 0 ? <Badge label={`${c.amber} sarı`} tone="amber" /> : null}
        {c.pending_approval > 0 ? <Badge label={`${c.pending_approval} onay bekliyor`} tone="sky" /> : null}
        {c.bulk > 0 ? <Badge label={`${c.bulk} toplu işaretleme`} tone="violet" /> : null}
        {c.paper > 0 ? <Badge label={`${c.paper} kağıt öğrencisi`} /> : null}
      </View>
    </Pressable>
  );
}

export default function InstitutionPoolScreen() {
  const q = useQuery({ queryKey: institutionKeys.poolOverview, queryFn: getInstitutionPoolOverview });

  return (
    <InstitutionScreen<InstitutionPoolOverviewResponse> title="Haftalık Havuz" query={q}>
      {(d) => {
        if (d.students === 0) {
          return <Empty text="Kurumunda haftalık havuz modunda öğrenci yok. Rehber, öğrencinin sayfasından havuz moduna geçirince burada görünür." />;
        }
        const p = d.participation;
        const pace = d.pace;
        const src = d.sources;
        const coachShare = src.done_units > 0 ? Math.round((src.coach_units / src.done_units) * 100) : null;
        return (
          <>
            <KpiGrid>
              <Kpi label="Havuz öğrencisi" value={String(d.students)} sub={`${d.coaches} rehber · ${d.open_periods} açık dönem`} />
              <Kpi
                label="Son dönem ortalaması"
                value={pctText(d.avg_last_pct)}
                sub="kapanmış dönem, tatil hariç"
                tone={rateTone(d.avg_last_pct).text}
              />
              <Kpi
                label="Açık dönem şu an"
                value={pctText(d.avg_open_pct)}
                sub={d.avg_expected_pct != null ? `bu güne beklenen %${d.avg_expected_pct}` : "beklenen yok"}
                tone={rateTone(d.avg_open_pct).text}
              />
              <Kpi
                label="Geciken seans"
                value={String(d.late_sessions)}
                sub={`${d.red_students} kırmızı · ${d.amber_students} sarı öğrenci`}
                tone={d.late_sessions > 0 ? "text-rose-600" : "text-slate-900"}
              />
            </KpiGrid>

            <Section title="Bugün öğrenciler" hint={`${p.students} öğrenci`}>
              <StackBar
                parts={[
                  { label: "İşaretledi", value: p.ticked_today, color: "bg-emerald-500" },
                  { label: "Kabı var", value: Math.max(0, p.cup_today - p.ticked_today), color: "bg-sky-500" },
                  { label: "Havuza dokunmadı", value: p.idle, color: "bg-rose-400" },
                  { label: "Kağıt öğrencisi", value: p.paper, color: "bg-slate-400" },
                ]}
              />
              <InfoNote>
                Kap = öğrencinin havuzdan o güne aldığı kalemler. Kağıt öğrencisi uygulamaya kayıt girmez; ilerlemesini rehber seansta işaretler.
              </InfoNote>
            </Section>

            <Section title="Tempo (açık dönem)">
              <StackBar
                parts={[
                  { label: "Önde", value: pace.onde, color: "bg-emerald-500" },
                  { label: "Yolunda", value: pace.yolunda, color: "bg-sky-500" },
                  { label: "Geride", value: pace.geride, color: "bg-amber-400" },
                  { label: "Belirsiz", value: pace.belirsiz, color: "bg-slate-300" },
                ]}
              />
              <InfoNote>
                Yapılan birim · {src.done_units}/{src.total_units}
                {coachShare != null ? ` · rehberin seansta işaretlediği pay %${coachShare}` : ""}
              </InfoNote>
            </Section>

            {d.signals.some((s) => s.students > 0) ? (
              <Section title="Uyarı aileleri" hint="yalnız öğrencisi olanlar">
                {d.signals.filter((s) => s.students > 0).map((s) => (
                  <View key={s.key} className="rounded-xl border border-slate-200 bg-white p-3">
                    <View className="flex-row items-center justify-between gap-2">
                      <Text className="flex-1 text-sm font-semibold text-slate-900">{s.label}</Text>
                      <Text className="text-sm font-bold text-slate-900">{s.students} öğr.</Text>
                    </View>
                    <Text className="mt-0.5 text-[11px] text-slate-500">{s.hint}</Text>
                    <View className="mt-2 flex-row gap-1">
                      {s.red > 0 ? <Badge label={`${s.red} kırmızı`} tone="rose" /> : null}
                      {s.amber > 0 ? <Badge label={`${s.amber} sarı`} tone="amber" /> : null}
                      {s.info > 0 ? <Badge label={`${s.info} bilgi`} tone="sky" /> : null}
                    </View>
                  </View>
                ))}
              </Section>
            ) : null}

            {d.subjects.length > 0 ? (
              <Section title="Derslere göre ilerleme" hint="açık dönem, birim">
                <View className="gap-3 rounded-2xl border border-slate-200 bg-white p-3">
                  {d.subjects.map((s) => {
                    const c = subjectColors(s.name);
                    return (
                      <View key={s.name} className="gap-1">
                        <View className="flex-row items-center justify-between gap-2">
                          <Text className="flex-1 text-[13px] font-semibold text-slate-800">{s.name}</Text>
                          <Text className="text-[12px] text-slate-500">
                            {s.done}/{s.total} · <Text className="font-bold text-slate-900">%{s.pct}</Text>
                          </Text>
                        </View>
                        <View className="h-2 overflow-hidden rounded-full bg-slate-100">
                          <View style={{ width: `${Math.min(100, s.pct)}%`, backgroundColor: c.rail }} className="h-2 rounded-full" />
                        </View>
                        <Text className="text-[10px] text-slate-400">{s.students} öğrencide kalem var</Text>
                      </View>
                    );
                  })}
                </View>
              </Section>
            ) : null}

            {d.trend.length > 0 ? (
              <Section title="Son haftalar" hint="kapanan dönemlerin ortalaması">
                <MiniBars points={d.trend.map((t) => ({ label: fmtDay(t.week_start), value: t.avg_pct }))} />
              </Section>
            ) : null}

            {d.late.length > 0 ? (
              <Section title="Seansı geciken öğrenciler" hint="beklenen gün 3+ geçti">
                {d.late.map((r) => (
                  <LateRow key={r.student_id} r={r} />
                ))}
              </Section>
            ) : null}

            {d.groups.length > 0 ? (
              <Section title="Şubeler" hint="son dönem havuz %">
                {d.groups.map((g) => (
                  <GroupRow key={g.class_group} g={g} />
                ))}
              </Section>
            ) : null}

            {d.coaches_rows.length > 0 ? (
              <Section title="Rehber yükü" hint="bugün görüşme + geciken + kırmızı">
                {d.coaches_rows.map((c) => (
                  <CoachRow key={c.coach_id} c={c} />
                ))}
              </Section>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
