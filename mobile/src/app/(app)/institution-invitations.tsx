import * as React from "react";
import * as Clipboard from "expo-clipboard";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, Share, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { Badge, Banner, Empty, InstitutionScreen } from "@/components/institution/ui";
import { ApiError } from "@/lib/api";
import {
  createInstitutionInvitation,
  getInstitutionInvitations,
  institutionKeys,
  revokeInstitutionInvitation,
  type InvitationItem,
  type InvitationListResponse,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { label: string; tone: "amber" | "emerald" | "slate" | "rose" }> = {
  pending: { label: "Bekliyor", tone: "amber" },
  consumed: { label: "Kullanıldı", tone: "emerald" },
  expired: { label: "Süresi doldu", tone: "slate" },
  revoked: { label: "İptal edildi", tone: "rose" },
};

function Row({ inv, onRevoke }: { inv: InvitationItem; onRevoke: () => void }) {
  const st = STATUS[inv.status] ?? STATUS.pending;
  const [copied, setCopied] = React.useState(false);
  return (
    <View className={cn("rounded-xl border border-slate-200 bg-white p-3", inv.status !== "pending" ? "opacity-70" : "")}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-sm font-semibold text-slate-900" numberOfLines={1}>{inv.full_name || inv.email || "Açık davetiye"}</Text>
        <Badge label={st.label} tone={st.tone} />
      </View>
      {inv.email ? <Text className="text-[11px] text-slate-400">{inv.email}</Text> : null}
      {inv.is_usable ? (
        <View className="mt-2 flex-row gap-2">
          <Pressable
            onPress={async () => { await Clipboard.setStringAsync(inv.signup_url); setCopied(true); }}
            className="flex-1 flex-row items-center justify-center gap-1 rounded-lg border border-slate-300 py-2 active:bg-slate-50"
          >
            <Ionicons name={copied ? "checkmark" : "copy-outline"} size={16} color="#0e7490" />
            <Text className="text-xs font-semibold text-brand-700">{copied ? "Kopyalandı" : "Linki kopyala"}</Text>
          </Pressable>
          <Pressable onPress={() => void Share.share({ message: inv.signup_url })} className="flex-row items-center justify-center gap-1 rounded-lg border border-slate-300 px-3 py-2 active:bg-slate-50">
            <Ionicons name="share-outline" size={16} color="#0e7490" />
          </Pressable>
          <Pressable onPress={onRevoke} className="flex-row items-center justify-center gap-1 rounded-lg border border-rose-200 px-3 py-2 active:bg-rose-50">
            <Text className="text-xs font-semibold text-rose-600">İptal</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

export default function InstitutionInvitationsScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: institutionKeys.invitations, queryFn: getInstitutionInvitations });
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [created, setCreated] = React.useState<InvitationItem | null>(null);

  const createMut = useMutation({
    mutationFn: () => createInstitutionInvitation({ full_name: name.trim() || undefined, email: email.trim() || undefined }),
    onSuccess: (res) => { setCreated(res.data); qc.invalidateQueries({ queryKey: institutionKeys.invitations }); },
    onError: (e) => Alert.alert("Oluşturulamadı", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  const revokeMut = useMutation({
    mutationFn: (id: number) => revokeInstitutionInvitation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: institutionKeys.invitations }),
    onError: (e) => Alert.alert("İptal edilemedi", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  function confirmRevoke(id: number) {
    Alert.alert("Daveti iptal et", "Bu davet linki geçersiz olacak. Devam edilsin mi?", [
      { text: "Vazgeç", style: "cancel" },
      { text: "İptal et", style: "destructive", onPress: () => revokeMut.mutate(id) },
    ]);
  }

  function openCreate() { setName(""); setEmail(""); setCreated(null); setOpen(true); }

  return (
    <InstitutionScreen<InvitationListResponse>
      title="Öğretmen Davetleri"
      query={q}
      demoContext="invitations"
      headerRight={
        <Pressable onPress={openCreate} className="rounded-lg bg-brand-700 px-3 py-1.5 active:bg-brand-800">
          <Text className="text-xs font-semibold text-white">Yeni davet</Text>
        </Pressable>
      }
    >
      {(d) => (
        <>
          <Banner kind="info">Davet linki tek kullanımlıktır. Öğretmen linkten kayıt olup kurumuna bağlanır. İstediğin zaman iptal edebilirsin.</Banner>
          {d.items.length === 0 ? (
            <Empty text="Henüz davet yok. “Yeni davet” ile başla." />
          ) : (
            <View className="gap-2">{d.items.map((inv) => <Row key={inv.id} inv={inv} onRevoke={() => confirmRevoke(inv.id)} />)}</View>
          )}

          <FormSheet visible={open} title={created ? "Davet oluşturuldu" : "Öğretmen davet et"} onClose={() => setOpen(false)}>
            {created ? (
              <View className="gap-4 pb-2">
                <View className="items-center gap-2 py-2">
                  <View className="size-14 items-center justify-center rounded-full bg-emerald-100">
                    <Ionicons name="checkmark" size={30} color="#059669" />
                  </View>
                  <Text className="text-center text-base font-semibold text-slate-900">Davet hazır</Text>
                  <Text className="text-center text-sm text-slate-500">{created.full_name || created.email || "Açık davetiye"}</Text>
                </View>
                <View className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <Text className="text-[11px] text-slate-500" numberOfLines={2}>{created.signup_url}</Text>
                </View>
                <Pressable onPress={() => void Share.share({ message: created.signup_url })} className="flex-row items-center justify-center gap-2 rounded-xl bg-brand-700 py-3.5 active:bg-brand-800">
                  <Ionicons name="share-outline" size={18} color="#fff" />
                  <Text className="text-base font-semibold text-white">Linki paylaş</Text>
                </Pressable>
                <Pressable onPress={() => setOpen(false)} className="items-center rounded-xl border border-slate-300 py-3 active:bg-slate-50">
                  <Text className="text-base font-semibold text-slate-600">Tamam</Text>
                </Pressable>
              </View>
            ) : (
              <View className="gap-4 pb-2">
                <View className="gap-1">
                  <Text className="text-xs font-medium text-slate-600">Ad soyad (opsiyonel)</Text>
                  <TextInput value={name} onChangeText={setName} placeholder="Öğretmenin adı soyadı" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
                </View>
                <View className="gap-1">
                  <Text className="text-xs font-medium text-slate-600">E-posta (opsiyonel)</Text>
                  <TextInput value={email} onChangeText={setEmail} placeholder="ornek@eposta.com" placeholderTextColor="#94a3b8" autoCapitalize="none" keyboardType="email-address" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
                </View>
                <Text className="text-[11px] text-slate-400">E-posta belirtirsen davet o adrese kilitlenir. Boş bırakırsan açık (herkese açık tek kullanımlık) davet oluşur.</Text>
                <Pressable onPress={() => createMut.mutate()} disabled={createMut.isPending} className={cn("items-center rounded-xl py-3.5", createMut.isPending ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}>
                  <Text className="text-base font-semibold text-white">{createMut.isPending ? "Oluşturuluyor…" : "Davet oluştur"}</Text>
                </Pressable>
              </View>
            )}
          </FormSheet>
        </>
      )}
    </InstitutionScreen>
  );
}
