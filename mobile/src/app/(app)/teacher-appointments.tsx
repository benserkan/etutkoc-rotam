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
  approveAppointment,
  apptKeys,
  fmtApptDate,
  getTeacherAppointments,
  recordAppointmentSession,
  rejectAppointment,
  setAppointmentStatus,
  type AppointmentItem,
} from "@/lib/appointments";

/**
 * Koç "Görüşmeler" — 14 günlük randevu listesi + bekleyen istek onay/red +
 * yapıldı/gelmedi/iptal işaretleme. Planlama (yeni randevu/haftalık seri/
 * uygunluk saatleri/Google bağlantısı) web'de (PARITY).
 */
export default function TeacherAppointmentsRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: apptKeys.teacher, queryFn: getTeacherAppointments });

  const invalidate = () => void qc.invalidateQueries({ queryKey: apptKeys.teacher });
  const approve = useMutation({
    mutationFn: (id: number) => approveAppointment(id),
    onSuccess: invalidate,
    onError: () => Alert.alert("Olmadı", "İstek onaylanamadı — saat dolu olabilir."),
  });
  const reject = useMutation({
    mutationFn: (id: number) => rejectAppointment(id),
    onSuccess: invalidate,
    onError: () => Alert.alert("Olmadı", "İstek reddedilemedi."),
  });
  const status = useMutation({
    mutationFn: ({ id, s }: { id: number; s: "cancelled" | "done" | "no_show" }) =>
      setAppointmentStatus(id, s),
    onSuccess: invalidate,
    onError: () => Alert.alert("Olmadı", "Durum güncellenemedi."),
  });
  const noShow = useMutation({
    mutationFn: (id: number) => recordAppointmentSession(id, { outcome: "no_show" }),
    onSuccess: invalidate,
    onError: () => Alert.alert("Olmadı", "Kaydedilemedi."),
  });
  const [recording, setRecording] = React.useState<AppointmentItem | null>(null);

  const data = q.data;
  const byDate = React.useMemo(() => {
    const map = new Map<string, AppointmentItem[]>();
    for (const a of data?.items ?? []) {
      const arr = map.get(a.date) ?? [];
      arr.push(a);
      map.set(a.date, arr);
    }
    return [...map.entries()].sort((x, y) => x[0].localeCompare(y[0]));
  }, [data?.items]);

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
        <Text className="text-base font-semibold text-slate-800">Görüşmeler</Text>
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
          {/* Bekleyen istekler */}
          {data.pending.length > 0 ? (
            <View className="rounded-2xl border border-amber-200 bg-amber-50 p-4 gap-2">
              <Text className="text-sm font-bold text-amber-900">
                Onay bekleyen istekler ({data.pending.length})
              </Text>
              {data.pending.map((p) => (
                <View key={p.id} className="rounded-xl border border-amber-200 bg-white p-3">
                  <Text className="text-sm text-slate-900">
                    <Text className="font-bold">{p.student_name}</Text>
                    {" "}· {fmtApptDate(p)} {p.start_time} · {p.duration_min} dk
                  </Text>
                  {p.request_note ? (
                    <Text className="mt-0.5 text-xs text-slate-500">&quot;{p.request_note}&quot;</Text>
                  ) : null}
                  <View className="mt-2 flex-row gap-2">
                    <Pressable
                      onPress={() => approve.mutate(p.id)}
                      disabled={approve.isPending}
                      className="rounded-lg bg-emerald-600 px-3.5 py-1.5 active:bg-emerald-700"
                    >
                      <Text className="text-xs font-bold text-white">Onayla</Text>
                    </Pressable>
                    <Pressable
                      onPress={() =>
                        Alert.alert("Reddet", `${p.student_name} isteğine uygun değil misin?`, [
                          { text: "Vazgeç", style: "cancel" },
                          { text: "Reddet", style: "destructive", onPress: () => reject.mutate(p.id) },
                        ])
                      }
                      disabled={reject.isPending}
                      className="rounded-lg border border-slate-300 px-3.5 py-1.5 active:bg-slate-100"
                    >
                      <Text className="text-xs font-semibold text-slate-700">Reddet</Text>
                    </Pressable>
                  </View>
                </View>
              ))}
            </View>
          ) : null}

          {byDate.length === 0 && data.pending.length === 0 ? (
            <View className="rounded-2xl border border-dashed border-slate-300 bg-white p-6">
              <Text className="text-center text-sm text-slate-500">
                Önümüzdeki iki haftada planlı görüşme yok. Yeni görüşme planlamak
                için web panelindeki Görüşmeler sayfasını kullan.
              </Text>
            </View>
          ) : null}

          {byDate.map(([date, items]) => (
            <View key={date} className="rounded-2xl border border-slate-200 bg-white">
              <Text className="border-b border-slate-100 px-4 py-2 text-xs font-bold uppercase tracking-wide text-slate-500">
                {fmtApptDate(items[0])}
              </Text>
              {items.map((a) => (
                <View key={a.id} className="border-b border-slate-50 px-4 py-2.5">
                  <View className="flex-row items-center justify-between">
                    <Text className="text-sm text-slate-900">
                      <Text className="font-bold">{a.start_time}</Text> · {a.student_name}
                      {a.series_id ? "  ↻" : ""}
                    </Text>
                    <Text
                      className={
                        a.status === "scheduled"
                          ? "text-xs font-semibold text-cyan-700"
                          : a.status === "done"
                            ? "text-xs font-semibold text-emerald-700"
                            : a.status === "no_show" || a.status === "cancelled"
                              ? "text-xs font-semibold text-rose-600"
                              : "text-xs font-semibold text-slate-500"
                      }
                    >
                      {a.status_label}
                    </Text>
                  </View>
                  {a.status === "scheduled" ? (
                    <View className="mt-1.5 flex-row flex-wrap gap-2">
                      {a.meeting_link ? (
                        <Pressable
                          onPress={() => void Linking.openURL(a.meeting_link!)}
                          className="flex-row items-center gap-1 rounded-lg bg-cyan-700 px-3 py-1.5 active:bg-cyan-800"
                        >
                          <Ionicons name="videocam" size={13} color="white" />
                          <Text className="text-xs font-bold text-white">Katıl</Text>
                        </Pressable>
                      ) : null}
                      {a.is_past ? (
                        <>
                          <Pressable
                            onPress={() => setRecording(a)}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 active:bg-emerald-700"
                          >
                            <Text className="text-xs font-bold text-white">Seansı kaydet</Text>
                          </Pressable>
                          <Pressable
                            onPress={() =>
                              Alert.alert(
                                "Gelmedi",
                                `${a.student_name} görüşmeye gelmedi olarak kaydedilsin mi? (Tahsilata sayılmaz)`,
                                [
                                  { text: "Vazgeç", style: "cancel" },
                                  { text: "Kaydet", style: "destructive", onPress: () => noShow.mutate(a.id) },
                                ],
                              )
                            }
                            disabled={noShow.isPending}
                            className="rounded-lg border border-rose-300 px-3 py-1.5 active:bg-rose-50"
                          >
                            <Text className="text-xs font-semibold text-rose-700">Gelmedi</Text>
                          </Pressable>
                        </>
                      ) : (
                        <Pressable
                          onPress={() =>
                            Alert.alert("İptal", "Görüşme iptal edilsin mi? Öğrenci ve veliye haber gider.", [
                              { text: "Vazgeç", style: "cancel" },
                              {
                                text: "İptal et",
                                style: "destructive",
                                onPress: () => status.mutate({ id: a.id, s: "cancelled" }),
                              },
                            ])
                          }
                          disabled={status.isPending}
                          className="rounded-lg border border-slate-300 px-3 py-1.5 active:bg-slate-100"
                        >
                          <Text className="text-xs font-semibold text-slate-600">İptal</Text>
                        </Pressable>
                      )}
                    </View>
                  ) : null}
                  {a.status === "done" || a.status === "no_show" ? (
                    a.session_id ? (
                      <View className="mt-1 flex-row items-center gap-1">
                        <Ionicons name="checkmark-circle" size={13} color="#047857" />
                        <Text className="text-[11px] font-semibold text-emerald-700">
                          Seans kaydedildi
                        </Text>
                      </View>
                    ) : (
                      <Pressable
                        onPress={() => setRecording(a)}
                        className="mt-1.5 self-start rounded-lg border border-emerald-300 px-3 py-1.5 active:bg-emerald-50"
                      >
                        <Text className="text-xs font-semibold text-emerald-700">
                          Seansı kaydet
                        </Text>
                      </Pressable>
                    )
                  ) : null}
                </View>
              ))}
            </View>
          ))}

          <Text className="px-2 text-center text-[11px] text-slate-400">
            Yeni görüşme planlama, haftalık tekrar, uygunluk saatleri ve Google
            Meet bağlantısı web panelinde.
          </Text>
        </ScrollView>
      )}

      {recording ? (
        <RecordSheet
          appt={recording}
          onClose={() => setRecording(null)}
          onSaved={() => {
            setRecording(null);
            invalidate();
          }}
        />
      ) : null}
    </SafeAreaView>
  );
}

