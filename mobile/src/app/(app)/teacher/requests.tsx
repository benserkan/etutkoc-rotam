import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Modal,
  Pressable,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { TeacherRequestsView } from "@/components/teacher/teacher-requests-view";
import { ApiError } from "@/lib/api";
import {
  approveTeacherRequest,
  getTeacherRequests,
  rejectTeacherRequest,
  respondTeacherRequest,
  teacherRequestKeys,
  type TeacherRequestListItem,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Filter = "pending" | "all";
type ActionType = "reject" | "respond";

export default function TeacherRequestsTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = React.useState<Filter>("pending");
  const [action, setAction] = React.useState<{ item: TeacherRequestListItem; type: ActionType } | null>(null);
  const [text, setText] = React.useState("");

  const q = useQuery({
    queryKey: teacherRequestKeys.list(filter),
    queryFn: () => getTeacherRequests(filter),
  });

  function invalidate() {
    qc.invalidateQueries({ queryKey: ["teacher", "requests"] });
    qc.invalidateQueries({ queryKey: ["teacher", "students"] });
    qc.invalidateQueries({ queryKey: ["teacher", "student"] });
  }
  function onErr(e: unknown) {
    const msg = e instanceof ApiError ? e.message : "İşlem başarısız";
    Alert.alert("İşlem başarısız", msg);
  }

  const approveMut = useMutation({
    mutationFn: (id: number) => approveTeacherRequest(id),
    onSuccess: invalidate,
    onError: onErr,
  });
  const rejectMut = useMutation({
    mutationFn: (v: { id: number; reason: string }) => rejectTeacherRequest(v.id, v.reason),
    onSuccess: () => { invalidate(); closeAction(); },
    onError: onErr,
  });
  const respondMut = useMutation({
    mutationFn: (v: { id: number; response: string }) => respondTeacherRequest(v.id, v.response),
    onSuccess: () => { invalidate(); closeAction(); },
    onError: onErr,
  });
  const busy = approveMut.isPending || rejectMut.isPending || respondMut.isPending;

  function closeAction() {
    setAction(null);
    setText("");
  }
  function onApprove(r: TeacherRequestListItem) {
    Alert.alert("Talebi onayla", "Bu değişiklik öğrencinin programına uygulanacak. Onaylıyor musun?", [
      { text: "Vazgeç", style: "cancel" },
      { text: "Onayla", onPress: () => approveMut.mutate(r.id) },
    ]);
  }
  function submitAction() {
    if (!action) return;
    const t = text.trim();
    if (!t) {
      Alert.alert("Eksik", action.type === "reject" ? "Red gerekçesi gerekli." : "Yanıt metni gerekli.");
      return;
    }
    if (action.type === "reject") rejectMut.mutate({ id: action.item.id, reason: t });
    else respondMut.mutate({ id: action.item.id, response: t });
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-4 py-3">
        <Text className="text-xl font-bold text-slate-900">Talepler</Text>
        <Text className="mt-0.5 text-xs text-slate-500">Öğrencilerinin program istekleri ve soruları.</Text>
      </View>

      {/* Filtre */}
      <View className="flex-row gap-2 px-4 pb-2">
        {(["pending", "all"] as Filter[]).map((f) => {
          const active = f === filter;
          return (
            <Pressable
              key={f}
              onPress={() => setFilter(f)}
              className={cn("rounded-full border px-4 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white")}
            >
              <Text className={cn("text-xs font-semibold", active ? "text-brand-700" : "text-slate-500")}>
                {f === "pending" ? "Bekleyenler" : "Tümü"}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Talepler yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <TeacherRequestsView
          data={q.data}
          busy={busy}
          onApprove={onApprove}
          onReject={(r) => setAction({ item: r, type: "reject" })}
          onRespond={(r) => setAction({ item: r, type: "respond" })}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
        />
      )}

      {/* Red gerekçesi / yanıt modalı */}
      <Modal visible={action != null} transparent statusBarTranslucent animationType="fade" onRequestClose={closeAction}>
        <KeyboardAvoidingView behavior="padding" className="flex-1 justify-end bg-black/40">
          <View className="rounded-t-3xl bg-white p-5 pb-8">
            <Text className="text-base font-bold text-slate-900">
              {action?.type === "reject" ? "Talebi reddet" : "Soruyu yanıtla"}
            </Text>
            <Text className="mt-1 text-xs text-slate-500">
              {action?.type === "reject" ? "Öğrenciye iletilecek red gerekçesi." : "Öğrenciye iletilecek yanıt."}
            </Text>
            <TextInput
              value={text}
              onChangeText={setText}
              placeholder={action?.type === "reject" ? "Örn. Bu hafta tempoyu korumamız gerek." : "Yanıtın..."}
              placeholderTextColor="#94a3b8"
              multiline
              autoFocus
              className="mt-3 min-h-[88px] rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900"
            />
            <View className="mt-4 flex-row gap-2">
              <Pressable onPress={closeAction} className="flex-1 items-center rounded-xl border border-slate-200 py-3 active:bg-slate-50">
                <Text className="text-sm font-semibold text-slate-600">Vazgeç</Text>
              </Pressable>
              <Pressable
                onPress={submitAction}
                disabled={busy}
                className={cn("flex-1 items-center rounded-xl py-3", action?.type === "reject" ? "bg-rose-600 active:bg-rose-700" : "bg-brand-700 active:bg-brand-800", busy && "opacity-50")}
              >
                <Text className="text-sm font-semibold text-white">{action?.type === "reject" ? "Reddet" : "Gönder"}</Text>
              </Pressable>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}
