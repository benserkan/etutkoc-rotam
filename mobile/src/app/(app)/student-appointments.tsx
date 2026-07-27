import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import * as React from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  apptKeys,
  fmtApptDate,
  getStudentAppointmentSlots,
  getStudentAppointments,
  requestAppointment,
  withdrawAppointment,
  type AppointmentItem,
} from "@/lib/appointments";

/**
 * Öğrenci "Görüşmelerim" — sıradaki online koçluk görüşmesi (Katıl) +
 * koçun boş saatinden görüşme isteme + bekleyen isteği geri çekme.
 */
export default function StudentAppointmentsRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: apptKeys.student, queryFn: getStudentAppointments });
  const [requestOpen, setRequestOpen] = React.useState(false);

  const withdraw = useMutation({
    mutationFn: (id: number) => withdrawAppointment(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: apptKeys.student }),
    onError: () => Alert.alert("Olmadı", "İstek geri çekilemedi — tekrar dene."),
  });

  const data = q.data;
  const next = data?.upcoming[0] ?? null;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Görüşmelerim</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          contentContainerClassName="px-4 py-3 gap-4 pb-10"
          refreshControl={
            <RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} />
          }
        >
          {/* Sıradaki görüşme */}
          {next ? (
            <View className="rounded-2xl border border-cyan-200 bg-cyan-50 p-5">
              <Text className="text-[11px] font-bold uppercase tracking-wide text-cyan-800">
                Sıradaki görüşmen
              </Text>
              <Text className="mt-1 text-lg font-bold text-slate-900">
                {fmtApptDate(next)} · {next.start_time}
              </Text>
              <Text className="mt-0.5 text-sm text-slate-600">
                {next.coach_name ?? "Koçun"} ile · {next.duration_min} dakika
              </Text>
              {next.meeting_link ? (
                <Pressable
                  onPress={() => void Linking.openURL(next.meeting_link!)}
                  className="mt-3 flex-row items-center justify-center gap-2 rounded-xl bg-cyan-700 px-4 py-3 active:bg-cyan-800"
                >
                  <Ionicons name="videocam" size={18} color="white" />
                  <Text className="font-bold text-white">Görüşmeye katıl</Text>
                </Pressable>
              ) : (
                <Text className="mt-2 text-xs text-slate-500">
                  Görüşme bağlantısını koçun paylaşacak — saat gelince buradan katılabileceksin.
                </Text>
              )}
            </View>
          ) : (
            <View className="rounded-2xl border border-dashed border-slate-300 bg-white p-6">
              <Text className="text-center text-sm text-slate-500">
                Planlanmış bir görüşmen yok.
                {data.can_request && !data.has_pending
                  ? " İstersen aşağıdan koçundan saat isteyebilirsin."
                  : ""}
              </Text>
            </View>
          )}

          {/* Bekleyen istek */}
          {data.pending.map((p) => (
            <View key={p.id} className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <Text className="text-sm text-amber-900">
                <Text className="font-bold">{fmtApptDate(p)} {p.start_time}</Text> için isteğin
                koçunun onayını bekliyor.
              </Text>
              <Pressable
                onPress={() =>
                  Alert.alert("İsteği geri çek", "Bu görüşme isteği silinsin mi?", [
                    { text: "Vazgeç", style: "cancel" },
                    { text: "Geri çek", style: "destructive", onPress: () => withdraw.mutate(p.id) },
                  ])
                }
                disabled={withdraw.isPending}
                className="mt-2 self-start rounded-lg border border-amber-300 px-3 py-1.5 active:bg-amber-100"
              >
                <Text className="text-xs font-semibold text-amber-900">Geri çek</Text>
              </Pressable>
            </View>
          ))}

          {/* Görüşme iste */}
          {data.can_request && !data.has_pending ? (
            <Pressable
              onPress={() => setRequestOpen(true)}
              className="flex-row items-center justify-center gap-2 rounded-2xl border border-cyan-300 bg-white px-4 py-3.5 active:bg-cyan-50"
            >
              <Ionicons name="calendar-outline" size={18} color="#0e7490" />
              <Text className="font-semibold text-cyan-800">Görüşme iste</Text>
            </Pressable>
          ) : null}

          {/* Sonraki görüşmeler */}
          {data.upcoming.length > 1 ? (
            <View className="rounded-2xl border border-slate-200 bg-white">
              <Text className="border-b border-slate-100 px-4 py-2.5 text-sm font-bold text-slate-800">
                Sonraki görüşmeler
              </Text>
              {data.upcoming.slice(1).map((a) => (
                <UpcomingRow key={a.id} appt={a} />
              ))}
            </View>
          ) : null}

          {/* Geçmiş */}
          {data.past.length > 0 ? (
            <View className="rounded-2xl border border-slate-200 bg-white">
              <Text className="border-b border-slate-100 px-4 py-2.5 text-sm font-bold text-slate-800">
                Geçmiş görüşmeler
              </Text>
              {data.past.map((a) => (
                <View key={a.id} className="flex-row items-center justify-between border-b border-slate-50 px-4 py-2.5">
                  <Text className="text-sm text-slate-500">
                    {fmtApptDate(a)} · {a.start_time}
                  </Text>
                  <Text
                    className={
                      a.status === "done"
                        ? "text-xs font-semibold text-emerald-700"
                        : a.status === "no_show"
                          ? "text-xs font-semibold text-rose-700"
                          : "text-xs font-semibold text-slate-500"
                    }
                  >
                    {a.status_label}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
        </ScrollView>
      )}

      {requestOpen ? <RequestSheet onClose={() => setRequestOpen(false)} /> : null}
    </SafeAreaView>
  );
}

function UpcomingRow({ appt }: { appt: AppointmentItem }) {
  return (
    <View className="flex-row items-center justify-between border-b border-slate-50 px-4 py-2.5">
      <Text className="text-sm text-slate-700">
        {fmtApptDate(appt)} · {appt.start_time} · {appt.duration_min} dk
      </Text>
      {appt.meeting_link ? (
        <Pressable onPress={() => void Linking.openURL(appt.meeting_link!)} hitSlop={6}>
          <Text className="text-xs font-bold text-cyan-700">Link</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

/** Slot seçici — gün çipleri → saat çipleri → not → gönder. */
function RequestSheet({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const slotsQ = useQuery({
    queryKey: apptKeys.studentSlots,
    queryFn: getStudentAppointmentSlots,
  });
  const [selDate, setSelDate] = React.useState<string | null>(null);
  const [selTime, setSelTime] = React.useState<string | null>(null);
  const [note, setNote] = React.useState("");

  const send = useMutation({
    mutationFn: () =>
      requestAppointment({
        date: selDate!,
        start_time: selTime!,
        note: note.trim() || undefined,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: apptKeys.student });
      onClose();
      Alert.alert("Gönderildi", "İsteğin koçuna iletildi — onaylayınca haber vereceğiz.");
    },
    onError: () =>
      Alert.alert("Olmadı", "Bu saat artık uygun olmayabilir — başka bir saat dene."),
  });

  const days = slotsQ.data?.days ?? [];
  const selDay = days.find((d) => d.date === selDate) ?? null;

  return (
    <FormSheet visible title="Görüşme iste" onClose={onClose}>
      {slotsQ.isLoading ? (
        <ActivityIndicator color="#0e7490" className="py-6" />
      ) : days.length === 0 ? (
        <Text className="py-4 text-center text-sm text-slate-500">
          Önümüzdeki iki haftada boş saat görünmüyor — koçunla mesajlaşarak saat
          belirleyebilirsin.
        </Text>
      ) : (
        <View className="gap-4">
          <View>
            <Text className="mb-1.5 text-xs font-bold text-slate-500">Gün</Text>
            <View className="flex-row flex-wrap gap-1.5">
              {days.map((d) => {
                const [, m, dd] = d.date.split("-");
                const sel = selDate === d.date;
                return (
                  <Pressable
                    key={d.date}
                    onPress={() => {
                      setSelDate(d.date);
                      setSelTime(null);
                    }}
                    className={
                      sel
                        ? "rounded-lg bg-cyan-700 px-3 py-2"
                        : "rounded-lg border border-slate-200 bg-white px-3 py-2 active:bg-slate-100"
                    }
                  >
                    <Text className={sel ? "text-xs font-bold text-white" : "text-xs font-medium text-slate-700"}>
                      {dd}.{m} {d.weekday_label.slice(0, 3)}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>

          {selDay ? (
            <View>
              <Text className="mb-1.5 text-xs font-bold text-slate-500">
                Saat ({selDay.slots[0]?.duration_min ?? 40} dk görüşme)
              </Text>
              <View className="flex-row flex-wrap gap-1.5">
                {selDay.slots.map((s) => {
                  const sel = selTime === s.start_time;
                  return (
                    <Pressable
                      key={s.start_time}
                      onPress={() => setSelTime(s.start_time)}
                      className={
                        sel
                          ? "rounded-lg bg-cyan-700 px-3 py-2"
                          : "rounded-lg border border-slate-200 bg-white px-3 py-2 active:bg-slate-100"
                      }
                    >
                      <Text className={sel ? "text-xs font-bold text-white" : "text-xs font-semibold text-slate-700"}>
                        {s.start_time}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ) : null}

          <View>
            <Text className="mb-1.5 text-xs font-bold text-slate-500">Not (isteğe bağlı)</Text>
            <TextInput
              value={note}
              onChangeText={setNote}
              placeholder="Örn. deneme sonucumu konuşmak istiyorum"
              maxLength={200}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
              placeholderTextColor="#94a3b8"
            />
          </View>

          <Pressable
            onPress={() => send.mutate()}
            disabled={!selDate || !selTime || send.isPending}
            className={
              !selDate || !selTime || send.isPending
                ? "items-center rounded-xl bg-slate-300 px-4 py-3"
                : "items-center rounded-xl bg-cyan-700 px-4 py-3 active:bg-cyan-800"
            }
          >
            <Text className="font-bold text-white">
              {send.isPending ? "Gönderiliyor…" : "İsteği gönder"}
            </Text>
          </Pressable>
        </View>
      )}
    </FormSheet>
  );
}