/** F4 — biten görüşmeyi seans kaydına çevir (gündem zorunlu; tahsilata sayılır). */
function RecordSheet({
  appt,
  onClose,
  onSaved,
}: {
  appt: AppointmentItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [agenda, setAgenda] = React.useState("");
  const [note, setNote] = React.useState("");
  const save = useMutation({
    mutationFn: () =>
      recordAppointmentSession(appt.id, {
        outcome: "done",
        agenda: agenda.trim(),
        coach_note: note.trim() || undefined,
      }),
    onSuccess: () => {
      onSaved();
      Alert.alert("Kaydedildi", "Seans kaydedildi — tahsilata işlendi.");
    },
    onError: () => Alert.alert("Olmadı", "Seans kaydedilemedi — tekrar dene."),
  });

  return (
    <FormSheet visible title={`Seansı kaydet — ${appt.student_name}`} onClose={onClose}>
      <View className="gap-3">
        <Text className="text-xs text-slate-500">
          {fmtApptDate(appt)} {appt.start_time} görüşmesi seans kaydına dönüşür;
          yapılan seans tahsilat panosuna otomatik işlenir.
        </Text>
        <View>
          <Text className="mb-1.5 text-xs font-bold text-slate-500">
            Gündem — ne konuşuldu? (zorunlu)
          </Text>
          <TextInput
            value={agenda}
            onChangeText={setAgenda}
            placeholder="Örn. deneme analizi + haftalık plan + motivasyon"
            multiline
            numberOfLines={3}
            className="min-h-[72px] rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
            placeholderTextColor="#94a3b8"
            textAlignVertical="top"
          />
        </View>
        <View>
          <Text className="mb-1.5 text-xs font-bold text-slate-500">
            Görüşme notu (isteğe bağlı)
          </Text>
          <TextInput
            value={note}
            onChangeText={setNote}
            multiline
            numberOfLines={2}
            className="min-h-[52px] rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
            textAlignVertical="top"
          />
        </View>
        <Pressable
          onPress={() => save.mutate()}
          disabled={!agenda.trim() || save.isPending}
          className={
            !agenda.trim() || save.isPending
              ? "items-center rounded-xl bg-slate-300 px-4 py-3"
              : "items-center rounded-xl bg-emerald-600 px-4 py-3 active:bg-emerald-700"
          }
        >
          <Text className="font-bold text-white">
            {save.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Text>
        </Pressable>
      </View>
    </FormSheet>
  );
}
