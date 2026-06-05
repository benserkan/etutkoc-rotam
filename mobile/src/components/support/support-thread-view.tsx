import * as React from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";

import type { SupportDetail } from "@/lib/support";
import { cn } from "@/lib/utils";
import { STATUS_TONE } from "./support-list-view";

const ROLE_TONE: Record<string, { bubble: string; name: string }> = {
  teacher: { bubble: "bg-sky-50", name: "text-sky-700" },
  institution_admin: { bubble: "bg-amber-50", name: "text-amber-700" },
  super_admin: { bubble: "bg-violet-50", name: "text-violet-700" },
};

function ago(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function SupportThreadView({
  data,
  busy,
  isTerminal,
  onReply,
  onWithdraw,
  onReview,
  onResolve,
}: {
  data: SupportDetail;
  busy: boolean;
  isTerminal: boolean;
  onReply: (body: string) => void;
  onWithdraw?: () => void;
  onReview?: () => void;
  onResolve?: () => void;
}) {
  const [text, setText] = React.useState("");
  const st = STATUS_TONE[data.status] ?? STATUS_TONE.open;
  const canManage = !!data.can_manage;
  const isMine = !canManage && data.target_user_id == null; // talep eden görünümü (kabaca)

  function send() {
    if (!text.trim()) return;
    onReply(text.trim());
    setText("");
  }

  return (
    <KeyboardAvoidingView className="flex-1" behavior={Platform.OS === "ios" ? "padding" : undefined} keyboardVerticalOffset={90}>
      <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-3" keyboardShouldPersistTaps="handled">
        {/* Başlık */}
        <View className="rounded-2xl border border-slate-200 bg-white p-4">
          <View className="flex-row items-start justify-between gap-2">
            <Text className="flex-1 text-base font-bold text-slate-900">{data.subject}</Text>
            <View className={cn("rounded-full px-2 py-0.5", st.bg)}>
              <Text className={cn("text-[11px] font-semibold", st.text)}>{data.status_label}</Text>
            </View>
          </View>
          <Text className="mt-1 text-xs text-slate-400">
            {data.category_label} · {data.requester_name}
          </Text>
        </View>

        {/* Mesajlar */}
        {data.messages.map((m) => {
          const tone = m.sender_role ? ROLE_TONE[m.sender_role] : undefined;
          return (
            <View key={m.id} className={cn("max-w-[85%] rounded-2xl p-3", m.is_me ? "self-end bg-brand-700" : cn("self-start", tone?.bubble ?? "bg-white"))}>
              {!m.is_me ? (
                <Text className={cn("text-[11px] font-semibold", tone?.name ?? "text-slate-500")}>{m.sender_name}</Text>
              ) : null}
              <Text className={cn("text-sm", m.is_me ? "text-white" : "text-slate-800")}>{m.body}</Text>
              <Text className={cn("mt-1 text-[10px]", m.is_me ? "text-brand-100" : "text-slate-400")}>{ago(m.created_at)}</Text>
            </View>
          );
        })}

        {/* Yönetim aksiyonları */}
        {canManage && !isTerminal ? (
          <View className="flex-row gap-2">
            {onReview ? (
              <Pressable onPress={onReview} disabled={busy} className="flex-1 items-center rounded-xl border border-amber-300 bg-amber-50 py-2.5 active:bg-amber-100">
                <Text className="text-sm font-semibold text-amber-700">İnceliyorum</Text>
              </Pressable>
            ) : null}
            {onResolve ? (
              <Pressable onPress={onResolve} disabled={busy} className="flex-1 items-center rounded-xl bg-emerald-600 py-2.5 active:bg-emerald-700">
                <Text className="text-sm font-semibold text-white">Çözümle</Text>
              </Pressable>
            ) : null}
          </View>
        ) : null}
        {isMine && !isTerminal && onWithdraw ? (
          <Pressable onPress={onWithdraw} disabled={busy} className="items-center rounded-xl border border-slate-300 py-2.5 active:bg-slate-50">
            <Text className="text-sm font-medium text-slate-600">Talebi geri çek</Text>
          </Pressable>
        ) : null}
      </ScrollView>

      {/* Yanıt kutusu */}
      {!isTerminal ? (
        <View className="flex-row items-end gap-2 border-t border-slate-200 bg-white px-3 py-2.5">
          <TextInput
            value={text}
            onChangeText={setText}
            placeholder="Yanıt yaz…"
            placeholderTextColor="#94a3b8"
            multiline
            className="max-h-24 flex-1 rounded-2xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
          />
          <Pressable
            onPress={send}
            disabled={busy || !text.trim()}
            className={cn("h-11 items-center justify-center rounded-2xl px-4", busy || !text.trim() ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
          >
            <Text className="text-sm font-semibold text-white">Gönder</Text>
          </Pressable>
        </View>
      ) : (
        <View className="border-t border-slate-200 bg-white px-4 py-3">
          <Text className="text-center text-xs text-slate-400">Bu talep kapatıldı.</Text>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}
