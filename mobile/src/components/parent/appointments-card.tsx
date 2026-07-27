import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { Linking, Pressable, Text, View } from "react-native";

import {
  apptKeys,
  fmtApptDate,
  getParentChildAppointments,
} from "@/lib/appointments";

/**
 * Veli — "Sıradaki koçluk görüşmesi" kartı (çocuk detayı).
 * Planlanmış görüşme yoksa hiç render olmaz.
 */
export function ParentAppointmentsCard({ studentId }: { studentId: number }) {
  const q = useQuery({
    queryKey: apptKeys.parentChild(studentId),
    queryFn: () => getParentChildAppointments(studentId),
  });
  const upcoming = q.data?.upcoming ?? [];
  if (upcoming.length === 0) return null;
  const next = upcoming[0];

  return (
    <View className="rounded-2xl border border-cyan-200 bg-cyan-50 p-4">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name="videocam-outline" size={15} color="#155e75" />
        <Text className="text-[11px] font-bold uppercase tracking-wide text-cyan-800">
          Sıradaki koçluk görüşmesi
        </Text>
      </View>
      <Text className="mt-1 text-sm font-bold text-slate-900">
        {fmtApptDate(next)} · {next.start_time}
        <Text className="font-normal text-slate-600">
          {"  "}({next.coach_name ?? "Koç"} ile, {next.duration_min} dk)
        </Text>
      </Text>
      {upcoming.length > 1 ? (
        <Text className="mt-0.5 text-xs text-slate-500">
          +{upcoming.length - 1} planlı görüşme daha
        </Text>
      ) : null}
      {next.meeting_link ? (
        <Pressable
          onPress={() => void Linking.openURL(next.meeting_link!)}
          className="mt-2.5 flex-row items-center justify-center gap-1.5 self-start rounded-xl bg-cyan-700 px-4 py-2 active:bg-cyan-800"
        >
          <Ionicons name="videocam" size={15} color="white" />
          <Text className="text-xs font-bold text-white">Görüşmeye katıl</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
