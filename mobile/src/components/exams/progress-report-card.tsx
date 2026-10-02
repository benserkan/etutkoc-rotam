import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { ApiError } from "@/lib/api";
import {
  addAgendaItems,
  examProgressKeys,
  fmtNet,
  fmtSigned,
  fmtTRDate,
  getExamProgress,
  parseNum,
  setExamTarget,
  type ExamProgressResponse,
} from "@/lib/exam-progress";
import { cn } from "@/lib/utils";

/**
 * Deneme Faz 2 (mobil) — Gelişim raporu kartı: hedef net, özet, otomatik yorum,
 * aksiyon planı (koç: seçilenleri seans gündemine ekler), ders gidişatı.
 * studentId verilirse koç ucu (düzenlenebilir), null ise öğrenci (salt okuma).
 */

const TONE = {
  good: { box: "border-emerald-200 bg-emerald-50", text: "text-emerald-900", icon: "trending-up" as const, color: "#047857" },
  warn: { box: "border-amber-200 bg-amber-50", text: "text-amber-900", icon: "warning-outline" as const, color: "#b45309" },
  info: { box: "border-sky-200 bg-sky-50", text: "text-sky-900", icon: "bulb-outline" as const, color: "#0369a1" },
};

const PRIORITY: Record<number, { label: string; cls: string }> = {
  1: { label: "Öncelikli", cls: "bg-rose-600" },
  2: { label: "Önemli", cls: "bg-amber-600" },
  3: { label: "Takip", cls: "bg-slate-500" },
};

function Card({ title, icon, children, right }: {
  title: string;
  icon: React.ComponentProps<typeof Ionicons>["name"];
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center justify-between gap-2">
        <View className="flex-1 flex-row items-center gap-1.5">
          <Ionicons name={icon} size={16} color="#0e7490" />
          <Text className="text-sm font-semibold text-slate-800">{title}</Text>
        </View>
        {right}
      </View>
      <View className="mt-3">{children}</View>
    </View>
  );
}

