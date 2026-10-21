import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { subjectColors } from "@/lib/subject-colors";
import type { StudentAnalytics, StudentWeeklyProgress, TopicFocusRow, WPDay } from "@/lib/student-progress";

/**
 * Mobil Gelişim sekmesinin üst bölümü (2026-10-21) — web /student/progress ile aynı uçlar
 * ve aynı sayılar: sınava hazırlık · bu hafta · haftadan haftaya · ritim · derslerim ·
 * denemelerim · net kaybettiğim konular. Altında mevcut DNA/Odak/Tekrar/Hedef kartları durur.
 */
const nf = (n: number, d = 1) => n.toLocaleString("tr-TR", { maximumFractionDigits: d });

function Card({ icon, title, desc, link, onLink, children }: {
  icon: keyof typeof Ionicons.glyphMap; title: string; desc?: string; link?: string; onLink?: () => void; children: React.ReactNode;
}) {
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="mb-3 flex-row items-start justify-between gap-2">
        <View className="flex-1 flex-row items-start gap-2.5">
          <View className="size-8 items-center justify-center rounded-lg bg-brand-700">
            <Ionicons name={icon} size={16} color="#fff" />
          </View>
          <View className="flex-1">
            <Text className="text-[15px] font-bold text-slate-900">{title}</Text>
            {desc ? <Text className="text-xs text-slate-500">{desc}</Text> : null}
          </View>
        </View>
        {link && onLink ? (
          <Pressable onPress={onLink} hitSlop={8}>
            <Text className="text-xs font-semibold text-brand-700">{link} →</Text>
          </Pressable>
        ) : null}
      </View>
      {children}
    </View>
  );
}

const STATUS = {
  green: { chip: "Yetişiyorsun", cls: "bg-emerald-400", text: "text-emerald-950" },
  amber: { chip: "Biraz hızlanmalısın", cls: "bg-amber-300", text: "text-amber-950" },
  red: { chip: "Hızlanman gerekiyor", cls: "bg-rose-300", text: "text-rose-950" },
} as const;

