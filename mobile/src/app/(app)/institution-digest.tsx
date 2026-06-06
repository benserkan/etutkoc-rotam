import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { Alert, Pressable, Text, View } from "react-native";

import { Badge, Banner, Empty, InstitutionScreen } from "@/components/institution/ui";
import { ApiError } from "@/lib/api";
import {
  getInstitutionDigestList,
  institutionKeys,
  sendInstitutionDigestNow,
  type AdminDigestListResponse,
  type AdminDigestSummary,
} from "@/lib/institution";

const STATUS: Record<string, { label: string; tone: "emerald" | "amber" | "rose" | "slate" | "sky" }> = {
  sent: { label: "Gönderildi", tone: "emerald" },
  log_only: { label: "Yalnız kayıt", tone: "sky" },
  failed: { label: "Başarısız", tone: "rose" },
  skipped_no_admin: { label: "Alıcı yok", tone: "slate" },
  pending: { label: "Bekliyor", tone: "amber" },
};

function range(a: string, b: string): string {
  const f = (iso: string) => { const d = new Date(iso); return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`; };
  return `${f(a)} – ${f(b)}`;
}

function Row({ r }: { r: AdminDigestSummary }) {
  const st = STATUS[r.send_status] ?? STATUS.pending;
  return (
    <Pressable
      onPress={() => router.push({ pathname: "/institution-digest-detail", params: { id: String(r.id) } })}
      className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-3 active:bg-slate-50"
    >
      <View className="flex-1">
        <Text className="text-sm font-semibold text-slate-900">{range(r.week_start_date, r.week_end_date)}</Text>
        <Text className="text-[11px] text-slate-400">{r.recipient_count} alıcı{r.sent_at ? ` · ${new Date(r.sent_at).toLocaleDateString("tr-TR")}` : ""}</Text>
      </View>
      <Badge label={st.label} tone={st.tone} />
    </Pressable>
  );
}

export default function InstitutionDigestScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: institutionKeys.digestList, queryFn: getInstitutionDigestList });
  const mut = useMutation({
    mutationFn: sendInstitutionDigestNow,
    onSuccess: () => { qc.invalidateQueries({ queryKey: institutionKeys.digestList }); Alert.alert("Gönderildi", "Haftalık özet şimdi gönderildi."); },
    onError: (e) => Alert.alert("Gönderilemedi", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  function confirmSend() {
    Alert.alert("Şimdi gönder", "Bu haftanın özetini yöneticilere şimdi göndermek istiyor musun?", [
      { text: "Vazgeç", style: "cancel" },
      { text: "Gönder", onPress: () => mut.mutate() },
    ]);
  }

  return (
    <InstitutionScreen<AdminDigestListResponse>
      title="Haftalık Özet"
      query={q}
      headerRight={
        <Pressable onPress={confirmSend} disabled={mut.isPending} className="rounded-lg bg-brand-700 px-3 py-1.5 active:bg-brand-800">
          <Text className="text-xs font-semibold text-white">{mut.isPending ? "…" : "Şimdi gönder"}</Text>
        </Pressable>
      }
    >
      {(d) => (
        <>
          <Banner kind="info">Her Pazartesi 12:00&apos;de otomatik gönderilir. Kurum performans özeti yöneticilerin e-postasına düşer.</Banner>
          {d.items.length === 0 ? <Empty text="Henüz haftalık özet yok." /> : <View className="gap-2">{d.items.map((r) => <Row key={r.id} r={r} />)}</View>}
        </>
      )}
    </InstitutionScreen>
  );
}
