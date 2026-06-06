import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FormSheet } from "@/components/ui/form-sheet";
import { SupportListView } from "@/components/support/support-list-view";
import { ApiError } from "@/lib/api";
import { createParentCoachRequest, getParentDashboard } from "@/lib/parent";
import { getMyRequests, supportKeys } from "@/lib/support";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { v: "progress_question", label: "Gidişat sorusu" },
  { v: "exam_comment", label: "Deneme yorumu" },
  { v: "other", label: "Diğer" },
];

export default function ParentSupportTab() {
  const qc = useQueryClient();
  const [open, setOpen] = React.useState(false);

  const mine = useQuery({ queryKey: supportKeys.mine, queryFn: getMyRequests });
  const dash = useQuery({ queryKey: ["parent", "dashboard"], queryFn: getParentDashboard });
  const children = (dash.data?.children ?? []).map((c) => ({ id: c.student_id, name: c.full_name }));

  const [childId, setChildId] = React.useState<number | null>(null);
  const [category, setCategory] = React.useState("progress_question");
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");

  React.useEffect(() => {
    if (childId === null && children.length === 1) setChildId(children[0].id);
  }, [children, childId]);

  const createMut = useMutation({
    mutationFn: () => createParentCoachRequest(childId!, { category, subject: subject.trim(), body: body.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: supportKeys.mine });
      setOpen(false); setSubject(""); setBody(""); setCategory("progress_question");
    },
    onError: (e) => Alert.alert("Gönderilemedi", e instanceof ApiError ? e.message : "İşlem başarısız."),
  });

  const canSend = childId !== null && subject.trim().length > 0 && body.trim().length > 0 && !createMut.isPending;

  if (mine.isLoading) {
    return (
      <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      </SafeAreaView>
    );
  }
  if (mine.isError || !mine.data) {
    return (
      <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => mine.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-4 pt-3 pb-1">
        <Text className="text-xl font-bold text-slate-900">Koça Talep</Text>
        <Text className="mt-0.5 text-xs text-slate-500">Çocuğunuzun koçuna soru/talep iletin; yanıtları buradan izleyin.</Text>
      </View>
      <Pressable
        onPress={() => setOpen(true)}
        className="mx-4 mt-2 flex-row items-center justify-center gap-2 rounded-2xl bg-brand-700 py-3.5 active:bg-brand-800"
      >
        <Ionicons name="add-circle-outline" size={20} color="#fff" />
        <Text className="text-base font-semibold text-white">Koça yeni soru</Text>
      </Pressable>

      <ScrollView className="flex-1">
        <SupportListView
          view="mine"
          onChangeView={() => {}}
          showInbox={false}
          canCreate={false}
          data={mine.data}
          createBusy={false}
          onCreate={() => {}}
          onOpen={(id) => router.push({ pathname: "/support-thread", params: { id: String(id) } })}
        />
      </ScrollView>

      <FormSheet visible={open} title="Koça yeni soru / talep" onClose={() => setOpen(false)}>
        <View className="gap-4 pb-2">
          {children.length > 1 ? (
            <View className="gap-1.5">
              <Text className="text-xs font-medium text-slate-600">Çocuk</Text>
              <View className="flex-row flex-wrap gap-2">
                {children.map((c) => {
                  const active = childId === c.id;
                  return (
                    <Pressable key={c.id} onPress={() => setChildId(c.id)}
                      className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                      <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{c.name}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ) : null}
          <View className="gap-1.5">
            <Text className="text-xs font-medium text-slate-600">Konu türü</Text>
            <View className="flex-row flex-wrap gap-2">
              {CATEGORIES.map((c) => {
                const active = category === c.v;
                return (
                  <Pressable key={c.v} onPress={() => setCategory(c.v)}
                    className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                    <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{c.label}</Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Başlık</Text>
            <TextInput value={subject} onChangeText={setSubject} maxLength={200}
              placeholder="örn. Son deneme hakkında" placeholderTextColor="#94a3b8"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
          </View>
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Mesajınız</Text>
            <TextInput value={body} onChangeText={setBody} maxLength={4000} multiline
              placeholder="Koçunuza iletmek istediğiniz soru/talep…" placeholderTextColor="#94a3b8"
              className="min-h-[88px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
          </View>
          <Pressable onPress={() => createMut.mutate()} disabled={!canSend}
            className={cn("items-center rounded-xl py-3.5", canSend ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}>
            <Text className="text-base font-semibold text-white">{createMut.isPending ? "Gönderiliyor…" : "Koça gönder"}</Text>
          </Pressable>
        </View>
      </FormSheet>
    </SafeAreaView>
  );
}