function Hero({ a }: { a: StudentAnalytics }) {
  const p = a.projection;
  const s = a.summary;
  const st = STATUS[p.status];
  const donePct = p.total_tests > 0 ? Math.min(100, Math.round((100 * p.completed) / p.total_tests)) : 0;
  const sentence = p.total_tests === 0
    ? "Kaynakların atanınca tempon ve sınava yetişme durumun burada görünür."
    : p.remaining <= 0
      ? "Kaynaklarındaki bütün testleri bitirdin!"
      : p.gap >= 0
        ? `Bu tempoyla kalan ${p.remaining} testi sınavdan önce bitirirsin.`
        : `Bu tempoyla ${Math.abs(p.gap)} test eksik kalır — günde ${nf(p.required_rate)} test çözersen yetişirsin.`;
  const tiles = [
    { icon: "speedometer-outline" as const, label: "Günlük tempo", value: `${nf(s.rate_7d)} test`, note: p.required_rate > 0 ? `gereken ${nf(p.required_rate)}` : "son 7 gün" },
    { icon: "checkmark-done-outline" as const, label: "Düzenlilik", value: `%${s.consistency_7d_pct}`, note: "programlı günler (7 gün)" },
    { icon: "flame-outline" as const, label: "En uzun seri", value: `${s.longest_streak_30} gün`, note: "son 30 gün" },
    { icon: "pulse-outline" as const, label: "Aktif gün", value: `${s.active_days_30}/30`, note: "son 30 gün" },
  ];
  return (
    <View className="overflow-hidden rounded-3xl bg-indigo-950 p-5">
      <Text className="text-[11px] font-bold uppercase tracking-widest text-cyan-200">Sınava hazırlık</Text>
      {p.days_left != null ? (
        <View className="mt-1 flex-row items-end gap-2">
          <Text className="text-5xl font-extrabold text-white">{p.days_left}</Text>
          <Text className="pb-1.5 text-base font-semibold text-cyan-100">gün kaldı{p.exam_label ? ` · ${p.exam_label}` : ""}</Text>
        </View>
      ) : (
        <Text className="mt-1 text-xl font-bold text-white">Sınav tarihin tanımlı değil</Text>
      )}
      {p.total_tests > 0 ? (
        <View className={`mt-2 self-start rounded-full px-3 py-1 ${st.cls}`}>
          <Text className={`text-xs font-bold ${st.text}`}>{st.chip}</Text>
        </View>
      ) : null}
      <Text className="mt-2 text-sm text-cyan-50">{sentence}</Text>
      {p.total_tests > 0 ? (
        <View className="mt-3">
          <View className="flex-row justify-between">
            <Text className="text-[11px] text-cyan-100">Kaynaklarındaki testler</Text>
            <Text className="text-[11px] text-cyan-100">{p.completed}/{p.total_tests} · %{donePct}</Text>
          </View>
          <View className="mt-1 h-2.5 overflow-hidden rounded-full bg-white/15">
            <View className="h-full rounded-full bg-emerald-300" style={{ width: `${donePct}%` }} />
          </View>
        </View>
      ) : null}
      <View className="mt-4 flex-row flex-wrap justify-between gap-y-2">
        {tiles.map((t) => (
          <View key={t.label} className="rounded-2xl bg-white/10 p-3" style={{ width: "48.5%" }}>
            <View className="flex-row items-center gap-1">
              <Ionicons name={t.icon} size={12} color="#a5f3fc" />
              <Text className="text-[10px] font-semibold uppercase text-cyan-100">{t.label}</Text>
            </View>
            <Text className="mt-0.5 text-xl font-extrabold text-white">{t.value}</Text>
            <Text className="text-[10px] text-cyan-100">{t.note}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const DAY_CLS: Record<WPDay["state"], { box: string; text: string }> = {
  done: { box: "bg-emerald-600", text: "text-white" },
  partial: { box: "bg-amber-400", text: "text-amber-950" },
  missed: { box: "bg-rose-600", text: "text-white" },
  today: { box: "bg-brand-700", text: "text-white" },
  future: { box: "bg-slate-100", text: "text-slate-500" },
  none: { box: "border border-dashed border-slate-300", text: "text-slate-400" },
};

const STATUS_CHIP: Record<string, { label: string; cls: string; text: string }> = {
  normal: { label: "Her zamanki", cls: "bg-slate-100", text: "text-slate-700" },
  above: { label: "Normalden iyi", cls: "bg-blue-100", text: "text-blue-800" },
  below: { label: "Normalden kötü", cls: "bg-orange-100", text: "text-orange-800" },
  critical: { label: "Geçmişin en kötüsü", cls: "bg-rose-700", text: "text-white" },
  insufficient: { label: "Veri az", cls: "bg-slate-100", text: "text-slate-600" },
};

function ThisWeek({ w }: { w: StudentWeeklyProgress }) {
  if (!w.has_program || !w.week) return null;
  const wk = w.week;
  const cards = [w.headline.gorev_pct, w.headline.test_done].filter(Boolean);
  const pr = w.projection;
  return (
    <Card icon="flag-outline" title={wk.kind === "donem" ? "Bu dönem nasıl gidiyor?" : "Bu hafta nasıl gidiyor?"}
          desc={`${wk.label} · ${wk.ended ? "bitti" : `${wk.day_index}. gün / ${wk.days}`}`}>
      <View className="gap-2.5">
        {cards.map((c) => {
          const chip = STATUS_CHIP[c.status];
          return (
            <View key={c.key} className="rounded-xl border border-slate-200 p-3">
              <View className="flex-row items-start justify-between gap-2">
                <View>
                  <Text className="text-xs font-semibold text-slate-600">{c.name}</Text>
                  <Text className="text-2xl font-extrabold text-slate-900">{c.value_label}</Text>
                </View>
                {chip ? (
                  <View className={`rounded-full px-2.5 py-1 ${chip.cls}`}>
                    <Text className={`text-[10px] font-bold ${chip.text}`}>{chip.label}</Text>
                  </View>
                ) : null}
              </View>
              <Text className="mt-1 text-xs text-slate-500">{c.verdict}</Text>
            </View>
          );
        })}
      </View>
      <View className="mt-3 flex-row gap-1">
        {w.days.map((d) => {
          const c = DAY_CLS[d.state];
          return (
            <View key={d.date} className={`flex-1 items-center rounded-lg py-1.5 ${c.box}`}>
              <Text className={`text-[9px] font-bold uppercase ${c.text}`}>{d.day}</Text>
              <Text className={`text-[11px] font-extrabold ${c.text}`}>{d.total > 0 ? `${d.done}/${d.total}` : "—"}</Text>
            </View>
          );
        })}
      </View>
      {pr?.projected_pct != null && !wk.ended ? (
        <Text className="mt-3 rounded-lg bg-cyan-50 px-3 py-2 text-xs text-slate-700">
          Böyle giderse hafta sonunda görevlerinin %{Math.round(pr.projected_pct)}&apos;ini tamamlarsın
          {pr.band_low != null && pr.band_high != null ? ` — genelde %${Math.round(pr.band_low)}–${Math.round(pr.band_high)}.` : "."}
        </Text>
      ) : null}
    </Card>
  );
}

function Weeks({ w }: { w: StudentWeeklyProgress }) {
  const pts = w.chart.filter((c) => c.value != null);
  if (pts.length < 2) return null;
  return (
    <Card icon="stats-chart-outline" title="Haftadan haftaya" desc="Görevlerinin yüzde kaçını tamamladın">
      <View className="h-36 flex-row items-end gap-1.5">
        {pts.map((c) => (
          <View key={c.label + c.range} className="h-full flex-1 items-center justify-end gap-0.5">
            <Text className={`text-[10px] font-bold ${c.current ? "text-brand-700" : "text-slate-500"}`}>%{Math.round(c.value ?? 0)}</Text>
            <View className={`w-full rounded-t-md ${c.current ? "bg-brand-600" : "bg-slate-300"}`} style={{ height: `${Math.max(3, (c.value ?? 0) * 0.75)}%` }} />
            <Text className="text-[9px] text-slate-500">{c.current ? "bu h." : c.label}</Text>
          </View>
        ))}
      </View>
      {w.period_summary?.median != null ? (
        <Text className="mt-2 text-xs text-slate-500">Ortancan %{Math.round(w.period_summary.median)} — {w.period_summary.weeks} hafta üzerinden.</Text>
      ) : null}
    </Card>
  );
}

function Rhythm({ a }: { a: StudentAnalytics }) {
  const cal = a.activity_calendar;
  const lead = cal.length ? cal[0].weekday : 0;
  const cells: ({ date: string; active: boolean; has_plan: boolean } | null)[] = [...Array(lead).fill(null), ...cal];
  const rows: (typeof cells)[] = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
  return (
    <Card icon="calendar-outline" title="Çalışma ritmim" desc="Yeşil: çalıştın · kırmızı: görev vardı, çalışılmadı">
      <View className="gap-1">
        <View className="flex-row gap-1">
          {["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"].map((x) => (
            <Text key={x} className="flex-1 text-center text-[10px] font-semibold text-slate-500">{x}</Text>
          ))}
        </View>
        {rows.map((r, i) => (
          <View key={i} className="flex-row gap-1">
            {Array.from({ length: 7 }).map((_, j) => {
              const c = r[j];
              return (
                <View key={j} className={`h-6 flex-1 rounded ${!c ? "" : c.active ? "bg-emerald-500" : c.has_plan ? "bg-rose-500" : "bg-slate-100"}`} />
              );
            })}
          </View>
        ))}
      </View>
      {(a.dow_all ?? []).length > 0 ? (
        <>
          <Text className="mb-1 mt-3 text-xs font-semibold text-slate-700">Hangi gün ne kadar tamamlıyorum?</Text>
          <View className="flex-row gap-1">
            {(a.dow_all ?? []).map((r) => (
              <View key={r.weekday} className="flex-1 items-center">
                <View className="h-12 w-full justify-end overflow-hidden rounded-md bg-slate-100">
                  <View
                    className={r.hit_pct == null ? "" : r.hit_pct >= 75 ? "bg-emerald-500" : r.hit_pct >= 50 ? "bg-amber-400" : "bg-rose-500"}
                    style={{ height: `${Math.max(4, r.hit_pct ?? 0)}%` }}
                  />
                </View>
                <Text className="text-[9px] text-slate-500">{r.label}</Text>
                <Text className="text-[10px] font-bold text-slate-800">{r.hit_pct == null ? "—" : `%${r.hit_pct}`}</Text>
              </View>
            ))}
          </View>
        </>
      ) : null}
    </Card>
  );
}

function accCls(p: number) {
  return p >= 70 ? "text-emerald-700" : p >= 50 ? "text-amber-700" : "text-rose-700";
}

function Subjects({ a }: { a: StudentAnalytics }) {
  const rows = (a.subject_work ?? []).filter((r) => r.total > 0 || r.total_topics > 0);
  const c = a.curriculum;
  if (rows.length === 0 && !c) return null;
  return (
    <Card icon="library-outline" title="Derslerim" desc="Son 30 gün: test, doğruluk, müfredat"
          link="Konular" onLink={() => router.push({ pathname: "/topic-performance", params: { source: "student" } })}>
      {c ? (
        <View className="mb-3 flex-row items-center gap-3 rounded-xl bg-indigo-50 px-3 py-2.5">
          <Text className="text-2xl font-extrabold text-indigo-900">%{Math.round(c.coverage_pct)}</Text>
          <Text className="flex-1 text-xs text-slate-700">
            {c.focus_grade ? `${c.focus_grade}. sınıf müfredatında ` : "Müfredatta "}
            {c.total_topics} konunun {c.started_topics} tanesine başladın.
          </Text>
        </View>
      ) : null}
      <View className="gap-2">
        {rows.map((r) => {
          const col = subjectColors(r.name);
          return (
            <View key={r.subject_id} className="rounded-xl border border-slate-200 p-3" style={{ borderLeftWidth: 4, borderLeftColor: col.rail }}>
              <View className="flex-row items-center justify-between">
                <Text className="flex-1 text-sm font-bold text-slate-900">{r.name}</Text>
                <Text className="text-xs text-slate-500">
                  {r.total} test{r.accuracy_pct != null ? " · " : ""}
                  {r.accuracy_pct != null ? <Text className={`font-bold ${accCls(r.accuracy_pct)}`}>%{Math.round(r.accuracy_pct)} doğru</Text> : null}
                </Text>
              </View>
              {r.coverage_pct != null && r.total_topics > 0 ? (
                <View className="mt-1.5">
                  <View className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <View className="h-full rounded-full bg-indigo-600" style={{ width: `${Math.min(100, r.coverage_pct)}%` }} />
                  </View>
                  <Text className="mt-0.5 text-[10px] text-slate-500">{r.started_topics}/{r.total_topics} konu{r.next_topic ? ` · sıradaki: ${r.next_topic}` : ""}</Text>
                </View>
              ) : null}
            </View>
          );
        })}
      </View>
    </Card>
  );
}

function Exams({ a }: { a: StudentAnalytics }) {
  return (
    <Card icon="trophy-outline" title="Denemelerim" desc="Son 60 gün · netler yalnız aynı türde kıyaslanır"
          link="Tümü" onLink={() => router.navigate("/(app)/student/exams")}>
      {a.exam_trend.length === 0 ? (
        <Text className="text-sm text-slate-500">Son 60 günde deneme sonucu yok.</Text>
      ) : (
        <>
          {a.exam_trend_delta != null ? (
            <View className={`mb-2 flex-row items-center gap-2 rounded-xl px-3 py-2 ${a.exam_trend_delta >= 0 ? "bg-emerald-600" : "bg-rose-600"}`}>
              <Ionicons name={a.exam_trend_delta >= 0 ? "trending-up" : "trending-down"} size={16} color="#fff" />
              <Text className="flex-1 text-xs font-semibold text-white">
                Son {a.exam_trend_section} denemende {a.exam_trend_delta >= 0 ? "+" : ""}{nf(a.exam_trend_delta, 2)} net
              </Text>
            </View>
          ) : null}
          {a.exam_trend.map((e, i) => (
            <View key={`${e.title}-${i}`} className="flex-row items-center justify-between border-b border-slate-100 py-2">
              <View className="flex-1 pr-2">
                <Text className="text-sm font-medium text-slate-900">{e.title}</Text>
                <Text className="text-[11px] text-slate-500">{e.section_label}{e.exam_date ? ` · ${e.exam_date.split("-").reverse().join(".")}` : ""}</Text>
              </View>
              <Text className="text-lg font-extrabold text-slate-900">{nf(e.net, 2)}</Text>
            </View>
          ))}
        </>
      )}
    </Card>
  );
}

function Weak({ focus }: { focus: TopicFocusRow[] }) {
  const rows = focus.slice(0, 5);
  return (
    <Card icon="locate-outline" title="Net kaybettiğim konular" desc="En çok yanlış/boş bıraktığın konular"
          link="Konular" onLink={() => router.push({ pathname: "/topic-performance", params: { source: "student" } })}>
      {rows.length === 0 ? (
        <Text className="text-sm text-slate-500">Belirgin bir zayıf konu yok. Doğru/yanlış girdikçe burası dolar.</Text>
      ) : (
        <View className="gap-2">
          {rows.map((r, i) => (
            <View key={`${r.topic_name}-${i}`} className="flex-row items-center gap-3 rounded-xl border border-slate-200 p-2.5">
              <View className="size-7 items-center justify-center rounded-full bg-slate-800">
                <Text className="text-xs font-bold text-white">{i + 1}</Text>
              </View>
              <View className="flex-1">
                <Text className="text-sm font-semibold text-slate-900">{r.topic_name}</Text>
                <Text className="text-[11px] text-slate-500">
                  {r.subject_name ?? ""}{r.exam_only ? " · denemede" : ""}
                  {r.accuracy_pct != null ? ` · %${Math.round(r.accuracy_pct)} doğru` : ""}{r.wrong > 0 ? ` · ${r.wrong} yanlış` : ""}
                </Text>
              </View>
              {r.level === "zayif" || r.level === "dikkat" ? (
                <View className={`rounded-full px-2 py-0.5 ${r.level === "zayif" ? "bg-rose-600" : "bg-amber-400"}`}>
                  <Text className={`text-[10px] font-bold ${r.level === "zayif" ? "text-white" : "text-amber-950"}`}>{r.level === "zayif" ? "Zayıf" : "Dikkat"}</Text>
                </View>
              ) : null}
            </View>
          ))}
        </View>
      )}
    </Card>
  );
}

export function ProgressOverview({ a, w, focus }: { a: StudentAnalytics; w: StudentWeeklyProgress | undefined; focus: TopicFocusRow[] }) {
  return (
    <View className="gap-4">
      <Hero a={a} />
      {w ? <ThisWeek w={w} /> : null}
      {w ? <Weeks w={w} /> : null}
      <Rhythm a={a} />
      <Subjects a={a} />
      <Exams a={a} />
      <Weak focus={focus} />
    </View>
  );
}
