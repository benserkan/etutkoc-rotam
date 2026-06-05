import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { StudentRequestItem, StudentRequestListResponse } from "@/lib/student";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  change: "Sayı değişikliği",
  replace: "Kaynak değişikliği",
  remove: "Görev kaldırma",
  question: "Soru",
  add: "Görev ekleme",
};

const STATUS: Record<string, { label: string; bg: string; text: string }> = {
  pending: { label: "Bekliyor", bg: "bg-amber-50", text: "text-amber-700" },
  approved: { label: "Onaylandı", bg: "bg-emerald-50", text: "text-emerald-700" },
  rejected: { label: "Reddedildi", bg: "bg-rose-50", text: "text-rose-700" },
  withdrawn: { label: "Geri çekildi", bg: "bg-slate-100", text: "text-slate-500" },
  resolved: { label: "Yanıtlandı", bg: "bg-cyan-50", text: "text-cyan-700" },
};

const TR_MONTHS_SHORT = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];
function shortDate(iso: string | null): string {
  if (!iso) return "";
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

function RequestCard({
  req,
  busy,
  onWithdraw,
}: {
  req: StudentRequestItem;
  busy: boolean;
  onWithdraw: (id: number) => void;
}) {
  const st = STATUS[req.status] ?? STATUS.pending;
  const proposed: string[] = [];
  if (req.proposed_count != null) proposed.push(`${req.proposed_count} test`);
  if (req.proposed_book_name) proposed.push(req.proposed_book_name);
  if (req.proposed_section_label) proposed.push(req.proposed_section_label);
  if (req.proposed_date) proposed.push(shortDate(req.proposed_date));

  function confirmWithdraw() {
    Alert.alert("Talebi geri çek", "Bu talebi geri çekmek istiyor musun?", [
      { text: "Vazgeç", style: "cancel" },
      { text: "Geri çek", style: "destructive", onPress: () => onWithdraw(req.id) },
    ]);
  }

  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center justify-between gap-2">
        <Text className="text-sm font-semibold text-slate-800">{TYPE_LABEL[req.type] ?? req.type}</Text>
        <View className={cn("rounded-full px-2 py-0.5", st.bg)}>
          <Text className={cn("text-[11px] font-semibold", st.text)}>{st.label}</Text>
        </View>
      </View>

      {req.task_title ? (
        <Text className="mt-1 text-[13px] text-slate-600" numberOfLines={2}>
          {req.task_title}
          {req.task_date ? <Text className="text-slate-400">  ·  {shortDate(req.task_date)}</Text> : null}
        </Text>
      ) : null}

      {proposed.length > 0 ? (
        <Text className="mt-1 text-[13px] text-brand-700">Önerin: {proposed.join(" · ")}</Text>
      ) : null}

      {req.message ? (
        <Text className="mt-2 text-sm text-slate-700">{req.message}</Text>
      ) : null}

      {req.teacher_response ? (
        <View className="mt-2.5 rounded-xl bg-cyan-50 p-3">
          <Text className="text-[11px] font-semibold uppercase tracking-wide text-cyan-700">Koçun yanıtı</Text>
          <Text className="mt-0.5 text-sm text-cyan-900">{req.teacher_response}</Text>
        </View>
      ) : null}

      <View className="mt-2 flex-row items-center justify-between">
        <Text className="text-[11px] text-slate-400">{shortDate(req.created_at.slice(0, 10))}</Text>
        {req.status === "pending" ? (
          <Pressable onPress={confirmWithdraw} disabled={busy} hitSlop={6}>
            <Text className="text-sm font-medium text-rose-600">Geri çek</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

export function RequestsView({
  data,
  busy = false,
  onWithdraw,
  refreshing = false,
  onRefresh,
}: {
  data: StudentRequestListResponse;
  busy?: boolean;
  onWithdraw: (id: number) => void;
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
      {data.items.length === 0 ? (
        <View className="mt-10 items-center gap-3 px-6">
          <Ionicons name="chatbubbles-outline" size={44} color="#94a3b8" />
          <Text className="text-center text-base font-semibold text-slate-700">Henüz talebin yok</Text>
          <Text className="text-center text-sm text-slate-500">
            Bir göreve dokunup &quot;Koça ilet&quot; ile soru sorabilir, sayı değişikliği isteyebilirsin.
          </Text>
        </View>
      ) : (
        data.items.map((r) => <RequestCard key={r.id} req={r} busy={busy} onWithdraw={onWithdraw} />)
      )}
    </ScrollView>
  );
}
