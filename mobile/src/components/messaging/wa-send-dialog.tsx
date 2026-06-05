import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError } from "@/lib/api";
import {
  buildWaLink,
  getMessagingTarget,
  getMessagingTemplates,
  messagingKeys,
  type WaTemplateBrief,
} from "@/lib/messaging";
import { cn } from "@/lib/utils";

interface Props {
  visible: boolean;
  onClose: () => void;
  targetUserId: number;
  targetLabel?: string; // "öğrenci" | "veli" (gösterim)
  defaultCategory?: string; // "ogrenci" | "veli" ...
}

export function WaSendDialog({ visible, onClose, targetUserId, targetLabel, defaultCategory = "ogrenci" }: Props) {
  const [category, setCategory] = React.useState<string | null>(defaultCategory);
  const [templateId, setTemplateId] = React.useState<number | null>(null);
  const [vars, setVars] = React.useState<Record<string, string>>({});
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const templatesQ = useQuery({
    queryKey: messagingKeys.templates(category),
    queryFn: () => getMessagingTemplates(category),
    enabled: visible,
  });
  const targetQ = useQuery({
    queryKey: messagingKeys.target(targetUserId),
    queryFn: () => getMessagingTarget(targetUserId),
    enabled: visible && targetUserId > 0,
  });

  const items = templatesQ.data?.items ?? [];
  const categories = templatesQ.data?.categories ?? {};
  const selected = items.find((t) => t.id === templateId) ?? null;

  // Modal kapanınca sıfırla
  React.useEffect(() => {
    if (!visible) {
      setTemplateId(null);
      setVars({});
      setNote("");
      setCategory(defaultCategory);
    }
  }, [visible, defaultCategory]);

  function selectTemplate(t: WaTemplateBrief) {
    setTemplateId(t.id);
    const init: Record<string, string> = {};
    for (const v of t.variables) init[v.key] = v.example ?? "";
    setVars(init);
    setNote("");
  }

  function preview(): string {
    if (!selected) return "";
    let text = selected.content_template;
    for (const v of selected.variables) {
      text = text.split(`{{${v.key}}}`).join(vars[v.key] || v.example || `{${v.key}}`);
    }
    if (selected.allow_freeform_note && note.trim()) text += `\n\n${note.trim()}`;
    return text;
  }

  async function send() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await buildWaLink({
        template_id: selected.id,
        target_user_id: targetUserId,
        variables: vars,
        freeform_note: selected.allow_freeform_note && note.trim() ? note.trim() : undefined,
      });
      const ok = await Linking.canOpenURL(res.wa_url);
      if (!ok) {
        Alert.alert("WhatsApp bulunamadı", "Bu cihazda WhatsApp yüklü değil.");
        return;
      }
      await Linking.openURL(res.wa_url);
      onClose();
    } catch (e) {
      const err = e as ApiError;
      Alert.alert("Gönderilemedi", err?.message ?? "Bir hata oluştu.");
    } finally {
      setBusy(false);
    }
  }

  const target = targetQ.data;
  const catKeys = Object.keys(categories);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
        {/* Başlık */}
        <View className="flex-row items-center justify-between border-b border-slate-200 px-4 py-3">
          <View className="flex-row items-center gap-2">
            <Ionicons name="logo-whatsapp" size={22} color="#16a34a" />
            <Text className="text-base font-semibold text-slate-800">WhatsApp gönder</Text>
          </View>
          <Pressable onPress={onClose} hitSlop={8} className="size-9 items-center justify-center rounded-full active:bg-slate-200">
            <Ionicons name="close" size={24} color="#334155" />
          </Pressable>
        </View>

        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} className="flex-1">
          <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
            {/* Hedef */}
            <View className="rounded-2xl border border-slate-200 bg-white p-4">
              <View className="flex-row items-center gap-2">
                <Ionicons name={target?.phone_verified ? "shield-checkmark" : "shield-outline"} size={18} color={target?.phone_verified ? "#16a34a" : "#d97706"} />
                <Text className="text-sm font-semibold text-slate-800">{target?.full_name ?? targetLabel ?? "Hedef"}</Text>
              </View>
              {target ? (
                <Text className="mt-1 text-xs text-slate-500">{target.phone_masked || "telefon yok"}</Text>
              ) : null}
              {target && !target.phone_verified ? (
                <Text className="mt-1 text-[11px] text-amber-600">
                  Telefon doğrulanmamış — gönderim başarısız olabilir.
                </Text>
              ) : null}
            </View>

            {/* Kategori filtresi */}
            {catKeys.length > 1 ? (
              <View className="flex-row flex-wrap gap-2">
                {catKeys.map((k) => {
                  const active = k === category;
                  return (
                    <Pressable
                      key={k}
                      onPress={() => { setCategory(k); setTemplateId(null); }}
                      className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white")}
                    >
                      <Text className={cn("text-xs font-medium", active ? "text-brand-700" : "text-slate-600")}>{categories[k]}</Text>
                    </Pressable>
                  );
                })}
              </View>
            ) : null}

            {/* Şablon seçimi */}
            {templatesQ.isLoading ? (
              <ActivityIndicator color="#0e7490" />
            ) : items.length === 0 ? (
              <Text className="px-1 text-sm text-slate-500">Bu kategori için şablon yok.</Text>
            ) : !selected ? (
              <View className="gap-2">
                <Text className="px-1 text-sm font-semibold text-slate-700">Bir şablon seç</Text>
                {items.map((t) => (
                  <Pressable
                    key={t.id}
                    onPress={() => selectTemplate(t)}
                    className="rounded-2xl border border-slate-200 bg-white p-3.5 active:bg-slate-50"
                  >
                    <Text className="text-sm font-semibold text-slate-800">{t.name_tr}</Text>
                    <Text className="mt-1 text-xs text-slate-500" numberOfLines={2}>{t.content_template}</Text>
                  </Pressable>
                ))}
              </View>
            ) : (
              <View className="gap-4">
                {/* Seçili şablon başlığı + değiştir */}
                <View className="flex-row items-center justify-between">
                  <Text className="text-sm font-semibold text-slate-800">{selected.name_tr}</Text>
                  <Pressable onPress={() => setTemplateId(null)} hitSlop={6}>
                    <Text className="text-xs font-medium text-brand-700">Değiştir</Text>
                  </Pressable>
                </View>

                {/* Değişkenler */}
                {selected.variables.length > 0 ? (
                  <View className="gap-3">
                    {selected.variables.map((v) => (
                      <View key={v.key}>
                        <Text className="mb-1 text-xs font-medium text-slate-600">{v.label_tr}</Text>
                        <TextInput
                          value={vars[v.key] ?? ""}
                          onChangeText={(txt) => setVars((p) => ({ ...p, [v.key]: txt }))}
                          placeholder={v.example}
                          placeholderTextColor="#94a3b8"
                          className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
                        />
                      </View>
                    ))}
                  </View>
                ) : null}

                {/* Serbest not */}
                {selected.allow_freeform_note ? (
                  <View>
                    <Text className="mb-1 text-xs font-medium text-slate-600">Ek not (opsiyonel)</Text>
                    <TextInput
                      value={note}
                      onChangeText={setNote}
                      placeholder="Mesaja eklenecek kısa not"
                      placeholderTextColor="#94a3b8"
                      multiline
                      className="min-h-[64px] rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900"
                    />
                  </View>
                ) : null}

                {/* Önizleme */}
                <View className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3.5">
                  <Text className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">Önizleme</Text>
                  <Text className="text-sm leading-relaxed text-emerald-950">{preview()}</Text>
                </View>
              </View>
            )}
          </ScrollView>
        </KeyboardAvoidingView>

        {/* Gönder */}
        {selected ? (
          <View className="border-t border-slate-200 bg-white px-4 py-3">
            <Pressable
              onPress={send}
              disabled={busy}
              className={cn("flex-row items-center justify-center gap-2 rounded-xl py-3.5", busy ? "bg-emerald-400" : "bg-emerald-600 active:bg-emerald-700")}
            >
              {busy ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <>
                  <Ionicons name="logo-whatsapp" size={20} color="#fff" />
                  <Text className="text-[15px] font-semibold text-white">WhatsApp&apos;ı aç</Text>
                </>
              )}
            </Pressable>
            <Text className="mt-2 text-center text-[11px] text-slate-400">
              Mesaj hazır açılır; son &quot;gönder&quot; tuşuna sen basacaksın.
            </Text>
          </View>
        ) : null}
      </SafeAreaView>
    </Modal>
  );
}