export function ProgressReportCard({
  studentId,
  section,
  parentStudentId = null,
}: {
  studentId: number | null;
  section: string | null;
  /** Veli görünümü: çocuğun id'si (studentId null) — salt okuma. */
  parentStudentId?: number | null;
}) {
  const isTeacher = studentId != null;
  const isParent = parentStudentId != null;
  const q = useQuery({
    queryKey: examProgressKeys.progress(studentId, section, parentStudentId),
    queryFn: () => getExamProgress(studentId, section, parentStudentId),
  });
  const [targetOpen, setTargetOpen] = React.useState(false);

  if (q.isLoading) {
    return (
      <View className="items-center py-6">
        <ActivityIndicator color="#0e7490" />
      </View>
    );
  }
  const d = q.data;
  if (!d || !d.stats) return null;
  const s = d.stats;
  const t = d.target;

  return (
    <View className="gap-3">
      <Text className="px-1 pt-1 text-sm font-semibold text-slate-700">
        {isTeacher ? "Gelişim raporu" : "Gelişim ve hedef"} · {d.section_label}
      </Text>

      <Card
        title="Hedef net"
        icon="flag-outline"
        right={
          isTeacher ? (
            <Pressable onPress={() => setTargetOpen(true)} hitSlop={8} className="rounded-lg bg-brand-50 px-2.5 py-1">
              <Text className="text-xs font-semibold text-brand-700">{t ? "Düzenle" : "Hedef belirle"}</Text>
            </Pressable>
          ) : null
        }
      >
        {!t ? (
          <Text className="text-sm text-slate-500">
            {isTeacher
              ? "Bu tür için hedef net belirlenmedi."
              : isParent
                ? "Koç henüz hedef belirlemedi."
                : "Koçun henüz hedef belirlemedi."}
          </Text>
        ) : (
          <View className="gap-2">
            <View className="flex-row items-end justify-between">
              <View>
                <Text className="text-[11px] text-slate-500">Hedef</Text>
                <Text className="text-3xl font-extrabold text-slate-900">{fmtNet(t.target_net)}</Text>
              </View>
              <View className="items-end">
                <Text className="text-[11px] text-slate-500">Şu an ({t.basis})</Text>
                <Text className="text-lg font-bold text-slate-800">{fmtNet(t.basis_net)}</Text>
                <Text className={cn("text-sm font-semibold", (t.gap ?? 0) <= 0 ? "text-emerald-700" : "text-amber-700")}>
                  {(t.gap ?? 0) <= 0 ? "Hedef tuttu" : `Kalan ${fmtNet(t.gap)} net`}
                </Text>
              </View>
            </View>
            {t.progress_pct != null ? (
              <View className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                <View
                  className={cn("h-full rounded-full", t.progress_pct >= 100 ? "bg-emerald-600" : "bg-amber-500")}
                  style={{ width: `${Math.min(100, t.progress_pct)}%` }}
                />
              </View>
            ) : null}
            <Text className="text-xs text-slate-500">
              {t.target_date ? `Hedef tarih ${fmtTRDate(t.target_date)}${t.weeks_left != null ? ` · ${t.weeks_left} hafta` : ""}` : ""}
              {t.per_week_needed ? ` · haftada ${fmtNet(t.per_week_needed)} net artış gerekir` : ""}
            </Text>
            {t.note ? <Text className="text-sm text-slate-700">Koç notu: {t.note}</Text> : null}
          </View>
        )}
      </Card>

      <Card title="Gelişim özeti" icon="trending-up-outline">
        <View className="flex-row flex-wrap">
          {[
            { l: "İlk → son", v: `${fmtNet(s.first_net)} → ${fmtNet(s.last_net)}`, sub: `${fmtSigned(s.change)} net` },
            { l: "Son 3 ortalama", v: fmtNet(s.avg_last3), sub: `Genel ${fmtNet(s.avg_net)}` },
            { l: "En iyi", v: fmtNet(s.best_net), sub: `${s.count} deneme` },
            { l: "Eğim", v: s.slope == null ? "—" : fmtSigned(s.slope), sub: "net / deneme" },
          ].map((x) => (
            <View key={x.l} className="w-1/2 py-1.5 pr-2">
              <Text className="text-[11px] text-slate-500">{x.l}</Text>
              <Text className="text-base font-bold text-slate-900">{x.v}</Text>
              <Text className="text-[11px] text-slate-400">{x.sub}</Text>
            </View>
          ))}
        </View>
      </Card>

      {d.commentary.length ? (
        <Card title="Otomatik yorum" icon="bulb-outline">
          <View className="gap-2">
            {d.commentary.map((c) => {
              const tn = TONE[c.tone] ?? TONE.info;
              return (
                <View key={c.text} className={cn("flex-row gap-2 rounded-xl border px-3 py-2", tn.box)}>
                  <Ionicons name={tn.icon} size={16} color={tn.color} style={{ marginTop: 1 }} />
                  <Text className={cn("flex-1 text-sm", tn.text)}>{c.text}</Text>
                </View>
              );
            })}
          </View>
        </Card>
      ) : null}

      <ActionPlan data={d} studentId={studentId} isParent={isParent} />

      {d.subjects.length ? (
        <Card title="Ders gidişatı" icon="list-outline">
          <View className="gap-1.5">
            {d.subjects.map((x) => (
              <View key={x.name} className="flex-row items-center justify-between border-b border-slate-100 pb-1.5">
                <Text className="flex-1 pr-2 text-sm text-slate-800">{x.name}</Text>
                <Text className="text-xs text-slate-500">
                  {fmtNet(x.first)} → <Text className="font-semibold text-slate-900">{fmtNet(x.last)}</Text>
                </Text>
                <Text
                  className={cn(
                    "w-16 text-right text-xs font-semibold",
                    (x.change ?? 0) >= 1 ? "text-emerald-700" : (x.change ?? 0) <= -1 ? "text-rose-700" : "text-slate-500",
                  )}
                >
                  {x.change == null ? "—" : fmtSigned(x.change)}
                </Text>
              </View>
            ))}
          </View>
        </Card>
      ) : null}

      {isTeacher ? (
        <FormSheet visible={targetOpen} title={`${d.section_label} hedef neti`} onClose={() => setTargetOpen(false)}>
          {targetOpen ? <TargetForm studentId={studentId} data={d} onDone={() => setTargetOpen(false)} /> : null}
        </FormSheet>
      ) : null}
    </View>
  );
}

