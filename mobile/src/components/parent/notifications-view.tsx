import { Ionicons } from "@expo/vector-icons";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import type { ParentNotificationItem, ParentNotificationsResponse } from "@/lib/parent";
import { cn } from "@/lib/utils";

const KIND_LABEL: Record<string, string> = {
  daily_summary: "Günlük özet",
  empty_day: "Boş gün uyarısı",
  weekly_report: "Haftalık rapor",
  new_program: "Yeni program",
  drop_alert: "Düşüş uyarısı",
  teacher_note: "Koç notu",
  invitation: "Davet",
  otp: "Doğrulama kodu",
  exam_approaching: "Sınav yaklaşıyor",
};
const CHANNEL_LABEL: Record<string, string> = { email: "E-posta", whatsapp: "WhatsApp", sms: "SMS" };
const STATUS: Record<string, { label: string; bg: string; text: string }> = {
  sent: { label: "Gönderildi", bg: "bg-emerald-50", text: "text-emerald-700" },
  queued: { label: "Sırada", bg: "bg-amber-50", text: "text-amber-700" },
  failed: { label: "Başarısız", bg: "bg-rose-50", text: "text-rose-700" },
  suppressed: { label: "Gönderilmedi", bg: "bg-slate-100", text: "text-slate-500" },
};

const TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function fmt(iso: string | null): string {
  if (!iso) return "";
  const [datePart, timePart] = iso.split("T");
  const [, m, d] = datePart.split("-").map(Number);
  const hm = timePart ? timePart.slice(0, 5) : "";
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS[m - 1]}${hm ? ` ${hm}` : ""}`;
}

function Card({ n }: { n: ParentNotificationItem }) {
  const st = STATUS[n.status] ?? STATUS.queued;
  const title = n.subject || KIND_LABEL[n.kind] || n.kind;
  const when = fmt(n.sent_at ?? n.queued_at);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-start justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={2}>
          {title}
        </Text>
        <View className={cn("rounded-full px-2 py-0.5", st.bg)}>
          <Text className={cn("text-[11px] font-semibold", st.text)}>{st.label}</Text>
        </View>
      </View>
      <View className="mt-1.5 flex-row items-center gap-2">
        <Text className="text-xs text-slate-500">{CHANNEL_LABEL[n.channel] ?? n.channel}</Text>
        {n.student_name ? <Text className="text-xs text-slate-400">· {n.student_name}</Text> : null}
        {when ? <Text className="ml-auto text-xs text-slate-400">{when}</Text> : null}
      </View>
    </View>
  );
}

export function NotificationsView({
  data,
  refreshing = false,
  onRefresh,
}: {
  data: ParentNotificationsResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-3"
      refreshControl={
        onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
      }
    >
      <Text className="px-1 text-xl font-bold text-slate-900">Bildirimler</Text>
      {data.items.length === 0 ? (
        <View className="mt-10 items-center gap-3 px-6">
          <Ionicons name="notifications-outline" size={44} color="#94a3b8" />
          <Text className="text-center text-base font-semibold text-slate-700">Bildirim yok</Text>
          <Text className="text-center text-sm text-slate-500">
            Haftalık rapor, uyarı ve duyurular burada görünür.
          </Text>
        </View>
      ) : (
        data.items.map((n) => <Card key={n.id} n={n} />)
      )}
    </ScrollView>
  );
}
