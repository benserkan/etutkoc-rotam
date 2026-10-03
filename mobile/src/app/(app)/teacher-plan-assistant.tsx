/**
 * Paket asistanı — mobil sohbet ekranı (2026-10-03; web PlanAssistant paritesi).
 * Hazır sorular hesabın durumundan anında cevaplanır; serbest soru yapay zekâya
 * gider; "Bize yaz" konuşmayı destek ekibine aktarır. Kanal ios/android —
 * sunucu web ödemesinden hiç söz etmez (App Store 3.1.1).
 */
import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  askPlanAssistant,
  getPlanAssistant,
  handoffPlanAssistant,
  planAssistantKeys,
  type PlanAssistantAction,
  type PlanAssistantMessage,
} from "@/lib/plan-assistant";
import { cn } from "@/lib/utils";

type Msg = PlanAssistantMessage & { action?: PlanAssistantAction | null; pending?: boolean };

export default function PlanAssistantScreen() {
  const stateQ = useQuery({ queryKey: planAssistantKeys.state, queryFn: getPlanAssistant, staleTime: 30_000 });
  const [msgs, setMsgs] = React.useState<Msg[]>([]);
  const [input, setInput] = React.useState("");
  const [used, setUsed] = React.useState<string[]>([]);
  const [handoff, setHandoff] = React.useState(false);
  const [handoffText, setHandoffText] = React.useState("");
  const [done, setDone] = React.useState<string | null>(null);
  const scrollRef = React.useRef<ScrollView>(null);

  const history = (): PlanAssistantMessage[] =>
    msgs.filter((m) => !m.pending).map((m) => ({ role: m.role, text: m.text }));

  const ask = useMutation({
    mutationFn: (b: { chip?: string; question?: string; label: string }) =>
      askPlanAssistant({ chip: b.chip, question: b.question, history: history() }),
    onMutate: (b) =>
      setMsgs((m) => [...m, { role: "user", text: b.label }, { role: "assistant", text: "", pending: true }]),
    onSuccess: (res) =>
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "assistant", text: res.answer, action: res.action }]),
    onError: () =>
      setMsgs((m) => [
        ...m.filter((x) => !x.pending),
        {
          role: "assistant",
          text: "Bağlantıda bir sorun oldu. Tekrar dene ya da 'Bize yaz' ile ekibimize ilet.",
          action: { type: "handoff", label: "Bize yaz" },
        },
      ]),
  });

  const send = useMutation({
    mutationFn: () => handoffPlanAssistant({ message: handoffText.trim(), transcript: history() }),
    onSuccess: (res) => {
      setDone(res.message);
      setHandoff(false);
      setHandoffText("");
    },
  });

  const chips = (stateQ.data?.chips ?? []).filter((c) => !used.includes(c.id));

  function onAction(a: PlanAssistantAction) {
    if (a.type === "select_plan" && a.plan) {
      router.replace({ pathname: "/teacher-plan", params: { select: a.plan } });
    } else if (a.type === "handoff") {
      setHandoff(true);
    }
  }

  function submit() {
    const q = input.trim();
    if (!q || ask.isPending) return;
    setInput("");
    ask.mutate({ question: q, label: q });
  }

  return (
    <SafeAreaView edges={["top", "bottom"]} className="flex-1 bg-white">
      <View className="flex-row items-center gap-3 bg-brand-700 px-4 py-3">
        <Pressable onPress={() => router.back()} hitSlop={10} accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={24} color="#fff" />
        </Pressable>
        <View className="h-9 w-9 items-center justify-center rounded-full bg-white/20">
          <Ionicons name="sparkles" size={18} color="#fff" />
        </View>
        <View className="flex-1">
          <Text className="text-base font-bold text-white">Paket asistanı</Text>
          <View className="flex-row items-center gap-1.5">
            <View className="h-2 w-2 rounded-full bg-emerald-400" />
            <Text className="text-xs text-cyan-100">Hazır sorulara anında cevap</Text>
          </View>
        </View>
      </View>

      <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView
          ref={scrollRef}
          className="flex-1"
          contentContainerClassName="gap-3 px-4 py-4"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}
          keyboardShouldPersistTaps="handled"
        >
          {stateQ.isLoading ? (
            <ActivityIndicator color="#0e7490" />
          ) : (
            <Bubble role="assistant" text={stateQ.data?.greeting ?? "Merhaba! Paket ya da kredi hakkında ne sormak istersin?"} />
          )}
          {msgs.map((m, i) => (
            <View key={i} className="gap-2">
              {m.pending ? (
                <View className="flex-row items-center gap-2 self-start rounded-2xl bg-slate-100 px-4 py-3">
                  <ActivityIndicator size="small" color="#64748b" />
                  <Text className="text-sm text-slate-500">Düşünüyor…</Text>
                </View>
              ) : (
                <Bubble role={m.role} text={m.text} />
              )}
              {m.action?.label && m.action.type !== "open" ? (
                <Pressable
                  onPress={() => onAction(m.action!)}
                  className="self-start rounded-full border border-brand-600 px-4 py-2 active:bg-brand-50"
                >
                  <Text className="text-sm font-semibold text-brand-700">{m.action.label}</Text>
                </Pressable>
              ) : null}
            </View>
          ))}

          {done ? (
            <View className="rounded-2xl bg-emerald-600 px-4 py-3">
              <Text className="text-sm text-white">{done}</Text>
            </View>
          ) : null}

          {handoff ? (
            <View className="gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <Text className="text-sm font-bold text-slate-900">Ekibimize yaz</Text>
              <Text className="text-xs text-slate-500">
                Bu konuşma da mesajınla birlikte iletilir. Cevabı Destek ekranından takip edersin.
              </Text>
              <TextInput
                value={handoffText}
                onChangeText={setHandoffText}
                placeholder="Sorununu kısaca anlat…"
                placeholderTextColor="#94a3b8"
                multiline
                maxLength={2000}
                className="min-h-[80px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-base text-slate-900"
              />
              {send.isError ? <Text className="text-xs text-rose-700">Gönderilemedi, tekrar dene.</Text> : null}
              <View className="flex-row justify-end gap-2">
                <Pressable onPress={() => setHandoff(false)} className="rounded-full px-4 py-2.5">
                  <Text className="text-sm font-semibold text-slate-600">Vazgeç</Text>
                </Pressable>
                <Pressable
                  disabled={handoffText.trim().length < 3 || send.isPending}
                  onPress={() => send.mutate()}
                  className={cn(
                    "rounded-full px-5 py-2.5",
                    handoffText.trim().length < 3 ? "bg-slate-300" : "bg-brand-700 active:bg-brand-800",
                  )}
                >
                  <Text className="text-sm font-bold text-white">{send.isPending ? "Gönderiliyor…" : "Gönder"}</Text>
                </Pressable>
              </View>
            </View>
          ) : null}

          {chips.length > 0 && !ask.isPending ? (
            <View className="flex-row flex-wrap gap-2 pt-1">
              {chips.map((c) => (
                <Pressable
                  key={c.id}
                  onPress={() => {
                    setUsed((u) => [...u, c.id]);
                    if (c.id === "human") setHandoff(true);
                    else ask.mutate({ chip: c.id, label: c.label });
                  }}
                  className="rounded-full border border-brand-600/40 bg-white px-3.5 py-2 active:bg-brand-50"
                >
                  <Text className="text-sm text-brand-800">{c.label}</Text>
                </Pressable>
              ))}
            </View>
          ) : null}
        </ScrollView>

        <View className="flex-row items-end gap-2 border-t border-slate-200 bg-white px-3 py-3">
          <TextInput
            value={input}
            onChangeText={setInput}
            onSubmitEditing={submit}
            placeholder="Sorunu yaz…"
            placeholderTextColor="#94a3b8"
            maxLength={800}
            returnKeyType="send"
            className="h-12 flex-1 rounded-full border border-slate-300 bg-white px-4 text-base text-slate-900"
          />
          <Pressable
            onPress={submit}
            disabled={!input.trim() || ask.isPending}
            accessibilityLabel="Soruyu gönder"
            className={cn(
              "h-12 w-12 items-center justify-center rounded-full",
              input.trim() ? "bg-brand-700 active:bg-brand-800" : "bg-slate-300",
            )}
          >
            <Ionicons name="send" size={18} color="#fff" />
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ role, text }: { role: "user" | "assistant"; text: string }) {
  return (
    <View
      className={cn(
        "max-w-[85%] rounded-2xl px-4 py-3",
        role === "user" ? "self-end rounded-br-md bg-brand-700" : "self-start rounded-bl-md bg-slate-100",
      )}
    >
      <Text className={cn("text-[15px] leading-6", role === "user" ? "text-white" : "text-slate-800")}>{text}</Text>
    </View>
  );
}
