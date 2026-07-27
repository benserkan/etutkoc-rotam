import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { apptKeys, fmtApptDate, getStudentAppointments } from "@/lib/appointments";

/**
 * Bugün ekranı — "Sıradaki görüşme" bandı. Yaklaşan görüşme veya bekleyen
 * istek yoksa hiç render olmaz (Bugün ekranında gürültü yapmaz).
 * Dokun → Görüşmelerim ekranı.
 */
export function NextAppointmentBanner() {
  const q = useQuery({ queryKey: apptKeys.student, queryFn: getStudentAppointments });
  const data = q.data;
  if (!data) return null;
  const next = data.upcoming[0] ?? null;
  const pending = data.pending[0] ?? null;
  if (!next && !pending) return null;

  return (
    <Pressable
      onPress={() => router.push("/student-appointments")}
      className="flex-row items-center justify-between rounded-2xl border border-cyan-200 bg-cyan-50 px-4 py-3 active:bg-cyan-100"
    >
      <View className="flex-1 flex-row items-center gap-2.5">
        <Ionicons name="videocam-outline" size={20} color="#0e7490" />
        <View className="flex-1">
          {next ? (
            <>
              <Text className="text-[13px] font-bold text-cyan-900">
                Sıradaki görüşmen: {fmtApptDate(next)} · {next.start_time}
              </Text>
              <Text className="text-[11px] text-cyan-800">
                {next.coach_name ?? "Koçun"} ile · {next.duration_min} dk
                {next.meeting_link ? " · katılma linki hazır" : ""}
              </Text>
            </>
          ) : (
            <>
              <Text className="text-[13px] font-bold text-cyan-900">
                Görüşme isteğin onay bekliyor
              </Text>
              <Text className="text-[11px] text-cyan-800">
                {pending ? `${fmtApptDate(pending)} · ${pending.start_time}` : ""}
              </Text>
            </>
          )}
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#0e7490" />
    </Pressable>
  );
}
