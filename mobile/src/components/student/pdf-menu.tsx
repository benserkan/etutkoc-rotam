import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { openStudentPdf, type PdfKind } from "@/lib/student-progress";

/**
 * "PDF / Paylaş" (2026-10-21) — web'deki Yazdır + Paylaş menüsünün mobil karşılığı.
 * PDF sunucuda üretilir, telefonun PDF görüntüleyicisinde açılır; oradaki paylaş simgesiyle
 * WhatsApp'a gönderilir ya da kaydedilir (uygulamaya yeni yerel modül gerekmez).
 */
export function PdfMenuButton({ dayDate, weekStart, compact = false }: { dayDate: string; weekStart: string; compact?: boolean }) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState<PdfKind | null>(null);

  async function go(kind: PdfKind) {
    setBusy(kind);
    try {
      await openStudentPdf(kind, kind === "day" ? dayDate : kind === "week" ? weekStart : undefined);
      setOpen(false);
    } catch {
      Alert.alert("PDF açılamadı", "Bağlantını kontrol edip tekrar dene.");
    } finally {
      setBusy(null);
    }
  }

  const items: { kind: PdfKind; icon: keyof typeof Ionicons.glyphMap; title: string; desc: string }[] = [
    { kind: "day", icon: "today-outline", title: "Günün programı", desc: "Günün görevleri — doğru/yanlış yazma alanlı" },
    { kind: "week", icon: "calendar-outline", title: "Haftalık program", desc: "7 günlük plan, yatay sayfa" },
    { kind: "exams", icon: "trophy-outline", title: "Deneme sonuçlarım", desc: "Tüm denemelerin netleri, ders ders" },
  ];

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={6}
        accessibilityLabel="PDF olarak paylaş ya da kaydet"
        className={`flex-row items-center gap-1.5 rounded-full border border-slate-300 bg-white active:bg-slate-100 ${compact ? "px-2.5 py-1.5" : "px-3.5 py-2"}`}
      >
        <Ionicons name="share-social-outline" size={16} color="#0e7490" />
        <Text className="text-xs font-semibold text-brand-700">PDF / Paylaş</Text>
      </Pressable>
      <FormSheet visible={open} title="PDF olarak paylaş" onClose={() => setOpen(false)}>
        <Text className="mb-3 text-sm text-slate-500">
          PDF telefonunda açılır. Açılan sayfadaki paylaş simgesiyle WhatsApp&apos;a gönderebilir ya da kaydedebilirsin.
        </Text>
        <View className="gap-2.5">
          {items.map((it) => (
            <Pressable
              key={it.kind}
              onPress={() => void go(it.kind)}
              disabled={busy != null}
              className="flex-row items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 active:bg-slate-50"
            >
              <View className="size-10 items-center justify-center rounded-xl bg-brand-700">
                <Ionicons name={it.icon} size={20} color="#fff" />
              </View>
              <View className="flex-1">
                <Text className="text-[15px] font-semibold text-slate-900">{it.title}</Text>
                <Text className="text-xs text-slate-500">{it.desc}</Text>
              </View>
              {busy === it.kind ? <ActivityIndicator color="#0e7490" /> : <Ionicons name="open-outline" size={18} color="#94a3b8" />}
            </Pressable>
          ))}
        </View>
      </FormSheet>
    </>
  );
}
