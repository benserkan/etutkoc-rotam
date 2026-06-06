import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

type Item = { label: string; sub: string; icon: keyof typeof Ionicons.glyphMap; path: string };

const GROUPS: { title: string; items: Item[] }[] = [
  {
    title: "Kişiler",
    items: [
      { label: "Öğretmen Davetleri", sub: "Koç davet et, linki paylaş", icon: "person-add-outline", path: "/institution-invitations" },
    ],
  },
  {
    title: "Analiz",
    items: [
      { label: "Program Uyumu", sub: "Tamamlama + doğruluk + boş program", icon: "clipboard-outline", path: "/institution-compliance" },
      { label: "Akademik Çıktı", sub: "Deneme net başarısı + trend", icon: "school-outline", path: "/institution-academic" },
      { label: "Risk Paneli", sub: "Risk altındaki öğrenciler", icon: "warning-outline", path: "/institution-at-risk" },
      { label: "Kohort Analizi", sub: "Sınıf/alan/hedef grupları", icon: "people-outline", path: "/institution-cohorts" },
      { label: "Aktivite Haritası", sub: "Koç giriş/görev/not ısı haritası", icon: "grid-outline", path: "/institution-heatmap" },
      { label: "Tükenmişlik Panosu", sub: "Yük/düşüş sinyalleri", icon: "flame-outline", path: "/institution-burnout" },
      { label: "Öğretmen Karnesi", sub: "Etkililik skoru", icon: "ribbon-outline", path: "/institution-scorecard" },
      { label: "Hedef Analizi", sub: "Hedef kapsama + ilerleme", icon: "flag-outline", path: "/institution-goals" },
      { label: "Haftalık Özet", sub: "Yönetici özet arşivi", icon: "newspaper-outline", path: "/institution-digest" },
      { label: "Veli Güveni", sub: "Kapsama + bildirim teslimi", icon: "heart-outline", path: "/institution-parent-trust" },
    ],
  },
  {
    title: "Üyelik",
    items: [
      { label: "Kredi Kullanımı", sub: "Yapay zekâ kredi tüketimi", icon: "flash-outline", path: "/institution-usage" },
      { label: "Limitler", sub: "Koç/öğrenci kotaları", icon: "speedometer-outline", path: "/institution-quota" },
      { label: "Hesap Ayarları", sub: "Paket + yükseltme talebi", icon: "settings-outline", path: "/institution-subscription" },
    ],
  },
  {
    title: "Genel",
    items: [
      { label: "Aktivite Akışı", sub: "Kim katıldı, kim yükseltti", icon: "pulse-outline", path: "/institution-activity" },
    ],
  },
];

function MenuItem({ item }: { item: Item }) {
  return (
    <Pressable
      onPress={() => router.push(item.path as never)}
      className="flex-row items-center gap-3 rounded-xl border border-slate-200 bg-white px-3 py-3 active:bg-slate-50"
    >
      <View className="size-9 items-center justify-center rounded-full bg-brand-50">
        <Ionicons name={item.icon} size={18} color="#0e7490" />
      </View>
      <View className="flex-1">
        <Text className="text-[15px] font-semibold text-slate-900">{item.label}</Text>
        <Text className="text-[11px] text-slate-400" numberOfLines={1}>{item.sub}</Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
    </Pressable>
  );
}

export default function InstitutionAnalizHub() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-5 pb-1 pt-3">
        <Text className="text-2xl font-extrabold text-slate-900">Analiz & Yönetim</Text>
      </View>
      <ScrollView className="flex-1" contentContainerClassName="px-4 py-3 gap-4">
        {GROUPS.map((g) => (
          <View key={g.title} className="gap-2">
            <Text className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">{g.title}</Text>
            <View className="gap-2">{g.items.map((it) => <MenuItem key={it.path} item={it} />)}</View>
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
