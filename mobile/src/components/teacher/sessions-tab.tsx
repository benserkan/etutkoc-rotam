import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  createTeacherSession,
  getTeacherStudentSessions,
  teacherDetailKeys,
  type SessionCreateBody,
  type StudentSessionListResponse,
} from "@/lib/teacher";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}
function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const STATUS_OPTS = [
  { v: "done", label: "Yapıldı" },
  { v: "postponed", label: "Ertelendi" },
  { v: "cancelled", label: "İptal" },
  { v: "no_show", label: "Gelmedi" },
];
const CHANNEL_OPTS = [
  { v: "in_person", label: "Yüz yüze" },
  { v: "online", label: "Online" },
  { v: "phone", label: "Telefon" },
];
const STATUS_TONE: Record<string, { bg: string; text: string }> = {
  done: { bg: "bg-emerald-50", text: "text-emerald-700" },
  postponed: { bg: "bg-amber-50", text: "text-amber-700" },
  cancelled: { bg: "bg-slate-100", text: "text-slate-600" },
  no_show: { bg: "bg-rose-50", text: "text-rose-700" },
};
const MOODS = ["😟", "🙁", "😐", "🙂", "😄"];

function Chips({
  opts,
  value,
  onSelect,
}: {
  opts: { v: string; label: string }[];
  value: string | null;
  onSelect: (v: string) => void;
}) {
  return (
    <View className="flex-row flex-wrap gap-2">
      {opts.map((o) => {
        const active = o.v === value;
        return (
          <Pressable
            key={o.v}
            onPress={() => onSelect(o.v)}
            className={cn(
              "rounded-full border px-3 py-1.5",
              active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white",
            )}
          >
            <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function SessionForm({
  busy,
  error,
  onSubmit,
}: {
  busy: boolean;
  error: string | null;
  onSubmit: (body: SessionCreateBody) => void;
}) {
  const [date, setDate] = React.useState(todayISO());
  const [status, setStatus] = React.useState("done");
  const [channel, setChannel] = React.useState<string | null>("in_person");
  const [duration, setDuration] = React.useState("");
  const [agenda, setAgenda] = React.useState("");
  const [coachNote, setCoachNote] = React.useState("");
  const [nextChange, setNextChange] = React.useState("");
  const [mood, setMood] = React.useState<number | null>(null);

  const canSave = agenda.trim().length > 0 && !busy;

  return (
    <View className="gap-4 pb-2">
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Tarih</Text>
        <TextInput
          value={date}
          onChangeText={(v) => setDate(v.replace(/[^0-9-]/g, "").slice(0, 10))}
          placeholder="YYYY-AA-GG"
          placeholderTextColor="#94a3b8"
          keyboardType="numbers-and-punctuation"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Durum</Text>
        <Chips opts={STATUS_OPTS} value={status} onSelect={setStatus} />
      </View>

      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Görüşme şekli</Text>
        <Chips opts={CHANNEL_OPTS} value={channel} onSelect={setChannel} />
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Süre (dk, isteğe bağlı)</Text>
        <TextInput
          value={duration}
          onChangeText={(v) => setDuration(v.replace(/[^0-9]/g, "").slice(0, 3))}
          keyboardType="number-pad"
          placeholder="örn. 45"
          placeholderTextColor="#94a3b8"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Gündem / konuşulanlar *</Text>
        <TextInput
          value={agenda}
          onChangeText={setAgenda}
          placeholder="Bu seansta neyi ele aldınız?"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-[72px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Koç notu (isteğe bağlı)</Text>
        <TextInput
          value={coachNote}
          onChangeText={setCoachNote}
          placeholder="Yalnız sana özel gözlemler…"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-[60px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Bir sonraki değişiklik (isteğe bağlı)</Text>
        <TextInput
          value={nextChange}
          onChangeText={setNextChange}
          placeholder="Sonraki seansa kadar yapılacak…"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-[48px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Ruh hali (isteğe bağlı)</Text>
        <View className="flex-row gap-2">
          {MOODS.map((emo, i) => {
            const active = mood === i + 1;
            return (
              <Pressable
                key={emo}
                onPress={() => setMood(active ? null : i + 1)}
                className={cn(
                  "size-12 items-center justify-center rounded-xl border",
                  active ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white",
                )}
              >
                <Text className="text-2xl">{emo}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

      <Pressable
        onPress={() =>
          onSubmit({
            session_date: date,
            status,
            channel,
            duration_min: duration ? Number(duration) : null,
            agenda: agenda.trim(),
            coach_note: coachNote.trim() || null,
            next_change: nextChange.trim() || null,
            mood,
            capture_source: "manual",
          })
        }
        disabled={!canSave}
        className={cn("items-center rounded-xl py-3.5", canSave ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Seansı kaydet"}</Text>
      </Pressable>
    </View>
  );
}

export function SessionsTabView({
  data,
  addBusy,
  addError,
  onAdd,
}: {
  data: StudentSessionListResponse;
  addBusy: boolean;
  addError: string | null;
  onAdd: (body: SessionCreateBody) => void;
}) {
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const s = data.summary;

  return (
    <View className="gap-4 px-4 py-4">
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">
          Seanslar · {s.total} kayıt
        </Text>
        <Text className="mt-2 text-sm text-brand-100">
          {s.last_session_date ? `Son seans: ${shortDate(s.last_session_date)}` : "Henüz seans yok"}
          {s.total > 0 ? ` · ${s.done_count} yapıldı` : ""}
        </Text>
      </View>

      <Pressable
        onPress={() => setSheetOpen(true)}
        className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3.5 active:bg-brand-100"
      >
        <Ionicons name="add-circle-outline" size={20} color="#0e7490" />
        <Text className="text-base font-semibold text-brand-700">Seans kaydet</Text>
      </Pressable>

      {data.rows.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="chatbubbles-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">
            Henüz seans kaydı yok. Görüşmelerini kaydet, geçmişi burada birikir.
          </Text>
        </View>
      ) : (
        <View className="gap-2.5">
          {data.rows.map((r) => {
            const t = STATUS_TONE[r.status] ?? { bg: "bg-slate-100", text: "text-slate-600" };
            return (
              <View key={r.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                <View className="flex-row items-center justify-between gap-2">
                  <Text className="text-sm font-semibold text-slate-800">{shortDate(r.session_date)}</Text>
                  <View className="flex-row items-center gap-1.5">
                    {r.mood != null ? <Text className="text-base">{MOODS[r.mood - 1]}</Text> : null}
                    <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
                      <Text className={cn("text-[11px] font-semibold", t.text)}>{r.status_label}</Text>
                    </View>
                  </View>
                </View>
                <Text className="mt-2 text-[15px] text-slate-900">{r.agenda}</Text>
                {r.coach_note ? (
                  <Text className="mt-1.5 text-xs italic text-slate-500">{r.coach_note}</Text>
                ) : null}
                {r.next_change ? (
                  <View className="mt-2 rounded-lg bg-brand-50 px-3 py-2">
                    <Text className="text-[11px] font-semibold text-brand-700">Sonraki adım</Text>
                    <Text className="text-xs text-brand-800">{r.next_change}</Text>
                  </View>
                ) : null}
                <View className="mt-2 flex-row gap-2">
                  {r.channel_label ? (
                    <Text className="text-[11px] text-slate-400">{r.channel_label}</Text>
                  ) : null}
                  {r.duration_min ? <Text className="text-[11px] text-slate-400">· {r.duration_min} dk</Text> : null}
                </View>
              </View>
            );
          })}
        </View>
      )}

      <FormSheet visible={sheetOpen} title="Seans kaydet" onClose={() => setSheetOpen(false)}>
        <SessionForm
          busy={addBusy}
          error={addError}
          onSubmit={(body) => {
            onAdd(body);
            setSheetOpen(false);
          }}
        />
      </FormSheet>
    </View>
  );
}

export function SessionsTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [addError, setAddError] = React.useState<string | null>(null);

  const q = useQuery({
    queryKey: teacherDetailKeys.sessions(studentId),
    queryFn: () => getTeacherStudentSessions(studentId),
    enabled: studentId > 0,
  });

  const addMut = useMutation({
    mutationFn: (body: SessionCreateBody) => createTeacherSession(studentId, body),
    onMutate: () => setAddError(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: teacherDetailKeys.sessions(studentId) });
    },
    onError: (e) => setAddError(e instanceof ApiError ? e.message : "Kaydedilemedi"),
  });

  if (q.isLoading) {
    return (
      <View className="items-center justify-center py-16">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (q.isError || !q.data) {
    return (
      <View className="items-center gap-3 py-16 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
        <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <SessionsTabView
      data={q.data}
      addBusy={addMut.isPending}
      addError={addError}
      onAdd={(body) => addMut.mutate(body)}
    />
  );
}