function ActionPlan({
  data,
  studentId,
  isParent = false,
}: {
  data: ExamProgressResponse;
  studentId: number | null;
  isParent?: boolean;
}) {
  const isTeacher = studentId != null;
  const qc = useQueryClient();
  const [picked, setPicked] = React.useState<string[]>([]);
  const mut = useMutation({
    mutationFn: () =>
      addAgendaItems(
        studentId ?? 0,
        data.actions
          .filter((a) => picked.includes(a.key))
          .map((a) => ({ text: `${a.title} — ${a.detail}`, key: a.key, exam_id: a.exam_id, source: "exam" })),
      ),
    onSuccess: (res) => {
      setPicked([]);
      qc.invalidateQueries({ queryKey: examProgressKeys.all(studentId) });
      Alert.alert(
        "Seans gündemine eklendi",
        res.added > 0
          ? `${res.added} madde sıradaki seansın gündemine eklendi; yeni seans açarken işaretli gelir.`
          : "Bu maddeler zaten gündemde.",
      );
    },
    onError: (e) => Alert.alert("Eklenemedi", e instanceof ApiError ? e.message : "Bir hata oluştu."),
  });
  if (!data.actions.length) return null;
  return (
    <Card
      title={isTeacher ? "Aksiyon planı" : isParent ? "Çalışma öncelikleri" : "Çalışma önceliklerin"}
      icon="checkbox-outline"
    >
      <View className="gap-2">
        {data.actions.map((a) => {
          const p = PRIORITY[a.priority] ?? PRIORITY[3];
          const selectable = isTeacher && !a.queued;
          const on = picked.includes(a.key);
          return (
            <Pressable
              key={a.key}
              disabled={!selectable}
              onPress={() => setPicked((x) => (on ? x.filter((k) => k !== a.key) : [...x, a.key]))}
              className={cn("flex-row gap-2.5 rounded-xl border px-3 py-2.5", on ? "border-brand-600 bg-brand-50" : "border-slate-200")}
            >
              {isTeacher ? (
                <Ionicons
                  name={a.queued ? "checkmark-done-circle" : on ? "checkbox" : "square-outline"}
                  size={20}
                  color={a.queued ? "#0e7490" : on ? "#0e7490" : "#94a3b8"}
                />
              ) : null}
              <View className="flex-1">
                <View className="flex-row flex-wrap items-center gap-1.5">
                  <Text className="text-sm font-semibold text-slate-900">{a.title}</Text>
                  <Text className={cn("overflow-hidden rounded px-1.5 py-0.5 text-[10px] font-bold text-white", p.cls)}>
                    {p.label}
                  </Text>
                  {isTeacher && a.queued ? (
                    <Text className="overflow-hidden rounded bg-brand-700 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      Seans gündeminde
                    </Text>
                  ) : null}
                </View>
                <Text className="mt-0.5 text-xs text-slate-500">{a.detail}</Text>
              </View>
            </Pressable>
          );
        })}
        {isTeacher ? (
          <Pressable
            onPress={() => mut.mutate()}
            disabled={!picked.length || mut.isPending}
            className={cn("mt-1 items-center rounded-xl py-3", picked.length ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
          >
            <Text className="font-semibold text-white">
              {mut.isPending ? "Ekleniyor…" : `Seçilenleri seansa ekle${picked.length ? ` (${picked.length})` : ""}`}
            </Text>
          </Pressable>
        ) : null}
      </View>
    </Card>
  );
}

function TargetForm({ studentId, data, onDone }: { studentId: number; data: ExamProgressResponse; onDone: () => void }) {
  const t = data.target;
  const qc = useQueryClient();
  const [net, setNet] = React.useState(t ? String(t.target_net).replace(".", ",") : "");
  const [date, setDate] = React.useState(t?.target_date ?? "");
  const [note, setNote] = React.useState(t?.note ?? "");
  const [err, setErr] = React.useState<string | null>(null);
  const mut = useMutation({
    mutationFn: (body: { target_net: number | null; target_date?: string | null; note?: string | null }) =>
      setExamTarget(studentId, { section: data.section ?? "", ...body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: examProgressKeys.all(studentId) });
      onDone();
    },
    onError: (e) => setErr(e instanceof ApiError ? e.message : "Kaydedilemedi"),
  });
  return (
    <View className="gap-3 pb-2">
      <Text className="text-xs text-slate-500">
        Son 3 denemenin ortalaması {fmtNet(data.stats?.avg_last3)} · en iyi {fmtNet(data.stats?.best_net)}. Öğrenci de görür.
      </Text>
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Toplam hedef net</Text>
        <TextInput
          value={net}
          onChangeText={setNet}
          keyboardType="decimal-pad"
          placeholder="örn. 80"
          placeholderTextColor="#94a3b8"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Hedef tarih (isteğe bağlı)</Text>
        <TextInput
          value={date}
          onChangeText={(v) => setDate(v.replace(/[^0-9-]/g, "").slice(0, 10))}
          placeholder="YYYY-AA-GG"
          placeholderTextColor="#94a3b8"
          keyboardType="numbers-and-punctuation"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Hedef notu</Text>
        <TextInput
          value={note}
          onChangeText={setNote}
          maxLength={300}
          multiline
          className="min-h-[64px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
        />
      </View>
      {err ? <Text className="text-sm text-rose-600">{err}</Text> : null}
      <Pressable
        onPress={() => {
          const n = parseNum(net);
          if (n == null) {
            setErr("Hedef net girin.");
            return;
          }
          mut.mutate({ target_net: n, target_date: date || null, note: note || null });
        }}
        disabled={mut.isPending}
        className="items-center rounded-xl bg-brand-700 py-3.5 active:bg-brand-800"
      >
        <Text className="text-base font-semibold text-white">Kaydet</Text>
      </Pressable>
      {t ? (
        <Pressable onPress={() => mut.mutate({ target_net: null })} className="items-center py-2">
          <Text className="font-semibold text-rose-600">Hedefi kaldır</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
